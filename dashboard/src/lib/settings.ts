/**
 * Typed wrapper over the `anamnesis config` CLI. Python owns the config.json
 * contract; this never reads or writes the file directly. The raw API key never
 * crosses this boundary (only a masked preview + a "set" flag).
 */
import { runCli } from "./cli";

export interface ReflectionSettings {
  provider: string;
  model: string;
  baseUrl: string;
  timeout: number;
  maxTokens: number;
  apiKeySet: boolean;
  apiKeyPreview: string;
}

export interface Settings {
  machineId: string;
  remote: string;
  reflection: ReflectionSettings;
  /** Dotted keys currently forced by an environment variable (file value ignored). */
  envOverrides: string[];
}

export interface SettingsPatch {
  machineId?: string;
  remote?: string;
  provider?: string;
  model?: string;
  baseUrl?: string;
  timeout?: string;
  maxTokens?: string;
  /** A new key value; omit to leave unchanged. */
  apiKey?: string;
  /** Remove the stored key. */
  clearApiKey?: boolean;
}

type Field = { value: unknown; source: string };

function collectEnvOverrides(view: Record<string, unknown>): string[] {
  const out: string[] = [];
  const top = view as { machine_id: Field; remote: Field; reflection: Record<string, unknown> };
  if (top.machine_id.source === "env") out.push("machine_id");
  if (top.remote.source === "env") out.push("remote");
  const refl = top.reflection as Record<string, Field | string | boolean>;
  for (const k of ["provider", "model", "base_url", "timeout", "max_tokens"]) {
    if ((refl[k] as Field).source === "env") out.push(`reflection.${k}`);
  }
  if ((refl.api_key_source as string) === "env") out.push("reflection.api_key");
  return out;
}

export async function getSettings(): Promise<Settings> {
  const { stdout } = await runCli(["config", "list", "--json"]);
  const view = JSON.parse(stdout) as Record<string, never>;
  const top = view as never as {
    machine_id: Field; remote: Field;
    reflection: {
      provider: Field; model: Field; base_url: Field; timeout: Field; max_tokens: Field;
      api_key_set: boolean; api_key_preview: string;
    };
  };
  const r = top.reflection;
  return {
    machineId: String(top.machine_id.value),
    remote: String(top.remote.value),
    reflection: {
      provider: String(r.provider.value),
      model: String(r.model.value),
      baseUrl: String(r.base_url.value),
      timeout: Number(r.timeout.value),
      maxTokens: Number(r.max_tokens.value),
      apiKeySet: Boolean(r.api_key_set),
      apiKeyPreview: String(r.api_key_preview),
    },
    envOverrides: collectEnvOverrides(view),
  };
}

export async function setSettings(patch: SettingsPatch): Promise<void> {
  const pairs: string[] = [];
  const push = (key: string, value?: string) => {
    if (value !== undefined && value !== "") pairs.push(key, value);
  };
  push("machine_id", patch.machineId);
  push("remote", patch.remote);
  push("reflection.provider", patch.provider);
  push("reflection.model", patch.model);
  push("reflection.base_url", patch.baseUrl);
  push("reflection.timeout", patch.timeout);
  push("reflection.max_tokens", patch.maxTokens);
  push("reflection.api_key", patch.apiKey);
  if (pairs.length > 0) await runCli(["config", "set", ...pairs]);
  if (patch.clearApiKey) await runCli(["config", "unset", "reflection.api_key"]);
}
