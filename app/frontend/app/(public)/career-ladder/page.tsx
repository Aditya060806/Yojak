'use client';

import Link from 'next/link';
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { ArrowRight, ChartBar, CircleNotch, LockKey, Path, WarningCircle } from '@phosphor-icons/react';
import api from '@/lib/api';
import { isStaticMode } from '@/lib/static';
import { Button } from '@/components/ui/button';
import { PageIntro } from '@/components/yojak/bits';

type Cohort = { n: number; groups: number; oof_auc: number; features: { feature: string; correlation: number }[]; interpretation: string };
type Match = { support: number; source_version: string; model_id: string; limitations: string[];
    vocabulary_evidence?: { submitted: number; observed_count: number; unobserved: string[]; meaning: string };
    matches: { row_key: string; title: string; location: string; score: number; matched: string[]; missing: string[]; skills_truncated: boolean }[];
    research: { jds: Cohort | null; sds: Cohort | null } };
type Strategy = { skills: string[]; coverage: number; proven_optimal: boolean };
type Plan = { support: number; before: number; optimized: Strategy | null; frequency: Strategy | null; solver?: string; meaning?: string };
type Pay = { available: boolean; reason?: string; bands?: string[]; deployment_caveat?: string; observed_test_coverage: number };
const families = ['Data analyst', 'Data scientist', 'Data engineer', 'Data architect', 'Business analyst', 'Software', 'Operations', 'Other', 'All'];

export default function CareerLadder() {
    const [role, setRole] = useState('Data analyst');
    const [experience, setExperience] = useState('2');
    const [skills, setSkills] = useState('Python, SQL, Excel');
    const [completeOnly, setCompleteOnly] = useState(false);
    const key = JSON.stringify([role, experience, skills, completeOnly]);
    const query = useMutation({ mutationFn: async () => {
        if (isStaticMode()) throw new Error('The SAS workspace is private and available locally only. Public SAS records are not exported.');
        const payload = { role_family: role, experience: Number(experience), skills: skills.split(',').map(s => s.trim()).filter(Boolean), complete_only: completeOnly };
        const match = (await api.post<Match>('/sas/match', payload)).data;
        const plan = (await api.post<Plan>('/sas/plan', payload)).data;
        const pay = (await api.post<Pay>('/sas/pay-range', payload)).data;
        return { key, match, plan, pay };
    }});
    const current = query.data?.key === key ? query.data : undefined;
    return <div className="container pb-16">
        <PageIntro title="Career ladder" lead="Role requirements, skill priorities and compensation evidence from the supplied SAS datasets." />
        <div className="mb-8 flex flex-wrap items-center justify-between gap-3 border-y py-3 text-sm">
            <span className="flex items-center gap-2 font-medium"><LockKey size={17} /> SAS private workspace</span>
            <div className="flex flex-wrap gap-5"><Link href="/model-performance" className="flex items-center gap-2 text-primary hover:underline">Model performance <ChartBar size={16} /></Link><Link href="/student" className="flex items-center gap-2 text-primary hover:underline">Naukri / ESCO workspace <ArrowRight size={16} /></Link></div>
        </div>
        <div className="grid gap-8 lg:grid-cols-[280px_minmax(0,1fr)]">
            <aside className="lg:sticky lg:top-24 lg:self-start">
                <form className="space-y-5" onSubmit={e => { e.preventDefault(); query.mutate(); }}>
                    <h2 className="text-lg font-semibold">Your starting point</h2>
                    <label className="block text-sm font-medium" htmlFor="career-role">Role family
                        <select id="career-role" className="mt-2 w-full rounded-md border bg-background p-3" value={role} onChange={e => setRole(e.target.value)}>{families.map(f => <option key={f}>{f}</option>)}</select>
                    </label>
                    <label className="block text-sm font-medium" htmlFor="career-experience">Experience in years
                        <input id="career-experience" required type="number" min="0" max="40" step="0.5" value={experience} onChange={e => setExperience(e.target.value)} className="mt-2 w-full rounded-md border bg-background p-3" />
                    </label>
                    <label className="block text-sm font-medium" htmlFor="career-skills">Current skills, comma-separated
                        <textarea id="career-skills" maxLength={2000} rows={4} value={skills} onChange={e => setSkills(e.target.value)} className="mt-2 w-full resize-y rounded-md border bg-background p-3 font-normal" />
                    </label>
                    <label className="flex items-start gap-3 text-sm"><input type="checkbox" className="mt-1 accent-emerald-700" checked={completeOnly} onChange={e => setCompleteOnly(e.target.checked)} />Complete skill lists only</label>
                    <Button type="submit" className="w-full" disabled={query.isPending || experience === ''}>
                        {query.isPending ? <CircleNotch className="animate-spin" size={18} /> : <Path size={18} />} Analyze profile
                    </Button>
                </form>
                <p className="mt-6 border-t pt-4 text-xs leading-relaxed text-muted-foreground">Historical snapshot. Skill coverage is not a hiring probability. Salary units and pay period remain unverified.</p>
            </aside>
            <div className="min-w-0 space-y-8" aria-live="polite" aria-busy={query.isPending}>
                {query.isPending && <div className="space-y-4 py-10" role="status"><p className="text-sm">Comparing role requirements and learning priorities...</p>{[1, 2, 3].map(i => <div key={i} className="h-20 animate-pulse rounded-md bg-muted" />)}</div>}
                {query.error && <div role="alert" className="flex gap-3 rounded-md border border-red-200 bg-red-50 p-5 text-sm text-red-900"><WarningCircle size={22} className="shrink-0" /><p>{query.error.message}</p></div>}
                {!query.isPending && !current && !query.error && <div className="border-y py-16 text-center"><ChartBar size={40} className="mx-auto mb-5 text-primary" /><h2 className="text-xl font-semibold">A decision backed by evidence</h2><p className="mt-3 text-sm text-muted-foreground">{query.data ? 'Your inputs changed. Run the analysis again for current results.' : 'No profile analysis yet.'}</p></div>}
                {!query.isPending && current && <>
                    {current.match.vocabulary_evidence && <section className="border-b pb-5">
                        <h2 className="text-lg font-semibold">Evidence coverage</h2>
                        <p className="mt-2 text-sm">{current.match.vocabulary_evidence.observed_count} of {current.match.vocabulary_evidence.submitted} submitted skills appear in this posting pool.</p>
                        {!!current.match.vocabulary_evidence.unobserved.length && <p className="mt-2 break-words text-sm text-amber-800">Not observed: {current.match.vocabulary_evidence.unobserved.join(', ')}.</p>}
                        <p className="mt-2 text-xs text-muted-foreground">{current.match.vocabulary_evidence.meaning}</p>
                    </section>}
                    <section className="border-b pb-6">
                        <div className="flex flex-wrap items-baseline justify-between gap-3"><h2 className="text-xl font-semibold">Compensation evidence</h2><span className="font-mono text-xs text-muted-foreground">{current.match.support.toLocaleString()} comparable records</span></div>
                        {current.pay.available ? <><div className="my-5 flex flex-wrap gap-2">{current.pay.bands?.map(b => <span key={b} className="border-b-2 border-emerald-600 bg-emerald-50 px-4 py-3 font-mono text-lg text-emerald-950">{b.replace('to', ' to ')}</span>)}</div><p className="text-sm text-muted-foreground">Native salary bands. {current.pay.deployment_caveat}</p></> : <p className="mt-4 text-sm text-muted-foreground">{current.pay.reason}</p>}
                    </section>
                    <section>
                        <h2 className="mb-5 text-xl font-semibold">What to learn next</h2>
                        {current.plan.optimized && current.plan.frequency ? <div className="grid gap-6 sm:grid-cols-2">
                            {[{ title: 'Coverage-based plan', value: current.plan.optimized, accent: true }, { title: 'Frequency-based advice', value: current.plan.frequency, accent: false }].map(item => <div key={item.title} className={`border-t-2 pt-4 ${item.accent ? 'border-emerald-600' : 'border-amber-500'}`}>
                                <h3 className="font-medium">{item.title}</h3><p className="my-3 text-3xl font-semibold tabular-nums">{item.value.coverage}<span className="ml-2 text-sm font-normal text-muted-foreground">of {current.plan.support} records</span></p>
                                <p className="text-sm leading-relaxed">{item.value.skills.join(', ') || 'No additional skills needed for this pool.'}</p>
                            </div>)}
                        </div> : <p className="text-sm text-muted-foreground">No comparable records for these filters. Try another role or experience level.</p>}
                        {current.plan.optimized && <p className="mt-4 text-xs leading-relaxed text-muted-foreground">Starting coverage: {current.plan.before}. {current.plan.meaning} {current.plan.solver}; {current.plan.optimized.proven_optimal ? 'optimality proven for this instance' : 'optimality not proven'}.</p>}
                    </section>
                    <section className="border-t pt-6"><h2 className="mb-4 text-xl font-semibold">Observed role requirements</h2>
                        {!current.match.matches.length && <p className="text-sm text-muted-foreground">No records match the current filters.</p>}
                        <div className="divide-y">{current.match.matches.map(job => <article key={job.row_key} className="py-4">
                            <div className="flex items-start justify-between gap-4"><h3 className="min-w-0 break-words font-medium">{job.title}</h3><span className="shrink-0 font-mono text-sm text-primary">{Math.round(job.score * 100)}%</span></div>
                            <p className="mt-1 break-words text-xs text-muted-foreground">{job.location}{job.skills_truncated ? ' / truncated source skills' : ''}</p>
                            <p className="mt-3 break-words text-sm"><span className="text-emerald-700">Matched: </span>{job.matched.join(', ') || 'None'}</p>
                            <p className="mt-1 break-words text-sm"><span className="text-muted-foreground">Missing: </span>{job.missing.join(', ') || 'None observed'}</p>
                        </article>)}</div>
                    </section>
                    <section className="border-t pt-6"><h2 className="mb-2 text-xl font-semibold">Separate cohort research</h2><p className="mb-6 text-sm text-muted-foreground">These cohorts are not linked to you or the job postings. Associations do not establish causation.</p>
                        <div className="grid gap-8 md:grid-cols-2">{(['jds', 'sds'] as const).map(name => {
                            const cohort = current.match.research[name];
                            return <div key={name}><h3 className="font-medium">{name === 'jds' ? 'Junior technical skills' : 'Senior personality traits'}</h3>{cohort ? <><p className="my-2 text-xs text-muted-foreground">{cohort.n} observations / {cohort.groups} validation groups</p>
                                {cohort.features.map(f => <div key={f.feature} className="my-4"><div className="mb-1 flex justify-between gap-2 text-xs"><span className="break-words">{f.feature.replaceAll('_', ' ')}</span><span className="font-mono">{f.correlation.toFixed(2)}</span></div><div className="h-1.5 bg-muted"><div className={`h-full ${f.correlation >= 0 ? 'bg-emerald-600' : 'bg-amber-500'}`} style={{ width: `${Math.abs(f.correlation) * 100}%` }} /></div></div>)}
                                <p className="text-xs leading-relaxed text-muted-foreground">Point-biserial correlation with the recorded outcome. No individual employee scoring.</p></> : <p className="mt-3 text-sm text-muted-foreground">Research artifact unavailable.</p>}</div>;
                        })}</div>
                    </section>
                    <footer className="border-t pt-4 text-xs leading-relaxed text-muted-foreground"><p>Source {current.match.source_version} / model {current.match.model_id}</p>{current.match.limitations.map(l => <p key={l} className="mt-1">{l}</p>)}</footer>
                </>}
            </div>
        </div>
    </div>;
}
