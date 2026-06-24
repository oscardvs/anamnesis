import { RootProvider } from 'fumadocs-ui/provider/next';
import './global.css';
import { Geist, Geist_Mono, Space_Grotesk } from 'next/font/google';
import StaticSearchDialog from '@/components/search-dialog';
import type { Metadata } from 'next';
import { appName, tagline } from '@/lib/shared';

export const metadata: Metadata = {
  title: {
    default: `${appName}: ${tagline}`,
    template: `%s · ${appName}`,
  },
  description: tagline,
  applicationName: appName,
  authors: [{ name: 'Oscar Devos' }],
  openGraph: {
    type: 'website',
    siteName: appName,
    title: `${appName}: ${tagline}`,
    description: tagline,
    images: [{ url: '/og/home/image.png', width: 1200, height: 630, alt: appName }],
  },
  twitter: {
    card: 'summary_large_image',
    title: `${appName}: ${tagline}`,
    description: tagline,
    images: ['/og/home/image.png'],
  },
};

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
  display: 'swap',
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
  display: 'swap',
});

const spaceGrotesk = Space_Grotesk({
  variable: '--font-space-grotesk',
  subsets: ['latin'],
  display: 'swap',
});

export default function Layout({ children }: LayoutProps<'/'>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${spaceGrotesk.variable}`}
      suppressHydrationWarning
    >
      <body className="flex flex-col min-h-screen">
        {/* Mark JS as available before paint so reveal content is visible
            without JS (crawlers/no-JS) and only hidden-then-revealed with it. */}
        <script
          dangerouslySetInnerHTML={{
            __html: "document.documentElement.classList.add('js')",
          }}
        />
        <RootProvider search={{ SearchDialog: StaticSearchDialog }}>
          {children}
        </RootProvider>
      </body>
    </html>
  );
}
