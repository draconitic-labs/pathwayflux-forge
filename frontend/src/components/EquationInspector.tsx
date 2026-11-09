import { useEffect, useState } from "react";
import * as api from "../api/client";
import type { EquationInfo, PathwayProject } from "../lib/types";

interface Props {
  project: PathwayProject;
  selectedReactionId: string | null;
}

export function EquationInspector({ project, selectedReactionId }: Props) {
  const [reactions, setReactions] = useState<EquationInfo[]>([]);
  const [odes, setOdes] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .equations(project)
      .then((data) => {
        if (cancelled) return;
        setReactions(data.reactions);
        setOdes(data.odes);
        setError(null);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e.message || e));
      });
    return () => {
      cancelled = true;
    };
  }, [project]);

  const ordered = selectedReactionId
    ? [
        ...reactions.filter((r) => r.reaction_id === selectedReactionId),
        ...reactions.filter((r) => r.reaction_id !== selectedReactionId),
      ]
    : reactions;

  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        Deterministic rate laws and mass-balance ODEs for the open model.
      </p>
      {error && <p className="muted">Could not load equations: {error}</p>}
      {!ordered.length && !error && (
        <div className="empty-hint">Add reactions to inspect rate equations.</div>
      )}
      {ordered.map((r) => (
        <div
          key={r.reaction_id}
          className="eq-block"
          style={{
            borderColor:
              r.reaction_id === selectedReactionId ? "#a78bfa" : undefined,
          }}
        >
          <h3>
            {r.name}{" "}
            <span className="badge" style={{ marginLeft: 6 }}>
              {r.rate_law}
            </span>
          </h3>
          <div className="eq-formula">{r.equation}</div>
          <div className="eq-params">
            {Object.entries(r.parameters).map(([k, v]) => (
              <span key={k} className="chip">
                {k} = {String(v)}
              </span>
            ))}
          </div>
        </div>
      ))}

      <div className="section-title">Mass-balance ODEs</div>
      {Object.entries(odes).map(([id, eq]) => {
        const name = project.metabolites.find((m) => m.id === id)?.name || id;
        return (
          <div key={id} className="eq-block">
            <h3>{name}</h3>
            <div className="eq-formula">{eq}</div>
          </div>
        );
      })}
    </div>
  );
}
