import type { Metadata } from "next";
import { Geist, Geist_Mono, Space_Grotesk } from "next/font/google";

import { AppFrame } from "@/components/app-frame";
import { AppToaster } from "@/components/app-toaster";
import { ServiceWorkerRegister } from "@/components/sw-register";
import { ThemeProvider } from "@/components/theme-provider";

import { pwaMetadata } from "./pwa-metadata";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const spaceGrotesk = Space_Grotesk({ variable: "--font-space-grotesk", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Anamnesis",
  description: "Cross-machine memory for Claude Code - a git-like memory GUI.",
  ...pwaMetadata,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} ${spaceGrotesk.variable} h-full antialiased`}
    >
      <body className="grain min-h-full">
        <ServiceWorkerRegister />
        <ThemeProvider>
          <AppFrame>{children}</AppFrame>
          <AppToaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
