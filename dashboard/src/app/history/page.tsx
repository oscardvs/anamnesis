import { HistoryExplorer } from "@/components/history-explorer";
import { PageHeader } from "@/components/ui/misc";
import { globalHistory } from "@/lib/git";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export default async function HistoryPage() {
  const commits = await globalHistory(200);
  return (
    <div className="animate-rise space-y-6">
      <PageHeader
        eyebrow="timeline"
        title="History"
        description="Every sync commit across the fleet, newest first. Select a commit to see the notes it changed."
      />
      <HistoryExplorer commits={commits} />
    </div>
  );
}
