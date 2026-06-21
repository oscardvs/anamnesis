"use client";

import { Search } from "lucide-react";

import { BrandMark } from "@/components/brand-mark";
import { SyncControl } from "@/components/sync-control";
import { ThemeToggle } from "@/components/theme-toggle";
import { Kbd } from "@/components/ui/misc";

export function Topbar({ onOpenCommand }: { onOpenCommand: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-bg/75 px-4 backdrop-blur-xl md:px-6">
      <div className="md:hidden">
        <BrandMark className="size-6" />
      </div>
      <button
        onClick={onOpenCommand}
        className="group flex h-9 max-w-md flex-1 items-center gap-2 rounded-lg bezel bg-surface-2 px-3 text-sm text-faint transition-colors duration-150 hover:bg-elevated hover:text-muted"
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
