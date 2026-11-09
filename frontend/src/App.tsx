import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as api from "./api/client";
import { AnalysisPanel } from "./components/AnalysisPanel";
import { ConcentrationChart } from "./components/ConcentrationChart";
import { EquationInspector } from "./components/EquationInspector";
import { ParameterEditor } from "./components/ParameterEditor";
import { PathwayCanvas } from "./components/PathwayCanvas";
import { ScenarioManager } from "./components/ScenarioManager";
import { Timeline } from "./components/Timeline";
import {
  emptyProject,
  type CompareResult,
  type PathwayProject,
  type ProjectSummary,
  type SimulationResult,
  uid,
} from "./lib/types";

type RightTab =
  | "params"
  | "equations"
  | "scenarios"
  | "analysis"
  | "report"
  | "assumptions";

export default function App() {
  const [projectId, setProjectId] = useState<string>("demo-glycolysis");
  const [project, setProject] = useState<PathwayProject | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [backendOk, setBackendOk] = useState(false);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [compare, setCompare] = useState<CompareResult | null>(null);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedKind, setSelectedKind] = useState<"metabolite" | "reaction" | null>(
    null
  );
  const [rightTab, setRightTab] = useState<RightTab>("params");
  const [toast, setToast] = useState<{ msg: string; err?: boolean } | null>(null);
  const [reportText, setReportText] = useState("");
  const playRef = useRef<number | null>(null);

  const showToast = useCallback((msg: string, err = false) => {
    setToast({ msg, err });
    window.setTimeout(() => setToast(null), 3200);
  }, []);

  const loadProjectList = useCallback(async () => {
    try {
      const list = await api.listProjects();
      setProjects(list);
    } catch {
      /* ignore */
    }
  }, []);

  const loadProject = useCallback(
    async (id: string) => {
      setBusy(true);
      try {
        const p = await api.getProject(id);
        setProject(p);
        setProjectId(id);
        setScenarioId(p.scenarios[0]?.id ?? null);
        setResult(null);
        setCompare(null);
        setFrameIndex(0);
        setPlaying(false);
        showToast(`Loaded ${p.meta.name}`);
      } catch (e) {
        showToast(String((e as Error).message || e), true);
      } finally {
        setBusy(false);
      }
    },
    [showToast]
  );

  useEffect(() => {
    api
      .health()
      .then(() => {
        setBackendOk(true);
        return loadProjectList();
      })
      .then(() => loadProject("demo-glycolysis"))
      .catch(() => {
        setBackendOk(false);
        // Offline fallback: still allow UI with empty project
        setProject(emptyProject("Offline draft"));
      });
  }, [loadProject, loadProjectList]);

  // Timeline playback
  useEffect(() => {
    if (!playing || !result?.time.length) {
      if (playRef.current) cancelAnimationFrame(playRef.current);
      return;
    }
    let last = performance.now();
    const step = (now: number) => {
      if (now - last > 40) {
        last = now;
        setFrameIndex((i) => {
          const next = i + 1;
          if (next >= result.time.length) {
            setPlaying(false);
            return result.time.length - 1;
          }
          return next;
        });
      }
      playRef.current = requestAnimationFrame(step);
    };
    playRef.current = requestAnimationFrame(step);
    return () => {
      if (playRef.current) cancelAnimationFrame(playRef.current);
    };
  }, [playing, result]);

  const metrics = useMemo(() => {
    if (!result || !project) return null;
    const finals: { name: string; value: number }[] = [];
    for (const m of project.metabolites.filter((x) => !x.is_boundary).slice(0, 4)) {
      const s = result.concentrations[m.id];
      if (s?.length) finals.push({ name: m.name, value: s[s.length - 1] });
    }
    return finals;
  }, [result, project]);

  const runSim = async () => {
    if (!project) return;
    setBusy(true);
    try {
      const res = await api.simulate(project, scenarioId);
      if (!res.success) throw new Error(res.message || "Simulation failed");
      setResult(res);
      setFrameIndex(0);
      setPlaying(true);
      showToast("Simulation complete");
    } catch (e) {
      showToast(String((e as Error).message || e), true);
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    if (!project) return;
    setBusy(true);
    try {
      await api.saveProject(projectId, project);
      await loadProjectList();
      showToast("Project saved locally");
    } catch (e) {
      showToast(String((e as Error).message || e), true);
    } finally {
      setBusy(false);
    }
  };

  const newBlank = async () => {
    const p = emptyProject("Untitled Pathway");
    try {
      const { id, project: saved } = await api.createProject(p);
      setProject(saved);
      setProjectId(id);
      setScenarioId(saved.scenarios[0]?.id ?? null);
      setResult(null);
      await loadProjectList();
      showToast("Created new project");
    } catch (e) {
      setProject(p);
      showToast(String((e as Error).message || e), true);
    }
  };

  const addMetabolite = () => {
    if (!project) return;
    const id = uid();
    setProject({
      ...project,
      metabolites: [
        ...project.metabolites,
        {
          id,
          name: `M${project.metabolites.length + 1}`,
          compartment_id: project.compartments[0]?.id || "cyto",
          initial_concentration: 1,
          is_boundary: false,
          charge: 0,
          formula: "",
          x: 150 + project.metabolites.length * 40,
          y: 200 + (project.metabolites.length % 3) * 50,
          notes: "",
        },
      ],
    });
    setSelectedId(id);
    setSelectedKind("metabolite");
  };

  const addReaction = () => {
    if (!project) return;
    const mets = project.metabolites.filter((m) => !m.is_boundary);
    if (mets.length < 2) {
      showToast("Need at least two metabolites for a reaction", true);
      return;
    }
    const id = uid();
    setProject({
      ...project,
      reactions: [
        ...project.reactions,
        {
          id,
          name: `R${project.reactions.length + 1}`,
          substrates: [{ metabolite_id: mets[0].id, stoichiometry: 1 }],
          products: [{ metabolite_id: mets[1].id, stoichiometry: 1 }],
          modifiers: [],
          rate_law: "mass_action",
          parameters: {
            kf: 1,
            kr: 0,
            Vmax: 1,
            Km: 1,
            Km_product: 1,
            Ki: 1,
            n_hill: 1,
            K_half: 1,
            enzyme_id: null,
            inhibitor_id: null,
            custom_expression: "",
          },
          reversible: false,
          enzyme_id: null,
          compartment_id: null,
          notes: "",
        },
      ],
    });
    setSelectedId(id);
    setSelectedKind("reaction");
    setRightTab("params");
  };

  const addEnzyme = () => {
    if (!project) return;
    setProject({
      ...project,
      enzymes: [
        ...project.enzymes,
        {
          id: uid(),
          name: `Enzyme ${project.enzymes.length + 1}`,
          concentration: 1,
          kcat: 1,
          notes: "",
        },
      ],
    });
  };

  const addInhibitor = () => {
    if (!project) return;
    const target = project.reactions[0]?.id;
    setProject({
      ...project,
      inhibitors: [
        ...project.inhibitors,
        {
          id: uid(),
          name: `Inhibitor ${project.inhibitors.length + 1}`,
          metabolite_id: null,
          concentration: 0,
          ki: 1,
          inhibition_type: "competitive",
          target_reaction_ids: target ? [target] : [],
          notes: "",
        },
      ],
    });
    setRightTab("params");
    showToast("Inhibitor added — edit Ki and targets in Parameters");
  };

  const addCofactor = () => {
    if (!project) return;
    const met = project.metabolites[0];
    if (!met) {
      showToast("Add a metabolite first to link as cofactor", true);
      return;
    }
    setProject({
      ...project,
      cofactors: [
        ...project.cofactors,
        {
          id: uid(),
          name: `Cofactor ${project.cofactors.length + 1}`,
          metabolite_id: met.id,
          role: "cosubstrate",
          notes: "",
        },
      ],
    });
    showToast("Cofactor linked to " + met.name);
  };

  const addCompartment = () => {
    if (!project) return;
    const n = project.compartments.length;
    setProject({
      ...project,
      compartments: [
        ...project.compartments,
        {
          id: uid(),
          name: `Compartment ${n + 1}`,
          volume: 1,
          color: "#0f172a",
          x: 40 + n * 30,
          y: 40 + n * 30,
          width: 500,
          height: 360,
        },
      ],
    });
  };

  const onCompare = async () => {
    if (!project) return;
    setBusy(true);
    try {
      const res = await api.compare(
        project,
        project.scenarios.map((s) => s.id)
      );
      setCompare(res);
      // load baseline trajectory into canvas if available
      const first = project.scenarios[0];
      if (first && res.scenarios[first.id]?.success) {
        setResult(res.scenarios[first.id]);
        setFrameIndex(0);
      }
      setRightTab("scenarios");
      showToast("Scenario comparison complete");
    } catch (e) {
      showToast(String((e as Error).message || e), true);
    } finally {
      setBusy(false);
    }
  };

  const exportReport = async () => {
    if (!project) return;
    try {
      const md = await api.reportMarkdown(project, result, compare);
      setReportText(md);
      setRightTab("report");
      const blob = new Blob([md], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${project.meta.name.replace(/\s+/g, "_")}_report.md`;
      a.click();
      URL.revokeObjectURL(url);
      showToast("Report exported");
    } catch (e) {
      showToast(String((e as Error).message || e), true);
    }
  };

  const exportJson = () => {
    if (!project) return;
    const blob = new Blob([JSON.stringify(project, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${projectId}.pathwayflux.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("Project JSON downloaded");
  };

  if (!project) {
    return (
      <div className="app-shell" style={{ placeItems: "center", display: "grid" }}>
        <p className="muted">Loading PathwayFlux Forge…</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">PF</div>
          <div>
            <h1>PathwayFlux Forge</h1>
            <span>Local ODE pathway modeling</span>
          </div>
        </div>
        <div className="topbar-actions">
          <select
            style={{ width: 200 }}
            value={projectId}
            onChange={(e) => loadProject(e.target.value)}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
            {!projects.find((p) => p.id === projectId) && (
              <option value={projectId}>{project.meta.name}</option>
            )}
          </select>
          <button type="button" onClick={newBlank}>
            New
          </button>
          <button type="button" onClick={save} disabled={busy}>
            Save
          </button>
          <button type="button" onClick={addMetabolite}>
            + Metabolite
          </button>
          <button type="button" onClick={addEnzyme}>
            + Enzyme
          </button>
          <button type="button" onClick={addReaction}>
            + Reaction
          </button>
          <button type="button" onClick={addCofactor}>
            + Cofactor
          </button>
          <button type="button" onClick={addInhibitor}>
            + Inhibitor
          </button>
          <button type="button" onClick={addCompartment}>
            + Compartment
          </button>
          <button type="button" className="primary" onClick={runSim} disabled={busy}>
            {busy ? "Working…" : "Simulate"}
          </button>
          <button type="button" onClick={exportReport}>
            Export report
          </button>
          <button type="button" onClick={exportJson}>
            Export JSON
          </button>
        </div>
        <div className="topbar-status">
          <span className={`dot ${backendOk ? "" : "err"}`} />
          {backendOk ? "backend · 8741" : "backend offline"}
          <span>{project.meta.units_concentration}</span>
        </div>
      </header>

      <div className="workspace">
        <aside className="panel">
          <div className="panel-header">
            <h2>Model</h2>
          </div>
          <div className="panel-body">
            <div className="field">
              <label>project name</label>
              <input
                value={project.meta.name}
                onChange={(e) =>
                  setProject({
                    ...project,
                    meta: { ...project.meta, name: e.target.value },
                  })
                }
              />
            </div>
            <div className="field">
              <label>description</label>
              <textarea
                rows={3}
                value={project.meta.description}
                onChange={(e) =>
                  setProject({
                    ...project,
                    meta: { ...project.meta, description: e.target.value },
                  })
                }
              />
            </div>

            <div className="section-title">
              Metabolites ({project.metabolites.length})
            </div>
            {project.metabolites.map((m) => (
              <div
                key={m.id}
                className={`list-item ${selectedId === m.id ? "selected" : ""}`}
                onClick={() => {
                  setSelectedId(m.id);
                  setSelectedKind("metabolite");
                  setRightTab("params");
                }}
              >
                <span className="title">{m.name}</span>
                <span className="badge">
                  {m.initial_concentration}
                  {m.is_boundary ? " ▣" : ""}
                </span>
              </div>
            ))}

            <div className="section-title">
              Reactions ({project.reactions.length})
            </div>
            {project.reactions.map((r) => (
              <div
                key={r.id}
                className={`list-item ${selectedId === r.id ? "selected" : ""}`}
                onClick={() => {
                  setSelectedId(r.id);
                  setSelectedKind("reaction");
                  setRightTab("equations");
                }}
              >
                <span className="title">{r.name}</span>
                <span className="badge">{r.rate_law}</span>
              </div>
            ))}

            <div className="section-title">
              Enzymes ({project.enzymes.length}) · Cofactors ({project.cofactors.length})
            </div>
            {project.enzymes.map((e) => (
              <div key={e.id} className="list-item">
                <span className="title">{e.name}</span>
                <span className="badge">kcat={e.kcat}</span>
              </div>
            ))}
            {project.cofactors.map((c) => (
              <div key={c.id} className="list-item">
                <span className="title">{c.name}</span>
                <span className="badge">{c.role}</span>
              </div>
            ))}
            <div className="section-title">
              Inhibitors ({project.inhibitors.length})
            </div>
            {project.inhibitors.map((i) => (
              <div key={i.id} className="list-item">
                <span className="title">{i.name}</span>
                <span className="badge">Ki={i.ki}</span>
              </div>
            ))}

            <div className="section-title">Live metrics</div>
            {metrics ? (
              <div className="metric-grid">
                {metrics.map((m) => (
                  <div key={m.name} className="metric-card">
                    <div className="label">{m.name} final</div>
                    <div className="value">{m.value.toFixed(4)}</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">Run Simulate to populate finals.</p>
            )}

            <div className="section-title">Trajectory</div>
            <ConcentrationChart
              project={project}
              result={result}
              frameIndex={frameIndex}
            />

            {compare && (
              <>
                <div className="section-title">Scenario finals (pyruvate-like)</div>
                {Object.entries(compare.scenarios).map(([sid, res]) => {
                  const name = compare.scenario_names[sid] || sid;
                  const pyr =
                    res.concentrations["pyr"] ||
                    Object.values(res.concentrations).find((s) => s?.length);
                  const final = pyr?.[pyr.length - 1];
                  return (
                    <div key={sid} className="list-item">
                      <span className="title">{name}</span>
                      <span className="badge">
                        {final != null ? final.toFixed(4) : "—"}
                      </span>
                    </div>
                  );
                })}
              </>
            )}
          </div>
        </aside>

        <main className="canvas-wrap" style={{ display: "contents" }}>
          <PathwayCanvas
            project={project}
            result={result}
            frameIndex={frameIndex}
            selectedId={selectedId}
            onSelect={(id, kind) => {
              setSelectedId(id);
              setSelectedKind(kind);
              if (kind === "reaction") setRightTab("equations");
              if (kind === "metabolite") setRightTab("params");
            }}
            onMoveMetabolite={(id, x, y) => {
              setProject((prev) =>
                prev
                  ? {
                      ...prev,
                      metabolites: prev.metabolites.map((m) =>
                        m.id === id ? { ...m, x, y } : m
                      ),
                    }
                  : prev
              );
            }}
          />
        </main>

        <aside className="panel right">
          <div className="tabs">
            {(
              [
                ["params", "Parameters"],
                ["equations", "Equations"],
                ["scenarios", "Scenarios"],
                ["analysis", "Analysis"],
                ["assumptions", "Assumptions"],
                ["report", "Report"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={`tab ${rightTab === id ? "active" : ""}`}
                onClick={() => setRightTab(id)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="panel-body">
            {rightTab === "params" && (
              <ParameterEditor
                project={project}
                selectedId={selectedId}
                selectedKind={selectedKind}
                onChange={setProject}
              />
            )}
            {rightTab === "equations" && (
              <EquationInspector
                project={project}
                selectedReactionId={
                  selectedKind === "reaction" ? selectedId : null
                }
              />
            )}
            {rightTab === "scenarios" && (
              <ScenarioManager
                project={project}
                activeScenarioId={scenarioId}
                onChange={setProject}
                onSelect={setScenarioId}
                onCompare={onCompare}
                comparing={busy}
              />
            )}
            {rightTab === "analysis" && (
              <AnalysisPanel
                project={project}
                scenarioId={scenarioId}
                onResult={(r) => {
                  setResult(r);
                  setFrameIndex(0);
                  setPlaying(true);
                }}
                onToast={showToast}
              />
            )}
            {rightTab === "assumptions" && (
              <div>
                <p className="muted" style={{ marginTop: 0 }}>
                  Explicit model assumptions travel with the project file for
                  reproducibility.
                </p>
                <ul className="assumptions">
                  {project.assumptions.map((a) => (
                    <li key={a.id}>
                      <strong>[{a.category}]</strong> {a.text}
                    </li>
                  ))}
                </ul>
                {!project.assumptions.length && (
                  <p className="muted">No assumptions recorded yet.</p>
                )}
                <div className="btn-row">
                  <button
                    type="button"
                    onClick={() =>
                      setProject({
                        ...project,
                        assumptions: [
                          ...project.assumptions,
                          {
                            id: uid(),
                            text: "New assumption",
                            category: "other",
                          },
                        ],
                      })
                    }
                  >
                    + Assumption
                  </button>
                </div>
                {project.assumptions.map((a) => (
                  <div key={a.id} className="field" style={{ marginTop: 8 }}>
                    <label>{a.category}</label>
                    <input
                      value={a.text}
                      onChange={(e) =>
                        setProject({
                          ...project,
                          assumptions: project.assumptions.map((x) =>
                            x.id === a.id ? { ...x, text: e.target.value } : x
                          ),
                        })
                      }
                    />
                  </div>
                ))}
              </div>
            )}
            {rightTab === "report" && (
              <div>
                <p className="muted" style={{ marginTop: 0 }}>
                  Markdown report for lab notes / teaching handouts.
                </p>
                <div className="btn-row">
                  <button type="button" className="primary" onClick={exportReport}>
                    Generate & download
                  </button>
                </div>
                {reportText ? (
                  <pre className="report-preview">{reportText}</pre>
                ) : (
                  <div className="empty-hint">
                    Click generate to build a report from the current model and
                    last simulation.
                  </div>
                )}
              </div>
            )}
          </div>
        </aside>
      </div>

      <Timeline
        result={result}
        frameIndex={frameIndex}
        playing={playing}
        onFrame={setFrameIndex}
        onPlaying={setPlaying}
      />

      {toast && (
        <div className={`toast ${toast.err ? "error" : ""}`}>{toast.msg}</div>
      )}
    </div>
  );
}
