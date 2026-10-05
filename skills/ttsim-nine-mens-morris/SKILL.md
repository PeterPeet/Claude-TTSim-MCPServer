---
name: ttsim-nine-mens-morris
description: Play Nine Men's Morris (Mühle) against Peter in Tabletop Simulator (TTSim) using the ttsim MCP tools — coin toss, placing, moving, flying, mills and removals on Peter's Workshop table. Use whenever Peter wants to play, continue or reset a game of Nine Men's Morris in TTSim.
---

# Nine Men's Morris in TTSim

You play Nine Men's Morris against Peter on his TTSim table (the Steam Workshop mod "Nine Men's Morris"). You see the
table only through the `ttsim` MCP tools (`ttsim_status`, `run_lua`, `move_objects`, `roll_dice`, `read_dice`,
`highlight`, ...). Peter watches everything happen in TTSim.

## 1. Before the first move of a session

1. `ttsim_status` — TTSim must be reachable and `game` must be `Nine Men's Morris`.
2. Load the helper: read `nmm.lua` (next to this file) and send its whole content with `run_lua`.
   It defines the Lua function `TTSIM_NMM`. If a later call fails with "attempt to call a nil value", the game was
   reloaded: send `nmm.lua` again.
3. `return TTSIM_NMM({ action = "read" })` — read the position (section 3).

## 2. The table

| What | Details |
|---|---|
| Board | the `Board` with 24 snap points, centred at the origin |
| Red tokens (Peter's) | tint `8b3333`, 9 tokens; rack on Peter's side (z = −11.25) |
| Blue tokens (yours) | tint `1f689b`, 9 tokens; rack on the far side (z = +11.25) |
| Coin | type `Coin`, right of the board; faces "Heads" and "Tails" |
| Reset button | object named "Reset Button", left of the board (arrows in a circle) |

Removed tokens are put on the table behind their owner's rack (z = ±13.5).

**Notation.** The 24 points use the standard 7 × 7 grid: columns a–g from Peter's left to right, rows 1–7 from Peter's
side to yours. The outer square is a1 d1 g1 g4 g7 d7 a7 a4, the middle square b2 d2 f2 f4 f6 d6 b6 b4, the inner square
c3 d3 e3 e4 e5 d5 c5 c4. Moves: `d6` (place), `d6-d5` (move), `d6-d5, removes b4` (with removal).

```
7  o-----------o-----------o      o = point. Lines are the connections;
   |           |           |      every straight line of three points
6  |   o-------o-------o   |      is a mill (16 in total).
   |   |       |       |   |
5  |   |   o---o---o   |   |
   |   |   |       |   |   |
4  o---o---o       o---o---o
   |   |   |       |   |   |
3  |   |   o---o---o   |   |
   |   |       |       |   |
2  |   o-------o-------o   |
   |           |           |
1  o-----------o-----------o      ← Peter's side (red rack)
   a   b   c   d   e   f   g
```

## 3. The helper `TTSIM_NMM`

Call it with `run_lua`, e.g. `return TTSIM_NMM({ action = "read" })`.

| Action | Moves anything? | Returns |
|---|---|---|
| `read` | no | `diagram` (the board with `R`/`B`/`.`), and per colour: `points` occupied, `on_board`, `in_hand`, `removed`, `phase` (placing / moving / flying), current `mills`, `legal_moves`. Also `loose` tokens it cannot place and `moving` (read again if > 0). |
| `plan` with `color` and `place = "d6"` or `move = { "d6", "d5" }`, optional `remove = "b4"` | no | `notation`, `mill`, `moves` for `move_objects`, the resulting `diagram`, and `wins` if the move wins. Refuses: placing with an empty hand, moving while tokens are in hand, occupied targets, non-adjacent moves (unless flying), a mill without a removal, a removal without a mill, removing from a mill while other tokens are free. |
| `reset` | yes | Calls the mod's own reset: all 18 tokens glide back to their racks. Only with Peter's consent. |

To carry out a `plan`, pass its `moves` to `move_objects`, then `read` and check the result.

Show Peter the `diagram` in a code block when it helps (e.g. at the start, after mills, when the position is tense).

## 4. A game, step by step

**New game.** `read`. If tokens are on the board and Peter wants a new game, ask him; on yes, `reset`, then `read`
until `moving` is 0 and both colours have 9 in hand.

**Coin toss.** Ask Peter to call heads or tails. Flip the coin with `roll_dice` (its GUID from
`list_objects` with type `Coin`) and report the face. Whoever wins the toss places first. (If the `roll_dice` tool
reports a type error for the coin, the MCP server is outdated: flip with `run_lua` —
`getObjectFromGUID(guid).randomize()` — and read `getRotationValue()` once `resting` is true.)

**Your turn.**
1. `read` and look at the diagram.
2. Choose a move (sections 5 and 6). If it closes a mill, also choose which of Peter's tokens to remove.
3. `plan` it, then `move_objects` with the returned moves, then `read` to confirm.
4. Tell Peter the move in notation, e.g. "I place on d6." / "d6-d5, closing a mill — I remove your token on b4."
5. Hand over: "Your turn."

**Peter's turn.**
1. Wait until Peter says he has moved. Do not touch his tokens before that.
2. `read`. Work out his move by comparing with the position after your last move: a new red token (placing), a red
   token that changed points (moving/flying), and a blue token that left the board (removal).
3. Check it against the rules. If something looks illegal, say exactly why — Peter decides.
4. If Peter removed one of your tokens but left it somewhere odd, that is fine: a blue token off the board and off the
   rack counts as removed.

**End.** A player loses when reduced to two tokens or when they cannot move on their turn. Announce it, and offer
a new game (with `reset`).

## 5. Rules

- **Placing:** players alternate placing one token from hand on any free point until all 18 are placed.
- **Moving:** then players alternate moving one token along a line to an adjacent free point.
- **Flying:** a player with exactly three tokens left (and none in hand) may move a token to any free point.
- **Mills:** forming three in a row along a line (by placing or moving) lets that player remove one opposing token
  from the board. A token in a mill may only be removed if all of the opponent's tokens are in mills. Removed tokens
  never return. Opening a mill and closing it again on a later turn forms a new mill.
- **Winning:** the opponent is reduced to two tokens, or cannot make a legal move.

## 6. Playing well

- Placing phase: mobility beats early mills. The four points with four neighbours (d2, b4, f4, d6) are the
  strongest; corners have only two neighbours. Do not rush to complete a mill if Peter can simply block it.
- Always block a point where Peter would complete a mill on his next turn, unless you close your own mill first.
- Look for a "double attack": one placement that threatens two different mills at once.
- Keep your tokens able to move; a player who gets locked in loses. Count `legal_moves` for both sides.
- Moving phase: a mill you can open and close again repeatedly (a "running mill", ideally with a blocking token
  next to it) wins material every second turn.
- When removing: take tokens that are about to form a mill, or that keep Peter mobile; otherwise a token whose
  removal frees your own position.
- Explain your reasoning in a sentence when the move is not obvious — Peter wants to see why.

## 7. When something is off

- `moving` > 0: tokens are still settling; read again.
- `loose` tokens: a token lies between points; ask Peter where it belongs.
- A tool error: report it in plain words; do not guess the position.
