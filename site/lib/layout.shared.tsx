import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';
import { repoUrl } from './shared';
import { Wordmark } from '@/components/wordmark';

export function baseOptions(): BaseLayoutProps {
  return {
    nav: {
      title: <Wordmark />,
      transparentMode: 'top',
    },
    links: [
      { text: 'Docs', url: '/docs' },
      { text: 'Why Anamnesis', url: '/#why' },
    ],
    githubUrl: repoUrl,
  };
}
