# Credits

Yojak was built for **Build for Bharat 2.0** on top of two existing codebases. This file says exactly what came from each and what is new. Licences for data sources are in [NOTICE](NOTICE).

## From SkillAlign (MIT, by Yasser Khattach)

Forked from [github.com/Y4SSERk/SkillAlign](https://github.com/Y4SSERk/SkillAlign), last upstream commit `cf0681d`. The MIT licence and copyright in [LICENSE](LICENSE) are unchanged.

Inherited, then fixed or extended in Yojak:

| Area | Files | What Yojak changed |
|---|---|---|
| FastAPI app layout (routes, services, repos, schemas) | `app/api/**` | Lifespan startup, latency middleware, generic 500s, admin-token guard, new routes |
| Neo4j client and DI | `app/core/neo4j.py`, `app/core/deps.py` | Admin guard added |
| ML engine (mpnet + FAISS) | `app/core/ml.py` | Correct cosine from squared L2, load-once caching, settings-driven paths |
| ESCO pipeline | `ml_pipeline/data_ingestion.py`, `data_processing.py`, `embedding_generator.py`, `neo4j_etl.py`, `run_pipeline.py` | Windows CSV fix, string dtypes, altLabels, occupation→ISCO links for all occupations, batching, stage selection |
| Recommendation, skill-gap, notes, catalog, diagnostics endpoints | `app/api/{routes,services,repos}/*` | Fixed property names, filters, 404s, notes metadata, new diagnostics |
| Next.js frontend (base layout, shadcn/ui primitives) | `app/frontend/**` | Missing `lib/` restored, bugs fixed, then fully redesigned (see below) |

The Phase 0 audit of the inherited code is in [reports/phase0_audit.md](reports/phase0_audit.md).

## From Vyuha (our team's repo)

Source: [github.com/TrombokenduShiv/Vyuha](https://github.com/TrombokenduShiv/Vyuha), commit `cef4a130bdd66e6499df27ab43f9eaa8357dfa76`. Vyuha has no licence file. It is our own team's code, reused here by its authors.

| Vyuha file | Used in Yojak as |
|---|---|
| `ml/graph/model/hgt.py`: `HGTAttentionLayer` | Copied unchanged into `ml_pipeline/graph/hgt/` |
| `ml/graph/model/hgt.py`: `HGTModel` | Rewritten for job/skill/company/city/occupation/experience nodes with a link-prediction head |
| `ml/graph/model/temporal_encoder.py` | Copied. Only used if real posting timestamps exist (see reports) |
| `ml/graph/training/train_hgt.py` | Training-loop structure (AdamW, cosine LR, early stopping) adapted; focal loss replaced with BCE/BPR plus negative sampling |
| `ml/graph/data/loader.py` | Validation ideas reused: duplicate-ID checks, dangling-edge checks, hash-based splits |

## New in Yojak

Everything else was written for this project, including:

- The India data layer (Naukri cleaning, city→state→tier, skill and title linking to ESCO, NCO-2015 mapping, data-quality report)
- Baselines, evaluation harness and model comparison
- Optimal upskilling engine (lazy greedy, exact ILP, effort-aware budgeted variant)
- Salary quantile models with conformal calibration and a selection-bias analysis
- Stakeholder views (student, recruiter, institution, workforce planner) and the evidence pages
- The test suite, CI, and local setup scripts

## Data

ESCO (CC BY 4.0), the Naukri dataset (CC BY-NC-SA 4.0), GeoNames (CC BY 4.0), DataMeet / Survey of India boundaries, and AISHE, PLFS and NCO-2015 government publications. Full attributions are in [NOTICE](NOTICE), and URLs with retrieval dates are in [data/SOURCES.md](data/SOURCES.md).
