-- ttsim_mcp:list_markers  Read-only. Labels drawn by draw_markers and how many of their lines are still there.
local args = JSON.decode([==[{{args}}]==])
local function xyz(p)
  if p.x ~= nil then return p.x, p.y, p.z end
  return p[1], p[2], p[3]
end
local function signature(points)
  local x1, _, z1 = xyz(points[1])
  local xn, _, zn = xyz(points[#points])
  return string.format("%d|%.2f|%.2f|%.2f|%.2f", #points, x1, z1, xn, zn)
end
local lines = Global.getVectorLines() or {}
local present = {}
for _, l in ipairs(lines) do
  local s = signature(l.points)
  present[s] = (present[s] or 0) + 1
end
local markers = {}
for label, entry in pairs(TTSIM_MCP_MARKERS or {}) do
  local found = 0
  for _, s in ipairs(entry) do
    if (present[s] or 0) > 0 then found = found + 1 end
  end
  table.insert(markers, { label = label, lines = #entry, present = found })
end
return { markers = markers, vector_lines = #lines }
