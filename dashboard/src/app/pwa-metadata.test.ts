import { describe, expect, it } from "vitest";

import { pwaMetadata } from "./pwa-metadata";

describe("pwaMetadata", () => {
  it("links the manifest and enables iOS standalone", () => {
    expect(pwaMetadata.manifest).toBe("/manifest.webmanifest");
    expect(pwaMetadata.appleWebApp).toMatchObject({ capable: true, title: "Anamnesis" });
  });

  it("declares an apple-touch-icon", () => {
    expect(JSON.stringify(pwaMetadata.icons)).toContain("/icons/apple-touch-icon.png");
  });
});
