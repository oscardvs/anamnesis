import { createMDX } from 'fumadocs-mdx/next';

const withMDX = createMDX();
const basePath = process.env.PAGES_BASE_PATH ?? '/anamnesis';

/** @type {import('next').NextConfig} */
const config = {
  reactStrictMode: true,
  output: 'export',
  trailingSlash: true,
  images: { unoptimized: true },
  basePath,
  assetPrefix: basePath || undefined,
};

export default withMDX(config);
