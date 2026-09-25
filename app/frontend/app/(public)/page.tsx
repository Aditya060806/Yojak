'use client';

import Link from 'next/link';
import dynamic from 'next/dynamic';
import { motion } from 'motion/react';
import {
    ArrowRight, Briefcase, Buildings, ChartLineUp, GraduationCap, MapTrifold, Scales, ShieldCheck, Student,
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
            <Evidence />
            <Views />
            <HowItWorks />
            <Honesty />
        </div>
    );
}

function Hero() {
    return (
        <section className="relative border-b">
            <div className="container grid min-h-[calc(100dvh-4rem)] items-center gap-8 py-10 lg:grid-cols-[0.92fr_1.08fr] lg:py-12">
                <motion.div
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.45, ease }}
                    className="space-y-6"
                >
                    <p className="text-sm font-medium text-primary">Yojak for India&apos;s skill market</p>
                    <h1 className="max-w-[12ch] text-balance text-5xl font-semibold leading-[0.98] tracking-tight md:text-6xl">
                        Find the job fit. See the evidence.
                    </h1>
                    <p className="max-w-[50ch] text-base leading-relaxed text-muted-foreground">
                        Skill matching, upskilling plans, salary ranges, and workforce signals from one transparent graph.
                    </p>
                    <div className="flex flex-wrap gap-3">
                        <Button asChild size="lg">
                            <Link href="/student">Start matching <ArrowRight size={18} /></Link>
                        </Button>
                        <Button asChild size="lg" variant="outline">
                            <Link href="/evidence">View evidence</Link>
                        </Button>
                    </div>
                </motion.div>
                <motion.div
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.55, ease, delay: 0.06 }}
                    className="relative"
                >
                    <div className="overflow-hidden rounded-2xl border bg-card shadow-[0_24px_80px_-50px_hsl(var(--primary)/0.45)]">
                        <div className="h-[340px] md:h-[500px]">
                            <Constellation className="h-full w-full" />
                        </div>
                        <div className="grid gap-px border-t bg-border sm:grid-cols-3">
                            <HeroStat label="Skills graph" value="ESCO" />
                            <HeroStat label="Primary market" value="India" />
                            <HeroStat label="Mode" value="Evidence first" />
                        </div>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}

function HeroStat({ label, value }: { label: string; value: string }) {
    return (
        <div className="bg-card px-4 py-3">
            <p className="text-[11px] text-muted-foreground">{label}</p>
            <p className="mt-1 text-sm font-medium">{value}</p>
        </div>
    );
}

function Figure({ value, label, source, loading }: { value: React.ReactNode; label: string; source: string; loading: boolean }) {
    return (
        <div className="space-y-2">
            <p className="tabular text-4xl font-semibold tracking-tight">
                {loading ? <span className="inline-block h-9 w-24 animate-pulse rounded bg-muted" /> : value}
            </p>
            <p className="max-w-[18rem] text-sm leading-relaxed text-foreground/80">{label}</p>
            <p className="font-mono text-[11px] text-muted-foreground">{source}</p>
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
                    <h2 className="text-3xl font-semibold tracking-tight">Numbers with receipts</h2>
                    <p className="text-muted-foreground">
                        The site reads generated reports. Missing evidence stays visibly pending instead of turning into marketing copy.
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
                    <Finding icon={<ChartLineUp size={22} />} title="Plans are compared with exact optimization" source="impact.json"
                             loading={imp.isLoading}>
                        {imp.data ? (
                            <>For Tier 2 and Tier 3 freshers, the 3-skill plan reaches a median of{' '}
                                <b className="text-foreground">{num(imp.data.eligible_after_optimal_median)}</b> postings, compared with{' '}
                                <b className="text-foreground">{num(imp.data.eligible_after_frequency_median)}</b> for the common-skills baseline.</>
                        ) : <Pending what="impact estimate not generated yet" />}
                    </Finding>
                    <div className="grid gap-4">
                        <Finding icon={<Scales size={22} />} title="The served ranker is disclosed" source="model_comparison.json"
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
        <div className="flex h-full flex-col rounded-2xl border bg-card p-5">
            <div className="flex items-center gap-3 text-primary">
                {icon}
                <h3 className="text-base font-semibold text-foreground">{title}</h3>
            </div>
            <div className="mt-4 flex-1 text-sm leading-relaxed text-muted-foreground">
                {loading ? <span className="block h-12 animate-pulse rounded bg-muted" /> : children}
            </div>
            <p className="mt-5 font-mono text-[11px] text-muted-foreground">{source}</p>
        </div>
    );
}

function Views() {
    return (
        <section className="container py-20">
            <div className="grid gap-10 lg:grid-cols-[0.78fr_1.22fr]">
                <div className="max-w-[48ch] space-y-3">
                    <h2 className="text-3xl font-semibold tracking-tight">Four workspaces, one vocabulary</h2>
                    <p className="text-muted-foreground">
                        Students, recruiters, institutions, and planners ask different questions. Yojak keeps the skill evidence consistent.
                    </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
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
                                className="group flex min-h-44 flex-col rounded-2xl border bg-card p-5 transition-colors hover:border-primary/35 hover:bg-accent/45"
                            >
                                <div className="flex items-center justify-between">
                                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                                        <v.icon size={22} />
                                    </span>
                                    <ArrowRight size={18} className="text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary" />
                                </div>
                                <h3 className="mt-5 text-lg font-semibold tracking-tight">{v.title}</h3>
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
                    <h2 className="text-3xl font-semibold tracking-tight">From posting to answer</h2>
                    <p className="text-muted-foreground">
                        The pipeline is built for auditability. Each step can be rerun and checked against its report.
                    </p>
                </div>
                <div className="grid gap-px overflow-hidden rounded-2xl border bg-border sm:grid-cols-2">
                    {PIPELINE.map((s) => (
                        <div key={s.title} className="bg-card p-6">
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
            <div className="grid gap-8 rounded-2xl border bg-card p-6 md:grid-cols-[1fr_1.35fr] md:p-10">
                <div className="space-y-4">
                    <Buildings size={30} className="text-primary" />
                    <h2 className="text-3xl font-semibold tracking-tight">What Yojak does not claim</h2>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                        Limitations are part of the interface, because a planning tool should say where its evidence ends.
                    </p>
                    <Link href="/evidence" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
                        Read the limitations <ArrowRight size={14} />
                    </Link>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                    {items.map((t) => (
                        <div key={t} className="rounded-xl border bg-background p-4 text-sm leading-relaxed text-muted-foreground">
                            {t}
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
