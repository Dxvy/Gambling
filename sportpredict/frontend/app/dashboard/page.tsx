"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import {
  TrendingUp,
  Target,
  CheckCircle2,
  Zap,
  Download,
  ChevronUp,
  ChevronDown,
} from "lucide-react";
import { format, parseISO } from "date-fns";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ThemeToggle } from "@/components/ThemeToggle";
import NavUser from "@/components/NavUser";
import { supabase } from "@/lib/supabase";
import { leaguesByCountry } from "@/lib/constants";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────

interface PredictionRow {
  id: string;
  homeTeam: string;
  awayTeam: string;
  league: string;
  prediction: string;
  confidence: number;
  isValueBet: boolean;
  matchDate: string;
  result: string | null;
  correct: boolean | null;
  created_at: string;
}

type SortKey = "created_at" | "league" | "confidence" | "correct";
type SortDir = "asc" | "desc";

// ── Constants ─────────────────────────────────────────────────────────────────

const INITIAL_BANKROLL = 100;
const BET_SIZE = 10;

const FOOTBALL_LEAGUES = new Set(
  Object.values(leaguesByCountry)
    .flat()
    .map((l) => l.name)
);

// ── Helpers ───────────────────────────────────────────────────────────────────

function getSport(league: string) {
  return FOOTBALL_LEAGUES.has(league) ? "football" : "other";
}

function predLabel(p: string) {
  return p === "HOME" ? "Home" : p === "AWAY" ? "Away" : "Draw";
}

function exportToCSV(rows: PredictionRow[]) {
  const headers = [
    "Date",
    "Home Team",
    "Away Team",
    "League",
    "Prediction",
    "Confidence (%)",
    "Value Bet",
    "Match Date",
    "Result",
    "Correct",
  ];
  const lines = rows.map((r) => [
    format(parseISO(r.created_at), "yyyy-MM-dd HH:mm"),
    r.homeTeam,
    r.awayTeam,
    r.league,
    r.prediction,
    r.confidence,
    r.isValueBet ? "Yes" : "No",
    r.matchDate,
    r.result ?? "Pending",
    r.correct === null ? "Pending" : r.correct ? "Yes" : "No",
  ]);

  const csv = [headers, ...lines]
    .map((row) =>
      row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")
    )
    .join("\n");

  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `predictions-${format(new Date(), "yyyy-MM-dd")}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  icon,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
  accent?: "green" | "blue" | "purple" | "amber";
}) {
  const accentClasses = {
    green: "bg-green-500/10 text-green-600 dark:text-green-400",
    blue: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
    purple: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
    amber: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  };
  return (
    <Card>
      <CardContent className="flex items-start gap-3 pt-5">
        <span
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
            accentClasses[accent ?? "blue"]
          )}
        >
          {icon}
        </span>
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="mt-0.5 text-2xl font-bold tabular-nums text-foreground">
            {value}
          </p>
          {sub && (
            <p className="mt-0.5 text-[11px] text-muted-foreground">{sub}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function RoiTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ value: number; payload: { label: string } }>;
}) {
  if (!active || !payload?.length) return null;
  const bankroll = payload[0].value;
  const net = bankroll - INITIAL_BANKROLL;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="font-semibold text-foreground">€{bankroll.toFixed(0)}</p>
      <p
        className={cn(
          "mt-0.5",
          net >= 0
            ? "text-green-600 dark:text-green-400"
            : "text-red-500 dark:text-red-400"
        )}
      >
        {net >= 0 ? "+" : ""}€{net.toFixed(0)} net
      </p>
    </div>
  );
}

function SortHeader({
  label,
  sortKey,
  current,
  dir,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  current: SortKey;
  dir: SortDir;
  onSort: (k: SortKey) => void;
}) {
  const active = current === sortKey;
  return (
    <button
      onClick={() => onSort(sortKey)}
      className="flex items-center gap-0.5 text-left font-medium hover:text-foreground"
    >
      {label}
      <span className="ml-0.5 flex flex-col">
        <ChevronUp
          className={cn(
            "h-2.5 w-2.5",
            active && dir === "asc" ? "text-foreground" : "opacity-30"
          )}
        />
        <ChevronDown
          className={cn(
            "h-2.5 w-2.5 -mt-0.5",
            active && dir === "desc" ? "text-foreground" : "opacity-30"
          )}
        />
      </span>
    </button>
  );
}

// ── Skeleton loaders ──────────────────────────────────────────────────────────

function StatsSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {[...Array(4)].map((_, i) => (
        <Card key={i}>
          <CardContent className="flex items-start gap-3 pt-5">
            <Skeleton className="h-9 w-9 rounded-lg" />
            <div className="flex-1 space-y-1.5">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-7 w-14" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="space-y-2">
      {[...Array(5)].map((_, i) => (
        <Skeleton key={i} className="h-10 w-full rounded-lg" />
      ))}
    </div>
  );
}

// ── Dashboard page ────────────────────────────────────────────────────────────

const PREDICTION_COLORS: Record<string, string> = {
  HOME: "bg-blue-600 text-white",
  DRAW: "bg-yellow-500 text-white",
  AWAY: "bg-violet-600 text-white",
};

export default function DashboardPage() {
  // ── Data ─────────────────────────────────────────────────────────────────
  const [rows, setRows] = useState<PredictionRow[]>([]);
  const [loading, setLoading] = useState(true);

  // ── Filters ──────────────────────────────────────────────────────────────
  const [sport, setSport] = useState("all");
  const [league, setLeague] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [valueBetsOnly, setValueBetsOnly] = useState(false);

  // ── Table sort ───────────────────────────────────────────────────────────
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // ── Dark-mode detection for chart colors ─────────────────────────────────
  const [isDark, setIsDark] = useState(false);
  useEffect(() => {
    const update = () =>
      setIsDark(document.documentElement.classList.contains("dark"));
    update();
    const obs = new MutationObserver(update);
    obs.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => obs.disconnect();
  }, []);

  // ── Fetch ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) return;

      const { data } = await supabase
        .from("prediction_history")
        .select("*")
        .order("created_at", { ascending: true });

      setRows(data ?? []);
      setLoading(false);
    })();
  }, []);

  // ── Derived: unique leagues from loaded data ──────────────────────────────
  const leagues = useMemo(
    () => [...new Set(rows.map((r) => r.league))].sort(),
    [rows]
  );

  // ── Filtered rows ─────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (sport !== "all" && getSport(r.league) !== sport) return false;
      if (league !== "all" && r.league !== league) return false;
      if (valueBetsOnly && !r.isValueBet) return false;
      if (dateFrom && r.created_at.slice(0, 10) < dateFrom) return false;
      if (dateTo && r.created_at.slice(0, 10) > dateTo) return false;
      return true;
    });
  }, [rows, sport, league, valueBetsOnly, dateFrom, dateTo]);

  // ── Stats ─────────────────────────────────────────────────────────────────
  const resolved = useMemo(
    () => filtered.filter((r) => r.correct !== null),
    [filtered]
  );
  const correctCount = useMemo(
    () => resolved.filter((r) => r.correct).length,
    [resolved]
  );
  const accuracy =
    resolved.length > 0
      ? Math.round((correctCount / resolved.length) * 100)
      : null;

  const streak = useMemo(() => {
    let s = 0;
    for (let i = resolved.length - 1; i >= 0; i--) {
      if (resolved[i].correct) s++;
      else break;
    }
    return s;
  }, [resolved]);

  // ── ROI chart data (resolved predictions in chronological order) ──────────
  const roiData = useMemo(() => {
    let bankroll = INITIAL_BANKROLL;
    const points: { label: string; bankroll: number }[] = [
      { label: "Start", bankroll: INITIAL_BANKROLL },
    ];
    resolved.forEach((r, i) => {
      bankroll += r.correct ? BET_SIZE : -BET_SIZE;
      points.push({
        label: `#${i + 1}`,
        bankroll,
      });
    });
    return points;
  }, [resolved]);

  // ── Sorted table rows ─────────────────────────────────────────────────────
  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "created_at") {
        cmp = a.created_at.localeCompare(b.created_at);
      } else if (sortKey === "league") {
        cmp = a.league.localeCompare(b.league);
      } else if (sortKey === "confidence") {
        cmp = a.confidence - b.confidence;
      } else if (sortKey === "correct") {
        const va = a.correct === null ? -1 : a.correct ? 1 : 0;
        const vb = b.correct === null ? -1 : b.correct ? 1 : 0;
        cmp = va - vb;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  // ── Chart colors ──────────────────────────────────────────────────────────
  const chartColors = isDark
    ? { axis: "#64748b", grid: "#1e293b", positive: "#22c55e", line: "#3b82f6" }
    : { axis: "#94a3b8", grid: "#f1f5f9", positive: "#16a34a", line: "#2563eb" };

  // ── Render ────────────────────────────────────────────────────────────────

  const filterSelectClass = cn(
    "h-8 rounded-lg border border-border bg-background px-2.5 text-xs",
    "text-foreground focus:outline-none focus:ring-2 focus:ring-blue-600/30"
  );

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* ── Navbar ── */}
      <header className="sticky top-0 z-30 border-b border-border bg-background">
        <div className="flex h-14 items-center justify-between px-4 md:px-6">
          <Link
            href="/"
            className="text-lg font-bold tracking-tight text-foreground"
          >
            SportPredict
          </Link>
          <nav className="hidden items-center gap-6 text-sm md:flex">
            <Link
              href="/sports"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              Sports
            </Link>
            <Link
              href="/lottery"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              Lottery
            </Link>
            <Link href="/dashboard" className="font-medium text-foreground">
              Dashboard
            </Link>
          </nav>
          <div className="flex items-center gap-2">
            <NavUser />
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-6">
        {/* ── Page header ── */}
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Your prediction analytics and history
            </p>
          </div>
          <button
            onClick={() => exportToCSV(sorted)}
            disabled={sorted.length === 0}
            className={cn(
              "flex items-center gap-1.5 rounded-xl border border-border px-3 py-2",
              "text-xs font-medium text-muted-foreground transition-colors",
              "hover:bg-muted hover:text-foreground",
              "disabled:cursor-not-allowed disabled:opacity-40"
            )}
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </button>
        </div>

        {/* ── Filters ── */}
        <div className="mb-6 flex flex-wrap items-center gap-2">
          {/* Sport */}
          <select
            value={sport}
            onChange={(e) => {
              setSport(e.target.value);
              setLeague("all");
            }}
            className={filterSelectClass}
          >
            <option value="all">All sports</option>
            <option value="football">Football</option>
          </select>

          {/* League */}
          <select
            value={league}
            onChange={(e) => setLeague(e.target.value)}
            className={filterSelectClass}
          >
            <option value="all">All leagues</option>
            {leagues.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>

          {/* Date from */}
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            max={dateTo || undefined}
            className={cn(filterSelectClass, "cursor-pointer")}
            aria-label="From date"
          />

          {/* Date to */}
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            min={dateFrom || undefined}
            className={cn(filterSelectClass, "cursor-pointer")}
            aria-label="To date"
          />

          {/* Value bets */}
          <button
            onClick={() => setValueBetsOnly((v) => !v)}
            className={cn(
              "flex h-8 items-center gap-1.5 rounded-lg border px-3 text-xs font-medium transition-colors",
              valueBetsOnly
                ? "border-purple-500 bg-purple-600 text-white"
                : "border-border text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            Value bets only
          </button>

          {/* Clear */}
          {(sport !== "all" ||
            league !== "all" ||
            dateFrom ||
            dateTo ||
            valueBetsOnly) && (
            <button
              onClick={() => {
                setSport("all");
                setLeague("all");
                setDateFrom("");
                setDateTo("");
                setValueBetsOnly(false);
              }}
              className="text-xs text-blue-600 hover:underline dark:text-blue-400"
            >
              Clear filters
            </button>
          )}
        </div>

        {/* ── Stat cards ── */}
        {loading ? (
          <div className="mb-6">
            <StatsSkeleton />
          </div>
        ) : (
          <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard
              label="Total Predictions"
              value={filtered.length}
              sub={
                filtered.length !== rows.length
                  ? `${rows.length} total`
                  : undefined
              }
              icon={<Target className="h-4 w-4" />}
              accent="blue"
            />
            <StatCard
              label="Accuracy"
              value={accuracy !== null ? `${accuracy}%` : "—"}
              sub={
                resolved.length > 0
                  ? `${resolved.length} resolved`
                  : "No results yet"
              }
              icon={<TrendingUp className="h-4 w-4" />}
              accent={
                accuracy === null
                  ? "blue"
                  : accuracy >= 60
                  ? "green"
                  : accuracy >= 50
                  ? "amber"
                  : "purple"
              }
            />
            <StatCard
              label="Correct Picks"
              value={correctCount}
              sub={
                resolved.length > 0
                  ? `of ${resolved.length} resolved`
                  : "No results yet"
              }
              icon={<CheckCircle2 className="h-4 w-4" />}
              accent="green"
            />
            <StatCard
              label="Win Streak"
              value={streak}
              sub={streak > 0 ? "consecutive wins" : "No active streak"}
              icon={<Zap className="h-4 w-4" />}
              accent="amber"
            />
          </div>
        )}

        {/* ── ROI Chart ── */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-sm">
              Bankroll Simulation{" "}
              <span className="font-normal text-muted-foreground">
                (€{INITIAL_BANKROLL} start · €{BET_SIZE}/bet)
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-5">
            {loading ? (
              <Skeleton className="h-[200px] w-full rounded-lg" />
            ) : resolved.length === 0 ? (
              <div className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">
                <p>Chart populates as predictions are resolved.</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart
                  data={roiData}
                  margin={{ top: 8, right: 16, bottom: 0, left: 0 }}
                >
                  <CartesianGrid
                    strokeDasharray="4 4"
                    stroke={chartColors.grid}
                    vertical={false}
                  />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 10, fill: chartColors.axis }}
                    axisLine={false}
                    tickLine={false}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tickFormatter={(v) => `€${v}`}
                    tick={{ fontSize: 10, fill: chartColors.axis }}
                    axisLine={false}
                    tickLine={false}
                    width={52}
                    domain={["auto", "auto"]}
                  />
                  <Tooltip
                    content={<RoiTooltip />}
                    cursor={{
                      stroke: chartColors.axis,
                      strokeWidth: 1,
                      strokeDasharray: "4 4",
                    }}
                  />
                  <ReferenceLine
                    y={INITIAL_BANKROLL}
                    stroke={chartColors.axis}
                    strokeDasharray="4 4"
                    strokeWidth={1}
                  />
                  <Line
                    type="monotone"
                    dataKey="bankroll"
                    stroke={chartColors.line}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 0 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* ── History Table ── */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">
              Prediction History
              {!loading && (
                <span className="ml-2 font-normal text-muted-foreground">
                  {sorted.length} row{sorted.length !== 1 ? "s" : ""}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-4">
            {loading ? (
              <TableSkeleton />
            ) : sorted.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border py-12 text-center">
                <p className="text-sm text-muted-foreground">
                  {rows.length === 0
                    ? "No predictions saved yet. Save a match prediction from the Sports page."
                    : "No predictions match the current filters."}
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto -mx-4 px-4">
                <table className="w-full min-w-[720px] text-xs">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground">
                      <th className="pb-2 pr-4 text-left font-medium">
                        <SortHeader
                          label="Date"
                          sortKey="created_at"
                          current={sortKey}
                          dir={sortDir}
                          onSort={toggleSort}
                        />
                      </th>
                      <th className="pb-2 pr-4 text-left font-medium">
                        Match
                      </th>
                      <th className="pb-2 pr-4 text-left font-medium">
                        <SortHeader
                          label="League"
                          sortKey="league"
                          current={sortKey}
                          dir={sortDir}
                          onSort={toggleSort}
                        />
                      </th>
                      <th className="pb-2 pr-4 text-left font-medium">
                        Prediction
                      </th>
                      <th className="pb-2 pr-4 text-right font-medium">
                        <SortHeader
                          label="Conf."
                          sortKey="confidence"
                          current={sortKey}
                          dir={sortDir}
                          onSort={toggleSort}
                        />
                      </th>
                      <th className="pb-2 pr-4 text-left font-medium">
                        Result
                      </th>
                      <th className="pb-2 text-left font-medium">
                        <SortHeader
                          label="Correct"
                          sortKey="correct"
                          current={sortKey}
                          dir={sortDir}
                          onSort={toggleSort}
                        />
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {sorted.map((r) => (
                      <tr
                        key={r.id}
                        className="text-foreground transition-colors hover:bg-muted/40"
                      >
                        {/* Date */}
                        <td className="py-2.5 pr-4 tabular-nums text-muted-foreground">
                          {format(parseISO(r.created_at), "dd MMM yy")}
                        </td>

                        {/* Match */}
                        <td className="py-2.5 pr-4">
                          <span className="font-medium">{r.homeTeam}</span>
                          <span className="mx-1 text-muted-foreground">vs</span>
                          <span className="font-medium">{r.awayTeam}</span>
                          {r.isValueBet && (
                            <Badge className="ml-1.5 h-4 border-0 bg-purple-600 px-1 text-[9px] font-semibold text-white">
                              VALUE
                            </Badge>
                          )}
                        </td>

                        {/* League */}
                        <td className="py-2.5 pr-4 text-muted-foreground">
                          {r.league}
                        </td>

                        {/* Prediction */}
                        <td className="py-2.5 pr-4">
                          <span
                            className={cn(
                              "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold",
                              PREDICTION_COLORS[r.prediction] ??
                                "bg-muted text-muted-foreground"
                            )}
                          >
                            {predLabel(r.prediction)}
                          </span>
                        </td>

                        {/* Confidence */}
                        <td className="py-2.5 pr-4 text-right tabular-nums">
                          <span
                            className={cn(
                              "font-medium",
                              r.confidence >= 70
                                ? "text-green-600 dark:text-green-400"
                                : r.confidence >= 55
                                ? "text-amber-500"
                                : "text-muted-foreground"
                            )}
                          >
                            {r.confidence}%
                          </span>
                        </td>

                        {/* Result */}
                        <td className="py-2.5 pr-4">
                          {r.result ? (
                            <span
                              className={cn(
                                "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold",
                                PREDICTION_COLORS[r.result] ??
                                  "bg-muted text-muted-foreground"
                              )}
                            >
                              {predLabel(r.result)}
                            </span>
                          ) : (
                            <span className="text-muted-foreground/60 italic">
                              Pending
                            </span>
                          )}
                        </td>

                        {/* Correct */}
                        <td className="py-2.5">
                          {r.correct === null ? (
                            <span className="text-muted-foreground/60">—</span>
                          ) : r.correct ? (
                            <span className="font-bold text-green-600 dark:text-green-400">
                              ✓
                            </span>
                          ) : (
                            <span className="font-bold text-red-500 dark:text-red-400">
                              ✗
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
