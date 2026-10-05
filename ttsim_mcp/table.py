"""3D controls (layer 2, REQ-OBJ, REQ-DICE): objects, positions, moves, measuring and dice.

Generic: knows about objects and coordinates, never about a specific game.
All positions and distances are in TTSim world units; skills convert to game units.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ttsim_mcp.comms import TTSimConnection, TTSimTimeoutError, render_lua

POLL_INTERVAL = 0.15
MOVE_TIMEOUT = 10.0
ROLL_TIMEOUT = 15.0
# A die is read only after this long, so a roll is never read before it has left the table.
MIN_ROLL_TIME = 0.5
# A die tilted more than this from lying flat counts as cocked (45° = two faces equally up).
COCKED_TILT_DEGREES = 10.0

Point = Sequence[float]
Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class Box:
    """World-axis bounding box; a point is a box of size 0."""

    center: Vec3
    size: Vec3


def rounded(data: Any, digits: int = 4) -> Any:
    """Round all floats in nested data, so tool output carries no physics noise like 2.5e-06."""
    if isinstance(data, float):
        return round(data, digits) + 0.0  # + 0.0 turns -0.0 into 0.0
    if isinstance(data, list):
        return [rounded(v, digits) for v in data]
    if isinstance(data, dict):
        return {k: rounded(v, digits) for k, v in data.items()}
    return data


def center_distance(a: Box, b: Box) -> float:
    """Horizontal (x/z) distance between box centres; height is ignored."""
    return math.hypot(b.center[0] - a.center[0], b.center[2] - a.center[2])


def edge_distance(a: Box, b: Box) -> float:
    """Horizontal (x/z) gap between two boxes; 0 if they overlap."""
    gaps = []
    for axis in (0, 2):
        span = abs(b.center[axis] - a.center[axis]) - (a.size[axis] + b.size[axis]) / 2
        gaps.append(max(span, 0.0))
    return math.hypot(*gaps)


def is_cocked(tilt: float, tolerance: float = COCKED_TILT_DEGREES) -> bool:
    """Whether a die's tilt (degrees between its top face and straight up, computed in Lua) is too large."""
    return tilt > tolerance


def _run(conn: TTSimConnection, template: str, args: dict[str, Any] | None = None) -> Any:
    return conn.execute_lua(render_lua(template, args))


def _given(**args: Any) -> dict[str, Any]:
    return {k: v for k, v in args.items() if v is not None}


def _poll(
    read: Callable[[], Any],
    done: Callable[[Any], bool],
    describe_pending: Callable[[Any], str],
    timeout: float,
    poll_interval: float,
    min_time: float = 0.0,
) -> Any:
    start = time.monotonic()
    while True:
        state = read()
        elapsed = time.monotonic() - start
        if elapsed >= min_time and done(state):
            return state
        if elapsed >= timeout:
            raise TTSimTimeoutError(f"Still not settled after {timeout:g} s: {describe_pending(state)}")
        time.sleep(poll_interval)


def list_objects(
    conn: TTSimConnection,
    *,
    name: str | None = None,
    type: str | None = None,
    tag: str | None = None,
    tint: str | None = None,
) -> dict[str, Any]:
    """Objects on the table with GUID, name, description, type, tags, tint, position, rotation."""
    if tint is not None:
        tint = tint.lower().lstrip("#")
    return rounded(_run(conn, "list_objects.lua", _given(name=name, type=type, tag=tag, tint=tint)))


def inspect_object(conn: TTSimConnection, guid: str) -> dict[str, Any]:
    """Full details of one object, including bounds and snap points (world coordinates)."""
    return rounded(_run(conn, "inspect_object.lua", {"guid": guid}))


def move_object(
    conn: TTSimConnection,
    guid: str,
    position: Point,
    rotation: Point | None = None,
    smooth: bool = True,
    timeout: float = MOVE_TIMEOUT,
    poll_interval: float = POLL_INTERVAL,
) -> dict[str, Any]:
    """Move one object and wait until it has settled; returns its final position and rotation."""
    move = _given(guid=guid, position=list(position), rotation=list(rotation) if rotation else None)
    return move_objects(conn, moves=[move], smooth=smooth, timeout=timeout, poll_interval=poll_interval)


def move_objects(
    conn: TTSimConnection,
    moves: Sequence[dict[str, Any]] | None = None,
    guids: Sequence[str] | None = None,
    offset: Point | None = None,
    smooth: bool = True,
    timeout: float = MOVE_TIMEOUT,
    poll_interval: float = POLL_INTERVAL,
) -> dict[str, Any]:
    """Move several objects at once, either to explicit positions (`moves`: [{guid, position, rotation?}])
    or all by the same `offset` (`guids` + `offset`, keeping their formation). Waits until all have settled.
    """
    if (moves is None) == (guids is None and offset is None):
        raise ValueError("Give either `moves`, or `guids` together with `offset`.")
    if moves is None:
        if not guids or offset is None:
            raise ValueError("Moving by offset needs both `guids` and `offset`.")
        moves = [{"guid": g, "offset": list(offset)} for g in guids]
    if not moves:
        raise ValueError("Nothing to move.")
    _run(conn, "move_objects.lua", {"moves": list(moves), "smooth": smooth})
    state = _poll(
        read=lambda: _run(conn, "motion_state.lua", {"guids": [m["guid"] for m in moves]}),
        done=lambda s: all(not o["moving"] and o["resting"] for o in s["objects"]),
        describe_pending=lambda s: ", ".join(
            o["guid"] for o in s["objects"] if o["moving"] or not o["resting"]
        ),
        timeout=timeout,
        poll_interval=poll_interval,
    )
    objects = [
        _given(guid=o["guid"], position=o["position"], rotation=o.get("rotation")) for o in state["objects"]
    ]
    return rounded({"objects": objects})


def table_geometry(conn: TTSimConnection) -> dict[str, Any]:
    """Table type and bounding box, plus global snap points."""
    return rounded(_run(conn, "table_geometry.lua"))


def measure(conn: TTSimConnection, a: str | Point, b: str | Point) -> dict[str, Any]:
    """Horizontal distance between two objects (GUIDs) or points ([x, y, z]), in world units.

    `center`: between centres. `edge`: between the objects' bounding boxes (0 if they overlap).
    """
    guids = [t for t in (a, b) if isinstance(t, str)]
    boxes: dict[str, Box] = {}
    if guids:
        for o in _run(conn, "bounds.lua", {"guids": guids})["objects"]:
            boxes[o["guid"]] = Box(center=tuple(o["center"]), size=tuple(o["size"]))

    def box(target: str | Point) -> Box:
        if isinstance(target, str):
            return boxes[target]
        return Box(center=(target[0], target[1], target[2]), size=(0.0, 0.0, 0.0))

    box_a, box_b = box(a), box(b)
    return rounded(
        {
            "center": center_distance(box_a, box_b),
            "edge": edge_distance(box_a, box_b),
            "dx": box_b.center[0] - box_a.center[0],
            "dy": box_b.center[1] - box_a.center[1],
            "dz": box_b.center[2] - box_a.center[2],
        }
    )


def highlight(
    conn: TTSimConnection, guid: str, color: str = "Yellow", seconds: float = 3.0
) -> dict[str, Any]:
    """Highlight an object for a few seconds, to point it out to the player."""
    _run(conn, "highlight.lua", {"guid": guid, "color": color, "seconds": seconds})
    return {"guid": guid, "color": color, "seconds": seconds}


def _dice_result(dice: list[dict[str, Any]], cocked_tilt: float) -> dict[str, Any]:
    for d in dice:
        d["cocked"] = is_cocked(d["tilt"], cocked_tilt)
    return rounded(
        {
            "dice": dice,
            # Coins report a face name ("Heads"); only numeric dice values count towards the total.
            "total": sum(d["value"] for d in dice if isinstance(d["value"], int | float)),
            "cocked": [d["guid"] for d in dice if d["cocked"]],
        }
    )


def roll_dice(
    conn: TTSimConnection,
    guids: Sequence[str],
    timeout: float = ROLL_TIMEOUT,
    poll_interval: float = POLL_INTERVAL,
    min_roll_time: float = MIN_ROLL_TIME,
    cocked_tilt: float = COCKED_TILT_DEGREES,
) -> dict[str, Any]:
    """Roll dice with TTSim's physics roll (coins and other objects with named faces: TTSim's randomize)
    and return their values once all have come to rest."""
    if not guids:
        raise ValueError("roll_dice needs at least one die GUID.")
    _run(conn, "roll_dice.lua", {"guids": list(guids)})
    state = _poll(
        read=lambda: _run(conn, "dice_state.lua", {"guids": list(guids)}),
        done=lambda s: all(d["resting"] for d in s["dice"]),
        describe_pending=lambda s: ", ".join(d["guid"] for d in s["dice"] if not d["resting"]),
        timeout=timeout,
        poll_interval=poll_interval,
        min_time=min_roll_time,
    )
    return _dice_result(state["dice"], cocked_tilt)


def read_dice(
    conn: TTSimConnection, guids: Sequence[str] | None = None, cocked_tilt: float = COCKED_TILT_DEGREES
) -> dict[str, Any]:
    """Current values of the given dice/coins, or of all dice and coins on the table, without rolling them."""
    state = _run(conn, "dice_state.lua", _given(guids=list(guids) if guids else None))
    return _dice_result(state["dice"], cocked_tilt)
