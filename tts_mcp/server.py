"""MCP adapter (layer 3, REQ-MCP): exposes comms, access and table as tools. Argument handling only."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from tts_mcp import access, table
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
    except (TTSError, ValueError) as e:
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

    # 3D controls (REQ-OBJ, REQ-DICE). Positions, rotations and distances are TTS world units,
    # given as [x, y, z]; y is up. Rotations are Euler angles in degrees.

    @server.tool()
    async def list_objects(
        name: str | None = None, type: str | None = None, tag: str | None = None, tint: str | None = None
    ) -> Any:
        """List objects on the table: guid, name, description, type, tags, tint (hex), position, rotation,
        locked, resting. Optional filters: name (case-insensitive substring), type (e.g. "Dice"), tag,
        tint (hex, e.g. "bbbbbb"). GUIDs change when a game is loaded, so look objects up each session.
        """
        return await _call(partial(table.list_objects, conn, name=name, type=type, tag=tag, tint=tint))

    @server.tool()
    async def inspect_object(guid: str) -> Any:
        """Full details of one object: everything list_objects gives, plus scale, bounds (world-axis
        box: center, size), value (dice etc.), whether it is held or moving, and its snap points in
        world coordinates (e.g. the slots on a game board).
        """
        return await _call(table.inspect_object, conn, guid)

    @server.tool()
    async def move_object(
        guid: str, position: list[float], rotation: list[float] | None = None, smooth: bool = True
    ) -> Any:
        """Move one object to `position` (optionally `rotation`) and wait until it has settled.
        smooth=true (default) glides it so the player sees the move; false teleports it.
        Place pieces slightly above their resting height and let physics settle them.
        Returns the final position and rotation.
        """
        return await _call(partial(table.move_object, conn, guid, position, rotation, smooth))

    @server.tool()
    async def move_objects(
        moves: list[dict[str, Any]] | None = None,
        guids: list[str] | None = None,
        offset: list[float] | None = None,
        smooth: bool = True,
    ) -> Any:
        """Move several objects at once and wait until all have settled. Either:
        - `moves`: [{"guid", "position", "rotation"?}, ...] for explicit targets, or
        - `guids` + `offset` [dx, dy, dz] to shift them together, keeping their formation.
        """
        return await _call(partial(table.move_objects, conn, moves, guids, offset, smooth))

    @server.tool()
    async def table_geometry() -> Any:
        """The table's type and bounding box (center, size), and global snap points.
        Snap points that belong to a board are listed by inspect_object on the board.
        """
        return await _call(table.table_geometry, conn)

    @server.tool()
    async def measure(a: str | list[float], b: str | list[float]) -> Any:
        """Horizontal distance between two objects (GUIDs) or points ([x, y, z]), in world units.
        Returns center (centre to centre), edge (between bounding boxes, 0 if overlapping), dx, dy, dz.
        """
        return await _call(table.measure, conn, a, b)

    @server.tool()
    async def highlight(guid: str, color: str = "Yellow", seconds: float = 3.0) -> Any:
        """Highlight an object for a few seconds to point it out to the player.
        color is a TTS colour name: White, Red, Orange, Yellow, Green, Blue, Purple, Pink, ...
        """
        return await _call(table.highlight, conn, guid, color, seconds)

    @server.tool()
    async def roll_dice(guids: list[str], cocked_tilt: float = table.COCKED_TILT_DEGREES) -> Any:
        """Roll dice with TTS's physics roll (visibly lifted and spun, like pressing R) and wait until all
        have come to rest. Returns each die's value and tilt (degrees from lying flat), the total, and
        `cocked`: dice tilted more than `cocked_tilt` (default 10°, for flat surfaces), whose value may be
        disputed. Dice bounce: roll them where nothing else can be hit, e.g. in a dice tray.
        """
        return await _call(partial(table.roll_dice, conn, guids, cocked_tilt=cocked_tilt))

    @server.tool()
    async def read_dice(
        guids: list[str] | None = None, cocked_tilt: float = table.COCKED_TILT_DEGREES
    ) -> Any:
        """Read dice values without rolling (e.g. after the player rolled): the given dice, or all dice
        on the table. Each die has value, resting, tilt, cocked, tint and position.
        """
        return await _call(partial(table.read_dice, conn, guids, cocked_tilt=cocked_tilt))

    return server


def main() -> None:
    with TTSConnection() as conn:
        create_server(conn).run("stdio")
