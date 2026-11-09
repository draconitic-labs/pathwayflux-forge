"""Parameter sweeps, sensitivity analysis, and scenario comparison."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.engine.ode import metric_from_series, simulate
from app.models.schema import (
    CompareResult,
    PathwayProject,
    ScenarioOverride,
    SensitivityResult,
    SimulationSettings,
    SweepResult,
)


def run_sweep(
    project: PathwayProject,
    param_target_type: str,
    param_target_id: str,
    param_name: str | None,
    values: list[float],
    scenario_id: str | None = None,
    observe_metabolite_ids: list[str] | None = None,
    observe_reaction_ids: list[str] | None = None,
    metric: str = "final",
    settings: SimulationSettings | None = None,
) -> SweepResult:
    observe_metabolite_ids = observe_metabolite_ids or []
    observe_reaction_ids = observe_reaction_ids or []

    if not observe_metabolite_ids and not observe_reaction_ids:
        observe_metabolite_ids = [m.id for m in project.metabolites if not m.is_boundary][:3]
        observe_reaction_ids = [r.id for r in project.reactions][:2]

    metrics: dict[str, list[float]] = {
        oid: [] for oid in observe_metabolite_ids + observe_reaction_ids
    }
    names: dict[str, str] = {}
    for m in project.metabolites:
        names[m.id] = m.name
    for r in project.reactions:
        names[r.id] = r.name

    for val in values:
        ov = ScenarioOverride(
            target_type=param_target_type,  # type: ignore[arg-type]
            target_id=param_target_id,
            param_name=param_name,
            value=val,
        )
        result = simulate(
            project,
            scenario_id=scenario_id,
            overrides=[ov],
            settings=settings,
        )
        if not result.success:
            for oid in metrics:
                metrics[oid].append(float("nan"))
            continue
        for mid in observe_metabolite_ids:
            series = result.concentrations.get(mid, [])
            metrics[mid].append(metric_from_series(series, result.time, metric))
        for rid in observe_reaction_ids:
            series = result.fluxes.get(rid, [])
            metrics[rid].append(metric_from_series(series, result.time, metric))

    return SweepResult(
        param_values=list(values),
        metrics=metrics,
        observe_names={k: names.get(k, k) for k in metrics},
        metric=metric,
        success=True,
        message="ok",
    )


def _param_key(p: dict[str, Any]) -> str:
    t = p.get("target_type", "?")
    tid = p.get("target_id", "?")
    pn = p.get("param_name")
    return f"{t}:{tid}" + (f":{pn}" if pn else "")


def _get_param_value(project: PathwayProject, p: dict[str, Any]) -> float | None:
    t = p.get("target_type")
    tid = p.get("target_id")
    pn = p.get("param_name")
    if t == "metabolite_initial":
        for m in project.metabolites:
            if m.id == tid:
                return m.initial_concentration
    elif t == "enzyme_concentration":
        for e in project.enzymes:
            if e.id == tid:
                return e.concentration
    elif t == "enzyme_kcat":
        for e in project.enzymes:
            if e.id == tid:
                return e.kcat
    elif t == "inhibitor_concentration":
        for i in project.inhibitors:
            if i.id == tid:
                return i.concentration
    elif t == "inhibitor_ki":
        for i in project.inhibitors:
            if i.id == tid:
                return i.ki
    elif t == "reaction_param" and pn:
        for r in project.reactions:
            if r.id == tid and hasattr(r.parameters, pn):
                return float(getattr(r.parameters, pn))
    return None


def run_sensitivity(
    project: PathwayProject,
    parameters: list[dict[str, Any]],
    observe_metabolite_ids: list[str] | None = None,
    scenario_id: str | None = None,
    relative_step: float = 0.01,
    settings: SimulationSettings | None = None,
) -> SensitivityResult:
    """Local relative sensitivity S = (dy/y) / (dp/p) at final time via finite differences."""
    observe_metabolite_ids = observe_metabolite_ids or [
        m.id for m in project.metabolites if not m.is_boundary
    ][:5]

    names = {m.id: m.name for m in project.metabolites}
    baseline = simulate(project, scenario_id=scenario_id, settings=settings)
    if not baseline.success:
        return SensitivityResult(
            sensitivities={},
            baseline_final={},
            param_keys=[],
            observe_names={},
            success=False,
            message=baseline.message,
        )

    baseline_final = {
        mid: baseline.concentrations[mid][-1]
        if mid in baseline.concentrations and baseline.concentrations[mid]
        else 0.0
        for mid in observe_metabolite_ids
    }

    param_keys = [_param_key(p) for p in parameters]
    sensitivities: dict[str, dict[str, float]] = {
        mid: {} for mid in observe_metabolite_ids
    }

    for p in parameters:
        key = _param_key(p)
        p0 = _get_param_value(project, p)
        if p0 is None:
            for mid in observe_metabolite_ids:
                sensitivities[mid][key] = 0.0
            continue
        # Avoid zero base
        step_base = p0 if abs(p0) > 1e-12 else 1.0
        dp = relative_step * step_base
        p1 = p0 + dp

        ov = ScenarioOverride(
            target_type=p["target_type"],
            target_id=p["target_id"],
            param_name=p.get("param_name"),
            value=p1,
        )
        pert = simulate(
            project,
            scenario_id=scenario_id,
            overrides=[ov],
            settings=settings,
        )
        for mid in observe_metabolite_ids:
            y0 = baseline_final[mid]
            y1 = (
                pert.concentrations[mid][-1]
                if pert.success and mid in pert.concentrations and pert.concentrations[mid]
                else y0
            )
            dy = y1 - y0
            # relative sensitivity
            if abs(y0) > 1e-15 and abs(p0) > 1e-15:
                sens = (dy / y0) / (dp / p0)
            elif abs(dp) > 1e-15:
                sens = dy / dp  # absolute fallback
            else:
                sens = 0.0
            sensitivities[mid][key] = float(sens)

    return SensitivityResult(
        sensitivities=sensitivities,
        baseline_final=baseline_final,
        param_keys=param_keys,
        observe_names={mid: names.get(mid, mid) for mid in observe_metabolite_ids},
        success=True,
        message="ok",
    )


def run_compare(
    project: PathwayProject,
    scenario_ids: list[str],
    settings: SimulationSettings | None = None,
) -> CompareResult:
    results = {}
    names = {}
    for sid in scenario_ids:
        sc_name = sid
        for sc in project.scenarios:
            if sc.id == sid:
                sc_name = sc.name
                break
        names[sid] = sc_name
        results[sid] = simulate(project, scenario_id=sid, settings=settings)

    ok = all(r.success for r in results.values()) if results else False
    return CompareResult(
        scenarios=results,
        scenario_names=names,
        success=ok,
        message="ok" if ok else "one or more scenarios failed",
    )
