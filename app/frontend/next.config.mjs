/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  // Required for static export: disables Next.js image optimization server
  images: { unoptimized: true },
};

export default nextConfig;
