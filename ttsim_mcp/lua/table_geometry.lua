-- ttsim_mcp:table_geometry  Read-only. Table type and bounds, plus global snap points.
local function vec(v) return { v.x, v.y, v.z } end
local result = { table = { type = Tables.getTable() }, snap_points = {} }
local t = Tables.getTableObject()
if t ~= nil then
  local b = t.getBounds()
  result.table.center = vec(b.center)
  result.table.size = vec(b.size)
end
for _, s in ipairs(Global.getSnapPoints()) do
  table.insert(result.snap_points, { position = vec(s.position), rotation = vec(s.rotation), tags = s.tags })
end
return result
