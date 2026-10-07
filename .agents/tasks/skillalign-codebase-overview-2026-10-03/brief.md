# Brief: full read-only deep read of the SkillAlign codebase

## Goal
The user asked to "read the codebase properly". Produce one comprehensive, accurate map of the
SkillAlign repo that an orchestrator agent (who has NOT read the code) can rely on to answer
follow-up questions and to brief future implementation work without re-reading the code.

Write the report to:
`d:\Endeavors\Coding\Projects\SkillAlign\.agents\tasks\skillalign-codebase-overview-2026-10-03\report.md`

Repo root: `d:\Endeavors\Coding\Projects\SkillAlign` (Windows, PowerShell). Python venv at
`d:\Endeavors\Coding\Projects\SkillAlign\.venv` (use `.venv\Scripts\python.exe`).

## Known layout (from directory listings only; nothing has been read yet)
- Root: README.md, CREDITS.md, NOTICE, LICENSE, pyproject.toml, requirements.txt,
  requirements-dev.txt, .env.example, .github/workflows/ci.yml, docs/optimality.md, docs/images/,
  data/SOURCES.md
- Backend (Python, likely FastAPI): `app/api/main.py`
  - `app/api/routes/`: catalog, diagnostics, extract, graph, health, institution, jobs, labelling,
    notes, occupations, recommendations, recruiter, reports, salary, skills, student, workforce
  - `app/api/services/`: catalog, diagnostics, notes, occupations, recommendations, skills, yojak
  - `app/api/repos/`: catalog, diagnostics, notes, occupations, recommendations, skills
  - `app/api/schemas/`: catalog, diagnostics, notes, occupations, recommendations, skills, yojak
  - `app/core/`: deps, extract, metrics_middleware, ml, models, neo4j, serving, settings
  - Note: many routes (extract, graph, institution, jobs, labelling, recruiter, reports, salary,
    student, workforce) have no matching service/repo file. Find out where their data comes from.
- Frontend (Next.js app router, shadcn per components.json, Tailwind): `app/frontend/`
  - `app/(public)/`: evidence, explore, institution, network, recommendations, recruiter,
    roadmap, student, workforce, plus page.tsx/layout.tsx; `app/(admin)/admin`
  - `components/` (features, layout, ui, yojak), `hooks/`, `lib/` (api.ts, format.ts, static.ts,
    utils.ts), `services/` (catalog, diagnostics, labelling, notes, occupations, recommendations,
    skills, yojak .ts), `types/`, next.config.mjs, package.json
- ML pipeline: `ml_pipeline/` — run_pipeline.py, acquire.py, common.py, data_ingestion.py,
  data_processing.py, embedding_generator.py, evaluate_all.py, impact.py, neo4j_etl.py,
  reporting.py; subpackages graph/ (baselines, data, evaluate, hgt/, lightgcn, metrics),
  india/ (clean, geo, gold, link, load_neo4j, multilingual, nco, run), salary/ (model, evaluate),
  supply/ (geo_boundaries, parse, workforce), synthetic/ (candidates), upskilling/ (effort,
  engine, evaluate, market)
- Scripts: `scripts/` — build_evaluation.py, demo.py, export_static.py, impact.py, render_readme.py,
  personas.yaml, neo4j.ps1/.sh, run.ps1/.sh, setup.ps1/.sh
- Tests: `tests/` — conftest.py, fixtures/, test_api_regressions, test_components, test_core,
  test_india_clean_geo, test_india_link_gold, test_integration_neo4j, test_pipeline_esco,
  test_recommendations, test_upskilling_engine, test_yojak_api
- Data/outputs: `data/` (raw, processed, reference, gold), `artifacts/` (cache, graph, logs,
  readme-validation, salary, synthetic, upskilling, workforce), `reports/` (data_quality.json,
  EVALUATION.md, impact.json, model_comparison.json, multilingual_eval.json, phase0_audit.md,
  salary_eval.json, upskilling_eval.json, workforce_summary.json)
- `tools/neo4j`, `tools/neo4j-test`, `tools/neo4j.zip` (bundled Neo4j distribution; don't read binaries)

## Questions the report must answer
1. Purpose and domain: what SkillAlign does, who the personas are (student, recruiter,
   institution, workforce/policy, admin), what "Yojak" is, and the data sources (ESCO, India NCO,
   etc.). Include a short glossary of domain terms.
2. Tech stack and tooling: Python version, key libraries (pin versions), lint/format/type tools,
   pytest config and markers, CI steps in ci.yml, frontend framework versions and npm scripts.
3. Configuration: every setting in app/core/settings.py with defaults and env var names; the key
   names in .env.example. Feature flags, static/offline modes, fallbacks when Neo4j is absent.
4. Backend architecture: app startup/lifespan in main.py, middleware (metrics, CORS), dependency
   injection in deps.py, the routes -> services -> repos layering and where it's bypassed.
   Give a FULL endpoint inventory table: method, path, handler file:function, data source
   (Neo4j query / artifact file / in-memory model), request and response schema, auth required?
5. Graph data model: Neo4j node labels, relationship types, key properties, constraints and
   indexes, and which code writes them (neo4j_etl.py, india/load_neo4j.py) vs reads them (repos).
6. ML pipeline: stage order and CLI of run_pipeline.py and india/run.py; for each module, inputs
   (data/raw, data/reference, data/gold), outputs (data/processed, artifacts/*, reports/*), and
   algorithms (embedding model names, HGT/LightGCN/baselines, salary model, upskilling engine,
   synthetic candidates, workforce supply). Summarize the headline metrics from reports/*.json and
   reports/EVALUATION.md.
7. Serving: how app/core/ml.py, serving.py and extract.py load and use pipeline artifacts at
   runtime (which files, when loaded, caching, failure behavior).
8. Frontend: map each page/route to the components, hooks and services it uses and to the backend
   endpoints those services call. Explain lib/api.ts (base URL, error handling) and lib/static.ts
   (static export mode?) plus scripts/export_static.py. Flag any frontend call with no matching
   backend route, or backend route unused by the frontend.
9. Tests: what each test file covers, fixtures used, which need Neo4j or artifacts, and gaps.
10. How to run locally end to end on Windows (setup, Neo4j, pipeline, API, frontend) with the
    exact commands from scripts/*.ps1 and README.
11. Code health: TODO/FIXME/HACK markers, dead or duplicated code, inconsistencies between README
    and code, hardcoded paths, Windows-specific pitfalls, error-handling gaps, and security
    observations (auth on admin/labelling/notes write endpoints, CORS, input validation, Cypher
    injection risk, secrets handling). Rank the top issues by impact.
12. Git state: current branch, last ~15 commits (one line each), and any uncommitted changes
    (`git status --short`, `git log --oneline -15`).

## Verification (run these and report actual results; don't guess)
- `.venv\Scripts\python.exe -m pytest -q` (skip or deselect tests that need a live Neo4j server if
  they would hang; report what was skipped and why). Use a timeout.
- `.venv\Scripts\python.exe -m ruff check .` (report counts, don't fix).
- In `app/frontend`: `npx tsc --noEmit` and `npm run lint` if defined (node_modules exists).
  Use timeouts; if any fail to run, say why.
- Mark every claim in the report as verified (read/ran) or inferred.

## Constraints
- READ-ONLY. Do not modify, format, or delete any source, config, data, or artifact file. The only
  file you may create is the report (create parent folders if missing).
- Do NOT open or print values from `.env`. Use `.env.example` for key names only.
- Skip `.venv`, `node_modules`, `.next`, `.git` internals, `__pycache__`, `.ruff_cache`, and
  binaries under `tools/`.
- For large data files, inspect headers/first rows and sizes only.
- Do not start long-running processes (uvicorn, `next dev`, Neo4j) and do not run the ML pipeline
  or anything that downloads data or makes outbound network calls.

## Report format
Markdown with these top-level sections: Summary (10 lines max), Architecture diagram (mermaid),
then one section per question above. Cite `path:line` for key claims. Dense tables over prose.
Aim for completeness over brevity; this report replaces re-reading the code.
