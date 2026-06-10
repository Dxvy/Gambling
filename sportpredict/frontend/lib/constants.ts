export const sportsList = [
  { id: "football", icon: "⚽", label: "Football", apiId: 1 },
  { id: "basketball", icon: "🏀", label: "Basketball", apiId: 2 },
  { id: "tennis", icon: "🎾", label: "Tennis", apiId: 3 },
  { id: "hockey", icon: "🏒", label: "Hockey", apiId: 4 },
  { id: "rugby", icon: "🏉", label: "Rugby", apiId: 5 },
  { id: "baseball", icon: "⚾", label: "Baseball", apiId: 6 },
];

// Replace numeric IDs with football-data.org competition codes
export const leaguesByCountry = {
  "France":    [{ id: "FL1",  name: "Ligue 1" }],
  "England":   [{ id: "PL",   name: "Premier League" }],
  "Spain":     [{ id: "PD",   name: "La Liga" }],
  "Germany":   [{ id: "BL1",  name: "Bundesliga" }],
  "Italy":     [{ id: "SA",   name: "Serie A" }],
  "Champions": [{ id: "CL",   name: "Champions League" }],
};