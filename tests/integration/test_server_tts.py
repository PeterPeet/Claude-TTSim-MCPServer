"""Integration: `python -m tts_mcp` over stdio against the real TTS (REQ-MCP-01, REQ-MCP-02).

Needs port 39998 free, so no other TTS-MCP instance (e.g. one started by a Claude Code session) may run.
"""

from __future__ import annotations

import json
import sys

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters

pytestmark = [pytest.mark.tts, pytest.mark.anyio]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


SERVER = StdioServerParameters(command=sys.executable, args=["-m", "tts_mcp"])


async def test_req_mcp_01_stdio_server_runs_lua_against_real_tts() -> None:
    async with Client(SERVER) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        assert {"run_lua", "get_scripts", "get_events", "tts_status"} <= names
        result = await client.call_tool("run_lua", {"code": "return 1+1"})
        assert json.loads(result.content[0].text) == 2


async def test_req_mcp_02_status_and_scripts_against_real_tts() -> None:
    async with Client(SERVER) as client:
        status = json.loads((await client.call_tool("tts_status", {})).content[0].text)
        assert status["reachable"] is True
        assert isinstance(status["game"], str)
        scripts = json.loads((await client.call_tool("get_scripts", {})).content[0].text)
        assert isinstance(scripts["global"]["script"], str)
