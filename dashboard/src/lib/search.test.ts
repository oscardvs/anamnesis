import { describe, expect, it } from "vitest";

import { buildMatch } from "./db";

describe("buildMatch (FTS5 MATCH builder)", () => {
  it("quotes and ANDs word tokens", () => {
    expect(buildMatch("libsql embedded")).toBe('"libsql" AND "embedded"');
  });

  it("neutralizes FTS5 operators and punctuation", () => {
    // Mirrors the Python _fts_query: every operator becomes inert literal text.
    expect(buildMatch("OR* weird:colon")).toBe('"OR" AND "weird" AND "colon"');
    expect(buildMatch('a "b" -c')).toBe('"a" AND "b" AND "c"');
  });

  it("returns empty string when there are no word tokens", () => {
    expect(buildMatch("   -:* ")).toBe("");
    expect(buildMatch("")).toBe("");
  });

  it("keeps unicode word characters", () => {
    expect(buildMatch("café déjà")).toBe('"café" AND "déjà"');
  });
});
