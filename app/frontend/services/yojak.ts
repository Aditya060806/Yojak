import api from '@/lib/api';

// ---------- shared ----------
export interface SkillRef {
    uri: string;
    label: string;
}

export interface ExtractedSkill extends SkillRef {
    score: number;
    method: string;
    source_text: string;
}

export interface Extraction {
    language: string;
    skills: ExtractedSkill[];
    unlinked_phrases: string[];
    threshold: number;
    threshold_status: string;
}

/** A salary is always a range; there is deliberately no single-number type. */
export interface SalaryRange {
    p10: number;
    p50: number;
    p90: number;
    n_support: number;
    sufficient: boolean;
}

export interface PathStep {
    kind: string;
    label: string;
    uri?: string | null;
}

export interface Why {
    matched_skills: SkillRef[];
    missing_skills: SkillRef[];
    contributions: { skill: SkillRef; score_drop: number }[];
    paths: PathStep[][];
    model?: string | null;
    notes: string[];
}

export interface Filters {
    tiers?: number[];
    states?: string[];
    exp_bands?: string[];
}

export interface Profile extends Filters {
    skills: string[];
    text?: string;
    language?: string;
    limit?: number;
}

// ---------- student ----------
export interface JobMatch {
    job_id: string;
    title: string;
    company: string;
    city: string | null;
    state: string | null;
    tier: number | null;
    exp_band: string | null;
    occupation_uri: string | null;
    occupation_label: string | null;
    nco_family: string | null;
    score: number;
    fit: number;
    salary: SalaryRange;
    why: Why;
}

export interface RoleMatch {
    occupation_uri: string;
    occupation_label: string;
    nco_family: string | null;
    postings: number;
    score: number;
    salary: SalaryRange | null;
    top_missing: SkillRef[];
    why: Why;
}

export interface StudentMatch {
    skills: SkillRef[];
    extraction: Extraction | null;
    roles: RoleMatch[];
    jobs: JobMatch[];
    pool_size: number;
    model: { benchmark_winner: string | null; served: string; served_name: string; note: string | null };
    salary_caveat: Record<string, unknown>;
}

export interface PlanStep {
    skill: SkillRef;
    jobs_unlocked: number;
    cumulative_eligible: number;
    effort: { effort: number; reuse_level?: string; proximity_factor?: number; note?: string };
    salary_of_unlocked: SalaryRange | null;
    salary_shift_p50: { p10: number; p50: number; p90: number } | null;
    why: Why;
}

export interface Plan {
    method: string;
    optimal: boolean | null;
    steps: PlanStep[];
    eligible_before: number;
    eligible_after: number;
    value_after: number;
}

export interface PlanRequest extends Profile {
    target_occupation?: string | null;
    target_isco2?: string | null;
    k: number;
    tau: number;
    value: 'count' | 'salary';
    budget?: number | null;
    effort_overrides?: Record<string, number>;
}

export interface StudentPlan {
    pool: { postings: number; occupation_uri: string | null; isco2: string | null; value: string };
    skills: SkillRef[];
    extraction: Extraction | null;
    optimal_plan: Plan;
    frequency_plan: Plan;
    effort_plan: Plan | null;
    notes: string[];
}

// ---------- recruiter ----------
export interface Candidate {
    candidate_id: string;
    synthetic: boolean;
    source: string;
    occupation_label: string | null;
    city: string | null;
    tier: number | null;
    exp_band: string | null;
    score: number;
    coverage: number;
    why: Why;
}

export interface RecruiterResult {
    jd_skills: SkillRef[];
    extraction: Extraction | null;
    candidates: Candidate[];
    pool: { synthetic: number; uploaded: number };
    notes: string[];
}

// ---------- institution ----------
export interface CoverageItem {
    skill: SkillRef;
    demand_postings: number;
    demand_share: number;
}

export interface InstitutionResult {
    syllabus_skills: SkillRef[];
    extraction: Extraction | null;
    scope: { postings: number; top_n: number } & Record<string, unknown>;
    coverage: number;
    covered: CoverageItem[];
    missing_high_demand: CoverageItem[];
    low_current_demand: CoverageItem[];
    notes: string[];
}

// ---------- workforce ----------
export interface StateRow {
    state: string;
    postings: number;
    share?: number;
    demand_share?: number;
    demand_share_of_field?: number;
    graduate_share: number | null;
    shortage_index: number | null;
    youth_ur_pct: number | null;
    outturn_total: number | null;
    postings_per_1000_graduates?: number | null;
    salary_p50_median?: number | null;
}

export interface TierRow {
    tier_label: string;
    postings: number;
    p10_median: number;
    p50_median: number;
    p90_median: number;
    disclosed_share: number;
}

export interface Demand {
    field: string | null;
    total_postings: number;
    by_state: StateRow[];
    tiers: TierRow[];
    top_skills_by_state: Record<string, { uri: string; label: string; postings: number }[]>;
    top_skills_by_tier: Record<string, { uri: string; label: string; postings: number }[]>;
    source: string;
}

export interface Shortage {
    field: string | null;
    formula: string;
    proxy: boolean;
    states: StateRow[];
    caveats: string[];
}

// ---------- graph ----------
export interface ConstellationNode {
    id: string;
    label: string;
    kind: 'skill' | 'occupation';
    uri: string;
    postings: number;
}

export interface Constellation {
    nodes: ConstellationNode[];
    edges: { source: string; target: string; weight: number; postings: number; kind: string }[];
    source: string;
    postings: number;
}

const form = (entries: Record<string, string | Blob | undefined | null>) => {
    const f = new FormData();
    for (const [k, v] of Object.entries(entries)) if (v !== undefined && v !== null) f.append(k, v);
    return f;
};

export const yojak = {
    extractText: async (text: string, language?: string) =>
        (await api.post<Extraction>('/extract/skills', { text, language })).data,
    extractFile: async (file: File) =>
        (await api.post<Extraction>('/extract/file', form({ file }), { headers: { 'Content-Type': 'multipart/form-data' } })).data,

    studentMatch: async (p: Profile) => (await api.post<StudentMatch>('/student/match', p)).data,
    studentPlan: async (p: PlanRequest) => (await api.post<StudentPlan>('/student/plan', p)).data,

    recruiterRank: async (jdText: string, jdSkills: string[], resumes: File[], includeSynthetic: boolean) => {
        const f = form({ jd_text: jdText, jd_skills: JSON.stringify(jdSkills), include_synthetic: String(includeSynthetic) });
        resumes.forEach((r) => f.append('resumes', r));
        return (await api.post<RecruiterResult>('/recruiter/rank', f, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
    },

    institutionCoverage: async (args: {
        text: string;
        file?: File | null;
        skills?: string[];
        occupations?: string[];
        isco2?: string | null;
        field?: string | null;
        tiers?: number[];
        states?: string[];
    }) => {
        const f = form({
            syllabus_text: args.text,
            syllabus: args.file ?? undefined,
            skills: JSON.stringify(args.skills ?? []),
            occupations: JSON.stringify(args.occupations ?? []),
            isco2: args.isco2 ?? undefined,
            field: args.field ?? undefined,
            tiers: JSON.stringify(args.tiers ?? []),
            states: JSON.stringify(args.states ?? []),
        });
        return (await api.post<InstitutionResult>('/institution/coverage', f, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
    },

    fields: async () => (await api.get<{ fields: { field: string; postings: number }[]; note: string }>('/workforce/fields')).data,
    demand: async (field?: string | null) => (await api.get<Demand>('/workforce/demand', { params: { field: field || undefined } })).data,
    shortage: async (field?: string | null) => (await api.get<Shortage>('/workforce/shortage', { params: { field: field || undefined } })).data,

    constellation: async () => (await api.get<Constellation>('/graph/constellation')).data,
    report: async <T = Record<string, unknown>>(name: string) => (await api.get<T>(`/reports/${name}`)).data,
};
