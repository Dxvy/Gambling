"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu } from "lucide-react";
import { sportsList } from "@/lib/constants";
import LeagueSidebar from "@/components/sports/LeagueSidebar";
import MatchList from "@/components/sports/MatchList";
import { ThemeToggle } from "@/components/ThemeToggle";
import NavUser from "@/components/NavUser";
import { cn } from "@/lib/utils";

export default function SportsPage() {
  const [activeSport, setActiveSport] = useState("football");
  const [activeLeague, setActiveLeague] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      {/* ── Fixed top shell ── */}
      <header className="z-30 shrink-0 border-b border-border bg-background">
        {/* Navbar */}
        <div className="flex h-14 items-center justify-between px-4">
          <div className="flex items-center gap-3">
            {/* Hamburger — mobile only */}
            <button
              className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted lg:hidden"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </button>
            <Link href="/" className="text-lg font-bold text-foreground tracking-tight">
              SportPredict
            </Link>
          </div>

          {/* Desktop nav links */}
          <nav className="hidden items-center gap-6 text-sm md:flex">
            <Link
              href="/sports"
              className="font-medium text-foreground"
            >
              Sports
            </Link>
            <Link
              href="/lottery"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              Lottery
            </Link>
            <Link
              href="/dashboard"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              Dashboard
            </Link>
          </nav>

          <div className="flex items-center gap-2">
            <NavUser />
            <ThemeToggle />
          </div>
        </div>

        {/* Sport icon bar — horizontally scrollable on mobile */}
        <div
          className="flex gap-1 overflow-x-auto px-3 pb-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          {sportsList.map((sport) => (
            <button
              key={sport.id}
              onClick={() => setActiveSport(sport.id)}
              className={cn(
                "flex shrink-0 flex-col items-center rounded-xl px-4 py-2 transition-colors",
                activeSport === sport.id
                  ? "bg-blue-600 text-white"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <span className="text-xl leading-none">{sport.icon}</span>
              <span className="mt-1 text-xs font-medium">{sport.label}</span>
            </button>
          ))}
        </div>
      </header>

      {/* ── Main content area ── */}
      <div className="flex min-h-0 flex-1">
        <LeagueSidebar
          activeLeague={activeLeague}
          onSelect={setActiveLeague}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        <main className="min-w-0 flex-1 overflow-y-auto">
          {/* Section heading */}
          <div className="border-b border-border px-4 py-3">
            <h1 className="text-sm font-semibold text-foreground">
              {activeSport.charAt(0).toUpperCase() + activeSport.slice(1)} Predictions
            </h1>
            {activeLeague !== null && (
              <button
                onClick={() => setActiveLeague(null)}
                className="mt-0.5 text-xs text-blue-600 hover:underline dark:text-blue-400"
              >
                ← All leagues
              </button>
            )}
          </div>

          <MatchList sport={activeSport} leagueId={activeLeague} />
        </main>
      </div>
    </div>
  );
}
