'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { motion } from 'motion/react';
import { Briefcase, Compass, Path, Sparkle, CircleNotch, Buildings, MapPin } from '@phosphor-icons/react';
import { yojak, type Filters, type Plan, type PlanRequest, type RoleMatch, type SkillRef, type StudentExample, type StudentMatch, type StudentPlan } from '@/services/yojak';
import { SkillInput } from '@/components/yojak/skill-input';
import { RoleComparison } from '@/components/yojak/role-comparison';
import { ExpSelect, Segmented, StateSelect, TierToggle } from '@/components/yojak/filters';
import {
    DemoNotice, EmptyState, ErrorState, ExamplePicker, FitBar, Hint, InfoHint, PageIntro, Panel, ResultSkeleton, SalaryRange, SkillChip,
    useStaticMode, WhyDrawer,
} from '@/components/yojak/bits';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { inr, num, pct, TIER_LABEL } from '@/lib/format';
import { cn } from '@/lib/utils';

type Tab = 'roles' | 'jobs' | 'plan';

export default function StudentPage() {
    const [skills, setSkills] = useState<SkillRef[]>([]);
    const [tiers, setTiers] = useState<number[]>([]);
    const [state, setState] = useState('');
    const [exp, setExp] = useState('');
    const [tab, setTab] = useState<Tab>('roles');
    const [target, setTarget] = useState<RoleMatch | null>(null);

    const filters = useMemo(() => ({
        tiers: tiers.length ? tiers : undefined,
        states: state ? [state] : undefined,
        exp_bands: exp ? [exp] : undefined,
    }), [tiers, state, exp]);

    const profileKey = JSON.stringify({ skills: skills.map((s) => s.uri), ...filters });
    const match = useMutation({
        mutationFn: async () => ({ result: await yojak.studentMatch({ skills: skills.map((s) => s.uri), ...filters, limit: 25 }), profileKey }),
        onSuccess: ({ result }) => { setTarget(result.roles[0] ?? null); },
    });

    const canRun = skills.length > 0;
    const demo = useStaticMode();
    if (demo) return <StudentDemo />;

    return (
        <div className="container">
            <PageIntro
                title="Your skills. Your next career move."
                lead="Add the skills you have in English, Hindi, Punjabi or romanised Hindi, or upload a resume. Yojak matches them against Indian job postings, explains every match, and plans what to learn next."
            />
            <div className="grid gap-8 lg:grid-cols-[380px_1fr]">
                <aside className="space-y-6 lg:sticky lg:top-24 lg:self-start">
                    <Panel className="space-y-6">
                        <SkillInput value={skills} onChange={setSkills} />
                        <div className="grid gap-4 border-t pt-5">
                            <TierToggle value={tiers} onChange={setTiers} />
                            <div className="grid grid-cols-2 gap-3">
                                <StateSelect value={state} onChange={setState} />
                                <ExpSelect value={exp} onChange={setExp} />
                            </div>
                        </div>
                        <Button size="lg" className="w-full" disabled={!canRun || match.isPending} onClick={() => match.mutate()}>
                            {match.isPending ? <CircleNotch size={18} className="animate-spin" /> : <Sparkle size={18} />}
                            Find my matches
                        </Button>
                    </Panel>
                </aside>

                <section className="min-w-0 space-y-5" aria-live="polite">
                    {!match.data && !match.isPending && !match.error && (
                        <EmptyState icon={<Compass size={40} weight="light" />} title="Your matches will appear here">
                            Start with three or more skills. Try &ldquo;Excel, Tally, GST, customer service&rdquo; or paste a few
                            lines from your resume.
                        </EmptyState>
                    )}
                    {match.error && <ErrorState error={match.error} onRetry={() => match.mutate()} />}
                    {match.isPending && <ResultSkeleton rows={5} />}
                    {match.data && match.data.profileKey !== profileKey && !match.isPending && <EmptyState title="Your profile has changed">Find matches again to update your roles and learning plan.</EmptyState>}
                    {match.data && match.data.profileKey === profileKey && !match.isPending && (
                        <Results key={match.submittedAt} data={match.data.result} tab={tab} setTab={setTab} target={target} setTarget={setTarget}
                                 skills={skills} filters={filters} />
                    )}
                </section>
            </div>
        </div>
    );
}

function Results({ data, tab, setTab, target, setTarget, skills, filters, savedPlan }: {
    data: StudentMatch; tab: Tab; setTab: (t: Tab) => void; target: RoleMatch | null; setTarget: (r: RoleMatch) => void;
    skills: SkillRef[]; filters: Filters; savedPlan?: StudentPlan;
}) {
    const [comparison, setComparison] = useState<string[]>([]);
    const toggleComparison = (uri: string) => setComparison((current) => current.includes(uri)
        ? current.filter((id) => id !== uri) : current.length < 3 ? [...current, uri] : current);
    const selectedRoles = data.roles.filter((role) => comparison.includes(role.occupation_uri));
    return (
        <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <Segmented<Tab>
                    label="Result view"
                    value={tab}
                    onChange={setTab}
                    options={[{ value: 'roles', label: 'Roles' }, { value: 'jobs', label: 'Postings' }, { value: 'plan', label: 'Learning plan' }]}
                />
                <p className="text-xs text-muted-foreground">
                    {num(data.pool_size)} postings in your filters  -  ranked by {data.model.served_name}{' '}
                    <InfoHint text={data.model.note ?? 'The serving model used for these results. See Evidence for available benchmark reports.'} />
                </p>
            </div>
            {tab === 'roles' && <>
                {selectedRoles.length > 0 && <RoleComparison roles={selectedRoles} example={!!savedPlan} onRemove={toggleComparison} onClear={() => setComparison([])} />}
                <Roles roles={data.roles} comparison={comparison} onCompare={toggleComparison} examplePlan={!!savedPlan} onPlan={(r) => { setTarget(r); setTab('plan'); }} />
            </>}
            {tab === 'jobs' && <Jobs data={data} />}
            {tab === 'plan' && (savedPlan ? <PlanResult data={savedPlan} /> : <PlanView skills={skills} filters={filters} roles={data.roles} target={target} setTarget={setTarget} />)}
        </div>
    );
}

function Roles({ roles, onPlan, comparison, onCompare, examplePlan = false }: { roles: RoleMatch[]; onPlan: (r: RoleMatch) => void; comparison: string[]; onCompare: (uri: string) => void; examplePlan?: boolean }) {
    if (!roles.length) return <EmptyState title="No roles matched">Try removing filters or adding more skills.</EmptyState>;
    return (
        <div className="grid gap-3 md:grid-cols-2">
            {roles.map((r, i) => (
                <motion.article
                    key={r.occupation_uri}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                    className={cn('flex min-w-0 flex-col rounded-xl border bg-card p-5', i === 0 && 'md:col-span-2')}
                >
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <h3 className="text-[17px] font-semibold capitalize leading-snug">{r.occupation_label}</h3>
                            <p className="mt-1 text-xs text-muted-foreground">
                                {num(r.postings)} postings{r.nco_family ? <>  -  NCO-2015 family {r.nco_family}</> : null}
                            </p>
                        </div>
                        {i === 0 && <Badge variant="accent">Best match</Badge>}
                    </div>
                    <div className="mt-4"><SalaryRange salary={r.salary} /></div>
                    {r.top_missing.length > 0 && (
                        <div className="mt-4 space-y-1.5">
                            <p className="text-xs text-muted-foreground">Postings for this role often ask for</p>
                            <div className="flex flex-wrap gap-1.5">
                                {r.top_missing.map((s) => <SkillChip key={s.uri} label={s.label} tone="gap" />)}
                            </div>
                        </div>
                    )}
                    <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-5">
                        <label className="inline-flex items-center gap-2 text-xs">
                            <input type="checkbox" checked={comparison.includes(r.occupation_uri)} disabled={comparison.length >= 3 && !comparison.includes(r.occupation_uri)} onChange={() => onCompare(r.occupation_uri)} aria-label={`Compare ${r.occupation_label}`} className="h-4 w-4 accent-[hsl(var(--primary))]" />
                            Compare
                        </label>
                        <WhyDrawer title={r.occupation_label} subtitle="Why this role matches" why={r.why} />
                        <Button size="sm" variant="outline" onClick={() => onPlan(r)}>
                            <Path size={15} /> {examplePlan ? 'View example plan' : 'Plan for this role'}
                        </Button>
                    </div>
                </motion.article>
            ))}
        </div>
    );
}

function Jobs({ data }: { data: StudentMatch }) {
    if (!data.jobs.length) return <EmptyState title="No postings matched">Try removing filters.</EmptyState>;
    return (
        <ul className="divide-y rounded-xl border bg-card">
            {data.jobs.map((j) => (
                <li key={j.job_id} className="grid gap-3 p-4 md:grid-cols-[1fr_auto] md:items-center">
                    <div className="min-w-0 space-y-1.5">
                        <p className="truncate font-medium">{j.title}</p>
                        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                            <span className="inline-flex items-center gap-1"><Buildings size={13} />{j.company}</span>
                            {j.city && <span className="inline-flex items-center gap-1"><MapPin size={13} />{j.city}</span>}
                            {j.tier && <span>{TIER_LABEL[j.tier]}</span>}
                            {j.occupation_label && <span className="capitalize">{j.occupation_label}</span>}
                        </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 md:justify-end">
                        <FitBar value={j.fit} />
                        <SalaryRange salary={j.salary} compact />
                        <WhyDrawer title={j.title} subtitle={`${j.company}${j.city ? `  -  ${j.city}` : ''}`} why={j.why} />
                    </div>
                </li>
            ))}
        </ul>
    );
}

function PlanView({ skills, filters, roles, target, setTarget }: {
    skills: SkillRef[]; filters: Filters; roles: RoleMatch[]; target: RoleMatch | null; setTarget: (r: RoleMatch) => void;
}) {
    const [k, setK] = useState(3);
    const [tau, setTau] = useState(0.6);
    const [value, setValue] = useState<'count' | 'salary'>('count');
    const [budgeted, setBudgeted] = useState(false);
    const planKey = JSON.stringify({ skills, filters, k, tau, value, target: target?.occupation_uri, budgeted });
    const plan = useMutation({
        mutationFn: async () => ({ result: await yojak.studentPlan({
            skills: skills.map((s) => s.uri), ...filters, k, tau, value,
            target_occupation: target?.occupation_uri ?? null, budget: budgeted ? 3 : null,
        } as PlanRequest), planKey }),
    });

    return (
        <div className="space-y-5">
            <Panel className="grid gap-4 md:grid-cols-[1.4fr_1fr_1fr_auto] md:items-end">
                <div className="space-y-1.5">
                    <label htmlFor="target" className="text-sm font-medium">Aim for</label>
                    <select
                        id="target"
                        value={target?.occupation_uri ?? ''}
                        onChange={(e) => { const r = roles.find((x) => x.occupation_uri === e.target.value); if (r) setTarget(r); }}
                        className="h-10 w-full rounded-md border border-input bg-card px-3 text-sm capitalize"
                    >
                        {roles.map((r) => <option key={r.occupation_uri} value={r.occupation_uri}>{r.occupation_label}</option>)}
                    </select>
                </div>
                <div className="space-y-1.5">
                    <label htmlFor="k" className="text-sm font-medium">Skills to learn: {k}</label>
                    <input id="k" type="range" min={1} max={6} value={k} onChange={(e) => setK(Number(e.target.value))} className="w-full accent-[hsl(var(--primary))]" />
                </div>
                <div className="space-y-1.5">
                    <label htmlFor="tau" className="flex items-center gap-1 text-sm font-medium">
                        Eligible when <InfoHint text="A posting counts as reachable when you cover this share of its skills, weighted so rare, specific skills count more." />
                    </label>
                    <select id="tau" value={tau} onChange={(e) => setTau(Number(e.target.value))} className="h-10 w-full rounded-md border border-input bg-card px-3 text-sm">
                        <option value={0.4}>40% of skills covered</option>
                        <option value={0.6}>60% of skills covered</option>
                        <option value={0.8}>80% of skills covered</option>
                    </select>
                </div>
                <Button onClick={() => plan.mutate()} disabled={plan.isPending || !target}>
                    {plan.isPending ? <CircleNotch size={16} className="animate-spin" /> : <Path size={16} />} Build plan
                </Button>
                <div className="flex flex-wrap items-center gap-4 md:col-span-4">
                    <Segmented<'count' | 'salary'> label="Optimise for" value={value} onChange={setValue}
                        options={[{ value: 'count', label: 'Most postings' }, { value: 'salary', label: 'Best-paid postings' }]} />
                    <label className="flex items-center gap-2 text-sm text-muted-foreground">
                        <input type="checkbox" checked={budgeted} onChange={(e) => setBudgeted(e.target.checked)} className="accent-[hsl(var(--primary))]" />
                        Also show an effort-aware plan (budget of about 3 typical skills)
                    </label>
                </div>
            </Panel>

            {plan.error && <ErrorState error={plan.error} />}
            {plan.isPending && <ResultSkeleton rows={2} />}
            {!plan.data && !plan.isPending && !plan.error && (
                <EmptyState icon={<Path size={36} weight="light" />} title="Build a plan">
                    Yojak searches for the set of skills that makes the most postings reachable, and shows it next to the usual
                    &ldquo;learn the most common skills&rdquo; advice.
                </EmptyState>
            )}
            {plan.data && plan.data.planKey !== planKey && !plan.isPending && <EmptyState title="Your plan settings have changed">Build a plan to see results for these settings.</EmptyState>}
            {plan.data && plan.data.planKey === planKey && !plan.isPending && <PlanResult data={plan.data.result} />}
        </div>
    );
}

function PlanResult({ data }: { data: StudentPlan }) {
    const opt = data.optimal_plan, fq = data.frequency_plan;
    const gain = opt.eligible_after - fq.eligible_after;
    return (
        <div className="space-y-5">
            <Panel className="grid gap-6 md:grid-cols-3">
                <div>
                    <p className="text-xs text-muted-foreground">Reachable now</p>
                    <p className="tabular text-3xl font-semibold">{num(opt.eligible_before)}</p>
                    <p className="text-xs text-muted-foreground">of {num(data.pool.postings)} postings in scope</p>
                </div>
                <div>
                    <p className="text-xs text-muted-foreground">After this learning plan</p>
                    <p className="tabular text-3xl font-semibold text-primary">{num(opt.eligible_after)}</p>
                    <p className="text-xs text-muted-foreground">{opt.method}</p>
                </div>
                <div>
                    <p className="text-xs text-muted-foreground">Versus common-skills advice</p>
                    <p className="tabular text-3xl font-semibold">{gain >= 0 ? '+' : ''}{num(gain)}</p>
                    <p className="text-xs text-muted-foreground">more reachable postings than learning the {fq.steps.length} most frequent skills</p>
                </div>
            </Panel>
            <div className="grid gap-4 lg:grid-cols-2">
                <PlanColumn title={opt.optimal === true ? 'Optimal learning plan' : 'Recommended learning plan'} plan={opt} highlight total={data.pool.postings} />
                <PlanColumn title="Most common skills" plan={fq} total={data.pool.postings} />
            </div>
            {data.effort_plan && <PlanColumn title="Effort-aware plan" plan={data.effort_plan} total={data.pool.postings} />}
            <ul className="space-y-1 text-xs text-muted-foreground">{data.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </div>
    );
}

function PlanColumn({ title, plan, highlight = false, total }: { title: string; plan: Plan; highlight?: boolean; total: number }) {
    return (
        <div className={cn('rounded-xl border bg-card p-5', highlight && 'border-primary/40 ring-1 ring-primary/20')}>
            <div className="mb-4 flex items-baseline justify-between gap-2">
                <h3 className="font-semibold">{title}</h3>
                <span className="tabular text-sm text-muted-foreground">{num(plan.eligible_before)} → {num(plan.eligible_after)}</span>
            </div>
            {plan.steps.length === 0 ? (
                <p className="text-sm text-muted-foreground">No skill in scope makes another posting reachable at this threshold.</p>
            ) : (
                <ol className="space-y-4">
                    {plan.steps.map((s, i) => (
                        <li key={s.skill.uri} className="grid grid-cols-[28px_1fr] gap-3">
                            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-muted text-xs font-semibold tabular">{i + 1}</span>
                            <div className="min-w-0 space-y-2">
                                <div className="flex flex-wrap items-baseline justify-between gap-2">
                                    <span className="font-medium">{s.skill.label}</span>
                                    <span className="tabular text-sm text-primary">+{num(s.jobs_unlocked)} postings</span>
                                </div>
                                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                                    <motion.div className="h-full rounded-full bg-primary"
                                        initial={{ width: 0 }} animate={{ width: `${Math.min(100, (s.cumulative_eligible / Math.max(1, total)) * 100)}%` }}
                                        transition={{ duration: 0.6, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }} />
                                </div>
                                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                                    <Hint text={s.effort.note ?? 'Heuristic: skill breadth and closeness to what you know.'}>
                                        <span>Effort {s.effort.effort.toFixed(2)}{s.effort.proximity_factor && s.effort.proximity_factor < 1 ? '  -  close to your skills' : ''}</span>
                                    </Hint>
                                    {s.salary_shift_p50 && (
                                        <Hint text="Median posted pay of the postings this step unlocks, minus the median of postings you already reach. Shown as a range across those postings.">
                                            <span>Pay shift {inr(s.salary_shift_p50.p10)} to {inr(s.salary_shift_p50.p90)}</span>
                                        </Hint>
                                    )}
                                    <WhyDrawer title={s.skill.label} subtitle="Why this skill" why={s.why} />
                                </div>
                            </div>
                        </li>
                    ))}
                </ol>
            )}
            <p className="mt-4 text-xs text-muted-foreground">{plan.method}  -  {pct(plan.eligible_after / Math.max(1, total))} of postings reachable</p>
        </div>
    );
}

/** Hosted demo: precomputed runs of the example profiles in scripts/personas.yaml. */
function StudentDemo() {
    const index = useQuery({ queryKey: ['examples'], queryFn: yojak.examples, staleTime: Infinity });
    const [id, setId] = useState<string | null>(null);
    const [tab, setTab] = useState<Tab>('roles');
    const items = useMemo(() => index.data?.student ?? [], [index.data]);
    useEffect(() => { if (!id && items.length) setId(items[0].id); }, [id, items]);
    const file = items.find((i) => i.id === id)?.file;
    const ex = useQuery({
        queryKey: ['example', file],
        queryFn: () => yojak.example<StudentExample>(file!),
        enabled: !!file,
        staleTime: Infinity,
    });
    const [target, setTarget] = useState<RoleMatch | null>(null);
    return (
        <div className="container">
            <PageIntro
                title="Your skills. Your next career move."
                lead="Yojak matches skills written in English, Hindi, Punjabi or romanised Hindi against Indian job postings, explains every match, and plans what to learn next."
            />
            <div className="grid gap-8 lg:grid-cols-[380px_1fr]">
                <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
                    <DemoNotice />
                    <Panel className="space-y-4">
                        <p className="text-sm font-semibold">Example profiles</p>
                        {index.error ? <ErrorState error={index.error} /> : <ExamplePicker items={items} value={id} onChange={(v) => { setId(v); setTab('roles'); setTarget(null); }} />}
                        {ex.data && (
                            <div className="space-y-2 border-t pt-4">
                                <p className="text-xs font-medium text-muted-foreground">What they typed</p>
                                <p className="rounded-md bg-muted/60 px-3 py-2 text-sm leading-relaxed" lang={ex.data.match.extraction?.language === 'hi' ? 'hi' : undefined}>
                                    {String(ex.data.persona.request.text ?? '')}
                                </p>
                                <p className="text-xs font-medium text-muted-foreground">Skills Yojak understood</p>
                                <div className="flex flex-wrap gap-1.5">
                                    {ex.data.match.skills.map((s) => <SkillChip key={s.uri} label={s.label} tone="have" />)}
                                </div>
                            </div>
                        )}
                    </Panel>
                </aside>
                <section className="min-w-0 space-y-5" aria-live="polite">
                    {(index.isLoading || ex.isLoading) && <ResultSkeleton rows={5} />}
                    {ex.error && <ErrorState error={ex.error} onRetry={() => ex.refetch()} />}
                    {ex.data && (
                        <Results key={file} data={ex.data.match} tab={tab} setTab={setTab} target={target ?? ex.data.match.roles[0] ?? null}
                                 setTarget={setTarget} skills={ex.data.match.skills} filters={{}} savedPlan={ex.data.plan} />
                    )}
                </section>
            </div>
        </div>
    );
}
