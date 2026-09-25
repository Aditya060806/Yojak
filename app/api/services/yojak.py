# app/api/services/yojak.py

"""Business logic for the four stakeholder views. Routes stay thin; everything is explainable here."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.core.extract import SkillExtractor, skill_set_from, top_k
from app.core.serving import Serving

LOW_DEMAND_SHARE = 0.002  # a syllabus skill in < 0.2% of in-scope postings has "low current demand"


# --- helpers -----------------------------------------------------------------------------------------

def _srv() -> Serving:
    return Serving.get()


def _ref(uri: str) -> dict:
    return {"uri": uri, "label": _srv().skill_labels.get(uri, uri)}


def _pool_rows(req) -> np.ndarray:
    return _srv().market.pool(exp_bands=req.exp_bands or None, tiers=req.tiers or None, states=req.states or None)


def _fit(rows: np.ndarray, have: list[int]) -> np.ndarray:
    m = _srv().market
    mask = np.zeros(len(m.skills), dtype=np.int64)
    mask[have] = 1
    R = m.R[rows]
    total = R @ m.w
    covered = R @ (m.w * mask)
    return np.where(total > 0, covered / np.maximum(total, 1), 0.0)


def _median_range(rows: np.ndarray) -> dict | None:
    if len(rows) == 0:
        return None
    m = _srv().market
    from ml_pipeline.salary.model import MIN_SUPPORT

    disclosed = int(m.jobs["salary_disclosed"].to_numpy()[rows].sum())
    return {"p10": round(float(np.median(m.p10[rows])), -3), "p50": round(float(np.median(m.p50[rows])), -3),
            "p90": round(float(np.median(m.p90[rows])), -3), "n_support": disclosed,
            "sufficient": disclosed >= MIN_SUPPORT}


def _resolve(req) -> tuple[list[str], dict | None, list[int]]:
    uris, extraction = skill_set_from(req.skills, req.text, req.language)
    have = _srv().skill_indices(uris)
    return uris, extraction, have


def _source_of(uri: str, extraction: dict | None) -> str | None:
    if not extraction:
        return None
    for s in extraction["skills"]:
        if s["uri"] == uri:
            return s["source_text"]
    return None


# --- extraction --------------------------------------------------------------------------------------

def extract(text: str, language: str | None) -> dict:
    return SkillExtractor.get().extract(text, language)


# --- student: match ---------------------------------------------------------------------------------

def student_match(req) -> dict:
    srv = _srv()
    m = srv.market
    uris, extraction, have = _resolve(req)
    rows = _pool_rows(req)
    scores = srv.ranker.score(have, rows)
    fits = _fit(rows, have)
    have_set = set(have)
    jobs_out = []
    for i in top_k(scores, req.limit):
        r = int(rows[i])
        job = m.jobs.iloc[r]
        skills = m.R[r].indices
        matched = [int(s) for s in skills if s in have_set]
        missing = sorted([int(s) for s in skills if s not in have_set], key=lambda s: -m.w[s])
        contrib = srv.ranker.occlusion(have, r) if have else {}
        paths = []
        for s in matched[:3]:
            uri = m.skills[s]
            src = _source_of(uri, extraction)
            path = ([{"kind": "your input", "label": src}] if src else []) + [
                {"kind": "ESCO skill", "label": srv.skill_labels.get(uri, uri), "uri": uri},
                {"kind": "posting", "label": f"{job['title']} ({job['companyName']})", "uri": job["jobId"]},
            ]
            if job["occupation_uri"]:
                path.append({"kind": "ESCO occupation", "label": job["occupation_label"], "uri": job["occupation_uri"]})
            paths.append(path)
        jobs_out.append({
            "job_id": job["jobId"], "title": job["title"], "company": job["companyName"],
            "city": job["primary_city"], "state": job["primary_state"],
            "tier": None if pd.isna(job["primary_tier"]) else int(job["primary_tier"]),
            "exp_band": job["exp_band"], "occupation_uri": job["occupation_uri"],
            "occupation_label": job["occupation_label"], "nco_family": job.get("nco_family"),
            "score": round(float(scores[i]), 5), "fit": round(float(fits[i]), 4),
            "salary": srv.salary_range_for_rows(np.array([r]))[0],
            "why": {
                "matched_skills": [_ref(m.skills[s]) for s in matched],
                "missing_skills": [_ref(m.skills[s]) for s in missing[:8]],
                "contributions": sorted(({"skill": _ref(m.skills[s]), "score_drop": d} for s, d in contrib.items()),
                                        key=lambda c: -c["score_drop"])[:6],
                "paths": paths,
                "model": srv.model_choice["served_name"],
            },
        })

    # Roles: aggregate the best 500 postings by ESCO occupation.
    best = top_k(scores, 500)
    occ = m.jobs["occupation_uri"].to_numpy()
    agg: dict[str, float] = {}
    for i in best:
        o = occ[rows[i]]
        if o:
            agg[o] = agg.get(o, 0.0) + float(scores[i])
    roles = []
    labels = dict(zip(m.jobs["occupation_uri"], m.jobs["occupation_label"], strict=False))
    nco = dict(zip(m.jobs["occupation_uri"], m.jobs["nco_family"], strict=False))
    for o, sc in sorted(agg.items(), key=lambda kv: -kv[1])[:8]:
        o_rows = rows[occ[rows] == o]
        counts = np.asarray(m.R[o_rows].sum(axis=0)).ravel()
        counts[have] = 0
        top_missing = [int(s) for s in np.argsort(-counts)[:6] if counts[s] > 0]
        profile = srv.occupation_profiles.get(o, {})
        essential_have = [u for u, t in profile.items() if t == "essential" and u in set(uris)]
        roles.append({
            "occupation_uri": o, "occupation_label": labels.get(o, o), "nco_family": nco.get(o),
            "postings": int(len(o_rows)), "score": round(sc, 4), "salary": _median_range(o_rows),
            "top_missing": [_ref(m.skills[s]) for s in top_missing],
            "why": {"matched_skills": [_ref(u) for u in essential_have[:8]],
                    "missing_skills": [_ref(m.skills[s]) for s in top_missing],
                    "paths": [[{"kind": "your skills", "label": f"{len(have)} skills"},
                               {"kind": "matching postings", "label": f"{int((occ[rows[best]] == o).sum())} of the top 500"},
                               {"kind": "ESCO occupation", "label": labels.get(o, o), "uri": o}]],
                    "notes": [f"Missing skills are the ones postings for this role list most often "
                              f"({len(o_rows)} postings in your filters)."],
                    "model": srv.model_choice["served_name"]},
        })
    return {"skills": [_ref(u) for u in uris], "extraction": extraction, "roles": roles, "jobs": jobs_out,
            "pool_size": int(len(rows)), "model": srv.model_choice, "salary_caveat": srv.salary_caveat}


# --- student: optimal plan --------------------------------------------------------------------------

def _plan_steps(problem, rows, plan_skills, have, costs, overrides, value_kind) -> dict:
    srv = _srv()
    m = srv.market
    unlocked = problem.jobs_unlocked_by(plan_skills)
    eligible_before = problem.eligible(problem.base)
    before_rows = rows[eligible_before]
    base_p50 = float(np.median(m.p50[before_rows])) if len(before_rows) else None
    steps, cum = [], int(eligible_before.sum())
    for s, jobs_idx in zip(plan_skills, unlocked, strict=True):
        cum += len(jobs_idx)
        u_rows = rows[np.array(jobs_idx, dtype=np.int64)] if jobs_idx else np.array([], dtype=np.int64)
        shift = None
        if len(u_rows) and base_p50:
            d = m.p50[u_rows] - base_p50
            shift = {"p10": round(float(np.percentile(d, 10)), -3), "p50": round(float(np.percentile(d, 50)), -3),
                     "p90": round(float(np.percentile(d, 90)), -3)}
        eff = srv.effort.explain(int(s), np.array(have, dtype=np.int64))
        uri = m.skills[s]
        if uri in overrides:
            eff = {**eff, "effort": float(overrides[uri]), "note": "set by you"}
        examples = [f"{m.jobs.iloc[r]['title']} ({m.jobs.iloc[r]['companyName']})" for r in u_rows[:3]]
        steps.append({
            "skill": _ref(uri), "jobs_unlocked": len(jobs_idx), "cumulative_eligible": cum, "effort": eff,
            "salary_of_unlocked": _median_range(u_rows), "salary_shift_p50": shift,
            "why": {"matched_skills": [], "paths": [[{"kind": "learn", "label": srv.skill_labels.get(uri, uri), "uri": uri},
                                                     {"kind": "becomes eligible for", "label": e}] for e in examples],
                    "notes": [f"Unlocks {len(jobs_idx)} posting(s) that were below the fit threshold."]},
        })
    return {"steps": steps, "eligible_before": int(eligible_before.sum()),
            "eligible_after": cum, "value_after": round(problem.F(plan_skills), 2)}


def student_plan(req) -> dict:
    from ml_pipeline.upskilling.engine import budgeted_partial, exact_ilp, frequency, greedy_F

    srv = _srv()
    m = srv.market
    uris, extraction, have = _resolve(req)
    notes = []
    occ, isco2 = req.target_occupation, req.target_isco2
    if not occ and not isco2:
        best = top_k(srv.ranker.score(have), 200)
        codes = m.jobs["isco_code"].to_numpy()[best]
        codes = [str(c)[:2] for c in codes if c]
        isco2 = max(set(codes), key=codes.count) if codes else None
        notes.append(f"No target given: using ISCO group {isco2}, the most common among your best-matching postings.")
    rows = m.pool(occupation_uri=occ, isco2=isco2, exp_bands=req.exp_bands or None, tiers=req.tiers or None,
                  states=req.states or None)
    if len(rows) == 0:
        raise ValueError("No postings match that target and those filters; widen the filters.")
    problem = m.problem(rows, np.array(have, dtype=np.int64), req.tau, req.value)
    cands = problem.candidates()
    gf = greedy_F(problem, req.k, cands)
    ilp = exact_ilp(problem, req.k, cands=cands, time_limit=1.5, hint=gf.skills)
    best = ilp if ilp.F >= gf.F else gf
    method = ("exact optimum (ILP, proven)" if best is ilp and ilp.optimal else
              "best found: greedy on F refined by ILP (1.5 s limit; optimality not proven)")
    fq = frequency(problem, req.k)
    overrides = req.effort_overrides or {}
    costs = srv.effort.costs(np.array(have, dtype=np.int64))
    for u, e in overrides.items():
        if u in m.skill_index:
            costs[m.skill_index[u]] = float(e)
    effort_plan = None
    if req.budget:
        bp = budgeted_partial(problem, costs, req.budget, cands, max_seeds=80, seed_pool=12)
        effort_plan = {"method": f"effort-aware (budget {req.budget:g}): partial enumeration + cost-benefit greedy",
                       "optimal": None, **_plan_steps(problem, rows, bp.skills, have, costs, overrides, req.value)}
    notes.append(f"Eligible = at least {req.tau:.0%} of a posting's skills (weighted by rarity) are covered.")
    notes.append("Effort weights are a heuristic (skill breadth, closeness to what you know), not measured learning time.")
    return {
        "pool": {"postings": int(len(rows)), "occupation_uri": occ, "isco2": isco2, "tiers": req.tiers,
                 "exp_bands": req.exp_bands, "value": req.value},
        "skills": [_ref(u) for u in uris], "extraction": extraction,
        "optimal_plan": {"method": method, "optimal": bool(best is ilp and ilp.optimal),
                         **_plan_steps(problem, rows, best.skills, have, costs, overrides, req.value)},
        "frequency_plan": {"method": "top-k most frequent skills (what most tools recommend)", "optimal": None,
                           **_plan_steps(problem, rows, fq.skills, have, costs, overrides, req.value)},
        "effort_plan": effort_plan, "notes": notes,
    }


# --- recruiter --------------------------------------------------------------------------------------

def recruiter_rank(jd_text: str | None, jd_skills: list[str], resumes: list[tuple[str, bytes]],
                   limit: int, include_synthetic: bool) -> dict:
    from app.core.extract import read_upload

    srv = _srv()
    m = srv.market
    uris, extraction = skill_set_from(jd_skills, jd_text)
    jd = [u for u in uris if u in m.skill_index]
    if not jd:
        raise ValueError("No ESCO skills found in the job description; add skills or more detail.")
    w = {u: float(m.w[m.skill_index[u]]) for u in jd}
    total = sum(w.values())
    pool = []
    if include_synthetic and len(srv.candidates):
        for r in srv.candidates.itertuples(index=False):
            pool.append({"candidate_id": r.candidate_id, "synthetic": True, "source": "synthetic demo pool",
                         "occupation_label": r.occupation_label, "city": r.city,
                         "tier": None if pd.isna(r.tier) else int(r.tier), "exp_band": r.exp_band,
                         "skills": set(r.skill_uris)})
    ex = SkillExtractor.get()
    for i, (name, content) in enumerate(resumes):
        text = read_upload(name, content)
        found = {s["uri"] for s in ex.extract(text)["skills"]}
        pool.append({"candidate_id": f"UP-{i + 1:02d}", "synthetic": False, "source": f"uploaded: {name}",
                     "occupation_label": None, "city": None, "tier": None, "exp_band": None, "skills": found})
    out = []
    for c in pool:
        matched = [u for u in jd if u in c["skills"]]
        cov = sum(w[u] for u in matched) / total
        # Secondary signal: breadth of related skills (log count) breaks ties among equal coverage.
        score = cov + 0.01 * math.log1p(len(c["skills"]))
        out.append({**{k: v for k, v in c.items() if k != "skills"}, "score": round(score, 5),
                    "coverage": round(cov, 4),
                    "why": {"matched_skills": [_ref(u) for u in matched],
                            "missing_skills": [_ref(u) for u in sorted(set(jd) - set(matched), key=lambda u: -w[u])],
                            "notes": ["Coverage weights rarer skills more (IDF over Indian postings)."]}})
    out.sort(key=lambda c: -c["score"])
    return {"jd_skills": [_ref(u) for u in jd], "extraction": extraction, "candidates": out[:limit],
            "pool": {"synthetic": sum(c["synthetic"] for c in pool), "uploaded": sum(not c["synthetic"] for c in pool)},
            "notes": ["Candidates marked SYNTHETIC are generated demo profiles, not real people.",
                      "Uploaded resumes are processed in memory and not stored."]}


# --- institution -----------------------------------------------------------------------------------

def institution_coverage(text: str, skills: list[str], occupations: list[str], isco2: str | None,
                         field: str | None, tiers: list[int] | None, states: list[str] | None, top_n: int = 40) -> dict:
    srv = _srv()
    m = srv.market
    uris, extraction = skill_set_from(skills, text)
    rows = m.pool(tiers=tiers or None, states=states or None, isco2=isco2)
    if occupations:
        rows = rows[np.isin(m.jobs["occupation_uri"].to_numpy()[rows], occupations)]
    if field:
        jf = srv.job_field
        rows = rows[np.array([jf.get(j) == field for j in m.jobs["jobId"].to_numpy()[rows]], dtype=bool)]
    if len(rows) == 0:
        raise ValueError("No postings in that scope; widen it.")
    counts = np.asarray(m.R[rows].sum(axis=0)).ravel()
    order = [int(s) for s in np.argsort(-counts)[:top_n] if counts[s] > 0]
    have = set(srv.skill_indices(uris))
    n = len(rows)

    def item(s):
        return {"skill": _ref(m.skills[s]), "demand_postings": int(counts[s]), "demand_share": round(counts[s] / n, 4)}

    covered = [item(s) for s in order if s in have]
    missing = [item(s) for s in order if s not in have]
    weight = counts[order].sum()
    coverage = float(counts[[s for s in order if s in have]].sum() / weight) if weight else 0.0
    low = sorted((item(s) for s in have if counts[s] / n < LOW_DEMAND_SHARE), key=lambda x: x["demand_postings"])
    return {"syllabus_skills": [_ref(u) for u in uris], "extraction": extraction,
            "scope": {"postings": n, "occupations": occupations, "isco2": isco2, "field": field, "tiers": tiers,
                      "states": states, "top_n": top_n},
            "coverage": round(coverage, 4), "covered": covered, "missing_high_demand": missing,
            "low_current_demand": low,
            "notes": [f"Demand = share of the {n:,} in-scope Naukri postings that list the skill.",
                      f"'Low current demand' = listed by fewer than {LOW_DEMAND_SHARE:.1%} of in-scope postings. "
                      "This is a snapshot (about two weeks of postings), so it says nothing about trends and "
                      "does not mean 'outdated'."]}


# --- salary -----------------------------------------------------------------------------------------

def salary_estimate(occupation_uri: str | None, isco_code: str | None, state: str | None, tier: int | None,
                    exp_min: float | None, skills: list[str]) -> dict:
    srv = _srv()
    labels = dict(zip(srv.market.jobs["occupation_uri"], srv.market.jobs["occupation_label"], strict=False))
    if occupation_uri and not isco_code:
        codes = srv.market.jobs.loc[srv.market.jobs["occupation_uri"] == occupation_uri, "isco_code"].dropna()
        isco_code = codes.iloc[0] if len(codes) else None
    exp_min = float(exp_min) if exp_min is not None else np.nan
    from ml_pipeline.india.clean import experience_band

    row = pd.DataFrame([{
        "isco_code": isco_code, "primary_state": state, "primary_tier": float(tier) if tier else np.nan,
        "primary_metro_region": None, "work_mode": "onsite", "exp_band": experience_band(exp_min),
        "exp_min": exp_min, "exp_max": exp_min + 3 if not np.isnan(exp_min) else np.nan, "company_rating": np.nan,
        "n_tags": float(len(skills)), "n_linked_skills": float(len(skills)), "n_cities": 1.0,
        "title_clean": labels.get(occupation_uri, "") or "", "skill_uris": skills, "tags": [],
    }])
    p = srv.salary.predict(row).iloc[0]
    n_support, sufficient = int(p["n_support"]), bool(p["sufficient"])
    if not tier:
        # No tier given: the estimate is for the occupation anywhere, so support is pooled over tiers.
        from ml_pipeline.salary.model import MIN_SUPPORT

        support = getattr(srv.salary, "support", {})
        n_support = sum(int(support.get(srv.salary.support_key(isco_code, t), 0)) for t in (0, 1, 2, 3))
        sufficient = n_support >= MIN_SUPPORT
    return {"salary": {"p10": round(float(p["p10"]), -3), "p50": round(float(p["p50"]), -3),
                       "p90": round(float(p["p90"]), -3), "n_support": n_support, "sufficient": sufficient},
            "basis": {"occupation_uri": occupation_uri, "isco_code": isco_code, "state": state, "tier": tier,
                      "exp_min": None if np.isnan(exp_min) else exp_min, "skills": len(skills)},
            "caveat": srv.salary_caveat}
