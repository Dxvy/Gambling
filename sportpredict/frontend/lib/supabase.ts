import { createBrowserClient } from "@supabase/ssr";

// Provide placeholder values so the module can be imported during SSR/prerender
// without throwing. The client is only actually used client-side (effects/handlers).
export const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL ?? "https://placeholder.supabase.co",
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "placeholder-anon-key",
);

export async function savePrediction(data: {
  homeTeam: string;
  awayTeam: string;
  league: string;
  prediction: string;
  confidence: number;
  isValueBet: boolean;
  matchDate: string;
}) {
  const { data: user } = await supabase.auth.getUser();
  if (!user.user) return;
  return supabase.from("prediction_history").insert({
    ...data,
    user_id: user.user.id,
  });
}

export interface MatchPredictionRow {
  fixture_id: number | string;
  home_prob: number;
  draw_prob: number;
  away_prob: number;
  prediction: "HOME" | "DRAW" | "AWAY";
  confidence: number;
  is_value_bet: boolean;
  home_form: string;
  away_form: string;
  is_low_quality: boolean;
}

/**
 * Fetch precomputed predictions for a set of fixture ids, keyed by fixture id
 * as a string (fixture_id is bigint in Postgres and can come back as either a
 * number or a string depending on size, while the frontend's Match.id is
 * always a string — normalizing to string here avoids a silent join miss).
 */
export async function fetchPredictionsByFixtureIds(
  fixtureIds: number[],
): Promise<Map<string, MatchPredictionRow>> {
  const map = new Map<string, MatchPredictionRow>();
  if (fixtureIds.length === 0) return map;

  const { data, error } = await supabase
    .from("match_predictions")
    .select(
      "fixture_id, home_prob, draw_prob, away_prob, prediction, confidence, is_value_bet, home_form, away_form, is_low_quality",
    )
    .in("fixture_id", fixtureIds);

  if (error || !data) return map;

  for (const row of data as MatchPredictionRow[]) {
    map.set(String(row.fixture_id), row);
  }
  return map;
}

export async function saveLotteryGrid(
  lottery: string,
  numbers: number[],
  bonus: number | null,
  label?: string,
) {
  const { data: user } = await supabase.auth.getUser();
  if (!user.user) return;
  return supabase.from("lottery_grids").insert({
    lottery,
    numbers,
    bonus,
    label,
    user_id: user.user.id,
  });
}

export async function savePushSubscription(subscription: PushSubscriptionJSON) {
  const { data: user } = await supabase.auth.getUser();
  if (!user.user || !subscription.endpoint || !subscription.keys) return;
  return supabase.from("push_subscriptions").upsert(
    {
      user_id:  user.user.id,
      endpoint: subscription.endpoint,
      p256dh:   subscription.keys.p256dh,
      auth:     subscription.keys.auth,
    },
    { onConflict: "endpoint" },
  );
}

export async function deletePushSubscription(endpoint: string) {
  return supabase.from("push_subscriptions").delete().eq("endpoint", endpoint);
}
