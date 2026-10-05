"""Unit tests for the pure helpers behind the 3D controls (REQ-OBJ-01, REQ-OBJ-06, REQ-DICE-01)."""

import pytest

from ttsim_mcp.comms import render_lua
from ttsim_mcp.table import Box, center_distance, edge_distance, is_cocked, rounded


def box(x: float, z: float, sx: float = 0.0, sz: float = 0.0, y: float = 0.0) -> Box:
    return Box(center=(x, y, z), size=(sx, 0.0, sz))


def test_req_obj_06_center_distance_is_horizontal() -> None:
    # Height difference is ignored: on a table, distances are measured across the surface.
    assert center_distance(box(0, 0, y=0), box(3, 4, y=10)) == pytest.approx(5.0)


def test_req_obj_06_edge_distance_between_separated_boxes() -> None:
    # Two 1×1 boxes whose centres are 3 apart along x: gap of 2 between the edges.
    assert edge_distance(box(0, 0, 1, 1), box(3, 0, 1, 1)) == pytest.approx(2.0)


def test_req_obj_06_edge_distance_diagonal() -> None:
    # Corner to corner: gaps of 3 (x) and 4 (z).
    assert edge_distance(box(0, 0, 2, 2), box(5, 6, 2, 2)) == pytest.approx(5.0)


def test_req_obj_06_edge_distance_overlapping_is_zero() -> None:
    assert edge_distance(box(0, 0, 2, 2), box(1, 1, 2, 2)) == 0.0


def test_req_obj_06_edge_distance_point_to_box() -> None:
    assert edge_distance(box(0, 0, 2, 2), box(4, 0)) == pytest.approx(3.0)


@pytest.mark.parametrize(
    ("tilt", "tolerance", "cocked"),
    [
        (0.0, 30.0, False),  # flat on the table
        (13.4, 30.0, False),  # resting in a bowl (spike)
        (30.6, 30.0, True),  # leaning steeply in a bowl (spike)
        (12.0, 10.0, True),  # stricter tolerance for a flat table
    ],
)
def test_req_dice_01_is_cocked(tilt: float, tolerance: float, cocked: bool) -> None:
    assert is_cocked(tilt, tolerance) is cocked


def test_req_obj_01_rounded_trims_float_noise() -> None:
    data = {"p": [2.50447806138254e-6, 1.4702001810073], "n": 3, "s": "x", "nested": [{"v": 0.12345678}]}
    assert rounded(data) == {"p": [0.0, 1.4702], "n": 3, "s": "x", "nested": [{"v": 0.1235}]}


def test_req_obj_01_render_lua_embeds_args_as_json() -> None:
    script = render_lua("list_objects.lua", {"type": "Dice"})
    assert '{"type": "Dice"}' in script
    assert "{{args}}" not in script


def test_req_obj_01_render_lua_rejects_long_bracket_terminator() -> None:
    with pytest.raises(ValueError):
        render_lua("list_objects.lua", {"name": "]==]"})
