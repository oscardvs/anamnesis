/**
 * Pure display helpers for the settings form. Kept separate from the React
 * component so the display logic (env-override detection, masked-key label,
 * patch construction) can be unit-tested in the plain node environment without
 * a DOM.
 */
import type { SettingsPatch } from "@/lib/settings";

/** Shown next to any field whose value is currently forced by an env var. */
export const OVERRIDE_BADGE = "set by environment (file value ignored)";

/** True when the given dotted key is one of the env-shadowed settings. */
export function isOverridden(envOverrides: string[], dottedKey: string): boolean {
  return envOverrides.includes(dottedKey);
}

/** The text to show for the masked api-key field (never the raw key). */
export function maskedKeyLabel(key: { apiKeySet: boolean; apiKeyPreview: string }): string {
  if (!key.apiKeySet) return "not set";
  return key.apiKeyPreview || "set";
}

/** The form's current field values, plus the api-key intent. */
export interface SettingsFormValues {
  machineId: string;
  remote: string;
  provider: string;
  model: string;
  baseUrl: string;
  timeout: string;
  maxTokens: string;
  /** True when the user is replacing the stored key with `apiKey`. */
  replacingKey: boolean;
  /** The new key value, only meaningful when `replacingKey` is true. */
  apiKey: string;
  /** True when the user chose to clear the stored key. */
  clearKey: boolean;
}

/**
 * Build the patch to POST from the form's current values. Any field whose
 * dotted key is in `envOverrides` is excluded: the environment is forcing that
 * value, so we must not write it back into config.json and pin the file value.
 */
export function buildPatch(form: SettingsFormValues, envOverrides: string[]): SettingsPatch {
  const allow = (dottedKey: string) => !isOverridden(envOverrides, dottedKey);
  const patch: SettingsPatch = {};

  if (allow("machine_id")) patch.machineId = form.machineId;
  if (allow("remote")) patch.remote = form.remote;
  if (allow("reflection.provider")) patch.provider = form.provider;
  if (allow("reflection.model")) patch.model = form.model;
  if (allow("reflection.base_url")) patch.baseUrl = form.baseUrl;
  if (allow("reflection.timeout")) patch.timeout = form.timeout;
  if (allow("reflection.max_tokens")) patch.maxTokens = form.maxTokens;

  if (allow("reflection.api_key")) {
    if (form.clearKey) patch.clearApiKey = true;
    else if (form.replacingKey && form.apiKey) patch.apiKey = form.apiKey;
  }

  return patch;
}
