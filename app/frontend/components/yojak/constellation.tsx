'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight, MagnifyingGlass, X } from '@phosphor-icons/react';
import { yojak } from '@/services/yojak';
import { ErrorState, SkeletonBlock } from './bits';
import { SkillNetworkScene } from './skill-network-scene';
import { num } from '@/lib/format';
import { cn } from '@/lib/utils';

export function Constellation({ className, expanded = false }: { className?: string; expanded?: boolean }) {
    const { data, error, isLoading, refetch } = useQuery({ queryKey: ['constellation'], queryFn: yojak.constellation, staleTime: Infinity });
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [query, setQuery] = useState('');
    const [kind, setKind] = useState<'all' | 'skill' | 'occupation'>('all');
    const selected = data?.nodes.find((n) => n.id === selectedId);
    const sorted = useMemo(() => [...(data?.nodes ?? [])].sort((a, b) => b.postings - a.postings), [data]);
    const visible = sorted.filter((n) => (kind === 'all' || n.kind === kind) && n.label.toLowerCase().includes(query.toLowerCase()));
    const neighbors = useMemo(() => {
        if (!data || !selectedId) return [];
        return data.edges.filter((e) => e.source === selectedId || e.target === selectedId)
            .sort((a, b) => b.postings - a.postings).map((e) => ({
                node: data.nodes.find((n) => n.id === (e.source === selectedId ? e.target : e.source)), edge: e,
            })).filter((entry) => entry.node);
    }, [data, selectedId]);

    if (error) return <div className="p-6"><ErrorState error={error} onRetry={() => refetch()} /></div>;
    if (isLoading || !data) return <div className={cn('flex h-full min-h-[320px] items-center justify-center', className)} aria-busy="true"><SkeletonBlock className="h-40 w-3/4" /></div>;
    if (!data.nodes.length) return <p className="p-6 text-sm text-muted-foreground">No skill relationships are available in this dataset.</p>;

    return <div className={cn('h-full min-w-0', expanded && 'grid gap-0 overflow-hidden border-y lg:grid-cols-[290px_1fr]', className)}>
        {expanded && <aside className="border-b bg-card p-5 lg:border-b-0 lg:border-r">
            <label className="relative block"><MagnifyingGlass size={17} className="absolute left-3 top-3 text-muted-foreground" /><input aria-label="Search network" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search skills and roles" className="h-10 w-full rounded-md border bg-background pl-9 pr-3 text-sm" /></label>
            <div className="mt-4 flex gap-1 rounded-md bg-muted p-1" aria-label="Node types">
                {(['all', 'skill', 'occupation'] as const).map((k) => <button key={k} aria-pressed={kind === k} onClick={() => setKind(k)} className={cn('flex-1 rounded px-2 py-1.5 text-xs font-medium', kind === k ? 'bg-card shadow-sm' : 'text-muted-foreground')}>{k === 'all' ? 'All' : k === 'skill' ? 'Skills' : 'Roles'}</button>)}
            </div>
            <p className="my-4 text-xs text-muted-foreground">{num(visible.length)} results, ordered by posting count</p>
            <div className="max-h-[240px] overflow-y-auto lg:max-h-[420px]">
                {visible.map((node) => <button key={node.id} onClick={() => setSelectedId(node.id)} aria-pressed={selectedId === node.id} className={cn('flex w-full items-center gap-3 rounded-md px-2 py-3 text-left text-sm hover:bg-muted', node.id === selectedId && 'bg-accent text-accent-foreground')}><span className={cn('h-2 w-2 shrink-0 rounded-full', node.kind === 'skill' ? 'bg-viz-4' : 'bg-caution')} /><span className="min-w-0 flex-1 break-words">{node.label}</span><span className="tabular text-xs text-muted-foreground">{num(node.postings)}</span></button>)}
                {!visible.length && <p className="py-6 text-sm text-muted-foreground">No matches. Try another skill or role.</p>}
            </div>
        </aside>}
        <div className="relative flex h-full min-h-[280px] min-w-0 flex-col">
            {!expanded && <div className="absolute left-4 right-4 top-4 z-20 flex items-center justify-end gap-2">
                <select aria-label="Focus a skill or occupation" value={selectedId ?? ''} onChange={(e) => setSelectedId(e.target.value || null)} className="h-9 max-w-[210px] rounded-md border bg-card/95 px-2 text-xs shadow-sm"><option value="">All relationships</option>{sorted.map((n) => <option key={n.id} value={n.id}>{n.label}</option>)}</select>
                <Link href="/network" className="network-control" aria-label="Open skill network" title="Open skill network"><ArrowUpRight size={17} /></Link>
            </div>}
            <div className={cn('min-h-0 flex-1', expanded && 'h-[420px] flex-none md:h-[510px]')}><SkillNetworkScene data={data} selectedId={selectedId} onSelect={(node) => setSelectedId(node.id)} /></div>
            {expanded && <div className="border-t bg-card p-5" aria-live="polite">
                <div className="flex items-start justify-between gap-4"><div><p className="text-[11px] font-medium uppercase text-muted-foreground">{selected?.kind ?? 'Skills and occupations'}</p><h2 className="mt-1 text-lg font-semibold">{selected?.label ?? 'India\'s skill relationships'}</h2><p className="mt-1 text-sm text-muted-foreground">{selected ? `${num(selected.postings)} postings list this ${selected.kind}. ${num(neighbors.length)} connected nodes.` : `${num(data.nodes.length)} nodes and ${num(data.edges.length)} relationships from ${num(data.postings)} historical postings.`}</p></div>{selectedId && <button className="network-control" aria-label="Clear selection" onClick={() => setSelectedId(null)}><X size={17} /></button>}</div>
                {selected && <div className="mt-4 flex flex-wrap gap-2">{neighbors.slice(0, 10).map(({ node, edge }) => node && <button key={node.id} onClick={() => setSelectedId(node.id)} className="rounded-md border px-2.5 py-1.5 text-xs hover:bg-accent" title={`${num(edge.postings)} shared postings; ${edge.kind}`}>{node.label} <span className="text-muted-foreground">{num(edge.postings)}</span></button>)}</div>}
                <p className="mt-4 text-xs leading-relaxed text-muted-foreground">Links show skills co-listed more often than chance, or skills characteristic of a role. Connections describe posting patterns, not career eligibility.</p>
            </div>}
            {!expanded && <div className="pointer-events-none absolute bottom-4 left-4 max-w-[calc(100%-200px)]" aria-live="polite"><p className="truncate text-sm font-medium">{selected?.label ?? 'Connected by skills'}</p><p className="mt-1 text-[11px] text-muted-foreground">{selected ? `${num(selected.postings)} postings` : `${num(data.nodes.length)} nodes from ${num(data.postings)} postings`}</p></div>}
        </div>
    </div>;
}
