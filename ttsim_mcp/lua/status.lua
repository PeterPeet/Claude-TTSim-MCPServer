-- Read-only: name of the loaded game, object count and seated players.
local players = {}
for _, p in ipairs(Player.getPlayers()) do
  table.insert(players, { color = p.color, host = p.host })
end
return {
  game = Info.name,
  objects = #getAllObjects(),
  players = players,
}
