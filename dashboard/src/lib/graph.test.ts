import { describe, expect, it } from "vitest";

import { buildGraph } from "./graph";

describe("buildGraph", () => {
  it("creates a hub per project and links notes to their hub", () => {
    const notes = [
      { id: "a1", type: "semantic", project: "p1", title: "A", body: "see [[b2]]" },
      { id: "b2", type: "procedural", project: "p1", title: "B", body: "no links" },
      { id: "c3", type: "episodic", project: "p2", title: "C", body: "" },
    ];
    const g = buildGraph(notes);

    const hubs = g.nodes.filter((n) => n.kind === "hub");
    expect(hubs.map((h) => h.project).sort()).toEqual(["p1", "p2"]);

    // every note is connected to its project hub
    const hubP1 = hubs.find((h) => h.project === "p1")!.id;
    expect(g.edges).toContainEqual([hubP1, "a1"]);
    expect(g.edges).toContainEqual([hubP1, "b2"]);

    // a [[b2]] wikilink in a1's body becomes a note-note edge (either order)
    expect(
      g.edges.some(([x, y]) => (x === "a1" && y === "b2") || (x === "b2" && y === "a1")),
    ).toBe(true);

    // mem nodes carry their type for colouring
    expect(g.nodes.find((n) => n.id === "a1")?.type).toBe("semantic");
  });

  it("resolves wikilinks by title slug and ignores unresolved/self links", () => {
    const notes = [
      { id: "x1", type: "semantic", project: "p", title: "Alpha Note", body: "links [[Alpha Note]] and [[missing]]" },
      { id: "y2", type: "semantic", project: "p", title: "Beta", body: "see [[Alpha Note]]" },
    ];
    const g = buildGraph(notes);
    // y2 -> x1 by title slug
    expect(g.edges.some(([a, b]) => (a === "y2" && b === "x1") || (a === "x1" && b === "y2"))).toBe(
      true,
    );
    // a self link ([[Alpha Note]] inside x1) is not added
    expect(g.edges.some(([a, b]) => a === "x1" && b === "x1")).toBe(false);
    // unresolved [[missing]] adds no stray node/edge
    expect(g.nodes.some((n) => n.id === "missing")).toBe(false);
  });

  it("connects notes that share a tag", () => {
    const notes = [
      { id: "t1", type: "semantic", project: "p", tags: ["mcp"] },
      { id: "t2", type: "semantic", project: "q", tags: ["mcp"] },
    ];
    const g = buildGraph(notes);
    expect(
      g.edges.some(([a, b]) => (a === "t1" && b === "t2") || (a === "t2" && b === "t1")),
    ).toBe(true);
  });

  it("does not crash on notes without bodies", () => {
    const g = buildGraph([{ id: "n1", type: "semantic", project: "p" }]);
    expect(g.nodes.filter((n) => n.kind === "hub")).toHaveLength(1);
    expect(g.nodes.filter((n) => n.kind === "mem")).toHaveLength(1);
  });
});
