-- ttsim_mcp:move_objects  Moves objects to a position or by an offset. All GUIDs are checked before anything moves.
local args = JSON.decode([==[{{args}}]==])
local function v(t) return Vector(t[1], t[2], t[3]) end
local plan = {}
for _, m in ipairs(args.moves) do
  local o = getObjectFromGUID(m.guid)
  if o == nil then error("No object with GUID '" .. tostring(m.guid) .. "'", 0) end
  local pos = nil
  if m.offset ~= nil then
    pos = o.getPosition() + v(m.offset)
  else
    pos = v(m.position)
  end
  table.insert(plan, { obj = o, pos = pos, rot = m.rotation and v(m.rotation) or nil })
end
for _, p in ipairs(plan) do
  if args.smooth then
    p.obj.setPositionSmooth(p.pos, false, false)
    if p.rot then p.obj.setRotationSmooth(p.rot, false, false) end
  else
    p.obj.setPosition(p.pos)
    if p.rot then p.obj.setRotation(p.rot) end
  end
end
return nil
