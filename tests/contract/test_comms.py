"""Contract tests for tts_mcp.comms against the fake TTS (REQ-COM-01..06)."""

from __future__ import annotations

import socket
import time

import pytest

from tests.conftest import wait_until
from tests.fake_tts import CompileError, FakeTTS, LuaError, NoReply, Value, free_port
from tts_mcp.comms import (
    TTSConnection,
    TTSListenerError,
    TTSLuaError,
    TTSNotRunningError,
    TTSTimeoutError,
)

Pair = tuple[FakeTTS, TTSConnection]


# REQ-COM-01 Execute Lua


def test_req_com_01_execute_lua_returns_value(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("return 1+1", Value(2))
    assert conn.execute_lua("return 1+1") == 2


def test_req_com_01_table_return_arrives_as_dict(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("return {a=1", Value({"a": 1, "b": [2, 3]}))
    assert conn.execute_lua("return {a=1, b={2,3}}") == {"a": 1, "b": [2, 3]}


def test_req_com_01_table_return_arrives_as_list(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("return {10,20}", Value([10, 20]))
    assert conn.execute_lua("return {10,20}") == [10, 20]


def test_req_com_01_nil_return_is_none(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("print('x')", Value(None))
    assert conn.execute_lua("print('x')") is None


def test_req_com_01_sends_wrapped_script_to_global(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("return 1+1", Value(2))
    conn.execute_lua("return 1+1")
    sent = fake.received[-1]
    assert sent["messageID"] == 3
    assert sent["guid"] == "-1"
    assert isinstance(sent["returnID"], int)
    assert "return 1+1" in sent["script"]
    assert "JSON.encode" in sent["script"]


def test_req_com_01_consecutive_calls_use_distinct_return_ids(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("return 1", Value(1))
    conn.execute_lua("return 1")
    conn.execute_lua("return 1")
    assert fake.received[0]["returnID"] != fake.received[1]["returnID"]


# REQ-COM-02 Timeout


def test_req_com_02_default_timeout_is_5_seconds() -> None:
    assert TTSConnection().timeout == 5.0


def test_req_com_02_no_reply_raises_timeout(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("return 1", NoReply())
    start = time.monotonic()
    with pytest.raises(TTSTimeoutError):
        conn.execute_lua("return 1", timeout=0.3)
    assert time.monotonic() - start < 1.0


def test_req_com_02_late_reply_after_timeout_does_not_break_next_call(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("return 'silent'", NoReply())
    fake.respond("return 2", Value(2))
    with pytest.raises(TTSTimeoutError):
        conn.execute_lua("return 'silent'", timeout=0.2)
    assert conn.execute_lua("return 2") == 2


# REQ-COM-03 Lua errors


def test_req_com_03_runtime_error_raises_lua_error_with_message(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond('error("boom")', LuaError("[Global] executeScript:(1,0-13): boom"))
    with pytest.raises(TTSLuaError, match="boom"):
        conn.execute_lua('error("boom")')


def test_req_com_03_compile_error_raises_lua_error_with_message(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("return 1 +", CompileError("[Global] executeScript:(2,0-3): unexpected symbol near 'end'"))
    with pytest.raises(TTSLuaError, match="unexpected symbol"):
        conn.execute_lua("return 1 +")


# REQ-COM-04 Not running


def test_req_com_04_nothing_listening_raises_not_running() -> None:
    with (
        TTSConnection(send_port=free_port(), listen_port=free_port(), timeout=1.0) as conn,
        pytest.raises(TTSNotRunningError, match="Tabletop Simulator"),
    ):
        conn.execute_lua("return 1")


def test_req_com_04_reply_port_in_use_raises_listener_error() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen()
        busy_port = blocker.getsockname()[1]
        conn = TTSConnection(send_port=free_port(), listen_port=busy_port)
        with pytest.raises(TTSListenerError, match=str(busy_port)):
            conn.start()


# REQ-COM-05 Events


def test_req_com_05_print_event_is_buffered(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    conn.start()
    fake.push_event({"message": "hello", "messageID": 2})
    assert wait_until(lambda: len(conn.events()) == 1)
    event = conn.events()[0]
    assert event.kind == "print"
    assert event.message["message"] == "hello"


@pytest.mark.parametrize(
    ("message_id", "kind"),
    [(1, "game_loaded"), (2, "print"), (3, "error"), (4, "custom"), (6, "game_saved"), (7, "object_created")],
)
def test_req_com_05_event_kinds(fake_and_conn: Pair, message_id: int, kind: str) -> None:
    fake, conn = fake_and_conn
    conn.start()
    fake.push_event({"messageID": message_id})
    assert wait_until(lambda: len(conn.events()) == 1)
    assert conn.events()[0].kind == kind


def test_req_com_05_events_since_returns_only_newer(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    conn.start()
    fake.push_event({"message": "a", "messageID": 2})
    assert wait_until(lambda: len(conn.events()) == 1)
    first_seq = conn.events()[0].seq
    fake.push_event({"message": "b", "messageID": 2})
    assert wait_until(lambda: len(conn.events()) == 2)
    assert [e.message["message"] for e in conn.events(since=first_seq)] == ["b"]


def test_req_com_05_buffer_is_bounded() -> None:
    reply_port = free_port()
    with (
        FakeTTS(reply_port=reply_port) as fake,
        TTSConnection(send_port=fake.port, listen_port=reply_port, event_buffer_size=3) as conn,
    ):
        conn.start()
        for i in range(5):
            fake.push_event({"message": str(i), "messageID": 2})
        assert wait_until(lambda: conn.events() and conn.events()[-1].message["message"] == "4")
        assert [e.message["message"] for e in conn.events()] == ["2", "3", "4"]


def test_req_com_05_lua_errors_are_also_kept_as_events(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("return 1 +", CompileError("unexpected symbol"))
    with pytest.raises(TTSLuaError):
        conn.execute_lua("return 1 +")
    assert any(e.kind == "error" for e in conn.events())


# REQ-COM-06 Fake TTS


def test_req_com_06_fake_records_received_messages(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("return 1", Value(1))
    conn.execute_lua("return 1")
    assert len(fake.received) == 1
