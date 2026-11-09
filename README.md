# PathwayFlux Forge

PathwayFlux Forge is a local web app for building small metabolic pathway models and simulating them as ordinary differential equations. A FastAPI and SciPy backend integrates the model; a React canvas shows concentrations and fluxes as they change.

## Features

- Pathway editor for metabolites, enzymes, reactions, cofactors, inhibitors and compartments
- Rate laws: mass action, Michaelis–Menten, competitive, non-competitive and uncompetitive inhibition, Hill, and custom arithmetic expressions
- Parameter sweeps, timed perturbations and local sensitivity analysis
- Scenarios (baseline, mutant, inhibited) compared with explicit parameter overrides
- Animated canvas: node size follows concentration, edge width follows flux, with a replay timeline
- Equation inspector showing each rate law and the mass-balance ODE of every metabolite
- Projects saved as `pathwayflux.json` with an `ASSUMPTIONS.md` beside them; Markdown and JSON reports

## Requirements

- Python 3.12 or newer
- Node.js 20 or newer

## Run

```bash
./scripts/start.sh
```

The script creates `backend/.venv`, installs the dependencies on first run, starts the API on `127.0.0.1:8741` and the UI on `127.0.0.1:5173`. Open http://127.0.0.1:5173. The demo model loads automatically.

To start the two parts yourself:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8741
```

```bash
cd frontend
npm ci
npm run dev
```

The UI reaches the API through the Vite proxy. The Vite dev and preview servers send no CORS headers, and the API accepts requests addressed to `127.0.0.1` or `localhost` only.

## Test and build

```bash
cd backend
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

```bash
cd frontend
npm run build
```

## Demo model

`backend/projects/demo-glycolysis` is a shortened glycolytic chain, Glucose → G6P → FBP → GAP → Pyruvate, with buffered ATP and ADP, competitive citrate inhibition of PFK, Hill kinetics at pyruvate kinase, and three scenarios: baseline, hexokinase mutant and PFK inhibited. Its assumptions are listed in the project's `ASSUMPTIONS.md`.

## Method

Each reaction's rate is computed from its rate law and the current concentrations. The rate of change of every non-boundary metabolite is the stoichiometry-weighted sum of the rates of the reactions that produce and consume it. SciPy's `solve_ivp` integrates the system with the chosen method (LSODA by default; RK45, BDF and Radau are also available). Boundary metabolites are held constant. Sensitivity is the relative change of an observed output for a small relative change of one parameter.

Custom rate expressions accept numbers, parameter names (`kf`, `kr`, `Vmax`, `Km`, `Km_product`, `Ki`, `n_hill`, `K_half`), metabolite names, `+ - * / **` and parentheses, up to 500 characters. Every rate law is evaluated once at the initial state before integration; a run with an invalid expression stops and names the reaction.

## Project layout

```
backend/
  app/engine/     rate laws, ODE integration, sweeps, sensitivity
  app/models/     Pydantic project schema
  app/services/   project files, demo model, reports
  app/main.py     FastAPI application
  projects/       saved projects
  tests/
frontend/         React and Vite UI
scripts/start.sh
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Health check |
| GET, POST, PUT, DELETE | `/api/projects…` | Project storage |
| POST | `/api/simulate` | Integrate the ODEs |
| POST | `/api/sweep` | Parameter sweep |
| POST | `/api/sensitivity` | Local relative sensitivity |
| POST | `/api/compare` | Run several scenarios |
| POST | `/api/perturb` | Two-phase perturbation |
| POST | `/api/equations` | Rate laws and ODEs |
| POST | `/api/report` | Markdown or JSON report |

## License

MIT. See [LICENSE](LICENSE). The UI bundles the DM Sans and JetBrains Mono fonts from Fontsource, under the SIL Open Font License 1.1.
