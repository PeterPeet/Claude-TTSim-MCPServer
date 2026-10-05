"""Read-only access to the loaded game, built on comms (REQ-MCP-02).

Scripts are read with Lua (`getLuaScript`, `UI.getXml`) instead of the External Editor API's
getScripts message, so nothing here can trigger a reload or overwrite of the mod's scripts.
"""

from __future__ import annotations

from typing import Any

from ttsim_mcp.comms import TTSimConnection, TTSimError, load_lua


def get_scripts(conn: TTSimConnection) -> dict[str, Any]:
    """Global script/UI plus every object with a non-empty script or UI."""
    return conn.execute_lua(load_lua("get_scripts.lua"))


def status(conn: TTSimConnection) -> dict[str, Any]:
    """Whether TTSim is reachable and, if so, the loaded game, object count and seated players."""
    try:
        info = conn.execute_lua(load_lua("status.lua"))
    except TTSimError as e:
        return {"reachable": False, "error": str(e)}
    return {"reachable": True, **info}


def get_events(conn: TTSimConnection, since: int = 0) -> dict[str, Any]:
    """Buffered TTSim events newer than `since`, with bulky script payloads reduced to a count."""
    events = []
    for event in conn.events(since=since):
        entry: dict[str, Any] = {"seq": event.seq, "time": event.time, "kind": event.kind}
        for key, value in event.message.items():
            if key == "messageID":
                continue
            if key == "scriptStates":
                entry["scripts"] = len(value)
            else:
                entry[key] = value
        events.append(entry)
    last_seq = events[-1]["seq"] if events else since
    return {"events": events, "last_seq": last_seq}
