-- ttsim_mcp:clear_markers  Removes the lines drawn by draw_markers under one label (or all labels); other lines stay.
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
local remove = {}
local labels = {}
if args.label ~= nil then
  labels = { args.label }
else
  for label, _ in pairs(TTSIM_MCP_MARKERS) do table.insert(labels, label) end
end
for _, label in ipairs(labels) do
  for _, s in ipairs(TTSIM_MCP_MARKERS[label] or {}) do remove[s] = (remove[s] or 0) + 1 end
  TTSIM_MCP_MARKERS[label] = nil
end
local keep = {}
local removed = 0
for _, l in ipairs(Global.getVectorLines() or {}) do
  local s = signature(l.points)
  if (remove[s] or 0) > 0 then
    remove[s] = remove[s] - 1
    removed = removed + 1
  else
    table.insert(keep, l)
  end
end
Global.setVectorLines(keep)
return { removed = removed, total = #keep }
