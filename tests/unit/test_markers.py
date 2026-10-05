"""Unit tests for marker geometry (REQ-OBJ-09)."""

from __future__ import annotations

import math

import pytest

from ttsim_mcp.table import circle_points, marker_lines


def test_req_obj_09_circle_points_lie_on_the_circle_and_close() -> None:
    points = circle_points([2.0, 1.0, -3.0], radius=3.0, segments=32)
    assert len(points) == 33
    assert points[0] == pytest.approx(points[-1])
    for x, y, z in points:
        assert math.hypot(x - 2.0, z + 3.0) == pytest.approx(3.0)
        assert y == pytest.approx(1.0)


def test_req_obj_09_circle_needs_positive_radius() -> None:
    with pytest.raises(ValueError, match="radius"):
        circle_points([0, 1, 0], radius=0)


def test_req_obj_09_marker_lines_from_circles_and_polylines() -> None:
    lines = marker_lines(
        circles=[{"center": [0, 1, 0], "radius": 3}],
        lines=[{"points": [[0, 1, 0], [5, 1, 0]], "color": "Red"}],
        color="Yellow",
        thickness=0.06,
    )
    assert len(lines) == 2
    assert lines[0]["color"] == "Yellow" and lines[0]["thickness"] == 0.06
    assert len(lines[0]["points"]) == 65
    assert lines[1] == {"points": [[0, 1, 0], [5, 1, 0]], "color": "Red", "thickness": 0.06}


def test_req_obj_09_marker_colour_can_be_rgb() -> None:
    lines = marker_lines(lines=[{"points": [[0, 1, 0], [1, 1, 0]], "color": [1, 0.5, 0]}])
    assert lines[0]["color"] == [1, 0.5, 0]


@pytest.mark.parametrize(
    "bad",
    [
        {"lines": [{"points": [[0, 1, 0]]}]},  # a line needs two points
        {"lines": [{"points": [[0, 1]]}]},  # points are [x, y, z]
        {},  # nothing to draw
    ],
)
def test_req_obj_09_invalid_markers_are_rejected(bad: dict) -> None:
    with pytest.raises(ValueError):
        marker_lines(**bad)
