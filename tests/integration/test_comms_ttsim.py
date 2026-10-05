"""Integration tests against the real Tabletop Simulator (REQ-COM). Run with `pytest -m ttsim`."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.conftest import wait_until
from ttsim_mcp.comms import TTSimConnection, TTSimLuaError

pytestmark = pytest.mark.ttsim


@pytest.fixture
def conn() -> Iterator[TTSimConnection]:
    with TTSimConnection() as c:
        yield c


def test_req_com_01_execute_lua_returns_value(conn: TTSimConnection) -> None:
    assert conn.execute_lua("return 1+1") == 2


def test_req_com_01_table_return_arrives_as_dict_and_list(conn: TTSimConnection) -> None:
    assert conn.execute_lua("return {a=1, b={2,3}}") == {"a": 1, "b": [2, 3]}


def test_req_com_03_runtime_error(conn: TTSimConnection) -> None:
    with pytest.raises(TTSimLuaError, match="ttsim-mcp integration test"):
        conn.execute_lua('error("ttsim-mcp integration test")')


def test_req_com_03_compile_error(conn: TTSimConnection) -> None:
    # Syntax errors bypass the wrapper, so TTSim also shows them in red in the game chat.
    # The string makes that chat message explain itself.
    label = "ttsim-mcp integration test: deliberate syntax error, please ignore"
    with pytest.raises(TTSimLuaError, match=label):
        conn.execute_lua(f'return 1 "{label}"')


def test_req_com_03_unserialisable_result(conn: TTSimConnection) -> None:
    with pytest.raises(TTSimLuaError, match="JSON"):
        conn.execute_lua("return getAllObjects()[1]")


def test_req_com_05_print_arrives_as_event(conn: TTSimConnection) -> None:
    conn.execute_lua("print('ttsim-mcp integration test')")
    assert wait_until(
        lambda: any(e.message.get("message") == "ttsim-mcp integration test" for e in conn.events())
    )
