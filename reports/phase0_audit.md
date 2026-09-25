# Phase 0 audit: SkillAlign as forked (2026-09-25)

Every result below was observed on this machine: Windows 11, Python 3.11.9, Node 24, and Neo4j Community 5.26.31 running natively on Java 17 with no Docker. The data was ESCO v1.2.x (English CSV, the 17 files the pipeline expects).

## What works

| Area | Result |
|---|---|
| Neo4j ETL | Loads 13,939 Skill, 3,039 Occupation, 640 SkillGroup, 619 OccupationGroup and 20 ConceptScheme nodes, and 126,051 `REQUIRES` edges |
| Pipeline | Completes in 104 s internally (169 s wall-clock including model load), once the Windows crash below is fixed |
| Catalog, skills, occupations, notes routes | 200 responses with correct data, 0.3 to 0.9 s each |
| `POST /recommendations` | The first call takes 9.5 s because the model loads lazily inside the request; later calls take 80 to 90 ms |
| Notes | Create, list, delete, and whitespace validation all work |

## What is broken (each item was reproduced)

| # | Problem | How to reproduce | Evidence |
|---|---|---|---|
| 1 | The pipeline crashes on Windows | `python -m ml_pipeline.run_pipeline` | `OverflowError` from `csv.field_size_limit(sys.maxsize)`. Fixed (see the note at the end). |
| 2 | The frontend does not compile | `npm run build` | `Can't resolve '@/lib/utils'` and `'@/lib/api'`. The folder doesn't exist, and `.gitignore` `lib/` would have ignored it anyway. |
| 3 | Every page returns HTTP 500 | `next dev`, then open `/`, `/recommendations`, `/explore`, `/roadmap`, `/admin`, `/admin/notes`, `/admin/health`, `/admin/settings` | All 8 pages return 500 |
| 4 | Essential vs optional is wrong in recommendations | Python + SQL recommendations | Matched skills are always labelled "essential" and missing ones always "optional" (the repo reads `r.relationType`, but the ETL writes `r.relation`) |
| 5 | Group labels show as codes | Same call | `groups: ['2521']` (the repo reads `g.preferredLabel`, but the ETL writes `label`) |
| 6 | Similarity scores are wrong and clamp to 0 | Same call | "data analyst" scores 0.0. FAISS returns squared L2 distance, and `ml.py` squares it again. |
| 7 | Hierarchical group filter is dead code | Code path | It traverses `broaderTransitive\|broader`, but the ETL creates `BROADER_THAN_OCC_GROUP` |
| 8 | Skill gap returns "Unknown" | `/occupations/<unknown>/skill-gap`, or a real occupation with filters that exclude every skill | 200 with `occupationLabel: "Unknown"` instead of a 404 or the real label |
| 9 | Health page endpoints are missing | `GET /admin/diagnostics/endpoints` and `/metrics` | 404 |
| 10 | The model reloads on every request | `POST /recommendations` while the FAISS index is missing | 112 s the first time, then 5.7 s on every later request |
| 11 | Notes metadata is incomplete | `PUT` a note, then `GET /notes` | `updatedAt: null` (the UI shows 1970), and `occupationLabel` is dropped by the schema |
| 12 | `data/` is not gitignored | `git check-ignore data/...` | `.gitignore` had an inline comment on the `data/` line, which git doesn't support. Fixed. |
| 13 | About 40% of occupations have no ISCO group edge | `rels-by-type` | Only 1,791 `IN_OCC_GROUP` edges for 3,039 occupations. The ETL drops occupation→occupation "broader" links, so child occupations never reach a group. |
| 14 | Config drift | Read the code | `ml.py` hard-codes the model name and paths; the data directory default is `./data/esco` in settings, `./data/raw` in `.env.example` and `./data/esco/` in the README; `.env.example` has no `NEO4J_*` variables |
| 15 | No tests and no CI | Repo | None exist |

## Risks for the Yojak build

- **Dataset licence.** The Naukri set (`shivamshrivastava21/indian-job-market-dataset-2025-2026`) is **CC BY-NC-SA 4.0**. A non-commercial hackathon entry is fine, but derived data must stay under NC-SA, and neither raw data nor row-level derived data may be committed.
- **Dates.** The dataset is one `.xlsx` published 2025-10-14, and `jobUploaded` is relative. The publish date is only an upper bound on the scrape date, so time-series claims will almost certainly not be supportable. This is to be confirmed in Phase 1.
- **Representativeness.** Naukri is formal-sector, urban and white-collar, so Tier-3 coverage will be thin.
- **Salary disclosure** is about 34%, which gives quantile models limited support.
- **Coverage gap.** About 40% of ESCO occupations lack an ISCO group edge (finding 13), which affects group filters and NCO mapping unless it is fixed.
- **HGT memory.** The Vyuha HGT does full-graph message passing. With about 100K jobs on a 6 GB GPU it may need subgraph batching.
- **Map boundaries.** The India map must use boundaries that follow the official claims, meaning the Survey of India index maps via datameet.

## Changes made during Phase 0

Two unavoidable fixes were made so the audit could run:
- `ml_pipeline/data_ingestion.py`: capped `csv.field_size_limit` at 2^31−1.
- `.gitignore`: repaired so data, tools and `.env` stay out of git and `app/frontend/lib/` can be tracked.
