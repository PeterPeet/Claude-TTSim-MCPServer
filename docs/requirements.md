# Requirements — TTS-MCP

Status values: `draft` → `agreed` → `done`. Only `agreed` requirements get implemented.
All requirements start as `draft` until Peter confirms them.

## User story

> As a solo tabletop player, I want Claude to have full access to Tabletop Simulator through an MCP server,
> so that Claude can see and handle pieces on the table and play games against me. Each game's rules and
> table conventions come from a separate skill.

## Goal

Peter plays a game in TTS against Claude. Claude reads the table, moves its own pieces, rolls real dice
and follows the rules; Peter watches everything happen in TTS. Backgammon is the first demonstration;
Age of Sigmar (Spearhead) is the long-term goal.

## Non-goals (for now)

- Visual recognition from screenshots
- Multiplayer or networked games beyond Peter's own machine
- Editing or saving the loaded mod's scripts
- Automatic enforcement of every rule (Peter remains the referee for edge cases)

---

## Phase 1 — Access (REQ-COM)

**REQ-COM-01 Execute Lua** — `done`
The bridge can send a Lua snippet to TTS and receive its return value.
- Acceptance: executing `return 1+1` returns `2`; a table return value arrives as a dict/list.

**REQ-COM-02 Timeout** — `done`
If TTS does not answer within a configurable timeout (default 5 s), the call raises `TTSTimeoutError`
instead of hanging.

**REQ-COM-03 Lua errors** — `done`
A Lua runtime error in TTS is surfaced as `TTSLuaError` containing the TTS error message.

**REQ-COM-04 Not running** — `done`
If nothing is listening on port 39999, the call raises `TTSNotRunningError` with a hint to start TTS
and load a game.

**REQ-COM-05 Events** — `done`
Messages TTS sends on its own (print, error, game loaded, game saved, object created) are received and kept
in a bounded buffer that can be read later.

**REQ-COM-06 Fake TTS** — `done`
`tests/fake_tts.py` provides a fake server with scripted responses (success, Lua error, no reply, events)
so all of REQ-COM can be tested without the game.

## Phase 2 — MCP server, raw access (REQ-MCP)

**REQ-MCP-01 Server** — `done`
`python -m tts_mcp` starts an MCP server over stdio that Claude Code can register.
- Acceptance: registered in Claude Code, its tools are listed, and `run_lua("return 1+1")` returns `2`
  against the real game.

**REQ-MCP-02 Raw access tools** — `done`
- `run_lua(code)` — execute Lua in the global context, return the result.
- `get_scripts()` — read the loaded mod's Global and object scripts (read-only).
- `get_events(since?)` — return buffered TTS events (REQ-COM-05).
- `tts_status()` — whether TTS is reachable and which game is loaded.

**REQ-MCP-03 Thin adapter** — `done`
The MCP layer contains no logic: only argument parsing and calls into `tts_mcp.comms` / `tts_mcp.table`.

**REQ-MCP-04 Errors as tool results** — `done`
`TTSTimeoutError`, `TTSLuaError` and `TTSNotRunningError` reach Claude as readable tool errors, not crashes.

## Phase 3 — 3D controls (REQ-OBJ, REQ-DICE)

All positions and distances are in TTS world units; any conversion to game units (inches etc.) is done by skills.

**REQ-OBJ-01 List objects** — `agreed`
List objects on the table with GUID, name, description, type, tags, tint, position and rotation.
Filters by name, tag or type are optional.

**REQ-OBJ-02 Inspect object** — `agreed`
Return the full details of one object, including bounds and any snap points it has.

**REQ-OBJ-03 Move object** — `agreed`
Move an object to a target position (optional rotation), smoothly by default so Peter sees it happen.
- Acceptance: after the move settles, the object's position is within a small tolerance of the target.

**REQ-OBJ-04 Move many** — `agreed`
Move several objects in one call (e.g. a stack of checkers or a unit), keeping or setting their positions.

**REQ-OBJ-05 Table geometry** — `agreed`
Report the table surface bounds and global snap points, so a skill can map game locations to coordinates.

**REQ-OBJ-06 Measure** — `agreed`
Distance between two objects or points in world units (centre to centre; edge to edge where bounds allow).

**REQ-OBJ-07 Highlight** — `agreed`
Highlight an object temporarily, so Claude can point at a piece for Peter.

**REQ-DICE-01 Roll physical dice** — `agreed`
Roll one or more existing dice objects on the table and return their values once all have stopped.
- Acceptance: rolling two d6 returns two values in 1..6 that match what TTS shows.

**REQ-DICE-02 Read dice** — `agreed`
Read the current face value of dice without rolling them (for dice Peter rolled).

## Phase 4 — Backgammon (REQ-BG)

**REQ-BG-01 Skill** — `agreed`
`skills/tts-backgammon/SKILL.md` explains how to play Backgammon in TTS with the TTS-MCP tools:
how to find the board, checkers and dice, the mapping of the 24 points, bar and bear-off to table coordinates,
the rules, and the turn flow with Peter.

**REQ-BG-02 Read position** — `agreed`
Following the skill, Claude can read the full position (checkers per point, bar, borne off) from the table.
- Acceptance: on a freshly set-up board Claude reports the standard starting position.

**REQ-BG-03 Make a move** — `agreed`
Claude rolls its dice, chooses a legal move, states it in backgammon notation, and moves the checkers
in TTS onto the correct points, stacked neatly.

**REQ-BG-04 Peter's turn** — `agreed`
Claude waits for Peter to say he has moved, re-reads the position, and points out if the move looks illegal
(Peter decides).

**REQ-BG-05 Full game** — `agreed`
Claude and Peter play a complete game, including hitting, entering from the bar and bearing off.
Doubling cube is optional.

**REQ-BG-06 Install** — `agreed`
The skill and MCP server can be installed into Claude Code from this repo with documented steps.

---

## Open questions (resolve by spike against real TTS)

- **Q1** Exact External Editor API message format. — **Resolved 2026-10-05 (spike):** send
  `{"messageID": 3, "guid": "-1", "script": "...", "returnID": <n>}` to :39999 (one connection per message).
  The reply arrives on :39998 as `{"messageID": 5, "returnID": <n>, "returnValue": <v>}`.
  `returnValue` is omitted when the script returns `nil`. Numbers arrive as floats (`2.0`).
- **Q2** Connections and serialisation. — **Resolved 2026-10-05 (spike):** TTS opens a new connection to :39998
  for every message and sends one pretty-printed JSON object per connection.
  Strings, numbers and booleans come back directly. **Returning a Lua table produces no reply at all**
  (the call would time out). `JSON.encode(...)` inside the script works: the value arrives as a JSON string.
  A Lua error arrives first as `{"messageID": 3, "guid": "-1", "error": "...", "errorMessagePrefix": "..."}`
  **without a returnID**, followed by a messageID 5 with the returnID and no returnValue.
  `print()` arrives as `{"messageID": 2, "message": "..."}`.
  Consequence for implementation: wrap scripts in Lua so tables are JSON-encoded and errors are caught with
  `pcall`, then returned under the same returnID. This also makes errors unambiguous when calls overlap.
- **Q3** Other listeners on :39998. — **Resolved 2026-10-05:** nothing else was listening on Peter's machine.
  An editor plugin (VS Code/Atom) would block it; `TTSNotRunningError`'s hint should mention this.
- **Q4** How is Peter's Backgammon mod built: board as one object, checkers named or tinted per colour,
  snap points per point, scripted dice or plain dice?
  — **Partly answered 2026-10-05 (spike):** 35 objects: 1 `Board`, 4 `Dice`, 30 `Backgammon Piece`.
  All have empty names. Colours, positions and snap points are still to be checked.
- **Q5** Which colour does Claude play, and who rolls Claude's dice (Claude via tool, or Peter)?
  — **Resolved 2026-10-05 (Peter):** Claude plays the colour the game assigns it; if none is assigned, the
  light (white) side. Decided by Claude, since Peter left it open: Claude rolls its own dice with the dice tool
  (REQ-DICE-01), so every roll is a visible physical roll in TTS. Peter rolls his own, and Claude reads them
  (REQ-DICE-02).
- **Q6** Does `getScripts` (messageID 0) have any side effects on the loaded game?
  — **Resolved 2026-10-05 by avoiding it:** `get_scripts` reads scripts with read-only Lua
  (`getLuaScript`, `UI.getXml`), so messageID 0 is never sent. The game name comes from `Info.name`.

## Changelog

- 2026-10-05 — Restarted from the TTS-MCP user story; Backgammon first, Age of Sigmar later.
  Replaces the earlier AoS-first draft.
- 2026-10-05 — All requirements marked `agreed` by Peter.
- 2026-10-05 — Spike results recorded for Q1–Q3, Q4 partly. No requirement changed.
- 2026-10-05 — Q5 resolved. No requirement changed.
- 2026-10-05 — Phase 1 done: REQ-COM-01..06 pass (unit, contract, and integration against real TTS).
- 2026-10-05 — Phase 2: REQ-MCP-02..04 done. REQ-MCP-01 passes over stdio against real TTS; the
  Claude Code registration (`.mcp.json`) still needs Peter's check in a new session. Q6 resolved.
- 2026-10-05 — REQ-MCP-01 done: tools listed and run_lua returns 2 in a Claude Code session. Phase 2 complete.
