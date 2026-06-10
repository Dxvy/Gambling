const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function fetchFixtures(leagueId: number, season = 2024) {
  const res = await fetch(
    `${BASE}/api/sports/fixtures?league_id=${leagueId}&season=${season}`
  );
  if (!res.ok) throw new Error("Failed to fetch fixtures");
  return res.json();
}

export async function predictMatch(
  homeId: number,
  awayId: number,
  leagueId: number
) {
  const res = await fetch(
    `${BASE}/api/sports/predict?home_id=${homeId}&away_id=${awayId}&league_id=${leagueId}`
  );
  if (!res.ok) throw new Error("Failed to fetch prediction");
  return res.json();
}

export async function fetchHotCold(lottery: string, lastDraws = 50) {
  const res = await fetch(
    `${BASE}/api/lottery/hot-cold/${lottery}?last_draws=${lastDraws}`
  );
  if (!res.ok) throw new Error("Failed to fetch hot/cold");
  return res.json();
}

export async function suggestNumbers(lottery: string, strategy = "balanced") {
  const res = await fetch(
    `${BASE}/api/lottery/suggest/${lottery}?strategy=${strategy}`
  );
  if (!res.ok) throw new Error("Failed to fetch suggestion");
  return res.json();
}
