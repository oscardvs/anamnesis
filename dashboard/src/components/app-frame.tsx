"use client";

import { useEffect, useState } from "react";

import { CommandMenu } from "@/components/command-menu";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

export function AppFrame({ children }: { children: React.ReactNode }) {
  const [cmdOpen, setCmdOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex min-h-[100dvh]">
      <Sidebar />
      <div className="relative z-[2] flex min-w-0 flex-1 flex-col">
        <Topbar onOpenCommand={() => setCmdOpen(true)} />
        <main className="flex-1 px-4 py-6 md:px-8 md:py-9">
          <div className="mx-auto w-full max-w-[1180px]">{children}</div>
        </main>
      </div>
      <CommandMenu open={cmdOpen} onOpenChange={setCmdOpen} />
    </div>
  );
}
