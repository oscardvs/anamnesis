import { MachinesView } from "@/components/machines-view";
import { PageHeader } from "@/components/ui/misc";
import { countsByMachine } from "@/lib/db";
import { fleet, repoState } from "@/lib/git";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export default async function MachinesPage() {
  const [machines, repo] = await Promise.all([fleet(countsByMachine()), repoState()]);
  return (
    <div className="animate-rise space-y-6">
      <PageHeader
        eyebrow="fleet"
        title="Machines"
        description="Every machine that has synced into this store, derived from commit authorship, with sync state and conflicts."
      />
      <MachinesView initial={{ machines, repo }} />
    </div>
  );
}
