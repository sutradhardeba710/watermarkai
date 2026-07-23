/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  images: {
    formats: ['image/avif', 'image/webp'],
    minimumCacheTTL: 86400,
  },
  // Isolate production output so next build cannot corrupt a running dev server.
  distDir: process.env.NODE_ENV === "production" ? ".next-build" : ".next",
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // Required by GIS for HTTP localhost development.
          { key: "Referrer-Policy", value: "no-referrer-when-downgrade" },
          // Preserve popup communication when the browser is not using FedCM.
          { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
        ],
      },
    ];
  },
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      { source: "/api/:path*", destination: `${api}/api/:path*` },
      { source: "/health/:path*", destination: `${api}/health/:path*` },
    ];
  },
};

module.exports = nextConfig;
