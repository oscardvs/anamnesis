"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { ArrowRight, Minus, Plus, X } from "lucide-react";

import { cn } from "@/lib/cn";

type GNode = { id: string; kind: "hub" | "mem"; project: string; type?: string; title?: string };
type Graph = { nodes: GNode[]; edges: [string, string][] };
type TypeKey = "semantic" | "procedural" | "episodic";

const TYPE_VARS: Record<TypeKey, string> = {
  semantic: "var(--type-semantic)",
  procedural: "var(--type-procedural)",
  episodic: "var(--type-episodic)",
};

const COLORS = {
  dark: { semantic: 0x8da4ff, procedural: 0x4fd39a, episodic: 0xc79bff, accent: 0xb79bff, edge: 0xa896ff, glow: 0xb79bff },
  light: { semantic: 0x4361d8, procedural: 0x1f9e63, episodic: 0xb23fd0, accent: 0x6a40d8, edge: 0x7a52e0, glow: 0x6a40d8 },
};

interface Engine {
  applyHidden(h: Record<TypeKey, boolean>): void;
  zoom(f: number): void;
  reset(): void;
  dispose(): void;
}

export function MemoryMap() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
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
        engine = createEngine(THREE, canvasRef.current, graph, resolvedTheme === "dark" ? "dark" : "light", {
          onSelect: (n) => setSelected(n),
          onOpen: open,
        });
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
  }, [graph, resolvedTheme, open]);

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
          {selected && (
            <div className="animate-rise absolute bottom-3 right-3 top-3 flex w-[280px] max-w-[calc(100%-1.5rem)] flex-col rounded-2xl border border-line-strong bg-surface/90 p-5 shadow-[var(--shadow)] backdrop-blur-xl">
              <button
                onClick={() => setSelected(null)}
                aria-label="Close"
                className="tap absolute right-3 top-3 flex size-6 items-center justify-center rounded-lg border border-line text-muted hover:text-text"
              >
                <X size={13} strokeWidth={2.2} />
              </button>
              <span className="mb-3 inline-flex w-fit items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-[10.5px] capitalize text-muted">
                <span
                  className="size-1.5 rounded-full"
                  style={{ background: selected.type ? TYPE_VARS[selected.type as TypeKey] : "var(--accent)" }}
                />
                {selected.type ?? "note"}
              </span>
              <h3 className="font-display text-base font-semibold leading-snug text-text">
                {selected.title ?? selected.id}
              </h3>
              <p className="mt-1.5 font-mono text-[11.5px] text-accent">{selected.project}</p>
              <button
                onClick={() => open(selected)}
                className="bg-accent-gradient sheen tap mt-auto flex h-9 items-center justify-center gap-2 rounded-xl text-[13px] font-semibold text-accent-contrast"
              >
                Open note <ArrowRight size={14} strokeWidth={2} />
              </button>
            </div>
          )}
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
  graph: Graph,
  theme: "dark" | "light",
  cb: { onSelect: (n: GNode | null) => void; onOpen: (n: GNode) => void },
): Engine {
  const cols = COLORS[theme];

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
    const base = n.kind === "hub" ? 6 : 3;
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
      sp.scale.setScalar(40);
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
  let focusId: string | null = null;

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
    if (focusId) {
      for (const [a, b] of graph.edges) {
        if (a !== focusId && b !== focusId) continue;
        const pa = pos.get(a);
        const pb = pos.get(b);
        if (pa && pb) p.push(pa[0], pa[1], pa[2], pb[0], pb[1], pb[2]);
      }
    }
    hlGeo.setAttribute("position", new THREE.Float32BufferAttribute(p, 3));
  };
  const applyFocus = () => {
    const neigh = focusId ? adj.get(focusId) : null;
    for (const m of meshes) {
      const n = nodeOf.get(m)!;
      const vis = isVis(n);
      m.visible = vis;
      const glow = glowOf.get(n.id);
      if (glow) glow.visible = vis;
      const base = baseOf.get(n.id) ?? 3;
      let sc = base;
      let op = 1;
      if (focusId) {
        if (n.id === focusId) sc = base * 1.8;
        else if (neigh?.has(n.id)) op = 1;
        else op = 0.14;
      }
      m.scale.setScalar(sc);
      m.material.opacity = op;
      if (glow) glow.material.opacity = focusId ? (n.id === focusId ? 0.95 : 0.12) : 0.5;
    }
    rebuildHighlight();
  };
  rebuildEdges();
  applyFocus();

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
    if (id !== focusId) {
      focusId = id;
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
    if (n && n.kind === "hub") cb.onOpen(n);
    else cb.onSelect(n);
  };
  const onLeave = () => {
    if (focusId) {
      focusId = null;
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

  let raf = 0;
  const tick = () => {
    if (!dragging) rot.y += 0.0016;
    group.rotation.x = rot.x;
    group.rotation.y = rot.y;
    camera.position.set(0, 0, radius);
    camera.lookAt(0, 0, 0);
    renderer.render(scene, camera);
    raf = requestAnimationFrame(tick);
  };
  tick();

  return {
    applyHidden(h) {
      hidden = h;
      rebuildEdges();
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
      try {
        renderer.dispose();
      } catch {
        /* ignore */
      }
    },
  };
}
