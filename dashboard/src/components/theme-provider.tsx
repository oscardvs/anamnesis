"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

/** Class-based theming; dark is the default Console look, light is a toggle. */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
