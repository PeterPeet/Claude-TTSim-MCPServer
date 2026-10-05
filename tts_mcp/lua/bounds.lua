-- tts_mcp:bounds  Read-only. Position and world-axis bounding box of objects.
local args = JSON.decode([==[{{args}}]==])
local function vec(v) return { v.x, v.y, v.z } end
local objects = {}
for _, guid in ipairs(args.guids) do
  local o = getObjectFromGUID(guid)
  if o == nil then error("No object with GUID '" .. tostring(guid) .. "'", 0) end
  local b = o.getBounds()
  table.insert(objects, { guid = guid, position = vec(o.getPosition()), center = vec(b.center), size = vec(b.size) })
end
return { objects = objects }
