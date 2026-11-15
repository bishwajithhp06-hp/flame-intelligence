# FLAME INTELLIGENCE

**Research exploration for fire safety in spacecraft and microgravity environments.**  
NASA Space Apps Challenge project · research prototype

FLAME INTELLIGENCE brings together local combustion-research records, NASA source metadata, evidence-aware scenario analysis, and research gaps in one interface. It is designed to help users explore what sources document—and what they do not establish.

> This is a research and demonstration tool. It is not a validated combustion model, spacecraft safety assessment, operational procedure, or NASA endorsement.

## The problem

Spacecraft fire-safety research is distributed across investigations, technical publications, and data repositories. A record title or publication citation alone does not establish that a specific material, atmosphere, pressure, airflow, and gravity combination was tested. FLAME INTELLIGENCE helps users find and compare source-linked records while keeping provenance, missing conditions, and uncertainty visible.

## Features

- **Dashboard:** summarizes the locally stored investigation, publication, finding, and datapoint records.
- **NASA Research Explorer:** searches stored PSI investigation metadata and NTRS publication metadata, shows source links and provenance, and exposes available record details.
- **Experiment comparison:** compares explicit structured conditions where both records provide compatible values. It does not produce a similarity score or claim scientific equivalence.
- **AI Research Assistant:** sends evidence-grounded questions to the server-side Gemini service and returns retrieved citations or an insufficient-evidence response.
- **Mission Intelligence:** accepts a hypothetical scenario, retrieves relevant evidence, runs four specialist analyses and a Mission Safety Synthesizer, and reports citations, claim-validation status, assumptions, uncertainties, and research gaps.
- **Analytics and insights:** explores the stored local datapoints and research findings with their provenance limitations.
- **Visual Lab and NASA Media:** offers an explicitly illustrative 3D visualization and source-attributed media from NASA's public media catalog.
- **PDF reports:** generates mission-analysis and experiment-comparison reports from the current results and stored records.

## Technology

- **Frontend:** React 19, Vite 8, Tailwind CSS 4, Recharts, Lucide, Three.js, and React Three Fiber.
- **Backend:** FastAPI, Pydantic, SQLAlchemy, HTTPX, Requests, Pandas, and BeautifulSoup.
- **Database:** local SQLite by default.
- **AI provider:** Google Gemini through the server-side `google-genai` SDK.
- **NASA sources:** NASA Physical Sciences Informatics (PSI), NASA Technical Reports Server (NTRS), and the NASA Images and Video Library.

Vite serves the frontend on port 5173 and proxies `/api` requests to the FastAPI development server on `127.0.0.1:8000`.

## Architecture

```text
frontend/
  src/App.jsx                     Application shell and module navigation
  src/components/                 Dashboard, explorer, AI, mission, analytics,
                                  comparison, insights, sources, and Visual Lab
  src/services/                   API, NASA media, and PDF download clients
  tests/                          Frontend contract, rendering, media, and PDF tests

backend/
  app/routes/                     FastAPI endpoints
  app/schemas/                    Request and response validation
  app/services/                   Mission evidence, Gemini, PSI, NTRS, analytics,
                                  experiment comparison, and PDF generation
  app/models/                     SQLAlchemy models
  app/seed_data/                  Local seed records
  tests/                          Backend, provenance, NASA integration, and PDF tests

docs/
  nasa-data-architecture.md       NASA source workflows, storage, provenance, and limits
```

The main API groups include dashboard and investigation reads, search, analytics, `/api/ai/query`, `/api/mission/analyze`, `/api/experiments`, `/api/experiments/compare`, `/api/sources`, and PDF report endpoints under `/api/reports`.

## NASA data integration and provenance

The backend can retrieve PSI investigation metadata and details, inspect listed files, retrieve explicitly selected eligible files within a 10 MiB limit, and list or explicitly download public PSI S3 objects within that cap. NTRS search retrieves paginated citation metadata such as titles, authors, abstracts, identifiers, DOIs, and available links. Retrieval state and source metadata are recorded separately from measurement data. Full workflow details and CLI examples are in [`docs/nasa-data-architecture.md`](docs/nasa-data-architecture.md).

The stored source records are a local retrieval snapshot, not a complete NASA PSI dataset archive.

Important evidence distinctions:

- The existing legacy local datapoints are **provenance-unverified**. Their legacy measured-flight flag does not make them verified NASA flight measurements.
- A NASA PSI source link can establish that a record came from a NASA-controlled source path; it does not independently validate every condition or measurement in that record.
- NTRS records are publication metadata. A citation does not establish the provenance of a numerical datapoint.
- Retrieved PSI file bytes are stored as raw files. The ingestion service does not parse their numeric rows into the application's combustion datapoint table or convert their units.
- Experiment descriptions do not establish that a combined hypothetical scenario was tested. Microgravity evidence is not treated as lunar-gravity evidence.
- Visual Lab output is illustrative and is not a physical combustion simulation or experimental observation.

## Mission Intelligence limitations

The mission API validates and preserves the submitted scenario, retrieves available local and source-linked evidence, validates generated claims against retrieved records and citations, and identifies unsupported or missing evidence. The current five logical roles are:

1. Combustion Analyst
2. Atmosphere Analyst
3. Material Safety Analyst
4. Fire Suppression Analyst
5. Mission Safety Synthesizer

The first four perspectives are generated together and the synthesizer receives their validated structured results. Output quality and availability depend on server-side Gemini configuration, provider access, and quota. Automated workflow tests use mocked Gemini responses; they do not establish live provider availability. Unsupported claims may be omitted and the result marked partial. No output is a safety certification, flight clearance, or operational recommendation.

## Local development

### Prerequisites

- Python with versions compatible with `backend/requirements.txt`. The current development environment was tested with Python 3.15; the repository does not currently declare a minimum Python version.
- Node.js `^20.19.0` or `>=22.12.0`. The frontend `.nvmrc` pins 22.12.0; Node 22.12.0 or a supported newer release is recommended.
- npm and PowerShell for the optional smoke test.

On Windows with nvm-windows, install and select the pinned Node version:

```powershell
nvm install 22.12.0
nvm use 22.12.0
node --version
```

### Backend

From the repository root, create and activate a Python environment, install dependencies, and copy the safe environment template only if a local `.env` does not already exist:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pytest pytest-asyncio
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `backend/.env` locally if Gemini-powered features are needed. `GEMINI_API_KEY` is optional for non-AI endpoints and must remain server-side. Do not place it in frontend variables or commit `.env`.

Start the API from the `backend` directory:

```powershell
python run.py
```

The local API binds to `http://127.0.0.1:8000`; health is available at `/api/health`. In development, interactive documentation is at `/docs`. The default `DATABASE_URL` is `sqlite:///./flame_intelligence.db`, resolved relative to the backend working directory. On first startup, the application creates tables, applies additive migrations, and seeds local records. The database and SQLite journal sidecars are intentionally excluded from source control.

### Frontend

In a second terminal from the repository root:

```powershell
cd frontend
nvm use 22.12.0
npm ci --include=optional
npm run dev
```

Open `http://localhost:5173`. The development server proxies `/api` to the backend at `127.0.0.1:8000`.

## Tests and quality checks

Run the backend tests from `backend/`:

```powershell
python -m pytest -q
```

Run the frontend tests and quality checks from `frontend/`:

```powershell
npm test
npm run lint
npm run build
```

With the backend and frontend already running, the Windows smoke test can be run from `backend/`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tests\smoke.ps1
```

The automated tests mock Gemini generation. A live Gemini request is separate and may incur provider usage; it is not part of the routine test commands.

## Security and deployment status

This repository is configured for local development and demonstration, not public production deployment. The API currently has no user authentication, authorization, or rate limiting. In particular, the Gemini-consuming endpoints must not be exposed to the public internet without an approved authentication and rate-limiting design. Never embed a shared API secret in public frontend JavaScript.

The development runner binds to loopback. CORS is configured through `CORS_ORIGINS`; a deployment would need an explicit production origin allowlist, managed secrets, TLS, appropriate request limits, monitoring, and a deployment-specific operational plan. API documentation is disabled outside the development, dev, and local environment modes. SQLite is intended here for a local, single-instance prototype, not multi-worker or multi-host production storage.

## License

No `LICENSE` file is present in the current project. Choose and add a license before publishing the repository publicly; no license is implied by this README.
