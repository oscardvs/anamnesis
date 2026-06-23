import { listMeta } from "@/lib/db";
import { CliPreviewButton } from "@/components/cli-preview-button";
import { ReflectionReview } from "@/components/reflection-review";
import { PageHeader } from "@/components/ui/misc";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export default async function ReviewPage() {
  const notes = listMeta({ provSource: "reflection", excludeTag: "reviewed", limit: 300 });
  return (
    <div className="animate-rise space-y-6">
      <PageHeader
        eyebrow="checkpoint"
        title="Review"
        description="LLM-distilled reflection notes await your review. Keep the good ones, delete the rest. Provenance is always preserved."
        actions={
          <>
            <CliPreviewButton label="Reflect all" endpoint="/api/reflect" buildQuery={(a) => (a ? "apply=1" : "")} variant="primary" />
            <CliPreviewButton label="Backfill provenance" endpoint="/api/backfill-provenance" buildQuery={(a) => (a ? "apply=1" : "")} />
          </>
        }
      />
      <ReflectionReview initialNotes={notes} />
    </div>
  );
}
