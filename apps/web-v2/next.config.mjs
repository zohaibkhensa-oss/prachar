/** @type {import('next').NextConfig} */
// API URL for proxying /api requests.
// Priority: API_URL env > NEXT_PUBLIC_API_BASE env > NEXT_PUBLIC_API_BASE build arg > localhost
const apiUrl =
  process.env.API_URL ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  typedRoutes: false,
  // Video generation can take up to 5 min for 60s videos (multi-clip stitch).
  // SSE stream must stay alive for the full duration.
  experimental: {
    proxyTimeout: 30 * 60 * 1000, // 30 minutes
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
