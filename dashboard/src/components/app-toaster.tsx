"use client";

import { useTheme } from "next-themes";
import { Toaster } from "sonner";

/** Sonner toaster wired to the active theme and styled to the Console palette. */
export function AppToaster() {
  const { resolvedTheme } = useTheme();
  return (
    <Toaster
      position="bottom-right"
      theme={(resolvedTheme as "dark" | "light") ?? "dark"}
      toastOptions={{
        classNames: {
          toast: "bezel !bg-elevated !text-text !rounded-xl",
          description: "!text-muted",
        },
      }}
    />
  );
}
