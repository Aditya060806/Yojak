# SAS implementation status

## Implemented and executed locally

- Four-source audit, provenance hashes, deduplication and multiplicities.
- Connected grouping and frozen Analytics train/validation/calibration/test splits.
- Missing/truncated text representations and label-independent quality flags.
- Rule taxonomy and a 100-record manual-review export (labels still pending).
- Sparse logistic baseline, CUDA interval AFT and separate soft-target classification.
- Validation-based selection, band-label calibration, group-bootstrap QWK interval,
  multiplicity-weighted and complete-skill-list test summaries.
- Read-only frozen-test calibration audit across role, experience, truncation and
  heuristic-quality slices, with group-bootstrap uncertainty and small-group
  suppression. Does not refit, select models or change the calibration radius.
- Grouped nested cross-validation for JDS/SDS and aggregate associations.
- Company random-intercept analysis and held-out-employer baseline.
- Ecological title cross-check and before/after heuristic association rules.
- Training-only clustered cumulative-logit slope diagnostic and multinomial
  fallback, with cluster-aware coefficient intervals. Common effects are not
  primary when slope equality is rejected.
- Three disabled-by-default private API routes and a source-labelled Career Ladder.
- Existing coverage optimizer reused with explicit threshold and solver status.
- Fixed 144-scenario per-family planner benchmark with separate frequency,
  direct-greedy, surrogate-greedy and portfolio results; complete-only sensitivity
  and deterministic bounded-subset exact checks. Outputs stay private.
- Private SAS CSV bundle and Studio programs, without uploading anything.
- Paired conservative/permissive token refits on CUDA with frozen AFT settings,
  separate calibration, conditional paired group-bootstrap uncertainty and
  byte-hash checks preserving champion artifacts. Results are private and
  displayed in the performance page; they are not a new model selection.

## Pending or deliberately not claimed

- SAS login, executed Studio/Model Studio models and Visual Analytics dashboards.
- Independent manual role review and organizer confirmation of salary units.
- Independent cross-tool review of the asymptotic slope diagnostic and multinomial estimates.
- CatBoost challenger, transformer fine-tuning and embedding clustering.
- Verified geographic tiers and ESCO linkage for the new source.
- Prospective planner evaluation.
- Peak GPU-memory profiling and fully independent external validation.
- Prospective employment/learning impact; all current coverage results are simulations.

The optional dependency file enables further experiments; installing a library
does not mean that experiment has run. Do not describe this implementation as
the complete 20-hour research and submission plan. Private report and slide
generation is separate from statistical review and publication authorization.

The revised 26-page Word/PDF note is built by `scripts/sas/build_note_v4.py`
from private reports, prepared observations and genuine local application evidence.
It incorporates the salary-explanation diagnostic, reference synthesis, model
comparisons and explicit pending work. `scripts/sas/render_note_windows.py`
exports through installed Word and renders page images for visual review.
The existing PowerPoint is not refreshed by this workflow and needs separate review.
`--stage explain` writes a private standalone
`salary_explanation.json`; `--stage analyze` refreshes the integrated research report.
