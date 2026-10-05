"""Integration: the backgammon helper (skills/ttsim-backgammon/bg.lua) against the real game (REQ-BG-02, -03).

Skipped unless the loaded game is Backgammon. Read-only: plans moves but never carries them out.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ttsim_mcp import access
from ttsim_mcp.comms import TTSimConnection, TTSimLuaError

pytestmark = pytest.mark.ttsim

HELPER = Path(__file__).parents[2] / "skills" / "ttsim-backgammon" / "bg.lua"


@pytest.fixture
def conn() -> Iterator[TTSimConnection]:
    with TTSimConnection() as c:
        if access.status(c).get("game") != "Backgammon":
            pytest.skip("Backgammon is not loaded")
        assert c.execute_lua(HELPER.read_text()) == {"loaded": "TTSIM_BG", "version": 1}
        yield c


def counted(summary: str) -> int:
    """Total checkers in a summary like "point:count in light's numbers, 24:2 13:5 8:3 6:5"."""
    entries = summary.split(", ", 1)[1]
    return 0 if entries == "-" else sum(int(e.split(":")[1]) for e in entries.split())


def test_req_bg_02_read_accounts_for_all_checkers(conn: TTSimConnection) -> None:
    position = conn.execute_lua('return TTSIM_BG({ action = "read" })')
    assert position["conflicts"] == []
    for color in ("light", "brown"):
        on_board = counted(position[color])
        assert (
            on_board
            + position["bar"][color]
            + position["off"][color]
            + sum(1 for c in position["loose"] if c["color"] == color)
            == 15
        )


def test_req_bg_02_starting_position_is_recognised(conn: TTSimConnection) -> None:
    position = conn.execute_lua('return TTSIM_BG({ action = "read" })')
    if position["pip"] != {"light": 167, "brown": 167}:
        pytest.skip("board is not in the starting position")
    assert position["light"].endswith("24:2 13:5 8:3 6:5")
    assert position["brown"].endswith("24:2 13:5 8:3 6:5")


def test_req_bg_03_plan_refuses_a_blocked_point(conn: TTSimConnection) -> None:
    position = conn.execute_lua('return TTSIM_BG({ action = "read" })')
    if position["pip"] != {"light": 167, "brown": 167}:
        pytest.skip("board is not in the starting position")
    with pytest.raises(TTSimLuaError, match="blocked"):
        conn.execute_lua('return TTSIM_BG({ action = "plan", color = "light", moves = { { 24, 19 } } })')


def test_req_bg_03_plan_opening_move(conn: TTSimConnection) -> None:
    position = conn.execute_lua('return TTSIM_BG({ action = "read" })')
    if position["pip"] != {"light": 167, "brown": 167}:
        pytest.skip("board is not in the starting position")
    plan = conn.execute_lua(
        'return TTSIM_BG({ action = "plan", color = "light", moves = { { 24, 18 }, { 13, 11 } } })'
    )
    assert plan["notation"] == "24/18 13/11"
    assert len(plan["moves"]) == 2
    assert all(len(m["position"]) == 3 for m in plan["moves"])
