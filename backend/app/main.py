"""PathwayFlux Forge — local FastAPI backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import __version__
from app.engine import (
    rate_law_latex,
    rate_law_params_display,
    run_compare,
    run_sensitivity,
    run_sweep,
    simulate,
    simulate_perturbation,
)
from app.models.schema import (
    CompareRequest,
    PathwayProject,
    PerturbationRequest,
    ProjectSummary,
    ReportRequest,
    SensitivityRequest,
    SimulateRequest,
    SweepRequest,
)
from app.services.demo import build_glycolysis_demo
from app.services.projects import (
    create_project,
    delete_project,
    export_project_json,
    list_projects,
    load_project,
    save_project,
)
from app.services.report import build_json_report, build_markdown_report


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Ensure demo project exists on disk
    existing = {p.id for p in list_projects()}
    if "demo-glycolysis" not in existing:
        create_project(build_glycolysis_demo(), project_id="demo-glycolysis")
    yield


app = FastAPI(
    title="PathwayFlux Forge",
    description="Local-first metabolic pathway ODE modeling API",
    version=__version__,
    lifespan=lifespan,
)

# The UI reaches the API through the Vite proxy, so no cross-origin access is granted.
# Accepting only local Host headers blocks DNS-rebinding requests from web pages.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


@app.exception_handler(ValueError)
async def value_error(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__, "app": "PathwayFlux Forge"}


# ---- Projects ----


@app.get("/api/projects", response_model=list[ProjectSummary])
def api_list_projects() -> list[ProjectSummary]:
    return list_projects()


@app.get("/api/projects/demo")
def api_demo_project() -> dict[str, Any]:
    return build_glycolysis_demo().model_dump()


@app.get("/api/projects/{project_id}")
def api_get_project(project_id: str) -> dict[str, Any]:
    try:
        return load_project(project_id).model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/projects")
def api_create_project(body: dict[str, Any]) -> dict[str, Any]:
    project = PathwayProject.model_validate(body.get("project", body))
    project_id = body.get("id")
    pid, saved = create_project(project, project_id=project_id)
    return {"id": pid, "project": saved.model_dump()}


@app.put("/api/projects/{project_id}")
def api_save_project(project_id: str, project: PathwayProject) -> dict[str, Any]:
    saved = save_project(project_id, project)
    return {"id": project_id, "project": saved.model_dump()}


@app.delete("/api/projects/{project_id}")
def api_delete_project(project_id: str) -> dict[str, str]:
    if project_id == "demo-glycolysis":
        raise HTTPException(400, "Cannot delete the built-in demo project")
    try:
        delete_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"status": "deleted", "id": project_id}


@app.get("/api/projects/{project_id}/export")
def api_export_project(project_id: str) -> Response:
    try:
        proj = load_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    content = export_project_json(proj)
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{project_id}.pathwayflux.json"'
        },
    )


# ---- Simulation & analysis ----


@app.post("/api/simulate")
def api_simulate(req: SimulateRequest) -> dict[str, Any]:
    result = simulate(
        req.project,
        scenario_id=req.scenario_id,
        overrides=req.overrides,
        settings=req.settings,
    )
    return result.model_dump()


@app.post("/api/sweep")
def api_sweep(req: SweepRequest) -> dict[str, Any]:
    result = run_sweep(
        req.project,
        param_target_type=req.param_target_type,
        param_target_id=req.param_target_id,
        param_name=req.param_name,
        values=req.values,
        scenario_id=req.scenario_id,
        observe_metabolite_ids=req.observe_metabolite_ids,
        observe_reaction_ids=req.observe_reaction_ids,
        metric=req.metric,
        settings=req.settings,
    )
    return result.model_dump()


@app.post("/api/sensitivity")
def api_sensitivity(req: SensitivityRequest) -> dict[str, Any]:
    result = run_sensitivity(
        req.project,
        parameters=req.parameters,
        observe_metabolite_ids=req.observe_metabolite_ids,
        scenario_id=req.scenario_id,
        relative_step=req.relative_step,
        settings=req.settings,
    )
    return result.model_dump()


@app.post("/api/compare")
def api_compare(req: CompareRequest) -> dict[str, Any]:
    result = run_compare(
        req.project,
        scenario_ids=req.scenario_ids,
        settings=req.settings,
    )
    return result.model_dump()


@app.post("/api/perturb")
def api_perturb(req: PerturbationRequest) -> dict[str, Any]:
    result = simulate_perturbation(
        req.project,
        t_perturb=req.t_perturb,
        overrides_before=req.overrides_before,
        overrides_after=req.overrides_after,
        scenario_id=req.scenario_id,
        settings=req.settings,
    )
    return result.model_dump()


# ---- Inspectors / reports ----


@app.post("/api/equations")
def api_equations(project: PathwayProject) -> dict[str, Any]:
    equations = []
    for rxn in project.reactions:
        equations.append(
            {
                "reaction_id": rxn.id,
                "name": rxn.name,
                "rate_law": rxn.rate_law.value,
                "equation": rate_law_latex(rxn),
                "parameters": rate_law_params_display(rxn),
                "substrates": [s.model_dump() for s in rxn.substrates],
                "products": [p.model_dump() for p in rxn.products],
                "reversible": rxn.reversible,
                "enzyme_id": rxn.enzyme_id,
            }
        )
    # ODE skeleton
    odes: dict[str, str] = {}
    for m in project.metabolites:
        if m.is_boundary:
            odes[m.id] = "d[c]/dt = 0  (boundary)"
            continue
        terms: list[str] = []
        for rxn in project.reactions:
            for s in rxn.substrates:
                if s.metabolite_id == m.id:
                    coeff = abs(s.stoichiometry)
                    terms.append(f"−{coeff:g}·v_{rxn.name}")
            for p in rxn.products:
                if p.metabolite_id == m.id:
                    coeff = abs(p.stoichiometry)
                    terms.append(f"+{coeff:g}·v_{rxn.name}")
        odes[m.id] = "d[c]/dt = " + (" ".join(terms) if terms else "0")
    return {"reactions": equations, "odes": odes}


@app.post("/api/report")
def api_report(req: ReportRequest) -> Response:
    if req.format == "json":
        body = build_json_report(req.project, req.simulation, req.compare)
        return Response(content=body, media_type="application/json")
    body = build_markdown_report(req.project, req.simulation, req.compare)
    return PlainTextResponse(content=body, media_type="text/markdown")


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8741, reload=False)


if __name__ == "__main__":
    run()
