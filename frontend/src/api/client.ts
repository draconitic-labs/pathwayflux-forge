import type {
  CompareResult,
  EquationInfo,
  PathwayProject,
  ProjectSummary,
  SensitivityResult,
  SimulationResult,
  SweepResult,
} from "../lib/types";

const BASE = "";

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return (await res.text()) as unknown as T;
}

export async function health(): Promise<{ status: string; version: string }> {
  return json("/api/health");
}

export async function listProjects(): Promise<ProjectSummary[]> {
  return json("/api/projects");
}

export async function getProject(id: string): Promise<PathwayProject> {
  return json(`/api/projects/${id}`);
}

export async function getDemo(): Promise<PathwayProject> {
  return json("/api/projects/demo");
}

export async function saveProject(
  id: string,
  project: PathwayProject
): Promise<{ id: string; project: PathwayProject }> {
  return json(`/api/projects/${id}`, {
    method: "PUT",
    body: JSON.stringify(project),
  });
}

export async function createProject(
  project: PathwayProject,
  id?: string
): Promise<{ id: string; project: PathwayProject }> {
  return json("/api/projects", {
    method: "POST",
    body: JSON.stringify({ project, id }),
  });
}

export async function simulate(
  project: PathwayProject,
  scenario_id?: string | null
): Promise<SimulationResult> {
  return json("/api/simulate", {
    method: "POST",
    body: JSON.stringify({ project, scenario_id: scenario_id || null }),
  });
}

export async function compare(
  project: PathwayProject,
  scenario_ids: string[]
): Promise<CompareResult> {
  return json("/api/compare", {
    method: "POST",
    body: JSON.stringify({ project, scenario_ids }),
  });
}

export async function sweep(body: Record<string, unknown>): Promise<SweepResult> {
  return json("/api/sweep", { method: "POST", body: JSON.stringify(body) });
}

export async function sensitivity(
  body: Record<string, unknown>
): Promise<SensitivityResult> {
  return json("/api/sensitivity", { method: "POST", body: JSON.stringify(body) });
}

export async function perturb(body: Record<string, unknown>): Promise<SimulationResult> {
  return json("/api/perturb", { method: "POST", body: JSON.stringify(body) });
}

export async function equations(
  project: PathwayProject
): Promise<{ reactions: EquationInfo[]; odes: Record<string, string> }> {
  return json("/api/equations", {
    method: "POST",
    body: JSON.stringify(project),
  });
}

export async function reportMarkdown(
  project: PathwayProject,
  simulation?: SimulationResult | null,
  compareResult?: CompareResult | null
): Promise<string> {
  const res = await fetch("/api/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project,
      simulation: simulation || null,
      compare: compareResult || null,
      format: "markdown",
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.text();
}
