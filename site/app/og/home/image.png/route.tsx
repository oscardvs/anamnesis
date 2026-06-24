import { ImageResponse } from 'next/og';
import { generate as DefaultImage } from 'fumadocs-ui/og';
import { appName, tagline } from '@/lib/shared';

export const dynamic = 'force-static';
export const revalidate = false;

export function GET() {
  return new ImageResponse(
    (
      <DefaultImage
        title={tagline}
        description="A file-first memory layer for Claude Code. Markdown you own, synced over your own private network, browsable. Local-first, open-source."
        site={appName}
      />
    ),
    { width: 1200, height: 630 },
  );
}
