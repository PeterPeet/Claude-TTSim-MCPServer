-- ttsim_mcp:card_face  Read-only. Where an object's face is: sheet URL and grid cell (cards), whole image, or PDF.
local args = JSON.decode([==[{{args}}]==])
local o = getObjectFromGUID(args.guid)
if o == nil then error("No object with GUID '" .. tostring(args.guid) .. "'", 0) end
local data = o.getData()
local result = { guid = o.getGUID(), name = o.getName(), type = o.type }
if data.CardID ~= nil and data.CustomDeck ~= nil then
  local deck_id = math.floor(data.CardID / 100)
  local deck = data.CustomDeck[deck_id] or data.CustomDeck[tostring(deck_id)]
  if deck == nil then error("Card '" .. args.guid .. "' has no CustomDeck entry " .. deck_id, 0) end
  result.kind = "image"
  result.card_id = data.CardID
  result.url = deck.FaceURL
  result.index = data.CardID % 100
  result.columns = deck.NumWidth
  result.rows = deck.NumHeight
elseif data.CustomPDF ~= nil and data.CustomPDF.PDFUrl ~= nil and data.CustomPDF.PDFUrl ~= "" then
  result.kind = "pdf"
  result.url = data.CustomPDF.PDFUrl
  result.page = data.CustomPDF.PDFPage or 0
elseif data.CustomImage ~= nil and data.CustomImage.ImageURL ~= nil and data.CustomImage.ImageURL ~= "" then
  result.kind = "image"
  result.url = data.CustomImage.ImageURL
  result.index = 0
  result.columns = 1
  result.rows = 1
else
  error("Object '" .. args.guid .. "' (" .. o.type .. ") has no custom face image", 0)
end
return result
