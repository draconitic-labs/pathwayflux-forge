"""Local project file storage (reproducible pathwayflux.json)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.models.schema import PathwayProject, ProjectSummary

# Default projects root: backend/projects
PROJECTS_ROOT = Path(__file__).resolve().parents[2] / "projects"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "pathway"


def ensure_root() -> Path:
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    return PROJECTS_ROOT


_PROJECT_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,127}")


def project_dir(project_id: str) -> Path:
    if not isinstance(project_id, str) or not _PROJECT_ID.fullmatch(project_id):
        raise ValueError(f"Invalid project id: {project_id!r}")
    return ensure_root() / project_id


def project_file(project_id: str) -> Path:
    return project_dir(project_id) / "pathwayflux.json"


def list_projects() -> list[ProjectSummary]:
    ensure_root()
    out: list[ProjectSummary] = []
    for d in sorted(PROJECTS_ROOT.iterdir()):
        if not d.is_dir():
            continue
        pf = d / "pathwayflux.json"
        if not pf.exists():
            continue
        try:
            data = json.loads(pf.read_text(encoding="utf-8"))
            proj = PathwayProject.model_validate(data)
            out.append(
                ProjectSummary(
                    id=d.name,
                    name=proj.meta.name,
                    description=proj.meta.description,
                    path=str(pf),
                    modified_at=proj.meta.modified_at or "",
                    n_metabolites=len(proj.metabolites),
                    n_reactions=len(proj.reactions),
                )
            )
        except Exception:
            continue
    return out


def load_project(project_id: str) -> PathwayProject:
    pf = project_file(project_id)
    if not pf.exists():
        raise FileNotFoundError(f"Project not found: {project_id}")
    data = json.loads(pf.read_text(encoding="utf-8"))
    return PathwayProject.model_validate(data)


def save_project(project_id: str, project: PathwayProject) -> PathwayProject:
    d = project_dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    project.meta.modified_at = _now()
    if not project.meta.created_at:
        project.meta.created_at = project.meta.modified_at
    pf = d / "pathwayflux.json"
    pf.write_text(
        project.model_dump_json(indent=2),
        encoding="utf-8",
    )
    # assumptions sidecar for clarity
    assumptions_path = d / "ASSUMPTIONS.md"
    lines = [
        f"# Assumptions — {project.meta.name}",
        "",
        f"Units: concentration = {project.meta.units_concentration}, "
        f"time = {project.meta.units_time}",
        "",
    ]
    if project.assumptions:
        for a in project.assumptions:
            lines.append(f"- **[{a.category}]** {a.text}")
    else:
        lines.append("_No explicit assumptions recorded._")
    lines.append("")
    assumptions_path.write_text("\n".join(lines), encoding="utf-8")
    return project


def create_project(project: PathwayProject, project_id: str | None = None) -> tuple[str, PathwayProject]:
    ensure_root()
    pid = project_id or _slug(project.meta.name)
    # uniquify
    base = pid
    n = 1
    while project_file(pid).exists():
        n += 1
        pid = f"{base}-{n}"
    project.meta.created_at = _now()
    project.meta.modified_at = project.meta.created_at
    save_project(pid, project)
    return pid, project


def delete_project(project_id: str) -> None:
    d = project_dir(project_id)
    if not d.exists():
        raise FileNotFoundError(project_id)
    pf = d / "pathwayflux.json"
    if pf.exists():
        pf.unlink()
    ap = d / "ASSUMPTIONS.md"
    if ap.exists():
        ap.unlink()
    # remove dir if empty
    try:
        d.rmdir()
    except OSError:
        pass


def export_project_json(project: PathwayProject) -> str:
    return project.model_dump_json(indent=2)
