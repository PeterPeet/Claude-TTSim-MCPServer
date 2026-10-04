local __ok, __res = pcall(function() {{code}}
end)
local __payload
if __ok then
  __payload = { ok = true, value = __res }
else
  __payload = { ok = false, error = tostring(__res) }
end
local __enc_ok, __json = pcall(JSON.encode, __payload)
if __enc_ok and __json ~= nil then
  return __json
end
return JSON.encode({ ok = false, error = "result is not JSON-serialisable: " .. tostring(__json) })

-- Wraps caller-supplied Lua so every call answers under its own returnID with a JSON string:
--   {"ok": true, "value": ...}  or  {"ok": false, "error": "..."}
-- TTS sends no reply at all when a script returns a raw Lua table, hence the JSON encoding.
-- {{code}} stays on line 1 so Lua error line numbers match the caller's code.
