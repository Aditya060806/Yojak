import { useQuery } from '@tanstack/react-query';
import { ApiError } from '@/lib/api';
import { yojak } from '@/services/yojak';

/**
 * A generated report from reports/*.json. Resolves to `null` when the report has not been
 * generated yet (404), so pages can show "pending" instead of an error or a made-up number.
 */
export function useReport<T = Record<string, unknown>>(name: string, enabled = true) {
    return useQuery<T | null>({
        queryKey: ['report', name],
        queryFn: async () => {
            try {
                return await yojak.report<T>(name);
            } catch (e) {
                if (e instanceof ApiError && e.status === 404) return null;
                throw e;
            }
        },
        enabled,
        staleTime: 10 * 60 * 1000,
    });
}

// Minimal shapes of the reports the UI reads. Anything else is shown raw on /evidence.
export interface DataQualityReport {
    dataset: { raw_rows: number; name: string; licence: string };
    final_jobs: number;
    geography: { distinct_cities: number; distinct_states: number; city_resolution_rate_excl_remote: number;
        jobs_by_primary_tier: Record<string, number> };
    skill_linking: { mention_coverage: number; distinct_esco_skills_used: number; threshold: number; threshold_status: string };
    title_linking: { job_coverage: number; distinct_occupations_used: number };
    salary: { disclosed_share: number };
    temporal: { inferred_scrape_date: string; forecasting_supported: boolean };
    gold_evaluation?: { skills?: { status: string; precision_mention_weighted?: number } };
}

interface TaskMetrics { 'recall@10': number; 'ndcg@10': number; mrr: number; 'ndcg@10_ci95'?: number[]; 'recall@10_ci95'?: number[] }

export interface ModelComparisonReport {
    models: Record<string, { name: string; mean: { t1?: TaskMetrics; t2?: TaskMetrics; t3?: TaskMetrics;
        latency?: { jobs_for_profile?: { p50_ms: number; p95_ms: number } }; memory?: { rss_mb: number } } }>;
    comparison: { winner: string; winner_name: string; rule: string; hgt_beats_best_baseline_on_t3?: boolean;
        hgt_vs_best_baseline?: { baseline: string; t3?: { mean_diff: number; ci95: number[] } } };
    quick_mode?: boolean;
}

export interface UpskillingMethod { mean_F: number; mean_gap_pct: number; p95_gap_pct: number; share_optimal: number;
    runtime_ms_p50: number; runtime_ms_p95: number; mean_extra_jobs_vs_frequency?: number; share_better_than_frequency?: number }

export interface UpskillingReport {
    grid: Record<string, { instances: number; mean_optimum: number; ilp_proven_optimal_share: number } & Record<string, UpskillingMethod | number>>;
}

export interface SalaryReport {
    test: { n: number; mae_inr: number; mdape_pct: number; coverage_raw: number; coverage_cqr: number; median_width_inr_cqr: number };
    baseline: { mae_inr: number; mdape_pct: number };
    selection_bias: { disclosed_share: number; propensity: { auc: number; interpretation: string } };
    display_rule: { min_support: number };
}

export interface ImpactReport {
    users: number;
    eligible_before_median: number;
    eligible_after_frequency_median: number;
    eligible_after_optimal_median: number;
    extra_postings_vs_frequency: { mean: number; median: number; iqr: number[] };
    share_users_with_more_postings: number;
    assumptions: Record<string, string | number | boolean>;
}
