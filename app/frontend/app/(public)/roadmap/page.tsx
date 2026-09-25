'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'motion/react';
import { ArrowRight, Target, X } from '@phosphor-icons/react';
import { occupationService } from '@/services/occupations';
import { SkillInput } from '@/components/yojak/skill-input';
import { OccupationSearch } from '@/components/yojak/occupation-search';
import { EmptyState, ErrorState, PageIntro, Panel, ResultSkeleton, SkillChip, LiveOnly, useStaticMode } from '@/components/yojak/bits';
import { Button } from '@/components/ui/button';
import { pct } from '@/lib/format';
import type { SkillRef } from '@/services/yojak';
import type { AutocompleteOption, SkillDetail } from '@/types';

/**
 * ESCO roadmap: how far your skills are from one occupation's ESCO profile. This is the
 * taxonomy view (what ESCO says the role needs). For the market view (what Indian postings
 * ask for, and the few skills that open the most jobs), use the learning plan on /student.
 */
export default function RoadmapPage() {
    const demo = useStaticMode();
    const [target, setTarget] = useState<AutocompleteOption | null>(null);
    const [skills, setSkills] = useState<SkillRef[]>([]);
    const { data, isLoading, error, refetch } = useQuery({
        queryKey: ['roadmap-skill-gap', target?.uri],
        queryFn: () => occupationService.getSkillGap(target!.uri),
        enabled: !!target,
    });
    const have = new Set(skills.map((s) => s.uri));
    const essential = data?.essentialSkills ?? [];
    const optional = data?.optionalSkills ?? [];
    const gotEssential = essential.filter((s) => have.has(s.uri));
    const needEssential = essential.filter((s) => !have.has(s.uri));
    const needOptional = optional.filter((s) => !have.has(s.uri));
    const progress = essential.length ? gotEssential.length / essential.length : 0;

    return (
        <div className="container">
            <PageIntro
                title="Roadmap to an occupation"
                lead="Pick an occupation and add your skills to see which of its ESCO essential skills you already have and which to learn next. This follows the ESCO profile of the role; the learning plan on the Students page follows what Indian postings actually ask for."
            />
            {demo ? <LiveOnly what="The ESCO roadmap" /> : (
            <div className="grid gap-8 lg:grid-cols-[380px_1fr]">
                <aside className="space-y-6 lg:sticky lg:top-24 lg:self-start">
                    <Panel className="space-y-6">
                        {target ? (
                            <div className="space-y-1.5">
                                <p className="text-sm font-medium">Target occupation</p>
                                <div className="flex items-center justify-between gap-2 rounded-lg border bg-accent px-3 py-2 text-accent-foreground">
                                    <span className="flex items-center gap-2 text-sm font-medium"><Target size={16} /> {target.label}</span>
                                    <button type="button" onClick={() => setTarget(null)} className="rounded p-1 hover:bg-background/40" aria-label="Change occupation">
                                        <X size={14} />
                                    </button>
                                </div>
                            </div>
                        ) : <OccupationSearch onSelect={setTarget} />}
                        <div className="border-t pt-5">
                            <SkillInput value={skills} onChange={setSkills} />
                        </div>
                    </Panel>
                </aside>
                <section className="min-w-0 space-y-6" aria-live="polite">
                    {!target && (
                        <EmptyState icon={<Target size={40} weight="light" />} title="Choose an occupation to start">
                            For example &ldquo;accountant&rdquo;, &ldquo;software developer&rdquo; or &ldquo;nurse&rdquo;.
                        </EmptyState>
                    )}
                    {error && <ErrorState error={error} onRetry={() => refetch()} />}
                    {target && isLoading && <ResultSkeleton rows={3} />}
                    {target && data && (
                        <>
                            <Panel className="space-y-4">
                                <div className="flex flex-wrap items-baseline justify-between gap-2">
                                    <p className="font-medium">Essential skills you have</p>
                                    <p className="tabular text-2xl font-semibold">{gotEssential.length} <span className="text-base font-normal text-muted-foreground">of {essential.length}</span></p>
                                </div>
                                <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                                    <motion.div className="h-full rounded-full bg-primary" initial={{ width: 0 }}
                                                animate={{ width: `${progress * 100}%` }} transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }} />
                                </div>
                                <p className="text-sm text-muted-foreground">
                                    {pct(progress)} of the essential skills in the ESCO profile of <b className="text-foreground">{data.occupationLabel}</b>.
                                </p>
                                <Button asChild variant="outline" size="sm">
                                    <Link href="/student">See which skills open the most Indian postings <ArrowRight size={14} /></Link>
                                </Button>
                            </Panel>
                            <Group title="Essential skills to learn next" skills={needEssential} tone="gap" />
                            <Group title="Essential skills you have" skills={gotEssential} tone="have" />
                            <Group title="Optional skills (nice to have)" skills={needOptional} tone="neutral" />
                        </>
                    )}
                </section>
            </div>
            )}
        </div>
    );
}

function Group({ title, skills, tone }: { title: string; skills: SkillDetail[]; tone: 'gap' | 'have' | 'neutral' }) {
    if (!skills.length) return null;
    return (
        <section className="space-y-3">
            <h2 className="text-base font-semibold">{title} <span className="tabular text-sm font-normal text-muted-foreground">{skills.length}</span></h2>
            <div className="flex flex-wrap gap-1.5">
                {skills.map((s) => <SkillChip key={s.uri} label={s.label} tone={tone} />)}
            </div>
        </section>
    );
}
