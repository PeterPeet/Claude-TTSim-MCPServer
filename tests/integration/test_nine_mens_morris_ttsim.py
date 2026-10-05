"""Integration: the Nine Men's Morris helper (skills/ttsim-nine-mens-morris/nmm.lua) against the real game.

REQ-NMM-02, -04. Skipped unless Nine Men's Morris is loaded. Read-only: plans moves, never carries them out.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ttsim_mcp import access
from ttsim_mcp.comms import TTSimConnection, TTSimLuaError

pytestmark = pytest.mark.ttsim

HELPER = Path(__file__).parents[2] / "skills" / "ttsim-nine-mens-morris" / "nmm.lua"


@pytest.fixture
def conn() -> Iterator[TTSimConnection]:
    with TTSimConnection() as c:
        if access.status(c).get("game") != "Nine Men's Morris":
            pytest.skip("Nine Men's Morris is not loaded")
        assert c.execute_lua(HELPER.read_text()) == {"loaded": "TTSIM_NMM", "version": 1}
        yield c


def read(conn: TTSimConnection) -> dict:
    return conn.execute_lua('return TTSIM_NMM({ action = "read" })')


def test_req_nmm_02_read_accounts_for_all_tokens(conn: TTSimConnection) -> None:
    position = read(conn)
    for color in ("red", "blue"):
        p = position[color]
        loose = sum(1 for t in position["loose"] if t["color"] == color)
        assert p["on_board"] + p["in_hand"] + p["removed"] + loose == 9
    assert position["diagram"].count("\n") == 13


def test_req_nmm_02_reset_board_is_recognised(conn: TTSimConnection) -> None:
    position = read(conn)
    if position["red"]["in_hand"] != 9 or position["blue"]["in_hand"] != 9:
        pytest.skip("board is not freshly reset")
    assert position["red"]["on_board"] == position["blue"]["on_board"] == 0
    assert position["red"]["phase"] == "placing"
    assert position["blue"]["legal_moves"] == 24


def test_req_nmm_04_plan_placing(conn: TTSimConnection) -> None:
    position = read(conn)
    if position["blue"]["in_hand"] == 0 or "d6" in position["red"]["points"] + position["blue"]["points"]:
        pytest.skip("needs blue tokens in hand and d6 free")
    plan = conn.execute_lua('return TTSIM_NMM({ action = "plan", color = "blue", place = "d6" })')
    assert plan["notation"] == "d6"
    assert len(plan["moves"]) == 1


def test_req_nmm_04_plan_refuses_illegal_actions(conn: TTSimConnection) -> None:
    with pytest.raises(TTSimLuaError, match="No point 'd4'"):
        conn.execute_lua('return TTSIM_NMM({ action = "plan", color = "blue", place = "d4" })')
    position = read(conn)
    if position["blue"]["in_hand"] > 0:
        with pytest.raises(TTSimLuaError, match="place instead of moving"):
            conn.execute_lua('return TTSIM_NMM({ action = "plan", color = "blue", move = { "d6", "d5" } })')
