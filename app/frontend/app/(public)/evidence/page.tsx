'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'motion/react';
import { CaretDown, CheckCircle, CircleDashed } from '@phosphor-icons/react';
import { yojak } from '@/services/yojak';
import {
    useReport, type ModelComparisonReport, type SalaryReport, type UpskillingMethod, type UpskillingReport,
} from '@/hooks/use-report';
import { Markdown } from '@/components/yojak/markdown';
import { ErrorState, PageIntro, Panel, Pending, ProxyNote, Section, SkeletonBlock } from '@/components/yojak/bits';
import { Segmented } from '@/components/yojak/filters';
import { inr, num, pct } from '@/lib/format';
import { cn } from '@/lib/utils';

const ease = [0.16, 1, 0.3, 1] as const;
const DESCRIPTIONS: Record<string, string> = {
    data_quality: 'Cleaning, geography, ESCO linking, NCO mapping, dates',
    model_comparison: 'Six recommenders on one leakage-free split',
    upskilling_eval: 'Greedy, frequency and exact ILP plans',
    salary_eval: 'Quantile model, conformal coverage, disclosure bias',
    workforce_summary: 'Demand by skill family, shortage proxy',
    multilingual_eval: 'Hindi, Punjabi and romanised-Hindi linking',
    impact: 'Tier-2/3 fresher impact estimate',
};

export default function EvidencePage() {
    const index = useQuery({ queryKey: ['report-index'], queryFn: yojak.reportIndex });
    return (
        <div className="container">
            <PageIntro
                title="Evidence"
                lead="Every number Yojak shows is produced by a script in the repository and saved to reports/. This page reads those files directly. Anything not yet measured is marked pending, never estimated."
            />
            {index.error && <ErrorState error={index.error} onRetry={() => index.refetch()} />}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {(index.data?.json ?? Array.from({ length: 7 }, (_, i) => ({ name: `loading-${i}`, available: false }))).map((r) => (
                    <ReportCard key={r.name} name={r.name} available={r.available} loading={!index.data} />
                ))}
            </div>
            <div className="space-y-16 pt-14">
                <ModelsSection />
                <UpskillingSection />
                <SalarySection />
                <EvaluationDoc />
            </div>
        </div>
    );
}

function ReportCard({ name, available, loading }: { name: string; available: boolean; loading: boolean }) {
    const [open, setOpen] = useState(false);
    const rep = useReport<{ provenance?: { generated_at_utc?: string; script?: string; git?: { commit?: string } } }>(name);
    if (loading) return <SkeletonBlock className="h-[108px] rounded-xl" />;
    const p = rep.data?.provenance;
    return (
        <div className="rounded-xl border bg-card">
            <button type="button" onClick={() => available && setOpen((o) => !o)} className="w-full space-y-2 p-4 text-left" aria-expanded={open}>
                <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 font-mono text-[13px]">
                        {available ? <CheckCircle size={16} weight="fill" className="text-primary" /> : <CircleDashed size={16} className="text-muted-foreground" />}
                        {name}.json
                    </span>
                    {available && <CaretDown size={14} className={cn('text-muted-foreground transition-transform', open && 'rotate-180')} />}
                </div>
                <p className="text-xs text-muted-foreground">{DESCRIPTIONS[name] ?? ''}</p>
                <p className="text-[11px] text-muted-foreground">
                    {available && p ? <>{p.generated_at_utc?.replace('T', ' ').replace('+00:00', ' UTC')} · {p.git?.commit?.slice(0, 7)}</> : <Pending what="not generated yet" />}
                </p>
            </button>
            {open && rep.data && (
                <pre className="max-h-80 overflow-auto border-t bg-muted/40 p-3 font-mono text-[11px] leading-relaxed">
                    {JSON.stringify(rep.data, null, 2)}
                </pre>
            )}
        </div>
    );
}

// ---------- link prediction ----------

type Task = 't1' | 't2' | 't3';
const TASK_LABEL: Record<Task, string> = { t1: 'T1 · complete a job’s skills', t2: 'T2 · recover occupation skills', t3: 'T3 · candidate → unseen jobs' };

function ModelsSection() {
    const { data, isLoading } = useReport<ModelComparisonReport>('model_comparison');
    const [task, setTask] = useState<Task>('t3');
    return (
        <Section
            title="Link prediction benchmark"
            description="NDCG@10 with 95% bootstrap intervals. Same split, same queries, same metric code for every model. The winner on T3 is the model the app serves."
            action={<Segmented<Task> label="Task" value={task} onChange={setTask}
                                     options={[{ value: 't1', label: 'T1' }, { value: 't2', label: 'T2' }, { value: 't3', label: 'T3' }]} />}
        >
            {isLoading ? <SkeletonBlock className="h-64 rounded-xl" /> : !data ? (
                <Panel><Pending what="python -m ml_pipeline.graph.evaluate has not been run" /></Panel>
            ) : (
                <Panel className="space-y-5">
                    {data.quick_mode && <ProxyNote title="Quick mode">This report used subsampled queries: a smoke test, not the final benchmark.</ProxyNote>}
                    <p className="text-sm font-medium">{TASK_LABEL[task]}</p>
                    <CiChart data={data} task={task} />
                    <div className="grid gap-3 text-sm sm:grid-cols-2">
                        <p><span className="text-muted-foreground">Shipped: </span><b>{data.comparison.winner_name}</b></p>
                        {data.comparison.hgt_vs_best_baseline?.t3 && (
                            <p>
                                <span className="text-muted-foreground">HGT − {data.comparison.hgt_vs_best_baseline.baseline} on T3: </span>
                                <span className="tabular">{data.comparison.hgt_vs_best_baseline.t3.mean_diff.toFixed(4)}</span>{' '}
                                <span className="tabular text-muted-foreground">[{data.comparison.hgt_vs_best_baseline.t3.ci95.map((v) => v.toFixed(4)).join(', ')}]</span>
                            </p>
                        )}
                    </div>
                    <LatencyTable data={data} />
                </Panel>
            )}
        </Section>
    );
}

function CiChart({ data, task }: { data: ModelComparisonReport; task: Task }) {
    const rows = Object.entries(data.models)
        .map(([key, m]) => ({ key, name: m.name, t: m.mean[task] }))
        .filter((r) => r.t)
        .sort((a, b) => (b.t!['ndcg@10'] - a.t!['ndcg@10']));
    if (!rows.length) return <p className="text-sm text-muted-foreground">No model reports this task.</p>;
    const max = Math.max(...rows.map((r) => r.t!['ndcg@10_ci95']?.[1] ?? r.t!['ndcg@10'])) * 1.08;
    return (
        <ul className="space-y-2.5">
            {rows.map((r, i) => {
                const v = r.t!['ndcg@10'];
                const [lo, hi] = r.t!['ndcg@10_ci95'] ?? [v, v];
                const winner = r.key === data.comparison.winner;
                return (
                    <li key={r.key} className="grid grid-cols-[minmax(0,180px)_1fr_64px] items-center gap-3 text-sm">
                        <span className={cn('truncate', winner && 'font-semibold')}>{r.name}</span>
                        <span className="relative h-6">
                            <span className="absolute inset-y-[11px] left-0 right-0 rounded bg-muted" />
                            <motion.span
                                className={cn('absolute inset-y-[11px] left-0 rounded', winner ? 'bg-primary' : 'bg-viz-3')}
                                initial={{ width: 0 }}
                                animate={{ width: `${(v / max) * 100}%` }}
                                transition={{ duration: 0.7, ease, delay: i * 0.05 }}
                            />
                            <span className="absolute top-[6px] h-3 border-x border-foreground/60"
                                  style={{ left: `${(lo / max) * 100}%`, width: `${Math.max(0.4, ((hi - lo) / max) * 100)}%` }} />
                        </span>
                        <span className="tabular text-right">{v.toFixed(3)}</span>
                    </li>
                );
            })}
        </ul>
    );
}

function LatencyTable({ data }: { data: ModelComparisonReport }) {
    return (
        <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
                <thead className="bg-muted/50 text-xs text-muted-foreground">
                    <tr>
                        <th className="px-3 py-2 text-left font-medium">Model</th>
                        <th className="px-3 py-2 text-right font-medium">T3 Recall@10</th>
                        <th className="px-3 py-2 text-right font-medium">T3 MRR</th>
                        <th className="px-3 py-2 text-right font-medium">p50 ms</th>
                        <th className="px-3 py-2 text-right font-medium">p95 ms</th>
                        <th className="px-3 py-2 text-right font-medium">Memory MB</th>
                    </tr>
                </thead>
                <tbody className="divide-y">
                    {Object.entries(data.models).map(([k, m]) => (
                        <tr key={k}>
                            <td className="px-3 py-2">{m.name}</td>
                            <td className="tabular px-3 py-2 text-right">{m.mean.t3 ? m.mean.t3['recall@10'].toFixed(3) : '–'}</td>
                            <td className="tabular px-3 py-2 text-right">{m.mean.t3 ? m.mean.t3.mrr.toFixed(3) : '–'}</td>
                            <td className="tabular px-3 py-2 text-right">{num(m.mean.latency?.jobs_for_profile?.p50_ms, 1)}</td>
                            <td className="tabular px-3 py-2 text-right">{num(m.mean.latency?.jobs_for_profile?.p95_ms, 1)}</td>
                            <td className="tabular px-3 py-2 text-right">{num(m.mean.memory?.rss_mb)}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

// ---------- upskilling ----------

const METHODS = [
    { key: 'greedy_F', label: 'Greedy on F', cls: 'bg-primary' },
    { key: 'lazy_greedy_G', label: 'Lazy greedy on G', cls: 'bg-viz-3' },
    { key: 'frequency', label: 'Top-k by frequency', cls: 'bg-caution' },
];

function UpskillingSection() {
    const { data, isLoading } = useReport<UpskillingReport>('upskilling_eval');
    return (
        <Section
            title="Optimal upskilling: gap to the exact optimum"
            description="Mean shortfall in postings unlocked, as a share of the proven ILP optimum. Lower is better; 0% means optimal."
        >
            {isLoading ? <SkeletonBlock className="h-72 rounded-xl" /> : !data ? (
                <Panel><Pending what="python -m ml_pipeline.upskilling.evaluate has not been run" /></Panel>
            ) : (
                <Panel className="space-y-5">
                    <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                        {METHODS.map((m) => <span key={m.key} className="flex items-center gap-1.5"><span className={cn('h-2.5 w-2.5 rounded-sm', m.cls)} />{m.label}</span>)}
                    </div>
                    <div className="grid gap-4 sm:grid-cols-3">
                        {Object.entries(data.grid).map(([key, cell]) => {
                            const [k, tau] = key.replace('k=', '').split(',tau=');
                            const gaps = METHODS.map((m) => (cell[m.key] as UpskillingMethod).mean_gap_pct);
                            const max = Math.max(1, ...gaps);
                            return (
                                <div key={key} className="rounded-lg border p-3">
                                    <p className="text-xs font-medium">k = {k} · τ = {tau}</p>
                                    <p className="text-[11px] text-muted-foreground">optimum {cell.mean_optimum.toFixed(1)} postings · {cell.instances} cases</p>
                                    <div className="mt-3 space-y-1.5">
                                        {METHODS.map((m, i) => (
                                            <div key={m.key} className="grid grid-cols-[1fr_48px] items-center gap-2">
                                                <span className="h-2 overflow-hidden rounded-full bg-muted">
                                                    <motion.span className={cn('block h-full rounded-full', m.cls)} initial={{ width: 0 }}
                                                                 animate={{ width: `${(gaps[i] / max) * 100}%` }} transition={{ duration: 0.6, ease }} />
                                                </span>
                                                <span className="tabular text-right text-[11px]">{gaps[i].toFixed(1)}%</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                    <p className="text-xs text-muted-foreground">
                        The app ships greedy on F refined by a time-limited ILP; see docs/optimality.md for why the textbook (1 − 1/e)
                        guarantee applies to the surrogate G and not to the eligibility count F.
                    </p>
                </Panel>
            )}
        </Section>
    );
}

// ---------- salary ----------

function SalarySection() {
    const { data, isLoading } = useReport<SalaryReport>('salary_eval');
    return (
        <Section title="Salary ranges" description="Posted pay on held-out postings that disclose it.">
            {isLoading ? <SkeletonBlock className="h-40 rounded-xl" /> : !data ? (
                <Panel><Pending what="salary evaluation not generated yet" /></Panel>
            ) : (
                <div className="grid gap-4 md:grid-cols-3">
                    <Panel className="space-y-1">
                        <p className="text-xs text-muted-foreground">P50 error (MAE · MdAPE)</p>
                        <p className="tabular text-2xl font-semibold">{inr(data.test.mae_inr)} · {data.test.mdape_pct.toFixed(1)}%</p>
                        <p className="text-xs text-muted-foreground">Baseline: {inr(data.baseline.mae_inr)} · {data.baseline.mdape_pct.toFixed(1)}%</p>
                    </Panel>
                    <Panel className="space-y-2">
                        <p className="text-xs text-muted-foreground">P10–P90 coverage (target 80%)</p>
                        <div className="flex items-baseline gap-2">
                            <span className="tabular text-lg text-muted-foreground line-through decoration-1">{pct(data.test.coverage_raw, 1)}</span>
                            <span className="tabular text-2xl font-semibold">{pct(data.test.coverage_cqr, 1)}</span>
                        </div>
                        <p className="text-xs text-muted-foreground">Before → after conformal calibration, on {num(data.test.n)} postings</p>
                    </Panel>
                    <Panel className="space-y-1">
                        <p className="text-xs text-muted-foreground">Who discloses pay (propensity AUC)</p>
                        <p className="tabular text-2xl font-semibold">{data.selection_bias.propensity.auc.toFixed(2)}</p>
                        <p className="text-xs text-muted-foreground">{pct(data.selection_bias.disclosed_share)} disclose. Well above 0.5: disclosure is not random.</p>
                    </Panel>
                </div>
            )}
        </Section>
    );
}

// ---------- the full write-up ----------

function EvaluationDoc() {
    const { data, isLoading } = useReport<{ markdown: string }>('evaluation');
    return (
        <Section title="Full evaluation" description="reports/EVALUATION.md, generated from the reports above.">
            {isLoading ? <SkeletonBlock className="h-96 rounded-xl" /> : !data ? (
                <Panel><Pending what="run python -m ml_pipeline.evaluate_all" /></Panel>
            ) : (
                <Panel className="p-5 md:p-8"><Markdown source={data.markdown} /></Panel>
            )}
        </Section>
    );
}
