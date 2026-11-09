export type RateLawType =
  | "mass_action"
  | "michaelis_menten"
  | "competitive_inhibition"
  | "noncompetitive_inhibition"
  | "uncompetitive_inhibition"
  | "hill"
  | "custom";

export interface Compartment {
  id: string;
  name: string;
  volume: number;
  color: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Metabolite {
  id: string;
  name: string;
  compartment_id: string;
  initial_concentration: number;
  is_boundary: boolean;
  charge: number;
  formula: string;
  x: number;
  y: number;
  notes: string;
}

export interface Enzyme {
  id: string;
  name: string;
  concentration: number;
  kcat: number;
  notes: string;
}

export interface Cofactor {
  id: string;
  name: string;
  metabolite_id: string;
  role: "cosubstrate" | "coproduct" | "prosthetic";
  notes: string;
}

export interface Inhibitor {
  id: string;
  name: string;
  metabolite_id: string | null;
  concentration: number;
  ki: number;
  inhibition_type: string;
  target_reaction_ids: string[];
  notes: string;
}

export interface SpeciesStoich {
  metabolite_id: string;
  stoichiometry: number;
}

export interface RateParameters {
  kf: number;
  kr: number;
  Vmax: number;
  Km: number;
  Km_product: number;
  Ki: number;
  n_hill: number;
  K_half: number;
  enzyme_id: string | null;
  inhibitor_id: string | null;
  custom_expression: string;
}

export interface Reaction {
  id: string;
  name: string;
  substrates: SpeciesStoich[];
  products: SpeciesStoich[];
  modifiers: string[];
  rate_law: RateLawType;
  parameters: RateParameters;
  reversible: boolean;
  enzyme_id: string | null;
  compartment_id: string | null;
  notes: string;
}

export interface ScenarioOverride {
  target_type:
    | "metabolite_initial"
    | "enzyme_concentration"
    | "enzyme_kcat"
    | "reaction_param"
    | "inhibitor_concentration"
    | "inhibitor_ki";
  target_id: string;
  param_name?: string | null;
  value: number;
}

export interface Scenario {
  id: string;
  name: string;
  kind: "baseline" | "mutant" | "inhibited" | "custom";
  description: string;
  overrides: ScenarioOverride[];
  color: string;
}

export interface Assumption {
  id: string;
  text: string;
  category: string;
}

export interface SimulationSettings {
  t_start: number;
  t_end: number;
  n_points: number;
  method: "RK45" | "BDF" | "LSODA" | "Radau";
  rtol: number;
  atol: number;
}

export interface ProjectMeta {
  name: string;
  description: string;
  author: string;
  created_at: string;
  modified_at: string;
  units_time: string;
  units_concentration: string;
  version: string;
  tags: string[];
}

export interface PathwayProject {
  schema_version: string;
  meta: ProjectMeta;
  compartments: Compartment[];
  metabolites: Metabolite[];
  enzymes: Enzyme[];
  cofactors: Cofactor[];
  inhibitors: Inhibitor[];
  reactions: Reaction[];
  scenarios: Scenario[];
  assumptions: Assumption[];
  simulation: SimulationSettings;
  layout_version: number;
}

export interface SimulationResult {
  time: number[];
  concentrations: Record<string, number[]>;
  fluxes: Record<string, number[]>;
  metabolite_names: Record<string, string>;
  reaction_names: Record<string, string>;
  success: boolean;
  message: string;
  t_end_actual: number;
  n_steps: number;
}

export interface SweepResult {
  param_values: number[];
  metrics: Record<string, number[]>;
  observe_names: Record<string, string>;
  metric: string;
  success: boolean;
  message: string;
}

export interface SensitivityResult {
  sensitivities: Record<string, Record<string, number>>;
  baseline_final: Record<string, number>;
  param_keys: string[];
  observe_names: Record<string, string>;
  success: boolean;
  message: string;
}

export interface CompareResult {
  scenarios: Record<string, SimulationResult>;
  scenario_names: Record<string, string>;
  success: boolean;
  message: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  description: string;
  path: string;
  modified_at: string;
  n_metabolites: number;
  n_reactions: number;
}

export interface EquationInfo {
  reaction_id: string;
  name: string;
  rate_law: string;
  equation: string;
  parameters: Record<string, number | string>;
  substrates: SpeciesStoich[];
  products: SpeciesStoich[];
  reversible: boolean;
  enzyme_id: string | null;
}

export function uid(): string {
  return Math.random().toString(16).slice(2, 10) + Date.now().toString(16).slice(-4);
}

export function emptyProject(name = "New Pathway"): PathwayProject {
  return {
    schema_version: "1.0",
    meta: {
      name,
      description: "",
      author: "",
      created_at: "",
      modified_at: "",
      units_time: "s",
      units_concentration: "mM",
      version: "1.0.0",
      tags: [],
    },
    compartments: [
      {
        id: "cyto",
        name: "Cytosol",
        volume: 1,
        color: "#0f172a",
        x: 40,
        y: 40,
        width: 800,
        height: 500,
      },
    ],
    metabolites: [],
    enzymes: [],
    cofactors: [],
    inhibitors: [],
    reactions: [],
    scenarios: [
      {
        id: "sc_baseline",
        name: "Baseline",
        kind: "baseline",
        description: "Default parameters",
        overrides: [],
        color: "#38bdf8",
      },
    ],
    assumptions: [],
    simulation: {
      t_start: 0,
      t_end: 50,
      n_points: 200,
      method: "LSODA",
      rtol: 1e-6,
      atol: 1e-9,
    },
    layout_version: 1,
  };
}
