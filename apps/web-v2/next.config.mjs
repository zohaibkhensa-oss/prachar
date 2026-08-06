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
  // Video generation via Modal can take 90-180s (cold start).
  // Default proxy timeout is 30s which is too short.
  experimental: {
    proxyTimeout: 300_000, // 5 minutes
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
