"use client";

import { useEffect, useState, useCallback } from "react";
import { Trash2, RefreshCw } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { SavedGrid } from "@/lib/lottery-types";
import { LOTTERY_CONFIGS } from "@/lib/lottery-types";

// ── Helpers ────────────────────────────────────────────────────────────────

function getSupabase() {
  // Lazy-load the supabase client only when env vars are present.
  // Avoids throwing during build / SSR when the vars aren't configured yet.
  if (
    !process.env.NEXT_PUBLIC_SUPABASE_URL ||
    !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  ) {
    return null;
  }
  // Dynamic require keeps the import tree clean for SSR
  const { supabase } = require("@/lib/supabase") as typeof import("@/lib/supabase");
  return supabase;
}

function lotteryEmoji(name: string): string {
  return LOTTERY_CONFIGS.find((c) => c.id === name)?.emoji ?? "🎰";
}

function lotteryLabel(name: string): string {
  return LOTTERY_CONFIGS.find((c) => c.id === name)?.label ?? name;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day:   "2-digit",
    month: "short",
    year:  "numeric",
  });
}

// ── Sub-components ─────────────────────────────────────────────────────────

function SmallBall({ value, isBonus }: { value: number; isBonus?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold",
        isBonus
          ? "bg-amber-400 text-amber-900"
          : "bg-blue-600 text-white",
      )}
    >
      {value}
    </span>
  );
}

function GridCard({ grid, onDelete }: { grid: SavedGrid; onDelete: () => void }) {
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    const sb = getSupabase();
    if (!sb) return;
    setDeleting(true);
    await sb.from("lottery_grids").delete().eq("id", grid.id);
    onDelete();
  }

  return (
    <Card size="sm">
      <CardContent className="pt-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <span>{lotteryEmoji(grid.lottery)}</span>
            <span className="text-xs font-semibold text-foreground">
              {lotteryLabel(grid.lottery)}
            </span>
            {grid.strategy && (
              <Badge className="h-4 border-0 px-1.5 text-[10px] bg-secondary text-secondary-foreground">
                {grid.strategy}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-muted-foreground">
              {formatDate(grid.created_at)}
            </span>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="text-muted-foreground hover:text-destructive transition-colors disabled:opacity-50"
              aria-label="Delete grid"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-1">
          {grid.numbers.map((n) => (
            <SmallBall key={n} value={n} />
          ))}
          {grid.bonus != null && <SmallBall value={grid.bonus} isBonus />}
        </div>
      </CardContent>
    </Card>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

interface SavedGridsListProps {
  /** Increment this to trigger a refetch (e.g. after saving a new grid). */
  refreshToken: number;
}

export default function SavedGridsList({ refreshToken }: SavedGridsListProps) {
  const [grids,   setGrids]   = useState<SavedGrid[]>([]);
  const [loading, setLoading] = useState(false);
  const [loggedIn, setLoggedIn] = useState<boolean | null>(null); // null = unknown

  const load = useCallback(async () => {
    const sb = getSupabase();
    if (!sb) {
      setLoggedIn(false);
      return;
    }

    setLoading(true);
    const { data: userResp } = await sb.auth.getUser();
    if (!userResp.user) {
      setLoggedIn(false);
      setLoading(false);
      return;
    }

    setLoggedIn(true);
    const { data } = await sb
      .from("lottery_grids")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(10);

    setGrids(data ?? []);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load, refreshToken]);

  // ── Render states ────────────────────────────────────────────────────────

  if (loggedIn === false) {
    return (
      <div className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
        <p>
          <span className="text-base">🔒</span> Log in to save and view your grids.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-xl ring-1 ring-foreground/10 p-3 space-y-2">
            <Skeleton className="h-4 w-32" />
            <div className="flex gap-1">
              {Array.from({ length: 5 }).map((_, j) => (
                <Skeleton key={j} className="h-7 w-7 rounded-full" />
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (grids.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
        No saved grids yet. Generate a combination and click&nbsp;
        <strong className="text-foreground">Save Grid</strong>.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">{grids.length} saved grid{grids.length !== 1 ? "s" : ""}</p>
        <button
          onClick={load}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <RefreshCw className="h-3 w-3" /> Refresh
        </button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {grids.map((g) => (
          <GridCard key={g.id} grid={g} onDelete={load} />
        ))}
      </div>
    </div>
  );
}
