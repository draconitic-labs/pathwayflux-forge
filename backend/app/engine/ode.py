"""ODE construction and numerical integration for pathway dynamics."""

from __future__ import annotations

import numpy as np
from scipy.integrate import solve_ivp

from app.engine.rate_laws import make_rate_function
from app.models.schema import (
    PathwayProject,
    ScenarioOverride,
    SimulationResult,
    SimulationSettings,
)


def apply_overrides(
    project: PathwayProject,
    overrides: list[ScenarioOverride],
) -> tuple[
    PathwayProject,
    dict[str, float],
    dict[str, float],
    dict[str, dict[str, float]],
]:
    """
    Apply scenario overrides.

    Returns:
      - mutated project copy
      - enzyme_scale: enzyme_id -> concentration, and enzyme_id__kcat -> kcat
      - inhibitor_overrides: inhibitor_id -> concentration
      - reaction_param_overrides: reaction_id -> {param: value}
    """
    proj = project.model_copy(deep=True)
    enzyme_scale: dict[str, float] = {}
    inhibitor_overrides: dict[str, float] = {}
    reaction_param_overrides: dict[str, dict[str, float]] = {}

    met_by_id = {m.id: m for m in proj.metabolites}
    enz_by_id = {e.id: e for e in proj.enzymes}
    inh_by_id = {i.id: i for i in proj.inhibitors}
    rxn_by_id = {r.id: r for r in proj.reactions}

    for ov in overrides:
        if ov.target_type == "metabolite_initial":
            if ov.target_id in met_by_id:
                met_by_id[ov.target_id].initial_concentration = ov.value
        elif ov.target_type == "enzyme_concentration":
            if ov.target_id in enz_by_id:
                enz_by_id[ov.target_id].concentration = ov.value
                enzyme_scale[ov.target_id] = ov.value
        elif ov.target_type == "enzyme_kcat":
            if ov.target_id in enz_by_id:
                enz_by_id[ov.target_id].kcat = ov.value
                enzyme_scale[f"{ov.target_id}__kcat"] = ov.value
        elif ov.target_type == "inhibitor_concentration":
            if ov.target_id in inh_by_id:
                inh_by_id[ov.target_id].concentration = ov.value
                inhibitor_overrides[ov.target_id] = ov.value
        elif ov.target_type == "inhibitor_ki":
            if ov.target_id in inh_by_id:
                inh_by_id[ov.target_id].ki = ov.value
                # also push into reactions that use this inhibitor
                for rxn in proj.reactions:
                    if rxn.parameters.inhibitor_id == ov.target_id:
                        rxn.parameters.Ki = ov.value
        elif ov.target_type == "reaction_param":
            if ov.target_id in rxn_by_id and ov.param_name:
                pname = ov.param_name
                if hasattr(rxn_by_id[ov.target_id].parameters, pname):
                    setattr(rxn_by_id[ov.target_id].parameters, pname, ov.value)
                    reaction_param_overrides.setdefault(ov.target_id, {})[pname] = ov.value

    return proj, enzyme_scale, inhibitor_overrides, reaction_param_overrides


def collect_scenario_overrides(
    project: PathwayProject,
    scenario_id: str | None,
    extra: list[ScenarioOverride] | None = None,
) -> list[ScenarioOverride]:
    overrides: list[ScenarioOverride] = []
    if scenario_id:
        for sc in project.scenarios:
            if sc.id == scenario_id:
                overrides.extend(sc.overrides)
                break
    if extra:
        overrides.extend(extra)
    return overrides


def build_stoichiometry(
    project: PathwayProject,
    variable_ids: list[str],
) -> tuple[np.ndarray, list[str]]:
    """
    S matrix: rows = variable metabolites, cols = reactions.
    Substrates contribute negative stoich, products positive.
    """
    rxn_ids = [r.id for r in project.reactions]
    idx = {mid: i for i, mid in enumerate(variable_ids)}
    S = np.zeros((len(variable_ids), len(rxn_ids)))

    for j, rxn in enumerate(project.reactions):
        for s in rxn.substrates:
            if s.metabolite_id in idx:
                coeff = -abs(s.stoichiometry) if s.stoichiometry != 0 else -1.0
                # if user stored signed stoich, respect sign for substrates
                if s.stoichiometry < 0:
                    coeff = s.stoichiometry
                S[idx[s.metabolite_id], j] += coeff
        for p in rxn.products:
            if p.metabolite_id in idx:
                coeff = abs(p.stoichiometry) if p.stoichiometry != 0 else 1.0
                if p.stoichiometry < 0:
                    coeff = p.stoichiometry
                S[idx[p.metabolite_id], j] += coeff
    return S, rxn_ids


def simulate(
    project: PathwayProject,
    scenario_id: str | None = None,
    overrides: list[ScenarioOverride] | None = None,
    settings: SimulationSettings | None = None,
) -> SimulationResult:
    """Integrate pathway ODEs and return concentration + flux time series."""
    settings = settings or project.simulation
    all_overrides = collect_scenario_overrides(project, scenario_id, overrides)
    proj, enzyme_scale, inh_over, rxn_param_over = apply_overrides(project, all_overrides)

    id_to_name = {m.id: m.name for m in proj.metabolites}
    name_to_id = {m.name: m.id for m in proj.metabolites}
    for m in proj.metabolites:
        safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in m.name)
        name_to_id[safe] = m.id

    # Variable metabolites (non-boundary)
    variable = [m for m in proj.metabolites if not m.is_boundary]
    variable_ids = [m.id for m in variable]
    boundary = {m.id: m.initial_concentration for m in proj.metabolites if m.is_boundary}

    if not variable_ids:
        return SimulationResult(
            time=[],
            concentrations={},
            fluxes={},
            metabolite_names=id_to_name,
            reaction_names={r.id: r.name for r in proj.reactions},
            success=False,
            message="No variable metabolites to integrate.",
        )

    y0 = np.array([m.initial_concentration for m in variable], dtype=float)
    S, rxn_ids = build_stoichiometry(proj, variable_ids)

    rate_fns = []
    for rxn in proj.reactions:
        p_over = rxn_param_over.get(rxn.id)
        rate_fns.append(
            make_rate_function(
                proj,
                rxn,
                name_to_id,
                id_to_name,
                enzyme_scale=enzyme_scale,
                inhibitor_overrides=inh_over,
                param_overrides=p_over,
            )
        )

    var_index = {mid: i for i, mid in enumerate(variable_ids)}

    def full_conc(y: np.ndarray) -> dict[str, float]:
        conc = dict(boundary)
        for mid, i in var_index.items():
            conc[mid] = max(float(y[i]), 0.0)
        return conc

    def fluxes_at(y: np.ndarray) -> np.ndarray:
        conc = full_conc(y)
        v = np.zeros(len(rate_fns))
        for j, fn in enumerate(rate_fns):
            try:
                v[j] = float(fn(conc))
            except Exception as exc:
                raise ValueError(f"Reaction {proj.reactions[j].name}: {exc}") from exc
        return v

    # Evaluate every rate law once at the initial state, so a bad custom expression is
    # reported before integration instead of failing partway through.
    try:
        fluxes_at(y0)
    except ValueError as exc:
        return SimulationResult(
            time=[],
            concentrations={},
            fluxes={},
            metabolite_names=id_to_name,
            reaction_names={r.id: r.name for r in proj.reactions},
            success=False,
            message=str(exc),
        )

    def rhs(_t: float, y: np.ndarray) -> np.ndarray:
        v = fluxes_at(y)
        return S @ v

    t_eval = np.linspace(settings.t_start, settings.t_end, settings.n_points)

    try:
        sol = solve_ivp(
            rhs,
            (settings.t_start, settings.t_end),
            y0,
            method=settings.method,
            t_eval=t_eval,
            rtol=settings.rtol,
            atol=settings.atol,
            dense_output=False,
        )
    except Exception as exc:
        return SimulationResult(
            time=[],
            concentrations={},
            fluxes={},
            metabolite_names=id_to_name,
            reaction_names={r.id: r.name for r in proj.reactions},
            success=False,
            message=f"Integrator error: {exc}",
        )

    if not sol.success and sol.t.size == 0:
        return SimulationResult(
            time=[],
            concentrations={},
            fluxes={},
            metabolite_names=id_to_name,
            reaction_names={r.id: r.name for r in proj.reactions},
            success=False,
            message=sol.message or "Integration failed",
        )

    times = sol.t.tolist()
    concentrations: dict[str, list[float]] = {}
    # boundary constants
    for mid, c0 in boundary.items():
        concentrations[mid] = [c0] * len(times)
    for i, mid in enumerate(variable_ids):
        concentrations[mid] = [max(float(v), 0.0) for v in sol.y[i]]

    fluxes: dict[str, list[float]] = {rid: [] for rid in rxn_ids}
    for k in range(len(times)):
        yk = sol.y[:, k]
        vk = fluxes_at(yk)
        for j, rid in enumerate(rxn_ids):
            fluxes[rid].append(float(vk[j]))

    return SimulationResult(
        time=times,
        concentrations=concentrations,
        fluxes=fluxes,
        metabolite_names=id_to_name,
        reaction_names={r.id: r.name for r in proj.reactions},
        success=True,
        message=sol.message or "ok",
        t_end_actual=float(sol.t[-1]) if sol.t.size else settings.t_end,
        n_steps=int(sol.t.size),
    )


def simulate_perturbation(
    project: PathwayProject,
    t_perturb: float,
    overrides_before: list[ScenarioOverride] | None = None,
    overrides_after: list[ScenarioOverride] | None = None,
    scenario_id: str | None = None,
    settings: SimulationSettings | None = None,
) -> SimulationResult:
    """Two-phase simulation: integrate to t_perturb, apply overrides, continue."""
    settings = settings or project.simulation
    t0, t1, t_end = settings.t_start, t_perturb, settings.t_end
    if not (t0 < t1 < t_end):
        return simulate(
            project,
            scenario_id=scenario_id,
            overrides=(overrides_before or []) + (overrides_after or []),
            settings=settings,
        )

    n_total = settings.n_points
    frac = (t1 - t0) / (t_end - t0)
    n1 = max(5, int(n_total * frac))
    n2 = max(5, n_total - n1)

    s1 = settings.model_copy(update={"t_start": t0, "t_end": t1, "n_points": n1})
    r1 = simulate(
        project,
        scenario_id=scenario_id,
        overrides=overrides_before or [],
        settings=s1,
    )
    if not r1.success or not r1.time:
        return r1

    # Build continuation project with final concentrations as initials
    proj2 = project.model_copy(deep=True)
    base_over = collect_scenario_overrides(project, scenario_id, overrides_before)
    proj2, _, _, _ = apply_overrides(proj2, base_over)

    for m in proj2.metabolites:
        if m.id in r1.concentrations and r1.concentrations[m.id]:
            m.initial_concentration = r1.concentrations[m.id][-1]

    s2 = settings.model_copy(update={"t_start": t1, "t_end": t_end, "n_points": n2})
    r2 = simulate(
        proj2,
        scenario_id=None,  # already baked into proj2 initials
        overrides=overrides_after or [],
        settings=s2,
    )
    if not r2.success:
        return r2

    # Stitch (drop duplicate first point of phase 2)
    time = r1.time + r2.time[1:]
    concentrations: dict[str, list[float]] = {}
    all_mids = set(r1.concentrations) | set(r2.concentrations)
    for mid in all_mids:
        a = r1.concentrations.get(mid, [])
        b = r2.concentrations.get(mid, [])
        concentrations[mid] = a + b[1:]

    fluxes: dict[str, list[float]] = {}
    all_rids = set(r1.fluxes) | set(r2.fluxes)
    for rid in all_rids:
        a = r1.fluxes.get(rid, [])
        b = r2.fluxes.get(rid, [])
        fluxes[rid] = a + b[1:]

    return SimulationResult(
        time=time,
        concentrations=concentrations,
        fluxes=fluxes,
        metabolite_names=r2.metabolite_names or r1.metabolite_names,
        reaction_names=r2.reaction_names or r1.reaction_names,
        success=True,
        message="perturbation ok",
        t_end_actual=time[-1] if time else t_end,
        n_steps=len(time),
    )


def metric_from_series(series: list[float], time: list[float], metric: str) -> float:
    if not series:
        return 0.0
    arr = np.array(series, dtype=float)
    if metric == "final":
        return float(arr[-1])
    if metric == "max":
        return float(np.max(arr))
    if metric == "auc":
        if len(time) < 2:
            return float(arr[-1])
        trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")
        return float(trapz(arr, time))
    if metric == "steady_state":
        # average of last 10% of trajectory
        n = max(1, len(arr) // 10)
        return float(np.mean(arr[-n:]))
    return float(arr[-1])
