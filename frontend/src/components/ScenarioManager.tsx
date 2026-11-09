import type { PathwayProject, Scenario } from "../lib/types";
import { uid } from "../lib/types";

interface Props {
  project: PathwayProject;
  activeScenarioId: string | null;
  onChange: (project: PathwayProject) => void;
  onSelect: (id: string) => void;
  onCompare: () => void;
  comparing: boolean;
}

export function ScenarioManager({
  project,
  activeScenarioId,
  onChange,
  onSelect,
  onCompare,
  comparing,
}: Props) {
  const addScenario = () => {
    const sc: Scenario = {
      id: uid(),
      name: `Scenario ${project.scenarios.length + 1}`,
      kind: "custom",
      description: "",
      overrides: [],
      color: "#94a3b8",
    };
    onChange({ ...project, scenarios: [...project.scenarios, sc] });
    onSelect(sc.id);
  };

  const updateScenario = (id: string, patch: Partial<Scenario>) => {
    onChange({
      ...project,
      scenarios: project.scenarios.map((s) =>
        s.id === id ? { ...s, ...patch } : s
      ),
    });
  };

  const active = project.scenarios.find((s) => s.id === activeScenarioId);

  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        Compare baseline, mutant, and inhibited states with explicit parameter
        overrides.
      </p>
      <div className="chip-row">
        {project.scenarios.map((s) => (
          <button
            key={s.id}
            type="button"
            className={`chip scenario ${s.id === activeScenarioId ? "active" : ""}`}
            style={{
              borderColor: s.id === activeScenarioId ? s.color : undefined,
              color: s.id === activeScenarioId ? s.color : undefined,
            }}
            onClick={() => onSelect(s.id)}
          >
            {s.name}
          </button>
        ))}
      </div>
      <div className="btn-row">
        <button type="button" onClick={addScenario}>
          + Scenario
        </button>
        <button type="button" className="primary" onClick={onCompare} disabled={comparing}>
          {comparing ? "Comparing…" : "Compare all"}
        </button>
      </div>

      {active && (
        <>
          <div className="section-title">Active scenario</div>
          <div className="field">
            <label>name</label>
            <input
              value={active.name}
              onChange={(e) => updateScenario(active.id, { name: e.target.value })}
            />
          </div>
          <div className="field-row">
            <div className="field">
              <label>kind</label>
              <select
                value={active.kind}
                onChange={(e) =>
                  updateScenario(active.id, {
                    kind: e.target.value as Scenario["kind"],
                  })
                }
              >
                <option value="baseline">baseline</option>
                <option value="mutant">mutant</option>
                <option value="inhibited">inhibited</option>
                <option value="custom">custom</option>
              </select>
            </div>
            <div className="field">
              <label>color</label>
              <input
                type="color"
                value={active.color}
                onChange={(e) => updateScenario(active.id, { color: e.target.value })}
              />
            </div>
          </div>
          <div className="field">
            <label>description</label>
            <textarea
              rows={2}
              value={active.description}
              onChange={(e) =>
                updateScenario(active.id, { description: e.target.value })
              }
            />
          </div>
          <div className="section-title">Overrides ({active.overrides.length})</div>
          {active.overrides.length === 0 && (
            <p className="muted">No overrides — uses project defaults.</p>
          )}
          {active.overrides.map((ov, idx) => (
            <div key={idx} className="eq-block">
              <div className="eq-params">
                <span className="chip">{ov.target_type}</span>
                <span className="chip">{ov.target_id}</span>
                {ov.param_name && <span className="chip">{ov.param_name}</span>}
                <span className="chip">= {ov.value}</span>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
