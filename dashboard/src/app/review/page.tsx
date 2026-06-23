import { listMeta } from "@/lib/db";
import { ReflectionReview } from "@/components/reflection-review";
import { ReviewPageActions } from "@/components/review-page-actions";
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
        actions={<ReviewPageActions />}
      />
      <ReflectionReview initialNotes={notes} />
    </div>
  );
}
