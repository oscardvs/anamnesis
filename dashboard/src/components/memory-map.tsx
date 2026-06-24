"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { ArrowRight, Minus, Plus, X } from "lucide-react";

import { cn } from "@/lib/cn";

type GNode = {
  id: string;
  kind: "hub" | "mem";
  project: string;
  type?: string;
  title?: string;
  tags?: string[];
  excerpt?: string;
};
type Graph = { nodes: GNode[]; edges: [string, string][] };
type TypeKey = "semantic" | "procedural" | "episodic";

const TYPE_VARS: Record<TypeKey, string> = {
  semantic: "var(--type-semantic)",
  procedural: "var(--type-procedural)",
  episodic: "var(--type-episodic)",
};

const COLORS = {
  dark: { semantic: 0x7aa2ff, procedural: 0x4ade80, episodic: 0xe085ff, accent: 0xb79bff, edge: 0x9a86ff, glow: 0xb79bff, fog: 0x141019 },
  light: { semantic: 0x2f56e0, procedural: 0x0f9d52, episodic: 0xc026d3, accent: 0x6a40d8, edge: 0x9a83ea, glow: 0x6a40d8, fog: 0xeae8f4 },
};

interface Engine {
  applyHidden(h: Record<TypeKey, boolean>): void;
  setSelected(id: string | null): void;
  zoom(f: number): void;
  reset(): void;
  dispose(): void;
}

export function MemoryMap() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const labelsRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { resolvedTheme } = useTheme();
  const [graph, setGraph] = useState<Graph | null>(null);
  const [failed, setFailed] = useState(false);
  const [hidden, setHidden] = useState<Record<TypeKey, boolean>>({
    semantic: false,
    procedural: false,
    episodic: false,
  });
  const [selected, setSelected] = useState<GNode | null>(null);
  const engineRef = useRef<Engine | null>(null);
  const hiddenRef = useRef(hidden);
  useEffect(() => {
    hiddenRef.current = hidden;
  }, [hidden]);

  const open = useCallback(
    (n: GNode) => {
      if (n.kind === "hub") router.push(`/browse?project=${encodeURIComponent(n.project)}`);
      else router.push(`/notes/${n.id}`);
    },
    [router],
  );

  useEffect(() => {
    let alive = true;
    fetch("/api/graph", { cache: "no-store" })
      .then((r) => r.json())
      .then((g: Graph) => alive && setGraph(g))
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!graph || !canvasRef.current) return;
    let engine: Engine | null = null;
    let disposed = false;
    (async () => {
      try {
        const THREE = await import("three");
        if (disposed || !canvasRef.current) return;
        engine = createEngine(
          THREE,
          canvasRef.current,
          labelsRef.current,
          graph,
          resolvedTheme === "dark" ? "dark" : "light",
          { onSelect: (n) => setSelected(n) },
        );
        engine.applyHidden(hiddenRef.current);
        engineRef.current = engine;
      } catch {
        setFailed(true);
      }
    })();
    return () => {
      disposed = true;
      engine?.dispose();
      engineRef.current = null;
    };
  }, [graph, resolvedTheme]);

  useEffect(() => {
    engineRef.current?.applyHidden(hidden);
  }, [hidden]);

  const counts = (() => {
    const c: Record<TypeKey, number> = { semantic: 0, procedural: 0, episodic: 0 };
    graph?.nodes.forEach((n) => {
      if (n.kind === "mem" && n.type && n.type in c) c[n.type as TypeKey]++;
    });
    return c;
  })();

  const toggle = (k: TypeKey) => setHidden((h) => ({ ...h, [k]: !h[k] }));

  return (
    <div
      className="relative h-[60vh] max-h-[520px] min-h-[360px] overflow-hidden rounded-3xl border border-line shadow-[var(--shadow)]"
      style={{
        background:
          "radial-gradient(120% 120% at 50% 38%, color-mix(in oklab, var(--accent) 8%, var(--surface)), var(--surface))",
      }}
    >
      {failed ? (
        <div className="flex h-full items-center justify-center px-6 text-center text-sm text-muted">
          The 3D map needs WebGL, which is unavailable here. Your memory is still browsable from the
          lists.
        </div>
      ) : (
        <>
          <canvas ref={canvasRef} className="absolute inset-0 size-full touch-none" style={{ cursor: "grab" }} />
          <div ref={labelsRef} className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden />

          {/* type filter chips */}
          <div className="absolute left-3 top-3 flex flex-wrap gap-1.5">
            {(Object.keys(TYPE_VARS) as TypeKey[]).map((k) => (
              <button
                key={k}
                onClick={() => toggle(k)}
                className={cn(
                  "tap flex items-center gap-1.5 rounded-full border border-line bg-surface/80 px-2.5 py-1 text-[11.5px] font-medium capitalize text-text backdrop-blur transition-opacity",
                  hidden[k] && "opacity-40",
                )}
              >
                <span className="size-1.5 rounded-full" style={{ background: TYPE_VARS[k] }} />
                {k}
                <span className="font-mono opacity-65">{counts[k]}</span>
              </button>
            ))}
          </div>

          {/* zoom controls */}
          <div className="absolute bottom-3 left-3 flex gap-1.5">
            <MapBtn label="Zoom out" onClick={() => engineRef.current?.zoom(0.8)}>
              <Minus size={15} strokeWidth={2.2} />
            </MapBtn>
            <button
              onClick={() => engineRef.current?.reset()}
              className="tap flex h-8 items-center rounded-lg border border-line bg-surface/80 px-3 text-[11.5px] font-medium text-muted backdrop-blur hover:border-accent hover:text-accent"
            >
              Reset
            </button>
            <MapBtn label="Zoom in" onClick={() => engineRef.current?.zoom(1.28)}>
              <Plus size={15} strokeWidth={2.2} />
            </MapBtn>
          </div>

          {/* selected-node detail card */}
          {selected &&
            (() => {
              const isHub = selected.kind === "hub";
              const memberCount = isHub
                ? (graph?.nodes.filter((n) => n.kind === "mem" && n.project === selected.project)
                    .length ?? 0)
                : 0;
              const closeCard = () => {
                setSelected(null);
                engineRef.current?.setSelected(null);
              };
              return (
                <div className="animate-rise absolute bottom-3 right-3 top-3 flex w-[290px] max-w-[calc(100%-1.5rem)] flex-col rounded-2xl border border-line-strong bg-surface/90 p-5 shadow-[var(--shadow)] backdrop-blur-xl">
                  <button
                    onClick={closeCard}
                    aria-label="Close"
                    className="tap absolute right-3 top-3 flex size-6 items-center justify-center rounded-lg border border-line text-muted hover:text-text"
                  >
                    <X size={13} strokeWidth={2.2} />
                  </button>
                  <span className="mb-3 inline-flex w-fit items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-[10.5px] capitalize text-muted">
                    <span
                      className="size-1.5 rounded-full"
                      style={{
                        background:
                          isHub || !selected.type
                            ? "var(--accent)"
                            : TYPE_VARS[selected.type as TypeKey],
                      }}
                    />
                    {isHub ? "project region" : (selected.type ?? "note")}
                  </span>
                  <h3
                    className={cn(
                      "font-semibold leading-snug text-text",
                      isHub ? "font-mono text-[15px]" : "font-display text-base",
                    )}
                  >
                    {isHub ? selected.project : (selected.title ?? selected.id)}
                  </h3>
                  {!isHub && (
                    <p className="mt-1.5 font-mono text-[11.5px] text-accent">{selected.project}</p>
                  )}
                  <p className="mt-3 line-clamp-5 text-[12.5px] leading-relaxed text-muted">
                    {isHub
                      ? `${memberCount} memories anchored to this project region. Click a node to read one, or open the region to browse them all.`
                      : (selected.excerpt ?? "No preview available for this note.")}
                  </p>
                  {!isHub && selected.tags && selected.tags.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {selected.tags.slice(0, 4).map((t) => (
                        <span
                          key={t}
                          className="rounded-md border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-muted"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                  <button
                    onClick={() => open(selected)}
                    className="bg-accent-gradient sheen tap mt-auto flex h-9 items-center justify-center gap-2 rounded-xl text-[13px] font-semibold text-accent-contrast"
                  >
                    {isHub ? "Browse region" : "Open note"} <ArrowRight size={14} strokeWidth={2} />
                  </button>
                </div>
              );
            })()}
        </>
      )}
    </div>
  );
}

function MapBtn({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className="tap flex size-8 items-center justify-center rounded-lg border border-line bg-surface/80 text-muted backdrop-blur hover:border-accent hover:text-accent"
    >
      {children}
    </button>
  );
}

type ThreeNs = typeof import("three");

function makeGlow(THREE: ThreeNs) {
  const s = 64;
  const cv = document.createElement("canvas");
  cv.width = cv.height = s;
  const g = cv.getContext("2d")!;
  const grd = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  grd.addColorStop(0, "rgba(255,255,255,1)");
  grd.addColorStop(0.35, "rgba(255,255,255,0.45)");
  grd.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grd;
  g.fillRect(0, 0, s, s);
  return new THREE.CanvasTexture(cv);
}

function createEngine(
  THREE: ThreeNs,
  canvas: HTMLCanvasElement,
  labelLayer: HTMLElement | null,
  graph: Graph,
  theme: "dark" | "light",
  cb: { onSelect: (n: GNode | null) => void },
): Engine {
  const cols = COLORS[theme];

  // Member count per project, so hubs can be sized by how much they hold.
  const memberCount = new Map<string, number>();
  for (const n of graph.nodes) {
    if (n.kind === "mem") memberCount.set(n.project, (memberCount.get(n.project) ?? 0) + 1);
  }

  // Layout: project hubs on a Fibonacci sphere, members scattered around their hub.
  const hubs = graph.nodes.filter((n) => n.kind === "hub");
  const NH = hubs.length || 1;
  const R = 158;
  const SPREAD = 44;
  const pos = new Map<string, [number, number, number]>();
  hubs.forEach((h, i) => {
    const y = NH > 1 ? 1 - (i / (NH - 1)) * 2 : 0;
    const rr = Math.sqrt(Math.max(0, 1 - y * y));
    const phi = i * 2.399963;
    pos.set(h.id, [Math.cos(phi) * rr * R, y * R, Math.sin(phi) * rr * R]);
  });
  const g3 = () => Math.random() + Math.random() + Math.random() - 1.5;
  for (const n of graph.nodes) {
    if (n.kind !== "mem") continue;
    const hp = pos.get(`hub:${n.project}`) ?? [0, 0, 0];
    pos.set(n.id, [hp[0] + g3() * SPREAD, hp[1] + g3() * SPREAD, hp[2] + g3() * SPREAD]);
  }

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  const scene = new THREE.Scene();
  // Distance fog gives the cloud real depth (near nodes crisp, far ones recede).
  scene.fog = new THREE.Fog(cols.fog, 240, 760);
  const camera = new THREE.PerspectiveCamera(55, 1, 1, 5000);
  const group = new THREE.Group();
  scene.add(group);
  const geo = new THREE.SphereGeometry(1, 14, 14);
  const glowTex = makeGlow(THREE);

  const colorOf = (n: GNode) =>
    n.kind === "hub" ? cols.accent : cols[(n.type as TypeKey) ?? "semantic"] ?? cols.accent;

  type Mesh = import("three").Mesh<import("three").SphereGeometry, import("three").MeshBasicMaterial>;
  const meshes: Mesh[] = [];
  const meshById = new Map<string, Mesh>();
  const baseOf = new Map<string, number>();
  const glowOf = new Map<string, import("three").Sprite>();
  const nodeOf = new WeakMap<object, GNode>();
  const adj = new Map<string, Set<string>>();
  graph.nodes.forEach((n) => adj.set(n.id, new Set()));

  for (const n of graph.nodes) {
    const mat = new THREE.MeshBasicMaterial({ color: colorOf(n), transparent: true, opacity: 1 });
    const m = new THREE.Mesh(geo, mat) as Mesh;
    const p = pos.get(n.id) ?? [0, 0, 0];
    m.position.set(p[0], p[1], p[2]);
    const base = n.kind === "hub" ? 5 + Math.min(7, (memberCount.get(n.project) ?? 0) / 16) : 3;
    m.scale.setScalar(base);
    nodeOf.set(m, n);
    baseOf.set(n.id, base);
    group.add(m);
    meshes.push(m);
    meshById.set(n.id, m);
    if (n.kind === "hub") {
      const sp = new THREE.Sprite(
        new THREE.SpriteMaterial({
          map: glowTex,
          color: cols.glow,
          transparent: true,
          opacity: 0.5,
          depthWrite: false,
          blending: THREE.AdditiveBlending,
        }),
      );
      sp.position.copy(m.position);
      sp.scale.setScalar(base * 5.5);
      group.add(sp);
      glowOf.set(n.id, sp);
    }
  }
  for (const [a, b] of graph.edges) {
    adj.get(a)?.add(b);
    adj.get(b)?.add(a);
  }

  const edgeGeo = new THREE.BufferGeometry();
  const edgeMat = new THREE.LineBasicMaterial({ color: cols.edge, transparent: true, opacity: 0.12 });
  group.add(new THREE.LineSegments(edgeGeo, edgeMat));
  const hlGeo = new THREE.BufferGeometry();
  const hlMat = new THREE.LineBasicMaterial({ color: cols.accent, transparent: true, opacity: 0.85 });
  group.add(new THREE.LineSegments(hlGeo, hlMat));

  let hidden: Record<TypeKey, boolean> = { semantic: false, procedural: false, episodic: false };
  const isVis = (n: GNode) => n.kind === "hub" || !hidden[n.type as TypeKey];
  // A clicked node stays focused (its card is open); hover focuses transiently.
  let hoverId: string | null = null;
  let selectedId: string | null = null;
  const focused = () => selectedId ?? hoverId;

  const rebuildEdges = () => {
    const p: number[] = [];
    for (const [a, b] of graph.edges) {
      const na = nodeOf.get(meshById.get(a) ?? {});
      const nb = nodeOf.get(meshById.get(b) ?? {});
      if (!na || !nb || !isVis(na) || !isVis(nb)) continue;
      const pa = pos.get(a)!;
      const pb = pos.get(b)!;
      p.push(pa[0], pa[1], pa[2], pb[0], pb[1], pb[2]);
    }
    edgeGeo.setAttribute("position", new THREE.Float32BufferAttribute(p, 3));
  };
  const rebuildHighlight = () => {
    const p: number[] = [];
    const f = focused();
    if (f) {
      for (const [a, b] of graph.edges) {
        if (a !== f && b !== f) continue;
        const pa = pos.get(a);
        const pb = pos.get(b);
        if (pa && pb) p.push(pa[0], pa[1], pa[2], pb[0], pb[1], pb[2]);
      }
    }
    hlGeo.setAttribute("position", new THREE.Float32BufferAttribute(p, 3));
  };
  const applyFocus = () => {
    const f = focused();
    const neigh = f ? adj.get(f) : null;
    for (const m of meshes) {
      const n = nodeOf.get(m)!;
      const vis = isVis(n);
      m.visible = vis;
      const glow = glowOf.get(n.id);
      if (glow) glow.visible = vis;
      const base = baseOf.get(n.id) ?? 3;
      let sc = base;
      let op = 1;
      if (f) {
        if (n.id === f) sc = base * 1.8;
        else if (neigh?.has(n.id)) op = 1;
        else op = 0.14;
      }
      m.scale.setScalar(sc);
      m.material.opacity = op;
      if (glow) glow.material.opacity = f ? (n.id === f ? 0.95 : 0.12) : 0.5;
    }
    rebuildHighlight();
  };
  rebuildEdges();
  applyFocus();

  // Project the project name next to each hub as a crisp HTML label.
  const labels: { el: HTMLDivElement; id: string }[] = [];
  if (labelLayer) {
    labelLayer.innerHTML = "";
    for (const h of hubs) {
      const el = document.createElement("div");
      el.textContent = h.project.replace(/^github\.com\//, "");
      el.style.cssText =
        "position:absolute;left:0;top:0;white-space:nowrap;font-family:var(--font-geist-mono),monospace;" +
        "font-size:10px;font-weight:600;letter-spacing:.02em;color:var(--muted);" +
        "background:color-mix(in oklab,var(--surface) 70%,transparent);border:1px solid var(--line);" +
        "border-radius:6px;padding:1px 6px;transform:translate(-9999px,-9999px);will-change:transform,opacity;" +
        "transition:opacity .2s ease;";
      labelLayer.appendChild(el);
      labels.push({ el, id: h.id });
    }
  }
  const labelVec = new THREE.Vector3();
  const updateLabels = () => {
    if (!labels.length) return;
    const w = canvas.clientWidth;
    const hgt = canvas.clientHeight;
    for (const { el, id } of labels) {
      const m = meshById.get(id);
      if (!m) continue;
      m.getWorldPosition(labelVec).project(camera);
      if (labelVec.z > 1 || labelVec.z < -1) {
        el.style.opacity = "0";
        continue;
      }
      const x = (labelVec.x * 0.5 + 0.5) * w;
      const y = (-labelVec.y * 0.5 + 0.5) * hgt;
      el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) translate(-50%, -150%)`;
      el.style.opacity = "0.92";
    }
  };

  let radius = 430;
  const rot = { x: -0.18, y: 0.5 };
  let dragging = false;
  let lx = 0;
  let ly = 0;
  let moved = 0;
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  const setNdc = (e: PointerEvent) => {
    const r = canvas.getBoundingClientRect();
    ndc.x = ((e.clientX - r.left) / r.width) * 2 - 1;
    ndc.y = -((e.clientY - r.top) / r.height) * 2 + 1;
  };
  const pick = (): Mesh | null => {
    ray.setFromCamera(ndc, camera);
    for (const h of ray.intersectObjects(meshes, false)) {
      const obj = h.object as Mesh;
      if (obj.visible && obj.material.opacity > 0.06) return obj;
    }
    return null;
  };
  const onDown = (e: PointerEvent) => {
    dragging = true;
    moved = 0;
    lx = e.clientX;
    ly = e.clientY;
    try {
      canvas.setPointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
    canvas.style.cursor = "grabbing";
  };
  const onMove = (e: PointerEvent) => {
    if (dragging) {
      const dx = e.clientX - lx;
      const dy = e.clientY - ly;
      moved += Math.abs(dx) + Math.abs(dy);
      rot.y += dx * 0.005;
      rot.x = Math.max(-1.35, Math.min(1.35, rot.x + dy * 0.005));
      lx = e.clientX;
      ly = e.clientY;
      return;
    }
    setNdc(e);
    const m = pick();
    const id = m ? nodeOf.get(m)!.id : null;
    if (id !== hoverId) {
      hoverId = id;
      canvas.style.cursor = m ? "pointer" : "grab";
      applyFocus();
    }
  };
  const onUp = (e: PointerEvent) => {
    if (!dragging) return;
    dragging = false;
    canvas.style.cursor = "grab";
    if (moved >= 5) return;
    setNdc(e);
    const m = pick();
    const n = m ? nodeOf.get(m)! : null;
    // A click selects the node (opens its card); navigation happens from the card.
    selectedId = n ? n.id : null;
    applyFocus();
    cb.onSelect(n);
  };
  const onLeave = () => {
    if (hoverId) {
      hoverId = null;
      applyFocus();
    }
  };
  const onWheel = (e: WheelEvent) => {
    e.preventDefault();
    radius = Math.max(180, Math.min(950, radius * Math.exp(e.deltaY * 0.0012)));
  };
  canvas.addEventListener("pointerdown", onDown);
  canvas.addEventListener("pointermove", onMove);
  canvas.addEventListener("pointerup", onUp);
  canvas.addEventListener("pointerleave", onLeave);
  canvas.addEventListener("wheel", onWheel, { passive: false });

  const resize = () => {
    const r = canvas.getBoundingClientRect();
    if (!r.width || !r.height) return;
    renderer.setSize(r.width, r.height, false);
    camera.aspect = r.width / r.height;
    camera.updateProjectionMatrix();
  };
  resize();
  const ro = new ResizeObserver(resize);
  ro.observe(canvas);

  const fog = scene.fog as import("three").Fog;
  let raf = 0;
  const tick = () => {
    // Idle gentle spin; pause while interacting or inspecting a node.
    if (!dragging && !hoverId && !selectedId) rot.y += 0.0011;
    group.rotation.x = rot.x;
    group.rotation.y = rot.y;
    camera.position.set(0, 0, radius);
    camera.lookAt(0, 0, 0);
    if (fog) {
      fog.near = radius * 0.5;
      fog.far = radius * 1.7;
    }
    renderer.render(scene, camera);
    updateLabels();
    raf = requestAnimationFrame(tick);
  };
  tick();

  return {
    applyHidden(h) {
      hidden = h;
      rebuildEdges();
      applyFocus();
    },
    setSelected(id) {
      selectedId = id;
      applyFocus();
    },
    zoom(f) {
      radius = Math.max(180, Math.min(950, radius / f));
    },
    reset() {
      radius = 430;
      rot.x = -0.18;
      rot.y = 0.5;
    },
    dispose() {
      cancelAnimationFrame(raf);
      ro.disconnect();
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("pointerleave", onLeave);
      canvas.removeEventListener("wheel", onWheel);
      meshes.forEach((m) => m.material.dispose());
      glowOf.forEach((sp) => sp.material.dispose());
      geo.dispose();
      edgeGeo.dispose();
      hlGeo.dispose();
      edgeMat.dispose();
      hlMat.dispose();
      glowTex.dispose();
      if (labelLayer) labelLayer.innerHTML = "";
      try {
        renderer.dispose();
      } catch {
        /* ignore */
      }
    },
  };
}
