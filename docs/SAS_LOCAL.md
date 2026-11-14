# Private SAS analytics

The hackathon data and all derived reports live outside public exports. Nothing in
this workflow uploads files or commits them. Do not enable the private API on a
public host. SAS platform access and transfer authorization must be verified by
the organizer before uploading the generated CSV bundle.

## Run

From the repository root, using the existing Python 3.11 environment:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-sas.txt
.venv/Scripts/python.exe -m ml_pipeline.sas.run --stage all
```

Stages `prepare`, `train`, `analyze`, `explain`, `benchmark`, `calibration-audit`,
and `package` can run separately. CUDA is
required by the training stage unless `--cpu` is explicitly supplied. CPU mode
trains a logistic baseline only. Inputs default to `SAS Data Problem Statement`;
`--source` accepts another local input directory. Outputs always go to the ignored
`private_sas` directory, never `app/frontend/public`.

```powershell
$env:YOJAK_SAS_LOCAL = '1'
.venv/Scripts/python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Open `/career-ladder` in the existing frontend. Changing any profile input hides
stale results. `/sas/match`, `/sas/plan`, and `/sas/pay-range` accept JSON with
`role_family`, `experience`, `skills`, and `complete_only`. Without the environment
flag these routes return 503 before loading private artifacts. Never point the
public Vercel frontend at this local private API.

## Interpretation

- Group-disjoint Analytics partitions are approximately 60/15/10/15 percent.
- Calibration concerns observed salary-band labels, not true continuous salaries.
- Scenario predictions for user profiles are outside the posting-calibration
  population; their coverage is not guaranteed.
- The identical-feature agreement bound is an empirical diagnostic, not a
  universal limit or explanation for every model error.
- JDS and SDS are separate aggregate research cohorts, never individual scorers.
- The title cross-check does not establish salary units or external validity.
- Role review is a pending human task in `private_sas/role_review.csv`.
- SAS scripts being present does not mean SAS executed them.

Before distribution, inspect package status, uncertainty, missing analyses and
data permissions. Generated submission files are working drafts until visual QA
and human review are complete. Do not publish private screenshots or reports.

## Planner benchmark

Run `.venv/Scripts/python.exe -m ml_pipeline.sas.run --stage benchmark` to write
`private_sas/planner_benchmark.json` and its Markdown summary. The frozen grid
uses each observed role family, experience 0/3/7, three declared hypothetical
profiles and all-list/complete-list views. Quality-flagged records are excluded.
Full-pool methods share the same observations and vocabulary. Exact checks are
limited to 500 rows and 200 candidate skills, with a one-second solver budget.
A separate deterministic subset of up to 40 observations preserves every selected
posting's skill denominator; its optimum applies only to that subset.

Portfolio noninferiority to frequency is guaranteed by including frequency as a
candidate. Separate greedy results and exact gaps make this visible. These are
overlapping scenario evaluations, not independent people or employment trials.
The benchmark does not tune the salary model or overwrite the reviewed approach
note. Integrate its new results into submission documents only after review.

## Frozen calibration audit

Run `.venv/Scripts/python.exe -m ml_pipeline.sas.run --stage calibration-audit`.
The private JSON and Markdown outputs verify that saved predictions cover exactly
the test partition, match prepared labels and reproduce the frozen calibration
radius. They report coverage and set width by role, experience midpoint,
truncated-list flag and heuristic-quality flag. Cells need 30 observations and
20 group identifiers; unsupported cells retain counts without estimated coverage.

Uncertainty uses 500 seeded group-bootstrap draws with the model and radius fixed.
It is not full training uncertainty or a simultaneous subgroup guarantee. Perfect
observed coverage may yield a degenerate bootstrap interval, not certainty.
No model is tuned and no calibration data is reused for selection by this stage.

## Safe packaging

`--stage package` refreshes the private SAS exchange bundle and writes
`submission/submission_readiness.json` plus a readable Markdown checklist.
It does not author or overwrite Word/PDF files. Readiness compares current
evidence hashes with the note build manifest and identifies missing, changed
or newly generated evidence. Even matching hashes require human review.
Document authoring and rendering are separate explicit commands documented above.

## Model performance page

### Token sensitivity

Run `.venv/Scripts/python.exe -m ml_pipeline.sas.run --stage sensitivity` for
two matched AFT refits. This explicit opt-in stage is not part of `all` and
requires a saved AFT champion. `--cpu` explicitly uses CPU for both refits.
The original winning settings and round count are fixed, with no further
search. Each variant fits its own training-only vocabulary and scaler and
calibrates on the original calibration rows. Test rows and groups stay paired.

Results go to `private_sas/truncation_sensitivity.json`; per-variant predictions
go to `private_sas/sensitivity/`. Source, model, original predictions and salary
report hashes must stay unchanged. The API rejects stale sensitivity evidence.
The reported interval resamples test groups, not training runs. A difference
interval crossing zero does not establish a predictive benefit. This is
post-hoc robustness evidence, not a license to select on the test set.
Packaging flags this new evidence until it is incorporated into a reviewed note;
the existing Word/PDF files are never silently overwritten.

### Evaluation interface

Open `/model-performance` from the Career Ladder workspace. Its read-only
`GET /sas/performance` endpoint requires the same `YOJAK_SAS_LOCAL=1` flag and
returns aggregate evidence only, with `Cache-Control: no-store`. Exact band
accuracy and the confusion matrix are computed from saved test predictions
after matching their keys, labels and calibrated boundaries to prepared data.
No training runs from a page request.

The page separates validation candidate comparisons, champion test metrics,
calibration slices and grouped cohort research. Missing or stale optional
reports are explicitly unavailable. Legacy research needs a matching evidence
build manifest to establish source linkage. Public demo mode never requests or
substitutes a confidential performance snapshot.

For browser regression checks, set `CODEX_NODE_MODULES` to the bundled runtime's
node_modules directory and run `node scripts/sas/check_performance_ui.cjs` with
the local frontend and backend active. Screenshots stay in ignored
`private_sas/performance_ui`. The check uses installed Edge in headless mode.
