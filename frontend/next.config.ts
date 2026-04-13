import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  // ส่ง env vars ไปยัง Python subprocess ได้ผ่าน process.env
  env: {
    GEMINI_API_KEY: process.env.GEMINI_API_KEY ?? "",
    NEWS_API_KEY:   process.env.NEWS_API_KEY   ?? "",
  },
};

export default nextConfig;
