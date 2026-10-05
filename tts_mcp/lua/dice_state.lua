-- tts_mcp:dice_state  Read-only. Values of the given dice, or of all dice on the table.
local args = JSON.decode([==[{{args}}]==])
local function vec(v) return { v.x, v.y, v.z } end
local objects = {}
if args.guids ~= nil then
  for _, guid in ipairs(args.guids) do
    local o = getObjectFromGUID(guid)
    if o == nil then error("No object with GUID '" .. tostring(guid) .. "'", 0) end
    table.insert(objects, o)
  end
else
  for _, o in ipairs(getAllObjects()) do
    if o.type == "Dice" then table.insert(objects, o) end
  end
end
local dice = {}
for _, o in ipairs(objects) do
  table.insert(dice, {
    guid = o.getGUID(),
    value = o.getValue(),
    resting = o.resting,
    tint = o.getColorTint():toHex(false),
    position = vec(o.getPosition()),
    rotation = vec(o.getRotation()),
  })
end
return { dice = dice }
