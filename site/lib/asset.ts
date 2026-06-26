// site/lib/asset.ts
// Static-export public assets are served under the site basePath (/anamnesis on
// GitHub Pages). next/image and Link auto-prefix, but a plain <img src> / <video
// src> does not, so prefix public asset paths with this helper. Evaluated at
// build/render time in server components, matching next.config.mjs.
const basePath = process.env.PAGES_BASE_PATH ?? '/anamnesis';

export function asset(path: string): string {
  const clean = path.startsWith('/') ? path : `/${path}`;
  return `${basePath}${clean}`;
}
