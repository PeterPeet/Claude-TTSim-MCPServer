# TTSim-MCP

An MCP server that gives Claude full access to Tabletop Simulator (TTSim) through its External Editor API,
plus game skills that teach Claude how to play specific games in TTSim against Peter.

## User story

> As a solo tabletop player, I want Claude to have full access to Tabletop Simulator through an MCP server,
> so that Claude can see and handle pieces on the table and play games against me. Each game's rules and
> table conventions come from a separate skill.

First demonstration: **Backgammon** (`skills/ttsim-backgammon`). Long-term goal: Warhammer Age of Sigmar (Spearhead).

## Working method: requirements-driven

- `docs/requirements.md` is the source of truth. Every requirement has a stable ID (`REQ-<AREA>-<NN>`).
- Only requirements with status `agreed` get implemented.
- Order of work for any requirement: **agree acceptance criteria → write failing test → implement → green**.
- Every test references the requirement it verifies, in its name or docstring
  (e.g. `test_req_com_01_execute_lua_returns_value`).
- Never change a requirement silently. If implementation shows a requirement is wrong or incomplete, stop,
  propose the change to Peter, and update `docs/requirements.md` (with a changelog line) before coding on.
- Unverified assumptions about TTSim behaviour go under "Open questions" in `docs/requirements.md`.
  Resolve them with a spike against the real game and record the result there.

## Architecture (layers, bottom to top)

1. **Access** — `ttsim_mcp/comms.py`: raw External Editor API. Sends JSON to TTSim on `localhost:39999`,
   listens on `localhost:39998` for messages from TTSim. No knowledge of objects or games.
   `ttsim_mcp/access.py`: read-only helpers on top of it (status, scripts, events).
2. **3D controls** — `ttsim_mcp/table.py`: objects, positions, rotations, moves, dice, measuring.
   Generic: knows about objects and coordinates, never about a specific game.
3. **MCP adapter** — `ttsim_mcp/server.py`: thin layer exposing layers 1 and 2 as MCP tools. Argument parsing only, no logic.
4. **Game skills** — `skills/<game>/SKILL.md` (+ optional data files): how a specific TTSim mod is laid out,
   the rules, and how to play against Peter using the MCP tools. Skills contain no Python.

Lower layers must not import upper layers. Game knowledge belongs in skills, not in `ttsim_mcp/`.
If a skill needs a capability the tools lack, add a *generic* tool to layer 2.

## Tech

- Python 3.11+, standard library first (socket, json, asyncio, dataclasses).
- The official MCP Python SDK (`mcp`) for layer 3. Other dependencies only when justified.
- `pytest` for tests, `ruff` for lint and format. Type hints everywhere.

## Lua

- All Lua sent to TTSim lives in `ttsim_mcp/lua/` as template files, not as inline strings in Python.
  The exception is the `run_lua` tool, which sends caller-supplied Lua as-is.
- Always initialise locals: write `local x = nil`, never `local x`. TTSim's Lua (MoonSharp) does not reset an
  uninitialised local to nil; it can hold a stale value from earlier code (found 2026-10-05, see Q10).
- Never send "Save & Play" (messageID 1) or anything else that overwrites the loaded mod's scripts
  without Peter's explicit consent.

## Tests

- `tests/unit/` — no network, no TTSim.
- `tests/contract/` — against `tests/fake_ttsim.py`, a fake TTSim that mimics ports 39999/39998.
  Default test target; must pass without TTSim running.
- `tests/integration/` — marked `@pytest.mark.ttsim`, require TTSim open with a game loaded. Skipped by default.

Commands (virtualenv in `.venv/`, set up with `python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`):
- `.venv/bin/pytest` — unit + contract
- `.venv/bin/pytest -m ttsim` — integration against real TTSim
- `.venv/bin/ruff check . && .venv/bin/ruff format --check .`

Only one program can listen on port 39998. While a Claude Code session has the `ttsim` MCP server
(`.mcp.json`) running, `pytest -m ttsim` fails with `TTSimListenerError`; run integration tests outside such a session
or with the server disabled.

## MCP SDK

`mcp` 2.x: the server class is `MCPServer` (`mcp.server.mcpserver`), not v1's `FastMCP`.
Exceptions other than `ToolError` reach the client only as a generic "Error executing tool …",
so the adapter converts `TTSimError` to `ToolError`.

## Phases

1. Access (REQ-COM)
2. MCP server with raw access tools (REQ-MCP)
3. 3D controls (REQ-OBJ, REQ-DICE)
4. Backgammon skill and a full game against Peter (REQ-BG)
5. Nine Men's Morris skill and coin flips (REQ-NMM, REQ-DICE-03)
6. Later: Age of Sigmar skill and any generic tools it needs

Finish and test a phase before starting the next one.
