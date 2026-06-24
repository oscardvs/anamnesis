"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

/** Class-based theming; light is the default recollection look, dark is a toggle. */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
