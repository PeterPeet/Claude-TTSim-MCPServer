-- ttsim_mcp:roll_dice  Rolls dice with TTSim's physics roll (lifted and spun, as when a player presses R).
local args = JSON.decode([==[{{args}}]==])
local dice = {}
for _, guid in ipairs(args.guids) do
  local o = getObjectFromGUID(guid)
  if o == nil then error("No object with GUID '" .. tostring(guid) .. "'", 0) end
  if o.type ~= "Dice" then error("Object '" .. guid .. "' is not a die (type " .. tostring(o.type) .. ")", 0) end
  table.insert(dice, o)
end
for _, o in ipairs(dice) do o.roll() end
return nil
