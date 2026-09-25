# Optimality of the upskilling planner

This note explains what Yojak optimises when it recommends "the next *k* skills to learn", which guarantees hold, which do not, and how we measure the difference. The code is `ml_pipeline/upskilling/engine.py`, and the measured results are in `reports/upskilling_eval.json`.

## Setup

- A person knows a set of skills **S**.
- Their target pool is a set of postings **J**, for example every posting in their ISCO sub-major group and experience band.
- Posting *j* lists the ESCO skills **R_j**.
- Each skill *s* has an integer weight **w_s** = round(1000 × (log((1+N)/(1+df_s)) + 1)), where *N* is the number of postings and *df_s* the number that list *s*. The weights are IDF-style, so rare, specific skills count for more than generic ones.

The **fit** of posting *j* for a skill set *T* is the weighted share of its skills that *T* covers:

    fit(T, j) = Σ_{s ∈ R_j ∩ T} w_s  /  Σ_{s ∈ R_j} w_s

Posting *j* is **eligible** when fit(T, j) ≥ τ, for τ ∈ {0.4, 0.6, 0.8}. Weights are integers and τ is a whole percentage, so eligibility is decided in exact integer arithmetic. Every algorithm, and the exact ILP, therefore agree on exactly the same objective.

Each posting has a value **v_j**: 1 to count postings, or the posting's predicted median salary (P50 from the salary model) to weight by pay.

## Two objectives

**True objective.** This is what the person actually cares about, the value of postings that become eligible:

    F(A) = Σ_j v_j · 1[ fit(S ∪ A, j) ≥ τ ]

**Surrogate:**

    G(A) = Σ_j v_j · min(1, fit(S ∪ A, j) / τ)

Both are monotone: adding a skill never lowers the objective. G ≥ F pointwise, since a job's G term is 1 exactly when it is eligible. G also rewards partial progress towards eligibility.

## F is not submodular

A set function is submodular when marginal gains shrink as the set grows: f(A ∪ {s}) − f(A) ≥ f(B ∪ {s}) − f(B) for all A ⊆ B.

**Counterexample.** Take one posting that requires {a, b} with equal weights, and τ = 1:

- F({b}) − F(∅) = 0, since *b* alone does not make the posting eligible.
- F({a, b}) − F({a}) = 1, since *b* completes it.

The gain from *b* grew when *a* was added, so F is not submodular. The same thing happens whenever a posting needs two or more missing skills to cross τ. The greedy (1 − 1/e) guarantee therefore **does not apply to F**. `tests/test_upskilling_engine.py::test_F_is_not_submodular_counterexample` reproduces this.

## G is monotone submodular

For one posting, let c(A) = Σ_{s ∈ R_j ∩ (S ∪ A)} w_s. This is a non-negative modular (additive) function of A. The posting's term in G is v_j · min(1, c(A) / (τ W_j)), a non-decreasing **concave** function of a non-negative modular function, and such compositions are monotone submodular. G is a non-negative weighted sum of these terms, so it is monotone submodular too.

So, by Nemhauser, Wolsey and Fisher (1978), **greedy on G returns A with G(A) ≥ (1 − 1/e) · max_{|B| ≤ k} G(B)**. Lazy greedy (Minoux, 1978) gives the same answer faster, by re-evaluating stale gains only when they reach the top of the heap. `test_lazy_greedy_matches_naive` checks that the two agree, and `test_greedy_meets_one_minus_one_over_e_on_G` checks the bound against brute force on random instances.

**What this guarantee is not.** It bounds G, not F. A plan that is near-optimal for G can be far from optimal for F, and we measured this directly. G rewards partial progress on every posting, much as counting skill frequency does. So on real pools, lazy greedy on G often picks the same skills as "top-k by frequency", while plans that *complete* specific postings unlock many more of them.

## What Yojak ships, and why

Guarantees on the wrong objective are not useful to a student, so we evaluate everything on **F**, against its exact optimum:

| Method | Guarantee | Role |
|---|---|---|
| Top-k by frequency | none | baseline; what most career tools do |
| Lazy greedy on G | (1 − 1/e) on G only | surrogate method |
| Greedy on F (ties broken by G gain) | none in theory | fast heuristic for the true objective |
| CP-SAT ILP on F | exact within the time limit; otherwise a feasible plan plus a **proven upper bound** | ground truth for the optimality gap |

The ILP is:

    maximise   Σ_j v_j y_j
    subject to 100 · (base_j + Σ_{s ∈ R_j \ S} w_s x_s) ≥ τ% · W_j · y_j     for every not-yet-eligible posting j
               Σ_s x_s ≤ k             (or Σ_s cost_s x_s ≤ budget)
               x_s, y_j ∈ {0, 1}

Only skills that appear in some posting that could still become eligible are modelled. Any other skill cannot change F, so dropping it is exact, not a heuristic. The solver is warm-started with the greedy plan, so it never returns anything worse.

`reports/upskilling_eval.json` reports each method's mean F, its **optimality gap** (mean and 95th percentile), how often it is exactly optimal, its gain over frequency, and its runtime. It also gives a **guaranteed upper bound on the gap** computed from the solver's proven bound, for instances where optimality wasn't proven within the time limit. The API uses the method the evaluation supports: greedy on F for instant answers, refined by the ILP under a short time limit, and it states in the response which one produced the plan.

## Effort-aware variant

Each candidate skill gets an effort weight *e_s*, a documented heuristic from `ml_pipeline/upskilling/effort.py`:
- **ESCO reuse level:** transversal skills are assumed quicker to pick up than occupation-specific ones.
- **Closeness:** 0.7× when the skill is an ESCO "related" skill of, or shares a small skill group with, something the person already knows.

It is **not** measured learning time, and users can override it.

With a budget B, the problem is to maximise G(A) subject to Σ_{s ∈ A} e_s ≤ B.

- **Cost-benefit greedy plus the best single affordable skill** gives a (1 − 1/e)/2 approximation on G (Khuller, Moss and Naor, 1999).
- **Partial enumeration.** Every affordable seed set of size ≤ 3, extended greedily, gives (1 − 1/e) (Sviridenko, 2004). We implement seeds of size ≤ 2, which is practical at interactive latency. It therefore carries no worst-case guarantee beyond the size-1 bound, and its actual gap to the budgeted ILP optimum is measured and reported, not assumed.

## Salary shift per step

For each recommended skill, the planner reports the postings it unlocks, and the salary shift: the P50 of the newly eligible postings minus the P50 of those already eligible, **as a range** (P10–P90 across those postings). It is never a single number. It describes *posted* pay for postings that become reachable, not a promise of earnings.

## References

- Nemhauser, Wolsey and Fisher (1978). An analysis of approximations for maximizing submodular set functions. *Mathematical Programming* 14.
- Minoux (1978). Accelerated greedy algorithms for maximizing submodular set functions.
- Khuller, Moss and Naor (1999). The budgeted maximum coverage problem. *Information Processing Letters* 70.
- Sviridenko (2004). A note on maximizing a submodular set function subject to a knapsack constraint. *Operations Research Letters* 32.
