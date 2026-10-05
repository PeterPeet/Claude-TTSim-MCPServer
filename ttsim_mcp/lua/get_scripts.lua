-- Read-only: collects the Global script/UI and every object script/UI that is not empty.
local objects = {}
for _, obj in ipairs(getAllObjects()) do
  local script = obj.getLuaScript() or ""
  local ui = obj.UI.getXml() or ""
  if script ~= "" or ui ~= "" then
    table.insert(objects, {
      guid = obj.getGUID(),
      name = obj.getName(),
      type = obj.type,
      script = script,
      ui = ui,
    })
  end
end
return {
  global = { script = Global.getLuaScript() or "", ui = Global.UI.getXml() or "" },
  objects = objects,
}
