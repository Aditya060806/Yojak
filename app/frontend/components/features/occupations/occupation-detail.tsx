'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, X } from '@phosphor-icons/react';
import { occupationService } from '@/services/occupations';
import { catalogService } from '@/services/catalog';
import { FilterDropdown } from '@/components/ui/filter-dropdown';
import { Segmented } from '@/components/yojak/filters';
import { ErrorState, Panel, ResultSkeleton, SalaryRange, Stat } from '@/components/yojak/bits';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import api from '@/lib/api';
import { cn } from '@/lib/utils';
import type { SalaryRange as Salary } from '@/services/yojak';
import type { SkillDetail } from '@/types';

type SkillType = 'all' | 'knowledge' | 'skill/competence';

/** One ESCO occupation: its essential and optional skills, with filters, plus Indian posted pay. */
export function OccupationDetail({ occupationUri, onClose, showHeader = true, className }: {
    occupationUri: string; onClose?: () => void; showHeader?: boolean; className?: string;
}) {
    const uri = decodeURIComponent(occupationUri);
    const [essentialOnly, setEssentialOnly] = useState(false);
    const [skillType, setSkillType] = useState<SkillType>('all');
    const [schemes, setSchemes] = useState<string[]>([]);

    const { data: conceptSchemes } = useQuery({ queryKey: ['concept-schemes'], queryFn: () => catalogService.getConceptSchemes() });
    const { data, isLoading, error, refetch } = useQuery({
        queryKey: ['skill-gap', uri, essentialOnly, skillType, schemes],
        queryFn: () => occupationService.getSkillGap(uri, {
            essentialOnly,
            skillType: skillType === 'all' ? undefined : skillType,
            schemes: schemes.length ? schemes.join(',') : undefined,
        }),
    });
    const salary = useQuery({
        queryKey: ['occ-salary', uri],
        queryFn: async () => (await api.get<{ salary: Salary }>('/salary/estimate', { params: { occupation_uri: uri } })).data.salary,
        retry: false,
    });

    if (isLoading) return <ResultSkeleton rows={3} />;
    if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
    if (!data) return null;

    return (
        <div className={cn('space-y-8', className)}>
            {showHeader && (
                <div className="flex items-start justify-between gap-4">
                    <div className="space-y-2">
                        <h1 className="text-balance text-3xl font-semibold tracking-tight md:text-4xl">{data.occupationLabel}</h1>
                        <div className="flex flex-wrap gap-2">
                            {data.iscoCode && <Badge variant="outline">ISCO-08 {data.iscoCode}</Badge>}
                            {data.iscoCode && data.iscoCode.length >= 4 && <Badge variant="muted">NCO-2015 family {data.iscoCode.slice(0, 4)}</Badge>}
                        </div>
                    </div>
                    {onClose && (
                        <button type="button" onClick={onClose} className="rounded-md p-1.5 hover:bg-muted" aria-label="Close"><X size={18} /></button>
                    )}
                </div>
            )}

            <div className="grid gap-4 md:grid-cols-[1fr_1fr_1.3fr]">
                <Panel><Stat label="Essential skills" value={data.essentialSkills.length} /></Panel>
                <Panel><Stat label="Optional skills" value={data.optionalSkills.length} /></Panel>
                <Panel className="space-y-2">
                    <p className="text-xs text-muted-foreground">Posted pay in India (typical role)</p>
                    {salary.isLoading ? <div className="h-10 animate-pulse rounded bg-muted" /> : <SalaryRange salary={salary.data ?? null} />}
                </Panel>
            </div>

            <div className="flex flex-wrap items-center gap-3">
                <Segmented<SkillType>
                    label="Skill type"
                    value={skillType}
                    onChange={setSkillType}
                    options={[{ value: 'all', label: 'All' }, { value: 'knowledge', label: 'Knowledge' }, { value: 'skill/competence', label: 'Skills' }]}
                />
                <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={essentialOnly} onChange={(e) => setEssentialOnly(e.target.checked)} className="h-4 w-4 accent-[hsl(var(--primary))]" />
                    Essential only
                </label>
                <div className="w-full sm:w-64">
                    <FilterDropdown
                        title="Schemes"
                        options={conceptSchemes?.map((s) => ({ uri: s.uri, label: s.label })) ?? []}
                        selectedUris={schemes}
                        onToggle={(u) => setSchemes((p) => (p.includes(u) ? p.filter((x) => x !== u) : [...p, u]))}
                        onClear={() => setSchemes([])}
                        placeholder="Filter by concept scheme"
                    />
                </div>
                <Button asChild variant="outline" size="sm" className="ml-auto">
                    <Link href="/student">Plan skills for roles like this <ArrowRight size={14} /></Link>
                </Button>
            </div>

            <SkillList title="Essential" skills={data.essentialSkills} tone="essential" />
            {!essentialOnly && <SkillList title="Optional" skills={data.optionalSkills} tone="optional" />}
        </div>
    );
}

function SkillList({ title, skills, tone }: { title: string; skills: SkillDetail[]; tone: 'essential' | 'optional' }) {
    if (!skills.length) return null;
    return (
        <section className="space-y-3">
            <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
                {title} <span className="tabular text-sm font-normal text-muted-foreground">{skills.length}</span>
            </h2>
            <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {skills.map((s) => (
                    <li key={s.uri} className={cn('rounded-lg border bg-card px-3.5 py-2.5', tone === 'essential' && 'border-l-2 border-l-primary')}>
                        <p className="text-sm font-medium leading-snug">{s.label}</p>
                        {(s.skillType || s.skill_type) && (
                            <p className="mt-0.5 text-xs text-muted-foreground">{s.skillType || s.skill_type}</p>
                        )}
                    </li>
                ))}
            </ul>
        </section>
    );
}
