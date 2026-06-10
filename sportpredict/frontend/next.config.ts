import type { NextConfig } from "next";

// NEXT_STATIC_EXPORT=1  →  fully-static `out/` folder for Capacitor / Android.
// All other builds (Vercel, local dev) use the default Next.js server so that
// proxy.ts, API route handlers, and SSR continue to work.
const isStaticExport = process.env.NEXT_STATIC_EXPORT === "1";

const nextConfig: NextConfig = {
  ...(isStaticExport && {
    output: "export",
    images: { unoptimized: true },
  }),
};

export default nextConfig;
