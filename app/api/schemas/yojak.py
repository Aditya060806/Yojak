# app/api/schemas/yojak.py

"""
Schemas for the Yojak stakeholder endpoints.

Honesty rules enforced here, not just in the UI:
  * SalaryRange has no single-number form: p10, p50, p90 and n_support are all required.
  * Candidate.synthetic is required, so no candidate can be returned without saying
    whether it is synthetic.
  * Every recommendation carries a `why` object.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Language = Literal["en", "hi", "pa", "hi-Latn"]


class SkillRef(BaseModel):
    uri: str
    label: str


class ExtractedSkill(SkillRef):
    score: float
    method: str
    source_text: str


class ExtractRequest(BaseModel):
    text: str = Field(..., max_length=50_000)
    language: Language | None = None


class ExtractResponse(BaseModel):
    language: str
    skills: list[ExtractedSkill]
    unlinked_phrases: list[str]
    threshold: float
    threshold_status: str


class SalaryRange(BaseModel):
    p10: float = Field(..., description="10th percentile, annual INR (posted salary midpoint)")
    p50: float = Field(..., description="median, annual INR")
    p90: float = Field(..., description="90th percentile, annual INR")
    n_support: int = Field(..., description="disclosed postings in the same ISCO unit group and tier")
    sufficient: bool = Field(..., description="n_support >= the minimum for showing a range")


class ProfileRequest(BaseModel):
    skills: list[str] = Field(default_factory=list, description="ESCO skill URIs")
    text: str | None = Field(None, max_length=20_000, description="free text in English/Hindi/Punjabi/romanised Hindi")
    language: Language | None = None
    tiers: list[int] | None = Field(None, description="city tiers to include (1, 2, 3)")
    states: list[str] | None = None
    exp_bands: list[str] | None = None
    limit: int = Field(20, ge=1, le=100)


class PathStep(BaseModel):
    kind: str
    label: str
    uri: str | None = None


class Why(BaseModel):
    matched_skills: list[SkillRef] = Field(default_factory=list)
    missing_skills: list[SkillRef] = Field(default_factory=list)
    contributions: list[dict[str, Any]] = Field(default_factory=list, description="score drop if each skill is removed")
    paths: list[list[PathStep]] = Field(default_factory=list, description="graph paths behind the match")
    model: str | None = None
    notes: list[str] = Field(default_factory=list)


class JobMatch(BaseModel):
    job_id: str
    title: str
    company: str
    city: str | None
    state: str | None
    tier: int | None
    exp_band: str | None
    occupation_uri: str | None
    occupation_label: str | None
    nco_family: str | None
    score: float
    fit: float = Field(..., description="IDF-weighted share of the posting's skills you have")
    salary: SalaryRange
    why: Why


class RoleMatch(BaseModel):
    occupation_uri: str
    occupation_label: str
    nco_family: str | None
    postings: int
    score: float
    salary: SalaryRange | None
    top_missing: list[SkillRef]
    why: Why


class StudentMatchResponse(BaseModel):
    skills: list[SkillRef]
    extraction: ExtractResponse | None
    roles: list[RoleMatch]
    jobs: list[JobMatch]
    pool_size: int
    model: dict[str, Any]
    salary_caveat: dict[str, Any]


class PlanRequest(ProfileRequest):
    target_occupation: str | None = Field(None, description="ESCO occupation URI to aim for")
    target_isco2: str | None = Field(None, description="or an ISCO sub-major group, e.g. '25'")
    k: int = Field(3, ge=1, le=8)
    tau: float = Field(0.6, ge=0.3, le=0.9)
    value: Literal["count", "salary"] = "count"
    budget: float | None = Field(None, ge=0.5, le=10, description="effort budget (effort-aware plan)")
    effort_overrides: dict[str, float] = Field(default_factory=dict, description="skill URI -> effort weight")


class PlanStep(BaseModel):
    skill: SkillRef
    jobs_unlocked: int
    cumulative_eligible: int
    effort: dict[str, Any]
    salary_of_unlocked: SalaryRange | None
    salary_shift_p50: dict[str, float] | None = Field(None, description="P50 of newly eligible minus currently eligible, as a range")
    why: Why


class Plan(BaseModel):
    method: str
    optimal: bool | None
    steps: list[PlanStep]
    eligible_before: int
    eligible_after: int
    value_after: float


class StudentPlanResponse(BaseModel):
    pool: dict[str, Any]
    skills: list[SkillRef]
    extraction: ExtractResponse | None
    optimal_plan: Plan
    frequency_plan: Plan
    effort_plan: Plan | None
    notes: list[str]


class Candidate(BaseModel):
    candidate_id: str
    synthetic: bool = Field(..., description="True for the generated demo pool; False for uploaded resumes")
    source: str
    occupation_label: str | None = None
    city: str | None = None
    tier: int | None = None
    exp_band: str | None = None
    score: float
    coverage: float = Field(..., description="IDF-weighted share of the JD's skills the candidate has")
    why: Why


class RecruiterResponse(BaseModel):
    jd_skills: list[SkillRef]
    extraction: ExtractResponse | None
    candidates: list[Candidate]
    pool: dict[str, int]
    notes: list[str]


class CoverageItem(BaseModel):
    skill: SkillRef
    demand_postings: int
    demand_share: float


class InstitutionResponse(BaseModel):
    syllabus_skills: list[SkillRef]
    extraction: ExtractResponse | None
    scope: dict[str, Any]
    coverage: float = Field(..., description="demand-weighted share of the top in-demand skills the syllabus covers")
    covered: list[CoverageItem]
    missing_high_demand: list[CoverageItem]
    low_current_demand: list[CoverageItem]
    notes: list[str]


class SalaryEstimateResponse(BaseModel):
    salary: SalaryRange
    basis: dict[str, Any]
    caveat: dict[str, Any]
