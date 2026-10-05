-- ttsim_mcp:roll_dice  Rolls dice with TTSim's physics roll (lifted and spun, as when a player presses R).
-- Coins and other objects with named faces are randomized instead, which also runs their own script (e.g. a coin flip).
local args = JSON.decode([==[{{args}}]==])
local objects = {}
for _, guid in ipairs(args.guids) do
  local o = getObjectFromGUID(guid)
  if o == nil then error("No object with GUID '" .. tostring(guid) .. "'", 0) end
  if o.type ~= "Dice" and #o.getRotationValues() == 0 then
    error("Object '" .. guid .. "' is not a die or coin: it has no faces (type " .. tostring(o.type) .. ")", 0)
  end
  table.insert(objects, o)
end
for _, o in ipairs(objects) do
  if o.type == "Dice" then o.roll() else o.randomize() end
end
return nil
