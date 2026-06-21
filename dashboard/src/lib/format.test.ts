import { describe, expect, it } from "vitest";

import { relativeTime, shortProject } from "./format";

const now = Date.parse("2026-06-18T12:00:00+00:00");

describe("relativeTime", () => {
  it("renders sub-minute as just now", () => {
    expect(relativeTime("2026-06-18T11:59:40+00:00", now)).toBe("just now");
  });
  it("renders hours and days", () => {
    expect(relativeTime("2026-06-18T09:00:00+00:00", now)).toBe("3h ago");
    expect(relativeTime("2026-06-15T12:00:00+00:00", now)).toBe("3d ago");
  });
  it("handles null and junk input", () => {
    expect(relativeTime(null, now)).toBe("unknown");
    expect(relativeTime("nonsense", now)).toBe("unknown");
  });
});

describe("shortProject", () => {
  it("drops the github host prefix", () => {
    expect(shortProject("github.com/oscardvs/anamnesis")).toBe("oscardvs/anamnesis");
  });
  it("leaves bare keys untouched", () => {
    expect(shortProject("ros2_ws")).toBe("ros2_ws");
  });
});
