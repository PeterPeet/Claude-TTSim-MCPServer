-- ttsim_mcp:list_objects  Read-only. Filters (all optional): name (substring, case-insensitive), type, tag, tint (hex).
local args = JSON.decode([==[{{args}}]==])
local function vec(v) return { v.x, v.y, v.z } end
local objects = {}
for _, o in ipairs(getAllObjects()) do
  local tint = o.getColorTint():toHex(false)
  local keep = (args.type == nil or o.type == args.type)
    and (args.tint == nil or tint == args.tint)
    and (args.tag == nil or o.hasTag(args.tag))
    and (args.name == nil or string.find(string.lower(o.getName()), string.lower(args.name), 1, true) ~= nil)
  if keep then
    table.insert(objects, {
      guid = o.getGUID(),
      name = o.getName(),
      description = o.getDescription(),
      type = o.type,
      tags = o.getTags(),
      tint = tint,
      position = vec(o.getPosition()),
      rotation = vec(o.getRotation()),
      locked = o.getLock(),
      resting = o.resting,
    })
  end
end
return { objects = objects }
