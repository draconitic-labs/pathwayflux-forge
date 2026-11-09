import { useState } from "react";
import * as api from "../api/client";
import type {
  PathwayProject,
  SensitivityResult,
  SimulationResult,
  SweepResult,
} from "../lib/types";

interface Props {
  project: PathwayProject;
  scenarioId: string | null;
  onResult: (r: SimulationResult) => void;
  onToast: (msg: string, err?: boolean) => void;
}

export function AnalysisPanel({ project, scenarioId, onResult, onToast }: Props) {
  const [sweepResult, setSweepResult] = useState<SweepResult | null>(null);
  const [sensResult, setSensResult] = useState<SensitivityResult | null>(null);
  const [busy, setBusy] = useState(false);

  const enz = project.enzymes[0];
  const observeMet =
    project.metabolites.find((m) => !m.is_boundary && m.name.toLowerCase().includes("pyr")) ||
    project.metabolites.find((m) => !m.is_boundary);

  const runSweep = async () => {
    if (!enz) {
      onToast("Add an enzyme first", true);
      return;
    }
    setBusy(true);
    try {
      const res = await api.sweep({
        project,
        scenario_id: scenarioId,
        param_target_type: "enzyme_kcat",
        param_target_id: enz.id,
        values: [0.2, 0.5, 1.0, 1.5, 2.0],
        observe_metabolite_ids: observeMet ? [observeMet.id] : [],
        metric: "final",
      });
      setSweepResult(res);
      onToast(`Parameter sweep on ${enz.name} kcat complete`);
    } catch (e) {
      onToast(String((e as Error).message || e), true);
    } finally {
      setBusy(false);
    }
  };

  const runSens = async () => {
    setBusy(true);
    try {
      const params = project.enzymes.flatMap((e) => [
        { target_type: "enzyme_kcat", target_id: e.id },
        { target_type: "enzyme_concentration", target_id: e.id },
      ]);
      for (const r of project.reactions.slice(0, 3)) {
        params.push({
          target_type: "reaction_param",
          target_id: r.id,
          param_name: "Vmax",
        } as { target_type: string; target_id: string; param_name?: string });
      }
      const res = await api.sensitivity({
        project,
        scenario_id: scenarioId,
        parameters: params,
        observe_metabolite_ids: project.metabolites
          .filter((m) => !m.is_boundary)
          .slice(0, 4)
          .map((m) => m.id),
        relative_step: 0.05,
      });
      setSensResult(res);
      onToast("Local sensitivity analysis complete");
    } catch (e) {
      onToast(String((e as Error).message || e), true);
    } finally {
      setBusy(false);
    }
  };

  const runPerturb = async () => {
    const inh = project.inhibitors[0];
    if (!inh) {
      onToast("No inhibitor defined for perturbation demo", true);
      return;
    }
    setBusy(true);
    try {
      const res = await api.perturb({
        project,
        scenario_id: scenarioId,
        t_perturb: project.simulation.t_end * 0.3,
        overrides_before: [],
        overrides_after: [
          {
            target_type: "inhibitor_concentration",
            target_id: inh.id,
            value: Math.max(inh.concentration, 2),
          },
          ...(inh.metabolite_id
            ? [
                {
                  target_type: "metabolite_initial",
                  target_id: inh.metabolite_id,
                  value: Math.max(inh.concentration, 2),
                },
              ]
            : []),
        ],
      });
      if (!res.success) throw new Error(res.message);
      onResult(res);
      onToast(`Perturbation at t=${(project.simulation.t_end * 0.3).toFixed(1)} applied`);
    } catch (e) {
      onToast(String((e as Error).message || e), true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        Deterministic experiments: sweeps, finite-difference sensitivity, and
        timed perturbations.
      </p>
      <div className="btn-row">
        <button type="button" disabled={busy} onClick={runSweep}>
          Sweep enzyme kcat
        </button>
        <button type="button" disabled={busy} onClick={runSens}>
          Sensitivity
        </button>
        <button type="button" disabled={busy} onClick={runPerturb}>
          Perturb inhibitor
        </button>
      </div>

      {sweepResult && (
        <>
          <div className="section-title">
            Sweep ({sweepResult.metric}) — {enz?.name} kcat
          </div>
          <svg className="spark" viewBox="0 0 300 80" preserveAspectRatio="none">
            {Object.entries(sweepResult.metrics).map(([oid, vals], mi) => {
              const finite = vals.filter((v) => Number.isFinite(v));
              if (!finite.length) return null;
              const min = Math.min(...finite);
              const max = Math.max(...finite);
              const span = max - min || 1;
              const pts = vals
                .map((v, i) => {
                  const x = (i / Math.max(1, vals.length - 1)) * 300;
                  const y = 70 - ((v - min) / span) * 60;
                  return `${x},${y}`;
                })
                .join(" ");
              const colors = ["#2dd4bf", "#a78bfa", "#fbbf24"];
              return (
                <polyline
                  key={oid}
                  fill="none"
                  stroke={colors[mi % colors.length]}
                  strokeWidth="2"
                  points={pts}
                />
              );
            })}
          </svg>
          <div className="eq-params" style={{ marginTop: 6 }}>
            {sweepResult.param_values.map((v) => (
              <span key={v} className="chip">
                {v}
              </span>
            ))}
          </div>
          {Object.entries(sweepResult.metrics).map(([oid, vals]) => (
            <div key={oid} className="muted" style={{ marginTop: 4 }}>
              {sweepResult.observe_names[oid] || oid}:{" "}
              {vals.map((v) => (Number.isFinite(v) ? v.toFixed(3) : "—")).join(", ")}
            </div>
          ))}
        </>
      )}

      {sensResult && sensResult.success && (
        <>
          <div className="section-title">Relative sensitivity (final)</div>
          <div style={{ overflowX: "auto" }}>
            <table className="table-sens">
              <thead>
                <tr>
                  <th>observe \\ param</th>
                  {sensResult.param_keys.map((k) => (
                    <th key={k} title={k}>
                      {k.split(":").slice(-1)[0].slice(0, 8)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(sensResult.sensitivities).map(([mid, row]) => (
                  <tr key={mid}>
                    <td>{sensResult.observe_names[mid] || mid}</td>
                    {sensResult.param_keys.map((k) => {
                      const v = row[k] ?? 0;
                      return (
                        <td
                          key={k}
                          style={{
                            color:
                              Math.abs(v) > 0.5
                                ? "#fbbf24"
                                : Math.abs(v) > 0.1
                                  ? "#2dd4bf"
                                  : "#64748b",
                          }}
                        >
                          {v.toFixed(2)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
