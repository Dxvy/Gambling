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
