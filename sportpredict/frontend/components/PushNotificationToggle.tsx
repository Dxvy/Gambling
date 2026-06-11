"use client";

import { useEffect, useState } from "react";
import { Bell, BellOff } from "lucide-react";
import { savePushSubscription, deletePushSubscription } from "@/lib/supabase";

const VAPID_PUBLIC_KEY = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY ?? "";

// Web Push application server keys are URL-safe base64 — convert to the
// Uint8Array shape PushManager.subscribe() expects.
function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const output = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) {
    output[i] = rawData.charCodeAt(i);
  }
  return output;
}

export default function PushNotificationToggle() {
  const [supported, setSupported] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!("serviceWorker" in navigator) || !("PushManager" in window) || !VAPID_PUBLIC_KEY) {
      return;
    }
    setSupported(true);

    navigator.serviceWorker.register("/sw.js").then(async (registration) => {
      const sub = await registration.pushManager.getSubscription();
      setSubscribed(!!sub);
    });
  }, []);

  async function toggle() {
    setBusy(true);
    try {
      const registration = await navigator.serviceWorker.ready;

      if (subscribed) {
        const sub = await registration.pushManager.getSubscription();
        if (sub) {
          await deletePushSubscription(sub.endpoint);
          await sub.unsubscribe();
        }
        setSubscribed(false);
        return;
      }

      const permission = await Notification.requestPermission();
      if (permission !== "granted") return;

      const sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      });
      await savePushSubscription(sub.toJSON());
      setSubscribed(true);
    } finally {
      setBusy(false);
    }
  }

  if (!supported) return null;

  return (
    <button
      onClick={toggle}
      disabled={busy}
      className="flex w-full items-center gap-2 px-3 py-2.5 text-sm text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
    >
      {subscribed ? <Bell className="h-3.5 w-3.5" /> : <BellOff className="h-3.5 w-3.5" />}
      {subscribed ? "Notifications on" : "Enable notifications"}
    </button>
  );
}
