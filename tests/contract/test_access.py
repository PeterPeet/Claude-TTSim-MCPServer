"""Contract tests for tts_mcp.access against the fake TTS (REQ-MCP-02)."""

from __future__ import annotations

from tests.conftest import wait_until
from tests.fake_tts import FakeTTS, Value, free_port
from tts_mcp import access
from tts_mcp.comms import TTSConnection

Pair = tuple[FakeTTS, TTSConnection]


def test_req_mcp_02_get_scripts_reads_via_lua(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    scripts = {
        "global": {"script": "function onLoad() end", "ui": ""},
        "objects": [{"guid": "abc123", "name": "Board", "type": "Board", "script": "x=1", "ui": ""}],
    }
    fake.respond("getLuaScript", Value(scripts))
    assert access.get_scripts(conn) == scripts
    # Read-only path: only Lua execution (messageID 3), never getScripts (0) or Save & Play (1).
    assert {m["messageID"] for m in fake.received} == {3}


def test_req_mcp_02_status_when_reachable(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    info = {"game": "Backgammon", "objects": 35, "players": [{"color": "White", "host": True}]}
    fake.respond("Info.name", Value(info))
    assert access.status(conn) == {"reachable": True, **info}


def test_req_mcp_02_status_when_not_running() -> None:
    with TTSConnection(send_port=free_port(), listen_port=free_port(), timeout=0.5) as conn:
        result = access.status(conn)
    assert result["reachable"] is False
    assert "Tabletop Simulator" in result["error"]


def test_req_mcp_02_events_since_and_last_seq(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    conn.start()
    fake.push_event({"message": "a", "messageID": 2})
    fake.push_event({"message": "b", "messageID": 2})
    assert wait_until(lambda: len(conn.events()) == 2)
    result = access.get_events(conn)
    assert [e["message"] for e in result["events"]] == ["a", "b"]
    assert result["last_seq"] == result["events"][-1]["seq"]
    assert access.get_events(conn, since=result["last_seq"])["events"] == []


def test_req_mcp_02_events_summarise_script_payloads(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    conn.start()
    states = [{"name": "Global", "guid": "-1", "script": "x" * 10_000, "ui": ""}]
    fake.push_event({"messageID": 1, "scriptStates": states})
    assert wait_until(lambda: len(conn.events()) == 1)
    event = access.get_events(conn)["events"][0]
    assert event["kind"] == "game_loaded"
    assert "scriptStates" not in event
    assert event["scripts"] == 1


def test_req_mcp_02_events_empty_buffer(fake_and_conn: Pair) -> None:
    _, conn = fake_and_conn
    assert access.get_events(conn, since=7) == {"events": [], "last_seq": 7}
