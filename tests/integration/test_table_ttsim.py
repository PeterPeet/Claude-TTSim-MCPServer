"""Integration: 3D controls against the real TTSim (REQ-OBJ, REQ-DICE). Run with `pytest -m ttsim`.

Uses whatever is on the table, so it works with any loaded game that has at least one unlocked object
and one die. Objects that are moved are put back where they were.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ttsim_mcp import table
from ttsim_mcp.comms import TTSimConnection, TTSimLuaError

pytestmark = pytest.mark.ttsim


@pytest.fixture
def conn() -> Iterator[TTSimConnection]:
    with TTSimConnection() as c:
        yield c


def first(conn: TTSimConnection, **filters: str) -> dict:
    objects = table.list_objects(conn, **filters)["objects"]
    if not objects:
        pytest.skip(f"no object matching {filters} on the table")
    return objects[0]


def test_req_obj_01_list_objects_fields_and_filters(conn: TTSimConnection) -> None:
    objects = table.list_objects(conn)["objects"]
    assert objects
    assert set(objects[0]) >= {"guid", "name", "description", "type", "tags", "tint", "position", "rotation"}
    die = first(conn, type="Dice")
    assert all(o["type"] == "Dice" for o in table.list_objects(conn, type="Dice")["objects"])
    assert table.list_objects(conn, tint=die["tint"])["objects"]


def test_req_obj_02_inspect_object(conn: TTSimConnection) -> None:
    obj = first(conn)
    details = table.inspect_object(conn, obj["guid"])
    assert details["guid"] == obj["guid"]
    assert set(details) >= {"bounds", "scale", "snap_points", "locked", "resting"}


def test_req_obj_02_unknown_guid(conn: TTSimConnection) -> None:
    with pytest.raises(TTSimLuaError, match="zzzzzz"):
        table.inspect_object(conn, "zzzzzz")


def test_req_obj_03_move_object_and_back(conn: TTSimConnection) -> None:
    die = first(conn, type="Dice")
    start = die["position"]
    target = [start[0], start[1], start[2] + 1.0]
    try:
        moved = table.move_object(conn, die["guid"], target)["objects"][0]
        assert moved["position"][0] == pytest.approx(target[0], abs=0.05)
        assert moved["position"][2] == pytest.approx(target[2], abs=0.05)
    finally:
        table.move_object(conn, die["guid"], start)


def test_req_obj_04_move_objects_by_offset_and_back(conn: TTSimConnection) -> None:
    dice = table.list_objects(conn, type="Dice")["objects"][:2]
    if len(dice) < 2:
        pytest.skip("needs two dice")
    guids = [d["guid"] for d in dice]
    gap_before = dice[1]["position"][2] - dice[0]["position"][2]
    try:
        moved = table.move_objects(conn, guids=guids, offset=[0, 0, 1.0])["objects"]
        assert moved[1]["position"][2] - moved[0]["position"][2] == pytest.approx(gap_before, abs=0.05)
    finally:
        table.move_objects(conn, guids=guids, offset=[0, 0, -1.0])


def test_req_obj_05_table_geometry(conn: TTSimConnection) -> None:
    geometry = table.table_geometry(conn)
    assert isinstance(geometry["table"]["type"], str)
    assert len(geometry["table"]["size"]) == 3
    assert isinstance(geometry["snap_points"], list)


def test_req_obj_06_measure_between_objects(conn: TTSimConnection) -> None:
    dice = table.list_objects(conn, type="Dice")["objects"][:2]
    if len(dice) < 2:
        pytest.skip("needs two dice")
    result = table.measure(conn, dice[0]["guid"], dice[1]["guid"])
    assert result["center"] > result["edge"] >= 0


def test_req_obj_07_highlight(conn: TTSimConnection) -> None:
    table.highlight(conn, first(conn)["guid"], seconds=1)


def test_req_dice_01_roll_two_dice(conn: TTSimConnection) -> None:
    dice = table.list_objects(conn, type="Dice")["objects"][:2]
    if len(dice) < 2:
        pytest.skip("needs two dice")
    result = table.roll_dice(conn, [d["guid"] for d in dice])
    assert all(1 <= d["value"] <= 6 for d in result["dice"])
    shown = table.read_dice(conn, [d["guid"] for d in dice])
    assert [d["value"] for d in shown["dice"]] == [d["value"] for d in result["dice"]]


def test_req_dice_02_read_all_dice(conn: TTSimConnection) -> None:
    result = table.read_dice(conn)
    assert result["dice"]
    assert all({"guid", "value", "resting", "tint"} <= set(d) for d in result["dice"])


def test_req_dice_03_flip_a_coin(conn: TTSimConnection) -> None:
    coin = first(conn, type="Coin")
    faces = {
        f["value"]
        for f in conn.execute_lua(f'return getObjectFromGUID("{coin["guid"]}").getRotationValues()')
    }
    result = table.roll_dice(conn, [coin["guid"]])
    face = result["dice"][0]["value"]
    assert face in faces
    assert table.read_dice(conn, [coin["guid"]])["dice"][0]["value"] == face
    assert any(d["guid"] == coin["guid"] for d in table.read_dice(conn)["dice"])
