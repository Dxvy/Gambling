"use client";

import { useMemo } from "react";
import MatchCard from "@/components/sports/MatchCard";
import { Skeleton } from "@/components/ui/skeleton";
import { mockMatches } from "@/lib/mock-data";

interface MatchListProps {
  sport: string;
  leagueId: string | null;
}

function MatchCardSkeleton() {
  return (
    <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4 space-y-3">
      <div className="flex justify-between">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-20" />
      </div>
      <div className="grid grid-cols-3 gap-2 items-center">
        <div className="space-y-1.5 flex flex-col items-center">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-2 w-16" />
        </div>
        <Skeleton className="h-3 w-6 mx-auto" />
        <div className="space-y-1.5 flex flex-col items-center">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-2 w-16" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        <Skeleton className="h-12 rounded-lg" />
        <Skeleton className="h-12 rounded-lg" />
        <Skeleton className="h-12 rounded-lg" />
      </div>
      <Skeleton className="h-3 w-full" />
    </div>
  );
}

export default function MatchList({ sport, leagueId }: MatchListProps) {
  const matches = useMemo(() => {
    // Football is the only sport with mock data; other sports show empty state
    if (sport !== "football") return [];
    if (leagueId !== null) {
      return mockMatches.filter((m) => m.leagueId === leagueId);
    }
    return mockMatches;
  }, [sport, leagueId]);

  if (sport !== "football") {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2 text-muted-foreground">
        <span className="text-3xl">🚧</span>
        <p className="text-sm">
          {sport.charAt(0).toUpperCase() + sport.slice(1)} predictions coming soon.
        </p>
      </div>
    );
  }

  if (matches.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2 text-muted-foreground">
        <span className="text-3xl">📭</span>
        <p className="text-sm">No upcoming matches for this league.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 xl:grid-cols-3">
      {matches.map((match) => (
        <MatchCard key={match.id} {...match} />
      ))}
    </div>
  );
}
