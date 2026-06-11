"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { supabase } from "@/lib/supabase";
import PushNotificationToggle from "@/components/PushNotificationToggle";

type UserInfo = { email?: string; avatarUrl?: string };

export default function NavUser() {
  const router = useRouter();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      if (data.user) {
        setUser({
          email: data.user.email,
          avatarUrl: data.user.user_metadata?.avatar_url,
        });
      }
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user) {
        setUser({
          email: session.user.email,
          avatarUrl: session.user.user_metadata?.avatar_url,
        });
      } else {
        setUser(null);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  async function logout() {
    await supabase.auth.signOut();
    setOpen(false);
    router.push("/auth");
  }

  if (!user) {
    return (
      <button
        onClick={() => router.push("/auth")}
        className="flex h-8 items-center rounded-lg border border-border px-3 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        Sign in
      </button>
    );
  }

  const initials = user.email ? user.email[0].toUpperCase() : "U";

  return (
    <div ref={menuRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-blue-600 text-xs font-semibold text-white"
        aria-label="User menu"
        aria-expanded={open}
      >
        {user.avatarUrl ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={user.avatarUrl}
            alt=""
            className="h-full w-full object-cover"
            referrerPolicy="no-referrer"
          />
        ) : (
          initials
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-50 min-w-[176px] rounded-xl border border-border bg-popover shadow-md">
          <p className="truncate border-b border-border px-3 py-2.5 text-xs text-muted-foreground">
            {user.email}
          </p>
          <PushNotificationToggle />
          <button
            onClick={logout}
            className="flex w-full items-center gap-2 px-3 py-2.5 text-sm text-foreground transition-colors hover:bg-muted"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
