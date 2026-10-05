-- ttsim_mcp:highlight  Highlights an object for a few seconds (colour name, e.g. "Yellow").
local args = JSON.decode([==[{{args}}]==])
local o = getObjectFromGUID(args.guid)
if o == nil then error("No object with GUID '" .. tostring(args.guid) .. "'", 0) end
o.highlightOn(Color.fromString(args.color), args.seconds)
return nil
