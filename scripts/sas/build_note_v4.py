"""Build a bounded, evidence-linked approach note from private local artifacts."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / "private_sas"
OUT = PRIVATE / "submission"
FIG = OUT / "figures_v4"
FIG.mkdir(exist_ok=True)
TEAL, BLUE, GOLD, RED = "#147D82", "#376399", "#BD8629", "#AD5260"
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 180,
        "savefig.bbox": "tight",
    }
)


def load(name):
    return json.loads((PRIVATE / name).read_text())


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / (name + ".png"), facecolor="white")
    plt.close(fig)


def diagram(name, layers):
    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.set(xlim=(0, 12), ylim=(0, 5))
    ax.axis("off")
    for i, (title, body) in enumerate(layers):
        x = 0.12 + i * 3
        ax.add_patch(
            FancyBboxPatch((x, 1.0), 2.65, 3.0, boxstyle="round,pad=.05", facecolor="#EFF6F6", edgecolor=TEAL)
        )
        ax.text(x + 1.325, 3.5, title, ha="center", va="center", weight="bold", fontsize=12, color=TEAL)
        ax.text(x + 1.325, 2.25, body, ha="center", va="center", fontsize=10, linespacing=1.7)
        if i < len(layers) - 1:
            ax.add_patch(
                FancyArrowPatch(
                    (x + 2.7, 2.5), (x + 2.93, 2.5), arrowstyle="-|>", mutation_scale=15, color=BLUE
                )
            )
    save(fig, name)


def figures(a, c, research, salary, manifest, verify, benchmark, sensitivity):
    diagram(
        "architecture",
        [
            ("Private sources", "Jobs and aggregates\nJunior cohort\nSenior cohort"),
            ("Offline analysis", "Audit and partitions\nCUDA salary model\nGrouped statistics"),
            ("Artifact service", "Version checks\nCPU inference\nCoverage optimizer"),
            ("Career Ladder", "Observed requirements\nThree-skill comparison\nQualified band sets"),
        ],
    )
    diagram(
        "training",
        [
            ("Fit", "8,836 training rows\nTF-IDF and scaler\nNo held-out fitting"),
            ("Select", "2,237 validation rows\nQWK comparison\nGain must exceed .005"),
            ("Calibrate", "1,437 calibration rows\nBand-index residuals\n90% nominal target"),
            ("Evaluate", "2,330 test rows\nQWK and macro-F1\nCoverage and width"),
        ],
    )
    diagram(
        "artifact_contract",
        [
            ("Source snapshot", "SHA-256 hashes\nAudit manifest\nVersioned inputs"),
            ("Prepared tables", "Parquet observations\nFrozen group IDs\nSplit assignments"),
            ("Fitted artifacts", "Training transforms\nBand model and radius\nResearch summaries"),
            ("Private API", "Source-version checks\nMatch and skill plan\nBand-set inference"),
        ],
    )
    diagram(
        "journey",
        [
            ("Profile", "Role and experience\nCurrent skills\nComplete-list filter"),
            ("Evidence", "Observed vocabulary\nMatching postings\nExplicit limitations"),
            ("Compare", "Three new skills\nCoverage vs frequency\nSolver status"),
            ("Decide", "Review requirements\nPlan practice\nNo hiring guarantee"),
        ],
    )
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    q = manifest["audit"]["analytics"]
    labels = ["Raw", "Distinct", "Complete skills", "Flagged"]
    vals = [
        len(a) + q["exact_duplicates_removed"],
        len(a),
        int((~a.skills_truncated).sum()),
        int(a.quality_flag.sum()),
    ]
    axes[0].barh(labels[::-1], vals[::-1], color=[GOLD, BLUE, TEAL, "#8A969E"])
    for i, v in enumerate(vals[::-1]):
        axes[0].text(v + 120, i, f"{v:,}", va="center", fontsize=9)
    axes[0].set(xlim=(0, 19500), title="Observation counts")
    missing = pd.Series(q["missing"]).sort_values().tail(3)
    axes[1].barh(missing.index, missing / q["raw_rows"] * 100, color=RED)
    axes[1].set(xlabel="Percent of raw records", title="Missing fields", xlim=(0, 100))
    save(fig, "quality")
    bands = ["0to3", "3to6", "6to10", "10to15", "15to25", "25to50"]
    bins = pd.cut(a.exp_mid, [-1, 2, 5, 8, 12, 40], labels=["0 to 2", "2 to 5", "5 to 8", "8 to 12", "12+"])
    matrix = pd.crosstab(bins, a.salary).reindex(columns=bands)
    fig, ax = plt.subplots(figsize=(8, 3.8))
    im = ax.imshow(matrix, cmap="YlGnBu", aspect="auto")
    ax.set(
        xticks=range(6),
        xticklabels=bands,
        yticks=range(5),
        yticklabels=matrix.index,
        xlabel="Native salary band",
        ylabel="Experience midpoint in years",
    )
    for i in range(5):
        for j in range(6):
            ax.text(
                j,
                i,
                str(matrix.iloc[i, j]),
                ha="center",
                va="center",
                color="white" if matrix.iloc[i, j] > matrix.to_numpy().max() * 0.55 else "black",
            )
    fig.colorbar(im, ax=ax, label="Distinct postings")
    save(fig, "experience")
    fam = a.role_family.value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.barh(fam.index, fam.values, color=[TEAL if f != "Other" else GOLD for f in fam.index])
    for i, v in enumerate(fam):
        ax.text(v + 80, i, f"{v:,}", va="center")
    ax.set(xlim=(0, fam.max() * 1.17), xlabel="Distinct postings")
    save(fig, "families")
    technical = [
        "python",
        "sql",
        "sas",
        "r",
        "machine learning",
        "hadoop",
        "spark",
        "java",
        "excel",
        "tableau",
        "data analysis",
        "data mining",
    ]
    sets = [set(s) for s in a.skills]
    singles = Counter(s for row in sets for s in row)
    graph = nx.Graph()
    for left, right in combinations(technical, 2):
        count = sum(left in row and right in row for row in sets)
        union = singles[left] + singles[right] - count
        if count >= 20:
            graph.add_edge(left, right, weight=count / union, count=count)
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    pos = nx.spring_layout(graph, seed=31, weight="weight", k=0.9)
    nx.draw_networkx_nodes(
        graph,
        pos,
        ax=ax,
        node_size=[180 + singles[n] * 0.35 for n in graph],
        node_color="#CDE8E5",
        edgecolors=TEAL,
    )
    nx.draw_networkx_edges(
        graph,
        pos,
        ax=ax,
        width=[graph[u][v]["weight"] * 12 for u, v in graph.edges],
        edge_color="#8BA5B5",
        alpha=0.65,
    )
    nx.draw_networkx_labels(graph, pos, ax=ax, font_size=9)
    ax.margins(0.18)
    ax.axis("off")
    save(fig, "network")
    (FIG / "network_data.json").write_text(
        json.dumps(
            {
                "n": len(a),
                "minimum_pair_count": 20,
                "edges": [{"left": u, "right": v, **d} for u, v, d in graph.edges(data=True)],
            },
            indent=2,
        )
    )
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    exps = salary["experiments"]
    ax.barh(
        [e["name"] for e in exps],
        [e["validation"]["qwk"] or 0 for e in exps],
        color=[TEAL if e["name"] == salary["champion"] else BLUE for e in exps],
    )
    for i, e in enumerate(exps):
        ax.text((e["validation"]["qwk"] or 0) + 0.01, i, f"{e['validation']['qwk'] or 0:.3f}", va="center")
    ax.set(xlim=(0, 0.86), xlabel="Validation quadratic weighted kappa")
    save(fig, "models")
    scored = pd.read_csv(PRIVATE / "test_predictions.csv")
    cm = pd.crosstab(scored.band, scored.prediction).reindex(index=range(6), columns=range(6), fill_value=0)
    fig, ax = plt.subplots(figsize=(7.5, 3.7))
    ax.imshow(cm, cmap="Blues", aspect="auto")
    ax.set(
        xticks=range(6),
        yticks=range(6),
        xticklabels=bands,
        yticklabels=bands,
        xlabel="Predicted band",
        ylabel="Observed band",
    )
    for i in range(6):
        for j in range(6):
            ax.text(
                j,
                i,
                str(cm.iloc[i, j]),
                ha="center",
                va="center",
                color="white" if cm.iloc[i, j] > cm.to_numpy().max() * 0.55 else "black",
                fontsize=9,
            )
    save(fig, "confusion")
    fig, ax = plt.subplots(figsize=(8, 3.4))
    sub = salary["calibration"]["by_family"]
    ax.barh(list(sub), [v["coverage"] * 100 for v in sub.values()], color=TEAL)
    ax.axvline(90, color=GOLD, linestyle="--", label="Nominal marginal target")
    ax.set(xlim=(0, 105), xlabel="Observed test coverage (%)")
    ax.legend(loc="lower left", fontsize=8)
    save(fig, "coverage")
    fig, ax = plt.subplots(figsize=(8, 3.8))
    slopes = np.asarray(research["ordinal"]["proportional_odds"]["threshold_slopes"])
    for i, f in enumerate(research["ordinal"]["features"]):
        ax.plot(range(5), slopes[:, i], marker="o", label=f)
    ax.set(
        xticks=range(5),
        xticklabels=["above 0", "above 1", "above 2", "above 3", "above 4"],
        ylabel="Cumulative-logit slope",
        xlabel="Band-index threshold",
    )
    ax.legend(ncol=2, fontsize=9)
    save(fig, "slopes")
    fig, ax = plt.subplots(figsize=(8, 4))
    titles = c.groupby("job_title").avg_salary_native.median().sort_values().index
    ax.boxplot(
        [c.loc[c.job_title == t, "avg_salary_native"] for t in titles],
        orientation="horizontal",
        tick_labels=titles,
        showfliers=False,
    )
    ax.set(xlabel="Reported company-title average pay in native units")
    save(fig, "company")
    paired = sensitivity["paired_mean_band_error"]
    delta, (lower, upper) = paired["delta"], paired["ci95"]
    fig, ax = plt.subplots(figsize=(9, 1.45))
    ax.errorbar(delta, 0, xerr=[[delta - lower], [upper - delta]], fmt="o", color=TEAL,
                capsize=5, linewidth=2, markersize=7)
    ax.axvline(0, color=GOLD, linestyle="--")
    ax.set(yticks=[], ylim=(-.6, .6), xlim=(min(lower, 0) - .007, max(upper, 0) + .007),
           xlabel="Mean band error difference (permissive minus conservative); negative favors permissive")
    save(fig, "token_sensitivity")
    for name in ["jds", "sds"]:
        f = pd.read_parquet(PRIVATE / f"{name}.parquet")
        feats = research[name]["features"]
        target = manifest["audit"][name]["target"]
        fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
        labs = [
            r["feature"]
            .replace("_skills", "")
            .replace("dashboard_and_storytelling", "storytelling")
            .replace("openness_to_experience", "openness")
            .replace("_", " ")
            for r in feats
        ]
        means = [f.groupby(target)[r["feature"]].mean() for r in feats]
        for i, m in enumerate(means):
            axes[0].plot([m.loc[0], m.loc[1]], [i, i], color="#AAB5BD", linewidth=2)
        axes[0].scatter([m.loc[0] for m in means], range(5), label="Low outcome", color=GOLD)
        axes[0].scatter([m.loc[1] for m in means], range(5), label="High outcome", color=TEAL)
        axes[0].set(yticks=range(5), yticklabels=labs, xlabel="Mean native score")
        axes[0].legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, 1.17), ncol=2)
        axes[1].barh(labs, [r["correlation"] for r in feats], color=BLUE)
        axes[1].set(xlim=(-0.1, 0.8), xlabel="Point-biserial correlation")
        save(fig, name)
    fig, ax = plt.subplots(figsize=(9, 3.3))
    methods = benchmark["summary"]["full_pool"]["methods"]
    labels = ["Direct greedy", "Surrogate greedy", "Portfolio"]
    left = np.zeros(3)
    for key, color in [("better", TEAL), ("equal", "#AAB5BD"), ("worse", RED)]:
        counts = np.array([methods[name][key] for name in ["greedy_F", "greedy_G", "portfolio"]])
        ax.barh(labels, counts, left=left, color=color, label=key.title())
        for i, count in enumerate(counts):
            if count:
                ax.text(left[i] + count / 2, i, str(count), ha="center", va="center", color="white")
        left += counts
    ax.set(xlabel="Nonempty full-pool scenarios compared with frequency advice")
    ax.legend(loc="upper center", bbox_to_anchor=(.5, 1.2), ncol=3)
    save(fig, "plans")
    fig, ax = plt.subplots(figsize=(8, 3.2))
    t = verify["route_timings"]
    ax.bar(list(t), [v["warm_p95_seconds"] * 1000 for v in t.values()], color=[TEAL, BLUE, GOLD])
    ax.set(ylabel="Warm p95 milliseconds", title="In-process TestClient measurements, 20 warm samples")
    save(fig, "latency")


class Note:
    def __init__(self):
        self.doc = Document()
        self.pages = []
        self.figure = 0
        sec = self.doc.sections[0]
        sec.page_width = Inches(8.27)
        sec.page_height = Inches(11.69)
        sec.top_margin = sec.bottom_margin = Inches(0.65)
        sec.left_margin = sec.right_margin = Inches(0.7)
        for name in ["Normal", "Body Text", "Caption", "Heading 1", "Heading 2", "Title", "Subtitle"]:
            style = self.doc.styles[name]
            style.font.name = "Times New Roman"
            style.font.size = Pt(12)
            style.paragraph_format.space_after = Pt(7)
            style.paragraph_format.line_spacing = 1
            style.font.color.rgb = RGBColor(0, 0, 0)
        self.doc.styles["Heading 1"].font.size = Pt(21)
        self.doc.styles["Heading 2"].font.size = Pt(14)
        self.doc.styles["Title"].font.size = Pt(34)
        self.doc.styles["Title"].font.color.rgb = RGBColor(0, 0, 0)
        for name in ["Title", "Subtitle"]:
            style = self.doc.styles[name]
            for border in style.element.xpath("./w:pPr/w:pBdr"):
                border.getparent().remove(border)
        foot = sec.footer.paragraphs[0]
        foot.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = foot.add_run("Yojak  |  SAS CU Hackathon  |  ")
        r.font.size = Pt(9)
        field = OxmlElement("w:fldSimple")
        field.set(qn("w:instr"), "PAGE")
        foot._p.append(field)
        self.doc.core_properties.title = "Yojak Workforce Intelligence Approach Note"
        self.doc.core_properties.author = "Yojak Team"

    def page(self, title, section):
        is_next = bool(self.pages)
        self.pages.append(title)
        p = self.doc.add_paragraph(section.upper())
        p.paragraph_format.page_break_before = is_next
        p.runs[0].font.size = Pt(10)
        p.runs[0].font.color.rgb = RGBColor.from_string("62717A")
        if is_next:
            self.doc.add_heading(title, level=1)
        else:
            self.doc.add_paragraph(title, style="Title")

    def p(self, text):
        self.doc.add_paragraph(text)

    def h(self, text):
        self.doc.add_heading(text, level=2)

    def table(self, headers, rows):
        table = self.doc.add_table(rows=1, cols=len(headers))
        table.style = "Light Shading Accent 1"
        for i, h in enumerate(headers):
            table.rows[0].cells[i].text = str(h)
        for row in rows:
            cells = table.add_row().cells
            for i, value in enumerate(row):
                cells[i].text = str(value)
        borders = OxmlElement("w:tblBorders")
        for edge in ["top", "left", "bottom", "right", "insideH", "insideV"]:
            border = OxmlElement(f"w:{edge}")
            for attr, value in {"val": "single", "sz": "4", "color": "D9D9D9"}.items():
                border.set(qn(f"w:{attr}"), value)
            borders.append(border)
        table._tbl.tblPr.append(borders)
        for row in table.rows:
            prop = row._tr.get_or_add_trPr()
            prop.append(OxmlElement("w:cantSplit"))
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.paragraph_format.space_after = Pt(4)
                    p.paragraph_format.space_before = Pt(3)
                    for run in p.runs:
                        run.font.size = Pt(10.5)
                        run.font.color.rgb = RGBColor(0, 0, 0)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(0)

    def image(self, name, caption, width=6.5):
        path = Path(name) if Path(name).is_absolute() else FIG / (name + ".png")
        self.doc.add_picture(str(path), width=Inches(width))
        self.figure += 1
        p = self.doc.add_paragraph(f"Figure {self.figure}. {caption}", style="Caption")
        for r in p.runs:
            r.font.size = Pt(10)
            r.italic = True


def build():
    m = load("manifest.json")
    s = load("salary_report.json")
    r = load("research_report.json")
    v = load("verification.json")
    benchmark = load("planner_benchmark.json")
    audit = load("calibration_audit.json")
    sensitivity = load("truncation_sensitivity.json")
    for report in (benchmark, audit, sensitivity):
        if report["source_version"] != m["source_version"]:
            raise ValueError("New evidence does not match the note source version")
    protected = ("manifest.json", "analytics.parquet", "salary_report.json", "band_model.joblib", "test_predictions.csv")
    if any(sensitivity.get("evidence_hashes", {}).get(name) != hashlib.sha256((PRIVATE / name).read_bytes()).hexdigest()
           for name in protected):
        raise ValueError("Token sensitivity evidence is stale; rebuild the experiment before the note")
    a = pd.read_parquet(PRIVATE / "analytics.parquet")
    c = pd.read_parquet(PRIVATE / "company.parquet")
    figures(a, c, r, s, m, v, benchmark, sensitivity)
    n = Note()
    q = m["audit"]["analytics"]
    test = s["test"]
    cal = s["calibration"]
    co = r["company"]
    ex = r["ordinal"]
    n.page("Yojak Workforce Intelligence", "Approach note")
    n.doc.add_paragraph("From observed skills to transparent career decisions", style="Subtitle")
    n.p("SAS CU Hackathon and Build for Bharat 2.0\nRound 2 technical approach note\nUpdated 8 October 2026")
    n.image(
        "architecture",
        "Implemented private SAS workflow. The legacy Naukri and ESCO workspace remains separate.",
    )
    n.h("Decision in brief")
    n.p(
        "Yojak helps a learner inspect role requirements, compare three-skill learning plans and understand uncertainty in advertised salary bands. Four supplied files provide market and cohort evidence, but they are not joined into a fictional career history. The system is working locally; external deployment of confidential outputs and SAS execution are not claimed."
    )
    n.table(
        ["Evidence", "Measured result"],
        [
            [
                "Salary band prediction",
                f"Test QWK {test['qwk']:.3f}; within one band {test['within_one_band']:.1%}",
            ],
            [
                "Uncertainty",
                f"Observed coverage {cal['test_coverage']:.1%}; mean set width {cal['mean_set_width']:.2f} of 6 bands",
            ],
            ["Delivery", "Next.js workspace, FastAPI routes, private artifacts, CUDA training"],
        ],
    )

    n.page("Executive synthesis and reading guide", "Overview")
    n.p(
        "Our central contribution is a reproducible path from imperfect posting data to a bounded decision. A model score is accompanied by source identity, evidence support, observable skill gaps and uncertainty. A learning plan is compared with a simple baseline under the same three-skill budget."
    )
    n.table(
        ["Section", "Pages", "Purpose"],
        [
            ["Problem and scope", "3 to 4", "Six questions and defensible business outcomes"],
            ["Approach and implementation", "5 to 6", "Architecture, boundaries and code ownership"],
            ["Data preparation", "7 to 10", "Quality decisions, partitions and measurement limits"],
            ["Analysis", "11 to 20", "Skill structure, GPU models, cohorts and optimization"],
            ["Evidence and implications", "21 to 24", "Runtime, product proof, conclusions and governance"],
            ["Reproduction and references", "25 to 26", "Commands, acceptance gates and reference synthesis"],
        ],
    )
    n.h("What changed after review")
    n.p(
        "We strengthen the mathematical explanation and artifact flow, add a freshly computed skill co-occurrence visualization, and expose vocabulary coverage in the application. The salary explanation now tests common slopes and switches to band-specific multinomial associations when that assumption fails. All figures are rebuilt from Yojak artifacts, not copied from another team's results."
    )
    n.h("What the results do not establish")
    n.p(
        "Observed skills are neither verified competence nor a hiring probability. Cohort associations are not causal returns to training. Native salary labels do not establish currency or pay period. No trial has measured placement improvement, time-to-hire reduction or employee outcomes."
    )

    n.page("Problem identification", "1 Problem definition")
    n.p(
        "A learner with a small set of skills faces three connected decisions: which role requirements overlap with those skills, which additions improve coverage, and how uncertain the compensation evidence is. Frequency lists alone cannot solve the second decision because a popular skill may add little to a profile that already covers many of the same postings."
    )
    n.table(
        ["Stakeholder", "Decision", "Evidence available"],
        [
            [
                "Students and professionals",
                "Choose a role and a small learning plan",
                "Posting skills, experience ranges and salary bands",
            ],
            [
                "Educators",
                "Review combinations of skills in curricula",
                "Within-family co-occurrence and transparent coverage",
            ],
            [
                "Employers",
                "Understand aggregate capability patterns",
                "Company-title aggregates and separate cohort research",
            ],
            [
                "Reviewers",
                "Assess analytical and engineering credibility",
                "Audits, grouped evaluation, code and actual local UI",
            ],
        ],
    )
    n.p(
        "We deliberately narrow the product to a Career Ladder workflow. This is a decision-support tool, not an automated applicant rejection system. It provides a way to inspect the evidence and compare alternatives without claiming a complete measurement of ability."
    )
    n.h("Why the supplied files matter")
    n.p(
        "Analytics Jobs supports requirement and band analysis. DataScience Jobs supports company-title compensation comparisons. JDS provides measured technical scores with recorded salary-hike classes. SDS provides personality measurements with an organizational success label. These are separate populations with different units of observation."
    )

    n.page("Six questions and success criteria", "1 Problem definition")
    n.table(
        ["Question", "Method", "Acceptance evidence"],
        [
            [
                "Q1 Role families and skill patterns",
                "Title rules and within-family associations",
                "Counts, manual-review sample and co-occurrence support",
            ],
            [
                "Q2 Salary bands",
                "Sparse baseline, CUDA AFT, calibrated sets",
                "Validation selection; untouched calibration; test error and width",
            ],
            [
                "Q3 Company and title compensation",
                "Mixed model and employer holdout",
                "Baseline comparison and unit caveat",
            ],
            [
                "Q4 Learning priorities",
                "Coverage optimization vs frequency",
                "Same skill budget; bounded exact-solver proof",
            ],
            [
                "Q5 Junior skills and outcomes",
                "Grouped nested logistic validation",
                "OOF AUC, bootstrap uncertainty, aggregate associations",
            ],
            [
                "Q6 Senior traits and outcomes",
                "Aggregate penalized logistic analysis",
                "Stability, uncertainty and no individual scoring",
            ],
        ],
    )
    n.h("Hypothesis rather than slogan")
    n.p(
        "The phrase 'Statistics pays twice' is a hypothesis to investigate. Market keywords and junior test scores measure different things in different samples. Even agreeing associations would not demonstrate a longitudinal or causal career ladder. We preserve this distinction in the interface and conclusions."
    )
    n.p(
        "Success means reproducible counts, group-disjoint partitions, training-only transformations, explicit salary units, source-labelled responses and a working local journey. Real-world benefit remains a future evaluation target, not a current metric."
    )

    n.page("End to end solution architecture", "2 Approach")
    n.image(
        "artifact_contract",
        "Artifact contracts connect reproducible offline work to private local inference.",
    )
    n.p(
        "The offline Python pipeline reads CSV and XLSX files, normalizes headers, audits missingness, parses ranges and records source hashes. Prepared Parquet files retain row keys, group IDs and split labels. Reports and a serialized band model form the contract between analysis and serving."
    )
    n.p(
        "FastAPI loads only the private SAS artifacts when explicitly enabled. The service checks preparation and source versions before inference. The frontend requests matching requirements, a three-skill plan and a salary-band set through three source-specific endpoints. It never substitutes legacy records when these endpoints are unavailable."
    )
    n.h("Reuse with a clear boundary")
    n.p(
        "The wider Yojak repository contains Naukri and ESCO linkage, Neo4j services, workforce views and a coverage optimizer. The SAS extension reuses the optimizer and UI infrastructure. It does not claim that the new source has completed ESCO linkage, geographic-tier verification or new GNN training. Public hosted-demo data is a separate authorized artifact path."
    )

    n.page("Technical implementation and ownership", "2 Approach")
    n.table(
        ["Component", "Implementation", "Responsibility"],
        [
            [
                "Data foundation",
                "ml_pipeline/sas/data.py",
                "Audits, row keys, grouping, partitions, review preservation",
            ],
            [
                "Salary prediction",
                "ml_pipeline/sas/model.py",
                "TF-IDF, CUDA AFT, soft targets, champion, calibration",
            ],
            [
                "Statistical explanation",
                "ml_pipeline/sas/explanation.py",
                "Clustered diagnostic and multinomial fallback",
            ],
            [
                "Cohort and company research",
                "ml_pipeline/sas/research.py",
                "Grouped validation, mixed effects and association rules",
            ],
            [
                "Private serving",
                "ml_pipeline/sas/service.py",
                "CPU inference, support, vocabulary and planning",
            ],
            ["HTTP contract", "app/api/routes/sas.py", "Validation and disabled-by-default routes"],
            [
                "User journey",
                "career-ladder/page.tsx",
                "Current-input results, loading, empty and error states",
            ],
            ["Reproduction", "run.py and verify.py", "Stages, artifact checks and route scenarios"],
        ],
    )
    n.p(
        "Python 3.11 runs the analysis and FastAPI service. Recorded model-library versions are NumPy "
        + s["versions"]["numpy"]
        + ", scikit-learn "
        + s["versions"]["scikit-learn"]
        + " and XGBoost "
        + s["versions"]["xgboost"]
        + ". The UI uses Next.js 14, React, TypeScript, Tailwind and React Query; OR-Tools supplies the bounded exact planning solver."
    )
    n.p(
        "The explanation, prediction and prescriptive planner are separate modules because they answer different questions. A good predictive model does not validate a causal coefficient, and a plan with high posting coverage does not establish a salary gain."
    )

    n.page("Data inventory and observation units", "3 Data exploration and preparation")
    n.table(
        ["Source", "Raw rows", "Primary unit", "Use"],
        [
            ["Analytics Jobs", 15841, "Posting", "Skills and banded pay"],
            ["DataScience Jobs", 1602, "Company-title record", "Reported salary aggregates"],
            ["JDS Skill Traits", 139, "Junior observation", "Five scores and hike class"],
            ["SDS Personality Traits", 161, "Senior observation", "Five traits and success class"],
        ],
    )
    n.p(
        "The combined row count is an inventory count, not one pooled statistical sample. A posting-count field in the company file represents aggregated volume; it must not be treated as independent workers or appended as additional Analytics rows. Repeated IDs in the trait files do not by themselves justify discarding observations with different measurements."
    )
    n.h("Provenance and confidentiality")
    n.p(
        f"Source version {m['source_version']} identifies this input snapshot. Full SHA-256 hashes, column names, missing counts and partition totals are recorded in manifest.json. The raw folder, private_sas, experiment outputs and supplied team references are excluded from Git. No confidential row export is included in the public Vercel snapshot."
    )
    n.p(
        "The supplied dictionary describes JDS scores on a 1 to 5 scale and SDS as normalized trait scores. The meaning and collection procedure of the binary success outcome remain limited. Neither file measures applicant selection or the effect of a training intervention."
    )

    n.page("Quality audit and corrective decisions", "3 Data exploration and preparation")
    n.image(
        "quality",
        "Counts and raw missing-field shares. Complete-only records are a sensitivity subset, not the primary sample.",
    )
    n.table(
        ["Issue", "Decision"],
        [
            [
                "1,001 exact duplicates excluding serial ID",
                "Keep one observation; retain multiplicity for sensitivity",
            ],
            [
                "12,907 distinct truncated skill lists",
                "Retain flag and raw text; conservative final-fragment handling",
            ],
            ["72 heuristic quality flags", "Do not call spam; compare inclusion and exclusion"],
            ["Missing descriptions and job type", "Retain records; description excluded from predictor text"],
            ["Conflicting observed bands", "Keep observed labels; group identical feature profiles"],
        ],
    )
    n.p(
        "Remote or part-time status alone is not an exclusion rule. The quality flag combines data-entry or typing language with promotional terms. It is a frozen heuristic, not verified ground truth. Missing and truncated content cannot be reconstructed by simply filling in the most common skill."
    )

    n.page("Feature derivation and measurement limits", "3 Data exploration and preparation")
    n.table(
        ["Derived feature", "Definition", "Caution"],
        [
            [
                "Experience",
                "Minimum, maximum, midpoint and width",
                "Range midpoint is not actual worker tenure",
            ],
            ["Salary band", "Six ordered observed labels", "No proven annual-lakh unit conversion"],
            [
                "Skills",
                "Conservative parsed tokens and limited aliases",
                "Absent token does not prove absent requirement",
            ],
            ["Role family", "Auditable designation rules", "Other remains large; manual review pending"],
            [
                "Group identity",
                "Connected exact and near feature signatures",
                "Depends on chosen grouping rules",
            ],
            [
                "Multiplicity",
                "Number of exact source duplicates",
                "Sensitivity weight only, not primary weighting",
            ],
        ],
    )
    n.p(
        f"There are {q['conflicting_feature_groups']:,} identical-feature groups with more than one salary label, involving {q['rows_in_conflicting_groups']:,} prepared records. Their in-sample majority-label agreement bound is {q['empirical_feature_agreement_bound']:.1%}. This is not a universal prediction ceiling and says nothing directly about the maximum QWK."
    )
    n.h("Why intervals are preserved")
    n.p(
        "The six native intervals are 0 to 3, 3 to 6, 6 to 10, 10 to 15, 15 to 25 and 25 to 50. AFT receives lower and upper bounds from each observed label. Contradictory bands are never averaged into a fabricated training interval. Midpoints appear only as explicitly qualified descriptive proxies in the cross-file check."
    )

    n.page("Partitions and leakage protection", "3 Data exploration and preparation")
    n.image(
        "training",
        "Realized Analytics partitions. Group hashing approximates the target 60/15/10/15 proportions.",
    )
    n.p(
        "Connected groups keep exact feature matches and normalized near matches in one partition. Serial IDs and target labels do not define split membership. Company evaluation holds out employers. Trait validation groups shared IDs and identical profiles, including transitive connections."
    )
    n.table(
        ["Protection", "Implementation evidence"],
        [
            ["Training-only preprocessing", "TF-IDF vocabulary and scaler fit only on training rows"],
            ["Calibration independence", "No hyperparameter tuning on calibration labels"],
            ["Group isolation", "Verification reports no cross-partition group overlap"],
            ["Manual review continuity", "Reruns preserve existing reviewer labels and notes"],
            ["Test history", "Exploratory source inspection preceded fitted-candidate evaluation"],
        ],
    )
    n.p(
        "These safeguards reduce leakage but do not create an independent external dataset. Related observations can remain beyond the chosen signatures, and source inspection occurred before model development. Test results describe this fitted candidate set on this snapshot, not prospective generalization to current hiring."
    )

    n.page("Market structure and role coverage", "4 Data analysis")
    n.image(
        "families",
        "Auditable title-rule families. Other is retained rather than forced into a named category.",
    )
    n.p(
        "The rule taxonomy supports a transparent first decision: inspect the population behind a role before interpreting its requirements. A named family is not a manually verified occupational label. A 100-record review file is prepared; independent labels and a confusion table remain necessary before claiming taxonomy accuracy."
    )
    n.p(
        "Reported prevalence uses distinct postings as the denominator. Family-level prevalence uses only that family. Quality-filtered and complete-only views answer different questions and must state their own support. Comparing figures from another team's cleaning policy without reconciling these denominators would be misleading."
    )
    n.h("Answer to Q1")
    n.p(
        "Title rules expose interpretable families but leave a substantial unassigned population. They are sufficient to demonstrate source-labelled exploration, not sufficient to claim comprehensive labor-market taxonomy coverage. Better manual labels should precede more complex title models."
    )

    n.page("Skill relationships with support", "4 Data analysis")
    n.image(
        "network",
        "Fresh Yojak co-occurrence view of 12 selected technical tokens. Edges require at least 20 joint postings; width is Jaccard overlap and node size reflects frequency.",
    )
    n.p(
        "For skills a and b, Jaccard similarity is joint posting count divided by the number of postings containing either skill. This compact graph communicates observed overlap without pretending that related skills are interchangeable. Its selected vocabulary is a visualization choice, not a complete ontology or a newly trained GNN."
    )
    n.p(
        "The analytical rule engine separately reports within-family support, confidence and lift. Confidence is P(b given a); lift divides that by P(b). Minimum support guards against spectacular-looking ratios from tiny counts. Included and excluded heuristic views are available for sensitivity analysis."
    )
    n.p(
        "Co-occurrence does not measure learning time, transferability or competence. Accordingly, the SAS planner still optimizes explicit observed-skill coverage; it does not silently award a missing skill because another token is nearby in this graph."
    )

    n.page("Salary bands and experience", "4 Data analysis")
    n.image(
        "experience",
        "Observed salary-band counts by required-experience midpoint. Interval labels are native and units remain unverified.",
    )
    n.p(
        "The distribution moves toward higher observed bands as required experience rises, but there is wide overlap. The heatmap is descriptive evidence of association, not an estimate of the effect of one additional year of work. Titles, employers, locations and selection into the posting sample may all matter."
    )
    n.h("Explanation before interpretation")
    n.p(
        "Our low-dimensional explanatory model uses experience midpoint, observed skill count, a statistics-token indicator and a modelling-token indicator. These proxies are intentionally inspectable. A keyword occurrence is not a professional skill assessment. The next page tests whether one common cumulative slope is defensible across the six bands."
    )
    n.p(
        "A continuous salary midpoint regression would add a stronger assumption than the data supply. The prediction pipeline instead preserves interval labels and reports band-level evaluation, while the company file retains its distinct aggregate-pay analysis."
    )

    n.page("Assumption testing changes the explanation", "4 Data analysis")
    n.image(
        "slopes",
        "Training-only cumulative-logit slopes by threshold. Differences motivate the multinomial fallback, not a common pay multiplier.",
    )
    d = ex["proportional_odds"]
    n.p(
        f"The group-clustered slope-equality Wald diagnostic gives chi-square {d['statistic']:.2f} with {d['df']} degrees of freedom (p = {d['p_value']:.2e}). Common slopes are rejected. The multinomial fallback converged and becomes the primary explanation; common-odds estimates remain diagnostic-only."
    )
    n.p(
        "The stacked design fits one binary cumulative logit per threshold. Its sandwich covariance clusters both repeated thresholds and related postings under the original group ID. Feature-level exploratory tests use false-discovery correction. This is an asymptotic slope-equality diagnostic, not the classical independent-observation Brant implementation."
    )
    n.p(
        "The fallback estimates band-specific log relative-probability ratios versus band 0, with clustered intervals. They are not common cumulative odds ratios or causal salary premiums. Omitted variables, noisy token features and dependence between groups remain limitations; independent SAS replication is pending."
    )

    n.page("CUDA model design and selection", "4 Data analysis")
    n.image(
        "models",
        "Validation results for the actual candidate set. Selection uses QWK with a greater-than-0.005 improvement requirement.",
    )
    n.p(
        "The input matrix combines training-fitted TF-IDF unigrams and bigrams of designation, skills and location with standardized experience and missingness flags. The vocabulary is capped at 12,000 features with minimum document frequency 3. Descriptions and salary text are excluded from predictor text."
    )
    n.p(
        "The baseline is L2 logistic regression with C=1. Four CUDA XGBoost AFT candidates combine depths 3 and 5 with normal-log-time scales 0.5 and 1.0. Histogram trees use eta 0.06, at most 400 rounds and 35-round early stopping. A separate soft-target classifier minimizes fractional cross-entropy over training-group band distributions; it is not the AFT experiment."
    )
    n.p(
        "AFT models log(Y) = f(x) + sigma Z, with Z standard normal. For an observed interval [L, U], its likelihood contribution is Phi((log(U) - f(x))/sigma) - Phi((log(L) - f(x))/sigma), where Phi is the normal cumulative distribution. At the first band's zero lower boundary, the second term takes its limiting value zero. Y is latent pay in unverified native units, not an observed exact salary."
    )
    n.p(
        f"The selected artifact is {s['champion']}. It was trained on {s['hardware']['nvidia_smi']}. CatBoost, transformer training and embedding clustering are not claimed. Single-profile inference uses CPU to avoid unnecessary CUDA context ownership in ASGI worker threads."
    )

    n.page("Test errors and calibrated uncertainty", "4 Data analysis")
    n.image("confusion", "Observed versus predicted labels for the 2,330 held-out posting records.", width=5.8)
    n.table(
        ["Metric", "Held-out result"],
        [
            [
                "Quadratic weighted kappa",
                f"{test['qwk']:.3f}; group-bootstrap 95% interval "
                f"{s['qwk_ci95_group_bootstrap'][0]:.3f} to {s['qwk_ci95_group_bootstrap'][1]:.3f}",
            ],
            ["Macro F1", f"{test['macro_f1']:.3f}"],
            ["Mean band error", f"{test['mean_band_error']:.3f}"],
            ["Within one band", f"{test['within_one_band']:.1%}"],
            ["90% target set coverage", f"{cal['test_coverage']:.1%}; group-bootstrap 95% interval "
             f"{audit['overall']['coverage_ci95'][0]:.1%} to {audit['overall']['coverage_ci95'][1]:.1%}"],
            ["Mean set width", f"{cal['mean_set_width']:.2f} of 6 labels"],
        ],
    )
    n.p(
        "The separate calibration set fixes a two-band residual radius, clipped at the first and last labels. The read-only audit uses 500 seeded group-bootstrap draws over 1,828 test groups, holding the model and radius fixed. These pointwise intervals omit training uncertainty and do not guarantee hypothetical user-profile coverage."
    )
    n.p(
        f"Software-family coverage is {audit['slices']['role_family']['Software']['coverage']:.1%}; complete-list coverage is {audit['slices']['skills_truncated']['False']['coverage']:.1%}. Data architect (5 rows) and flagged adverts (16 rows) are suppressed under the 30-row and 20-group support rule. Perfect observed coverage can yield a degenerate bootstrap interval, not certainty. Broad sets remain the main practical limitation."
    )

    n.page("Robustness and company evidence", "4 Data analysis")
    n.image(
        "company",
        "Distribution of company-title reported average salaries. Unweighted records; native units; boxplot outliers suppressed for readability, not removed from analysis.",
        width=5.6,
    )
    n.p(
        f"The company model fits log reported pay with title and experience fixed effects and a company random intercept. On {co['heldout_rows']} held-out company records, the title-median baseline MAE is {co['heldout_company_baseline_mae_native']:.3f}; the mixed-model MAE is {co['heldout_company_mae_native']:.3f}. The more complex model does not beat the baseline here."
    )
    n.p(
        f"The conditional company/residual variance ratio is {co['company_residual_icc']:.3f}, not a causal employer contribution. Posting-count-weighted fixed effects give MAE {co['weighted_fixed_effect_sensitivity_mae_native']:.3f}; weighting is a sensitivity estimand, not extra independent observations."
    )
    n.p(
        f"Matched-title cross-file Spearman correlation is {co['cross_file']['spearman']:.3f}: a plausibility check, not proof of units or independent validation. Salary-report multiplicity and complete-list sensitivities retain their separate estimands."
    )
    n.image("token_sensitivity", "Paired 95% group-bootstrap interval crosses zero. Models and partitions are fixed; this is post-hoc sensitivity, not model selection.")
    pair = sensitivity["paired_mean_band_error"]
    conservative, permissive = (sensitivity["variants"][name] for name in ("conservative", "permissive"))
    n.p(
        f"Two CUDA refits hold {sensitivity['rounds']} rounds and training settings fixed, fitting transforms on training rows only. Keeping trailing fragments changes test QWK from {conservative['test']['qwk']:.3f} to {permissive['test']['qwk']:.3f}. Mean band error changes by {pair['delta']:.3f} (95% interval {pair['ci95'][0]:.3f} to {pair['ci95'][1]:.3f}; {pair['repeats']:,} paired group draws). No clear benefit is established; the champion is unchanged. Calibration remains separate; uncertainty excludes retraining."
    )

    n.page("Junior technical skills and outcomes", "4 Data analysis")
    n.image(
        "jds",
        "Junior group means and raw correlations with recorded hike class. The two views are descriptive summaries of the same cohort, not independent validation.",
    )
    j = r["jds"]
    n.p(
        f"The junior cohort contains {j['n']} observations in {j['groups']} connected groups, with {j['class_counts'][1]} high and {j['class_counts'][0]} low outcomes. Nested grouped validation selects logistic regularization inside each outer training fold. Scaling is fitted within each fold. Grouped out-of-fold AUC is {j['oof_auc']:.3f}, with conditional group-bootstrap interval {j['oof_auc_ci95'][0]:.3f} to {j['oof_auc_ci95'][1]:.3f}."
    )
    n.p(
        f"The shallow-tree comparator has OOF AUC {j['tree_oof_auc']:.3f}. Storytelling and maths-statistics have the strongest raw correlations in this sample. Penalized multivariable odds ratios answer a different conditional question and may rank features differently. The 200-replicate bootstrap intervals are not full nested-refit uncertainty."
    )
    n.p(
        "Scores concentrate toward the top of the 1 to 5 scale. We do not interpret a one-point what-if change as a causal hike increase, and do not export an individual employee hike scorer. The practical implication is to investigate integrated quantitative and communication training through a prospective study."
    )

    n.page("Senior traits as aggregate research", "4 Data analysis")
    n.image(
        "sds",
        "Senior group means and raw correlations with the recorded success class. No individual suitability score is produced.",
    )
    senior = r["sds"]
    n.p(
        f"The senior cohort contains {senior['n']} observations in {senior['groups']} groups. Grouped OOF AUC is {senior['oof_auc']:.3f} with conditional bootstrap interval {senior['oof_auc_ci95'][0]:.3f} to {senior['oof_auc_ci95'][1]:.3f}; the shallow-tree comparator is {senior['tree_oof_auc']:.3f}. Openness and conscientiousness show strong raw associations, while neuroticism is near zero in the raw correlation."
    )
    n.p(
        "Such separation in a small, single-source sample warrants caution. Outcome definitions, selection into the cohort and whether observations were constructed are not established by the file. Adjusted coefficients can differ from marginal correlations without proving a behavioral mechanism."
    )
    n.h("Deployment boundary")
    n.p(
        "Personality traits are not inputs to matching, salary scenarios or the learning optimizer. The app exposes only aggregate research summaries. There is no route for individual hiring, promotion or retention decisions from SDS scores. No proxy for personality is inferred from GitHub activity."
    )

    n.page("Three skill planning and exact checks", "4 Data analysis")
    n.image(
        "plans",
        "Frozen grid of 144 hypothetical scenarios: eight role families, three experience levels, three profiles and two truncation views. Six pools are empty; counts above use the remaining 138.",
    )
    n.p(
        "For a posting j with observed skill set Rj, the planner counts coverage when |(S union A) intersect Rj| / |Rj| is at least 0.6, where S is the current profile and A contains at most three new skills. All observed skills and postings have equal weight in this SAS workflow."
    )
    n.p(
        "The service compares direct greedy coverage, a surrogate greedy method and frequency advice, retaining the best observed objective. CP-SAT is attempted only for pools of at most 500 postings and 200 candidate skills with a one-second limit. Optimality is claimed only when the solver proves it; otherwise the UI exposes the unproven status."
    )
    n.p(
        f"The portfolio beats frequency in {benchmark['summary']['full_pool']['methods']['portfolio']['better']} scenarios and ties in {benchmark['summary']['full_pool']['methods']['portfolio']['equal']}; direct greedy loses in {benchmark['summary']['full_pool']['methods']['greedy_F']['worse']}. Portfolio noninferiority is guaranteed because frequency is a candidate, not independent evidence of real-world superiority."
    )
    exact = benchmark["summary"]["bounded_pool"]["portfolio_exact_comparison"]
    n.p(
        f"Deterministic subsets retain at most 40 postings and their complete observed skill denominators. All {exact['proven_cases']} nonempty subsets receive exact proofs; the heuristic portfolio attains the optimum in {exact['attained_optimum']}, with a maximum gap of {exact['max_coverage_gap']} postings. Subset proofs do not certify full pools. Overlapping hypothetical scenarios are not independent people; complete-only differences are not causal truncation effects. Learning time and verified proficiency remain unmodeled."
    )

    n.page("Measured efficiency and quality gates", "5 Results and implementation evidence")
    n.image(
        "latency",
        "New local measurements from verify.py. These exclude network latency and browser rendering; they are not production service-level guarantees.",
    )
    n.table(
        ["Evidence", "Measurement or status"],
        [
            [
                "Recorded training stage",
                f"{s['total_seconds']:.2f} seconds; includes baseline and evaluation, not data preparation",
            ],
            ["GPU experiments", "Four AFT candidates and one soft-target run; two subsequent fixed-setting sensitivity refits"],
            [
                "Model artifact",
                f"{(PRIVATE / 'band_model.joblib').stat().st_size / 1024 / 1024:.2f} MiB serialized pipeline",
            ],
            ["Backend validation", "253 tests passed; 6 slow/live-Neo4j tests deselected (8 October 2026)"],
            ["Frontend validation", "TypeScript and lint passed; desktop/mobile evaluation tabs and unavailable state checked"],
            ["Source isolation", "Four dataset group checks and three route workflows passed"],
        ],
    )
    n.p(
        "The design spends CUDA work on offline fitting and serves small queries on CPU. Sparse text features avoid training a large language model on a modest tabular corpus. Timings are hardware- and cache-dependent; GPU peak memory and a controlled CPU-versus-GPU speedup experiment have not been recorded."
    )
    n.p(
        "The model report records library versions, hardware and code/source hashes. Reproducing it requires the matching prepared artifacts. Confidential outputs remain local, and API schema validation rejects invalid ranges and oversized inputs."
    )

    n.page("Working product and evidence coverage", "5 Results and implementation evidence")
    shot = PRIVATE / "reference_review/career-ladder-evidence.png"
    n.image(
        shot,
        "Actual local Career Ladder captured in Codex's in-app browser on 7 October 2026. This is application evidence, not a mockup or proof of SAS execution.",
    )
    n.p(
        "The displayed profile is Data analyst, two years of experience, with Python, SQL and Excel. In its 417-record pool, the coverage-based plan reaches 26 postings versus 18 for frequency advice, starting from one. The visible solver status says optimality is not proven for this case."
    )
    n.p(
        "The new evidence-coverage indicator reports how many normalized submitted skills occur in the selected pool and names those not observed. A missing vocabulary item is not evidence that the skill is irrelevant or that the person lacks ability. Empty input yields no percentage rather than a fabricated full-coverage value."
    )
    n.p(
        "Inputs changing hides stale results. The page handles loading, unavailable API, insufficient salary support and empty pools. Salary scenarios explicitly state that posting calibration does not provide a 90% guarantee for a user profile. No confidential content is silently substituted into the public demo."
    )

    n.page("Conclusions tied to the six questions", "5 Results and conclusions")
    n.table(
        ["Question", "Conclusion", "Remaining limitation"],
        [
            [
                "Q1",
                "Transparent families and supported co-occurrences can guide inspection",
                "Manual taxonomy accuracy unverified",
            ],
            [
                "Q2",
                f"Test QWK {test['qwk']:.3f}; common explanatory slopes rejected",
                "Wide sets; units and profile transfer unverified",
            ],
            [
                "Q3",
                "Mixed effects do not beat title-median holdout MAE",
                "Company averages are ecological measures",
            ],
            [
                "Q4",
                "Three-skill comparisons are operational and auditable",
                "Objective is observed coverage, not job success",
            ],
            [
                "Q5",
                "Quantitative and storytelling scores associate with hike class",
                "Small cohort; noncausal and conditional uncertainty",
            ],
            [
                "Q6",
                "Openness and conscientiousness associate with the recorded outcome",
                "No individual assessment or general population claim",
            ],
        ],
    )
    n.h("The defensible headline")
    n.p(
        "Yojak converts historical requirements into inspectable learning alternatives while keeping model uncertainty and data limitations visible. Its advantage is the combination of disciplined preparation, interval-aware prediction, baseline comparisons and a usable private workflow, not an assertion that the most complex model always wins."
    )
    n.p(
        "The 'Statistics pays twice' hypothesis remains unresolved as a causal or career-wide statement. Junior scores and market keywords are separate evidence streams. Stronger conclusions require clearer definitions, independent samples and prospective intervention or outcome data."
    )

    n.page("Stakeholder implications and safeguards", "6 Implications")
    n.image(
        "journey",
        "A learner-facing decision loop. Reviewing and practicing skills is a proposed action, not a measured employment outcome.",
    )
    n.table(
        ["Stakeholder", "Responsible action", "Future impact measure"],
        [
            [
                "Learner",
                "Inspect gaps and compare a small learning plan",
                "Completion and independently assessed skill gain",
            ],
            [
                "Educator",
                "Review recurring combinations and prerequisites",
                "Curriculum coverage with external assessments",
            ],
            [
                "Employer",
                "Use aggregate research to frame questions",
                "Consented prospective validation, not automatic screening",
            ],
            [
                "Project team",
                "Confirm units and manually review roles",
                "Review accuracy, external coverage and error slices",
            ],
        ],
    )
    n.p(
        "Institution name and personality are not SAS profile inputs, but omitting them does not prove fairness. Geography, skill access and source selection can still create disparities. Fairness evaluation needs representative consented data and clearly defined outcomes, none of which can be manufactured from these four files."
    )

    n.page("Reproduction and submission readiness", "Appendix A")
    n.table(
        ["Command or file", "Purpose"],
        [
            ["python -m ml_pipeline.sas.run --stage prepare", "Create audits and frozen partitions"],
            ["python -m ml_pipeline.sas.run --stage train", "Run CUDA portfolio and calibration"],
            [
                "python -m ml_pipeline.sas.run --stage analyze",
                "Refresh cohort, company and explanation reports",
            ],
            ["python -m ml_pipeline.sas.verify", "Check groups, routes and planner scenarios"],
            ["python -m ml_pipeline.sas.run --stage sensitivity", "Paired token-handling refits without replacing the champion"],
            ["python scripts/sas/build_note_v4.py", "Rebuild this note and figures from local artifacts"],
            ["scripts/sas/validate.sas", "SAS handoff program; not executed"],
        ],
    )
    n.p(
        "Run analysis commands from the repository virtual environment. Document generation uses the bundled artifact Python runtime. Enable the local API with YOJAK_SAS_LOCAL=1 and bind it to loopback; keep that flag disabled on a public service. Open /career-ladder on the local Next.js frontend."
    )
    n.h("SAS handoff status")
    n.p(
        "A private CSV bundle and shared partition manifests are ready. Approved SAS Studio execution, coefficient/prediction reconciliation and four Visual Analytics pages remain pending access. Compare identical observations, encodings, weights and estimators with documented tolerances; differently penalized estimators need not agree to two decimals."
    )
    n.h("Before submission")
    n.p(
        "Complete independent role review; obtain salary-unit clarification; execute approved SAS checks; verify document pagination and figures; rehearse the live profile journey. Defer optional CatBoost, embeddings and Model Studio additions before weakening auditability. No current artifact demonstrates external or prospective validation."
    )

    n.page("Reference synthesis and evidence register", "Appendix B")
    n.table(
        ["Provided reference", "Useful idea adopted", "Boundary retained"],
        [
            [
                "DeezNerdz, La Casa De Rozgaar, pp 2 to 6",
                "Explicit architecture layers, model equations and benchmark tables",
                "No imported odds multipliers, latency or causal claims",
            ],
            [
                "Optiprime, ProofOfSkill, pp 5 to 20",
                "Quality issue log, distributions, paired group plots and error matrices",
                "No supply shortage from normalized unrelated scales",
            ],
            [
                "Syntax Squad, Talent Bridge, pp 13 to 17",
                "Skill relationship diagrams and vocabulary-coverage visibility",
                "No similarity-as-competence or personality readiness scorer",
            ],
        ],
    )
    n.p(
        "These team-authored notes were supplied as methodological and presentation references. Their results use different cleaning, splitting and modeling choices, so they are not benchmark comparators for Yojak. Our diagrams are newly authored; the skill network is recomputed from our prepared postings. No personal identifiers or original figures are reproduced."
    )
    n.h("Primary evidence")
    n.p(
        "manifest.json records provenance; salary_report.json and test_predictions.csv supply prediction evidence; research_report.json supplies statistics. verification.json covers routes; planner_benchmark.json adds scenario and exact-gap evidence; calibration_audit.json adds subgroup uncertainty; truncation_sensitivity.json records paired refits and protected artifact hashes. Code, figure data and evidence hashes define the reproducible private implementation."
    )
    n.h("Method references")
    n.p(
        "XGBoost AFT tutorial: xgboost.readthedocs.io/en/latest/tutorials/aft_survival_analysis.html. Statsmodels cluster covariance implementation: github.com/statsmodels/statsmodels/blob/main/statsmodels/base/covtype.py. Split conformal background: mapie.readthedocs.io/en/stable/content/conformal-prediction/split-cross-conformal/. The implemented band residual method is specified on page 16; it is not the legacy continuous-INR calibration."
    )
    assert len(n.pages) == 26
    backup = OUT / "previous" / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup.mkdir(parents=True, exist_ok=True)
    for suffix in ["docx", "pdf"]:
        path = OUT / f"Yojak_Approach_Note.{suffix}"
        if path.exists():
            shutil.copy2(path, backup / path.name)
    target = OUT / "Yojak_Approach_Note.docx"
    n.doc.save(target)
    evidence = {
        name: hashlib.sha256((PRIVATE / name).read_bytes()).hexdigest()
        for name in ["manifest.json", "salary_report.json", "research_report.json", "verification.json",
                     "planner_benchmark.json", "calibration_audit.json", "truncation_sensitivity.json"]
    }
    (OUT / "note_build_manifest.json").write_text(
        json.dumps(
            {
                "intended_pages": 26,
                "sections": n.pages,
                "figures": n.figure,
                "source_version": m["source_version"],
                "evidence_hashes": evidence,
                "docx_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            },
            indent=2,
        )
    )
    print(target)


if __name__ == "__main__":
    build()
