/**
 * Pure display helpers for the settings form. Kept separate from the React
 * component so the display logic (env-override detection, masked-key label) can
 * be unit-tested in the plain node environment without a DOM.
 */

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
