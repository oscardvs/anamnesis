"use client";

import { Menu, Search } from "lucide-react";

import { BrandMark } from "@/components/brand-mark";
import { SyncControl } from "@/components/sync-control";
import { ThemeToggle } from "@/components/theme-toggle";
import { Kbd } from "@/components/ui/misc";

export function Topbar({
  onOpenCommand,
  onOpenNav,
}: {
  onOpenCommand: () => void;
  onOpenNav: () => void;
}) {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-bg/75 px-4 backdrop-blur-xl md:px-6">
      <button
        onClick={onOpenNav}
        aria-label="Open menu"
        className="tap flex size-9 items-center justify-center rounded-lg text-muted hover:bg-highlight hover:text-text md:hidden"
      >
        <Menu size={18} strokeWidth={1.7} />
      </button>
      <div className="md:hidden">
        <BrandMark className="size-6" />
      </div>
      <button
        onClick={onOpenCommand}
        className="group flex h-9 max-w-md flex-1 items-center gap-2 rounded-xl border border-line bg-surface-2 px-3 text-sm text-faint transition-[border-color,box-shadow,background-color] duration-150 hover:border-accent hover:bg-elevated hover:text-muted hover:shadow-[0_0_0_3px_var(--accent-tint)]"
      >
        <Search size={15} strokeWidth={1.5} />
        <span className="flex-1 text-left">Search memory...</span>
        <Kbd>⌘K</Kbd>
      </button>
      <div className="flex items-center gap-1.5">
        <SyncControl />
        <ThemeToggle />
      </div>
    </header>
  );
}
