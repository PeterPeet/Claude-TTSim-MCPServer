-- ttsim_mcp:draw_markers  Adds labelled marker lines to the vector lines; existing lines (player drawings) stay.
-- The label registry TTSIM_MCP_MARKERS lives in the Global environment until the game is reloaded.
local args = JSON.decode([==[{{args}}]==])
TTSIM_MCP_MARKERS = TTSIM_MCP_MARKERS or {}
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
local entry = TTSIM_MCP_MARKERS[args.label] or {}
for _, m in ipairs(args.lines) do
  local color = m.color
  if type(color) == "string" then color = Color.fromString(color) end
  local points = {}
  for _, p in ipairs(m.points) do table.insert(points, Vector(p[1], p[2], p[3])) end
  table.insert(lines, { points = points, color = color, thickness = m.thickness })
  table.insert(entry, signature(m.points))
end
TTSIM_MCP_MARKERS[args.label] = entry
Global.setVectorLines(lines)
return { label = args.label, added = #args.lines, total = #lines }
