"""Core ODE engine and analysis tests."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine.analysis import run_compare, run_sensitivity, run_sweep
from app.engine.ode import simulate, simulate_perturbation
from app.engine.rate_laws import mass_action_rate, michaelis_menten_rate
from app.models.schema import (
    Metabolite,
    PathwayProject,
    ProjectMeta,
    RateLawType,
    RateParameters,
    Reaction,
    ScenarioOverride,
    SpeciesStoich,
)
from app.services.demo import build_glycolysis_demo


def test_mass_action_simple():
    rxn = Reaction(
        id="r1",
        name="AtoB",
        substrates=[SpeciesStoich(metabolite_id="A", stoichiometry=1)],
        products=[SpeciesStoich(metabolite_id="B", stoichiometry=1)],
        rate_law=RateLawType.MASS_ACTION,
        parameters=RateParameters(kf=2.0, kr=0.0),
    )
    v = mass_action_rate(rxn, {"A": 3.0, "B": 0.0}, rxn.parameters)
    assert abs(v - 6.0) < 1e-9


def test_michaelis_menten_saturates():
    rxn = Reaction(
        id="r1",
        name="MM",
        substrates=[SpeciesStoich(metabolite_id="S", stoichiometry=1)],
        products=[SpeciesStoich(metabolite_id="P", stoichiometry=1)],
        rate_law=RateLawType.MICHAELIS_MENTEN,
        parameters=RateParameters(Vmax=10.0, Km=1.0),
    )
    v_low = michaelis_menten_rate(rxn, {"S": 0.1}, rxn.parameters)
    v_high = michaelis_menten_rate(rxn, {"S": 100.0}, rxn.parameters)
    assert v_high > v_low
    assert abs(v_high - 10.0) < 0.2


def test_simple_decay_ode():
    """A → ∅ with mass action should decay exponentially."""
    proj = PathwayProject(
        meta=ProjectMeta(name="decay"),
        metabolites=[
            Metabolite(
                id="A",
                name="A",
                compartment_id="c",
                initial_concentration=1.0,
            )
        ],
        reactions=[
            Reaction(
                id="r1",
                name="decay",
                substrates=[SpeciesStoich(metabolite_id="A", stoichiometry=1)],
                products=[],
                rate_law=RateLawType.MASS_ACTION,
                parameters=RateParameters(kf=0.5),
            )
        ],
    )
    proj.simulation.t_end = 10.0
    proj.simulation.n_points = 50
    res = simulate(proj)
    assert res.success
    assert res.concentrations["A"][0] == pytest.approx(1.0, abs=1e-6)
    # A(t) ≈ exp(-0.5 t)
    expected = np.exp(-0.5 * np.array(res.time))
    actual = np.array(res.concentrations["A"])
    assert np.allclose(actual, expected, rtol=0.05, atol=0.02)


def test_demo_simulation_runs():
    demo = build_glycolysis_demo()
    res = simulate(demo, scenario_id="sc_baseline")
    assert res.success
    assert len(res.time) > 10
    assert "glc" in res.concentrations
    assert "rxn_hk" in res.fluxes
    # Glucose should be consumed
    assert res.concentrations["glc"][-1] < res.concentrations["glc"][0]
    # Pyruvate should rise
    assert res.concentrations["pyr"][-1] > res.concentrations["pyr"][0]


def test_mutant_slower_than_baseline():
    demo = build_glycolysis_demo()
    base = simulate(demo, scenario_id="sc_baseline")
    mut = simulate(demo, scenario_id="sc_mutant")
    assert base.success and mut.success
    # Mutant HK → less pyruvate accumulation in same time
    assert mut.concentrations["pyr"][-1] < base.concentrations["pyr"][-1]


def test_inhibited_reduces_pfk_flux():
    demo = build_glycolysis_demo()
    base = simulate(demo, scenario_id="sc_baseline")
    inh = simulate(demo, scenario_id="sc_inhibited")
    assert base.success and inh.success
    # Mean PFK flux should be lower when inhibited
    base_flux = np.mean(base.fluxes["rxn_pfk"])
    inh_flux = np.mean(inh.fluxes["rxn_pfk"])
    assert inh_flux < base_flux


def test_sweep():
    demo = build_glycolysis_demo()
    result = run_sweep(
        demo,
        param_target_type="enzyme_kcat",
        param_target_id="enz_hk",
        param_name=None,
        values=[0.2, 0.5, 1.0, 2.0],
        observe_metabolite_ids=["pyr"],
        metric="final",
    )
    assert result.success
    assert len(result.param_values) == 4
    series = result.metrics["pyr"]
    assert all(np.isfinite(series))
    # Higher kcat → more product (monotone-ish)
    assert series[-1] >= series[0]


def test_sensitivity():
    demo = build_glycolysis_demo()
    result = run_sensitivity(
        demo,
        parameters=[
            {"target_type": "enzyme_kcat", "target_id": "enz_hk"},
            {
                "target_type": "reaction_param",
                "target_id": "rxn_pfk",
                "param_name": "Vmax",
            },
        ],
        observe_metabolite_ids=["pyr", "g6p"],
        relative_step=0.05,
    )
    assert result.success
    assert "pyr" in result.sensitivities
    assert any(abs(v) > 0 for v in result.sensitivities["pyr"].values())


def test_compare_scenarios():
    demo = build_glycolysis_demo()
    result = run_compare(
        demo, scenario_ids=["sc_baseline", "sc_mutant", "sc_inhibited"]
    )
    assert result.success
    assert len(result.scenarios) == 3


def test_perturbation():
    demo = build_glycolysis_demo()
    res = simulate_perturbation(
        demo,
        t_perturb=10.0,
        overrides_before=[],
        overrides_after=[
            ScenarioOverride(
                target_type="inhibitor_concentration",
                target_id="inh_cit",
                value=3.0,
            ),
            ScenarioOverride(
                target_type="metabolite_initial",
                target_id="cit",
                value=3.0,
            ),
        ],
    )
    assert res.success
    assert res.time[0] == pytest.approx(0.0)
    assert res.time[-1] == pytest.approx(50.0, abs=0.5)
