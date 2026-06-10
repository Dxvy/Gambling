"use client";

import { useState } from "react";
import { Save, CheckCircle, AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Match } from "@/lib/types";

const OUTCOMES = ["HOME", "DRAW", "AWAY"] as const;
const OUTCOME_LABELS = { HOME: "Home", DRAW: "Draw", AWAY: "Away" };

function FormDot({ result }: { result: string }) {
  return (
    <span
      aria-label={result}
      className={cn(
        "inline-block h-2.5 w-2.5 rounded-full",
        result === "W" && "bg-green-500",
        result === "D" && "bg-yellow-400",
        result === "L" && "bg-red-400",
      )}
    />
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const color =
    value >= 70 ? "bg-green-500" : value >= 55 ? "bg-yellow-400" : "bg-red-400";
  return (
    <div>
      <div className="mb-1 flex justify-between text-[10px] text-muted-foreground">
        <span>Confidence</span>
        <span className="font-medium tabular-nums">{value}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full transition-all duration-500", color)}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

export default function MatchCard({
  homeTeam,
  awayTeam,
  homeProb,
  drawProb,
  awayProb,
  prediction,
  confidence,
  isValueBet,
  matchDate,
  league,
  homeForm,
  awayForm,
}: Match) {
  const probs = { HOME: homeProb, DRAW: drawProb, AWAY: awayProb };

  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "ok" | "err">("idle");

  async function handleSave() {
    setSaving(true);
    setSaveStatus("idle");
    try {
      const { savePrediction } = await import("@/lib/supabase");
      const result = await savePrediction({
        homeTeam, awayTeam, league, prediction, confidence, isValueBet, matchDate,
      });
      if (result?.error) {
        setSaveStatus("err");
      } else {
        setSaveStatus("ok");
        setTimeout(() => setSaveStatus("idle"), 3000);
      }
    } catch {
      setSaveStatus("err");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card
      className={cn(
        "transition-all duration-200 hover:shadow-md",
        isValueBet && "ring-purple-400/40 ring-2",
      )}
    >
      <CardContent className="space-y-3 p-4">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2">
          <span className="text-xs font-medium text-muted-foreground">{league}</span>
          <div className="flex shrink-0 items-center gap-1.5">
            {isValueBet && (
              <Badge className="h-4 border-0 bg-purple-600 px-1.5 text-[10px] font-semibold text-white">
                VALUE BET
              </Badge>
            )}
            <span className="text-xs text-muted-foreground">{matchDate}</span>
          </div>
        </div>

        {/* Teams + form */}
        <div className="grid grid-cols-[1fr_32px_1fr] items-center gap-1">
          <div className="min-w-0 text-center">
            <p className="truncate text-sm font-semibold text-foreground">{homeTeam}</p>
            <div className="mt-1 flex justify-center gap-0.5">
              {homeForm.split("").map((r, i) => (
                <FormDot key={i} result={r} />
              ))}
            </div>
          </div>

          <div className="text-center text-xs font-light text-muted-foreground">VS</div>

          <div className="min-w-0 text-center">
            <p className="truncate text-sm font-semibold text-foreground">{awayTeam}</p>
            <div className="mt-1 flex justify-center gap-0.5">
              {awayForm.split("").map((r, i) => (
                <FormDot key={i} result={r} />
              ))}
            </div>
          </div>
        </div>

        {/* Outcome probability buttons */}
        <div className="grid grid-cols-3 gap-1.5">
          {OUTCOMES.map((outcome) => {
            const isActive = prediction === outcome;
            return (
              <div
                key={outcome}
                className={cn(
                  "rounded-lg px-2 py-2 text-center transition-colors",
                  isActive
                    ? "bg-blue-600 text-white"
                    : "bg-muted text-muted-foreground",
                )}
              >
                <div className="text-sm font-bold tabular-nums">{probs[outcome]}%</div>
                <div className="mt-0.5 text-[10px] font-medium">{OUTCOME_LABELS[outcome]}</div>
              </div>
            );
          })}
        </div>

        {/* Confidence bar */}
        <ConfidenceBar value={confidence} />

        {/* Save button */}
        <div className="flex items-center gap-2 pt-0.5">
          <button
            onClick={handleSave}
            disabled={saving}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors",
              "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground",
              "disabled:cursor-not-allowed disabled:opacity-50",
            )}
          >
            <Save className="h-3 w-3" />
            {saving ? "Saving…" : "Save"}
          </button>
          {saveStatus === "ok" && (
            <span className="flex items-center gap-1 text-[10px] text-green-600 dark:text-green-400">
              <CheckCircle className="h-3 w-3" /> Saved
            </span>
          )}
          {saveStatus === "err" && (
            <span className="flex items-center gap-1 text-[10px] text-red-600 dark:text-red-400">
              <AlertCircle className="h-3 w-3" /> Log in to save
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
