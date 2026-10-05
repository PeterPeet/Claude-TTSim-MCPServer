-- ttsim-nine-mens-morris helper. Send this whole file once per session with the run_lua tool; it defines the global
-- function TTSIM_NMM and returns its version. Afterwards call, e.g.:
--   return TTSIM_NMM({ action = "read" })
--   return TTSIM_NMM({ action = "plan", color = "blue", place = "d6" })
--   return TTSIM_NMM({ action = "plan", color = "blue", move = { "d6", "d5" }, remove = "b4" })
--   return TTSIM_NMM({ action = "reset" })
-- "plan" moves nothing: pass the returned `moves` to the move_objects tool.
-- "reset" calls the mod's own reset function (all tokens glide back to the racks); read again until moving = 0.
-- If a call fails with "attempt to call a nil value", the game was reloaded: send this file again.

TTSIM_NMM_VERSION = 1

function TTSIM_NMM(request)
  local TINTS = { ["8b3333"] = "red", ["1f689b"] = "blue" }
  local STEP = 2.09 -- grid step of the 7 x 7 notation grid (world units)
  local REMOVED_Z = { red = -13.5, blue = 13.5 } -- removed tokens lie on the table behind their owner's rack
  local TABLE_Y = 1.5 -- table surface there
  local TOKEN_HALF = 0.095
  local DROP = 0.12

  local MILLS = {
    { "a7", "d7", "g7" }, { "b6", "d6", "f6" }, { "c5", "d5", "e5" }, { "a4", "b4", "c4" },
    { "e4", "f4", "g4" }, { "c3", "d3", "e3" }, { "b2", "d2", "f2" }, { "a1", "d1", "g1" },
    { "a1", "a4", "a7" }, { "b2", "b4", "b6" }, { "c3", "c4", "c5" }, { "d1", "d2", "d3" },
    { "d5", "d6", "d7" }, { "e3", "e4", "e5" }, { "f2", "f4", "f6" }, { "g1", "g4", "g7" },
  }
  -- Two points are adjacent when they are neighbours on one of the 16 lines.
  local ADJ = {}
  for _, m in ipairs(MILLS) do
    for i = 1, 2 do
      ADJ[m[i]] = ADJ[m[i]] or {}
      ADJ[m[i + 1]] = ADJ[m[i + 1]] or {}
      ADJ[m[i]][m[i + 1]] = true
      ADJ[m[i + 1]][m[i]] = true
    end
  end

  -- The main board is the only Board with 24 snap points.
  local board = nil
  local reset_button = nil
  for _, o in ipairs(getAllObjects()) do
    if o.type == "Board" and #o.getSnapPoints() == 24 then board = o end
    if o.getName() == "Reset Button" then reset_button = o end
  end
  if board == nil then error("No Nine Men's Morris board (a Board with 24 snap points) on the table", 0) end

  -- points[name] = world position of the snap point; names from the grid: column a-g by x, row 1-7 by z.
  local points = {}
  local names = {}
  for _, s in ipairs(board.getSnapPoints()) do
    local p = board.positionToWorld(s.position)
    local col = math.floor((p.x - board.getPosition().x) / STEP + 0.5) + 4
    local row = math.floor((p.z - board.getPosition().z) / STEP + 0.5) + 4
    local name = string.sub("abcdefg", col, col) .. row
    points[name] = p
    table.insert(names, name)
  end
  for _, m in ipairs(MILLS) do
    for _, n in ipairs(m) do
      if points[n] == nil then error("Board point " .. n .. " not found among the snap points", 0) end
    end
  end
  table.sort(names)

  local function opponent(color)
    if color == "red" then return "blue" end
    return "red"
  end

  -- Classify every token: on a point, in hand (on its rack), or removed (anywhere else).
  local at = {} -- at[point] = { color, obj }
  local hand = { red = {}, blue = {} }
  local removed = { red = {}, blue = {} }
  local loose = {}
  local moving = 0
  for _, o in ipairs(getAllObjects()) do
    local color = TINTS[o.getColorTint():toHex(false)]
    if color ~= nil and o.type ~= "Board" then
      local p = o.getPosition()
      if o.isSmoothMoving() or not o.resting then moving = moving + 1 end
      local placed = false
      if math.abs(p.x) < 7.5 and math.abs(p.z) < 7.5 then
        for name, q in pairs(points) do
          if not placed and math.abs(p.x - q.x) < 0.7 and math.abs(p.z - q.z) < 0.7 then
            if at[name] ~= nil then
              table.insert(loose, { color = color, guid = o.getGUID(), note = "second token on " .. name })
            else
              at[name] = { color = color, obj = o }
            end
            placed = true
          end
        end
        if not placed then
          table.insert(loose, { color = color, guid = o.getGUID(), position = { p.x, p.y, p.z } })
          placed = true
        end
      end
      if not placed then
        if math.abs(p.x) < 9.5 and math.abs(math.abs(p.z) - 11.25) < 1.2 and p.y > 1.9 then
          table.insert(hand[color], o)
        else
          table.insert(removed[color], o)
        end
      end
    end
  end
  for _, color in ipairs({ "red", "blue" }) do
    table.sort(hand[color], function(a, b) return a.getPosition().x < b.getPosition().x end)
  end

  local function owner(state, name)
    local t = state[name]
    return t and t.color or nil
  end
  local function in_mill(state, name)
    local c = owner(state, name)
    if c == nil then return false end
    for _, m in ipairs(MILLS) do
      if (m[1] == name or m[2] == name or m[3] == name)
        and owner(state, m[1]) == c and owner(state, m[2]) == c and owner(state, m[3]) == c then
        return true
      end
    end
    return false
  end
  local function on_board(state, color)
    local list = {}
    for _, n in ipairs(names) do
      if owner(state, n) == color then table.insert(list, n) end
    end
    return list
  end
  local function phase(state, color, in_hand)
    if in_hand > 0 then return "placing" end
    if #on_board(state, color) == 3 then return "flying" end
    return "moving"
  end
  -- Number of legal moves (placing: free points; moving: adjacent free points; flying: any free point).
  local function mobility(state, color, in_hand)
    local free = 0
    for _, n in ipairs(names) do
      if state[n] == nil then free = free + 1 end
    end
    local ph = phase(state, color, in_hand)
    if ph ~= "moving" then return free end
    local count = 0
    for _, n in ipairs(on_board(state, color)) do
      for m in pairs(ADJ[n]) do
        if state[m] == nil then count = count + 1 end
      end
    end
    return count
  end

  local function diagram(state)
    local lines = {
      "7  o-----------o-----------o",
      "   |           |           |",
      "6  |   o-------o-------o   |",
      "   |   |       |       |   |",
      "5  |   |   o---o---o   |   |",
      "   |   |   |       |   |   |",
      "4  o---o---o       o---o---o",
      "   |   |   |       |   |   |",
      "3  |   |   o---o---o   |   |",
      "   |   |       |       |   |",
      "2  |   o-------o-------o   |",
      "   |           |           |",
      "1  o-----------o-----------o",
      "   a   b   c   d   e   f   g",
    }
    for _, n in ipairs(names) do
      local col = string.byte(n, 1) - string.byte("a")
      local row = tonumber(string.sub(n, 2))
      local li = (7 - row) * 2 + 1
      local ci = 4 + col * 4
      local mark = "."
      if owner(state, n) == "red" then mark = "R" elseif owner(state, n) == "blue" then mark = "B" end
      lines[li] = string.sub(lines[li], 1, ci - 1) .. mark .. string.sub(lines[li], ci + 1)
    end
    return table.concat(lines, "\n")
  end

  local function read()
    local result = { diagram = diagram(at), loose = loose, moving = moving }
    for _, color in ipairs({ "red", "blue" }) do
      local mills = {}
      for _, m in ipairs(MILLS) do
        if owner(at, m[1]) == color and owner(at, m[2]) == color and owner(at, m[3]) == color then
          table.insert(mills, table.concat(m, "-"))
        end
      end
      result[color] = {
        points = table.concat(on_board(at, color), " "),
        on_board = #on_board(at, color),
        in_hand = #hand[color],
        removed = #removed[color],
        phase = phase(at, color, #hand[color]),
        mills = mills,
        legal_moves = mobility(at, color, #hand[color]),
      }
    end
    return result
  end

  local function removed_slot(color, k)
    return { -6.7 + (k - 1) * 1.67, TABLE_Y + TOKEN_HALF + DROP, REMOVED_Z[color] }
  end
  local function point_slot(name)
    local p = points[name]
    return { p.x, p.y + TOKEN_HALF + DROP, p.z }
  end

  local function plan(color, place, move, remove)
    if color ~= "red" and color ~= "blue" then error("color must be 'red' or 'blue'", 0) end
    local opp = opponent(color)
    local state = {}
    for n, t in pairs(at) do state[n] = t end
    local in_hand = #hand[color]
    local out, notation = {}, ""
    local token, target = nil, nil
    if place ~= nil then
      if in_hand == 0 then error(color .. " has no tokens left in hand: move instead of placing", 0) end
      if points[place] == nil then error("No point '" .. tostring(place) .. "'", 0) end
      if state[place] ~= nil then error("Point " .. place .. " is occupied", 0) end
      token = hand[color][in_hand]
      target = place
      notation = place
    elseif move ~= nil then
      local from, to = move[1], move[2]
      if in_hand > 0 then error(color .. " still has " .. in_hand .. " tokens in hand: place instead of moving", 0) end
      if points[from] == nil or points[to] == nil then error("Unknown point in move " .. tostring(from) .. "-" .. tostring(to), 0) end
      if owner(state, from) ~= color then error("No " .. color .. " token on " .. from, 0) end
      if state[to] ~= nil then error("Point " .. to .. " is occupied", 0) end
      local flying = phase(state, color, in_hand) == "flying"
      if not flying and not ADJ[from][to] then error(from .. " and " .. to .. " are not adjacent (" .. color .. " cannot fly yet)", 0) end
      token = state[from].obj
      state[from] = nil
      target = to
      notation = from .. "-" .. to
    else
      error("plan needs `place` or `move`", 0)
    end
    state[target] = { color = color, obj = token }
    table.insert(out, { guid = token.getGUID(), position = point_slot(target) })
    local mill = in_mill(state, target)
    if mill and remove == nil then
      error(notation .. " closes a mill: add remove = \"<point>\" with one of " .. opp .. "'s tokens", 0)
    end
    if remove ~= nil then
      if not mill then error(notation .. " does not close a mill, so nothing may be removed", 0) end
      if owner(state, remove) ~= opp then error("No " .. opp .. " token on " .. tostring(remove), 0) end
      if in_mill(state, remove) then
        for _, n in ipairs(on_board(state, opp)) do
          if not in_mill(state, n) then
            error(remove .. " is part of a mill; remove a token outside mills (e.g. " .. n .. ")", 0)
          end
        end
      end
      local victim = state[remove].obj
      state[remove] = nil
      table.insert(out, { guid = victim.getGUID(), position = removed_slot(opp, #removed[opp] + 1) })
      notation = notation .. ", removes " .. remove
    end
    local opp_hand = #hand[opp]
    local opp_left = #on_board(state, opp) + opp_hand
    local result = { color = color, notation = notation, mill = mill, moves = out, diagram = diagram(state) }
    if opp_left < 3 then
      result.wins = color .. " wins: " .. opp .. " has only " .. opp_left .. " tokens left"
    elseif opp_hand == 0 and mobility(state, opp, 0) == 0 then
      result.wins = color .. " wins: " .. opp .. " cannot move"
    end
    return result
  end

  local function reset()
    if reset_button == nil then error("No object named 'Reset Button' on the table", 0) end
    reset_button.call("resetPieces")
    return { reset = true, note = "tokens are gliding back to the racks; read again until moving = 0" }
  end

  request = request or {}
  if request.action == "read" then return read() end
  if request.action == "plan" then return plan(request.color, request.place, request.move, request.remove) end
  if request.action == "reset" then return reset() end
  error("Unknown action '" .. tostring(request.action) .. "' (read, plan, reset)", 0)
end

return { loaded = "TTSIM_NMM", version = TTSIM_NMM_VERSION }
