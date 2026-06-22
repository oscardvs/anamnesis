import { describe, expect, it } from "vitest";

import manifest from "./manifest";

describe("web app manifest", () => {
  it("is installable: standalone display, start url, and named", () => {
    const m = manifest();
    expect(m.name).toBe("Anamnesis");
    expect(m.short_name).toBe("Anamnesis");
    expect(m.display).toBe("standalone");
    expect(m.start_url).toBe("/");
  });

  it("declares 192, 512, and a maskable icon", () => {
    const icons = manifest().icons ?? [];
    const sizes = icons.map((i) => i.sizes);
    expect(sizes).toContain("192x192");
    expect(sizes).toContain("512x512");
    expect(icons.some((i) => i.purpose === "maskable")).toBe(true);
  });
});
