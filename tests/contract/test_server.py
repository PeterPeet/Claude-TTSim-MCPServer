"""Contract tests for the MCP adapter, in-process against the fake TTS (REQ-MCP-01..04)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from mcp import Client

from tests.fake_tts import CompileError, FakeTTS, LuaError, NoReply, Value, free_port
from tts_mcp.comms import TTSConnection
from tts_mcp.server import create_server

pytestmark = pytest.mark.anyio

Pair = tuple[FakeTTS, TTSConnection]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def payload(result: Any) -> Any:
    return json.loads(result.content[0].text)


async def test_req_mcp_01_lists_raw_access_tools(fake_and_conn: Pair) -> None:
    _, conn = fake_and_conn
    async with Client(create_server(conn)) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) >= {"run_lua", "get_scripts", "get_events", "tts_status"}
    assert all(t.description for t in tools.values())


async def test_req_mcp_02_run_lua_returns_value(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("return 1+1", Value(2))
    async with Client(create_server(conn)) as client:
        result = await client.call_tool("run_lua", {"code": "return 1+1"})
    assert not result.is_error
    assert payload(result) == 2


async def test_req_mcp_02_run_lua_returns_table(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("return {a=1}", Value({"a": 1}))
    async with Client(create_server(conn)) as client:
        result = await client.call_tool("run_lua", {"code": "return {a=1}"})
    assert payload(result) == {"a": 1}


async def test_req_mcp_02_tts_status(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("Info.name", Value({"game": "Backgammon", "objects": 35, "players": []}))
    async with Client(create_server(conn)) as client:
        result = await client.call_tool("tts_status", {})
    assert payload(result)["game"] == "Backgammon"


async def test_req_mcp_02_get_scripts(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("getLuaScript", Value({"global": {"script": "", "ui": ""}, "objects": []}))
    async with Client(create_server(conn)) as client:
        result = await client.call_tool("get_scripts", {})
    assert payload(result)["objects"] == []


async def test_req_mcp_02_get_events(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("print", Value(None))
    async with Client(create_server(conn)) as client:
        await client.call_tool("run_lua", {"code": "print('x')"})
        fake.push_event({"message": "x", "messageID": 2})
        for _ in range(100):
            result = await client.call_tool("get_events", {"since": 0})
            if payload(result)["events"]:
                break
    assert payload(result)["events"][0]["message"] == "x"


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (LuaError("boom at line 1"), "boom at line 1"),
        (CompileError("unexpected symbol near 'end'"), "unexpected symbol"),
        (NoReply(), "did not answer"),
    ],
)
async def test_req_mcp_04_tts_errors_are_readable_tool_errors(
    fake_and_conn: Pair, response: Any, expected: str
) -> None:
    fake, conn = fake_and_conn
    fake.respond("bad()", response)
    fake.respond("return 1", Value(1))
    conn.timeout = 0.3
    async with Client(create_server(conn)) as client:
        result = await client.call_tool("run_lua", {"code": "bad()"})
        assert result.is_error
        assert expected in result.content[0].text
        # The server survives and keeps working.
        assert payload(await client.call_tool("run_lua", {"code": "return 1"})) == 1


async def test_req_mcp_04_not_running_is_readable_tool_error() -> None:
    with TTSConnection(send_port=free_port(), listen_port=free_port(), timeout=0.5) as conn:
        async with Client(create_server(conn)) as client:
            result = await client.call_tool("run_lua", {"code": "return 1"})
    assert result.is_error
    assert "Start Tabletop Simulator" in result.content[0].text
