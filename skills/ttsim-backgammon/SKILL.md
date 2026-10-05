---
name: ttsim-backgammon
description: Play Backgammon against Peter in Tabletop Simulator (TTSim) using the ttsim MCP tools — set up the board, roll real dice, move checkers, check Peter's moves. Use whenever Peter wants to play, continue or set up a backgammon game in TTSim.
---

# Backgammon in TTSim

You play Backgammon against Peter on his TTSim table. You see the table only through the `ttsim` MCP tools
(`ttsim_status`, `run_lua`, `list_objects`, `move_objects`, `roll_dice`, `read_dice`, `highlight`, ...).
Peter watches everything happen in TTSim, so every move you make must be visible and tidy.

## 1. Before the first move of a session

1. `ttsim_status` — TTSim must be reachable and `game` must be `Backgammon`.
2. Load the helper: read `bg.lua` (next to this file) and send its whole content with `run_lua`.
   It defines the Lua function `TTSIM_BG` inside TTSim. If any later call fails with
   "attempt to call a nil value", Peter reloaded the game: send `bg.lua` again.
3. `return TTSIM_BG({ action = "read" })` — read the position (see section 3).

Object GUIDs change every time the game is loaded. Never reuse GUIDs from an earlier session; find objects by type
and tint (`list_objects`) or through the helper.

## 2. The table

| What | How to find it |
|---|---|
| Board | the only object of type `Board`, locked, centred at the origin |
| Light checkers (yours) | type `Backgammon Piece`, tint `bbbbbb`, 15 pieces |
| Brown checkers (Peter's) | type `Backgammon Piece`, tint `4e2c00`, 15 pieces |
| Your dice | type `Dice`, tint `ffffff` (white), 2 dice |
| Peter's dice | type `Dice`, tint `264d71` (blue), 2 dice |

**Colours.** You play the colour the game assigns you; if none is assigned, light. Peter plays brown. Peter's seat
is near brown's home board.

**Geometry** (world units, y is up). The board's long axis is z. The left half (x < 0) holds light's points 1–12,
the right half (x > 0) light's points 13–24. Each point is a row of 5 snap points running from the board edge
(|x| ≈ 6.5) inwards (|x| ≈ 2.5). The raised bar runs across the middle (z between −0.7 and 0.7). Both home boards
are at the z < 0 end; the bear-off tray there (z ≈ −10.2) takes borne-off checkers: light on the left half, brown on
the right. The strip between the point tips (x between −2 and 2) is where the dice lie between rolls.

**Numbering.** Each player counts their own points: 1 = deepest point of their home board, 24 = their starting
corner. Brown's number for a point is 25 minus light's number. Always talk to Peter in **his** numbers when you
describe his checkers and in **yours** for your own, and say whose numbers you use when it could be unclear.

## 3. The helper `TTSIM_BG`

Call it with `run_lua`, e.g. `return TTSIM_BG({ action = "read" })`.

| Action | Moves anything? | Returns |
|---|---|---|
| `read` | no | `light` / `brown`: "point:count" in each player's own numbers; `bar`, `off`, `pip` per colour; `loose` checkers it cannot place on a point; `conflicts` (points holding both colours — should be empty); `moving` (checkers still in motion — read again if > 0) |
| `plan` with `color` and `moves = { {from, to}, ... }` | no | `notation` (e.g. `24/18 13/11*`), `hits`, and `moves`: `[{guid, position}]` for the `move_objects` tool. Uses the mover's own numbers; 25 = bar, 0 = off. Several entries for one checker are fine (`{13, 7}, {7, 1}`). Refuses blocked points, moving while on the bar, and bearing off before all checkers are home. It does **not** check that the move matches the dice — that is your job. |
| `tidy` | no | `moves` that straighten every checker into its proper slot (after Peter left pieces askew) |
| `setup` | no | `moves` that put all 30 checkers into the starting position |

To carry out `plan`, `tidy` or `setup`: pass its `moves` to `move_objects` (smooth, waits until everything has
settled), then `read` again and check the result. Hit checkers are moved to the bar automatically by `plan`.

## 4. Dice

- **Your roll:** first glide both white dice to your dice spot beside the board, then roll them there, so no die
  can knock a checker: `move_objects` with your two dice to `[-11, 1.6, 8]` and `[-11, 1.6, 9.5]`, then
  `roll_dice` with their GUIDs. If Peter has put a dice tray on the table, use the tray instead.
- If `roll_dice` reports a die in `cocked`, or a die ends up off the table, roll both again (standard rule).
- **Peter's roll:** Peter rolls his blue dice himself. When he says he has rolled or moved, `read_dice` with the blue
  dice's GUIDs.
- Never invent or "assume" dice values. Every value comes from a physical die in TTSim.

## 5. A game, step by step

**New game.** `read`. If it is not the starting position (`24:2 13:5 8:3 6:5` for both colours), ask Peter whether
to set up a new game; on yes, `setup` → `move_objects`. Then the opening roll: you roll one white die, Peter rolls
one blue die. Equal → both roll again. The higher die starts and plays **both** numbers as its first move.

**Your turn.**
1. Roll (section 4). Tell Peter the roll.
2. Work out your legal moves from the position (section 6) and choose one (section 7).
3. `plan` it, then `move_objects` with the returned moves, then `read` and confirm the position is what you expected.
4. Tell Peter your move in notation, e.g. "I rolled 6-2: 24/18 13/11 (my numbers)." Mention hits and the pip counts.
5. Hand over: "Your turn."

**Peter's turn.**
1. Wait until Peter says he has moved. Do not touch his pieces or dice before that.
2. `read_dice` (blue dice) and `read`. Work out his move by comparing brown's points, the bar and light's bar with the
   position after your last move.
3. Check it against his dice and the rules. If it looks illegal, say exactly why — Peter decides (he is the referee).
4. If his checkers lie askew (`loose` not empty, or the position looks right but untidy), run `tidy` and carry it out.
5. Your turn.

**End.** The first player to bear off all 15 checkers wins. Gammon (2 points) if the loser has borne off none;
backgammon (3 points) if the loser also still has a checker on the bar or in the winner's home board.
There is no doubling cube on this table; if Peter wants one, track the cube value in the conversation.

## 6. Rules checklist (legality)

- Each die is a separate move of one checker by that many points, from higher to lower own numbers.
  Doubles are played four times.
- A checker may land on an empty point, an own point, or a point with exactly one opposing checker (a blot), which is
  hit and goes to the bar. Two or more opposing checkers block the point.
- A player with a checker on the bar must enter it first: entering with die d lands on own point 25 − d
  (in the opponent's home board). No other checker moves until all are entered.
- You must use both dice if any legal way allows it. If only one can be used, use the higher one if possible.
- Bearing off only when all 15 checkers are in the home board (own points 1–6). A die bears off a checker from the
  matching point; a higher die may bear off from the highest occupied point if no checker is on a higher point.

## 7. Playing well

Opening moves (yours, in your numbers):

| Roll | Move | Roll | Move |
|---|---|---|---|
| 2-1 | 13/11 6/5 | 5-1 | 13/8 6/5 |
| 3-1 | 8/5 6/5 | 5-2 | 13/11 13/8 |
| 3-2 | 24/21 13/11 | 5-3 | 8/3 6/3 |
| 4-1 | 24/23 13/9 | 5-4 | 24/20 13/8 |
| 4-2 | 8/4 6/4 | 6-1 | 13/7 8/7 |
| 4-3 | 24/20 13/10 | 6-2 | 24/18 13/11 |
| 6-3 | 24/18 13/10 | 6-4 | 24/14 |
| 6-5 | 24/13 | | |

Later in the game: make points in your home board and in front of Peter's back checkers; avoid leaving blots
within direct reach (1–6 pips) of his checkers unless the gain is worth it; hit when it gains tempo or a key point;
in a race (no more contact), just bring checkers home and bear off efficiently. Explain your reasoning in a sentence
when the move is not obvious — Peter wants to see why.

## 8. When something is off

- `moving` > 0 in `read`: pieces are still settling; read again.
- `loose` checkers: a piece lies outside any point; ask Peter where it belongs, or `tidy` if it is obviously close.
- `conflicts`: both colours on one point — something was knocked over; stop and ask Peter.
- A tool error: report it to Peter in plain words; do not guess the position.
