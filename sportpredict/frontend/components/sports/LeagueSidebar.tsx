"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, X } from "lucide-react";
import { leaguesByCountry } from "@/lib/constants";
import { cn } from "@/lib/utils";

const COUNTRY_FLAGS: Record<string, string> = {
  France:       "🇫🇷",
  England:      "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
  Spain:        "🇪🇸",
  Germany:      "🇩🇪",
  Italy:        "🇮🇹",
  Portugal:     "🇵🇹",
  Netherlands:  "🇳🇱",
  Brazil:       "🇧🇷",
  Europe:       "🏆",
  World:        "🌍",
};

interface LeagueSidebarProps {
  activeLeague: string | null;
  onSelect: (id: string | null) => void;
  isOpen: boolean;
  onClose: () => void;
}

function SidebarContent({
  activeLeague,
  onSelect,
  onClose,
}: {
  activeLeague: string | null;
  onSelect: (id: string | null) => void;
  onClose: () => void;
}) {
  const [expanded, setExpanded] = useState<string[]>(["France", "England"]);

  function toggleCountry(country: string) {
    setExpanded((prev) =>
      prev.includes(country)
        ? prev.filter((c) => c !== country)
        : [...prev, country],
    );
  }

  function selectLeague(id: string | null) {
    onSelect(id);
    onClose();
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Sidebar header */}
      <div className="flex items-center justify-between border-b border-border px-3 py-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Competitions
        </span>
        {/* Close only shown on mobile (via parent) */}
        <button
          onClick={onClose}
          className="lg:hidden flex h-6 w-6 items-center justify-center rounded text-muted-foreground hover:text-foreground"
          aria-label="Close sidebar"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* All leagues shortcut */}
      <div className="border-b border-border px-3 py-2">
        <button
          onClick={() => selectLeague(null)}
          className={cn(
            "w-full rounded-md px-2 py-1.5 text-left text-sm font-medium transition-colors",
            activeLeague === null
              ? "bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400"
              : "text-foreground hover:bg-muted",
          )}
        >
          All Leagues
        </button>
      </div>

      {/* Country / league list */}
      <div className="flex-1 overflow-y-auto py-1">
        {Object.entries(leaguesByCountry).map(([country, leagues]) => {
          const isExpanded = expanded.includes(country);
          return (
            <div key={country}>
              <button
                onClick={() => toggleCountry(country)}
                className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium text-foreground hover:bg-muted/60 transition-colors"
              >
                <span className="flex items-center gap-2">
                  <span>{COUNTRY_FLAGS[country] ?? "🏳️"}</span>
                  <span>{country}</span>
                </span>
                {isExpanded ? (
                  <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                )}
              </button>

              {isExpanded && (
                <ul className="mb-1">
                  {leagues.map((league) => (
                    <li key={league.id}>
                      <button
                        onClick={() => selectLeague(league.id)}
                        className={cn(
                          "w-full text-left px-8 py-1.5 text-sm transition-colors",
                          activeLeague === league.id
                            ? "bg-blue-50 text-blue-600 font-medium dark:bg-blue-900/20 dark:text-blue-400"
                            : "text-muted-foreground hover:text-foreground hover:bg-muted/60",
                        )}
                      >
                        {league.name}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function LeagueSidebar({
  activeLeague,
  onSelect,
  isOpen,
  onClose,
}: LeagueSidebarProps) {
  const content = (
    <SidebarContent
      activeLeague={activeLeague}
      onSelect={onSelect}
      onClose={onClose}
    />
  );

  return (
    <>
      {/* Desktop — always visible, in-flow */}
      <aside className="hidden h-full w-56 shrink-0 overflow-hidden border-r border-border bg-card lg:flex lg:flex-col">
        {content}
      </aside>

      {/* Mobile — slide-in drawer with backdrop */}
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          "fixed inset-0 z-50 lg:hidden transition-opacity duration-200",
          isOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
        )}
      >
        {/* Backdrop */}
        <div
          className="absolute inset-0 bg-black/50"
          onClick={onClose}
        />
        {/* Drawer */}
        <aside
          className={cn(
            "absolute left-0 top-0 h-full w-64 bg-card shadow-xl transition-transform duration-200",
            isOpen ? "translate-x-0" : "-translate-x-full",
          )}
        >
          {content}
        </aside>
      </div>
    </>
  );
}
