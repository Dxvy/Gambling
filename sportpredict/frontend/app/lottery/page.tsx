"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Sparkles, Save, CheckCircle, AlertCircle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ThemeToggle } from "@/components/ThemeToggle";
import NavUser from "@/components/NavUser";
import NumberGrid   from "@/components/lottery/NumberGrid";
import SelectedBalls from "@/components/lottery/SelectedBalls";
import SavedGridsList from "@/components/lottery/SavedGridsList";
import { cn } from "@/lib/utils";
import { fetchLotteryInsight } from "@/lib/api";
import {
  LOTTERY_CONFIGS,
  STRATEGIES,
  getLotteryConfig,
  type LotteryId,
  type Strategy,
  type HotColdData,
  type SuggestionResult,
} from "@/lib/lottery-types";

// ── Constants ──────────────────────────────────────────────────────────────

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Delay between each ball being revealed (ms)
const REVEAL_INTERVAL_MS = 110;

// ── Helpers ────────────────────────────────────────────────────────────────

async function fetchHotCold(lottery: LotteryId): Promise<HotColdData> {
  const res = await fetch(`${API}/api/lottery/hot-cold/${lottery}`);
  if (!res.ok) throw new Error("Failed to load statistics");
  return res.json();
}

async function fetchSuggestion(
  lottery:  LotteryId,
  strategy: Strategy,
): Promise<SuggestionResult> {
  const res = await fetch(
    `${API}/api/lottery/suggest/${lottery}?strategy=${strategy}`,
  );
  if (!res.ok) throw new Error("Failed to generate numbers");
  return res.json();
}

// ── Page component ─────────────────────────────────────────────────────────

export default function LotteryPage() {
  // Controls
  const [lottery,  setLottery]  = useState<LotteryId>("loto");
  const [strategy, setStrategy] = useState<Strategy>("balanced");

  // Data
  const [hotCold,       setHotCold]       = useState<HotColdData | null>(null);
  const [suggestion,    setSuggestion]    = useState<SuggestionResult | null>(null);
  const [revealedCount, setRevealedCount] = useState(0);

  // UI state
  const [isLoadingHC,   setIsLoadingHC]   = useState(false);
  const [isGenerating,  setIsGenerating]  = useState(false);
  const [isSaving,      setIsSaving]      = useState(false);
  const [saveStatus,    setSaveStatus]    = useState<"idle" | "ok" | "err">("idle");
  const [refreshToken,  setRefreshToken]  = useState(0);

  // AI insight
  const [insight,        setInsight]        = useState<string | null>(null);
  const [isLoadingInsight, setIsLoadingInsight] = useState(false);
  const [insightError,   setInsightError]   = useState(false);

  // Keep track of reveal timers so we can cancel them on new generate
  const revealTimers = useRef<ReturnType<typeof setTimeout>[]>([]);

  // ── Hot/cold fetch — runs on lottery type change ─────────────────────────

  const loadHotCold = useCallback(async (id: LotteryId) => {
    setIsLoadingHC(true);
    try {
      const data = await fetchHotCold(id);
      setHotCold(data);
    } catch {
      // Non-fatal — grid just shows no coloring
      setHotCold(null);
    } finally {
      setIsLoadingHC(false);
    }
  }, []);

  useEffect(() => {
    loadHotCold(lottery);
    // Clear previous suggestion when switching lottery type
    setSuggestion(null);
    setRevealedCount(0);
  }, [lottery, loadHotCold]);

  // ── Generate ─────────────────────────────────────────────────────────────

  async function generate() {
    setIsGenerating(true);
    setSaveStatus("idle");

    // Cancel any in-progress reveal
    revealTimers.current.forEach(clearTimeout);
    revealTimers.current = [];
    setRevealedCount(0);
    setSuggestion(null);
    setInsight(null);
    setInsightError(false);

    try {
      const data = await fetchSuggestion(lottery, strategy);
      setSuggestion(data);

      // Stagger reveal: one ball every REVEAL_INTERVAL_MS ms
      const totalBalls = data.numbers.length;
      const timers = data.numbers.map((_, idx) =>
        setTimeout(
          () => setRevealedCount(idx + 1),
          (idx + 1) * REVEAL_INTERVAL_MS,
        ),
      );
      revealTimers.current = timers;
    } catch {
      // Keep previous suggestion visible, don't crash
    } finally {
      setIsGenerating(false);
    }
  }

  // ── Save to Supabase ──────────────────────────────────────────────────────

  async function saveGrid() {
    if (!suggestion) return;
    setIsSaving(true);
    setSaveStatus("idle");

    try {
      // Dynamic import keeps Supabase out of the initial bundle
      const { saveLotteryGrid } = await import("@/lib/supabase");
      // For EuroMillions (2 bonus stars), only the first is stored in the
      // single `bonus` int column — full star support needs a schema migration
      const bonusInt = suggestion.bonus.length > 0 ? suggestion.bonus[0] : null;
      const result   = await saveLotteryGrid(lottery, suggestion.numbers, bonusInt, strategy);

      if (result?.error) {
        setSaveStatus("err");
      } else {
        setSaveStatus("ok");
        setRefreshToken((t) => t + 1);
        // Reset status after 3 s
        setTimeout(() => setSaveStatus("idle"), 3000);
      }
    } catch {
      setSaveStatus("err");
    } finally {
      setIsSaving(false);
    }
  }

  // ── AI Insight ────────────────────────────────────────────────────────────

  async function getInsight() {
    if (!suggestion) return;
    if (insight) {
      setInsight(null);
      return;
    }
    setIsLoadingInsight(true);
    setInsightError(false);
    try {
      const { insight: text } = await fetchLotteryInsight(
        lottery, suggestion.numbers, suggestion.bonus, strategy,
      );
      setInsight(text);
    } catch {
      setInsightError(true);
    } finally {
      setIsLoadingInsight(false);
    }
  }

  // ── Derived state ─────────────────────────────────────────────────────────

  const config     = getLotteryConfig(lottery);
  const hotSet     = new Set(hotCold?.hot  ?? []);
  const coldSet    = new Set(hotCold?.cold ?? []);
  const selectedSet = new Set(suggestion?.numbers ?? []);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex min-h-screen flex-col bg-background">

      {/* ── Navbar ── */}
      <header className="sticky top-0 z-30 border-b border-border bg-background">
        <div className="flex h-14 items-center justify-between px-4 md:px-6">
          <Link href="/" className="text-lg font-bold tracking-tight text-foreground">
            SportPredict
          </Link>
          <nav className="hidden items-center gap-6 text-sm md:flex">
            <Link href="/sports"    className="text-muted-foreground hover:text-foreground transition-colors">Sports</Link>
            <Link href="/lottery"   className="font-medium text-foreground">Lottery</Link>
            <Link href="/dashboard" className="text-muted-foreground hover:text-foreground transition-colors">Dashboard</Link>
          </nav>
          <div className="flex items-center gap-2">
            <NavUser />
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* ── Main content ── */}
      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6 md:px-6">

        {/* ── Page title ── */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">Lottery Tool</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Generate smart number combinations based on historical draw statistics.
          </p>
        </div>

        {/* ── Configurator card ── */}
        <Card className="mb-6">
          <CardContent className="space-y-5 p-5">

            {/* Lottery type */}
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Lottery type
              </label>
              <div className="flex flex-wrap gap-2">
                {LOTTERY_CONFIGS.map((cfg) => (
                  <button
                    key={cfg.id}
                    onClick={() => setLottery(cfg.id)}
                    className={cn(
                      "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors",
                      lottery === cfg.id
                        ? "bg-blue-600 text-white"
                        : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground",
                    )}
                  >
                    <span>{cfg.emoji}</span>
                    <span className="hidden sm:inline">{cfg.label}</span>
                    <span className="sm:hidden">{cfg.id === "euromillions" ? "Euro" : cfg.label.split(" ")[0]}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Strategy */}
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Strategy
              </label>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {STRATEGIES.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setStrategy(s.id)}
                    title={s.desc}
                    className={cn(
                      "flex flex-col items-center rounded-xl px-3 py-2.5 text-xs font-medium transition-colors",
                      strategy === s.id
                        ? "bg-blue-600 text-white"
                        : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground",
                    )}
                  >
                    <span className="text-sm">{s.label}</span>
                    <span className={cn(
                      "mt-0.5 font-normal",
                      strategy === s.id ? "text-blue-100" : "text-muted-foreground/70",
                    )}>
                      {s.desc}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Generate button */}
            <button
              onClick={generate}
              disabled={isGenerating}
              className={cn(
                "flex w-full items-center justify-center gap-2 rounded-xl",
                "py-3 text-sm font-semibold transition-colors",
                "bg-blue-600 text-white hover:bg-blue-700",
                "disabled:cursor-not-allowed disabled:opacity-60",
              )}
            >
              <Sparkles className={cn("h-4 w-4", isGenerating && "animate-spin")} />
              {isGenerating ? "Generating…" : `Generate ${config.count} Numbers`}
            </button>
          </CardContent>
        </Card>

        {/* ── Generated numbers ── */}
        {suggestion && (
          <Card className="mb-6">
            <CardContent className="p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-foreground">Your Numbers</h2>
                <span className="text-xs text-muted-foreground capitalize">
                  {suggestion.strategy} strategy
                </span>
              </div>

              <SelectedBalls
                numbers={suggestion.numbers}
                bonus={suggestion.bonus}
                revealedCount={revealedCount}
                lotteryLabel={config.label}
              />

              {/* Save / AI Insight buttons */}
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <button
                  onClick={saveGrid}
                  disabled={isSaving || revealedCount < suggestion.numbers.length}
                  className={cn(
                    "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors",
                    "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground",
                    "disabled:cursor-not-allowed disabled:opacity-50",
                  )}
                >
                  <Save className="h-4 w-4" />
                  {isSaving ? "Saving…" : "Save Grid"}
                </button>

                <button
                  onClick={getInsight}
                  disabled={isLoadingInsight || revealedCount < suggestion.numbers.length}
                  className={cn(
                    "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors",
                    "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground",
                    "disabled:cursor-not-allowed disabled:opacity-50",
                  )}
                >
                  <Sparkles className={cn("h-4 w-4", isLoadingInsight && "animate-spin")} />
                  {isLoadingInsight ? "Thinking…" : insight ? "Hide insight" : "AI Insight"}
                </button>

                {saveStatus === "ok" && (
                  <span className="flex items-center gap-1.5 text-xs text-green-600 dark:text-green-400">
                    <CheckCircle className="h-3.5 w-3.5" /> Saved!
                  </span>
                )}
                {saveStatus === "err" && (
                  <span className="flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400">
                    <AlertCircle className="h-3.5 w-3.5" /> Log in to save grids.
                  </span>
                )}
                {insightError && (
                  <span className="flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400">
                    <AlertCircle className="h-3.5 w-3.5" /> Insight unavailable.
                  </span>
                )}
              </div>

              {/* AI Insight text */}
              {insight && (
                <div className="rounded-xl bg-muted/60 p-3 text-sm leading-relaxed text-muted-foreground">
                  <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-foreground/70">
                    <Sparkles className="h-3.5 w-3.5" /> AI Insight
                  </div>
                  {insight}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* ── Number grid ── */}
        <Card className="mb-6">
          <CardContent className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-foreground">
                Number Heat Map
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  1 – {config.max}
                </span>
              </h2>
              {isLoadingHC && (
                <span className="text-xs text-muted-foreground animate-pulse">
                  Loading stats…
                </span>
              )}
            </div>

            {/* Legend */}
            <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-blue-600" />
                Selected
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-green-500/50" />
                Hot (frequent)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-full bg-red-500/40" />
                Cold (rare)
              </span>
            </div>

            {/* Grid or skeleton while loading */}
            {isLoadingHC ? (
              <div className="grid grid-cols-7 gap-1">
                {Array.from({ length: config.max }).map((_, i) => (
                  <Skeleton key={i} className="aspect-square rounded-full" />
                ))}
              </div>
            ) : (
              <NumberGrid
                maxNumber={config.max}
                cols={config.cols}
                hotSet={hotSet}
                coldSet={coldSet}
                selectedSet={selectedSet}
              />
            )}

            {/* EuroMillions bonus star grid */}
            {lottery === "euromillions" && (
              <div className="border-t border-border pt-4 space-y-2">
                <p className="text-xs font-medium text-muted-foreground">
                  Stars grid (1 – 12)
                </p>
                <NumberGrid
                  maxNumber={12}
                  cols={6}
                  hotSet={new Set()}
                  coldSet={new Set()}
                  selectedSet={new Set(suggestion?.bonus ?? [])}
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── Saved grids ── */}
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-foreground">Recent Saved Grids</h2>
          <SavedGridsList refreshToken={refreshToken} />
        </section>
      </main>
    </div>
  );
}
