import type { Match } from "./types";

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

type MatchInsightInput = Pick<
  Match,
  | "homeTeam"
  | "awayTeam"
  | "league"
  | "homeProb"
  | "drawProb"
  | "awayProb"
  | "prediction"
  | "confidence"
  | "homeForm"
  | "awayForm"
  | "isValueBet"
>;

export async function fetchMatchInsight(match: MatchInsightInput): Promise<{ insight: string }> {
  const res = await fetch(`${BASE}/api/sports/insight`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      home_team: match.homeTeam,
      away_team: match.awayTeam,
      league: match.league,
      home_prob: match.homeProb,
      draw_prob: match.drawProb,
      away_prob: match.awayProb,
      prediction: match.prediction,
      confidence: match.confidence,
      home_form: match.homeForm,
      away_form: match.awayForm,
      is_value_bet: match.isValueBet,
    }),
  });
  if (!res.ok) throw new Error("Failed to fetch AI insight");
  return res.json();
}

export async function fetchLotteryInsight(
  lottery: string,
  numbers: number[],
  bonus: number[],
  strategy: string
): Promise<{ insight: string }> {
  const res = await fetch(`${BASE}/api/lottery/insight`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lottery, numbers, bonus, strategy }),
  });
  if (!res.ok) throw new Error("Failed to fetch AI insight");
  return res.json();
}
