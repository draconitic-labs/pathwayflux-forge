"""HTTP API tests: local-only access, project id validation and the custom rate evaluator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine.rate_laws import custom_rate
from app.main import app
from app.models.schema import RateLawType, RateParameters, Reaction, SpeciesStoich
from app.services import projects


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, "PROJECTS_ROOT", tmp_path / "projects")
    with TestClient(app, base_url="http://127.0.0.1") as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_foreign_host_rejected(client):
    r = client.get("/api/health", headers={"Host": "attacker.example"})
    assert r.status_code == 400


def test_no_cross_origin_grant(client):
    r = client.get("/api/health", headers={"Origin": "https://attacker.example"})
    assert "access-control-allow-origin" not in r.headers


@pytest.mark.parametrize("bad_id", ["../escape", "..", "a/b", "UPPER", "-lead", 7])
def test_create_rejects_unsafe_ids(client, tmp_path, bad_id):
    demo = client.get("/api/projects/demo").json()
    r = client.post("/api/projects", json={"id": bad_id, "project": demo})
    assert r.status_code == 400
    assert not (tmp_path / "escape").exists()


def test_save_rejects_dot_dot(client):
    demo = client.get("/api/projects/demo").json()
    r = client.put("/api/projects/..", json=demo)
    assert r.status_code in (400, 404, 405)


def test_create_list_delete_round_trip(client):
    demo = client.get("/api/projects/demo").json()
    r = client.post("/api/projects", json={"id": "my-model", "project": demo})
    assert r.status_code == 200
    ids = {p["id"] for p in client.get("/api/projects").json()}
    assert {"demo-glycolysis", "my-model"} <= ids
    assert client.delete("/api/projects/my-model").status_code == 200


def _reaction(expr: str) -> tuple[Reaction, RateParameters]:
    params = RateParameters(kf=2.0, custom_expression=expr)
    rxn = Reaction(
        name="r",
        substrates=[SpeciesStoich(metabolite_id="m1", stoichiometry=1)],
        products=[],
        rate_law=RateLawType.CUSTOM,
        parameters=params,
    )
    return rxn, params


def test_custom_rate_arithmetic():
    rxn, params = _reaction("kf * A / (1 + A) - 0.5 ** 2")
    v = custom_rate(rxn, {"m1": 3.0}, params, {"A": "m1"}, {"m1": "A"})
    assert v == pytest.approx(2.0 * 3.0 / 4.0 - 0.25)


@pytest.mark.parametrize(
    "expr",
    ["kf.__class__", "__import__", "A()", "kf if A else 0", "[kf]", "'x'", "A.real"],
)
def test_custom_rate_rejects_non_arithmetic(expr):
    rxn, params = _reaction(expr)
    with pytest.raises(ValueError):
        custom_rate(rxn, {"m1": 1.0}, params, {"A": "m1"}, {"m1": "A"})


def test_custom_rate_metabolite_named_like_dunder_cannot_reach_attributes():
    # Metabolite names come from the project file, so they must not unlock attribute access or calls.
    names = ["__class__", "__name__", "__len__"]
    conc = {f"m{i}": 1.0 for i in range(len(names))}
    id_to_name = {f"m{i}": n for i, n in enumerate(names)}
    rxn, params = _reaction("kf.__class__.__name__.__len__()")
    with pytest.raises(ValueError):
        custom_rate(rxn, conc, params, {v: k for k, v in id_to_name.items()}, id_to_name)


def _demo_with_custom(expr: str):
    from app.services.demo import build_glycolysis_demo

    project = build_glycolysis_demo()
    rxn = project.reactions[0]
    rxn.rate_law = RateLawType.CUSTOM
    rxn.parameters.custom_expression = expr
    return project, rxn.name


def test_simulation_reports_a_bad_custom_expression():
    from app.engine.ode import simulate

    project, name = _demo_with_custom("kf * no_such_metabolite")
    result = simulate(project)
    assert result.success is False
    assert name in result.message and "Unknown symbol" in result.message
    assert result.time == []


def test_simulate_endpoint_returns_the_expression_error(client):
    project, name = _demo_with_custom("kf *")
    r = client.post("/api/simulate", json={"project": project.model_dump()})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False and name in body["message"]


@pytest.mark.parametrize(
    "expr",
    ["-" * 5000 + "1", "(" * 3000 + "1" + ")" * 3000, "(" * 240 + "1" + ")" * 240, "1" + "+1" * 2000],
)
def test_oversized_or_deeply_nested_expressions_fail_cleanly(expr):
    rxn, params = _reaction(expr)
    with pytest.raises(ValueError):
        custom_rate(rxn, {"m1": 1.0}, params, {"A": "m1"}, {"m1": "A"})


def test_long_unary_chain_within_the_limit_evaluates():
    rxn, params = _reaction("-" * 498 + "kf")
    assert custom_rate(rxn, {"m1": 1.0}, params, {"A": "m1"}, {"m1": "A"}) == 2.0


def test_long_project_name_gets_a_valid_id(client):
    demo = client.get("/api/projects/demo").json()
    demo["meta"]["name"] = "Glycolysis " * 30
    r = client.post("/api/projects", json={"project": demo})
    assert r.status_code == 200, r.text
    assert len(r.json()["id"]) <= 128
