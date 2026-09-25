'use client';

import { useQuery } from '@tanstack/react-query';
import { diagnosticsService } from '@/services/diagnostics';
import { ErrorState, Panel, Section, SkeletonBlock, Stat } from '@/components/yojak/bits';
import { num } from '@/lib/format';
import { cn } from '@/lib/utils';

const METHOD: Record<string, string> = {
    GET: 'text-primary border-primary/30',
    POST: 'text-accent-foreground border-accent-foreground/30',
    PUT: 'text-caution-foreground border-caution/40',
    DELETE: 'text-destructive border-destructive/40',
};

export default function SystemHealthPage() {
    const nodes = useQuery({ queryKey: ['diagnostics-nodes'], queryFn: diagnosticsService.getNodesByLabel, refetchInterval: 30_000 });
    const rels = useQuery({ queryKey: ['diagnostics-rels'], queryFn: diagnosticsService.getRelsByType, refetchInterval: 30_000 });
    const endpoints = useQuery({ queryKey: ['diagnostics-endpoints'], queryFn: diagnosticsService.getEndpoints, refetchInterval: 60_000 });
    const metrics = useQuery({ queryKey: ['diagnostics-metrics'], queryFn: diagnosticsService.getMetrics, refetchInterval: 5_000 });

    const totalNodes = nodes.data?.labels.reduce((s, n) => s + n.count, 0) ?? 0;
    const totalRels = rels.data?.types.reduce((s, r) => s + r.count, 0) ?? 0;
    const byTag = (endpoints.data?.endpoints ?? []).reduce<Record<string, NonNullable<typeof endpoints.data>['endpoints']>>((acc, ep) => {
        (acc[ep.tags[0] || 'other'] ??= []).push(ep);
        return acc;
    }, {});
    const m = metrics.data?.metrics ?? [];
    const error = nodes.error || rels.error || endpoints.error;

    return (
        <div className="space-y-10">
            <div className="space-y-1.5">
                <h1 className="text-3xl font-semibold tracking-tight">System health</h1>
                <p className="text-muted-foreground">Live counts from Neo4j and request latency measured by the API itself.</p>
            </div>
            {error && <ErrorState error={error} />}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Panel><Stat label="Graph nodes" value={nodes.isLoading ? '…' : num(totalNodes)} hint={`${nodes.data?.labels.length ?? 0} labels`} /></Panel>
                <Panel><Stat label="Relationships" value={rels.isLoading ? '…' : num(totalRels)} hint={`${rels.data?.types.length ?? 0} types`} /></Panel>
                <Panel><Stat label="API endpoints" value={num(endpoints.data?.endpoints.length ?? 0)} hint={`${Object.keys(byTag).length} groups`} /></Panel>
                <Panel>
                    <Stat label="Median p50 latency" value={m.length ? `${num(median(m.map((x) => x.p50_ms)), 1)} ms` : '–'}
                          hint={`across ${m.length} endpoints (rolling window)`} />
                </Panel>
            </div>

            <Section title="Latency by endpoint" description={metrics.data?.note ?? 'Refreshes every 5 seconds.'}>
                {metrics.isLoading ? <SkeletonBlock className="h-40" /> : m.length === 0 ? (
                    <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">No requests yet. Use the app and come back.</p>
                ) : (
                    <div className="overflow-x-auto rounded-xl border bg-card">
                        <table className="w-full text-sm">
                            <thead className="bg-muted/50 text-xs text-muted-foreground">
                                <tr>
                                    <th className="px-4 py-2 text-left font-medium">Endpoint</th>
                                    <th className="px-4 py-2 text-right font-medium">Requests</th>
                                    <th className="px-4 py-2 text-right font-medium">p50 ms</th>
                                    <th className="px-4 py-2 text-right font-medium">p95 ms</th>
                                    <th className="px-4 py-2 text-right font-medium">max ms</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y">
                                {[...m].sort((a, b) => b.p95_ms - a.p95_ms).map((x) => (
                                    <tr key={x.endpoint}>
                                        <td className="px-4 py-2 font-mono text-xs">{x.endpoint}</td>
                                        <td className="tabular px-4 py-2 text-right">{num(x.count)}</td>
                                        <td className="tabular px-4 py-2 text-right">{num(x.p50_ms, 1)}</td>
                                        <td className="tabular px-4 py-2 text-right">{num(x.p95_ms, 1)}</td>
                                        <td className="tabular px-4 py-2 text-right text-muted-foreground">{num(x.max_ms, 1)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </Section>

            <div className="grid gap-8 lg:grid-cols-2">
                <Section title="Nodes by label"><Counts rows={(nodes.data?.labels ?? []).map((n) => [n.label, n.count])} /></Section>
                <Section title="Relationships by type"><Counts rows={(rels.data?.types ?? []).map((r) => [r.type, r.count])} /></Section>
            </div>

            <Section title="API endpoints">
                <div className="grid gap-6 md:grid-cols-2">
                    {Object.entries(byTag).map(([tag, eps]) => (
                        <div key={tag} className="space-y-2">
                            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{tag}</p>
                            <ul className="divide-y rounded-lg border bg-card">
                                {eps.map((ep, i) => (
                                    <li key={`${ep.method}-${ep.path}-${i}`} className="flex items-center gap-3 px-3 py-2 font-mono text-xs">
                                        <span className={cn('w-14 rounded border px-1.5 py-0.5 text-center text-[10px] font-semibold', METHOD[ep.method] ?? 'text-muted-foreground')}>{ep.method}</span>
                                        <span className="truncate text-muted-foreground">{ep.path}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>
            </Section>
        </div>
    );
}

function Counts({ rows }: { rows: [string, number][] }) {
    const max = Math.max(1, ...rows.map(([, c]) => c));
    return (
        <ul className="space-y-2 rounded-xl border bg-card p-4">
            {[...rows].sort((a, b) => b[1] - a[1]).map(([label, count]) => (
                <li key={label} className="grid grid-cols-[minmax(0,1fr)_minmax(60px,40%)_80px] items-center gap-3 text-sm">
                    <span className="truncate font-mono text-xs">{label}</span>
                    <span className="h-1.5 overflow-hidden rounded-full bg-muted">
                        <span className="block h-full rounded-full bg-primary" style={{ width: `${Math.max(1, (Math.log1p(count) / Math.log1p(max)) * 100)}%` }} />
                    </span>
                    <span className="tabular text-right text-xs">{num(count)}</span>
                </li>
            ))}
        </ul>
    );
}

function median(xs: number[]) {
    const s = [...xs].sort((a, b) => a - b);
    const mid = Math.floor(s.length / 2);
    return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}
