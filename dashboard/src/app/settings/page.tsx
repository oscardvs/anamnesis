import { getSettings, type Settings } from "@/lib/settings";
import { PageHeader } from "@/components/ui/misc";

import { SettingsForm } from "./settings-form";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export default async function SettingsPage() {
  const initial: Settings = await getSettings();
  return (
    <div className="animate-rise space-y-6">
      <PageHeader
        eyebrow="machine-local"
        title="Settings"
        description="Reflection provider and store identity. Stored locally in ~/.anamnesis/config.json (never synced). Environment variables, when set, override these values."
      />
      <SettingsForm initial={initial} />
    </div>
  );
}
