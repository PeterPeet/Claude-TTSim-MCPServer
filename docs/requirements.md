# Requirements — TTSim-MCP

Status values: `draft` → `agreed` → `done`. Only `agreed` requirements get implemented.
All requirements start as `draft` until Peter confirms them.

## User story

> As a solo tabletop player, I want Claude to have full access to Tabletop Simulator through an MCP server,
> so that Claude can see and handle pieces on the table and play games against me. Each game's rules and
> table conventions come from a separate skill.

## Goal

Peter plays a game in TTSim against Claude. Claude reads the table, moves its own pieces, rolls real dice
and follows the rules; Peter watches everything happen in TTSim. Backgammon is the first demonstration;
Age of Sigmar (Spearhead) is the long-term goal.

## Non-goals (for now)

- Visual recognition from screenshots (reading a single card or rule sheet image that the game itself uses is allowed,
  see REQ-OBJ-08)
- Multiplayer or networked games beyond Peter's own machine
- Editing or saving the loaded mod's scripts
- Automatic enforcement of every rule (Peter remains the referee for edge cases)

---

## Phase 1 — Access (REQ-COM)

**REQ-COM-01 Execute Lua** — `done`
The bridge can send a Lua snippet to TTSim and receive its return value.
- Acceptance: executing `return 1+1` returns `2`; a table return value arrives as a dict/list.

**REQ-COM-02 Timeout** — `done`
If TTSim does not answer within a configurable timeout (default 5 s), the call raises `TTSimTimeoutError`
instead of hanging.

**REQ-COM-03 Lua errors** — `done`
A Lua runtime error in TTSim is surfaced as `TTSimLuaError` containing the TTSim error message.

**REQ-COM-04 Not running** — `done`
If nothing is listening on port 39999, the call raises `TTSimNotRunningError` with a hint to start TTSim
and load a game.

**REQ-COM-05 Events** — `done`
Messages TTSim sends on its own (print, error, game loaded, game saved, object created) are received and kept
in a bounded buffer that can be read later.

**REQ-COM-06 Fake TTSim** — `done`
`tests/fake_ttsim.py` provides a fake server with scripted responses (success, Lua error, no reply, events)
so all of REQ-COM can be tested without the game.

## Phase 2 — MCP server, raw access (REQ-MCP)

**REQ-MCP-01 Server** — `done`
`python -m ttsim_mcp` starts an MCP server over stdio that Claude Code can register.
- Acceptance: registered in Claude Code, its tools are listed, and `run_lua("return 1+1")` returns `2`
  against the real game.

**REQ-MCP-02 Raw access tools** — `done`
- `run_lua(code)` — execute Lua in the global context, return the result.
- `get_scripts()` — read the loaded mod's Global and object scripts (read-only).
- `get_events(since?)` — return buffered TTSim events (REQ-COM-05).
- `ttsim_status()` — whether TTSim is reachable and which game is loaded.

**REQ-MCP-03 Thin adapter** — `done`
The MCP layer contains no logic: only argument parsing and calls into `ttsim_mcp.comms` / `ttsim_mcp.table`.

**REQ-MCP-04 Errors as tool results** — `done`
`TTSimTimeoutError`, `TTSimLuaError` and `TTSimNotRunningError` reach Claude as readable tool errors, not crashes.

## Phase 3 — 3D controls (REQ-OBJ, REQ-DICE)

All positions and distances are in TTSim world units; any conversion to game units (inches etc.) is done by skills.

**REQ-OBJ-01 List objects** — `done`
List objects on the table with GUID, name, description, type, tags, tint, position and rotation.
Filters by name, tag or type are optional.

**REQ-OBJ-02 Inspect object** — `done`
Return the full details of one object, including bounds and any snap points it has.

**REQ-OBJ-03 Move object** — `done`
Move an object to a target position (optional rotation), smoothly by default so Peter sees it happen.
- Acceptance: after the move settles, the object's position is within a small tolerance of the target.

**REQ-OBJ-04 Move many** — `done`
Move several objects in one call (e.g. a stack of checkers or a unit), keeping or setting their positions.

**REQ-OBJ-05 Table geometry** — `done`
Report the table surface bounds and global snap points, so a skill can map game locations to coordinates.

**REQ-OBJ-06 Measure** — `done`
Distance between two objects or points in world units (centre to centre; edge to edge where bounds allow).

**REQ-OBJ-07 Highlight** — `done`
Highlight an object temporarily, so Claude can point at a piece for Peter.

**REQ-DICE-01 Roll physical dice** — `done`
Roll one or more existing dice objects with TTSim's physics roll (`roll()`: the die is lifted and spun visibly, as when
a player presses R), and return the values once all dice have stopped. Flag dice that came to rest tilted (cocked).
- Acceptance: rolling two d6 visibly rolls them in TTSim and returns two values in 1..6 that match what TTSim shows.

**REQ-DICE-02 Read dice** — `done`
Read the current face value of dice without rolling them (for dice Peter rolled).

## Phase 4 — Backgammon (REQ-BG)

**REQ-BG-01 Skill** — `done`
`skills/ttsim-backgammon/SKILL.md` explains how to play Backgammon in TTSim with the TTSim-MCP tools:
how to find the board, checkers and dice, the mapping of the 24 points, bar and bear-off to table coordinates,
the rules, and the turn flow with Peter.

**REQ-BG-02 Read position** — `done`
Following the skill, Claude can read the full position (checkers per point, bar, borne off) from the table.
- Acceptance: on a freshly set-up board Claude reports the standard starting position.

**REQ-BG-03 Make a move** — `done`
Claude rolls its dice, chooses a legal move, states it in backgammon notation, and moves the checkers
in TTSim onto the correct points, stacked neatly.

**REQ-BG-04 Peter's turn** — `done`
Claude waits for Peter to say he has moved, re-reads the position, and points out if the move looks illegal
(Peter decides).

**REQ-BG-05 Full game** — `done`
Claude and Peter play a complete game, including hitting, entering from the bar and bearing off.
Doubling cube is optional.

**REQ-BG-06 Install** — `done`
The skill and MCP server can be installed into Claude Code from this repo with documented steps.

## Phase 5 — Nine Men's Morris (REQ-NMM, REQ-DICE-03)

Table: the Steam Workshop mod "Nine Men's Morris" (see Q11). Peter plays red (rack on his side), Claude blue.
Removed tokens are put on the table beside their owner's rack.

**REQ-DICE-03 Flip coins** — `done`
`roll_dice` and `read_dice` also accept coins (any object with named faces): a coin is flipped with TTSim's own
randomize (which runs the coin's script, if it has one) and its result is reported by face name, e.g. "Heads".
Generic, in layer 2; no game knowledge.
- Acceptance: flipping the mod's coin visibly throws it and returns "Heads" or "Tails" matching what TTSim shows.

**REQ-NMM-01 Skill** — `done`
`skills/ttsim-nine-mens-morris/SKILL.md` explains the table (board, racks, tokens, coin, reset button), the
standard notation (a1–g7, row 1 on Peter's side, column a on his left), the rules (placing, moving, flying with three,
mills, removing, winning) and the turn flow with Peter.

**REQ-NMM-02 Read position** — `done`
Claude can read the position from the table: which of the 24 points hold red or blue tokens, how many tokens each
player still has in hand (on the rack) and how many were removed.
- Acceptance: on a freshly reset board Claude reports 24 empty points and 9 tokens in hand per player.

**REQ-NMM-03 Coin toss** — `done`
Who starts is decided by a coin flip: Peter calls heads or tails, Claude flips the coin (REQ-DICE-03) and reads it.

**REQ-NMM-04 Claude's turn** — `done`
Claude places a token from its rack onto a free point (placing phase), or moves one to an adjacent free point
(moving phase), or to any free point when it has three left (flying). On closing a mill it removes one of Peter's
tokens following the rules and puts it beside the board. Every action is stated in notation (e.g. `d6`, `d6-d5`,
`d6-d5, removes b4`).

**REQ-NMM-05 Peter's turn** — `done`
Claude waits until Peter says he has moved, reads the position, works out his move (and any removal), and points out
if it looks illegal (Peter decides).

**REQ-NMM-06 Reset** — `done`
A new game starts by calling the mod's own reset function (`resetPieces` on the reset button), with Peter's consent.

**REQ-NMM-07 Full game** — `done`
Claude and Peter play a complete game to a win (opponent reduced to two tokens, or unable to move).

## Phase 6 — Card and document faces (REQ-OBJ-08)

Generic tool needed by the next game skill: Claude reads the text of cards and rule sheets on the table. The game
skill itself and its requirements are kept privately, outside this repository.

**REQ-OBJ-08 Card face image** — `done`
Generic, layer 2: return the face of a card (or any custom tile/token) as an image Claude can read, cut out of
the deck's face sheet by its CardID and scaled to at most 2000 px. For a custom PDF object, return the text of its pages
instead (with the page the object currently shows). Images and PDFs are taken from TTSim's local cache
(`~/Library/Tabletop Simulator/Mods/Images`, `.../Mods/PDF`), so nothing is downloaded; if the file is not cached,
the tool says so.
- Acceptance: for a card in Blue's hand, the tool returns the single card (not the whole sheet), and its text is
  readable. For a custom PDF object, the tool returns the text of its pages.

**REQ-OBJ-09 Draw markers** — `done`
Generic, layer 2: draw temporary circles and polylines on the table (TTSim vector lines) to show the player areas,
ranges or planned moves, each with a colour, and remove them again by a label. Markers are added to the existing vector
lines, never replacing the player's own drawings, and can be listed so a skill can check they are still there.
- Acceptance: drawing a 3" circle at a point shows it in TTSim; a line the player drew beforehand is still there;
  clearing by label removes only the tool's markers.

---

## Open questions (resolve by spike against real TTSim)

- **Q1** Exact External Editor API message format. — **Resolved 2026-10-05 (spike):** send
  `{"messageID": 3, "guid": "-1", "script": "...", "returnID": <n>}` to :39999 (one connection per message).
  The reply arrives on :39998 as `{"messageID": 5, "returnID": <n>, "returnValue": <v>}`.
  `returnValue` is omitted when the script returns `nil`. Numbers arrive as floats (`2.0`).
- **Q2** Connections and serialisation. — **Resolved 2026-10-05 (spike):** TTSim opens a new connection to :39998
  for every message and sends one pretty-printed JSON object per connection.
  Strings, numbers and booleans come back directly. **Returning a Lua table produces no reply at all**
  (the call would time out). `JSON.encode(...)` inside the script works: the value arrives as a JSON string.
  A Lua error arrives first as `{"messageID": 3, "guid": "-1", "error": "...", "errorMessagePrefix": "..."}`
  **without a returnID**, followed by a messageID 5 with the returnID and no returnValue.
  `print()` arrives as `{"messageID": 2, "message": "..."}`.
  Consequence for implementation: wrap scripts in Lua so tables are JSON-encoded and errors are caught with
  `pcall`, then returned under the same returnID. This also makes errors unambiguous when calls overlap.
- **Q3** Other listeners on :39998. — **Resolved 2026-10-05:** nothing else was listening on Peter's machine.
  An editor plugin (VS Code/Atom) would block it; `TTSimNotRunningError`'s hint should mention this.
- **Q4** How is Peter's Backgammon mod built: board as one object, checkers named or tinted per colour,
  snap points per point, scripted dice or plain dice?
  — **Partly answered 2026-10-05 (spike):** 35 objects: 1 `Board`, 4 `Dice`, 30 `Backgammon Piece`.
  All have empty names. Colours, positions and snap points are still to be checked.
  — **Mostly answered 2026-10-05 (second spike):** checkers are told apart only by tint: 15 × `bbbbbb` (light)
  and 15 × `4e2c00` (brown). Dice: 2 × white tint `ffffff`, 2 × blue tint `264d71`. The board is locked,
  centred at the origin, 15.22 × 22.91 units (x × z), and has 120 snap points (24 points × 5 checker slots,
  1 unit apart along x). The board has no Lua script; the table is `Table_RPG`. How points are numbered
  is left to the skill (phase 4).
- **Q7** Are object GUIDs stable? — **Resolved 2026-10-05 (spike): no.** After the game was loaded again,
  every object had a new GUID (board `0905ba` → `735307`). Skills must find objects by type, tint, tags
  or position and never store GUIDs between sessions.
- **Q8** How do dice report a roll? — **Resolved 2026-10-05 (spike):** right after `roll()` the die reports
  `resting = false`; about 2 s later `resting = true` and `getValue()` gives the top face.
  So a roll is: `roll()` every die, then poll until all are resting.
  **Fairness test 2026-10-05:** 100 rolls of all 4 dice with `roll()` (400 results), measured every physics frame.
  Faces 1–6: 60/71/69/74/55/71, chi-square 4.16 with 5 degrees of freedom (critical value 11.07 at 5 %), so
  consistent with fair dice. Dice rise 4.7 units on average (2.3 min, 7.5 max) and show 4.1 different faces in
  flight; only 1 of 400 showed a single face. 1 of 400 landed cocked, none timed out. The dice land near where
  they started, which is why it looks like a roll in place, but they drift: after 100 rolls they were up to
  5 units from their start. Skills should put dice back in their home area before rolling.
  **Rolling off the board, 2026-10-05:** dice roll fine on the free table beside the board (drift ~0.3 units), and a
  bowl contains them, but its curved bottom leaves them tilted 10–30°. A flat dice tray would contain them without
  tilt; Peter will provide one later. The Age of Sigmar mod has its own dice area with roll and sort buttons
  (to be explained by Peter).
- **Q9** Tool output shape. — **Found 2026-10-05:** a tool that returns a bare list is shown to Claude as one
  block per item. Tools return objects (e.g. `{"objects": [...]}`) instead.
- **Q5** Which colour does Claude play, and who rolls Claude's dice (Claude via tool, or Peter)?
  — **Resolved 2026-10-05 (Peter):** Claude plays the colour the game assigns it; if none is assigned, the
  light (white) side. Decided by Claude, since Peter left it open: Claude rolls its own dice with the dice tool
  (REQ-DICE-01), so every roll is a visible physical roll in TTSim. Peter rolls his own, and Claude reads them
  (REQ-DICE-02).
- **Q6** Does `getScripts` (messageID 0) have any side effects on the loaded game?
  — **Resolved 2026-10-05 by avoiding it:** `get_scripts` reads scripts with read-only Lua
  (`getLuaScript`, `UI.getXml`), so messageID 0 is never sent. The game name comes from `Info.name`.
- **Q10** Lua quirks in TTSim. — **Found 2026-10-05:** a local declared without a value (`local row`) is not
  guaranteed to be nil in TTSim's Lua (MoonSharp); it held a stale table from earlier code. Always write
  `local row = nil`. Rule added to CLAUDE.md.
- **Q11** How is the Workshop mod "Nine Men's Morris" built? — **Answered 2026-10-05 (spike):** main board
  (type `Board`, centred at the origin) with 24 snap points on three nested squares (half-sizes 6.27, 4.18, 2.09;
  height 2.13), matching the 7 × 7 grid of the standard notation with a step of 2.09. Two racks with 9 snap points
  each: red tokens (`8b3333`, type `Generic`) at z = −11.25 (Peter's side), blue (`1f689b`) at z = +11.25. A coin
  (type `Coin`, faces "Heads" = value 1, "Tails" = value 2) whose script flips it with physics on randomize. A reset
  button (type `Tile`) whose script function `resetPieces()` glides all tokens back to the racks; it creates no
  clickable button, so it is called with `call("resetPieces")`. Unlike the built-in Backgammon, this saved mod's
  Global script lists the token GUIDs, so they are stable here; the skill still finds tokens by tint.

## Changelog

- 2026-10-05 — Restarted from the TTSim-MCP user story; Backgammon first, Age of Sigmar later.
  Replaces the earlier AoS-first draft.
- 2026-10-05 — All requirements marked `agreed` by Peter.
- 2026-10-05 — Spike results recorded for Q1–Q3, Q4 partly. No requirement changed.
- 2026-10-05 — Q5 resolved. No requirement changed.
- 2026-10-05 — Phase 1 done: REQ-COM-01..06 pass (unit, contract, and integration against real TTSim).
- 2026-10-05 — Phase 2: REQ-MCP-02..04 done. REQ-MCP-01 passes over stdio against real TTSim; the
  Claude Code registration (`.mcp.json`) still needs Peter's check in a new session. Q6 resolved.
- 2026-10-05 — REQ-MCP-01 done: tools listed and run_lua returns 2 in a Claude Code session. Phase 2 complete.
- 2026-10-05 — Spike results Q4 (mostly), Q7–Q9 recorded.
- 2026-10-05 — REQ-DICE-01 changed at Peter's request: dice are thrown physically (pick up, throw with
  velocity and spin) instead of using TTSim's `roll()`. Adds the target area and the cocked-die flag.
- 2026-10-05 — REQ-DICE-01 changed back at Peter's request: the scripted throw was not visible enough, so dice
  use TTSim's `roll()` again. Target area dropped; cocked-die flag kept.
- 2026-10-05 — Cocked-die detection fixed (no requirement change): it now uses the true tilt from lying flat,
  computed in Lua from the die's axes. The old check read Euler angles and could misjudge flat dice. Tilt is
  reported per die; the threshold is adjustable (default 10°).
- 2026-10-05 — Phase 3 implemented (REQ-OBJ-01..07, REQ-DICE-01..02): unit and contract tests pass; every Lua
  template was run against the real game via `run_lua`. Status stays `agreed` until `pytest -m ttsim` has run
  (needs port 39998 free, i.e. outside a session with the `ttsim` server) and Peter has confirmed the roll is visible.
- 2026-10-05 — Phase 3 done: `pytest -m ttsim` 18/18 passed against the real game; every tool used live in a Claude Code
  session; 400-roll fairness test for REQ-DICE-01 (Peter saw the dice lift and spin).
- 2026-10-05 — Renamed TTS → TTSim throughout (Peter's request), to avoid confusion with text-to-speech: package
  `ttsim_mcp`, MCP server `ttsim`, tool `ttsim_status`, error classes `TTSim*Error`, pytest marker `ttsim`, skill
  `ttsim-backgammon`. No requirement changed. The project folder keeps its name.
- 2026-10-05 — Phase 4 started. Board mapped (snap points + ray casts): light plays from the left half (home board
  left, z < 0), brown from the right; raised bar at z ±0.7; bear-off tray at z ≈ −10.2. Skill
  `skills/ttsim-backgammon` (SKILL.md + Lua helper `bg.lua`, loaded once per session as `TTSIM_BG`), linked into
  `.claude/skills/` for Claude Code. REQ-BG-02 done: on the real board the helper reports the standard starting
  position for both colours (pip 167 each). Claude plays light with the white dice, rolling them off the board.
- 2026-10-05 — Milestone 1 (Peter): Claude plays Backgammon against Peter in TTSim. Opening roll and two full turns
  each played live: REQ-BG-01, -03, -04 done; REQ-BG-06 done (setup in README.md). REQ-BG-05 (a complete game with
  hits, bar entry and bearing off) stays open: those parts are verified only by planning, not yet in play.
  `main` updated to this state. Next: a skill for another game.
- 2026-10-05 — Phase 5 drafted: Nine Men's Morris (REQ-NMM-01..07) and coin flips (REQ-DICE-03), all `draft`.
  Q11 recorded from the spike on the Workshop mod.
- 2026-10-05 — Phase 5 agreed by Peter: red = Peter, blue = Claude; removed tokens go beside their owner's rack.
- 2026-10-05 — REQ-DICE-03 implemented: `roll_dice` flips coins with TTSim's randomize (runs the coin's own script),
  `read_dice` reports face names and includes coins. Spike: the mod's coin rose 4.3–6.0 units and showed both faces in
  each of 6 flips. Contract tests pass; `pytest -m ttsim` (coin integration test) still to run outside a session.
- 2026-10-05 — Skill `skills/ttsim-nine-mens-morris` (SKILL.md + Lua helper `nmm.lua`, loaded as `TTSIM_NMM`), linked
  into `.claude/skills/`. REQ-NMM-02 done: on the reset board the helper reports 24 empty points and 9 tokens in hand
  per colour. Planning checks verified live (placing, refusing moves while placing, invalid points, removal without
  mill); mill/removal and flying still to be shown in play.
- 2026-10-05 — REQ-DICE-03 done: `pytest -m ttsim` with Nine Men's Morris loaded, 18 passed (incl. the coin flip and
  the four Nine Men's Morris helper tests), 9 skipped (need Backgammon or dice on the table).
- 2026-10-05 — Full games marked played at Peter's request: REQ-BG-05 done (complete Backgammon game) and REQ-NMM-07
  done (Nine Men's Morris played from the placing phase into the moving phase; Peter resigned at 9 blue vs 6 red after
  three mills with removals). REQ-NMM-01 and -05 done: the skill guided the whole game, and Claude worked out each of
  Peter's moves, including a deliberate illegal double move, which it flagged and waited on. Still open: REQ-NMM-03
  (coin toss) and -06 (reset) were not part of this session; REQ-NMM-04 is shown for placing, moving, mills and
  removals, but flying has not come up in play.
- 2026-10-05 — Phase 5 done. REQ-NMM-03 done: Peter confirms the coin toss decided the start of this game (played in
  an earlier session). REQ-NMM-04 done: flying tested live on a staged position (blue reduced to b6 d5 d6). Blue flew
  b6-d7 (not adjacent), closing d5-d6-d7 and removing a4, while the helper refused a non-adjacent move for red
  (6 tokens, cannot fly yet). REQ-NMM-06 done: `reset` returned all 18 tokens to the racks; the helper then read
  24 empty points and 9 in hand per colour.
- 2026-10-05 — Phase 6 drafted and agreed: REQ-OBJ-08 (card and PDF faces from TTSim's local cache, extended to PDF
  objects at Peter's request). Requirements of the game skill that needs it are kept privately.
- 2026-10-05 — REQ-OBJ-09 drafted (draw markers), proposed while marking objectives on a battlefield.
- 2026-10-05 — REQ-OBJ-09 marked `agreed` by Peter.
- 2026-10-05 — REQ-OBJ-09 implemented: draw_markers, list_markers, clear_markers. Unit and contract tests pass; the Lua
  templates were run against the real game via run_lua (a stand-in player line survived drawing and clearing; the
  label registry persists between calls until the game is reloaded). Integration test pending (port 39998 in use).
- 2026-10-05 — REQ-OBJ-08 and REQ-OBJ-09 done: `pytest -m ttsim -k "req_obj_08 or req_obj_09"` 2/2 passed against the real game
  (run by Peter); both tools were also used live (card images, PDF text, objective markers).
