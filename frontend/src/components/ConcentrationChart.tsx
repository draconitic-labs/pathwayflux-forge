import type { PathwayProject, SimulationResult } from "../lib/types";

interface Props {
  project: PathwayProject;
  result: SimulationResult | null;
  frameIndex: number;
}

const COLORS = [
  "#2dd4bf",
  "#38bdf8",
  "#a78bfa",
  "#f472b6",
  "#fbbf24",
  "#34d399",
  "#fb7185",
  "#67e8f9",
];

export function ConcentrationChart({ project, result, frameIndex }: Props) {
  if (!result || !result.time.length) {
    return <div className="empty-hint">Run a simulation to plot concentrations.</div>;
  }

  const mets = project.metabolites.filter((m) => !m.is_boundary);
  const W = 300;
  const H = 120;
  const pad = 8;

  let maxY = 1e-9;
  for (const m of mets) {
    const s = result.concentrations[m.id];
    if (!s) continue;
    for (const v of s) maxY = Math.max(maxY, v);
  }

  const t0 = result.time[0];
  const t1 = result.time[result.time.length - 1] || 1;
  const xOf = (t: number) => pad + ((t - t0) / (t1 - t0 || 1)) * (W - 2 * pad);
  const yOf = (v: number) => H - pad - (v / maxY) * (H - 2 * pad);
  const cursorX = xOf(result.time[Math.min(frameIndex, result.time.length - 1)]);

  return (
    <div>
      <svg className="spark" viewBox={`0 0 ${W} ${H}`} style={{ height: 120 }}>
        <line
          x1={cursorX}
          y1={pad}
          x2={cursorX}
          y2={H - pad}
          stroke="#64748b"
          strokeDasharray="3 2"
        />
        {mets.map((m, i) => {
          const s = result.concentrations[m.id];
          if (!s) return null;
          const pts = s
            .map((v, j) => `${xOf(result.time[j])},${yOf(v)}`)
            .join(" ");
          return (
            <polyline
              key={m.id}
              fill="none"
              stroke={COLORS[i % COLORS.length]}
              strokeWidth="1.8"
              points={pts}
            />
          );
        })}
      </svg>
      <div className="chip-row" style={{ marginTop: 6 }}>
        {mets.map((m, i) => (
          <span key={m.id} className="chip" style={{ borderColor: COLORS[i % COLORS.length] }}>
            {m.name}
          </span>
        ))}
      </div>
    </div>
  );
}
