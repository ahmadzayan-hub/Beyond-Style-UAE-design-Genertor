/** @type {import('next').NextConfig} */
// LOCAL DEV / E2E CONVENIENCE ONLY. Production (Vercel) does NOT use
// this rewrite: lib/api.ts fetches the backend directly at
// NEXT_PUBLIC_API_URL (CORS, not a server-side proxy) — see
// docs/DEPLOYMENT.md. When NEXT_PUBLIC_API_URL is unset (local dev),
// lib/api.ts falls back to relative "/api/..." paths, which this
// rewrite then proxies to BACKEND_URL (default http://localhost:8000).
// The published production backend (Replit Deployment). Not a secret:
// NEXT_PUBLIC_* values are baked into client JS by design. A Vercel
// build uses this as the default backend origin so the site works even
// when the dashboard env var is not set; an explicit NEXT_PUBLIC_API_URL
// always wins, and local dev (no VERCEL) keeps the empty base + rewrite.
const PRODUCTION_BACKEND = "https://beyond-style-uae-design-genertor.replit.app";

const nextConfig = {
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL ||
      (process.env.VERCEL ? PRODUCTION_BACKEND : ""),
  },
  async rewrites() {
    // Never bake the localhost rewrite into a Vercel build: production must
    // use NEXT_PUBLIC_API_URL (direct browser→backend fetch). With the
    // rewrite baked, /api/* proxied to localhost and Vercel returned
    // DNS_HOSTNAME_RESOLVED_PRIVATE 404s that masqueraded as app errors.
    if (process.env.VERCEL && !process.env.BACKEND_URL) return [];
    const backend = process.env.BACKEND_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
