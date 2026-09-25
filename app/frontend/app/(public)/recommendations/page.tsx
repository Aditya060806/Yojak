'use client';

import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { useMutation, useQuery } from '@tanstack/react-query';
import { motion } from 'motion/react';
import { CircleNotch, Compass, Sparkle, X } from '@phosphor-icons/react';
import { recommendationService } from '@/services/recommendations';
import { catalogService } from '@/services/catalog';
import { FilterDropdown } from '@/components/ui/filter-dropdown';
import { OccupationDetail } from '@/components/features/occupations/occupation-detail';
import { SkillInput } from '@/components/yojak/skill-input';
import { EmptyState, ErrorState, Hint, PageIntro, Panel, ResultSkeleton, SkillChip, LiveOnly, useStaticMode } from '@/components/yojak/bits';
import { Button } from '@/components/ui/button';
import type { SkillRef } from '@/services/yojak';
import type { OccupationRecommendation } from '@/types';

/**
 * SkillAlign's original matcher, kept working: your skills -> ESCO occupations by
 * embedding similarity (all-mpnet-base-v2 + FAISS) and skill overlap. Yojak's Student view
 * ranks real Indian postings instead; this page stays as the taxonomy-only baseline (B2).
 */
export default function RecommendationsPage() {
    const demo = useStaticMode();
    const [skills, setSkills] = useState<SkillRef[]>([]);
    const [groups, setGroups] = useState<string[]>([]);
    const [schemes, setSchemes] = useState<string[]>([]);
    const [open, setOpen] = useState<OccupationRecommendation | null>(null);

    const { data: occupationGroups } = useQuery({ queryKey: ['occupation-groups'], queryFn: () => catalogService.getOccupationGroups() });
    const { data: conceptSchemes } = useQuery({ queryKey: ['concept-schemes'], queryFn: () => catalogService.getConceptSchemes() });
    const run = useMutation({
        mutationFn: () => recommendationService.getRecommendations({
            skills: skills.map((s) => s.uri),
            occupation_groups: groups.length ? groups : undefined,
            schemes: schemes.length ? schemes : undefined,
            limit: 10,
        }),
    });
    const toggle = (set: (f: (p: string[]) => string[]) => void) => (u: string) => set((p) => (p.includes(u) ? p.filter((x) => x !== u) : [...p, u]));

    return (
        <div className="container">
            <PageIntro
                title="Match skills to ESCO occupations"
                lead="The original SkillAlign matcher: your skills are compared with every ESCO occupation profile by meaning (sentence embeddings) and by overlap. It reads the European taxonomy, not Indian postings; for jobs in India, use the Students page."
            />
            {demo ? <LiveOnly what="The ESCO occupation matcher" /> : (
            <div className="grid gap-8 lg:grid-cols-[380px_1fr]">
                <aside className="space-y-6 lg:sticky lg:top-24 lg:self-start">
                    <Panel className="space-y-6">
                        <SkillInput value={skills} onChange={setSkills} allowFile={false} />
                        <div className="space-y-3 border-t pt-5">
                            <p className="text-sm font-medium">Limit to</p>
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
                        </div>
                        <Button size="lg" className="w-full" disabled={!skills.length || run.isPending} onClick={() => run.mutate()}>
                            {run.isPending ? <CircleNotch size={18} className="animate-spin" /> : <Sparkle size={18} />}
                            Match occupations
                        </Button>
                    </Panel>
                </aside>
                <section className="min-w-0 space-y-4" aria-live="polite">
                    {!run.data && !run.isPending && !run.error && (
                        <EmptyState icon={<Compass size={40} weight="light" />} title="Matching occupations will appear here">
                            Add a few skills and press Match.
                        </EmptyState>
                    )}
                    {run.error && <ErrorState error={run.error} onRetry={() => run.mutate()} />}
                    {run.isPending && <ResultSkeleton rows={5} />}
                    {run.data && !run.isPending && (run.data.recommendations.length === 0 ? (
                        <EmptyState title="No occupations matched">Try more skills or fewer filters.</EmptyState>
                    ) : run.data.recommendations.map((rec, i) => (
                        <motion.button
                            key={rec.uri}
                            type="button"
                            onClick={() => setOpen(rec)}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.04, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                            className="block w-full rounded-xl border bg-card p-5 text-left transition-colors hover:border-primary/40"
                        >
                            <div className="flex items-start justify-between gap-4">
                                <div className="min-w-0">
                                    <p className="font-mono text-xs text-muted-foreground">{String(i + 1).padStart(2, '0')}{rec.isco_code ? `  -  ISCO ${rec.isco_code}` : ''}</p>
                                    <h2 className="mt-1 text-lg font-semibold tracking-tight">{rec.label}</h2>
                                </div>
                                <Hint text={`Blend of embedding similarity (${rec.similarity_score.toFixed(2)}) and skill overlap with the ESCO profile.`}>
                                    <span className="tabular text-2xl font-semibold text-primary">{Math.round(rec.match_percentage)}%</span>
                                </Hint>
                            </div>
                            {rec.description && <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{rec.description}</p>}
                            <div className="mt-3 flex flex-wrap gap-1.5">
                                {rec.matched_skills.slice(0, 5).map((s) => <SkillChip key={s.uri} label={s.label} tone="have" />)}
                                {rec.missing_skills.slice(0, 4).map((s) => <SkillChip key={s.uri} label={s.label} tone="gap" />)}
                            </div>
                        </motion.button>
                    )))}
                </section>
            </div>
            )}
            <Dialog.Root open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
                <Dialog.Portal>
                    <Dialog.Overlay className="fixed inset-0 z-50 bg-background/60 backdrop-blur-sm" />
                    <Dialog.Content className="fixed inset-y-0 right-0 z-50 w-full max-w-3xl overflow-y-auto border-l bg-background p-6 shadow-2xl">
                        <div className="flex items-center justify-between pb-4">
                            <Dialog.Title className="text-sm text-muted-foreground">Occupation profile</Dialog.Title>
                            <Dialog.Close className="rounded-md p-1.5 hover:bg-muted" aria-label="Close"><X size={18} /></Dialog.Close>
                        </div>
                        <Dialog.Description className="sr-only">ESCO skills for the selected occupation</Dialog.Description>
                        {open && <OccupationDetail occupationUri={open.uri} />}
                    </Dialog.Content>
                </Dialog.Portal>
            </Dialog.Root>
        </div>
    );
}
