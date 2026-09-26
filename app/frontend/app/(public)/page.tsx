'use client';

import Link from 'next/link';
import dynamic from 'next/dynamic';
import { motion } from 'motion/react';
import { useState } from 'react';
import {
    ArrowRight, ArrowUpRight, Briefcase, ChartLineUp, GraduationCap, MapTrifold, Scales, ShieldCheck, Student, Graph, Database, Path,
} from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { Pending } from '@/components/yojak/bits';
import {
    useReport, type DataQualityReport, type ImpactReport, type ModelComparisonReport, type SalaryReport,
} from '@/hooks/use-report';
import { num, pct } from '@/lib/format';

const Constellation = dynamic(() => import('@/components/yojak/constellation').then((m) => m.Constellation), { ssr: false });

const ease = [0.16, 1, 0.3, 1] as const;

const VIEWS = [
    {
        href: '/student', icon: Student, title: 'Students',
        body: 'Match your skills to roles, see gaps, and compare focused learning plans.',
    },
    {
        href: '/recruiter', icon: Briefcase, title: 'Recruiters',
        body: 'Rank profiles against a job description with visible matched and missing skills.',
    },
    {
        href: '/institution', icon: GraduationCap, title: 'Institutions',
        body: 'Compare a syllabus with regional demand and export the curriculum gaps.',
    },
    {
        href: '/workforce', icon: MapTrifold, title: 'Workforce',
        body: 'Inspect demand, supply proxies, cities, tiers, and state-level shortages.',
    },
];

const PIPELINE = [
    { title: 'Clean postings', body: 'Deduplicate jobs, parse salary, experience, locations, and skill tags.' },
    { title: 'Link skills', body: 'Map titles and tags to ESCO skills, occupations, and NCO families.' },
    { title: 'Score fit', body: 'Rank jobs, candidates, curricula, and regions with the same skill graph.' },
    { title: 'Show proof', body: 'Expose salary support, model choice, extraction paths, and report status.' },
];

export default function LandingPage() {
    return (
        <div className="overflow-x-clip">
            <Hero />
            <Views />
            <Evidence />
            <HowItWorks />
            <Honesty />
        </div>
    );
}

function Hero() {
    const [workspace, setWorkspace] = useState(0);
    const actions = ['Find my career matches', 'Discover the right talent', 'Evaluate a curriculum', 'Explore workforce demand'];
    return (
        <section className="relative border-b bg-card">
            <div className="container relative min-h-[650px] md:min-h-[570px] lg:min-h-[600px]">
                <div className="hero-scene" aria-label="Skill relationships">
                    <Constellation className="h-full w-full" />
                </div>
                <motion.div
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.45, ease }}
                    className="relative z-10 w-full space-y-4 pb-[320px] pt-8 md:w-[40%] md:space-y-5 md:pb-12 md:pt-16 lg:pt-20"
                >
                    <p className="flex items-center gap-2 text-xs font-medium uppercase text-muted-foreground"><Graph size={16} className="text-primary" />Talent &amp; workforce intelligence</p>
                    <h1 className="text-[48px] font-semibold leading-none md:text-[72px]">Yojak<span className="text-primary">.</span></h1>
                    <h2 className="max-w-[360px] text-[25px] font-medium leading-[1.25] md:text-[30px]">Connect what you know to what comes next.</h2>
                    <p className="max-w-[40ch] text-sm leading-relaxed text-muted-foreground">
                        Find your fit in India&apos;s workforce. Turn skill gaps into focused learning plans and better decisions.
                    </p>
                    <div className="flex w-fit max-w-full gap-0.5 rounded-md border bg-background p-1" aria-label="Choose your workspace">
                        {VIEWS.map((view, i) => <button key={view.href} onClick={() => setWorkspace(i)} aria-label={view.title} aria-pressed={workspace === i} title={view.title}
                            className={`flex h-9 items-center gap-1.5 rounded px-2 text-xs font-medium transition-colors ${workspace === i ? 'bg-foreground text-background' : 'text-muted-foreground hover:bg-muted'}`}>
                            <view.icon size={15} /><span className="hidden xl:inline">{view.title}</span><span className="md:hidden">{['Career', 'Talent', 'Study', 'Plan'][i]}</span>
                        </button>)}
                    </div>
                    <Button asChild size="lg" className="max-w-full px-4"><Link href={VIEWS[workspace].href}>{actions[workspace]} <ArrowRight size={17} /></Link></Button>
                    <Link href="/evidence" className="flex w-fit items-center gap-2 text-xs font-medium text-muted-foreground hover:text-primary"><ShieldCheck size={16} />Explore the evidence <ArrowUpRight size={13} /></Link>
                </motion.div>
            </div>
        </section>
    );
}

function Figure({ value, label, source, loading }: { value: React.ReactNode; label: string; source: string; loading: boolean }) {
    return (
        <div className="space-y-2">
            <p className="tabular text-4xl font-semibold tracking-tight">
                {loading ? <span className="inline-block h-9 w-24 animate-pulse rounded bg-muted" /> : value}
            </p>
            <p className="max-w-[18rem] text-sm leading-relaxed text-foreground/80">{label}</p>
            <Link href="/evidence" className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-primary" title={source}>Source &amp; methodology <ArrowUpRight size={12} /></Link>
        </div>
    );
}

function Evidence() {
    const dq = useReport<DataQualityReport>('data_quality');
    const mc = useReport<ModelComparisonReport>('model_comparison');
    const sal = useReport<SalaryReport>('salary_eval');
    const imp = useReport<ImpactReport>('impact');
    const d = dq.data;
    const tiers = d?.geography.jobs_by_primary_tier ?? {};
    const t = (k: string) => tiers[k] ?? tiers[`${k}.0`] ?? 0;
    const tier23 = d ? (t('2') + t('3')) / Math.max(1, t('1') + t('2') + t('3')) : null;
    const winner = mc.data?.comparison?.winner ? mc.data.models[mc.data.comparison.winner] : null;

    return (
        <section className="bg-muted/35">
            <div className="container space-y-10 py-16">
                <div className="max-w-[62ch] space-y-3">
                    <p className="text-xs font-medium uppercase text-primary">Measured, not assumed</p>
                    <h2 className="text-[28px] font-semibold">Evidence behind every decision.</h2>
                    <p className="text-muted-foreground">
                        Real posting data, evaluated models, and visible uncertainty. Explore the results and the limits of what they can tell us.
                    </p>
                </div>
                <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
                    <Figure loading={dq.isLoading} value={d ? num(d.dataset.raw_rows) : '-'} label="Indian job postings analysed"
                            source="data_quality.json" />
                    <Figure loading={dq.isLoading} value={d ? num(d.geography.distinct_cities) : '-'}
                            label={d ? `cities across ${d.geography.distinct_states} states and UTs` : 'cities'} source="data_quality.json" />
                    <Figure loading={dq.isLoading} value={tier23 !== null ? pct(tier23) : '-'} label="of located postings are in Tier 2 and Tier 3 cities"
                            source="data_quality.json" />
                    <Figure loading={dq.isLoading} value={d ? num(d.title_linking.distinct_occupations_used) : '-'}
                            label="ESCO occupations the postings map to" source="data_quality.json" />
                </div>
                <div className="grid gap-4 lg:grid-cols-[1.12fr_0.88fr]">
                    <Finding icon={<ChartLineUp size={22} />} title="Learn fewer skills. Reach more opportunities." source="impact.json"
                             loading={imp.isLoading}>
                        {imp.data ? (
                            <>For Tier 2 and Tier 3 freshers, the 3-skill plan reaches a median of{' '}
                                <b className="text-foreground">{num(imp.data.eligible_after_optimal_median)}</b> postings, compared with{' '}
                                <b className="text-foreground">{num(imp.data.eligible_after_frequency_median)}</b> for the common-skills baseline.</>
                        ) : <Pending what="impact estimate not generated yet" />}
                    </Finding>
                    <div className="grid gap-4">
                        <Finding icon={<Scales size={22} />} title="Matching, backed by evaluation" source="model_comparison.json"
                                 loading={mc.isLoading}>
                            {winner && mc.data ? (
                                <><b className="text-foreground">{winner.name}</b> ranks first on unseen matching, with NDCG@10{' '}
                                    {winner.mean.t3?.['ndcg@10'].toFixed(3)}.</>
                            ) : <Pending what="benchmark not generated yet" />}
                        </Finding>
                        <Finding icon={<ShieldCheck size={22} />} title="Salary remains a range" source="salary_eval.json"
                                 loading={sal.isLoading}>
                            {sal.data ? (
                                <>P10 to P90 ranges cover <b className="text-foreground">{pct(sal.data.test.coverage_cqr)}</b> of held-out salaries.
                                    Disclosure bias is shown with every result.</>
                            ) : <Pending what="salary evaluation not generated yet" />}
                        </Finding>
                    </div>
                </div>
                <Link href="/evidence" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
                    Open the full evidence view <ArrowRight size={14} />
                </Link>
            </div>
        </section>
    );
}

function Finding({ icon, title, source, loading, children }: {
    icon: React.ReactNode; title: string; source: string; loading: boolean; children: React.ReactNode;
}) {
    return (
        <div className="flex h-full flex-col rounded-lg border bg-card p-5">
            <div className="flex items-center gap-3 text-primary">
                {icon}
                <h3 className="text-base font-semibold text-foreground">{title}</h3>
            </div>
            <div className="mt-4 flex-1 text-sm leading-relaxed text-muted-foreground">
                {loading ? <span className="block h-12 animate-pulse rounded bg-muted" /> : children}
            </div>
            <Link href="/evidence" className="mt-5 inline-flex w-fit items-center gap-1 text-[11px] text-muted-foreground hover:text-primary" title={source}>View evaluation <ArrowUpRight size={12} /></Link>
        </div>
    );
}

function Views() {
    return (
        <section className="container py-8 md:py-16">
            <div className="grid gap-8 lg:grid-cols-[0.78fr_1.22fr]">
                <div className="max-w-[48ch] space-y-3">
                    <p className="text-xs font-medium uppercase text-primary">Your workspace</p>
                    <h2 className="text-[28px] font-semibold leading-tight">A clearer next step.<br />For every stakeholder.</h2>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                        Career decisions, hiring, curriculum alignment, and workforce planning share one foundation: the skills that connect people to opportunities.
                    </p>
                    <Link href="/network" className="inline-flex items-center gap-2 pt-3 text-sm font-medium text-primary">Explore skill intelligence <ArrowUpRight size={16} /></Link>
                </div>
                <div className="grid gap-x-8 sm:grid-cols-2">
                    {VIEWS.map((v, i) => (
                        <motion.div
                            key={v.href}
                            initial={{ opacity: 0, y: 12 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true, margin: '-60px' }}
                            transition={{ duration: 0.35, ease, delay: i * 0.04 }}
                        >
                            <Link
                                href={v.href}
                                className="group flex min-h-36 flex-col border-b py-5 transition-colors hover:text-primary"
                            >
                                <div className="flex items-center justify-between">
                                    <span className={`flex h-9 w-9 items-center justify-center rounded-md ${['bg-emerald-100 text-emerald-800', 'bg-blue-100 text-blue-800', 'bg-amber-100 text-amber-800', 'bg-rose-100 text-rose-800'][i]}`}>
                                        <v.icon size={22} />
                                    </span>
                                    <ArrowRight size={18} className="text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary" />
                                </div>
                                <h3 className="mt-3 text-base font-semibold">{v.title}</h3>
                                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{v.body}</p>
                            </Link>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}

function HowItWorks() {
    return (
        <section className="border-y">
            <div className="container grid gap-10 py-20 lg:grid-cols-[1fr_1.5fr]">
                <div className="max-w-[45ch] space-y-3">
                    <Database size={24} className="text-primary" />
                    <h2 className="text-[28px] font-semibold">From data to a decision.</h2>
                    <p className="text-muted-foreground">
                        The pipeline is built for auditability. Each step can be rerun and checked against its report.
                    </p>
                </div>
                <div className="grid gap-x-8 gap-y-6 sm:grid-cols-2">
                    {PIPELINE.map((s) => (
                        <div key={s.title} className="border-t pt-5">
                            <p className="font-semibold">{s.title}</p>
                            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}

function Honesty() {
    const items = [
        'The postings are a historical snapshot, not a live jobs feed.',
        'Skill coverage supports decisions. It does not predict hiring.',
        'Recruiter demo candidates are synthetic and clearly labelled.',
        'Graduate supply is a state-level proxy from public sources.',
        'Posted salary is shown only as a supported range.',
    ];
    return (
        <section className="container py-16">
            <div className="grid gap-8 md:grid-cols-[1fr_1.35fr]">
                <div className="space-y-4">
                    <Path size={26} className="text-primary" />
                    <h2 className="text-[28px] font-semibold">Useful evidence.<br />Honest boundaries.</h2>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                        Limitations are part of the interface, because a planning tool should say where its evidence ends.
                    </p>
                    <Link href="/evidence" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
                        Read the limitations <ArrowRight size={14} />
                    </Link>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                    {items.map((t) => (
                        <div key={t} className="flex items-start gap-3 border-t py-4 text-sm leading-relaxed text-muted-foreground">
                            <ShieldCheck size={17} className="mt-0.5 shrink-0 text-primary" />
                            {t}
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
