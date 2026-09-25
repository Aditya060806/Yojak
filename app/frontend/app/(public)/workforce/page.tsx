'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { useQuery } from '@tanstack/react-query';
import { MapTrifold, X } from '@phosphor-icons/react';
import { yojak, type StateRow } from '@/services/yojak';
import { Segmented } from '@/components/yojak/filters';
import { ErrorState, InfoHint, PageIntro, Panel, ProxyNote, Section, SkeletonBlock, Stat } from '@/components/yojak/bits';
import { Badge } from '@/components/ui/badge';
import { inr, num, pct, titleCase } from '@/lib/format';
import { cn } from '@/lib/utils';

const IndiaMap = dynamic(() => import('@/components/yojak/india-map').then((m) => m.IndiaMap), {
    ssr: false,
    loading: () => <SkeletonBlock className="aspect-[56/62] w-full" />,
});

type Metric = 'demand' | 'shortage' | 'youth';

const METRIC: Record<Metric, { label: string; format: (v: number) => string }> = {
    demand: { label: 'Postings', format: (v) => num(v) },
    shortage: { label: 'Shortage index', format: (v) => v.toFixed(2) },
    youth: { label: 'Youth unemployment', format: (v) => `${v.toFixed(1)}%` },
};

export default function WorkforcePage() {
    const [metric, setMetric] = useState<Metric>('demand');
    const [field, setField] = useState('');
    const [selected, setSelected] = useState<string | null>(null);
    const fields = useQuery({ queryKey: ['wf-fields'], queryFn: yojak.fields });
    const demand = useQuery({ queryKey: ['wf-demand', field], queryFn: () => yojak.demand(field || null) });
    const shortage = useQuery({ queryKey: ['wf-shortage', field], queryFn: () => yojak.shortage(field || null) });

    const rows: StateRow[] = useMemo(() => shortage.data?.states ?? [], [shortage.data]);
    const values = useMemo(() => {
        const out: Record<string, number | null> = {};
        for (const r of rows) {
            out[r.state] = metric === 'demand' ? r.postings : metric === 'shortage' ? r.shortage_index : r.youth_ur_pct;
        }
        return out;
    }, [rows, metric]);
    const sel = rows.find((r) => r.state === selected) ?? null;
    const error = demand.error || shortage.error;

    return (
        <div className="container">
            <PageIntro
                title="Where the jobs are, and where the graduates come from"
                lead="Posting demand by state and skill family from the Naukri data, set against graduate out-turn (AISHE 2021-22) and youth unemployment (PLFS 2023-24). The shortage index is a coarse proxy; the caveats below explain exactly why."
            >
                <div className="flex flex-wrap gap-2 pt-1">
                    <Badge variant="proxy">Proxy indicator</Badge>
                    <Badge variant="muted">Snapshot: about two weeks of postings</Badge>
                </div>
            </PageIntro>

            {error && <ErrorState error={error} onRetry={() => { demand.refetch(); shortage.refetch(); }} />}

            <div className="flex flex-wrap items-end gap-4 pb-6">
                <Segmented<Metric>
                    label="Map metric"
                    value={metric}
                    onChange={setMetric}
                    options={[{ value: 'demand', label: 'Demand' }, { value: 'shortage', label: 'Shortage index' }, { value: 'youth', label: 'Youth unemployment' }]}
                />
                <div className="min-w-[240px] space-y-1.5">
                    <label htmlFor="wf-field" className="flex items-center gap-1.5 text-sm font-medium">
                        Skill family <InfoHint text="ISCED-F 2013 broad field of education, assigned to each posting from the ESCO knowledge its skills belong to." />
                    </label>
                    <select id="wf-field" value={field} onChange={(e) => setField(e.target.value)}
                            className="h-10 w-full rounded-md border border-input bg-card px-3 text-sm">
                        <option value="">All postings</option>
                        {fields.data?.fields.filter((f) => f.field !== 'unassigned').map((f) => (
                            <option key={f.field} value={f.field}>{titleCase(f.field)} ({num(f.postings)})</option>
                        ))}
                    </select>
                </div>
                {metric === 'youth' && field && (
                    <p className="pb-2 text-xs text-muted-foreground">Youth unemployment is a state figure; it does not change with the skill family.</p>
                )}
            </div>

            <div className="grid gap-8 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
                <Panel className="p-3 sm:p-5">
                    {rows.length ? (
                        <IndiaMap values={values} format={METRIC[metric].format} selected={selected} onSelect={setSelected}
                                  label={METRIC[metric].label} />
                    ) : <SkeletonBlock className="aspect-[56/62] w-full" />}
                    <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
                        Boundaries: DataMeet state boundaries (Survey of India based). The file predates the 2019 reorganisation, so
                        Ladakh has no separate shape; its postings are in the table. Click a state for details.
                    </p>
                </Panel>
                <div className="space-y-6">
                    {sel ? <StateDetail row={sel} top={demand.data?.top_skills_by_state[sel.state] ?? []} onClose={() => setSelected(null)} field={field} />
                        : <Ranking rows={rows} metric={metric} onSelect={setSelected} />}
                </div>
            </div>

            <Section title="By city tier" description="Predicted posted-salary medians per posting, and how often pay is disclosed." className="pt-12">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    {(demand.data?.tiers ?? []).map((t) => (
                        <Panel key={t.tier_label} className="space-y-3">
                            <p className="text-sm font-medium">{t.tier_label === 'unknown' ? 'Location unknown' : t.tier_label}</p>
                            <Stat label="Postings" value={num(t.postings)} />
                            <p className="tabular text-sm">
                                {inr(t.p10_median)} <span className="text-muted-foreground">to</span> {inr(t.p90_median)}
                            </p>
                            <p className="text-xs text-muted-foreground">Median P10 to P90 range, median P50 {inr(t.p50_median)}. {pct(t.disclosed_share)} disclose pay.</p>
                        </Panel>
                    ))}
                </div>
            </Section>

            <Section title="How to read this" className="pt-12">
                <ProxyNote title="Shortage index">
                    <code className="text-[12px]">{shortage.data?.formula ?? '...'}</code>. Above 1 means the state&apos;s share of these
                    postings is larger than its share of graduates.
                </ProxyNote>
                <ul className="grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
                    {(shortage.data?.caveats ?? []).map((c) => (
                        <li key={c} className="flex gap-2.5 rounded-lg border bg-card p-3">
                            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-caution" />{c}
                        </li>
                    ))}
                </ul>
            </Section>
        </div>
    );
}

function Ranking({ rows, metric, onSelect }: { rows: StateRow[]; metric: Metric; onSelect: (s: string) => void }) {
    const key = (r: StateRow) => (metric === 'demand' ? r.postings : metric === 'shortage' ? r.shortage_index : r.youth_ur_pct);
    const sorted = [...rows].sort((a, b) => (key(b) ?? -Infinity) - (key(a) ?? -Infinity));
    const max = Math.max(1e-9, ...sorted.map((r) => key(r) ?? 0));
    return (
        <Panel className="p-0">
            <div className="flex items-center justify-between border-b px-4 py-3">
                <p className="text-sm font-semibold">States by {METRIC[metric].label.toLowerCase()}</p>
                <MapTrifold size={18} className="text-muted-foreground" />
            </div>
            <ol className="max-h-[560px] divide-y overflow-y-auto">
                {sorted.map((r, i) => {
                    const v = key(r);
                    return (
                        <li key={r.state}>
                            <button type="button" onClick={() => onSelect(r.state)}
                                    className="grid w-full grid-cols-[24px_minmax(0,1fr)_minmax(60px,35%)_64px] items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-muted/50">
                                <span className="tabular text-xs text-muted-foreground">{i + 1}</span>
                                <span className="truncate">{r.state}</span>
                                <span className="h-1.5 overflow-hidden rounded-full bg-muted">
                                    <span className={cn('block h-full rounded-full', metric === 'shortage' ? 'bg-caution' : 'bg-primary')}
                                          style={{ width: v !== null && v !== undefined ? `${Math.max(1, (v / max) * 100)}%` : 0 }} />
                                </span>
                                <span className="tabular text-right text-xs">{v !== null && v !== undefined ? METRIC[metric].format(v) : '-'}</span>
                            </button>
                        </li>
                    );
                })}
            </ol>
        </Panel>
    );
}

function StateDetail({ row, top, onClose, field }: {
    row: StateRow; top: { uri: string; label: string; postings: number }[]; onClose: () => void; field: string;
}) {
    return (
        <Panel className="space-y-5">
            <div className="flex items-start justify-between gap-3">
                <div>
                    <p className="text-xs text-muted-foreground">{field ? titleCase(field) : 'All postings'}</p>
                    <h2 className="text-xl font-semibold tracking-tight">{row.state}</h2>
                </div>
                <button type="button" onClick={onClose} className="rounded-md p-1.5 hover:bg-muted" aria-label="Back to the ranking">
                    <X size={18} />
                </button>
            </div>
            <div className="grid grid-cols-2 gap-5">
                <Stat label="Postings" value={num(row.postings)}
                      hint={row.demand_share_of_field !== undefined ? `${pct(row.demand_share_of_field, 1)} of this family in India` : row.demand_share !== undefined ? `${pct(row.demand_share, 1)} of India` : undefined} />
                <Stat label="Shortage index (proxy)" value={row.shortage_index !== null ? row.shortage_index.toFixed(2) : '-'}
                      hint={row.graduate_share !== null ? `${pct(row.graduate_share, 1)} of India's graduates` : 'No graduate figure'} />
                <Stat label="Graduate out-turn (AISHE 2021-22)" value={row.outturn_total !== null ? num(row.outturn_total) : '-'} />
                <Stat label="Youth unemployment (PLFS 2023-24)" value={row.youth_ur_pct !== null ? `${row.youth_ur_pct.toFixed(1)}%` : '-'} hint="Age 15-29, usual status" />
                {row.salary_p50_median !== undefined && row.salary_p50_median !== null && (
                    <Stat label="Median predicted P50 salary" value={inr(row.salary_p50_median)} hint="Posted pay, not realised" />
                )}
            </div>
            {top.length > 0 && (
                <div className="space-y-2 border-t pt-4">
                    <p className="text-sm font-semibold">Skills most listed by postings here</p>
                    <ul className="space-y-1.5">
                        {top.slice(0, 10).map((s) => (
                            <li key={s.uri} className="flex items-center justify-between gap-3 text-sm">
                                <span className="truncate">{s.label}</span>
                                <span className="tabular text-xs text-muted-foreground">{num(s.postings)}</span>
                            </li>
                        ))}
                    </ul>
                    {field && <p className="text-xs text-muted-foreground">Top skills are for all postings in the state.</p>}
                </div>
            )}
        </Panel>
    );
}
