'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'motion/react';
import { ArrowUpRight, MagnifyingGlass, X } from '@phosphor-icons/react';
import { occupationService } from '@/services/occupations';
import { catalogService } from '@/services/catalog';
import { FilterDropdown } from '@/components/ui/filter-dropdown';
import { EmptyState, ErrorState, LiveOnly, PageIntro, SkeletonBlock, useStaticMode } from '@/components/yojak/bits';
import { useDebounce } from '@/hooks/use-debounce';
import { num } from '@/lib/format';

export default function ExplorePage() {
    const [q, setQ] = useState('');
    const [groups, setGroups] = useState<string[]>([]);
    const [schemes, setSchemes] = useState<string[]>([]);
    const debounced = useDebounce(q, 350);

    const { data: occupationGroups } = useQuery({ queryKey: ['occupation-groups'], queryFn: () => catalogService.getOccupationGroups() });
    const { data: conceptSchemes } = useQuery({ queryKey: ['concept-schemes'], queryFn: () => catalogService.getConceptSchemes() });
    const { data, isLoading, error, refetch } = useQuery({
        queryKey: ['occupations', debounced, groups, schemes],
        queryFn: () => occupationService.search({
            q: debounced || undefined,
            groups: groups.length ? groups.join(',') : undefined,
            schemes: schemes.length ? schemes.join(',') : undefined,
            limit: 60,
        }),
    });
    const toggle = (set: (f: (p: string[]) => string[]) => void) => (u: string) => set((p) => (p.includes(u) ? p.filter((x) => x !== u) : [...p, u]));
    const filtered = groups.length > 0 || schemes.length > 0 || q.length > 0;
    const demo = useStaticMode();

    return (
        <div className="container">
            <PageIntro
                title="Explore the ESCO occupations"
                lead="Every ESCO occupation with its essential and optional skills, ISCO-08 codes and NCO-2015 families. Search by name, or filter by ISCO group and ESCO concept scheme."
            />
            {demo ? <LiveOnly what="The ESCO explorer" /> : <>
            <div className="sticky top-16 z-30 -mx-4 border-b bg-background/85 px-4 py-3 backdrop-blur md:-mx-6 md:px-6 lg:-mx-8 lg:px-8">
                <div className="flex flex-col gap-3 md:flex-row md:items-center">
                    <div className="relative flex-1 md:max-w-md">
                        <MagnifyingGlass size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                        <input
                            value={q}
                            onChange={(e) => setQ(e.target.value)}
                            placeholder="Search occupations, e.g. data analyst"
                            aria-label="Search occupations"
                            className="h-10 w-full rounded-md border border-input bg-card pl-9 pr-3 text-sm placeholder:text-muted-foreground/80"
                        />
                    </div>
                    <div className="flex gap-2 overflow-x-auto no-scrollbar">
                        <FilterDropdown
                            title="ISCO groups"
                            options={occupationGroups?.map((g) => ({ uri: g.uri, label: g.label, code: g.code })) ?? []}
                            selectedUris={groups}
                            onToggle={toggle(setGroups)}
                            onClear={() => setGroups([])}
                            placeholder="ISCO groups"
                        />
                        <FilterDropdown
                            title="Schemes"
                            options={conceptSchemes?.map((s) => ({ uri: s.uri, label: s.label })) ?? []}
                            selectedUris={schemes}
                            onToggle={toggle(setSchemes)}
                            onClear={() => setSchemes([])}
                            placeholder="Concept schemes"
                        />
                        {filtered && (
                            <button type="button" onClick={() => { setGroups([]); setSchemes([]); setQ(''); }}
                                    className="inline-flex h-10 items-center gap-1 rounded-md px-3 text-sm text-muted-foreground hover:bg-muted hover:text-foreground">
                                <X size={14} /> Clear
                            </button>
                        )}
                    </div>
                    <p className="tabular text-sm text-muted-foreground md:ml-auto">{data ? `${num(data.length)} shown` : ''}</p>
                </div>
            </div>

            <div className="pt-6">
                {error && <ErrorState error={error} onRetry={() => refetch()} />}
                {isLoading && (
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {Array.from({ length: 9 }).map((_, i) => <SkeletonBlock key={i} className="h-36 rounded-xl" />)}
                    </div>
                )}
                {data && data.length === 0 && <EmptyState title="No occupations match">Try a shorter search or remove a filter.</EmptyState>}
                {data && data.length > 0 && (
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {data.map((o, i) => (
                            <motion.div key={o.uri} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: Math.min(i, 18) * 0.02, duration: 0.3 }}>
                                <Link
                                    href={`/explore/${encodeURIComponent(o.uri)}`}
                                    className="group flex h-full flex-col rounded-xl border bg-card p-5 transition-colors hover:border-primary/40"
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <h2 className="font-medium leading-snug group-hover:text-primary">{o.label}</h2>
                                        <ArrowUpRight size={16} className="shrink-0 text-muted-foreground group-hover:text-primary" />
                                    </div>
                                    {o.iscoCode && <p className="mt-1 font-mono text-xs text-muted-foreground">ISCO {o.iscoCode}</p>}
                                    {o.description && <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-muted-foreground">{o.description}</p>}
                                </Link>
                            </motion.div>
                        ))}
                    </div>
                )}
            </div>
            </>}
        </div>
    );
}
