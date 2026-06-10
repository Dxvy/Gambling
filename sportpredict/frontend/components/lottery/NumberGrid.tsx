"use client";

import { cn } from "@/lib/utils";

// Map column count → Tailwind grid class.
// Listed explicitly so Tailwind's scanner can detect and include them.
const COLS_CLASS: Record<number, string> = {
  6:  "grid-cols-6",
  7:  "grid-cols-7",
  10: "grid-cols-10",
};

interface NumberGridProps {
  maxNumber:       number;
  cols:            number;
  hotSet:          ReadonlySet<number>;
  coldSet:         ReadonlySet<number>;
  selectedSet:     ReadonlySet<number>;
}

function cellClass(
  n:           number,
  hotSet:      ReadonlySet<number>,
  coldSet:     ReadonlySet<number>,
  selectedSet: ReadonlySet<number>,
): string {
  if (selectedSet.has(n)) {
    // Selected numbers pop out in blue, regardless of their hot/cold status
    return "bg-blue-600 text-white shadow-md shadow-blue-500/25 scale-110 z-10 ring-2 ring-blue-400/60";
  }
  if (hotSet.has(n)) {
    return "bg-green-500/20 text-green-700 dark:bg-green-500/25 dark:text-green-300 font-semibold";
  }
  if (coldSet.has(n)) {
    return "bg-red-500/15 text-red-700 dark:bg-red-500/20 dark:text-red-400";
  }
  return "bg-muted/70 text-muted-foreground hover:bg-muted";
}

export default function NumberGrid({
  maxNumber,
  cols,
  hotSet,
  coldSet,
  selectedSet,
}: NumberGridProps) {
  const gridClass = COLS_CLASS[cols] ?? "grid-cols-7";

  return (
    <div className={cn("grid gap-1", gridClass)}>
      {Array.from({ length: maxNumber }, (_, i) => i + 1).map((n) => (
        <div
          key={n}
          className={cn(
            // Base: square, circular, transition for highlight state changes
            "relative flex aspect-square items-center justify-center",
            "rounded-full text-xs font-medium transition-all duration-200",
            cellClass(n, hotSet, coldSet, selectedSet),
          )}
        >
          {n}
        </div>
      ))}
    </div>
  );
}
