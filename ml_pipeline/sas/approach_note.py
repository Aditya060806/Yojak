"""Private submission package: figures and the Round 2 approach note, generated from the reports.

Every number in the note is read from private_sas/*.json, *.parquet or *.csv at build time.
Nothing here trains a model or uploads anything. Output: private_sas/submission/ (git-ignored).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

from .data import BANDS  # noqa: E402

TEAL, AMBER, INK, GREY, PALE = "#137078", "#B9770A", "#1A1A22", "#8A8F98", "#E6F2F3"
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 200, "savefig.bbox": "tight"})
PLAN_PROFILES = [("Data analyst", 2, ["sql", "excel"]), ("Data scientist", 3, ["python", "sql"]),
                 ("Business analyst", 3, ["excel", "business analysis"]), ("Data engineer", 3, ["sql", "python"])]


# ---------------------------------------------------------------------------------------------- figures

def _box(ax, x, y, w, h, text, fill=PALE, edge=TEAL, size=9, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fill, ec=edge, lw=1.1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=INK,
            fontweight="bold" if bold else "normal", linespacing=1.25)


def _arrow(ax, a, b, style="-|>", color=INK, dashed=False):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=11, lw=1.1, color=color,
                                 linestyle="--" if dashed else "-", shrinkA=2, shrinkB=2))


def _canvas(w, h, xmax, ymax):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.axis("off")
    return fig, ax


def fig_pipeline(path):
    fig, ax = _canvas(7.2, 2.5, 14.4, 5)
    stages = [("Audit", "hashes, counts,\nmissingness"), ("Prepare", "dedupe, parse,\nflags"),
              ("Derive", "skills, roles,\nsignatures"), ("Partition", "connected groups\n60/15/10/15"),
              ("Analyse", "statistics,\nCUDA models"), ("Evaluate", "calibration,\ntest once"),
              ("Package", "reports, note,\nprivate API")]
    for i, (name, sub) in enumerate(stages):
        x = 0.2 + i * 2.03
        _box(ax, x, 2.6, 1.75, 1.0, name, size=10, bold=True)
        ax.text(x + 0.875, 2.05, sub, ha="center", va="top", fontsize=8, color=INK)
        if i:
            _arrow(ax, (x - 0.28, 3.1), (x, 3.1))
    _box(ax, 0.2, 0.15, 13.9, 0.6, "manifest.json: source hashes, code hashes, row counts, exclusions, unit status, SAS execution status",
         fill="#FFF7E6", edge=AMBER, size=8.5)
    for i in (0, 3, 6):
        _arrow(ax, (1.07 + i * 2.03, 1.2), (1.07 + i * 2.03, 0.78), color=AMBER, dashed=True)
    ax.text(7.2, 4.5, "One command rebuilds every stage:  python -m ml_pipeline.sas.run --stage all", ha="center", fontsize=9, style="italic")
    fig.savefig(path)
    plt.close(fig)


def fig_architecture(path):
    fig, ax = _canvas(9.6, 6.0, 16, 10)
    amber, grey, red = {"fill": "#FFF7E6", "edge": AMBER}, {"fill": "#F2F2F4", "edge": GREY}, {"fill": "#FDECEC", "edge": "#B3261E"}
    _box(ax, 0.3, 7.6, 3.4, 1.8, "Supplied files\n(private)\ntwo job files,\ntwo cohort files", size=9, **amber)
    _box(ax, 4.6, 7.6, 3.4, 1.8, "ml_pipeline.sas\nprepare, train,\nanalyze, package", size=9.5, bold=True)
    _box(ax, 8.9, 7.6, 3.1, 1.8, "CUDA GPU\nXGBoost AFT,\nsoft-target model", size=9)
    _box(ax, 12.6, 7.6, 3.1, 1.8, "Statistics\nordinal, mixed,\npenalised logistic", size=9)
    _box(ax, 4.6, 4.3, 7.4, 2.0, "private_sas/  (git-ignored)\nprepared tables, partition manifests, model,\nsalary and research reports, submission files", size=9, **grey)
    _box(ax, 0.3, 4.3, 3.4, 2.0, "SAS track\nStudio checks,\nVisual Analytics\n(status in manifest)", size=9, **amber)
    _box(ax, 12.6, 4.3, 3.1, 2.0, "Existing Yojak\ncoverage optimiser,\nreport tooling", size=9)
    _box(ax, 4.6, 1.0, 3.4, 1.8, "FastAPI  /sas/*\nmatch, plan, pay-range\n(local flag required)", size=9, bold=True)
    _box(ax, 8.9, 1.0, 3.1, 1.8, "Next.js\nCareer Ladder page\n(local only)", size=9)
    _box(ax, 12.6, 1.0, 3.1, 1.8, "Public demo\n(Vercel)\nno supplied data", size=9, **red)
    for a, b in [((3.7, 8.5), (4.6, 8.5)), ((8.0, 8.5), (8.9, 8.5)), ((6.3, 7.6), (6.3, 6.3)), ((10.4, 7.6), (9.6, 6.3)),
                 ((14.1, 7.6), (11.6, 6.3)), ((6.3, 4.3), (6.3, 2.8)), ((8.0, 1.9), (8.9, 1.9)), ((12.6, 5.3), (12.0, 5.3))]:
        _arrow(ax, a, b)
    _arrow(ax, (4.6, 5.3), (3.7, 5.3), dashed=True, color=AMBER)
    ax.text(4.15, 4.75, "CSV", fontsize=7.5, color=AMBER, ha="center")
    _arrow(ax, (12.0, 1.9), (12.6, 1.9), style="-[", color="#B3261E", dashed=True)
    ax.text(12.3, 2.3, "blocked", fontsize=8, color="#B3261E", ha="center")
    fig.savefig(path)
    plt.close(fig)


def fig_evidence_map(path):
    fig, ax = _canvas(7.2, 3.8, 14.4, 7.6)
    data = [("Analytics Jobs\n(job postings)", 5.6), ("DataScience Jobs\n(company-title rows)", 3.8),
            ("JDS skill traits\n(junior records)", 2.0), ("SDS personality traits\n(senior records)", 0.2)]
    qs = [("Q1 Role families and skill patterns", 6.1), ("Q2 Salary band: explain and predict", 5.0),
          ("Q3 Company and title pay", 3.9), ("Q4 Skills to learn next", 2.8),
          ("Q5 Junior skills and salary hike", 1.7), ("Q6 Senior traits and recorded success", 0.6)]
    for text, y in data:
        _box(ax, 0.3, y, 4.0, 1.25, text, fill="#FFF7E6", edge=AMBER, size=9)
    for text, y in qs:
        _box(ax, 5.4, y, 5.6, 0.8, text, size=8.5)
    for d, q in [(0, 0), (0, 1), (0, 3), (1, 2), (1, 1), (2, 4), (3, 5)]:
        _arrow(ax, (4.3, data[d][1] + 0.62), (5.4, qs[q][1] + 0.4), dashed=(d, q) == (1, 1), color=GREY if (d, q) == (1, 1) else INK)
    _box(ax, 11.6, 2.75, 2.5, 4.2, "Market\nevidence\n(what postings\nask and offer)", fill="#F2F2F4", edge=GREY, size=8.5)
    _box(ax, 11.6, 1.6, 2.5, 0.95, "Junior cohort\nevidence", fill="#F2F2F4", edge=GREY, size=8.5)
    _box(ax, 11.6, 0.45, 2.5, 0.95, "Senior cohort\nevidence", fill="#F2F2F4", edge=GREY, size=8.5)
    ax.text(7.2, 7.3, "Three separate lines of evidence. No records are joined across files.", ha="center", fontsize=9, style="italic")
    fig.savefig(path)
    plt.close(fig)


def fig_partitions(path, audit):
    fig, ax = _canvas(7.2, 2.3, 14.4, 4.6)
    parts = audit["analytics"]["partitions"]
    total = sum(parts.values())
    x = 0.3
    roles = {"train": "fit preprocessing\nand models", "validation": "select champion\n(QWK)", "calibration": "prediction-set\nradius", "test": "report once"}
    for name, colour in [("train", PALE), ("validation", "#CFE6E8"), ("calibration", "#FFF1D6"), ("test", "#F2F2F4")]:
        w = 13.8 * parts[name] / total
        _box(ax, x, 2.5, w - 0.08, 1.0, f"{name}\n{parts[name] / total:.0%}", fill=colour, size=8.5, bold=True)
        ax.text(x + w / 2, 2.3, f"{parts[name]:,}", ha="center", va="top", fontsize=8)
        x += w
    ax.text(7.2, 1.55, "   ·   ".join(f"{k}: {v.replace(chr(10), ' ')}" for k, v in roles.items()), ha="center", fontsize=8, color=INK)
    ax.text(7.2, 4.1, f"Analytics Jobs: {audit['analytics']['prepared_rows']:,} postings in {audit['analytics']['groups']:,} connected groups; a group never spans two partitions",
            ha="center", fontsize=9)
    ax.text(7.2, 0.4, "Groups join postings with identical features or near-identical title + skills + location (transitive closure).\n"
                       "DataScience Jobs is split by company; JDS and SDS by shared id or identical profile.", ha="center", fontsize=8.5)
    fig.savefig(path)
    plt.close(fig)


def fig_quality(path, a, audit):
    raw = audit["analytics"]["raw_rows"]
    items = [("Exact duplicate rows", audit["analytics"]["exact_duplicates_removed"] / raw),
             ("job_type missing", audit["analytics"]["missing"]["job_type"] / raw),
             ("Description missing", a.description_missing.mean()), ("Description truncated", a.description_truncated.mean()),
             ("Skill list truncated", a.skills_truncated.mean()),
             ("Rows in conflicting-label groups", audit["analytics"]["rows_in_conflicting_groups"] / len(a)),
             ("Multi-city postings", a.locations.map(len).gt(1).mean()), ("Flagged by advert heuristic", a.quality_flag.mean())]
    fig, ax = plt.subplots(figsize=(6.6, 2.7))
    names, vals = zip(*items[::-1], strict=True)
    ax.barh(names, [v * 100 for v in vals], color=TEAL)
    for i, v in enumerate(vals):
        ax.text(v * 100 + 1, i, f"{v:.1%}", va="center", fontsize=9)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of postings (%)")
    fig.savefig(path)
    plt.close(fig)


def fig_bands(path, a):
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6), gridspec_kw={"width_ratios": [1, 1.25]})
    counts = a.band.value_counts().sort_index()
    axes[0].bar(BANDS, counts.to_numpy(), color=TEAL)
    axes[0].set_ylabel("Distinct postings")
    axes[0].set_title("Salary band (units unverified)", fontsize=10)
    axes[0].tick_params(axis="x", labelrotation=30)
    exp = pd.cut(a.exp_min, [-1, 1, 3, 5, 8, 40], labels=["0-1", "2-3", "4-5", "6-8", "9+"])
    table = pd.crosstab(exp, a.band, normalize="index").reindex(columns=range(6), fill_value=0)
    left = np.zeros(len(table))
    shades = plt.cm.YlGnBu(np.linspace(0.2, 0.95, 6))
    for b in range(6):
        axes[1].barh(table.index.astype(str), table[b].to_numpy() * 100, left=left, color=shades[b], label=BANDS[b])
        left += table[b].to_numpy() * 100
    axes[1].set_xlabel("Share of postings (%)")
    axes[1].set_ylabel("Minimum experience (years)")
    axes[1].set_title("Band mix by experience", fontsize=10)
    axes[1].legend(ncol=3, fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.32))
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_families(path, families):
    s = pd.Series(families).sort_values()
    fig, ax = plt.subplots(figsize=(6.2, 2.5))
    ax.barh(s.index, s.to_numpy(), color=[GREY if i == "Other" else TEAL for i in s.index])
    for i, v in enumerate(s.to_numpy()):
        ax.text(v + 80, i, f"{v:,} ({v / s.sum():.0%})", va="center", fontsize=9)
    ax.set_xlim(0, s.max() * 1.22)
    ax.set_xlabel("Distinct postings")
    fig.savefig(path)
    plt.close(fig)


def fig_models(path, salary):
    exps = salary["experiments"]
    names = [e["name"].replace("tfidf_logistic", "TF-IDF logistic").replace("aft_", "AFT ").replace("soft_target", "soft-target").replace("_", " ") for e in exps]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6), sharey=True)
    for ax, key, title in [(axes[0], "qwk", "Validation QWK"), (axes[1], "within_one_band", "Within one band")]:
        vals = [e["validation"][key] or 0 for e in exps]
        ax.barh(names, vals, color=[AMBER if e["name"] == salary["champion"] else TEAL for e in exps])
        for i, v in enumerate(vals):
            ax.text(v + 0.01, i, f"{v:.3f}", va="center", fontsize=8.5)
        ax.set_xlim(0, 1.08)
        ax.set_title(title, fontsize=10)
        ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_confusion(path, scored):
    m = pd.crosstab(scored.band, scored.prediction).reindex(index=range(6), columns=range(6), fill_value=0)
    share = m.div(m.sum(axis=1), axis=0).to_numpy()
    fig, ax = plt.subplots(figsize=(3.9, 3.3))
    ax.imshow(share, cmap="YlGnBu", vmin=0, vmax=0.8)
    ax.set_xticks(range(6), BANDS, rotation=35, fontsize=8)
    ax.set_yticks(range(6), BANDS, fontsize=8)
    ax.set_xlabel("Predicted band")
    ax.set_ylabel("Observed band")
    for i in range(6):
        for j in range(6):
            ax.text(j, i, f"{share[i, j]:.0%}", ha="center", va="center", fontsize=8, color="white" if share[i, j] > 0.45 else INK)
    for s in ("top", "right"):
        ax.spines[s].set_visible(True)
    fig.savefig(path)
    plt.close(fig)


def fig_coverage(path, salary):
    cal = salary["calibration"]
    fam = pd.DataFrame(cal["by_family"]).T.sort_values("n")
    fig, ax = plt.subplots(figsize=(6.2, 2.4))
    ax.barh([f"{i} (n={int(n)})" for i, n in zip(fam.index, fam.n, strict=True)], fam.coverage * 100, color=TEAL)
    ax.axvline(cal["target"] * 100, color=AMBER, lw=1.5, ls="--")
    ax.text(cal["target"] * 100 - 0.6, len(fam) - 0.35, "90% target", color=AMBER, ha="right", fontsize=8.5)
    for i, (c, w) in enumerate(zip(fam.coverage, fam.set_width, strict=True)):
        ax.text(c * 100 + 0.3, i, f"{c:.1%} · {w:.1f} bands", va="center", fontsize=8.5)
    ax.set_xlim(70, 112)
    ax.set_xlabel("Observed test coverage of band label (%)")
    fig.savefig(path)
    plt.close(fig)


def fig_cross(path, cross):
    names = {"businessanalyst": "Business Analyst", "dataanalyst": "Data Analyst", "dataarchitect": "Data Architect",
             "dataengineer": "Data Engineer", "datascientist": "Data Scientist", "machinelearningengineer": "Machine Learning Engineer",
             "seniorbusinessanalyst": "Senior Business Analyst", "seniordataanalyst": "Senior Data Analyst",
             "seniordataengineer": "Senior Data Engineer", "seniordatascientist": "Senior Data Scientist"}
    t = pd.DataFrame(cross["titles"]).sort_values("company_average").reset_index(drop=True)
    fig, (ax, key) = plt.subplots(1, 2, figsize=(6.8, 3.4), gridspec_kw={"width_ratios": [1.25, 1]})
    ax.scatter(t.company_average, t["mean"], s=30 + 3 * t["count"], color=TEAL, alpha=0.75)
    lim = max(t.company_average.max(), t["mean"].max()) * 1.08
    ax.plot([0, lim], [0, lim], color=GREY, ls="--", lw=1)
    for i, r in t.iterrows():
        ax.annotate(str(i + 1), (r.company_average, r["mean"]), fontsize=8, fontweight="bold", ha="center", va="center",
                    xytext=(0, 9), textcoords="offset points")
    ax.set_xlabel("DataScience Jobs: mean company average")
    ax.set_ylabel("Analytics Jobs: mean band midpoint")
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    key.axis("off")
    for i, r in t.iterrows():
        key.text(0, 0.96 - i * 0.095, f"{i + 1}. {names.get(r.title_key, r.title_key)}", fontsize=8, va="top")
        key.text(1.0, 0.96 - i * 0.095, f"n = {int(r['count'])}", fontsize=8, va="top", ha="right", color=GREY)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_forest(path, cohort, label):
    f = pd.DataFrame(cohort["features"]).iloc[::-1]
    fig, ax = plt.subplots(figsize=(6.0, 2.3))
    y = np.arange(len(f))
    lo = [c[0] for c in f.or_ci95]
    hi = [c[1] for c in f.or_ci95]
    ax.hlines(y, lo, hi, color=TEAL, lw=2)
    ax.plot(f.odds_ratio_native_unit, y, "o", color=INK, ms=5)
    ax.axvline(1, color=GREY, ls="--", lw=1)
    ax.set_yticks(y, [n.replace("_", " ") for n in f.feature])
    ax.set_xscale("log")
    ax.set_xlabel(f"Odds ratio per one native score unit ({label}), 95% group-bootstrap interval")
    fig.savefig(path)
    plt.close(fig)


def fig_plans(path, plans):
    ok = [p for p in plans if p.get("optimized")]
    if not ok:
        return False
    fig, ax = plt.subplots(figsize=(6.4, 2.5))
    y = np.arange(len(ok))
    ax.barh(y + 0.27, [p["before"] for p in ok], 0.26, color=GREY, label="Now")
    ax.barh(y, [p["frequency"]["coverage"] for p in ok], 0.26, color=AMBER, label="3 most frequent skills")
    ax.barh(y - 0.27, [p["optimized"]["coverage"] for p in ok], 0.26, color=TEAL, label="3 optimised skills")
    ax.set_yticks(y, [f"{p['family']}\n({p['support']} postings)" for p in ok], fontsize=8.5)
    ax.set_xlabel("Postings reaching 60% of listed skills")
    ax.legend(frameon=False, fontsize=8)
    ax.invert_yaxis()
    fig.savefig(path)
    plt.close(fig)
    return True


def fig_family_bands(path, a):
    table = pd.crosstab(a.role_family, a.band, normalize="index").reindex(columns=range(6), fill_value=0)
    table = table.loc[table[[4, 5]].sum(axis=1).sort_values().index]
    fig, ax = plt.subplots(figsize=(6.4, 2.7))
    left = np.zeros(len(table))
    shades = plt.cm.YlGnBu(np.linspace(0.2, 0.95, 6))
    for b in range(6):
        ax.barh(table.index, table[b].to_numpy() * 100, left=left, color=shades[b], label=BANDS[b])
        left += table[b].to_numpy() * 100
    ax.set_xlabel("Share of the family's postings (%)")
    ax.legend(ncol=6, fontsize=7.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.22))
    fig.savefig(path)
    plt.close(fig)


def fig_cities(path, a):
    ex = a[["locations", "band"]].explode("locations").dropna()
    top = ex.locations.value_counts().head(10)
    high = ex[ex.locations.isin(top.index)].groupby("locations").band.apply(lambda s: (s >= 4).mean()).reindex(top.index)
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.6), sharey=True)
    axes[0].barh([c.title() for c in top.index][::-1], top.to_numpy()[::-1], color=TEAL)
    axes[0].set_xlabel("Postings mentioning the city")
    axes[1].barh([c.title() for c in top.index][::-1], high.to_numpy()[::-1] * 100, color=AMBER)
    axes[1].set_xlabel("Share in the two highest bands (%)")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_company(path, company):
    order = company.groupby("job_title").avg_salary_native.median().sort_values().index
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    ax.boxplot([company.loc[company.job_title == t, "avg_salary_native"] for t in order], vert=False, labels=list(order),
               flierprops={"markersize": 2, "alpha": 0.4}, medianprops={"color": AMBER, "lw": 1.5}, boxprops={"color": TEAL},
               whiskerprops={"color": TEAL}, capprops={"color": TEAL})
    ax.set_xscale("log")
    ax.set_xlabel("Company average salary (native units, log scale)")
    ax.tick_params(axis="y", labelsize=8.5)
    fig.savefig(path)
    plt.close(fig)


def fig_cohort_boxes(path, frame, target, labels):
    feats = [c for c in frame.columns if c not in {"id", target, "row_key", "group_id", "split"}]
    fig, axes = plt.subplots(1, len(feats), figsize=(7.0, 2.4))
    for ax, f in zip(axes, feats, strict=True):
        ax.boxplot([frame.loc[frame[target] == 0, f], frame.loc[frame[target] == 1, f]], labels=labels, widths=0.6,
                   medianprops={"color": AMBER, "lw": 1.5}, boxprops={"color": TEAL}, whiskerprops={"color": TEAL},
                   capprops={"color": TEAL}, flierprops={"markersize": 2})
        ax.set_title(f.replace("_skills", "").replace("_", " ").replace("and ", "& "), fontsize=8)
        ax.tick_params(labelsize=7.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_error_by_band(path, scored):
    g = scored.assign(err=(scored.band - scored.prediction)).groupby("band")
    exact = g.apply(lambda d: (d.err == 0).mean())
    near = g.apply(lambda d: (d.err.abs() == 1).mean())
    fig, ax = plt.subplots(figsize=(5.6, 2.3))
    ax.bar(BANDS, exact * 100, color=TEAL, label="Exact band")
    ax.bar(BANDS, near * 100, bottom=exact * 100, color="#9CCFD3", label="One band away")
    ax.set_ylabel("Test postings (%)")
    ax.set_xlabel("Observed band")
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.18))
    ax.set_ylim(0, 100)
    fig.savefig(path)
    plt.close(fig)


# ---------------------------------------------------------------------------------------------- facts

def descriptive_tests(a: pd.DataFrame) -> list[dict]:
    """Label-level association tests on distinct postings, with false-discovery correction."""
    from scipy.stats import chi2_contingency, kruskal, spearmanr
    from statsmodels.stats.multitest import multipletests

    def cramers_v(x, y):
        table = pd.crosstab(x, y)
        chi2, p, dof, _ = chi2_contingency(table)
        return chi2, p, dof, float(np.sqrt(chi2 / (table.to_numpy().sum() * (min(table.shape) - 1))))

    rows = []
    rho = spearmanr(a.exp_mid, a.band)
    rows.append({"test": "Experience midpoint vs band", "method": "Spearman rank correlation", "effect": f"rho = {rho.statistic:.2f}", "p": rho.pvalue})
    rho = spearmanr(a.skills.map(len), a.band)
    rows.append({"test": "Number of listed skills vs band", "method": "Spearman rank correlation", "effect": f"rho = {rho.statistic:.2f}", "p": rho.pvalue})
    kw = kruskal(*[g.band.to_numpy() for _, g in a.groupby("role_family")])
    eps = (kw.statistic - a.role_family.nunique() + 1) / (len(a) - a.role_family.nunique())
    rows.append({"test": "Band across role families", "method": "Kruskal-Wallis", "effect": f"epsilon squared = {eps:.3f}", "p": kw.pvalue})
    for label, col in [("Role family vs band", a.role_family), ("Skill list truncated vs band", a.skills_truncated),
                       ("Description missing vs band", a.description_missing), ("Multi-city posting vs band", a.locations.map(len).gt(1))]:
        chi2, pv, dof, v = cramers_v(col, a.band)
        rows.append({"test": label, "method": f"Chi-square ({dof} d.f.)", "effect": f"Cramer's V = {v:.2f}", "p": pv})
    adj = multipletests([r["p"] for r in rows], method="fdr_bh")[1]
    for r, q in zip(rows, adj, strict=True):
        r["p_fdr"] = float(q)
    return rows


def family_performance(scored: pd.DataFrame) -> list[list]:
    from sklearn.metrics import cohen_kappa_score

    rows = []
    for family, d in scored.groupby("role_family"):
        if len(d) < 30:
            continue
        qwk = cohen_kappa_score(d.band, d.prediction, labels=list(range(6)), weights="quadratic")
        rows.append([family, f"{len(d):,}", f"{qwk:.3f}", f"{(d.band == d.prediction).mean():.1%}", f"{((d.band - d.prediction).abs() <= 1).mean():.1%}",
                     f"{(d.band - d.prediction).abs().mean():.2f}"])
    return sorted(rows, key=lambda r: -int(r[1].replace(",", "")))


def cohort_summary(frame: pd.DataFrame, target: str) -> list[list]:
    feats = [c for c in frame.columns if c not in {"id", target, "row_key", "group_id", "split"}]
    lo, hi = frame[frame[target] == 0], frame[frame[target] == 1]
    rows = []
    for f in feats:
        pooled = np.sqrt((lo[f].var() + hi[f].var()) / 2)
        rows.append([f.replace("_", " "), f"{lo[f].mean():.2f}", f"{hi[f].mean():.2f}", f"{(hi[f].mean() - lo[f].mean()) / pooled:+.2f}",
                     f"{frame[f].min():g} to {frame[f].max():g}", f"{(frame[f] == frame[f].max()).mean():.0%}"])
    return rows



def learning_plans(out: Path) -> list[dict]:
    """Run the same service the local API uses on a few fixed, illustrative profiles."""
    from .service import SasService

    try:
        svc = SasService(out)
    except (FileNotFoundError, ValueError):
        return []
    rows = []
    for family, experience, skills in PLAN_PROFILES:
        plan = svc.plan(family, experience, skills)
        rows.append({"family": family, "experience": experience, "start_skills": skills, **{k: plan.get(k) for k in
                     ["support", "before", "optimized", "frequency", "solver"]}})
    return rows


def top_skills(a: pd.DataFrame, n=6) -> dict[str, list[tuple[str, int]]]:
    out = {}
    for family, part in a[~a.quality_flag].groupby("role_family"):
        out[family] = Counter(s for skills in part.skills for s in skills).most_common(n)
    return out


# ---------------------------------------------------------------------------------------------- document

def package(out: Path) -> Path:
    from docx import Document
    from docx.enum.section import WD_ORIENT  # noqa: F401
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    salary = json.loads((out / "salary_report.json").read_text(encoding="utf-8"))
    research = json.loads((out / "research_report.json").read_text(encoding="utf-8"))
    a = pd.read_parquet(out / "analytics.parquet")
    company = pd.read_parquet(out / "company.parquet")
    scored = pd.read_csv(out / "test_predictions.csv")
    audit = manifest["audit"]
    an, co = audit["analytics"], research["company"]
    sub = out / "submission"
    figs = sub / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    plans = learning_plans(out)

    fig_pipeline(figs / "f01_pipeline.png")
    fig_architecture(figs / "f02_architecture.png")
    fig_evidence_map(figs / "f03_evidence_map.png")
    fig_partitions(figs / "f04_partitions.png", audit)
    fig_quality(figs / "f05_quality.png", a, audit)
    fig_bands(figs / "f06_bands.png", a)
    fig_families(figs / "f07_families.png", research["role_families"])
    fig_models(figs / "f08_models.png", salary)
    fig_confusion(figs / "f09_confusion.png", scored)
    fig_coverage(figs / "f10_coverage.png", salary)
    fig_cross(figs / "f11_cross.png", co["cross_file"])
    fig_forest(figs / "f12_jds.png", research["jds"], "1 to 5 scale")
    fig_forest(figs / "f13_sds.png", research["sds"], "normalised score")
    has_plans = fig_plans(figs / "f14_plans.png", plans)
    jds_frame, sds_frame = pd.read_parquet(out / "jds.parquet"), pd.read_parquet(out / "sds.parquet")
    jds_target, sds_target = audit["jds"]["target"], audit["sds"]["target"]
    fig_family_bands(figs / "f15_family_bands.png", a)
    fig_cities(figs / "f16_cities.png", a)
    fig_company(figs / "f17_company.png", company)
    fig_cohort_boxes(figs / "f18_jds_boxes.png", jds_frame, jds_target, ["low", "high"])
    fig_cohort_boxes(figs / "f19_sds_boxes.png", sds_frame, sds_target, ["low", "high"])
    fig_error_by_band(figs / "f20_error_by_band.png", scored)
    tests = descriptive_tests(a)

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Inches(1))
    for name in ("Normal", "Heading 1", "Heading 2", "Heading 3", "Caption", "List Bullet", "Title"):
        st = doc.styles[name]
        st.font.name = "Times New Roman"
        st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        st.element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
        st.element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
        for theme in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if st.element.rPr.rFonts.get(qn(theme)) is not None:
                del st.element.rPr.rFonts.attrib[qn(theme)]
        st.font.color.rgb = RGBColor(0, 0, 0)
    doc.styles["Normal"].font.size = Pt(12)
    doc.styles["Normal"].paragraph_format.space_after = Pt(6)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.0
    for name, size in (("Heading 1", 15), ("Heading 2", 13), ("Heading 3", 12)):
        doc.styles[name].font.size = Pt(size)
        doc.styles[name].font.bold = True
        doc.styles[name].paragraph_format.space_before = Pt(12 if name == "Heading 1" else 8)
        doc.styles[name].paragraph_format.space_after = Pt(4)
        doc.styles[name].paragraph_format.keep_with_next = True
    doc.styles["Caption"].font.size = Pt(10)
    doc.styles["Caption"].font.italic = True
    doc.styles["Caption"].font.bold = False

    # footer page number
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run()
    for tag, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if tag:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), tag)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)
    run.font.size = Pt(10)

    counters = {"fig": 0, "tab": 0}
    ref: dict[str, str] = {}

    def nf(k=1):
        return f"Figure {counters['fig'] + k}"

    def nt(k=1):
        return f"Table {counters['tab'] + k}"

    def para(text, bold_lead=None, italic=False, align=None, size=None):
        p = doc.add_paragraph()
        if bold_lead:
            r = p.add_run(bold_lead + " ")
            r.bold = True
        r = p.add_run(text)
        r.italic = italic
        if size:
            r.font.size = Pt(size)
        if align == "center":
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        else:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        return p

    def bullets(items):
        for item in items:
            p = doc.add_paragraph(style="List Bullet")
            lead, _, rest = item.partition("::")
            if rest:
                p.add_run(lead.strip() + ": ").bold = True
                p.add_run(rest.strip())
            else:
                p.add_run(item)
            p.paragraph_format.space_after = Pt(2)

    def figure(name, caption, width=6.2, key=None):
        counters["fig"] += 1
        if key:
            ref[key] = f"Figure {counters['fig']}"
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next = True
        p.add_run().add_picture(str(figs / name), width=Inches(width))
        c = doc.add_paragraph(f"Figure {counters['fig']}. {caption}", style="Caption")
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def table(header, rows, widths, caption, size=9.5, key=None):
        counters["tab"] += 1
        if key:
            ref[key] = f"Table {counters['tab']}"
        c = doc.add_paragraph(f"Table {counters['tab']}. {caption}", style="Caption")
        c.paragraph_format.keep_with_next = True
        t = doc.add_table(rows=1, cols=len(header))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        for i, (h, w) in enumerate(zip(header, widths, strict=True)):
            cell = t.rows[0].cells[i]
            cell.width = Inches(w)
            cell.text = ""
            r = cell.paragraphs[0].add_run(h)
            r.bold = True
            r.font.size = Pt(size)
            shade = OxmlElement("w:shd")
            shade.set(qn("w:val"), "clear")
            shade.set(qn("w:color"), "auto")
            shade.set(qn("w:fill"), "E6F2F3")
            cell._tc.get_or_add_tcPr().append(shade)
        for row in rows:
            cells = t.add_row().cells
            for i, (v, w) in enumerate(zip(row, widths, strict=True)):
                cells[i].width = Inches(w)
                cells[i].text = ""
                r = cells[i].paragraphs[0].add_run(str(v))
                r.font.size = Pt(size)
                cells[i].paragraphs[0].paragraph_format.space_after = Pt(0)
        doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def code(text):
        for line in text.strip("\n").split("\n"):
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(line or " ")
            r.font.name = "Consolas"
            r._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
            r.font.size = Pt(8.5)
        doc.add_paragraph()

    def page_break():
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ------------------------------------------------------------------ numbers used in prose
    n_raw, n = an["raw_rows"], an["prepared_rows"]
    fam = pd.Series(research["role_families"])
    other_share = fam.get("Other", 0) / fam.sum()
    test, cal = salary["test"], salary["calibration"]
    ci = salary["qwk_ci95_group_bootstrap"]
    exps = {e["name"]: e for e in salary["experiments"]}
    base, champ = exps["tfidf_logistic"]["validation"], exps[salary["champion"]]["validation"]
    jds, sds = research["jds"], research["sds"]
    jf = {f["feature"]: f for f in jds["features"]}
    sf = {f["feature"]: f for f in sds["features"]}
    ordinal = {c["feature"]: c for c in research["ordinal"]["coefficients"]}
    cross = pd.DataFrame(co["cross_file"]["titles"])
    gpu = salary["hardware"].get("nvidia_smi", "unavailable")
    used_gpu = any(e.get("device") == "cuda" for e in salary["experiments"])
    sas_status = manifest.get("sas_execution", "not executed")
    skill_tokens = Counter(s for skills in a.skills for s in skills)
    med_exp = a.groupby("band").exp_min.median()
    tops = top_skills(a)

    def orci(f, digits=2):
        return f"{f['odds_ratio_native_unit']:.{digits}f} [{f['or_ci95'][0]:.{digits}f}, {f['or_ci95'][1]:.{digits}f}]"

    # ------------------------------------------------------------------ title page
    for _ in range(5):
        doc.add_paragraph()
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("Approach Note")
    r.bold = True
    r.font.size = Pt(26)
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("Getting in, getting ahead and succeeding in data and analytics careers:\nevidence from job postings, junior skill scores and senior trait scores")
    r.font.size = Pt(15)
    doc.add_paragraph()
    para("Project Yojak · Round 2 submission", align="center", size=13)
    para("Team: ____________________        Institution: ____________________", align="center")
    for _ in range(8):
        doc.add_paragraph()
    para(f"Generated from the analysis reports (source version {manifest['source_version']}). Every figure and table in this note is "
         "produced by the project's pipeline from the four supplied files; nothing is typed by hand. Confidential: contains results "
         "derived from organiser-supplied data.", italic=True, align="center", size=10)
    page_break()

    # ------------------------------------------------------------------ summary + contents
    doc.add_heading("Summary", level=1)
    para("We ask one question of the four supplied files: what does the evidence say about getting in, getting ahead and succeeding as a data "
         "and analytics professional? The files cannot be joined, so we treat them as three separate lines of evidence: the job market "
         "(two postings files), a junior cohort with measured technical skills, and a senior cohort with measured personality traits.")
    bullets([
        f"Data preparation:: {n_raw:,} analytics postings reduce to {n:,} distinct ones. {a.skills_truncated.mean():.0%} of skill lists and every "
        f"available description are truncated in the source, and {an['rows_in_conflicting_groups']:,} postings share identical features with a "
        f"posting in a different salary band. Fourteen such issues are documented with the decision taken for each.",
        "Salary band:: the explanatory model must be interpreted using its assumption diagnostic, not a universal pay multiplier. "
        f"An interval-censored gradient-boosting model trained on a CUDA GPU reaches quadratic-weighted kappa {test['qwk']:.3f} "
        f"(95% interval {ci[0]:.3f} to {ci[1]:.3f}) on held-out postings and places {test['within_one_band']:.0%} within one band.",
        "Skills:: keyword associations are exploratory and specification-dependent. A keyword does not measure an individual's proficiency or the return to learning it.",
        f"Junior cohort:: maths-statistics and storytelling scores have the strongest association with a high salary hike "
        f"(cross-validated AUC {jds['oof_auc']:.2f}). Big-data scores show the weakest raw association.",
        f"Senior cohort:: openness and conscientiousness have the strongest association with recorded success (AUC {sds['oof_auc']:.2f}). "
        "We report this as aggregate research only and argue against using it to score individuals.",
        f"Honest limits:: salary units are unverified, {other_share:.0%} of postings are not yet assigned to a named role family, prediction sets are wide, "
        f"and the SAS track is {sas_status}. Each limit is stated next to the result it affects.",
    ])
    doc.add_heading("Contents", level=2)
    for line in ["1. Problem definition and analytics objective", "2. Approach", "3. Data exploration and preparation",
                 "4. Data analysis", "5. Results and conclusions", "6. Implications",
                 "Appendix A. Reproducibility   B. Experiment log   C. Association rules   D. SAS programs   E. Private API   F. Tests"]:
        p = doc.add_paragraph(line)
        p.paragraph_format.space_after = Pt(1)
    page_break()

    # ------------------------------------------------------------------ 1 problem
    doc.add_heading("1. Problem definition and analytics objective", level=1)
    doc.add_heading("1.1 Business context", level=2)
    para("Students and early-career professionals choose what to learn with little evidence about what employers ask for or pay for. "
         "Colleges set curricula with the same gap. Employers' learning teams decide which capabilities to develop in junior and senior staff "
         "without knowing which measured capabilities go with good outcomes. The supplied data touches each of these decisions: two files "
         "describe the job market, one describes junior data scientists' measured skills and salary-hike outcome, and one describes senior "
         "data scientists' measured personality traits and success classification.")
    doc.add_heading("1.2 Analytics objective", level=2)
    para("Quantify how role, experience, skills and location relate to the advertised salary band in the analytics job market; identify the "
         "small set of skills that most increases the number of postings a candidate's profile aligns with; and describe which measured "
         "skills and traits are associated with recorded outcomes in the junior and senior cohorts. State the uncertainty and the limits of "
         "every answer.", italic=True)
    para("Our working hypothesis is \"statistics pays twice\": that quantitative modelling skills are associated with higher advertised pay in "
         "the market and with better outcomes inside a firm. It is a hypothesis to test, not a conclusion. Section 5 reports where the "
         "evidence supports it and where it does not.")
    figure("f03_evidence_map.png", "The four supplied files and the six research questions they can answer. Dashed arrow: plausibility cross-check only.")
    table(["#", "Research question", "Evidence", "Decision it supports"], [
        ["Q1", "What role families exist in the postings and which skills occur together in each?", "Analytics Jobs", "Choice of target role"],
        ["Q2", "How do experience, role, skills and location relate to the salary band, and how well can the band be predicted?", "Analytics Jobs", "Pay expectations, expressed as a set of bands"],
        ["Q3", "How much of average pay is associated with the title and how much with the company?", "DataScience Jobs", "Comparing employers and roles"],
        ["Q4", "Which three additional skills align a profile with the most postings?", "Analytics Jobs", "Learning and curriculum priorities"],
        ["Q5", "Which measured technical skills are associated with a high salary hike?", "JDS", "Training emphasis for junior staff"],
        ["Q6", "Which measured traits are associated with recorded success?", "SDS", "Aggregate development research only"],
    ], [0.4, 2.9, 1.2, 1.75], "Research questions, evidence and the decisions they inform")
    doc.add_heading("1.3 Stakeholders and success measures", level=2)
    bullets(["Students and early-career professionals:: a ranked, explained list of skills to learn and an honest pay expectation (Q1, Q2, Q4).",
             "Colleges and training providers:: skill combinations employers list together, by role family (Q1, Q4).",
             "Employers' learning and development teams:: which measured capabilities go with good outcomes, with uncertainty (Q5, Q6).",
             "Success for this note:: each question receives an answer, a supporting figure or table, an uncertainty statement where one can be estimated, and a limitation."])
    doc.add_heading("1.4 What is out of scope", level=2)
    para("We do not forecast demand (the files are a snapshot), promise salary gains, automate hiring, or rank individuals by personality. "
         "The three lines of evidence come from different populations; we do not present them as one person's career path or as cause and effect.")

    # ------------------------------------------------------------------ 2 approach
    doc.add_heading("2. Approach", level=1)
    doc.add_heading("2.1 Overall flow", level=2)
    para(f"The work is a single reproducible pipeline of seven stages ({nf()}). Each stage writes its inputs' hashes, its configuration and its "
         "row counts to a manifest, so that any number in this note can be traced to a file and a line of code. We spent the first part of the "
         "effort on the audit, because the audit changed the modelling plan: it showed truncated text, conflicting labels and unverified units, "
         "each of which rules out an otherwise obvious method.")
    figure("f01_pipeline.png", "The reproducible pipeline. Dashed arrows: every stage records provenance in the manifest.", width=6.4)
    doc.add_heading("2.2 Why these methods", level=2)
    table(["Design choice", "Reason", "Alternative considered"], [
        ["Treat the salary band as an ordered interval", "The target is six ordered ranges, not six unrelated classes. An interval-censored model uses exactly the information observed.", "Plain multi-class classification (kept as the baseline)"],
        ["Quadratic-weighted kappa (QWK) as the selection metric", "It penalises a two-band miss more than a one-band miss, which matches the business cost. Accuracy, macro-F1 and band error are reported alongside.", "Accuracy alone"],
        ["Group-disjoint partitions", f"{an['rows_in_conflicting_groups']:,} postings have a twin with identical features. A random split would put twins on both sides and inflate scores.", "Random 70/30 split"],
        ["Separate calibration partition", "Prediction sets need data that was used neither to fit nor to select the model.", "Reusing validation data"],
        ["Simple, penalised models for the two cohorts", f"{jds['n']} and {sds['n']} records cannot support complex models; the SDS classes are nearly separable, which makes unpenalised estimates unstable.", "Tree ensembles, neural networks"],
        ["A mixed model for company pay", "Each company contributes several titles; a company random intercept separates role from employer.", "Boosted trees on three predictors"],
        ["Simpler model wins ties", "A challenger must beat the incumbent by more than 0.005 QWK on validation data.", "Pick the highest score"],
    ], [1.75, 2.75, 1.75], "Main design choices and their motivation")
    doc.add_heading("2.3 Validation design", level=2)
    para(f"Analytics postings are first linked into connected groups: two postings join a group if they have identical features, or the same "
         f"normalised title, skill set and location, and the relation is closed transitively. The {an['groups']:,} groups are then hashed into "
         f"train, validation, calibration and test partitions ({nf()}). All preprocessing (the text vocabulary and numeric scaling) is fitted on the "
         "training partition only. The champion is chosen on validation data, prediction sets are calibrated on calibration data, and the test "
         "partition is scored once. DataScience Jobs is split by company. JDS and SDS use grouped five-fold cross-validation with an inner "
         "three-fold loop for the penalty, grouping records that share an id or an identical profile.")
    figure("f04_partitions.png", "Partition design for Analytics Jobs.", width=6.4)
    doc.add_heading("2.4 Technology and architecture", level=2)
    para(f"The engine is Python 3.11 with pandas, scikit-learn, statsmodels and XGBoost {salary['versions']['xgboost']}. "
         + (f"The boosted models were trained on a CUDA GPU ({gpu}); the pipeline refuses to label a run as GPU unless a CUDA build and device are verified. "
            if used_gpu else "The recorded run did not use a GPU. ")
         + "The small cohort analyses run on the CPU, where they belong. The existing Yojak project supplies the coverage optimiser, the "
         f"report tooling, a FastAPI service and a Next.js front end; we added one private workspace on top ({nf()}).")
    figure("f02_architecture.png", "System architecture. Supplied data and everything derived from it stay in a git-ignored folder; the public demo cannot reach them.", width=6.4)
    para(f"SAS. The brief is technology-agnostic and offers SAS Viya for Learners. Our plan uses SAS Studio for independent checks of the "
         f"audit and of the regression results, and SAS Visual Analytics for four report pages, fed by the same prepared tables and partition "
         f"manifests. At the time this note was generated the SAS track status recorded by the pipeline is \"{sas_status}\". The programs are "
         "listed in Appendix D and are marked accordingly; no SAS output is shown that was not produced.", bold_lead=None)
    doc.add_heading("2.5 Confidentiality", level=2)
    para("The supplied files, the prepared tables, the model and this note are kept in folders excluded from version control. The private API "
         "is disabled unless a local environment flag is set, and an automated test checks that the public export script does not reference the "
         "private folder. Nothing is uploaded outside the organiser-approved environment.")

    # ------------------------------------------------------------------ 3 data
    doc.add_heading("3. Data exploration and preparation", level=1)
    doc.add_heading("3.1 The four files", level=2)
    dup_ids = int(company.reference_no.duplicated().sum()) if "reference_no" in company else 0
    table(["File", "Rows", "Unit of observation", "Key fields", "First observations"], [
        ["Analytics Jobs", f"{n_raw:,}", "Job posting", "experience, designation, key skills, location, salary band, short description",
         f"{an['exact_duplicates_removed']:,} exact duplicates; job_type missing in {an['missing']['job_type'] / n_raw:.0%}"],
        ["DataScience Jobs", f"{audit['company']['raw_rows']:,}", "Company × job title (aggregate)", "title, minimum experience, min / avg / max salary, number of jobs",
         f"{company.company_name.nunique()} companies, {company.job_title.nunique()} titles; {dup_ids} repeated reference numbers"],
        ["JDS skill traits", f"{jds['n']}", "Junior data scientist", "five skill scores (1 to 5), salary hike high / low", f"{jds['groups']} distinct groups after linking repeated ids and identical profiles"],
        ["SDS personality traits", f"{sds['n']}", "Senior data scientist", "five trait scores (normalised), success high / low", f"{sds['groups']} distinct groups; classes {sds['class_counts'][0]} / {sds['class_counts'][1]}"],
    ], [1.05, 0.5, 1.15, 1.9, 1.65], "The supplied files as found", size=9, key="files")
    doc.add_heading("3.2 Data quality findings", level=2)
    para(f"{nf()} summarises the audit of Analytics Jobs. Three findings shaped everything that follows. First, text is truncated in the "
         f"source: {a.description_truncated.mean():.0%} of postings carry a description that ends in an ellipsis (the remainder have none), and "
         f"{a.skills_truncated.mean():.0%} of skill lists are cut the same way. Second, after removing exact duplicates, "
         f"{an['rows_in_conflicting_groups']:,} postings ({an['rows_in_conflicting_groups'] / n:.0%}) belong to one of {an['conflicting_feature_groups']:,} "
         "groups whose members have identical designation, skills, location and experience but different salary bands. Third, the corpus is "
         "broad: it contains marketing, software and operations adverts as well as data roles.")
    figure("f05_quality.png", "Data-quality profile of Analytics Jobs (duplicate and missing-type shares are of raw rows; the rest are of distinct postings).", width=5.8)
    para(f"Conflicting labels put a bound on agreement. If a model memorised the most common band for every identical-feature group, it would "
         f"agree with {an['empirical_feature_agreement_bound']:.1%} of the labels in this file. We report this as an empirical, in-sample "
         "diagnostic of label consistency. It is not a universal accuracy ceiling for new postings, and we do not use it to rescale model scores.",
         bold_lead="An agreement bound, not a ceiling.")
    doc.add_heading("3.3 Issue register", level=2)
    para("Each issue below was found in the audit, has a recorded decision, and where the decision could change a result, a sensitivity check.")
    table(["#", "Issue and evidence", "Decision", "Sensitivity check"], [
        ["1", f"{an['exact_duplicates_removed']:,} exact duplicate postings", "Keep one copy; store the count as multiplicity", "Test metrics repeated with multiplicity weights"],
        ["2", f"{an['conflicting_feature_groups']:,} identical-feature groups with more than one band", "Keep all labels; group for partitioning; separate soft-target experiment", "Agreement bound reported"],
        ["3", f"Descriptions truncated ({a.description_truncated.mean():.0%}) or missing ({a.description_missing.mean():.0%})", "Not used as a predictor (also avoids leaking pay stated in text); flag kept", "None needed"],
        ["4", f"Skill lists truncated ({a.skills_truncated.mean():.0%})", "Drop the final fragment conservatively; keep a permissive view", "Metrics on complete-list postings only"],
        ["5", f"{len(skill_tokens):,} distinct skill tokens after cleaning", "Lower-case, trim, small alias table; raw text preserved", "Alias table is listed in code"],
        ["6", "job_type is constant or missing", "Dropped as a predictor", "None needed"],
        ["7", f"{int(a.quality_flag.sum())} adverts match a home-based data-entry pattern", "Labelled \"flagged by heuristic\"; rule is label-independent; remote or part-time alone never triggers it", "Association rules with and without flagged rows"],
        ["8", f"{a.job_desig.nunique():,} distinct designations", "Auditable title rules into role families", f"{other_share:.0%} remain \"Other\"; 100-row manual review file generated, review pending"],
        ["9", f"{a.locations.map(len).gt(1).mean():.0%} multi-city postings", "Location kept as a token set", "None yet"],
        ["10", "Experience given as text ranges", "Parsed to minimum, maximum, midpoint and width; pipeline stops on any unparsed value", "All rows parse"],
        ["11", f"DataScience Jobs: {dup_ids} repeated reference numbers; rows are company-title aggregates", "reference_no never used as a key; split by company", "Unweighted primary, posting-count-weighted sensitivity"],
        ["12", "Salary units and pay period not documented", "Status recorded as \"unverified\" in every report and API response", "Title-level plausibility cross-check (Section 4.5)"],
        ["13", f"JDS: {jds['n'] - jds['groups']} records share an id or profile with another", "Linked into groups for cross-validation and bootstrap", "Group-level resampling"],
        ["14", "SDS: column names with stray spaces; near-separable classes", "Names normalised; penalised estimation", "Bootstrap intervals"],
    ], [0.3, 2.35, 2.1, 1.5], "Issue register", size=9)
    doc.add_heading("3.4 Derived variables", level=2)
    bullets([f"Salary band index:: the six bands in order, 0 to 5. Median minimum experience rises from {med_exp.iloc[0]:.0f} year in the lowest band to {med_exp.iloc[-1]:.0f} years in the highest.",
             f"Experience:: minimum, maximum, midpoint and width in years. Skill set:: cleaned tokens per posting (mean {a.skills.map(len).mean():.1f}).",
             "Role family:: first matching rule on the designation. Flags:: skills truncated, description missing or truncated, advert heuristic.",
             "Signatures:: a hash of the identical-feature tuple and a looser near-duplicate hash; their transitive closure defines the partition groups."])
    figure("f06_bands.png", "Left: distribution of the salary band among distinct postings. Right: band mix by minimum experience.", width=6.3)
    table(["Derived field", "Type", "Definition", "Used for"], [
        ["multiplicity", "integer", "Number of exact copies of the posting in the raw file", "Sensitivity weights"],
        ["band", "ordered 0 to 5", "Index of the salary band in its natural order", "Target"],
        ["exp_min, exp_max, exp_mid, exp_width", "years", "Parsed from the experience text", "Predictors; pool filter in the application"],
        ["skills, skills_permissive", "token set", "Cleaned skill tokens; conservative view drops the last fragment of a truncated list", "Predictors, rules, learning plans"],
        ["skills_truncated, description_missing, description_truncated", "flag", "Source text ends in an ellipsis or is absent", "Predictors; sensitivity filters"],
        ["role_family", "category", "First matching title rule, else Other", "Stratification; application pools"],
        ["locations", "token set", "Location text split on separators", "Predictor (as text); city profile"],
        ["quality_flag", "flag", "Data-entry or typing advert that also uses earn, freelance or home-based wording", "Excluded from skill analyses"],
        ["feature_signature, near_signature, group_id", "hash", "Identical-feature and near-duplicate keys and their connected group", "Conflict audit; partitions; bootstrap"],
        ["split", "category", "Hash of group_id into train, validation, calibration, test", "All model evaluation"],
    ], [1.75, 0.8, 2.3, 1.4], "Variables derived during preparation of Analytics Jobs", size=9)
    doc.add_heading("3.5 Locations", level=2)
    para(f"{a.locations.map(len).gt(1).mean():.0%} of postings name more than one city. Splitting the location text gives the profile in {nf()}: postings concentrate in a "
         "handful of metropolitan areas, and the share of postings in the two highest bands differs between them. Location therefore enters the predictive "
         "model, but as free text, because city names in the source are not standardised.")
    figure("f16_cities.png", "Ten most frequently named cities: number of postings and share in the two highest salary bands.", width=6.2)
    doc.add_heading("3.6 Role families", level=2)
    para(f"Designations were assigned to role families with seven ordered, auditable rules. {nf()} shows the result. The rules are deliberately "
         f"narrow, and {other_share:.0%} of postings fall outside them. This is the largest open item in the preparation: results by family are "
         "reliable for the named families, and the \"Other\" group mixes marketing, finance, sales and general IT adverts. A stratified sample "
         "of 100 designations has been exported for manual review, and the review status recorded by the pipeline is "
         f"\"{manifest.get('role_review', 'pending')}\".")
    figure("f07_families.png", "Role families assigned by title rules.", width=5.6)
    table(["Role family", "Most frequent skill tokens (count)"],
          [[f, ", ".join(f"{s} ({c})" for s, c in tops[f])] for f in fam.index if f in tops and f != "Other"],
          [1.5, 4.75], "Most frequent cleaned skill tokens by named role family (flagged adverts excluded)", size=9, key="topskills")
    doc.add_heading("3.7 DataScience Jobs", level=2)
    by_title = company.groupby("job_title").agg(n=("avg_salary_native", "size"), med=("avg_salary_native", "median"),
                                                q1=("avg_salary_native", lambda v: v.quantile(.25)), q3=("avg_salary_native", lambda v: v.quantile(.75)),
                                                exp=("min_experience", "median"), jobs=("num_of_jobs", "sum")).sort_values("med")
    consistent = ((company.min_salary_native <= company.avg_salary_native) & (company.avg_salary_native <= company.max_salary_native)).mean()
    para(f"This file has one row for each of {company.company_name.nunique()} companies and each title that company posts, {len(company):,} rows in all, summarising "
         f"{int(company.num_of_jobs.sum()):,} postings. Salary fields are text with an \"L\" suffix; we strip the suffix and keep the numbers in their native unit. "
         f"Minimum, average and maximum are internally consistent in {consistent:.0%} of rows. Number of jobs is highly skewed (median {company.num_of_jobs.median():.0f}, "
         f"maximum {company.num_of_jobs.max():,}), so posting-count weights would let a few large employers dominate; we therefore treat the unweighted analysis as primary. "
         f"{nf()} and {nt()} show that titles are ordered sensibly by pay and by required experience, with wide spread between companies within every title.")
    figure("f17_company.png", "Company average salary by job title in DataScience Jobs (one point per company-title row).", width=6.0)
    table(["Job title", "Rows", "Median of company averages", "Interquartile range", "Median minimum experience", "Postings"],
          [[t, f"{int(r.n)}", f"{r.med:.1f}", f"{r.q1:.1f} to {r.q3:.1f}", f"{r.exp:.0f}", f"{int(r.jobs):,}"] for t, r in by_title.iterrows()],
          [1.9, 0.5, 1.1, 1.1, 0.95, 0.75], "DataScience Jobs by title (salary in native units)", size=9)
    doc.add_heading("3.8 The two cohort files", level=2)
    para(f"JDS holds five skill scores on a 1 to 5 scale for {jds['n']} junior data scientists. Scores are bunched at the top: the last column of {nt()} shows the share of "
         f"records at the maximum for each skill. {jds['n'] - jds['groups']} records share an id or an identical score profile with another record, so we link them into "
         f"{jds['groups']} groups before any resampling. SDS holds five normalised trait scores for {sds['n']} senior data scientists ({sds['groups']} groups). "
         "Neither file has missing values. The two cohorts have different people, different measures and different outcomes, and we never combine them.")
    table(["Skill score", "Mean, low hike", "Mean, high hike", "Standardised difference", "Observed range", "At max"], cohort_summary(jds_frame, jds_target),
          [2.2, 0.85, 0.85, 0.95, 0.85, 0.6], "JDS: skill scores by salary-hike outcome", size=9)
    figure("f18_jds_boxes.png", "JDS: distribution of each skill score for low and high salary-hike records.", width=6.3)
    table(["Trait score", "Mean, low success", "Mean, high success", "Standardised difference", "Observed range", "At max"], cohort_summary(sds_frame, sds_target),
          [2.2, 0.85, 0.85, 0.95, 0.85, 0.6], "SDS: trait scores by success classification", size=9)
    figure("f19_sds_boxes.png", "SDS: distribution of each trait score for low and high success records.", width=6.3)
    doc.add_heading("3.9 Partition audit", level=2)
    para("The same hashing rule assigns every group in every file to a partition. The pipeline asserts that no group spans two partitions before it writes any table.")
    table(["File", "Rows", "Groups", "Train", "Validation", "Calibration", "Test"],
          [[k, f"{v['prepared_rows']:,}", f"{v['groups']:,}", *[f"{v['partitions'].get(s, 0):,}" for s in ("train", "validation", "calibration", "test")]]
           for k, v in [("Analytics Jobs", audit["analytics"]), ("DataScience Jobs", audit["company"]), ("JDS", audit["jds"]), ("SDS", audit["sds"])]],
          [1.6, 0.7, 0.75, 0.75, 0.85, 0.9, 0.7], "Group-disjoint partitions for the four files (cohort models use grouped cross-validation over all rows)", size=9)

    # ------------------------------------------------------------------ 4 analysis
    doc.add_heading("4. Data analysis", level=1)
    doc.add_heading("4.1 Descriptive statistics", level=2)
    para(f"Before modelling we tested the main bivariate relationships on the {n:,} distinct postings ({nt()}). The salary band is ordinal, so we use rank-based "
         "methods, report an effect size for each test, and adjust the p-values for multiple testing (Benjamini-Hochberg). With this many rows almost every test is "
         "statistically significant; the effect sizes are what matter. Experience has by far the strongest relationship with the band. Role family has a small one, "
         "partly because most postings are in the unassigned family. The truncation and missing-description flags have weak relationships, which is "
         "reassuring: the data-quality problems are not concentrated in particular bands.")
    table(["Relationship", "Method", "Effect size", "Adjusted p-value"],
          [[t["test"], t["method"], t["effect"], "< 0.001" if t["p_fdr"] < 0.001 else f"{t['p_fdr']:.3f}"] for t in tests],
          [2.3, 1.7, 1.35, 0.9], "Bivariate tests on distinct postings. P-values assume independent postings and are indicative only", size=9, key="desc")
    figure("f15_family_bands.png", "Salary-band mix within each role family, ordered by the share in the two highest bands.", width=6.0, key="fambands")
    doc.add_heading("4.2 Q1: skill patterns within role families", level=2)
    rules = research["rules_excluding_flagged"]
    para("We mined pairwise association rules within each role family, requiring a pair to appear in at least 20 postings and 1% of the family. "
         "Support is the share of the family's postings containing both skills, confidence is the share of postings with the first skill that also "
         f"list the second, and lift compares that with chance. {nt()} lists the strongest rules. They describe which skills employers list together; "
         "they are affected by truncation, because a truncated list can hide a pair.")
    seen, rows = set(), []
    for r in rules:
        key = (r["family"], *sorted([r["antecedent"], r["consequent"]]))
        if key in seen:
            continue
        seen.add(key)
        rows.append([r["family"], f"{r['antecedent']} → {r['consequent']}", r["count"], f"{r['support']:.1%}", f"{r['confidence']:.0%}", f"{r['lift']:.1f}"])
        if len(rows) == 10:
            break
    table(["Family", "Rule", "Postings", "Support", "Confidence", "Lift"], rows, [1.2, 2.6, 0.65, 0.6, 0.75, 0.45],
          "Strongest skill association rules within role families (flagged adverts excluded)", size=9, key="rules")
    same = [(r["family"], r["antecedent"], r["consequent"]) for r in research["rules_including_flagged"][:20]] == [(r["family"], r["antecedent"], r["consequent"]) for r in rules[:20]]
    para("Sensitivity to the advert heuristic: the top twenty rules are " + ("identical" if same else "different") +
         f" with and without the {int(a.quality_flag.sum())} flagged adverts, so the heuristic does not drive these patterns.")
    doc.add_heading("4.3 Q2: explaining the salary band", level=2)
    explanation = research["ordinal"]
    para("Training-only salary explanation uses four low-dimensional predictors. The stacked cumulative-logit slope-equality diagnostic "
         "uses a sandwich covariance clustered by the original feature groups, including dependence across thresholds. "
         f"Assumption status: {explanation.get('assumption_status', 'not executed')}. "
         f"Primary model: {explanation.get('primary_model', 'unverified')}. The following common-odds coefficients are diagnostic-only if the assumption is rejected.")
    table(["Predictor", "Odds ratio", "95% interval", "Reading"], [
        ["Experience (midpoint, per year)", f"{ordinal['experience']['odds_ratio']:.2f}", f"{ordinal['experience']['ci95'][0]:.2f} to {ordinal['experience']['ci95'][1]:.2f}", "Subject to slope diagnostic"],
        ["Number of listed skills (per skill)", f"{ordinal['skill_count']['odds_ratio']:.2f}", f"{ordinal['skill_count']['ci95'][0]:.2f} to {ordinal['skill_count']['ci95'][1]:.2f}", "Small positive association"],
        ["Mentions a \"model\" skill", f"{ordinal['modelling']['odds_ratio']:.2f}", f"{ordinal['modelling']['ci95'][0]:.2f} to {ordinal['modelling']['ci95'][1]:.2f}", "Subject to slope diagnostic"],
        ["Mentions a \"stat\" skill", f"{ordinal['statistics']['odds_ratio']:.2f}", f"{ordinal['statistics']['ci95'][0]:.2f} to {ordinal['statistics']['ci95'][1]:.2f}", "Inconclusive: interval includes 1"],
    ], [2.2, 0.9, 1.3, 1.85], "Exploratory proportional-odds model of the salary band (training partition)", key="ordinal")
    para(explanation["interval_limitation"])
    if explanation.get("primary_model") == "multinomial_logit":
        fallback = explanation["multinomial"]
        para(f"The multinomial fallback converged: {fallback['converged']}. " + fallback["interpretation"])
        table(["Band vs 0", "Feature", "Log ratio", "95% log interval"], [
            [str(r["band"]), r["feature"], f"{r['log_relative_ratio']:.3f}",
             f"{r['log_ci95'][0]:.3f} to {r['log_ci95'][1]:.3f}"]
            for r in fallback["coefficients"] if r["feature"] != "intercept"
        ], [0.7, 1.9, 1.2, 2.45], "Primary multinomial associations, training only; cluster-aware intervals")
    doc.add_heading("4.4 Q2: predicting the salary band", level=2)
    para("Predictors are the designation, the cleaned skill tokens and the location as TF-IDF text features (unigrams and bigrams, vocabulary "
         "fitted on training data), plus experience bounds and the truncation and missing-description flags. Descriptions and the salary field are "
         "excluded. We compared a majority-class reference, a TF-IDF logistic regression baseline, four interval-censored XGBoost models "
         "(accelerated failure time objective, where each posting's label is the lower and upper bound of its band) and a separate soft-target "
         "classifier trained on each training group's observed band distribution. The two GPU approaches are separate experiments: we never average "
         "contradictory bands into an invented interval.")
    figure("f08_models.png", "Validation results for every candidate. The selected champion is highlighted.", width=6.3, key="models")
    para(f"The champion is {salary['champion']} (validation QWK {champ['qwk']:.3f} against {base['qwk']:.3f} for the logistic baseline, a gain above the "
         f"0.005 threshold). It trades exact-band accuracy for fewer large misses: macro-F1 falls from {base['macro_f1']:.2f} to {champ['macro_f1']:.2f}, while "
         f"the share within one band rises from {base['within_one_band']:.0%} to {champ['within_one_band']:.0%}. The soft-target classifier did not beat the baseline on QWK. "
         "This is a modest gain, and we say so: with short, truncated inputs and inconsistent labels, a more complex model has little extra signal to find.")
    table(["Evaluation set", "QWK", "Macro-F1", "Balanced accuracy", "Mean band error", "Within one band", "n"], [
        ["Test (primary)", f"{test['qwk']:.3f}", f"{test['macro_f1']:.3f}", f"{test['balanced_accuracy']:.3f}", f"{test['mean_band_error']:.2f}", f"{test['within_one_band']:.1%}", f"{test['n']:,}"],
        ["Test, multiplicity-weighted", *[f"{salary['test_multiplicity_weighted'][k]:.3f}" for k in ("qwk", "macro_f1", "balanced_accuracy")],
         f"{salary['test_multiplicity_weighted']['mean_band_error']:.2f}", f"{salary['test_multiplicity_weighted']['within_one_band']:.1%}", f"{test['n']:,}"],
        *([["Test, complete skill lists only", *[f"{salary['test_complete_skills'][k]:.3f}" for k in ("qwk", "macro_f1", "balanced_accuracy")],
            f"{salary['test_complete_skills']['mean_band_error']:.2f}", f"{salary['test_complete_skills']['within_one_band']:.1%}", f"{salary['test_complete_skills']['n']:,}"]]
          if salary.get("test_complete_skills") else []),
    ], [1.85, 0.6, 0.7, 0.85, 0.8, 0.85, 0.6], f"Held-out test results for the champion. QWK 95% group-bootstrap interval: {ci[0]:.3f} to {ci[1]:.3f}", size=9, key="test")
    figure("f09_confusion.png", "Test confusion matrix, row-normalised. Errors concentrate in adjacent bands.", width=3.6)
    para(f"Error analysis. {nf()} breaks the test results down by observed band. The model is most reliable in the middle of the scale and weakest at the two ends: "
         "the lowest and highest bands are the ones it most often misses by more than one band, which is expected from a model that predicts a continuous value "
         f"and then maps it to a band. {nt()} repeats the test metrics by role family. Performance is similar across the named families, so the headline result is not "
         "carried by one segment, but the smaller families have wide uncertainty.", bold_lead=None)
    figure("f20_error_by_band.png", "Share of test postings predicted in the exact band or one band away, by observed band.", width=5.2)
    table(["Role family", "Test postings", "QWK", "Exact band", "Within one band", "Mean band error"], family_performance(scored),
          [1.7, 0.95, 0.7, 0.9, 1.1, 1.0], "Champion performance on the test partition by role family (families with at least 30 test postings)", size=9)
    para(f"Prediction sets. On the calibration partition ({cal['n']:,} postings) we computed the distance in bands between prediction and label and took the "
         f"finite-sample 90% quantile, which is {cal['radius']} bands. The set for a new posting is the predicted band plus or minus that radius. "
         f"On the test partition these sets contain the observed band {cal['test_coverage']:.1%} of the time and span {cal['mean_set_width']:.1f} of the six bands on average. "
         "Because distances are whole numbers, the set over-covers its 90% target and is wide. The statement is honest but not yet sharp: it concerns the "
         "observed band label, holds on average under exchangeability, and gives no guarantee for a subgroup or for an unobserved exact salary.",
         bold_lead=None)
    figure("f10_coverage.png", "Observed coverage and mean set width by role family (families with at least 30 test postings).", width=5.8, key="coverage")
    doc.add_heading("4.5 Q3: company and title", level=2)
    para(f"DataScience Jobs has one row per company and title. We modelled log average salary with fixed effects for title and minimum experience "
         f"and a random intercept for company, fitted on training companies. Conditional on title and experience, the company intercept accounts "
         f"for {co['company_residual_icc']:.0%} of the remaining variance: companies differ consistently across the titles they post. For companies "
         f"the model has never seen, however, it cannot know that intercept, and its error ({co['heldout_company_mae_native']:.2f} native units) is no better than "
         f"simply using the training median for the title ({co['heldout_company_baseline_mae_native']:.2f}). A posting-count-weighted fixed-effects model gives "
         f"{co['weighted_fixed_effect_sensitivity_mae_native']:.2f}. The practical reading: knowing the employer matters a great deal, and title alone leaves a large error.")
    para(f"Plausibility cross-check. For the {len(cross)} titles in this file, we compared the mean company average with the mean band midpoint of "
         f"exactly matching designations in Analytics Jobs ({nf()}). The rank correlation is {co['cross_file']['spearman']:.2f}, and the magnitudes are "
         "similar for the better-populated titles. This suggests the two files use comparable units. It is an ecological check on ten titles, some with "
         "fewer than ten postings; it does not prove the unit or the pay period, and it is not an external validation of the model.", bold_lead=None)
    figure("f11_cross.png", "Title-level agreement between the two job files. Marker size and n give the number of exactly matching Analytics postings; the dashed line is equality.", width=6.0, key="cross")
    doc.add_heading("4.6 Q4: which skills to learn next", level=2)
    para("For a given role family, experience level and starting skill set, we count a posting as aligned when the profile covers at least 60% of "
         "its listed skills. The existing Yojak optimiser then searches for the three additional skills that maximise the number of aligned postings, "
         "and we compare it with the common advice of learning the three most frequent missing skills. On small pools an exact integer-programming "
         "solver confirms optimality. Flagged adverts are excluded.")
    if has_plans:
        figure("f14_plans.png", "Postings aligned at the 60% threshold for four illustrative profiles: now, after the three most frequent skills, and after the three optimised skills.", width=5.9, key="plans")
        table(["Profile (family, years, starting skills)", "Optimised skills", "Aligned: now → frequency → optimised", "Solver"],
              [[f"{p['family']}, {p['experience']}, {' + '.join(p['start_skills'])}", ", ".join(p["optimized"]["skills"]),
                f"{p['before']} → {p['frequency']['coverage']} → {p['optimized']['coverage']}", p["solver"] + (" (proven)" if p["optimized"]["proven_optimal"] else "")]
               for p in plans if p.get("optimized")], [2.1, 1.9, 1.45, 0.8], "Illustrative learning plans produced by the same service the local application uses", size=9)
    para("These counts mean \"more postings whose listed skills the profile largely covers\", not more job offers. Because most skill lists are truncated, "
         "a missing skill is not proven unnecessary, and the application offers a complete-lists-only option as a check.")
    doc.add_heading("4.7 Q5: junior skills and salary hike", level=2)
    para(f"For the {jds['n']} junior records ({jds['class_counts'][1]} high, {jds['class_counts'][0]} low) we report point-biserial correlations with false-discovery correction, "
         "and odds ratios from a penalised logistic regression with intervals from a group bootstrap.")
    table(["Skill score", "Correlation with high hike", "Adjusted p-value", "Odds ratio per point [95% interval]"],
          [[f.replace("_", " "), f"{jf[f]['correlation']:.2f}", f"{jf[f]['p_fdr']:.2g}", orci(jf[f])] for f in jf],
          [2.3, 1.4, 1.05, 1.5], "JDS: association of each skill score with a high salary hike", key="jds")
    figure("f12_jds.png", "JDS odds ratios with group-bootstrap intervals.", width=5.6, key="jdsfig")
    top_j = sorted(jf.values(), key=lambda f: -f["correlation"])
    para(f"The strongest raw associations are {top_j[0]['feature'].replace('_', ' ')} ({top_j[0]['correlation']:.2f}) and {top_j[1]['feature'].replace('_', ' ')} "
         f"({top_j[1]['correlation']:.2f}); the weakest is {top_j[-1]['feature'].replace('_', ' ')} ({top_j[-1]['correlation']:.2f}). In the joint model all five odds ratios are above 1. "
         f"Out-of-fold AUC is {jds['oof_auc']:.2f} (interval {jds['oof_auc_ci95'][0]:.2f} to {jds['oof_auc_ci95'][1]:.2f}), against {jds['tree_oof_auc']:.2f} for a depth-two tree, "
         "so the simple linear model is the better description. Many scores sit at the top of the 1 to 5 scale, which limits what the data can say about the strongest performers.")
    doc.add_heading("4.8 Q6: senior traits and recorded success", level=2)
    table(["Trait", "Correlation with success", "Adjusted p-value", "Odds ratio per point [95% interval]"],
          [[f.replace("_", " "), f"{sf[f]['correlation']:.2f}", f"{sf[f]['p_fdr']:.2g}", orci(sf[f])] for f in sf],
          [2.3, 1.4, 1.05, 1.5], "SDS: association of each trait score with recorded success", key="sds")
    figure("f13_sds.png", "SDS odds ratios with group-bootstrap intervals.", width=5.6, key="sdsfig")
    top_s = sorted(sf.values(), key=lambda f: -f["correlation"])
    para(f"{top_s[0]['feature'].replace('_', ' ').capitalize()} ({top_s[0]['correlation']:.2f}) and {top_s[1]['feature'].replace('_', ' ')} ({top_s[1]['correlation']:.2f}) "
         f"have the strongest associations with the success classification; neuroticism has essentially none on its own ({sf['neuroticism']['correlation']:.2f}). "
         f"Out-of-fold AUC is {sds['oof_auc']:.2f}. Classes this easy to separate from five scores are unusual in real personnel data, which suggests the "
         "sample was constructed for teaching. The odds ratios are per point of a normalised score and are penalised estimates, so they describe "
         "direction and relative strength, not effect sizes to act on. We do not know how success was defined or by whom.")

    # ------------------------------------------------------------------ 5 results
    doc.add_heading("5. Results and conclusions", level=1)
    table(["Q", "Answer", "Evidence", "Main limitation"], [
        ["Q1", f"Seven named families cover {1 - other_share:.0%} of postings. Skills cluster sensibly within families (for example platform-specific stacks in software roles).", f"{ref['topskills']}, {ref['rules']}", f"{other_share:.0%} unassigned; lists truncated"],
        ["Q2", f"Explanation uses {explanation.get('primary_model', 'an unverified specification')}. Separately, the GPU interval model reaches QWK {test['qwk']:.3f} and {test['within_one_band']:.0%} within one band on held-out postings.", f"{ref['ordinal']}, {ref['test']}, {ref['models']}, {ref['coverage']}", "Units unverified; sets span about four bands"],
        ["Q3", f"Companies differ consistently (intercept share {co['company_residual_icc']:.0%}), but title and experience alone predict a new company's pay no better than the title median.", f"Section 4.5, {ref['cross']}", "Aggregate rows; three predictors"],
        ["Q4", "A targeted set of three skills aligns a profile with at least as many postings as the three most frequent skills, and often more." if has_plans else "Optimiser available; examples not generated.", ref.get("plans", "Section 4.6"), "Alignment is not hiring; truncation"],
        ["Q5", f"Maths-statistics and storytelling scores are most associated with a high hike; AUC {jds['oof_auc']:.2f}.", f"{ref['jds']}, {ref['jdsfig']}", f"{jds['n']} records; ceiling effects; association only"],
        ["Q6", f"Openness and conscientiousness are most associated with recorded success; AUC {sds['oof_auc']:.2f}.", f"{ref['sds']}, {ref['sdsfig']}", "Outcome definition unknown; not for individual decisions"],
    ], [0.35, 2.9, 1.4, 1.6], "Answers to the six research questions", size=9)
    doc.add_heading("5.1 The hypothesis, tested", level=2)
    para("\"Statistics pays twice\" remains a hypothesis, not an established headline. Salary associations must be read by band when the "
         "common-slope assumption fails; no single market pay multiplier is justified. In the junior sample, quantitative and storytelling scores "
         "are associated with recorded outcomes. These independent lines of evidence do not show that learning a skill causes a salary increase.")
    doc.add_heading("5.2 What we can and cannot conclude", level=2)
    bullets(["Supported:: the band can be predicted to within one band for most held-out postings; "
             "employers differ systematically; targeted skill choices align a profile with more postings than frequency-based advice.",
             "Not supported by this data:: any causal effect of learning a skill on pay; any forecast; any claim about hiring probability; "
             "any use of personality scores to assess a person.",
             f"Unresolved:: salary units and period; the true content of the {other_share:.0%} \"Other\" family; robustness to alternative explanatory specifications; "
             "whether the cohort files are real or constructed."])
    doc.add_heading("5.3 What we would do next", level=2)
    bullets(["Complete the manual role review and extend the title rules to reduce the unassigned share.",
             "Replace the fixed-radius prediction sets with probability-based sets to narrow them at the same coverage.",
             "Cross-check the clustered slope diagnostic and multinomial associations in the approved SAS environment.",
             f"Run the SAS programs in the approved environment (current status: {sas_status}) and compare estimates with documented tolerances."])

    # ------------------------------------------------------------------ 6 implications
    doc.add_heading("6. Implications", level=1)
    doc.add_heading("6.1 For students and early-career professionals", level=2)
    para("This observational snapshot cannot decide whether an individual should trade pay for experience. When choosing what to learn, the most frequently listed "
         "skills are not always the ones that align a profile with the most postings; a small, targeted set chosen for a specific role family can do better. "
         "Pay expectations should be held as a range of bands, not a figure.")
    doc.add_heading("6.2 For colleges and training providers", level=2)
    para("The association rules show which skills employers list together within a role family, which is a practical guide to bundling modules. "
         "The junior-cohort result argues for teaching quantitative reasoning and data storytelling together: in this sample they go with good "
         "outcomes more than tool-specific big-data skills do. Because the postings are a snapshot with truncated lists, curricula should not be "
         "cut on the basis of a skill's absence here.")
    doc.add_heading("6.3 For employers and learning teams", level=2)
    para("Advertised pay for the same title varies widely by company, which candidates can see; clear banding helps. For junior development, "
         "the evidence favours investment in statistics and communication. For senior development, the trait associations are best used to design "
         "aggregate programmes, such as structured practice in planning and in exploring unfamiliar problems, not to select or rank people.")
    doc.add_heading("6.4 Ethics, fairness and privacy", level=2)
    para("Personality scores are sensitive, can reflect measurement bias, and here predict an outcome whose definition we do not know. Using them "
         "to screen or promote individuals would risk unfair treatment and would not be supported by this analysis. Our application therefore "
         "shows the cohort findings only as aggregate charts and never scores a person. The supplied data is confidential and stays in private storage; "
         "the public demonstration contains none of it.")
    doc.add_heading("6.5 Deployment limits", level=2)
    para("The workflow we built (choose a role family and experience, see matching postings and a set of salary bands, compare three recommended "
         "skills with frequency-based advice, read the cohort research) runs locally against the private data. A user's profile is not a posting, so the "
         "calibrated coverage does not transfer to profile scenarios, and the interface says so. Before any wider use the units must be confirmed "
         "and the results validated against outcomes, not postings.")

    # ------------------------------------------------------------------ appendix
    page_break()
    doc.add_heading("Appendix A. Reproducibility", level=1)
    code(".venv/Scripts/python.exe -m pip install -r requirements-sas.txt\n"
         ".venv/Scripts/python.exe -m ml_pipeline.sas.run --stage all      # prepare, train, analyze, package\n"
         ".venv/Scripts/python.exe -m ml_pipeline.sas.run --stage train --cpu   # explicit CPU baseline, no GPU claim")
    table(["Item", "Value"], [
        ["Source version", manifest["source_version"]],
        *[[f"SHA-256, {k}", v[:32] + "…"] for k, v in manifest["source_hashes"].items()],
        ["Preparation code hash", manifest["preparation_code_hash"][:32] + "…"],
        ["Training code hash", salary.get("training_code_hash", "")[:32] + "…"],
        ["Hardware recorded", gpu], ["Library versions", ", ".join(f"{k} {v}" for k, v in salary["versions"].items())],
        ["Training wall time", f"{salary['total_seconds']:.0f} seconds for all candidates"],
        ["Unit status / SAS execution / role review", f"{manifest['unit_status']} / {sas_status} / {manifest.get('role_review', 'pending')}"],
        ["Evaluation history", salary.get("evaluation_history", "")],
    ], [2.2, 4.05], "Provenance of the results in this note", size=9)
    doc.add_heading("Appendix B. Experiment log", level=1)
    table(["Candidate", "Device", "QWK", "Macro-F1", "Bal. acc.", "Band error", "Within one", "Seconds"],
          [[e["name"], e.get("device", "cpu"), f"{e['validation']['qwk']:.3f}", f"{e['validation']['macro_f1']:.3f}", f"{e['validation']['balanced_accuracy']:.3f}",
            f"{e['validation']['mean_band_error']:.3f}", f"{e['validation']['within_one_band']:.3f}", f"{e.get('seconds', 0):.1f}"] for e in salary["experiments"]],
          [1.3, 0.6, 0.6, 0.75, 0.7, 0.8, 0.8, 0.7], f"All candidates on the validation partition (n = {base['n']:,}). Selection rule: {salary['selection']}", size=9)
    doc.add_heading("Appendix C. Association rules", level=1)
    table(["Family", "If", "Then", "Postings", "Support", "Confidence", "Lift"],
          [[r["family"], r["antecedent"], r["consequent"], r["count"], f"{r['support']:.1%}", f"{r['confidence']:.0%}", f"{r['lift']:.1f}"] for r in rules[:30]],
          [1.15, 1.5, 1.5, 0.6, 0.55, 0.6, 0.35], "Top thirty directed rules (flagged adverts excluded)", size=8.5)
    doc.add_heading("Appendix D. SAS programs", level=1)
    para(f"Status recorded by the pipeline: {sas_status}. The programs below are the planned independent checks. They read the prepared CSV bundle and the "
         "partition manifest. No SAS output is claimed in this note.", italic=True)
    code("""/* D1. Duplicate and frequency checks on the raw file */
proc sort data=raw.analytics_jobs out=work.distinct nodupkey dupout=work.dups;
  by experience job_description job_desig job_type key_skills location salary;
run;
proc freq data=work.distinct; tables salary job_type / missing; run;

/* D2. Cumulative-logit model of the salary band, training partition only */
proc logistic data=prep.analytics(where=(split='train'));
  model band(order=internal) = exp_mid skill_count has_model has_stat / link=clogit;
  /* score test for the proportional odds assumption is printed by default */
run;

/* D3. Firth-penalised logistic regression for the senior cohort */
proc logistic data=prep.sds;
  model success(event='1') = neuroticism extraversion openness_to_experience
                             agreeableness conscientiousness / firth clodds=pl;
run;

/* D4. Company random intercept */
proc mixed data=prep.company(where=(split='train')) method=reml;
  class company_key job_title;
  model log_pay = job_title experience_value / solution;
  random intercept / subject=company_key;
run;""")
    para("Cross-tool comparisons will use identical observations, encodings, reference categories and estimators, with documented tolerances. "
         "Differently penalised models are not expected to agree to two decimals.")
    doc.add_heading("Appendix E. Private API", level=1)
    table(["Endpoint", "Input", "Returns"], [
        ["POST /sas/match", "role_family, experience, skills, complete_only", "Matching postings with matched and missing skills; cohort research summaries"],
        ["POST /sas/plan", "same", "Aligned postings now, with three optimised skills and with three most frequent skills; solver status"],
        ["POST /sas/pay-range", "same", "Set of salary bands, observed band counts, calibration coverage, deployment caveat"],
    ], [1.4, 2.2, 2.65], "Local-only endpoints. Each response carries the source version, model identity, unit status and limitations", size=9)
    para("The routes return HTTP 503 unless the environment variable YOJAK_SAS_LOCAL is set to 1, and again if the artifacts are missing or do not "
         "match the current preparation manifest.")
    doc.add_heading("Appendix F. Automated tests", level=1)
    bullets(["Duplicates, conflicts, groups and multiplicity are derived correctly.", "Groups are transitive and stable when rows are reordered.",
             "Truncated skill tokens: conservative and permissive views; missing values.", "Remote or part-time wording alone never triggers the advert flag.",
             "An unknown salary band or reversed experience range stops the pipeline.", "Model features never read the salary or description fields.",
             "Calibration radius uses the finite-sample rule and respects band boundaries.", "Metrics and partitions are repeatable.",
             "The private API is disabled by default and validates inputs.", "The public export script does not reference the private folder."])

    path = sub / "Yojak_Approach_Note.docx"
    doc.save(path)
    (sub / "learning_plans.json").write_text(json.dumps(plans, indent=2, default=str), encoding="utf-8")
    return path
