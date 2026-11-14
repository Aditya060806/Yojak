# Jury preparation

1. **Why not report accuracy alone?** Bands are ordered. QWK, mean band error,
   within-one-band accuracy and macro-F1 reveal different error patterns. We
   retain raw metrics rather than substituting a misleading ceiling ratio.
2. **What is the empirical agreement bound?** The sum of majority-label counts
   within identical observed-feature groups, divided by the number of rows.
   This is a descriptive in-sample property, not a generalization guarantee.
3. **Why AFT?** It uses interval likelihood rather than treating a midpoint as
   an observed exact salary. Its distributional assumptions remain limitations.
4. **How are soft targets different?** They represent training-group frequencies
   over six categories. They are not the interval-regression target.
5. **Does 90 percent coverage guarantee my pay?** No. Calibration concerns posting
   band labels under exchangeability. A profile scenario is a different input
   population, and exact salary was not observed.
6. **Does the title comparison prove annual lakhs?** No. Similar scales across
   aggregated files are a plausibility check. Authoritative unit confirmation
   remains pending.
7. **How is leakage prevented?** Connected shared-feature/ID groups stay together;
   preprocessing fits only training rows; validation selects candidates and a
   separate calibration partition constructs sets. Earlier exploration and any
   repeated evaluation must still be disclosed.
8. **Do technical skills cause salary hikes?** These cohort associations cannot
   establish that. Confounding, repeated records, measurement and sample size
   restrict interpretation. A prospective intervention study would be needed.
9. **Is personality used for hiring?** No. SDS is aggregate exploratory research;
   no individual personality, suitability, promotion or hiring score is served.
10. **Why use CUDA here?** Interval and soft-target boosting were actually run
    on CUDA. Small trait tables stay on CPU. Library installation alone is not
    evidence that a particular model ran.
11. **What has SAS executed?** Until approved access is available: nothing. The
    import bundle and programs are prepared, explicitly marked not executed.
    Do not describe prepared scripts as software validation.
12. **What is real-world impact?** Current learning results are simulated coverage
    improvements under a stated threshold and budget, not observed placements.
13. **What does optimal mean?** Only a solver-proven result is labelled optimal.
    Larger pools use compared greedy strategies without a global-optimum claim.
14. **What remains incomplete?** Consult SAS_IMPLEMENTATION_STATUS.md. Formal
    ordinal diagnostics, human role labels, certain challengers and authorized
    SAS execution must not be presented as complete.
