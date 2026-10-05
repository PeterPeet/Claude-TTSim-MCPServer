"""Contract tests for ttsim_mcp.table against the fake TTSim (REQ-OBJ-01..07, REQ-DICE-01..02).

The fake cannot run Lua, so these tests check what Python sends and how it handles the replies
(polling, timeouts, rounding). The Lua itself is verified by tests/integration/test_table_ttsim.py.
"""

from __future__ import annotations

import json
import time

import pytest

from tests.fake_ttsim import FakeTTSim, LuaError, Value
from ttsim_mcp import table
from ttsim_mcp.comms import TTSimConnection, TTSimLuaError, TTSimTimeoutError

Pair = tuple[FakeTTSim, TTSimConnection]
FAST = 0.01  # poll interval for tests


def sent_args(fake: FakeTTSim, marker: str) -> dict:
    """The JSON args embedded in the last script carrying `marker`."""
    script = fake.scripts_containing(marker)[-1]
    start = script.index("[==[") + 4
    return json.loads(script[start : script.index("]==]", start)])


def moving(guid: str, pos: list[float]) -> Value:
    return Value({"objects": [{"guid": guid, "moving": True, "resting": False, "position": pos}]})


def settled(guid: str, pos: list[float]) -> Value:
    return Value(
        {
            "objects": [
                {"guid": guid, "moving": False, "resting": True, "position": pos, "rotation": [0, 0, 0]}
            ]
        }
    )


# REQ-OBJ-01 List objects


def test_req_obj_01_list_objects_passes_filters_and_rounds(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    obj = {"guid": "abc123", "type": "Dice", "position": [0.62469673, 1.4702001, 5.7877216]}
    fake.respond("ttsim_mcp:list_objects", Value({"objects": [obj]}))
    result = table.list_objects(conn, type="Dice", tint="264D71")
    assert result == {"objects": [{"guid": "abc123", "type": "Dice", "position": [0.6247, 1.4702, 5.7877]}]}
    assert sent_args(fake, "ttsim_mcp:list_objects") == {"type": "Dice", "tint": "264d71"}


def test_req_obj_01_list_objects_empty_table_from_lua(fake_and_conn: Pair) -> None:
    # TTSim's JSON.encode turns an empty Lua table into [] even where an object was meant.
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:list_objects", Value({"objects": []}))
    assert table.list_objects(conn) == {"objects": []}


# REQ-OBJ-02 Inspect object


def test_req_obj_02_inspect_object(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:inspect_object", Value({"guid": "735307", "snap_points": []}))
    assert table.inspect_object(conn, "735307")["guid"] == "735307"
    assert sent_args(fake, "ttsim_mcp:inspect_object") == {"guid": "735307"}


def test_req_obj_02_unknown_guid_is_lua_error(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:inspect_object", LuaError("No object with GUID 'nope00'"))
    with pytest.raises(TTSimLuaError, match="nope00"):
        table.inspect_object(conn, "nope00")


# REQ-OBJ-03 Move object


def test_req_obj_03_move_object_waits_until_settled(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:move_objects", Value(None))
    fake.respond(
        "ttsim_mcp:motion_state",
        moving("abc123", [1, 2, 3]),
        moving("abc123", [2, 2, 3]),
        settled("abc123", [3.00001, 1.25, 3]),
    )
    result = table.move_object(conn, "abc123", [3, 1.25, 3], poll_interval=FAST)
    assert result["objects"][0]["position"] == [3.0, 1.25, 3]
    assert len(fake.scripts_containing("ttsim_mcp:motion_state")) == 3
    assert sent_args(fake, "ttsim_mcp:move_objects") == {
        "moves": [{"guid": "abc123", "position": [3, 1.25, 3]}],
        "smooth": True,
    }


def test_req_obj_03_move_object_with_rotation_and_instant(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:move_objects", Value(None))
    fake.respond("ttsim_mcp:motion_state", settled("abc123", [0, 1, 0]))
    table.move_object(conn, "abc123", [0, 1, 0], rotation=[0, 90, 0], smooth=False, poll_interval=FAST)
    assert sent_args(fake, "ttsim_mcp:move_objects") == {
        "moves": [{"guid": "abc123", "position": [0, 1, 0], "rotation": [0, 90, 0]}],
        "smooth": False,
    }


def test_req_obj_03_move_that_never_settles_times_out(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:move_objects", Value(None))
    fake.respond("ttsim_mcp:motion_state", moving("abc123", [1, 1, 1]))
    with pytest.raises(TTSimTimeoutError, match="abc123"):
        table.move_object(conn, "abc123", [0, 1, 0], timeout=0.2, poll_interval=FAST)


# REQ-OBJ-04 Move many


def test_req_obj_04_move_objects_by_offset_keeps_formation(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:move_objects", Value(None))
    fake.respond(
        "ttsim_mcp:motion_state",
        Value(
            {
                "objects": [
                    {"guid": "a", "moving": False, "resting": True, "position": [1, 1, 0]},
                    {"guid": "b", "moving": False, "resting": True, "position": [2, 1, 0]},
                ]
            }
        ),
    )
    result = table.move_objects(conn, guids=["a", "b"], offset=[1, 0, 0], poll_interval=FAST)
    assert [o["guid"] for o in result["objects"]] == ["a", "b"]
    assert sent_args(fake, "ttsim_mcp:move_objects")["moves"] == [
        {"guid": "a", "offset": [1, 0, 0]},
        {"guid": "b", "offset": [1, 0, 0]},
    ]


def test_req_obj_04_move_objects_with_explicit_positions(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:move_objects", Value(None))
    fake.respond("ttsim_mcp:motion_state", settled("a", [5, 1, 5]))
    table.move_objects(conn, moves=[{"guid": "a", "position": [5, 1, 5]}], poll_interval=FAST)
    assert sent_args(fake, "ttsim_mcp:move_objects")["moves"] == [{"guid": "a", "position": [5, 1, 5]}]


def test_req_obj_04_move_objects_needs_exactly_one_mode(fake_and_conn: Pair) -> None:
    _, conn = fake_and_conn
    with pytest.raises(ValueError):
        table.move_objects(conn)
    with pytest.raises(ValueError):
        table.move_objects(conn, moves=[{"guid": "a", "position": [0, 0, 0]}], guids=["a"], offset=[1, 0, 0])


# REQ-OBJ-05 Table geometry


def test_req_obj_05_table_geometry(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    geometry = {
        "table": {"type": "Table_RPG", "center": [0, -12, 0], "size": [64, 31, 43]},
        "snap_points": [],
    }
    fake.respond("ttsim_mcp:table_geometry", Value(geometry))
    assert table.table_geometry(conn) == geometry


# REQ-OBJ-06 Measure


def test_req_obj_06_measure_objects_and_points(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond(
        "ttsim_mcp:bounds",
        Value({"objects": [{"guid": "a", "position": [0, 1, 0], "center": [0, 1, 0], "size": [2, 1, 2]}]}),
    )
    result = table.measure(conn, "a", [4, 1, 0])
    assert result["center"] == pytest.approx(4.0)
    assert result["edge"] == pytest.approx(3.0)
    assert sent_args(fake, "ttsim_mcp:bounds") == {"guids": ["a"]}


def test_req_obj_06_measure_two_points_needs_no_ttsim(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    assert table.measure(conn, [0, 0, 0], [3, 0, 4])["center"] == pytest.approx(5.0)
    assert fake.received == []


# REQ-OBJ-07 Highlight


def test_req_obj_07_highlight(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:highlight", Value(None))
    table.highlight(conn, "abc123", color="Red", seconds=2)
    assert sent_args(fake, "ttsim_mcp:highlight") == {"guid": "abc123", "color": "Red", "seconds": 2}


# REQ-DICE-01 Roll physical dice


def dice_state(*dice: tuple[str, int, bool], tilt: float = 0.0) -> Value:
    return Value(
        {
            "dice": [
                {
                    "guid": g,
                    "value": v,
                    "resting": r,
                    "tilt": tilt,
                    "rotation": [0, 45, 0],
                    "position": [0, 1, 0],
                }
                for g, v, r in dice
            ]
        }
    )


def test_req_dice_01_roll_waits_for_all_dice_to_rest(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:roll_dice", Value(None))
    fake.respond(
        "ttsim_mcp:dice_state",
        dice_state(("d1", 2, False), ("d2", 5, False)),
        dice_state(("d1", 4, True), ("d2", 5, False)),
        dice_state(("d1", 4, True), ("d2", 6, True)),
    )
    result = table.roll_dice(conn, ["d1", "d2"], poll_interval=FAST, min_roll_time=0)
    assert [d["value"] for d in result["dice"]] == [4, 6]
    assert result["total"] == 10
    assert result["cocked"] == []
    assert sent_args(fake, "ttsim_mcp:roll_dice") == {"guids": ["d1", "d2"]}


def test_req_dice_01_roll_waits_at_least_min_roll_time(fake_and_conn: Pair) -> None:
    # Guards against reading a die that has not left the table yet.
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:roll_dice", Value(None))
    fake.respond("ttsim_mcp:dice_state", dice_state(("d1", 1, True)))
    start = time.monotonic()
    table.roll_dice(conn, ["d1"], poll_interval=FAST, min_roll_time=0.3)
    assert time.monotonic() - start >= 0.3


def test_req_dice_01_roll_reports_cocked_dice(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:roll_dice", Value(None))
    fake.respond("ttsim_mcp:dice_state", dice_state(("d1", 3, True), tilt=35.0))
    result = table.roll_dice(conn, ["d1"], poll_interval=FAST, min_roll_time=0)
    assert result["cocked"] == ["d1"]
    assert result["dice"][0]["cocked"] is True
    assert result["dice"][0]["tilt"] == 35.0


def test_req_dice_01_cocked_tolerance_is_adjustable(fake_and_conn: Pair) -> None:
    # 20° is cocked on a flat table (default 10°), but acceptable on a curved surface with tolerance 30°.
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:dice_state", dice_state(("d1", 3, True), tilt=20.0))
    assert table.read_dice(conn)["cocked"] == ["d1"]
    assert table.read_dice(conn, cocked_tilt=30)["cocked"] == []


def test_req_dice_01_roll_never_resting_times_out(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:roll_dice", Value(None))
    fake.respond("ttsim_mcp:dice_state", dice_state(("d1", 1, False)))
    with pytest.raises(TTSimTimeoutError, match="d1"):
        table.roll_dice(conn, ["d1"], timeout=0.2, poll_interval=FAST, min_roll_time=0)


def test_req_dice_01_roll_needs_dice(fake_and_conn: Pair) -> None:
    _, conn = fake_and_conn
    with pytest.raises(ValueError):
        table.roll_dice(conn, [])


# REQ-DICE-02 Read dice


def test_req_dice_02_read_dice_without_rolling(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:dice_state", dice_state(("d1", 3, True), ("d2", 3, True)))
    result = table.read_dice(conn)
    assert [d["value"] for d in result["dice"]] == [3, 3]
    assert sent_args(fake, "ttsim_mcp:dice_state") == {}
    assert not fake.scripts_containing("ttsim_mcp:roll_dice")


def test_req_dice_02_read_specific_dice(fake_and_conn: Pair) -> None:
    fake, conn = fake_and_conn
    fake.respond("ttsim_mcp:dice_state", dice_state(("d1", 3, True)))
    table.read_dice(conn, ["d1"])
    assert sent_args(fake, "ttsim_mcp:dice_state") == {"guids": ["d1"]}
