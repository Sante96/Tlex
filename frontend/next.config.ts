import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  reactCompiler: true,
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "image.tmdb.org",
        pathname: "/t/p/**",
      },
    ],
  },
  async rewrites() {
    return {
      // beforeFiles runs before Next.js checks filesystem (including route handlers)
      // afterFiles runs after - this lets route handlers take priority
      beforeFiles: [],
      afterFiles: [
        {
          source: "/api/v1/:path*",
          destination: `${backendUrl}/api/v1/:path*`,
        },
        {
          source: "/docs",
          destination: `${backendUrl}/docs`,
        },
        {
          source: "/openapi.json",
          destination: `${backendUrl}/openapi.json`,
        },
      ],
      fallback: [],
    };
  },
};

export default withNextIntl(nextConfig);
