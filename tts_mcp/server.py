"""MCP adapter (layer 3, REQ-MCP): exposes comms/access as tools. Argument handling only, no logic."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from tts_mcp import access
from tts_mcp.comms import TTSConnection, TTSError

INSTRUCTIONS = """\
Access to a running Tabletop Simulator (TTS) game through its External Editor API.
Start with tts_status to see whether TTS is reachable and which game is loaded.
run_lua is the universal tool: anything the TTS Lua API can do, it can do.
Game-specific knowledge (board layout, rules) comes from game skills, not from this server.
"""


async def _call(fn: Callable[..., Any], *args: Any) -> Any:
    """Run a blocking TTS call off the event loop; turn TTS errors into readable tool errors."""
    try:
        return await anyio.to_thread.run_sync(fn, *args)
    except TTSError as e:
        raise ToolError(f"{type(e).__name__}: {e}") from e


def create_server(conn: TTSConnection) -> MCPServer:
    server = MCPServer("tts-mcp", instructions=INSTRUCTIONS)

    @server.tool()
    async def run_lua(code: str) -> Any:
        """Execute Lua in the TTS Global script context and return the result.

        Use `return` to get a value back. Tables arrive as JSON objects/arrays; numbers, strings,
        booleans and nil (null) work too. TTS objects (userdata) cannot be returned directly:
        return their fields instead, e.g. `local o = getObjectFromGUID("abc123")
        return {name = o.getName(), pos = o.getPosition()}`.
        Lua runtime and syntax errors come back as tool errors with the TTS message.
        Changes made here are visible to the player immediately, so act deliberately.
        """
        return await _call(conn.execute_lua, code)

    @server.tool()
    async def get_scripts() -> Any:
        """Read the loaded game's Lua scripts and UI XML (read-only).

        Returns {"global": {"script", "ui"}, "objects": [{"guid", "name", "type", "script", "ui"}]},
        listing only objects whose script or UI is not empty.
        """
        return await _call(access.get_scripts, conn)

    @server.tool()
    async def get_events(since: int = 0) -> Any:
        """Messages TTS sent on its own since sequence number `since`: print output, Lua errors,
        game loaded/saved, objects created.

        Returns {"events": [{"seq", "time", "kind", ...}], "last_seq"}. Pass `last_seq` as `since`
        next time to get only new events. Only events received while this server runs are available.
        """
        return await _call(access.get_events, conn, since)

    @server.tool()
    async def tts_status() -> Any:
        """Check whether TTS is reachable; if so, return the loaded game's name, object count and
        seated players (colour, host). Never fails: an unreachable TTS is reported, not raised.
        """
        return await _call(access.status, conn)

    return server


def main() -> None:
    with TTSConnection() as conn:
        create_server(conn).run("stdio")
