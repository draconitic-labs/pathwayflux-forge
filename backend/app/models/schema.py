"""Pathway project schema — reproducible local model files."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _id() -> str:
    return uuid4().hex[:12]


class RateLawType(str, Enum):
    MASS_ACTION = "mass_action"
    MICHAELIS_MENTEN = "michaelis_menten"
    COMPETITIVE_INHIBITION = "competitive_inhibition"
    NONCOMPETITIVE_INHIBITION = "noncompetitive_inhibition"
    UNCOMPETITIVE_INHIBITION = "uncompetitive_inhibition"
    HILL = "hill"
    CUSTOM = "custom"


class Compartment(BaseModel):
    id: str = Field(default_factory=_id)
    name: str
    volume: float = 1.0
    color: str = "#1e293b"
    x: float = 0.0
    y: float = 0.0
    width: float = 400.0
    height: float = 300.0


class Metabolite(BaseModel):
    id: str = Field(default_factory=_id)
    name: str
    compartment_id: str
    initial_concentration: float = 0.0
    is_boundary: bool = False  # fixed concentration (source/sink)
    charge: int = 0
    formula: str = ""
    x: float = 100.0
    y: float = 100.0
    notes: str = ""


class Enzyme(BaseModel):
    id: str = Field(default_factory=_id)
    name: str
    concentration: float = 1.0
    kcat: float = 1.0
    notes: str = ""


class Cofactor(BaseModel):
    id: str = Field(default_factory=_id)
    name: str
    metabolite_id: str  # linked metabolite
    role: Literal["cosubstrate", "coproduct", "prosthetic"] = "cosubstrate"
    notes: str = ""


class Inhibitor(BaseModel):
    id: str = Field(default_factory=_id)
    name: str
    metabolite_id: str | None = None  # optional linked metabolite
    concentration: float = 0.0
    ki: float = 1.0
    inhibition_type: Literal[
        "competitive", "noncompetitive", "uncompetitive", "mixed"
    ] = "competitive"
    target_reaction_ids: list[str] = Field(default_factory=list)
    notes: str = ""


class SpeciesStoich(BaseModel):
    metabolite_id: str
    stoichiometry: float = 1.0  # positive for products, negative for substrates when signed


class RateParameters(BaseModel):
    """Parameters for built-in rate laws. Unused keys are ignored."""

    kf: float = 1.0  # forward mass-action
    kr: float = 0.0  # reverse mass-action (0 = irreversible)
    Vmax: float = 1.0
    Km: float = 1.0
    Km_product: float = 1.0
    Ki: float = 1.0
    n_hill: float = 1.0
    K_half: float = 1.0
    enzyme_id: str | None = None
    inhibitor_id: str | None = None
    custom_expression: str = ""  # e.g. "kf * A * B - kr * C" (metabolite names)


class Reaction(BaseModel):
    id: str = Field(default_factory=_id)
    name: str
    substrates: list[SpeciesStoich] = Field(default_factory=list)
    products: list[SpeciesStoich] = Field(default_factory=list)
    modifiers: list[str] = Field(default_factory=list)  # metabolite ids (enzymes as mets)
    rate_law: RateLawType = RateLawType.MASS_ACTION
    parameters: RateParameters = Field(default_factory=RateParameters)
    reversible: bool = False
    enzyme_id: str | None = None
    compartment_id: str | None = None
    notes: str = ""


class SimulationSettings(BaseModel):
    t_start: float = 0.0
    t_end: float = 100.0
    n_points: int = 200
    method: Literal["RK45", "BDF", "LSODA", "Radau"] = "LSODA"
    rtol: float = 1e-6
    atol: float = 1e-9


class ScenarioOverride(BaseModel):
    """Parameter or initial-condition override for a scenario."""

    target_type: Literal[
        "metabolite_initial",
        "enzyme_concentration",
        "enzyme_kcat",
        "reaction_param",
        "inhibitor_concentration",
        "inhibitor_ki",
    ]
    target_id: str
    param_name: str | None = None  # for reaction_param: kf, Vmax, Km, ...
    value: float


class Scenario(BaseModel):
    id: str = Field(default_factory=_id)
    name: str
    kind: Literal["baseline", "mutant", "inhibited", "custom"] = "custom"
    description: str = ""
    overrides: list[ScenarioOverride] = Field(default_factory=list)
    color: str = "#38bdf8"


class Assumption(BaseModel):
    id: str = Field(default_factory=_id)
    text: str
    category: Literal[
        "kinetics", "compartment", "boundary", "units", "approximation", "other"
    ] = "other"


class ProjectMeta(BaseModel):
    name: str = "Untitled Pathway"
    description: str = ""
    author: str = ""
    created_at: str = ""
    modified_at: str = ""
    units_time: str = "s"
    units_concentration: str = "mM"
    version: str = "1.0.0"
    tags: list[str] = Field(default_factory=list)


class PathwayProject(BaseModel):
    """Reproducible local project file (pathwayflux.json)."""

    schema_version: str = "1.0"
    meta: ProjectMeta = Field(default_factory=ProjectMeta)
    compartments: list[Compartment] = Field(default_factory=list)
    metabolites: list[Metabolite] = Field(default_factory=list)
    enzymes: list[Enzyme] = Field(default_factory=list)
    cofactors: list[Cofactor] = Field(default_factory=list)
    inhibitors: list[Inhibitor] = Field(default_factory=list)
    reactions: list[Reaction] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)
    layout_version: int = 1


# --- API request / response models ---


class SimulateRequest(BaseModel):
    project: PathwayProject
    scenario_id: str | None = None
    overrides: list[ScenarioOverride] = Field(default_factory=list)
    settings: SimulationSettings | None = None


class SweepRequest(BaseModel):
    project: PathwayProject
    scenario_id: str | None = None
    param_target_type: Literal[
        "metabolite_initial",
        "enzyme_concentration",
        "enzyme_kcat",
        "reaction_param",
        "inhibitor_concentration",
        "inhibitor_ki",
    ]
    param_target_id: str
    param_name: str | None = None
    values: list[float]
    observe_metabolite_ids: list[str] = Field(default_factory=list)
    observe_reaction_ids: list[str] = Field(default_factory=list)
    metric: Literal["final", "auc", "max", "steady_state"] = "final"
    settings: SimulationSettings | None = None


class SensitivityRequest(BaseModel):
    project: PathwayProject
    scenario_id: str | None = None
    parameters: list[dict[str, Any]]  # {target_type, target_id, param_name?}
    observe_metabolite_ids: list[str] = Field(default_factory=list)
    relative_step: float = 0.01
    settings: SimulationSettings | None = None


class CompareRequest(BaseModel):
    project: PathwayProject
    scenario_ids: list[str]
    settings: SimulationSettings | None = None


class PerturbationRequest(BaseModel):
    project: PathwayProject
    scenario_id: str | None = None
    # Step change at time t_perturb
    t_perturb: float
    overrides_before: list[ScenarioOverride] = Field(default_factory=list)
    overrides_after: list[ScenarioOverride] = Field(default_factory=list)
    settings: SimulationSettings | None = None


class SimulationResult(BaseModel):
    time: list[float]
    concentrations: dict[str, list[float]]  # metabolite_id -> series
    fluxes: dict[str, list[float]]  # reaction_id -> series
    metabolite_names: dict[str, str]
    reaction_names: dict[str, str]
    success: bool = True
    message: str = ""
    t_end_actual: float = 0.0
    n_steps: int = 0


class SweepResult(BaseModel):
    param_values: list[float]
    metrics: dict[str, list[float]]  # observe_id -> metric per param value
    observe_names: dict[str, str]
    metric: str
    success: bool = True
    message: str = ""


class SensitivityResult(BaseModel):
    # sensitivity[observe_id][param_key] = d(log y)/d(log p) or absolute
    sensitivities: dict[str, dict[str, float]]
    baseline_final: dict[str, float]
    param_keys: list[str]
    observe_names: dict[str, str]
    success: bool = True
    message: str = ""


class CompareResult(BaseModel):
    scenarios: dict[str, SimulationResult]  # scenario_id -> result
    scenario_names: dict[str, str]
    success: bool = True
    message: str = ""


class ReportRequest(BaseModel):
    project: PathwayProject
    simulation: SimulationResult | None = None
    compare: CompareResult | None = None
    format: Literal["markdown", "json"] = "markdown"


class ProjectSummary(BaseModel):
    id: str
    name: str
    description: str
    path: str
    modified_at: str
    n_metabolites: int
    n_reactions: int
