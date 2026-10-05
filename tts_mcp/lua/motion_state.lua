-- tts_mcp:motion_state  Read-only. Whether objects are still moving, and where they are.
local args = JSON.decode([==[{{args}}]==])
local function vec(v) return { v.x, v.y, v.z } end
local objects = {}
for _, guid in ipairs(args.guids) do
  local o = getObjectFromGUID(guid)
  if o == nil then error("No object with GUID '" .. tostring(guid) .. "'", 0) end
  table.insert(objects, {
    guid = guid,
    moving = o.isSmoothMoving(),
    resting = o.resting,
    position = vec(o.getPosition()),
    rotation = vec(o.getRotation()),
  })
end
return { objects = objects }
