'use client';

import { useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { motion } from 'motion/react';
import { CircleNotch, FileText, MagnifyingGlass, Trash, UploadSimple, UsersThree } from '@phosphor-icons/react';
import { yojak, type Candidate, type RecruiterResult, type SkillRef } from '@/services/yojak';
import { SkillInput } from '@/components/yojak/skill-input';
import {
    EmptyState, ErrorState, Hint, PageIntro, Panel, ProxyNote, ResultSkeleton, SkillChip, SyntheticBadge, WhyDrawer,
} from '@/components/yojak/bits';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EXP_LABEL, pct, TIER_LABEL } from '@/lib/format';
import { cn } from '@/lib/utils';

const MAX_RESUMES = 20;

export default function RecruiterPage() {
    const [skills, setSkills] = useState<SkillRef[]>([]);
    const [resumes, setResumes] = useState<File[]>([]);
    const [synthetic, setSynthetic] = useState(true);
    const fileRef = useRef<HTMLInputElement>(null);

    const rank = useMutation({
        mutationFn: () => yojak.recruiterRank('', skills.map((s) => s.uri), resumes, synthetic),
    });
    const canRun = skills.length > 0 && (synthetic || resumes.length > 0);

    return (
        <div className="container">
            <PageIntro
                title="Rank candidates by the skills the job actually needs"
                lead="Paste a job description or upload it. Yojak reads the ESCO skills in it; you correct the list. Candidates are ranked by how much of that list they cover, with rarer skills counting more, and every rank can be explained."
            />
            <div className="grid gap-8 lg:grid-cols-[400px_1fr]">
                <aside className="space-y-6 lg:sticky lg:top-24 lg:self-start">
                    <Panel className="space-y-6">
                        <div className="space-y-1">
                            <h2 className="text-sm font-semibold">1 · Skills the job needs</h2>
                            <p className="text-xs text-muted-foreground">Remove anything that was misread; add what is missing.</p>
                        </div>
                        <SkillInput
                            value={skills}
                            onChange={setSkills}
                            placeholder="Search ESCO skills, e.g. SQL"
                            textLabel="Paste the job description"
                            fileLabel="Upload a JD"
                            textPlaceholder="We are hiring a data analyst in Indore with SQL, Excel and Power BI, and good communication skills…"
                            emptyLabel="The job's skills will appear here"
                            textRows={5}
                        />
                        <div className="space-y-3 border-t pt-5">
                            <h2 className="text-sm font-semibold">2 · Candidates</h2>
                            <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm">
                                <input type="checkbox" checked={synthetic} onChange={(e) => setSynthetic(e.target.checked)}
                                       className="mt-0.5 h-4 w-4 accent-[hsl(var(--primary))]" />
                                <span>
                                    <span className="font-medium">Include the synthetic demo pool</span>
                                    <span className="mt-0.5 block text-xs text-muted-foreground">
                                        Generated profiles, not real people. Each is labelled <b>SYNTHETIC</b>.
                                    </span>
                                </span>
                            </label>
                            <input
                                ref={fileRef}
                                type="file"
                                multiple
                                accept=".pdf,.docx,.txt"
                                className="sr-only"
                                onChange={(e) => {
                                    const files = Array.from(e.target.files ?? []);
                                    setResumes((r) => [...r, ...files].slice(0, MAX_RESUMES));
                                    e.target.value = '';
                                }}
                            />
                            <button
                                type="button"
                                onClick={() => fileRef.current?.click()}
                                className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed px-3 py-4 text-sm text-muted-foreground hover:border-primary/50 hover:text-foreground"
                            >
                                <UploadSimple size={18} /> Add resumes (PDF, DOCX, text; up to {MAX_RESUMES})
                            </button>
                            {resumes.length > 0 && (
                                <ul className="space-y-1">
                                    {resumes.map((f, i) => (
                                        <li key={`${f.name}-${i}`} className="flex items-center gap-2 rounded-md bg-muted/50 px-2.5 py-1.5 text-sm">
                                            <FileText size={16} className="shrink-0 text-muted-foreground" />
                                            <span className="truncate">{f.name}</span>
                                            <button type="button" className="ml-auto rounded p-1 hover:bg-muted" aria-label={`Remove ${f.name}`}
                                                    onClick={() => setResumes((r) => r.filter((_, j) => j !== i))}>
                                                <Trash size={14} />
                                            </button>
                                        </li>
                                    ))}
                                </ul>
                            )}
                            <p className="text-xs text-muted-foreground">Resumes are read in memory to find skills and are never stored.</p>
                        </div>
                        <Button size="lg" className="w-full" disabled={!canRun || rank.isPending} onClick={() => rank.mutate()}>
                            {rank.isPending ? <CircleNotch size={18} className="animate-spin" /> : <MagnifyingGlass size={18} />}
                            Rank candidates
                        </Button>
                    </Panel>
                </aside>
                <section className="min-w-0 space-y-5" aria-live="polite">
                    {!rank.data && !rank.isPending && !rank.error && (
                        <EmptyState icon={<UsersThree size={40} weight="light" />} title="Ranked candidates will appear here">
                            Add the job&apos;s skills, then rank the synthetic demo pool, your uploaded resumes, or both.
                        </EmptyState>
                    )}
                    {rank.error && <ErrorState error={rank.error} onRetry={() => rank.mutate()} />}
                    {rank.isPending && <ResultSkeleton rows={6} />}
                    {rank.data && !rank.isPending && <Results data={rank.data} />}
                </section>
            </div>
        </div>
    );
}

function Results({ data }: { data: RecruiterResult }) {
    const top = data.candidates[0]?.score ?? 1;
    return (
        <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-muted-foreground">
                    Ranked {data.pool.synthetic + data.pool.uploaded} candidates
                    {data.pool.synthetic > 0 && <> ({data.pool.synthetic} synthetic</>}
                    {data.pool.uploaded > 0 && <>{data.pool.synthetic > 0 ? ', ' : ' ('}{data.pool.uploaded} uploaded</>}
                    {(data.pool.synthetic > 0 || data.pool.uploaded > 0) && ')'} against {data.jd_skills.length} skills
                </p>
            </div>
            {data.pool.synthetic > 0 && (
                <ProxyNote title="Synthetic candidates">
                    The demo pool is generated from ESCO occupation profiles and Indian posting patterns so ranking can be shown
                    without real people&apos;s data. Scores for these profiles say nothing about real candidates.
                </ProxyNote>
            )}
            <div className="overflow-hidden rounded-xl border bg-card">
                <div className="hidden grid-cols-[48px_1.4fr_1fr_160px_110px] gap-4 border-b bg-muted/40 px-4 py-2.5 text-xs font-medium text-muted-foreground md:grid">
                    <span>#</span><span>Candidate</span><span>Profile</span><span>Skill coverage</span><span className="text-right">Details</span>
                </div>
                <ol>
                    {data.candidates.map((c, i) => <Row key={c.candidate_id} c={c} rank={i + 1} top={top} jd={data.jd_skills.length} />)}
                </ol>
            </div>
            <div className="space-y-1 text-xs text-muted-foreground">{data.notes.map((n) => <p key={n}>{n}</p>)}</div>
        </div>
    );
}

function Row({ c, rank, top, jd }: { c: Candidate; rank: number; top: number; jd: number }) {
    const matched = c.why.matched_skills.length;
    return (
        <motion.li
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: Math.min(rank, 20) * 0.02 }}
            className="grid grid-cols-[36px_1fr_auto] items-center gap-x-3 gap-y-2 border-b px-4 py-3.5 last:border-b-0 md:grid-cols-[48px_1.4fr_1fr_160px_110px] md:gap-4"
        >
            <span className="tabular text-sm text-muted-foreground">{rank}</span>
            <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{c.candidate_id}</span>
                    {c.synthetic ? <SyntheticBadge /> : <Badge variant="accent">Uploaded</Badge>}
                </div>
                <p className="truncate text-xs text-muted-foreground">{c.synthetic ? c.occupation_label : c.source.replace('uploaded: ', '')}</p>
            </div>
            <div className="col-start-2 hidden text-sm text-muted-foreground md:col-start-auto md:block">
                {[c.city, c.tier ? TIER_LABEL[c.tier] : null, c.exp_band ? EXP_LABEL[c.exp_band] : null].filter(Boolean).join(' · ') || '—'}
            </div>
            <div className="col-span-2 col-start-2 md:col-span-1 md:col-start-auto">
                <Hint text={`Covers ${matched} of ${jd} required skills; rarer skills weigh more (${pct(c.coverage)} weighted).`}>
                    <span className="flex w-full items-center gap-2">
                        <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                            <motion.span
                                className={cn('block h-full rounded-full', c.synthetic ? 'bg-viz-3' : 'bg-primary')}
                                initial={{ width: 0 }}
                                animate={{ width: `${Math.max(2, (c.score / Math.max(top, 1e-6)) * 100)}%` }}
                                transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                            />
                        </span>
                        <span className="tabular w-10 text-right text-xs text-muted-foreground">{pct(c.coverage)}</span>
                    </span>
                </Hint>
            </div>
            <div className="col-start-3 row-start-1 text-right md:col-start-auto md:row-start-auto">
                <WhyDrawer
                    title={c.candidate_id}
                    subtitle={c.synthetic ? 'Synthetic demo profile' : c.source}
                    why={{ ...c.why, contributions: c.why.contributions ?? [], paths: c.why.paths ?? [] }}
                >
                    <div className="flex flex-wrap gap-1.5">
                        {c.synthetic && <SyntheticBadge />}
                        <SkillChip label={`${matched} of ${jd} skills`} />
                        <SkillChip label={`${pct(c.coverage)} weighted coverage`} />
                    </div>
                </WhyDrawer>
            </div>
        </motion.li>
    );
}
