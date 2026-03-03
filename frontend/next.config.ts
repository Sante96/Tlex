import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

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
          destination: "http://backend:8000/api/v1/:path*",
        },
        {
          source: "/docs",
          destination: "http://backend:8000/docs",
        },
        {
          source: "/openapi.json",
          destination: "http://backend:8000/openapi.json",
        },
      ],
      fallback: [],
    };
  },
};

export default withNextIntl(nextConfig);
