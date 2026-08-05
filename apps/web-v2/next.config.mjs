/** @type {import('next').NextConfig} */
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
        destination: "http://localhost:8000/:path*",
      },
    ];
  },
};

export default nextConfig;
