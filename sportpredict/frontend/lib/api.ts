import type { Match } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function fetchFixtures(leagueId: string, nextN = 10) {
  const res = await fetch(
    `${BASE}/api/sports/fixtures?league_id=${leagueId}&next_n=${nextN}`
  );
  if (!res.ok) throw new Error("Failed to fetch fixtures");
  return res.json();
}

function formatMatchDate(iso: string): string {
  const d = new Date(iso);
  return (
    d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) +
    " " +
    d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
  );
}

export async function fetchPredictBatch(leagueId: string, nextN = 10): Promise<Match[]> {
  const res = await fetch(
    `${BASE}/api/sports/predict/batch?league_id=${leagueId}&next_n=${nextN}`
  );
  if (!res.ok) throw new Error("Failed to fetch predictions");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const data: any[] = await res.json();
  return data.map((item, i) => ({
    id: item.fixture_id != null ? String(item.fixture_id) : String(i),
    homeTeam: item.home_team,
    awayTeam: item.away_team,
    homeProb: Math.round(item.home_prob),
    drawProb: Math.round(item.draw_prob),
    awayProb: Math.round(item.away_prob),
    prediction: item.prediction,
    confidence: item.confidence,
    isValueBet: item.is_value_bet,
    matchDate: item.date ? formatMatchDate(item.date) : "",
    league: item.league_id,
    leagueId: item.league_id,
    homeForm: "",
    awayForm: "",
  }));
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapFixture(item: any, i: number): Match {
  return {
    id: item.fixture_id != null ? String(item.fixture_id) : String(i),
    homeTeam: item.home_team.name,
    awayTeam: item.away_team.name,
    homeProb: 0,
    drawProb: 0,
    awayProb: 0,
    prediction: "HOME" as const,
    confidence: 0,
    isValueBet: false,
    matchDate: item.date ? formatMatchDate(item.date) : "",
    league: item.league,
    leagueId: item.league_id,
    homeForm: "",
    awayForm: "",
  };
}

export async function fetchUpcomingFixtures(leagueId: string, nextN = 10): Promise<Match[]> {
  const res = await fetch(
    `${BASE}/api/sports/fixtures?league_id=${leagueId}&next_n=${nextN}`
  );
  if (!res.ok) throw new Error("Failed to fetch fixtures");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const data: any[] = await res.json();
  return data.map(mapFixture);
}

/** Upcoming fixtures across every supported competition, combined and sorted by date. */
export async function fetchAllFixtures(): Promise<Match[]> {
  const res = await fetch(`${BASE}/api/sports/fixtures/all`);
  if (!res.ok) throw new Error("Failed to fetch fixtures");
  const data: { fixtures: unknown[] } = await res.json();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (data.fixtures as any[]).map(mapFixture);
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
