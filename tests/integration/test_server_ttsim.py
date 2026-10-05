"""Integration: `python -m ttsim_mcp` over stdio against the real TTSim (REQ-MCP-01, REQ-MCP-02).

Needs port 39998 free, so no other TTSim-MCP instance (e.g. one started by a Claude Code session) may run.
"""

from __future__ import annotations

import json
import sys

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters

pytestmark = [pytest.mark.ttsim, pytest.mark.anyio]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


SERVER = StdioServerParameters(command=sys.executable, args=["-m", "ttsim_mcp"])


async def test_req_mcp_01_stdio_server_runs_lua_against_real_ttsim() -> None:
    async with Client(SERVER) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        assert {"run_lua", "get_scripts", "get_events", "ttsim_status"} <= names
        result = await client.call_tool("run_lua", {"code": "return 1+1"})
        assert json.loads(result.content[0].text) == 2


async def test_req_mcp_02_status_and_scripts_against_real_ttsim() -> None:
    async with Client(SERVER) as client:
        status = json.loads((await client.call_tool("ttsim_status", {})).content[0].text)
        assert status["reachable"] is True
        assert isinstance(status["game"], str)
        scripts = json.loads((await client.call_tool("get_scripts", {})).content[0].text)
        assert isinstance(scripts["global"]["script"], str)
