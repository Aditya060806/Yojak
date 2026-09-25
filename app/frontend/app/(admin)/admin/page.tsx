'use client';

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, CheckCircle, CircleDashed, Pulse, Tag } from '@phosphor-icons/react';
import { diagnosticsService } from '@/services/diagnostics';
import { labellingService, type LabelTask } from '@/services/labelling';
import { yojak } from '@/services/yojak';
import { Panel, Section, Stat } from '@/components/yojak/bits';
import { num, pct } from '@/lib/format';

const TASKS: { task: LabelTask; label: string }[] = [
    { task: 'skills', label: 'Skill links (tag → ESCO skill)' },
    { task: 'titles', label: 'Title links (job title → ESCO occupation)' },
    { task: 'multilingual', label: 'Multilingual phrases' },
];

export default function AdminOverview() {
    const nodes = useQuery({ queryKey: ['diagnostics-nodes'], queryFn: diagnosticsService.getNodesByLabel });
    const rels = useQuery({ queryKey: ['diagnostics-rels'], queryFn: diagnosticsService.getRelsByType });
    const reports = useQuery({ queryKey: ['report-index'], queryFn: yojak.reportIndex });
    const totalNodes = nodes.data?.labels.reduce((s, n) => s + n.count, 0);
    const totalRels = rels.data?.types.reduce((s, r) => s + r.count, 0);
    const count = (label: string) => nodes.data?.labels.find((n) => n.label === label)?.count;

    return (
        <div className="space-y-10">
            <div className="space-y-1.5">
                <h1 className="text-3xl font-semibold tracking-tight">Overview</h1>
                <p className="text-muted-foreground">The graph, the gold-label work still to do, and which reports exist.</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Panel><Stat label="Graph nodes" value={totalNodes !== undefined ? num(totalNodes) : '…'} /></Panel>
                <Panel><Stat label="Relationships" value={totalRels !== undefined ? num(totalRels) : '…'} /></Panel>
                <Panel><Stat label="Job postings" value={count('Job') !== undefined ? num(count('Job')) : '…'} /></Panel>
                <Panel><Stat label="Synthetic candidates" value={count('Candidate') !== undefined ? num(count('Candidate')) : '–'} hint="labelled synthetic in the graph" /></Panel>
            </div>

            <Section title="Gold labelling" description="Precision figures stay 'pending' until these frozen samples are labelled."
                     action={<Link href="/admin/labelling" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">Open labelling <ArrowRight size={14} /></Link>}>
                <div className="grid gap-4 md:grid-cols-3">
                    {TASKS.map((t) => <LabelProgress key={t.task} task={t.task} label={t.label} />)}
                </div>
            </Section>

            <Section title="Reports" description="Written by the pipeline and evaluation scripts into reports/."
                     action={<Link href="/evidence" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">Evidence page <ArrowRight size={14} /></Link>}>
                <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {[...(reports.data?.json ?? []), ...(reports.data?.markdown ?? [])].map((r) => (
                        <li key={r.name} className="flex items-center gap-2 rounded-lg border bg-card px-3 py-2.5 font-mono text-[13px]">
                            {r.available ? <CheckCircle size={16} weight="fill" className="text-primary" /> : <CircleDashed size={16} className="text-muted-foreground" />}
                            {r.name}
                            <span className="ml-auto font-sans text-xs text-muted-foreground">{r.available ? 'generated' : 'pending'}</span>
                        </li>
                    ))}
                </ul>
            </Section>

            <Link href="/admin/health" className="flex items-center gap-3 rounded-xl border bg-card p-5 transition-colors hover:border-primary/40">
                <Pulse size={22} className="text-primary" />
                <span>
                    <span className="block font-medium">System health</span>
                    <span className="text-sm text-muted-foreground">Live latency per endpoint, node and relationship counts, every API route.</span>
                </span>
                <ArrowRight size={16} className="ml-auto text-muted-foreground" />
            </Link>
        </div>
    );
}

function LabelProgress({ task, label }: { task: LabelTask; label: string }) {
    const { data, error } = useQuery({ queryKey: ['label-progress', task], queryFn: () => labellingService.items(task), retry: false });
    const share = data && data.total ? data.done / data.total : 0;
    return (
        <Panel className="space-y-3">
            <p className="flex items-center gap-2 text-sm font-medium"><Tag size={16} className="text-primary" /> {label}</p>
            {error ? <p className="text-xs text-muted-foreground">Set the admin token in Settings to see progress.</p> : (
                <>
                    <p className="tabular text-2xl font-semibold">{data ? `${num(data.done)} / ${num(data.total)}` : '…'}</p>
                    <div className="h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${share * 100}%` }} /></div>
                    <p className="text-xs text-muted-foreground">{pct(share)} labelled</p>
                </>
            )}
        </Panel>
    );
}
