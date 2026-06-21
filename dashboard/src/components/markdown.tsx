"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/cn";

/** Render note markdown (GFM) into the Console prose styles. No raw HTML. */
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("anamnesis-prose", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ ...props }) => <a target="_blank" rel="noreferrer noopener" {...props} />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
