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
-- Tilt: angle between straight up and the die axis closest to it (0 = lying flat).
local function tilt(o)
  local best = 0
  for _, axis in ipairs({ o.getTransformUp(), o.getTransformRight(), o.getTransformForward() }) do
    best = math.max(best, math.abs(axis.y))
  end
  return math.deg(math.acos(math.min(1, best)))
end
local dice = {}
for _, o in ipairs(objects) do
  table.insert(dice, {
    guid = o.getGUID(),
    value = o.getValue(),
    resting = o.resting,
    tilt = tilt(o),
    tint = o.getColorTint():toHex(false),
    position = vec(o.getPosition()),
    rotation = vec(o.getRotation()),
  })
end
return { dice = dice }
