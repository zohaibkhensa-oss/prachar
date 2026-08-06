/** @type {import('next').NextConfig} */
// Support both API_URL (full URL) and API_HOST (Render service linking)
const apiUrl = process.env.API_URL || (process.env.API_HOST ? `https://${process.env.API_HOST}` : "http://localhost:8000");

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
