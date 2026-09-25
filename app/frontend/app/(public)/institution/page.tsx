'use client';

import { useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { motion } from 'motion/react';
import { BookOpenText, CircleNotch, DownloadSimple, FileText, GraduationCap, Trash, UploadSimple } from '@phosphor-icons/react';
import { yojak, type CoverageItem, type InstitutionResult } from '@/services/yojak';
import { StateSelect, TierToggle } from '@/components/yojak/filters';
import { EmptyState, ErrorState, InfoHint, PageIntro, Panel, ProxyNote, ResultSkeleton, Section } from '@/components/yojak/bits';
import { Button } from '@/components/ui/button';
import { downloadCsv, ISCO2, num, pct, titleCase } from '@/lib/format';
import { cn } from '@/lib/utils';

const ease = [0.16, 1, 0.3, 1] as const;

export default function InstitutionPage() {
    const [text, setText] = useState('');
    const [file, setFile] = useState<File | null>(null);
    const [isco2, setIsco2] = useState('');
    const [field, setField] = useState('');
    const [tiers, setTiers] = useState<number[]>([]);
    const [state, setState] = useState('');
    const fileRef = useRef<HTMLInputElement>(null);
    const fields = useQuery({ queryKey: ['wf-fields'], queryFn: yojak.fields });

    const run = useMutation({
        mutationFn: () => yojak.institutionCoverage({
            text, file, isco2: isco2 || null, field: field || null, tiers, states: state ? [state] : [],
        }),
    });
    const canRun = (text.trim().length > 0 || file) && !run.isPending;

    return (
        <div className="container">
            <PageIntro
                title="How well does your syllabus match what employers ask for?"
                lead="Upload a syllabus or paste the course list. Yojak finds the ESCO skills it teaches and compares them with the skills listed most often by postings in the region and sector you choose."
            />
            <div className="grid gap-8 lg:grid-cols-[400px_1fr]">
                <aside className="space-y-6 lg:sticky lg:top-24 lg:self-start">
                    <Panel className="space-y-6">
                        <div className="space-y-1.5">
                            <label htmlFor="syllabus" className="text-sm font-semibold">1 · Syllabus</label>
                            <textarea
                                id="syllabus"
                                rows={7}
                                value={text}
                                onChange={(e) => setText(e.target.value)}
                                placeholder={'Unit 1: Programming in C\nUnit 2: Data structures\nUnit 3: Database management systems, SQL\n…'}
                                className="w-full resize-y rounded-md border border-input bg-card px-3 py-2 text-sm leading-relaxed placeholder:text-muted-foreground/80"
                            />
                            <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" className="sr-only"
                                   onChange={(e) => { setFile(e.target.files?.[0] ?? null); e.target.value = ''; }} />
                            {file ? (
                                <div className="flex items-center gap-2 rounded-md bg-muted/50 px-2.5 py-2 text-sm">
                                    <FileText size={16} className="text-muted-foreground" />
                                    <span className="truncate">{file.name}</span>
                                    <button type="button" onClick={() => setFile(null)} className="ml-auto rounded p-1 hover:bg-muted" aria-label="Remove file">
                                        <Trash size={14} />
                                    </button>
                                </div>
                            ) : (
                                <button type="button" onClick={() => fileRef.current?.click()}
                                        className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground hover:border-primary/50 hover:text-foreground">
                                    <UploadSimple size={18} /> Upload syllabus (PDF, DOCX or text)
                                </button>
                            )}
                            <p className="text-xs text-muted-foreground">Read in memory, not stored.</p>
                        </div>
                        <div className="space-y-4 border-t pt-5">
                            <p className="text-sm font-semibold">2 · Compare with postings for</p>
                            <div className="space-y-1.5">
                                <label htmlFor="isco" className="text-sm font-medium">Occupation group</label>
                                <select id="isco" value={isco2} onChange={(e) => setIsco2(e.target.value)}
                                        className="h-10 w-full rounded-md border border-input bg-card px-3 text-sm">
                                    <option value="">All occupations</option>
                                    {Object.entries(ISCO2).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                                </select>
                            </div>
                            <div className="space-y-1.5">
                                <label htmlFor="field" className="flex items-center gap-1.5 text-sm font-medium">
                                    Skill family <InfoHint text="ISCED-F broad field of education, assigned to each posting from the ESCO knowledge its skills belong to." />
                                </label>
                                <select id="field" value={field} onChange={(e) => setField(e.target.value)}
                                        className="h-10 w-full rounded-md border border-input bg-card px-3 text-sm">
                                    <option value="">All families</option>
                                    {fields.data?.fields.filter((f) => f.field !== 'unassigned').map((f) => (
                                        <option key={f.field} value={f.field}>{titleCase(f.field)}</option>
                                    ))}
                                </select>
                            </div>
                            <TierToggle value={tiers} onChange={setTiers} />
                            <StateSelect value={state} onChange={setState} />
                        </div>
                        <Button size="lg" className="w-full" disabled={!canRun} onClick={() => run.mutate()}>
                            {run.isPending ? <CircleNotch size={18} className="animate-spin" /> : <BookOpenText size={18} />}
                            Check coverage
                        </Button>
                    </Panel>
                </aside>
                <section className="min-w-0 space-y-6" aria-live="polite">
                    {!run.data && !run.isPending && !run.error && (
                        <EmptyState icon={<GraduationCap size={40} weight="light" />} title="The coverage report will appear here">
                            Paste a few units of a course, or upload the full syllabus PDF, then choose which postings to compare with.
                        </EmptyState>
                    )}
                    {run.error && <ErrorState error={run.error} onRetry={() => run.mutate()} />}
                    {run.isPending && <ResultSkeleton rows={4} />}
                    {run.data && !run.isPending && <Report data={run.data} />}
                </section>
            </div>
        </div>
    );
}

function Ring({ value }: { value: number }) {
    const r = 52, c = 2 * Math.PI * r;
    return (
        <div className="relative h-36 w-36 shrink-0">
            <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
                <circle cx="60" cy="60" r={r} fill="none" strokeWidth="10" className="stroke-muted" />
                <motion.circle
                    cx="60" cy="60" r={r} fill="none" strokeWidth="10" strokeLinecap="round" className="stroke-primary"
                    strokeDasharray={c}
                    initial={{ strokeDashoffset: c }}
                    animate={{ strokeDashoffset: c * (1 - value) }}
                    transition={{ duration: 1.1, ease }}
                />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="tabular text-3xl font-semibold tracking-tight">{pct(value)}</span>
                <span className="text-[11px] text-muted-foreground">of demand covered</span>
            </div>
        </div>
    );
}

function Report({ data }: { data: InstitutionResult }) {
    const exportCsv = () => downloadCsv('yojak-syllabus-coverage.csv', [
        ...data.covered.map((c) => row(c, 'covered')),
        ...data.missing_high_demand.map((c) => row(c, 'missing, high demand')),
        ...data.low_current_demand.map((c) => row(c, 'taught, low current demand')),
    ]);
    const maxShare = Math.max(1e-6, ...data.missing_high_demand.map((m) => m.demand_share), ...data.covered.map((m) => m.demand_share));
    return (
        <div className="space-y-6">
            <Panel className="flex flex-col items-center gap-6 sm:flex-row sm:items-center">
                <Ring value={data.coverage} />
                <div className="space-y-2">
                    <p className="text-lg font-semibold tracking-tight">
                        The syllabus covers {data.covered.length} of the {data.scope.top_n} skills most listed by {num(data.scope.postings)} postings in scope.
                    </p>
                    <p className="text-sm text-muted-foreground">
                        Coverage is weighted by demand: a skill listed by many postings counts more. Yojak found{' '}
                        {data.syllabus_skills.length} ESCO skills in the syllabus.
                    </p>
                    <Button variant="outline" size="sm" onClick={exportCsv}>
                        <DownloadSimple size={16} /> Export CSV
                    </Button>
                </div>
            </Panel>

            <Section title="Most-demanded skills the syllabus does not teach" description="Ordered by the share of in-scope postings that list them.">
                {data.missing_high_demand.length === 0 ? (
                    <p className="text-sm text-muted-foreground">None: every top skill is covered.</p>
                ) : <Bars items={data.missing_high_demand.slice(0, 15)} max={maxShare} tone="gap" />}
            </Section>

            <Section title="In-demand skills it already covers">
                {data.covered.length === 0 ? (
                    <p className="text-sm text-muted-foreground">None of the top skills were found in the syllabus text.</p>
                ) : <Bars items={data.covered} max={maxShare} tone="have" />}
            </Section>

            {data.low_current_demand.length > 0 && (
                <Section title="Taught, but rarely asked for in current postings">
                    <ProxyNote title="A snapshot, not a verdict">
                        These postings cover about two weeks. &ldquo;Rarely asked for&rdquo; means fewer than 0.2% of in-scope postings list
                        the skill right now; it does not mean the skill is outdated or should be dropped.
                    </ProxyNote>
                    <div className="flex flex-wrap gap-1.5">
                        {data.low_current_demand.map((c) => (
                            <span key={c.skill.uri} className="rounded-md border px-2 py-1 text-[13px] text-muted-foreground">
                                {c.skill.label} <span className="tabular text-xs">· {num(c.demand_postings)}</span>
                            </span>
                        ))}
                    </div>
                </Section>
            )}
            <div className="space-y-1 text-xs text-muted-foreground">{data.notes.map((n) => <p key={n}>{n}</p>)}</div>
        </div>
    );
}

function row(c: CoverageItem, status: string) {
    return { skill: c.skill.label, esco_uri: c.skill.uri, status, postings: c.demand_postings, share_of_postings: c.demand_share };
}

function Bars({ items, max, tone }: { items: CoverageItem[]; max: number; tone: 'have' | 'gap' }) {
    return (
        <ul className="space-y-2 rounded-xl border bg-card p-4">
            {items.map((c, i) => (
                <li key={c.skill.uri} className="grid grid-cols-[minmax(0,1fr)_minmax(80px,40%)_56px] items-center gap-3 text-sm">
                    <span className="truncate" title={c.skill.label}>{c.skill.label}</span>
                    <span className="h-2 overflow-hidden rounded-full bg-muted">
                        <motion.span
                            className={cn('block h-full rounded-full', tone === 'have' ? 'bg-primary' : 'bg-caution')}
                            initial={{ width: 0 }}
                            animate={{ width: `${(c.demand_share / max) * 100}%` }}
                            transition={{ duration: 0.6, ease, delay: i * 0.02 }}
                        />
                    </span>
                    <span className="tabular text-right text-xs text-muted-foreground">{pct(c.demand_share, 1)}</span>
                </li>
            ))}
        </ul>
    );
}
