"use client";

import { useState } from "react";

import { Lock, Plug, RotateCcw, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";
import { Panel, Spinner } from "@/components/ui/misc";
import { cn } from "@/lib/cn";
import type { Settings } from "@/lib/settings";

import { buildPatch, isOverridden, maskedKeyLabel, OVERRIDE_BADGE } from "./helpers";

const inputClass =
  "h-9 w-full rounded-lg bezel bg-surface-2 px-3 text-sm text-text outline-none transition-colors placeholder:text-faint focus-visible:ring-2 focus-visible:ring-accent/50 disabled:opacity-60";

const labelClass = "mb-1.5 block text-[11px] font-medium uppercase tracking-[0.12em] text-faint";

const PROVIDERS = ["heuristic", "deepseek", "openai", "local"];

/** A labelled field that shows the env-override badge and disables itself when shadowed. */
function Field({
  label,
  dottedKey,
  overrides,
  children,
}: {
  label: string;
  dottedKey: string;
  overrides: string[];
  children: (overridden: boolean) => React.ReactNode;
}) {
  const overridden = isOverridden(overrides, dottedKey);
  return (
    <div>
      <div className="flex items-center justify-between">
        <label className={labelClass}>{label}</label>
        {overridden && (
          <Badge tone="warn" className="mb-1.5">
            <Lock size={11} strokeWidth={1.8} />
            {OVERRIDE_BADGE}
          </Badge>
        )}
      </div>
      {children(overridden)}
    </div>
  );
}

export function SettingsForm({ initial }: { initial: Settings }) {
  const r = initial.reflection;
  const o = initial.envOverrides;

  const [machineId, setMachineId] = useState(initial.machineId);
  const [remote, setRemote] = useState(initial.remote);
  const [provider, setProvider] = useState(r.provider);
  const [model, setModel] = useState(r.model);
  const [baseUrl, setBaseUrl] = useState(r.baseUrl);
  const [timeout, setTimeout] = useState(String(r.timeout));
  const [maxTokens, setMaxTokens] = useState(String(r.maxTokens));

  // The api key is write-only: we show the masked preview, and only collect a
  // new value when the user chooses to replace it. A blank field on Save leaves
  // the stored key unchanged.
  const [replacingKey, setReplacingKey] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);

  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const keyOverridden = isOverridden(o, "reflection.api_key");

  const onSave = async () => {
    setSaving(true);
    try {
      const patch = buildPatch(
        {
          machineId,
          remote,
          provider,
          model,
          baseUrl,
          timeout,
          maxTokens,
          replacingKey,
          apiKey,
          clearKey: clearApiKey,
        },
        o,
      );

      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { error?: string };
        toast.error("Could not save settings", {
          description: data.error || "The anamnesis CLI rejected the change.",
        });
        return;
      }
      // Reset the key controls to the saved state.
      setReplacingKey(false);
      setApiKey("");
      setClearApiKey(false);
      toast.success("Settings saved", { description: "Stored in ~/.anamnesis/config.json." });
    } catch {
      toast.error("Could not save settings", { description: "Could not reach the anamnesis CLI." });
    } finally {
      setSaving(false);
    }
  };

  const onTest = async () => {
    setTesting(true);
    try {
      const res = await fetch("/api/settings/test", { method: "POST" });
      const out = (await res.json()) as { ok: boolean; message: string };
      if (out.ok) toast.success("Connection ok", { description: out.message });
      else toast.error("Connection failed", { description: out.message || "see the CLI output" });
    } catch {
      toast.error("Test failed", { description: "Could not reach the anamnesis CLI." });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <Panel className="space-y-5 p-5 sm:p-6">
        <h2 className="font-display text-sm font-semibold tracking-tight text-text">Reflection</h2>

        <Field label="Provider" dottedKey="reflection.provider" overrides={o}>
          {(overridden) => (
            <select
              value={provider}
              disabled={overridden}
              onChange={(e) => setProvider(e.target.value)}
              className={inputClass}
            >
              {[...new Set([provider, ...PROVIDERS])].map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          )}
        </Field>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Field label="Model" dottedKey="reflection.model" overrides={o}>
            {(overridden) => (
              <input
                value={model}
                disabled={overridden}
                onChange={(e) => setModel(e.target.value)}
                className={inputClass}
                placeholder="deepseek-chat"
              />
            )}
          </Field>
          <Field label="Base URL" dottedKey="reflection.base_url" overrides={o}>
            {(overridden) => (
              <input
                value={baseUrl}
                disabled={overridden}
                onChange={(e) => setBaseUrl(e.target.value)}
                className={inputClass}
                placeholder="https://api.deepseek.com"
              />
            )}
          </Field>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Field label="Timeout (s)" dottedKey="reflection.timeout" overrides={o}>
            {(overridden) => (
              <input
                value={timeout}
                disabled={overridden}
                onChange={(e) => setTimeout(e.target.value)}
                className={inputClass}
                inputMode="numeric"
              />
            )}
          </Field>
          <Field label="Max tokens" dottedKey="reflection.max_tokens" overrides={o}>
            {(overridden) => (
              <input
                value={maxTokens}
                disabled={overridden}
                onChange={(e) => setMaxTokens(e.target.value)}
                className={inputClass}
                inputMode="numeric"
              />
            )}
          </Field>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <label className={labelClass}>API key</label>
            {keyOverridden && (
              <Badge tone="warn" className="mb-1.5">
                <Lock size={11} strokeWidth={1.8} />
                {OVERRIDE_BADGE}
              </Badge>
            )}
          </div>
          {keyOverridden ? (
            <p className="font-mono text-sm text-muted">{maskedKeyLabel(r)}</p>
          ) : clearApiKey ? (
            <div className="flex items-center gap-3">
              <span className="text-sm text-danger">will be cleared on save</span>
              <Button variant="ghost" size="sm" onClick={() => setClearApiKey(false)}>
                <RotateCcw strokeWidth={1.6} /> Keep
              </Button>
            </div>
          ) : replacingKey ? (
            <div className="flex items-center gap-2">
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className={inputClass}
                placeholder="paste new key"
                autoComplete="off"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setReplacingKey(false);
                  setApiKey("");
                }}
              >
                <RotateCcw strokeWidth={1.6} /> Cancel
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <span className="font-mono text-sm text-muted">{maskedKeyLabel(r)}</span>
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="sm" onClick={() => setReplacingKey(true)}>
                  Replace
                </Button>
                {r.apiKeySet && (
                  <Button variant="danger" size="sm" onClick={() => setClearApiKey(true)}>
                    <Trash2 strokeWidth={1.6} /> Clear
                  </Button>
                )}
              </div>
            </div>
          )}
          <p className="mt-1.5 text-xs text-faint">
            The key is write-only here. It is stored locally and never sent to the dashboard.
          </p>
        </div>
      </Panel>

      <Panel className="space-y-5 p-5 sm:p-6">
        <h2 className="font-display text-sm font-semibold tracking-tight text-text">Store</h2>
        <Field label="Machine ID" dottedKey="machine_id" overrides={o}>
          {(overridden) => (
            <input
              value={machineId}
              disabled={overridden}
              onChange={(e) => setMachineId(e.target.value)}
              className={inputClass}
            />
          )}
        </Field>
        <Field label="Remote" dottedKey="remote" overrides={o}>
          {(overridden) => (
            <input
              value={remote}
              disabled={overridden}
              onChange={(e) => setRemote(e.target.value)}
              className={cn(inputClass, "font-mono text-xs")}
            />
          )}
        </Field>
      </Panel>

      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button variant="outline" onClick={onTest} disabled={testing}>
          {testing ? <Spinner /> : <Plug strokeWidth={1.6} />} Test connection
        </Button>
        <Button variant="primary" onClick={onSave} disabled={saving}>
          {saving ? <Spinner /> : <Save strokeWidth={1.6} />} Save
        </Button>
      </div>
    </div>
  );
}
