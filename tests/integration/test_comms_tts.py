"""Integration tests against the real Tabletop Simulator (REQ-COM). Run with `pytest -m tts`."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.conftest import wait_until
from tts_mcp.comms import TTSConnection, TTSLuaError

pytestmark = pytest.mark.tts


@pytest.fixture
def conn() -> Iterator[TTSConnection]:
    with TTSConnection() as c:
        yield c


def test_req_com_01_execute_lua_returns_value(conn: TTSConnection) -> None:
    assert conn.execute_lua("return 1+1") == 2


def test_req_com_01_table_return_arrives_as_dict_and_list(conn: TTSConnection) -> None:
    assert conn.execute_lua("return {a=1, b={2,3}}") == {"a": 1, "b": [2, 3]}


def test_req_com_03_runtime_error(conn: TTSConnection) -> None:
    with pytest.raises(TTSLuaError, match="tts-mcp integration test"):
        conn.execute_lua('error("tts-mcp integration test")')


def test_req_com_03_compile_error(conn: TTSConnection) -> None:
    with pytest.raises(TTSLuaError, match="unexpected symbol"):
        conn.execute_lua("return 1 +")


def test_req_com_03_unserialisable_result(conn: TTSConnection) -> None:
    with pytest.raises(TTSLuaError, match="JSON"):
        conn.execute_lua("return getAllObjects()[1]")


def test_req_com_05_print_arrives_as_event(conn: TTSConnection) -> None:
    conn.execute_lua("print('tts-mcp integration test')")
    assert wait_until(
        lambda: any(e.message.get("message") == "tts-mcp integration test" for e in conn.events())
    )
