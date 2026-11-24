"""Local project file storage (reproducible pathwayflux.json)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from shutil import copy2
from tempfile import TemporaryDirectory

from filelock import FileLock

from app.models.schema import PathwayProject, ProjectSummary

# Default projects root: backend/projects
PROJECTS_ROOT = Path(__file__).resolve().parents[2] / "projects"
_MAX_PROJECT_ID_LENGTH = 128


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(name: str) -> str:
    # Leave room under the 128-character id limit for a "-N" suffix added on name clashes.
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower())[:100].strip("-")
    return s or "pathway"


def ensure_root() -> Path:
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    return PROJECTS_ROOT


def _write_lock() -> FileLock:
    # Keep a stable lock file; ownership is released by the OS on process exit.
    return FileLock(ensure_root() / ".projects.lock", preserve_lock_file=True)


_PROJECT_ID = re.compile(rf"[a-z0-9][a-z0-9-]{{0,{_MAX_PROJECT_ID_LENGTH - 1}}}")


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


def save_project(
    project_id: str, project: PathwayProject, *, create_only: bool = False
) -> PathwayProject:
    with _write_lock():
        if create_only and project_file(project_id).exists():
            raise FileExistsError(project_id)
        return _save_project(project_id, project)


def _save_project(project_id: str, project: PathwayProject) -> PathwayProject:
    d = project_dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    project.meta.modified_at = _now()
    if not project.meta.created_at:
        project.meta.created_at = project.meta.modified_at
    pf = d / "pathwayflux.json"
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
    # Publish the authoritative JSON last and restore the sidecar if publication fails.
    with TemporaryDirectory(prefix=".save-", dir=d) as staging:
        stage = Path(staging)
        new_project = stage / pf.name
        new_project.write_text(project.model_dump_json(indent=2), encoding="utf-8")
        new_assumptions = stage / assumptions_path.name
        new_assumptions.write_text("\n".join(lines), encoding="utf-8")
        previous_assumptions = stage / "previous-assumptions.md"
        if assumptions_path.exists():
            copy2(assumptions_path, previous_assumptions)
        new_assumptions.replace(assumptions_path)
        try:
            new_project.replace(pf)
        except OSError:
            if previous_assumptions.exists():
                previous_assumptions.replace(assumptions_path)
            else:
                assumptions_path.unlink()
            raise
    return project


def create_project(project: PathwayProject, project_id: str | None = None) -> tuple[str, PathwayProject]:
    base = project_id or _slug(project.meta.name)
    pid = base
    n = 1
    with _write_lock():
        while project_file(pid).exists():
            n += 1
            suffix = f"-{n}"
            pid = base[: _MAX_PROJECT_ID_LENGTH - len(suffix)] + suffix
        project.meta.created_at = _now()
        return pid, _save_project(pid, project)


def delete_project(project_id: str) -> None:
    with _write_lock():
        d = project_dir(project_id)
        if not d.exists():
            raise FileNotFoundError(project_id)
        ap = d / "ASSUMPTIONS.md"
        with TemporaryDirectory(prefix=".delete-", dir=d) as staging:
            previous_assumptions = Path(staging) / ap.name
            if ap.exists():
                copy2(ap, previous_assumptions)
                ap.unlink()
            try:
                (d / "pathwayflux.json").unlink(missing_ok=True)
            except OSError:
                if previous_assumptions.exists():
                    previous_assumptions.replace(ap)
                raise
        # Preserve unrelated files in existing project directories.
        try:
            d.rmdir()
        except OSError:
            pass


def export_project_json(project: PathwayProject) -> str:
    return project.model_dump_json(indent=2)
