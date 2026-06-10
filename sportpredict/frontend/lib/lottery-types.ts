export type LotteryId = "loto" | "euromillions" | "keno" | "pmu";
export type Strategy  = "balanced" | "hot" | "cold" | "random";

export interface LotteryConfig {
  id:         LotteryId;
  label:      string;
  emoji:      string;
  max:        number;   // highest main number
  count:      number;   // how many to pick
  bonusMax:   number | null;
  bonusCount: number;   // 0, 1, or 2
  cols:       number;   // grid columns
}

export interface HotColdData {
  hot:       number[];
  cold:      number[];
  /** Keys are stringified numbers because JSON object keys are strings. */
  frequency: Record<string, number>;
  draws_analyzed: number;
}

export interface SuggestionResult {
  numbers:  number[];
  bonus:    number[];   // 0, 1, or 2 items depending on lottery type
  strategy: Strategy;
}

export interface SavedGrid {
  id:         string;
  lottery:    string;
  numbers:    number[];
  bonus:      number | null;
  strategy:   string | null;
  label:      string | null;
  created_at: string;
}

// ── Static config ───────────────────────────────────────────────────────────

export const LOTTERY_CONFIGS: LotteryConfig[] = [
  {
    id:         "loto",
    label:      "Loto FDJ",
    emoji:      "🎱",
    max:        49,
    count:      5,
    bonusMax:   10,
    bonusCount: 1,
    cols:       7,
  },
  {
    id:         "euromillions",
    label:      "EuroMillions",
    emoji:      "⭐",
    max:        50,
    count:      5,
    bonusMax:   12,
    bonusCount: 2,
    cols:       10,
  },
  {
    id:         "keno",
    label:      "Keno",
    emoji:      "🎰",
    max:        70,
    count:      20,
    bonusMax:   null,
    bonusCount: 0,
    cols:       10,
  },
  {
    id:         "pmu",
    label:      "PMU Quinté+",
    emoji:      "🐴",
    max:        18,
    count:      5,
    bonusMax:   null,
    bonusCount: 0,
    cols:       6,
  },
];

export const STRATEGIES: { id: Strategy; label: string; desc: string }[] = [
  { id: "balanced", label: "Balanced",  desc: "Mix of hot, cold & random" },
  { id: "hot",      label: "🔥 Hot",    desc: "Most frequent numbers"     },
  { id: "cold",     label: "🧊 Cold",   desc: "Rarest numbers"            },
  { id: "random",   label: "🎲 Random", desc: "Pure chance"               },
];

export function getLotteryConfig(id: LotteryId): LotteryConfig {
  return LOTTERY_CONFIGS.find((c) => c.id === id)!;
}
