'use client';

import Link from 'next/link';
import dynamic from 'next/dynamic';
import { motion } from 'motion/react';
import {
    ArrowRight, Briefcase, Buildings, ChartLineUp, GraduationCap, MapTrifold, Scales, ShieldCheck, Student, Translate,
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
        href: '/student', icon: Student, title: 'Students and job seekers',
        body: 'Describe your skills in your own language or upload a resume. See the roles and postings you fit, why, and the three skills that open the most jobs near you.',
    },
    {
        href: '/recruiter', icon: Briefcase, title: 'Recruiters',
        body: 'Paste a job description, correct the skills Yojak reads from it, and rank candidates by weighted skill coverage, with every match explained.',
    },
    {
        href: '/institution', icon: GraduationCap, title: 'Colleges and training institutes',
        body: 'Upload a syllabus and see how much of what employers in your region ask for it covers, which skills are missing, and which are rarely asked for right now.',
    },
    {
        href: '/workforce', icon: MapTrifold, title: 'Workforce planners',
        body: 'Where postings are, state by state and by skill family, set against where graduates come from. A clearly labelled proxy, with its caveats.',
    },
];

const STEPS = [
    { title: 'Postings', body: 'Naukri postings, cleaned, de-duplicated and dated' },
    { title: 'Places', body: 'Every location resolved to a city, state and HRA tier' },
    { title: 'Skills', body: 'Tags and titles linked to ESCO skills and occupations, with NCO-2015 families' },
    { title: 'Graph', body: 'Jobs, skills, occupations, companies and cities in Neo4j' },
    { title: 'Models', body: 'Six recommenders benchmarked on one leakage-free split' },
    { title: 'Answers', body: 'Four views, each with a "why" panel and a salary range' },
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
        <section className="relative">
            <div
                aria-hidden
                className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[680px] bg-[radial-gradient(60%_50%_at_70%_30%,hsl(var(--primary)/0.10),transparent_70%)]"
            />
            <div className="container grid items-center gap-10 pb-12 pt-12 md:pt-20 lg:grid-cols-[1fr_1.05fr] lg:gap-12">
                <motion.div
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6, ease }}
                    className="space-y-7"
                >
                    <p className="inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1 text-xs text-muted-foreground">
                        <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                        Build for Bharat 2.0 · Intelligent talent and workforce ecosystem
                    </p>
                    <h1 className="text-balance text-4xl font-semibold leading-[1.05] tracking-tight md:text-6xl">
                        Connect India&apos;s talent to India&apos;s jobs, <span className="text-primary">and show the working.</span>
                    </h1>
                    <p className="max-w-[56ch] text-base leading-relaxed text-muted-foreground md:text-lg">
                        Yojak (<span lang="hi">योजक</span>, &ldquo;the one who connects&rdquo;) links Indian job postings to the ESCO
                        skills taxonomy, ranks jobs and candidates with the model that won an honest benchmark, and plans the
                        smallest set of skills that opens the most jobs. Every answer comes with its reasons.
                    </p>
                    <div className="flex flex-wrap gap-3">
                        <Button asChild size="lg">
                            <Link href="/student">Find my matches <ArrowRight size={18} /></Link>
                        </Button>
                        <Button asChild size="lg" variant="outline">
                            <Link href="/evidence">See the evidence</Link>
                        </Button>
                    </div>
                    <p className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Translate size={16} /> Type skills in English, <span lang="hi">हिन्दी</span>, <span lang="pa">ਪੰਜਾਬੀ</span> or Hinglish.
                    </p>
                </motion.div>
                <motion.div
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.9, ease, delay: 0.1 }}
                    className="relative"
                >
                    <div className="relative h-[380px] overflow-hidden rounded-2xl border bg-card/60 shadow-[0_1px_0_0_hsl(var(--border)),0_30px_80px_-40px_hsl(var(--primary)/0.35)] backdrop-blur md:h-[520px]">
                        <Constellation className="h-full w-full" />
                    </div>
                    <p className="mt-3 text-xs text-muted-foreground">
                        The most-listed ESCO skills in the postings, joined when employers list them together far more often
                        than chance. Hover a node; scroll to zoom.
                    </p>
                </motion.div>
            </div>
        </section>
    );
}

function Figure({ value, label, source, loading }: { value: React.ReactNode; label: string; source: string; loading: boolean }) {
    return (
        <div className="space-y-1.5 border-l pl-4 first:border-l-0 first:pl-0 md:first:pl-0">
            <p className="tabular text-3xl font-semibold tracking-tight md:text-[34px]">
                {loading ? <span className="inline-block h-8 w-24 animate-pulse rounded bg-muted" /> : value}
            </p>
            <p className="text-sm text-foreground/80">{label}</p>
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
        <section className="border-y bg-muted/30">
            <div className="container space-y-10 py-14">
                <div className="flex flex-wrap items-end justify-between gap-4">
                    <div className="space-y-1.5">
                        <h2 className="text-xl font-semibold tracking-tight">Measured, not claimed</h2>
                        <p className="max-w-[62ch] text-sm text-muted-foreground">
                            These figures are read live from the reports the pipeline writes. Anything not yet measured says so.
                        </p>
                    </div>
                    <Link href="/evidence" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
                        All reports <ArrowRight size={14} />
                    </Link>
                </div>
                <div className="grid grid-cols-2 gap-y-8 md:grid-cols-4">
                    <Figure loading={dq.isLoading} value={d ? num(d.dataset.raw_rows) : '–'} label="Indian job postings analysed"
                            source="data_quality.json" />
                    <Figure loading={dq.isLoading} value={d ? num(d.geography.distinct_cities) : '–'}
                            label={d ? `cities across ${d.geography.distinct_states} states and UTs` : 'cities'} source="data_quality.json" />
                    <Figure loading={dq.isLoading} value={tier23 !== null ? pct(tier23) : '–'} label="of located postings are in Tier-2 and Tier-3 cities"
                            source="data_quality.json" />
                    <Figure loading={dq.isLoading} value={d ? num(d.title_linking.distinct_occupations_used) : '–'}
                            label="ESCO occupations the postings map to" source="data_quality.json" />
                </div>
                <div className="grid gap-4 md:grid-cols-3">
                    <Finding icon={<ChartLineUp size={20} />} title="Plans checked against the exact optimum" source="impact.json"
                             loading={imp.isLoading}>
                        {imp.data ? (
                            <>For Tier-2/3 freshers, Yojak&apos;s 3-skill plan reaches a median of{' '}
                                <b className="text-foreground">{num(imp.data.eligible_after_optimal_median)}</b> postings, against{' '}
                                <b className="text-foreground">{num(imp.data.eligible_after_frequency_median)}</b> for learning the three most
                                common skills ({pct(imp.data.share_users_with_more_postings)} of profiles gain).</>
                        ) : <Pending what="impact estimate not generated yet" />}
                    </Finding>
                    <Finding icon={<Scales size={20} />} title="The model that won is the one we ship" source="model_comparison.json"
                             loading={mc.isLoading}>
                        {winner && mc.data ? (
                            <><b className="text-foreground">{winner.name}</b> ranked first on unseen candidate-to-job matching
                                (NDCG@10 {winner.mean.t3?.['ndcg@10'].toFixed(3)}) among six models, including a graph transformer.
                                {mc.data.comparison.hgt_beats_best_baseline_on_t3 === false && ' The graph transformer did not beat it, and the report says so.'}</>
                        ) : <Pending what="benchmark not generated yet" />}
                    </Finding>
                    <Finding icon={<ShieldCheck size={20} />} title="Salary as a range, never a guess" source="salary_eval.json"
                             loading={sal.isLoading}>
                        {sal.data ? (
                            <>P10–P90 ranges hold <b className="text-foreground">{pct(sal.data.test.coverage_cqr)}</b> of held-out salaries
                                (target 80%). Only {pct(sal.data.selection_bias.disclosed_share)} of postings disclose pay, and we show
                                that bias rather than hide it.</>
                        ) : <Pending what="salary evaluation not generated yet" />}
                    </Finding>
                </div>
            </div>
        </section>
    );
}

function Finding({ icon, title, source, loading, children }: {
    icon: React.ReactNode; title: string; source: string; loading: boolean; children: React.ReactNode;
}) {
    return (
        <div className="flex flex-col rounded-xl border bg-card p-5">
            <div className="flex items-center gap-2.5 text-primary">{icon}<h3 className="text-sm font-semibold text-foreground">{title}</h3></div>
            <div className="mt-3 flex-1 text-sm leading-relaxed text-muted-foreground">
                {loading ? <span className="block h-12 animate-pulse rounded bg-muted" /> : children}
            </div>
            <p className="mt-4 font-mono text-[11px] text-muted-foreground">{source}</p>
        </div>
    );
}

function Views() {
    return (
        <section className="container space-y-8 py-20">
            <div className="max-w-[60ch] space-y-2">
                <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">One graph, four ways in</h2>
                <p className="text-muted-foreground">
                    The same postings, skills and models answer a different question for each side of the labour market.
                </p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
                {VIEWS.map((v, i) => (
                    <motion.div
                        key={v.href}
                        initial={{ opacity: 0, y: 16 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true, margin: '-60px' }}
                        transition={{ duration: 0.5, ease, delay: i * 0.06 }}
                    >
                        <Link
                            href={v.href}
                            className="group flex h-full flex-col rounded-2xl border bg-card p-6 transition-colors hover:border-primary/40 hover:bg-accent/40"
                        >
                            <div className="flex items-center justify-between">
                                <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-accent-foreground">
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
        </section>
    );
}

function HowItWorks() {
    return (
        <section className="border-t">
            <div className="container space-y-10 py-20">
                <div className="max-w-[60ch] space-y-2">
                    <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">From a posting to an answer</h2>
                    <p className="text-muted-foreground">One command rebuilds every step, and every step writes a report.</p>
                </div>
                <ol className="grid gap-px overflow-hidden rounded-2xl border bg-border sm:grid-cols-2 lg:grid-cols-6">
                    {STEPS.map((s, i) => (
                        <li key={s.title} className="relative bg-card p-5">
                            <span className="font-mono text-xs text-primary">{String(i + 1).padStart(2, '0')}</span>
                            <p className="mt-2 font-medium">{s.title}</p>
                            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
                        </li>
                    ))}
                </ol>
            </div>
        </section>
    );
}

function Honesty() {
    const items = [
        'The postings cover about two weeks of formal, mostly urban hiring. Yojak does not forecast demand.',
        'Being eligible (covering most of a posting\'s skills) is not the same as being hired.',
        'Recruiter demo candidates are synthetic, and every one is labelled SYNTHETIC.',
        'Graduate supply is a state-level proxy from AISHE and PLFS, not counts by field.',
        'Salary is what postings advertise, and most postings do not advertise it.',
    ];
    return (
        <section className="container py-10">
            <div className="grid gap-8 rounded-2xl border bg-card p-6 md:grid-cols-[1fr_1.4fr] md:p-10">
                <div className="space-y-3">
                    <Buildings size={28} className="text-primary" />
                    <h2 className="text-2xl font-semibold tracking-tight">What Yojak does not claim</h2>
                    <p className="text-sm text-muted-foreground">
                        Every limitation below is also written into the evaluation report and shown next to the numbers it affects.
                    </p>
                    <Link href="/evidence" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
                        Read the evaluation <ArrowRight size={14} />
                    </Link>
                </div>
                <ul className="space-y-3">
                    {items.map((t) => (
                        <li key={t} className="flex gap-3 text-[15px] leading-relaxed">
                            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-caution" />
                            {t}
                        </li>
                    ))}
                </ul>
            </div>
        </section>
    );
}
