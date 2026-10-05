-- ttsim-backgammon helper. Send this whole file once per session with the run_lua tool; it defines the global
-- function TTSIM_BG and returns its version. Afterwards call, e.g.:
--   return TTSIM_BG({ action = "read" })
--   return TTSIM_BG({ action = "plan", color = "light", moves = { { 24, 18 }, { 13, 11 } } })
--   return TTSIM_BG({ action = "tidy" })
--   return TTSIM_BG({ action = "setup" })
-- Point numbers in "plan" are the mover's own (1-24); 25 = the bar, 0 = borne off.
-- "plan", "tidy" and "setup" move nothing: pass the returned `moves` to the move_objects tool.
-- If a call fails with "attempt to call a nil value", the game was reloaded: send this file again.

TTSIM_BG_VERSION = 1

function TTSIM_BG(request)
  local LIGHT_TINT, BROWN_TINT = "bbbbbb", "4e2c00"
  local CHECKER_TYPE = "Backgammon Piece"
  -- Board geometry, measured by casting rays onto the board (see docs/requirements.md, Q4):
  local SURFACE_Y = 1.14 -- playing surface and bear-off trays
  local BAR_TOP_Y = 2.22 -- top of the raised bar (z between -0.7 and 0.7)
  local TRAY_Z = -10.2 -- bear-off tray at the end next to both home boards (z -10.9 .. -9.5)
  local HALF_HEIGHT = 0.115 -- half a checker's height
  local LAYER = 0.24 -- one checker layer when stacking
  local DROP = 0.12 -- checkers are placed this far above their resting height and settle by physics

  local board = nil
  for _, o in ipairs(getAllObjects()) do
    if o.type == "Board" then board = o end
  end
  if board == nil then error("No backgammon board on the table", 0) end

  -- rows[side][i]: side -1 = left (x < 0), 1 = right; i = 1 is the row at the most negative z.
  -- Each row has .z and .slots (world positions, edge of the board first).
  local rows = { [-1] = {}, [1] = {} }
  do
    local snaps = { [-1] = {}, [1] = {} }
    for _, s in ipairs(board.getSnapPoints()) do
      local p = board.positionToWorld(s.position)
      table.insert(snaps[p.x < 0 and -1 or 1], p)
    end
    for _, side in ipairs({ -1, 1 }) do
      local list = snaps[side]
      table.sort(list, function(a, b) return a.z < b.z end)
      local row = nil
      for _, p in ipairs(list) do
        if row == nil or p.z - row.last > 0.5 then
          row = { slots = {}, zsum = 0 }
          table.insert(rows[side], row)
        end
        table.insert(row.slots, p)
        row.zsum = row.zsum + p.z
        row.last = p.z
      end
      for _, r in ipairs(rows[side]) do
        r.z = r.zsum / #r.slots
        table.sort(r.slots, function(a, b) return math.abs(a.x) > math.abs(b.x) end)
      end
      if #rows[side] ~= 12 then error("Expected 12 rows of snap points per side, found " .. #rows[side], 0) end
    end
  end

  -- Light's numbering: 1-12 on the left (1 = corner at z < 0, 6 = next to the bar, 12 = corner at z > 0),
  -- 13-24 on the right (13 = corner at z > 0, 19 = next to the bar, 24 = corner at z < 0).
  -- Brown's own number for a point is 25 - light's number.
  local function point_row(n)
    if n <= 12 then return rows[-1][n] end
    return rows[1][25 - n]
  end
  local function to_light(color, n)
    if color == "light" then return n end
    return 25 - n
  end
  local function opponent(color)
    if color == "light" then return "brown" end
    return "light"
  end
  local function side_of(color)
    if color == "light" then return -1 end
    return 1
  end

  local function classify(p)
    if math.abs(p.x) > 7.1 or math.abs(p.z) > 11.45 then return "loose" end
    if math.abs(p.z) > 9.35 then return "off" end
    if math.abs(p.z) < 0.75 and p.y > 2.0 then return "bar" end
    local side = p.x < 0 and -1 or 1
    for i, r in ipairs(rows[side]) do
      if math.abs(p.z - r.z) < 0.73 then
        if side < 0 then return i end
        return 25 - i
      end
    end
    return "loose"
  end

  -- Target positions for the k-th checker (1-based) of a stack.
  local function point_slot(n, k)
    local base = point_row(n).slots[(k - 1) % 5 + 1]
    local layer = math.floor((k - 1) / 5)
    return { base.x, SURFACE_Y + HALF_HEIGHT + DROP + layer * LAYER, base.z }
  end
  local function bar_slot(color, k)
    local layer = math.floor((k - 1) / 6)
    return { side_of(color) * (0.5 + (k - 1) % 6), BAR_TOP_Y + HALF_HEIGHT + DROP + layer * LAYER, 0 }
  end
  local function off_slot(color, k)
    local layer = math.floor((k - 1) / 7)
    return { side_of(color) * (0.5 + (k - 1) % 7), SURFACE_Y + HALF_HEIGHT + DROP + layer * LAYER, TRAY_Z }
  end
  local function slot(color, key, k)
    if key == "bar" then return bar_slot(color, k) end
    if key == "off" then return off_slot(color, k) end
    return point_slot(key, k)
  end

  -- Stack order: lowest layer first, then from the board edge inwards (bar/tray: from the centre outwards).
  -- The last checker in a list is the one to pick up next.
  local function stack_order(list, key)
    table.sort(list, function(a, b)
      local pa, pb = a.getPosition(), b.getPosition()
      if math.abs(pa.y - pb.y) > LAYER / 2 then return pa.y < pb.y end
      if key == "bar" or key == "off" then return math.abs(pa.x) < math.abs(pb.x) end
      return math.abs(pa.x) > math.abs(pb.x)
    end)
    return list
  end

  local function color_of(o)
    local tint = o.getColorTint():toHex(false)
    if tint == LIGHT_TINT then return "light" end
    if tint == BROWN_TINT then return "brown" end
    return nil
  end

  -- state[color][key] = list of checkers; key = 1..24 (light's numbering), "bar", "off" or "loose".
  local state = { light = {}, brown = {} }
  local moving = 0
  for _, o in ipairs(getAllObjects()) do
    if o.type == CHECKER_TYPE then
      local color = color_of(o)
      if color ~= nil then
        local key = classify(o.getPosition())
        state[color][key] = state[color][key] or {}
        table.insert(state[color][key], o)
        if o.isSmoothMoving() or not o.resting then moving = moving + 1 end
      end
    end
  end
  for _, color in ipairs({ "light", "brown" }) do
    for key, list in pairs(state[color]) do stack_order(list, key) end
  end
  local function count(color, key)
    local list = state[color][key]
    return list and #list or 0
  end

  local function read()
    local points, conflicts = {}, {}
    local pip = { light = 25 * count("light", "bar"), brown = 25 * count("brown", "bar") }
    local own = { light = {}, brown = {} }
    for n = 1, 24 do
      local l, b = count("light", n), count("brown", n)
      if l > 0 or b > 0 then
        table.insert(points, { point = n, light = l, brown = b })
      end
      if l > 0 and b > 0 then table.insert(conflicts, n) end
      pip.light = pip.light + l * n
      pip.brown = pip.brown + b * (25 - n)
    end
    for n = 24, 1, -1 do
      if count("light", n) > 0 then table.insert(own.light, n .. ":" .. count("light", n)) end
      if count("brown", 25 - n) > 0 then table.insert(own.brown, n .. ":" .. count("brown", 25 - n)) end
    end
    local loose = {}
    for _, color in ipairs({ "light", "brown" }) do
      for _, o in ipairs(state[color].loose or {}) do
        local p = o.getPosition()
        table.insert(loose, { color = color, guid = o.getGUID(), position = { p.x, p.y, p.z } })
      end
    end
    return {
      numbering = "points[].point is light's number; brown's own number is 25 - point",
      light = "point:count in light's numbers, " .. (#own.light > 0 and table.concat(own.light, " ") or "-"),
      brown = "point:count in brown's numbers, " .. (#own.brown > 0 and table.concat(own.brown, " ") or "-"),
      points = points,
      bar = { light = count("light", "bar"), brown = count("brown", "bar") },
      off = { light = count("light", "off"), brown = count("brown", "off") },
      pip = pip,
      loose = loose,
      conflicts = conflicts,
      moving = moving,
    }
  end

  local function plan(color, moves)
    if color ~= "light" and color ~= "brown" then error("color must be 'light' or 'brown'", 0) end
    local opp = opponent(color)
    -- Work on a copy, so several moves (also of the same checker) build on each other.
    local v = { light = {}, brown = {} }
    for _, c in ipairs({ "light", "brown" }) do
      for key, list in pairs(state[c]) do
        v[c][key] = {}
        for i, o in ipairs(list) do v[c][key][i] = o end
      end
    end
    local function list_of(c, key)
      v[c][key] = v[c][key] or {}
      return v[c][key]
    end
    local function all_home()
      for key, list in pairs(v[color]) do
        if #list > 0 and key ~= "off" then
          if key == "bar" or key == "loose" then return false end
          local own_number = color == "light" and key or 25 - key
          if own_number > 6 then return false end
        end
      end
      return true
    end
    local targets, order, notation, hits = {}, {}, {}, 0
    local function place(o, position)
      local guid = o.getGUID()
      if targets[guid] == nil then table.insert(order, guid) end
      targets[guid] = position
    end
    for _, m in ipairs(moves) do
      local from, to = m[1], m[2]
      local src = from == 25 and "bar" or to_light(color, from)
      local src_list = list_of(color, src)
      if #src_list == 0 then
        error("No " .. color .. " checker on " .. (from == 25 and "the bar" or "point " .. from), 0)
      end
      if from ~= 25 and #list_of(color, "bar") > 0 then
        error(color .. " has a checker on the bar and must enter it first", 0)
      end
      local dest, hit = "off", false
      if to == 0 then
        if not all_home() then error(color .. " cannot bear off: not all checkers are in the home board", 0) end
      else
        dest = to_light(color, to)
        local blockers = list_of(opp, dest)
        if #blockers >= 2 then error("Point " .. to .. " is blocked by " .. #blockers .. " " .. opp .. " checkers", 0) end
        if #blockers == 1 then
          local blot = table.remove(blockers)
          local bar = list_of(opp, "bar")
          table.insert(bar, blot)
          place(blot, bar_slot(opp, #bar))
          hit = true
          hits = hits + 1
        end
      end
      local checker = table.remove(src_list)
      local dest_list = list_of(color, dest)
      table.insert(dest_list, checker)
      place(checker, slot(color, dest, #dest_list))
      table.insert(notation, (from == 25 and "bar" or from) .. "/" .. (to == 0 and "off" or to) .. (hit and "*" or ""))
    end
    local out = {}
    for _, guid in ipairs(order) do table.insert(out, { guid = guid, position = targets[guid] }) end
    return { color = color, notation = table.concat(notation, " "), hits = hits, moves = out }
  end

  local function tidy()
    local out = {}
    for _, color in ipairs({ "light", "brown" }) do
      for key, list in pairs(state[color]) do
        if key ~= "loose" then
          for k, o in ipairs(list) do
            local target = slot(color, key, k)
            local p = o.getPosition()
            if math.abs(p.x - target[1]) > 0.15 or math.abs(p.z - target[3]) > 0.15 or math.abs(p.y - target[2]) > LAYER then
              table.insert(out, { guid = o.getGUID(), position = target })
            end
          end
        end
      end
    end
    return { moves = out }
  end

  -- Standard starting position, in each player's own numbering: 2 on 24, 5 on 13, 3 on 8, 5 on 6.
  local function setup()
    local out = {}
    local start = { 24, 24, 13, 13, 13, 13, 13, 8, 8, 8, 6, 6, 6, 6, 6 }
    for _, color in ipairs({ "light", "brown" }) do
      local pool = {}
      for _, list in pairs(state[color]) do
        for _, o in ipairs(list) do table.insert(pool, o) end
      end
      if #pool ~= 15 then error("Expected 15 " .. color .. " checkers, found " .. #pool, 0) end
      local filled = {}
      for i, own in ipairs(start) do
        local n = to_light(color, own)
        filled[n] = (filled[n] or 0) + 1
        table.insert(out, { guid = pool[i].getGUID(), position = point_slot(n, filled[n]) })
      end
    end
    return { moves = out }
  end

  request = request or {}
  if request.action == "read" then return read() end
  if request.action == "plan" then return plan(request.color, request.moves or {}) end
  if request.action == "tidy" then return tidy() end
  if request.action == "setup" then return setup() end
  error("Unknown action '" .. tostring(request.action) .. "' (read, plan, tidy, setup)", 0)
end

return { loaded = "TTSIM_BG", version = TTSIM_BG_VERSION }
