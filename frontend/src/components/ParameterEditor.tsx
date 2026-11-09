import type {
  Enzyme,
  Inhibitor,
  Metabolite,
  PathwayProject,
  Reaction,
} from "../lib/types";

interface Props {
  project: PathwayProject;
  selectedId: string | null;
  selectedKind: "metabolite" | "reaction" | null;
  onChange: (project: PathwayProject) => void;
}

export function ParameterEditor({
  project,
  selectedId,
  selectedKind,
  onChange,
}: Props) {
  const updateMet = (id: string, patch: Partial<Metabolite>) => {
    onChange({
      ...project,
      metabolites: project.metabolites.map((m) =>
        m.id === id ? { ...m, ...patch } : m
      ),
    });
  };

  const updateRxn = (id: string, patch: Partial<Reaction>) => {
    onChange({
      ...project,
      reactions: project.reactions.map((r) =>
        r.id === id ? { ...r, ...patch } : r
      ),
    });
  };

  const updateEnz = (id: string, patch: Partial<Enzyme>) => {
    onChange({
      ...project,
      enzymes: project.enzymes.map((e) => (e.id === id ? { ...e, ...patch } : e)),
    });
  };

  const updateInh = (id: string, patch: Partial<Inhibitor>) => {
    onChange({
      ...project,
      inhibitors: project.inhibitors.map((i) =>
        i.id === id ? { ...i, ...patch } : i
      ),
    });
  };

  const selectedMet =
    selectedKind === "metabolite"
      ? project.metabolites.find((m) => m.id === selectedId)
      : null;
  const selectedRxn =
    selectedKind === "reaction"
      ? project.reactions.find((r) => r.id === selectedId)
      : null;

  return (
    <div>
      <div className="section-title">Simulation horizon</div>
      <div className="field-row">
        <div className="field">
          <label>t end</label>
          <input
            type="number"
            value={project.simulation.t_end}
            onChange={(e) =>
              onChange({
                ...project,
                simulation: {
                  ...project.simulation,
                  t_end: Number(e.target.value),
                },
              })
            }
          />
        </div>
        <div className="field">
          <label>points</label>
          <input
            type="number"
            value={project.simulation.n_points}
            onChange={(e) =>
              onChange({
                ...project,
                simulation: {
                  ...project.simulation,
                  n_points: Number(e.target.value),
                },
              })
            }
          />
        </div>
      </div>
      <div className="field">
        <label>integrator</label>
        <select
          value={project.simulation.method}
          onChange={(e) =>
            onChange({
              ...project,
              simulation: {
                ...project.simulation,
                method: e.target.value as typeof project.simulation.method,
              },
            })
          }
        >
          <option value="LSODA">LSODA</option>
          <option value="BDF">BDF</option>
          <option value="RK45">RK45</option>
          <option value="Radau">Radau</option>
        </select>
      </div>

      {selectedMet && (
        <>
          <div className="section-title">Selected metabolite</div>
          <div className="field">
            <label>name</label>
            <input
              value={selectedMet.name}
              onChange={(e) => updateMet(selectedMet.id, { name: e.target.value })}
            />
          </div>
          <div className="field-row">
            <div className="field">
              <label>initial [{project.meta.units_concentration}]</label>
              <input
                type="number"
                step="any"
                value={selectedMet.initial_concentration}
                onChange={(e) =>
                  updateMet(selectedMet.id, {
                    initial_concentration: Number(e.target.value),
                  })
                }
              />
            </div>
            <div className="field">
              <label>boundary (fixed)</label>
              <select
                value={selectedMet.is_boundary ? "yes" : "no"}
                onChange={(e) =>
                  updateMet(selectedMet.id, {
                    is_boundary: e.target.value === "yes",
                  })
                }
              >
                <option value="no">no</option>
                <option value="yes">yes</option>
              </select>
            </div>
          </div>
          <div className="field">
            <label>formula</label>
            <input
              value={selectedMet.formula}
              onChange={(e) => updateMet(selectedMet.id, { formula: e.target.value })}
            />
          </div>
        </>
      )}

      {selectedRxn && (
        <>
          <div className="section-title">Selected reaction</div>
          <div className="field">
            <label>name</label>
            <input
              value={selectedRxn.name}
              onChange={(e) => updateRxn(selectedRxn.id, { name: e.target.value })}
            />
          </div>
          <div className="field">
            <label>rate law</label>
            <select
              value={selectedRxn.rate_law}
              onChange={(e) =>
                updateRxn(selectedRxn.id, {
                  rate_law: e.target.value as Reaction["rate_law"],
                })
              }
            >
              <option value="mass_action">Mass action</option>
              <option value="michaelis_menten">Michaelis–Menten</option>
              <option value="competitive_inhibition">Competitive inhibition</option>
              <option value="noncompetitive_inhibition">Noncompetitive inhibition</option>
              <option value="uncompetitive_inhibition">Uncompetitive inhibition</option>
              <option value="hill">Hill</option>
              <option value="custom">Custom</option>
            </select>
          </div>
          <div className="field-row">
            {(["kf", "kr", "Vmax", "Km", "Ki", "K_half", "n_hill"] as const).map(
              (key) => (
                <div className="field" key={key}>
                  <label>{key}</label>
                  <input
                    type="number"
                    step="any"
                    value={selectedRxn.parameters[key]}
                    onChange={(e) =>
                      updateRxn(selectedRxn.id, {
                        parameters: {
                          ...selectedRxn.parameters,
                          [key]: Number(e.target.value),
                        },
                      })
                    }
                  />
                </div>
              )
            )}
          </div>
          {selectedRxn.rate_law === "custom" && (
            <div className="field">
              <label>custom expression</label>
              <input
                value={selectedRxn.parameters.custom_expression}
                onChange={(e) =>
                  updateRxn(selectedRxn.id, {
                    parameters: {
                      ...selectedRxn.parameters,
                      custom_expression: e.target.value,
                    },
                  })
                }
                placeholder="kf * Glucose - kr * G6P"
              />
            </div>
          )}
          <div className="field">
            <label>enzyme</label>
            <select
              value={selectedRxn.enzyme_id || ""}
              onChange={(e) =>
                updateRxn(selectedRxn.id, {
                  enzyme_id: e.target.value || null,
                  parameters: {
                    ...selectedRxn.parameters,
                    enzyme_id: e.target.value || null,
                  },
                })
              }
            >
              <option value="">— none —</option>
              {project.enzymes.map((enz) => (
                <option key={enz.id} value={enz.id}>
                  {enz.name}
                </option>
              ))}
            </select>
          </div>
        </>
      )}

      <div className="section-title">Enzymes</div>
      {project.enzymes.map((enz) => (
        <div key={enz.id} className="eq-block">
          <strong style={{ fontSize: "0.85rem" }}>{enz.name}</strong>
          <div className="field-row" style={{ marginTop: 8 }}>
            <div className="field">
              <label>[E]</label>
              <input
                type="number"
                step="any"
                value={enz.concentration}
                onChange={(e) =>
                  updateEnz(enz.id, { concentration: Number(e.target.value) })
                }
              />
            </div>
            <div className="field">
              <label>kcat scale</label>
              <input
                type="number"
                step="any"
                value={enz.kcat}
                onChange={(e) =>
                  updateEnz(enz.id, { kcat: Number(e.target.value) })
                }
              />
            </div>
          </div>
        </div>
      ))}

      <div className="section-title">Inhibitors</div>
      {project.inhibitors.length === 0 && (
        <p className="muted">No inhibitors defined.</p>
      )}
      {project.inhibitors.map((inh) => (
        <div key={inh.id} className="eq-block">
          <strong style={{ fontSize: "0.85rem" }}>{inh.name}</strong>
          <div className="field-row" style={{ marginTop: 8 }}>
            <div className="field">
              <label>[I]</label>
              <input
                type="number"
                step="any"
                value={inh.concentration}
                onChange={(e) =>
                  updateInh(inh.id, { concentration: Number(e.target.value) })
                }
              />
            </div>
            <div className="field">
              <label>Ki</label>
              <input
                type="number"
                step="any"
                value={inh.ki}
                onChange={(e) => updateInh(inh.id, { ki: Number(e.target.value) })}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
