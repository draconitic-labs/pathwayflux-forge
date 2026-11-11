import { useCallback, useMemo, useRef, useState } from "react";
import type { JSX } from "react";
import type {
  Metabolite,
  PathwayProject,
  Reaction,
  SimulationResult,
} from "../lib/types";

interface Props {
  project: PathwayProject;
  result: SimulationResult | null;
  frameIndex: number;
  selectedId: string | null;
  onSelect: (id: string | null, kind: "metabolite" | "reaction" | null) => void;
  onMoveMetabolite: (id: string, x: number, y: number) => void;
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}

function metCenter(m: Metabolite) {
  return { x: m.x, y: m.y };
}

function reactionAnchor(
  rxn: Reaction,
  mets: Map<string, Metabolite>
): { x: number; y: number } {
  const pts: { x: number; y: number }[] = [];
  for (const s of rxn.substrates) {
    const m = mets.get(s.metabolite_id);
    if (m) pts.push(metCenter(m));
  }
  for (const p of rxn.products) {
    const m = mets.get(p.metabolite_id);
    if (m) pts.push(metCenter(m));
  }
  if (!pts.length) return { x: 200, y: 200 };
  return {
    x: pts.reduce((a, p) => a + p.x, 0) / pts.length,
    y: pts.reduce((a, p) => a + p.y, 0) / pts.length - 28,
  };
}

export function PathwayCanvas({
  project,
  result,
  frameIndex,
  selectedId,
  onSelect,
  onMoveMetabolite,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [scale, setScale] = useState(1);
  const dragRef = useRef<{
    kind: "pan" | "node";
    id?: string;
    startX: number;
    startY: number;
    origX: number;
    origY: number;
  } | null>(null);

  const metMap = useMemo(
    () => new Map(project.metabolites.map((m) => [m.id, m])),
    [project.metabolites]
  );

  const maxConc = useMemo(() => {
    if (!result) return 1;
    let m = 1e-9;
    for (const series of Object.values(result.concentrations)) {
      for (const v of series) m = Math.max(m, v);
    }
    return m;
  }, [result]);

  const maxFlux = useMemo(() => {
    if (!result) return 1;
    let m = 1e-9;
    for (const series of Object.values(result.fluxes)) {
      for (const v of series) m = Math.max(m, Math.abs(v));
    }
    return m;
  }, [result]);

  const concAt = useCallback(
    (id: string) => {
      if (!result?.concentrations[id]) {
        const met = metMap.get(id);
        return met?.initial_concentration ?? 0;
      }
      const series = result.concentrations[id];
      const i = clamp(frameIndex, 0, series.length - 1);
      return series[i] ?? 0;
    },
    [result, frameIndex, metMap]
  );

  const fluxAt = useCallback(
    (id: string) => {
      if (!result?.fluxes[id]) return 0;
      const series = result.fluxes[id];
      const i = clamp(frameIndex, 0, series.length - 1);
      return series[i] ?? 0;
    },
    [result, frameIndex]
  );

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.92 : 1.08;
    setScale((s) => clamp(s * delta, 0.35, 2.5));
  };

  const clientToSvg = (clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const p = pt.matrixTransform(ctm.inverse());
    return { x: (p.x - pan.x) / scale, y: (p.y - pan.y) / scale };
  };

  const onPointerDownBg = (e: React.PointerEvent) => {
    if ((e.target as Element).closest(".node-hit, .edge-hit")) return;
    dragRef.current = {
      kind: "pan",
      startX: e.clientX,
      startY: e.clientY,
      origX: pan.x,
      origY: pan.y,
    };
    onSelect(null, null);
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const d = dragRef.current;
    if (!d) return;
    if (d.kind === "pan") {
      setPan({
        x: d.origX + (e.clientX - d.startX),
        y: d.origY + (e.clientY - d.startY),
      });
    } else if (d.kind === "node" && d.id) {
      const p = clientToSvg(e.clientX, e.clientY);
      onMoveMetabolite(d.id, p.x, p.y);
    }
  };

  const onPointerUp = () => {
    dragRef.current = null;
  };

  const startNodeDrag = (e: React.PointerEvent, id: string) => {
    e.stopPropagation();
    const m = metMap.get(id);
    if (!m) return;
    dragRef.current = {
      kind: "node",
      id,
      startX: e.clientX,
      startY: e.clientY,
      origX: m.x,
      origY: m.y,
    };
    onSelect(id, "metabolite");
  };

  // Edge paths
  const edges = project.reactions.flatMap((rxn) => {
    const flux = Math.abs(fluxAt(rxn.id));
    const thickness = lerp(1.5, 10, clamp(flux / maxFlux, 0, 1));
    const intensity = clamp(flux / maxFlux, 0.15, 1);
    const mid = reactionAnchor(rxn, metMap);
    const segs: JSX.Element[] = [];

    const draw = (
      from: Metabolite,
      toX: number,
      toY: number,
      key: string,
      arrow: boolean
    ) => {
      const a = metCenter(from);
      const mx = (a.x + toX) / 2;
      const my = (a.y + toY) / 2 - 20;
      const d = `M ${a.x} ${a.y} Q ${mx} ${my} ${toX} ${toY}`;
      segs.push(
        <g key={key} className="edge-hit" onClick={() => onSelect(rxn.id, "reaction")}>
          <path
            d={d}
            fill="none"
            stroke={`rgba(34, 211, 238, ${0.15 + intensity * 0.55})`}
            strokeWidth={thickness + 6}
            strokeLinecap="round"
            opacity={0.35}
          />
          <path
            d={d}
            fill="none"
            stroke={selectedId === rxn.id ? "#a78bfa" : `rgba(45, 212, 191, ${0.45 + intensity * 0.55})`}
            strokeWidth={thickness}
            strokeLinecap="round"
            markerEnd={arrow ? "url(#arrow)" : undefined}
            style={{
              filter:
                intensity > 0.3
                  ? `drop-shadow(0 0 ${4 + intensity * 8}px rgba(34,211,238,${intensity * 0.7}))`
                  : undefined,
              transition: "stroke-width 0.15s, stroke 0.15s",
            }}
          />
        </g>
      );
    };

    for (const s of rxn.substrates) {
      const m = metMap.get(s.metabolite_id);
      if (m) draw(m, mid.x, mid.y, `${rxn.id}-s-${s.metabolite_id}`, false);
    }
    for (const p of rxn.products) {
      const m = metMap.get(p.metabolite_id);
      if (m) {
        // reverse: from mid to product
        const a = metCenter(m);
        const mx = (mid.x + a.x) / 2;
        const my = (mid.y + a.y) / 2 - 20;
        const d = `M ${mid.x} ${mid.y} Q ${mx} ${my} ${a.x} ${a.y}`;
        segs.push(
          <g
            key={`${rxn.id}-p-${p.metabolite_id}`}
            className="edge-hit"
            onClick={() => onSelect(rxn.id, "reaction")}
          >
            <path
              d={d}
              fill="none"
              stroke={`rgba(34, 211, 238, ${0.15 + intensity * 0.55})`}
              strokeWidth={thickness + 6}
              strokeLinecap="round"
              opacity={0.35}
            />
            <path
              d={d}
              fill="none"
              stroke={
                selectedId === rxn.id
                  ? "#a78bfa"
                  : `rgba(45, 212, 191, ${0.45 + intensity * 0.55})`
              }
              strokeWidth={thickness}
              strokeLinecap="round"
              markerEnd="url(#arrow)"
              style={{
                filter:
                  intensity > 0.3
                    ? `drop-shadow(0 0 ${4 + intensity * 8}px rgba(34,211,238,${intensity * 0.7}))`
                    : undefined,
                transition: "stroke-width 0.15s, stroke 0.15s",
              }}
            />
          </g>
        );
      }
    }

    // enzyme label badge
    segs.push(
      <g
        key={`${rxn.id}-label`}
        transform={`translate(${mid.x}, ${mid.y})`}
        className="edge-hit"
        onClick={() => onSelect(rxn.id, "reaction")}
        style={{ cursor: "pointer" }}
      >
        <rect
          x={-36}
          y={-12}
          width={72}
          height={24}
          rx={8}
          fill={selectedId === rxn.id ? "#312e81" : "#0f172aee"}
          stroke={selectedId === rxn.id ? "#a78bfa" : "#334155"}
          strokeWidth={1.5}
        />
        <text
          textAnchor="middle"
          y={4}
          fill="#e2e8f0"
          fontSize={10}
          fontFamily="DM Sans, sans-serif"
          fontWeight={600}
        >
          {rxn.name.length > 10 ? rxn.name.slice(0, 9) + "…" : rxn.name}
        </text>
      </g>
    );
    return segs;
  });

  return (
    <div className="canvas-wrap">
      <div className="canvas-toolbar">
        <button type="button" onClick={() => setScale((s) => clamp(s * 1.15, 0.35, 2.5))}>
          +
        </button>
        <button type="button" onClick={() => setScale((s) => clamp(s / 1.15, 0.35, 2.5))}>
          −
        </button>
        <button
          type="button"
          onClick={() => {
            setScale(1);
            setPan({ x: 0, y: 0 });
          }}
        >
          Reset view
        </button>
      </div>
      <svg
        ref={svgRef}
        className="canvas-svg"
        onWheel={onWheel}
        onPointerDown={onPointerDownBg}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#2dd4bf" />
          </marker>
          <radialGradient id="nodeGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#67e8f9" stopOpacity="0.9" />
            <stop offset="70%" stopColor="#0e7490" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#0e7490" stopOpacity="0" />
          </radialGradient>
          <filter id="softGlow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <g transform={`translate(${pan.x},${pan.y}) scale(${scale})`}>
          {/* Compartments */}
          {project.compartments.map((c) => (
            <g key={c.id}>
              <rect
                x={c.x}
                y={c.y}
                width={c.width}
                height={c.height}
                rx={18}
                fill={c.color || "#0f172a"}
                fillOpacity={0.55}
                stroke="#334155"
                strokeWidth={2}
                strokeDasharray="6 4"
              />
              <text
                x={c.x + 16}
                y={c.y + 24}
                fill="#64748b"
                fontSize={12}
                fontFamily="DM Sans, sans-serif"
                fontWeight={600}
                letterSpacing="0.08em"
              >
                {c.name.toUpperCase()}
              </text>
            </g>
          ))}

          {edges}

          {/* Metabolite nodes */}
          {project.metabolites.map((m) => {
            const c = concAt(m.id);
            const frac = clamp(c / maxConc, 0, 1);
            const r = lerp(18, 42, frac);
            const selected = selectedId === m.id;
            const glowR = r + 14 + frac * 10;
            return (
              <g
                key={m.id}
                className="node-hit"
                transform={`translate(${m.x}, ${m.y})`}
                onPointerDown={(e) => startNodeDrag(e, m.id)}
                style={{ cursor: "grab" }}
              >
                <circle
                  r={glowR}
                  fill="url(#nodeGlow)"
                  opacity={0.25 + frac * 0.55}
                  style={{ transition: "r 0.12s, opacity 0.12s" }}
                />
                <circle
                  r={r}
                  fill={m.is_boundary ? "#1e1b4b" : `rgba(8, 47, 73, ${0.75 + frac * 0.25})`}
                  stroke={selected ? "#a78bfa" : m.is_boundary ? "#818cf8" : "#22d3ee"}
                  strokeWidth={selected ? 3 : 2}
                  filter={frac > 0.2 ? "url(#softGlow)" : undefined}
                  style={{ transition: "r 0.12s" }}
                />
                <text
                  textAnchor="middle"
                  y={4}
                  fill="#f8fafc"
                  fontSize={11}
                  fontWeight={650}
                  fontFamily="DM Sans, sans-serif"
                  style={{ pointerEvents: "none" }}
                >
                  {m.name}
                </text>
                <text
                  textAnchor="middle"
                  y={r + 14}
                  fill="#94a3b8"
                  fontSize={9}
                  fontFamily="JetBrains Mono, monospace"
                  style={{ pointerEvents: "none" }}
                >
                  {c.toFixed(3)}
                  {m.is_boundary ? " ▣" : ""}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
      <div className="canvas-hint">
        Drag nodes · scroll zoom · size ∝ [c] · edge width ∝ flux
      </div>
    </div>
  );
}
