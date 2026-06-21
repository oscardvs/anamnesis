"use client";

import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Both icons are always rendered; CSS shows the right one based on the `.dark`
 * class (set by next-themes before paint). This avoids a hydration mismatch
 * without a mount-guard effect.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      aria-label="Toggle theme"
    >
      <Sun strokeWidth={1.5} className="hidden dark:block" />
      <Moon strokeWidth={1.5} className="block dark:hidden" />
    </Button>
  );
}
