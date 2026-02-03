import type { NextConfig } from "next";

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
    return [
      {
        source: "/api/:path*",
        destination: "http://backend:8000/api/:path*",
      },
      {
        source: "/docs",
        destination: "http://backend:8000/docs",
      },
      {
        source: "/openapi.json",
        destination: "http://backend:8000/openapi.json",
      },
    ];
  },
};

export default nextConfig;
