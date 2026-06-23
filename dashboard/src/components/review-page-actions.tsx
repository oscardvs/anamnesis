"use client";

import { CliPreviewButton } from "@/components/cli-preview-button";

/** Action buttons for the review page header. Client wrapper required to hold function props. */
export function ReviewPageActions() {
  return (
    <>
      <CliPreviewButton label="Reflect all" endpoint="/api/reflect" buildQuery={(a) => (a ? "apply=1" : "")} variant="primary" />
      <CliPreviewButton label="Backfill provenance" endpoint="/api/backfill-provenance" buildQuery={(a) => (a ? "apply=1" : "")} />
    </>
  );
}
