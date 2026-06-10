"use client";

import { cn } from "@/lib/utils";

interface SelectedBallsProps {
  numbers:      number[];
  bonus:        number[];
  /** How many balls have been revealed so far (increments over time for animation). */
  revealedCount: number;
  lotteryLabel:  string;
}

function Ball({
  value,
  variant,
  revealed,
  delay,
}: {
  value:    number;
  variant:  "main" | "bonus";
  revealed: boolean;
  delay:    number;
}) {
  return (
    <div
      className={cn(
        // Base size and shape
        "flex h-12 w-12 items-center justify-center rounded-full",
        "text-sm font-bold shadow-lg select-none",
        // Colour
        variant === "main"
          ? "bg-blue-600 text-white shadow-blue-500/30"
          : "bg-amber-400 text-amber-900 shadow-amber-400/40",
        // Appear animation driven by `revealed` flag
        "transition-all duration-300",
        revealed ? "opacity-100 scale-100" : "opacity-0 scale-50",
      )}
      // CSS custom property for potential future stagger via @keyframes
      style={{ transitionDelay: revealed ? `${delay}ms` : "0ms" }}
      aria-label={`${variant === "bonus" ? "Bonus " : ""}${value}`}
    >
      {value}
    </div>
  );
}

export default function SelectedBalls({
  numbers,
  bonus,
  revealedCount,
  lotteryLabel,
}: SelectedBallsProps) {
  if (numbers.length === 0) return null;

  return (
    <div className="space-y-3">
      {/* Main numbers */}
      <div className="flex flex-wrap items-center gap-2">
        {numbers.map((n, idx) => (
          <Ball
            key={n}
            value={n}
            variant="main"
            revealed={idx < revealedCount}
            delay={0}  // delay is handled by staggered state updates
          />
        ))}

        {/* Bonus numbers — only shown after all main numbers are revealed */}
        {bonus.length > 0 && revealedCount >= numbers.length && (
          <>
            <span className="text-xs font-medium text-muted-foreground px-1">+</span>
            {bonus.map((b, idx) => (
              <Ball
                key={`bonus-${b}`}
                value={b}
                variant="bonus"
                revealed
                delay={idx * 100}
              />
            ))}
          </>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded-full bg-blue-600" />
          {lotteryLabel} main
        </span>
        {bonus.length > 0 && (
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-full bg-amber-400" />
            Bonus
          </span>
        )}
      </div>
    </div>
  );
}
