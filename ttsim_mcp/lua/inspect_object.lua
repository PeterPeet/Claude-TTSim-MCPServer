-- ttsim_mcp:inspect_object  Read-only. Full details of one object; snap point positions in world coordinates.
local args = JSON.decode([==[{{args}}]==])
local function vec(v) return { v.x, v.y, v.z } end
local o = getObjectFromGUID(args.guid)
if o == nil then error("No object with GUID '" .. tostring(args.guid) .. "'", 0) end
local b = o.getBounds()
local snaps = {}
for _, s in ipairs(o.getSnapPoints()) do
  table.insert(snaps, {
    position = vec(o.positionToWorld(s.position)),
    rotation = vec(s.rotation),
    rotation_snap = s.rotation_snap,
    tags = s.tags,
  })
end
local value_ok, value = pcall(function() return o.getValue() end)
return {
  guid = o.getGUID(),
  name = o.getName(),
  description = o.getDescription(),
  type = o.type,
  tags = o.getTags(),
  tint = o.getColorTint():toHex(false),
  position = vec(o.getPosition()),
  rotation = vec(o.getRotation()),
  scale = vec(o.getScale()),
  bounds = { center = vec(b.center), size = vec(b.size) },
  locked = o.getLock(),
  resting = o.resting,
  smooth_moving = o.isSmoothMoving(),
  held_by = o.held_by_color,
  value = value_ok and value or nil,
  snap_points = snaps,
}
