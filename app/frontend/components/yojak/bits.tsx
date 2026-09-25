'use client';

import * as React from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import * as Tooltip from '@radix-ui/react-tooltip';
import { motion } from 'motion/react';
import { ArrowRight, Info, Warning, X, CircleNotch, FlowArrow } from '@phosphor-icons/react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { inr, num, pct } from '@/lib/format';
import type { PathStep, SalaryRange as Salary, Why } from '@/services/yojak';

// ---------- page scaffolding ----------

export function PageIntro({ title, lead, children }: { title: string; lead: string; children?: React.ReactNode }) {
    return (
        <div className="space-y-3 pb-8 pt-10 md:pt-14">
            <h1 className="text-balance text-3xl font-semibold tracking-tight md:text-[40px] md:leading-[1.1]">{title}</h1>
            <p className="max-w-[62ch] text-[15px] leading-relaxed text-muted-foreground md:text-base">{lead}</p>
            {children}
        </div>
    );
}

export function Section({ title, description, children, className, action }: {
    title?: string; description?: React.ReactNode; children: React.ReactNode; className?: string; action?: React.ReactNode;
}) {
    return (
        <section className={cn('space-y-4', className)}>
            {(title || action) && (
                <div className="flex flex-wrap items-end justify-between gap-3">
                    <div className="space-y-1">
                        {title && <h2 className="text-lg font-semibold tracking-tight">{title}</h2>}
                        {description && <p className="max-w-[70ch] text-sm text-muted-foreground">{description}</p>}
                    </div>
                    {action}
                </div>
            )}
            {children}
        </section>
    );
}

export function Panel({ className, children }: { className?: string; children: React.ReactNode }) {
    return <div className={cn('rounded-xl border bg-card p-5', className)}>{children}</div>;
}

// ---------- honesty labels ----------

export function SyntheticBadge() {
    return (
        <Hint text="A generated demo profile, not a real person. Built from ESCO occupation skills and Indian posting patterns.">
            <Badge variant="synthetic">Synthetic</Badge>
        </Hint>
    );
}

export function ProxyNote({ children, title = 'Proxy' }: { children: React.ReactNode; title?: string }) {
    return (
        <div className="flex gap-2.5 rounded-lg border border-caution/30 bg-caution-muted px-3.5 py-3 text-[13px] leading-relaxed text-caution-foreground">
            <Warning size={16} weight="bold" className="mt-0.5 shrink-0" />
            <div>
                <span className="font-semibold">{title}. </span>
                {children}
            </div>
        </div>
    );
}

export function Pending({ what }: { what: string }) {
    return (
        <span className="inline-flex items-center gap-1.5 rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            <CircleNotch size={12} /> {what}
        </span>
    );
}

export function Hint({ text, children }: { text: React.ReactNode; children: React.ReactNode }) {
    return (
        <Tooltip.Root>
            <Tooltip.Trigger asChild>
                <span className="inline-flex cursor-help">{children}</span>
            </Tooltip.Trigger>
            <Tooltip.Portal>
                <Tooltip.Content
                    sideOffset={6}
                    className="z-50 max-w-xs rounded-md border bg-popover px-3 py-2 text-xs leading-relaxed text-popover-foreground shadow-md"
                >
                    {text}
                </Tooltip.Content>
            </Tooltip.Portal>
        </Tooltip.Root>
    );
}

export function InfoHint({ text }: { text: React.ReactNode }) {
    return (
        <Hint text={text}>
            <Info size={14} className="text-muted-foreground" aria-label="More information" />
        </Hint>
    );
}

// ---------- states ----------

export function SkeletonBlock({ className }: { className?: string }) {
    return (
        <div className={cn('relative overflow-hidden rounded-md bg-muted', className)}>
            <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.6s_infinite] bg-gradient-to-r from-transparent via-foreground/[0.04] to-transparent" />
        </div>
    );
}

export function ResultSkeleton({ rows = 4 }: { rows?: number }) {
    return (
        <div className="space-y-3" aria-busy="true" aria-label="Loading">
            {Array.from({ length: rows }).map((_, i) => (
                <div key={i} className="rounded-xl border bg-card p-5">
                    <SkeletonBlock className="h-4 w-1/3" />
                    <SkeletonBlock className="mt-3 h-3 w-2/3" />
                    <SkeletonBlock className="mt-4 h-2 w-full" />
                </div>
            ))}
        </div>
    );
}

export function EmptyState({ icon, title, children }: { icon?: React.ReactNode; title: string; children?: React.ReactNode }) {
    return (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed px-6 py-14 text-center">
            {icon && <div className="mb-4 text-muted-foreground">{icon}</div>}
            <p className="font-medium">{title}</p>
            {children && <div className="mt-2 max-w-md text-sm text-muted-foreground">{children}</div>}
        </div>
    );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
    const message = error instanceof Error ? error.message : 'Something went wrong.';
    return (
        <div role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
            <p className="font-medium text-destructive">Couldn&apos;t load this</p>
            <p className="mt-1 text-muted-foreground">{message}</p>
            {onRetry && (
                <button onClick={onRetry} className="mt-2 text-sm font-medium text-primary hover:underline">
                    Try again
                </button>
            )}
        </div>
    );
}

// ---------- salary range: never a single number ----------

export function SalaryRange({ salary, compact = false }: { salary: Salary | null | undefined; compact?: boolean }) {
    if (!salary) return <span className="text-xs text-muted-foreground">No salary data</span>;
    const { p10, p50, p90, n_support, sufficient } = salary;
    if (![p10, p50, p90].every((v) => typeof v === 'number' && Number.isFinite(v))) {
        return <span className="text-xs text-muted-foreground">No salary range</span>;
    }
    if (!sufficient) {
        return (
            <Hint text={`Only ${n_support} similar postings disclose pay, too few to show a reliable range.`}>
                <span className="text-xs text-muted-foreground underline decoration-dotted underline-offset-2">
                    Not enough disclosed data
                </span>
            </Hint>
        );
    }
    const label = `${inr(p10)} to ${inr(p90)} a year, median ${inr(p50)}`;
    if (compact) {
        return (
            <Hint text={<>Posted pay range (P10 to P90), median {inr(p50)}. Based on {num(n_support)} similar postings that disclose pay.</>}>
                <span className="tabular text-sm" aria-label={label}>
                    {inr(p10)}<span className="text-muted-foreground"> to </span>{inr(p90)}
                </span>
            </Hint>
        );
    }
    const lo = Math.log(p10), hi = Math.log(p90), mid = Math.log(p50);
    const pos = hi > lo ? ((mid - lo) / (hi - lo)) * 100 : 50;
    return (
        <div className="space-y-1.5" aria-label={label}>
            <div className="flex items-baseline justify-between text-xs text-muted-foreground tabular">
                <span>{inr(p10)}</span>
                <span className="text-sm font-medium text-foreground">{inr(p50)}</span>
                <span>{inr(p90)}</span>
            </div>
            <div className="relative h-1.5 rounded-full bg-gradient-to-r from-viz-2 via-viz-3 to-viz-2">
                <span className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 rounded bg-foreground" style={{ left: `${pos}%` }} />
            </div>
            <p className="text-[11px] text-muted-foreground">
                Posted pay, P10 to P90 · {num(n_support)} disclosing postings
            </p>
        </div>
    );
}

// ---------- skills ----------

export function SkillChip({ label, tone = 'neutral', onRemove }: { label: string; tone?: 'neutral' | 'have' | 'gap'; onRemove?: () => void }) {
    return (
        <span
            className={cn(
                'inline-flex max-w-full items-center gap-1 rounded-md border px-2 py-1 text-[13px] leading-none',
                tone === 'have' && 'border-primary/30 bg-accent text-accent-foreground',
                tone === 'gap' && 'border-dashed text-muted-foreground',
                tone === 'neutral' && 'bg-card',
            )}
        >
            <span className="truncate">{label}</span>
            {onRemove && (
                <button type="button" onClick={onRemove} className="-mr-0.5 rounded p-0.5 hover:bg-muted" aria-label={`Remove ${label}`}>
                    <X size={12} />
                </button>
            )}
        </span>
    );
}

// ---------- why panel ----------

export function PathView({ path }: { path: PathStep[] }) {
    return (
        <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-2 text-[13px]">
            {path.map((step, i) => (
                <li key={i} className="flex items-center gap-1.5">
                    <span className="rounded-md border bg-card px-2 py-1">
                        <span className="block text-[10px] uppercase tracking-wide text-muted-foreground">{step.kind}</span>
                        <span className="font-medium">{step.label}</span>
                    </span>
                    {i < path.length - 1 && <ArrowRight size={14} className="text-muted-foreground" />}
                </li>
            ))}
        </ol>
    );
}

export function WhyContent({ why }: { why: Why }) {
    const maxDrop = Math.max(0.000001, ...why.contributions.map((c) => c.score_drop));
    return (
        <div className="space-y-6">
            {why.paths.length > 0 && (
                <div className="space-y-3">
                    <h3 className="text-sm font-semibold">Graph path</h3>
                    {why.paths.map((p, i) => <PathView key={i} path={p} />)}
                </div>
            )}
            {why.contributions.length > 0 && (
                <div className="space-y-2">
                    <h3 className="text-sm font-semibold">What drove the match</h3>
                    <p className="text-xs text-muted-foreground">How much the score drops if each of your skills is removed.</p>
                    <ul className="space-y-1.5">
                        {why.contributions.map((c) => (
                            <li key={c.skill.uri} className="grid grid-cols-[1fr_auto] items-center gap-3 text-[13px]">
                                <div>
                                    <span>{c.skill.label}</span>
                                    <div className="mt-1 h-1.5 rounded-full bg-muted">
                                        <motion.div
                                            className="h-full rounded-full bg-primary"
                                            initial={{ width: 0 }}
                                            animate={{ width: `${Math.max(2, (c.score_drop / maxDrop) * 100)}%` }}
                                            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                                        />
                                    </div>
                                </div>
                                <span className="tabular text-xs text-muted-foreground">{c.score_drop.toFixed(3)}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
            {why.matched_skills.length > 0 && (
                <div className="space-y-2">
                    <h3 className="text-sm font-semibold">Skills you have ({why.matched_skills.length})</h3>
                    <div className="flex flex-wrap gap-1.5">
                        {why.matched_skills.map((s) => <SkillChip key={s.uri} label={s.label} tone="have" />)}
                    </div>
                </div>
            )}
            {why.missing_skills.length > 0 && (
                <div className="space-y-2">
                    <h3 className="text-sm font-semibold">Skills to add ({why.missing_skills.length})</h3>
                    <div className="flex flex-wrap gap-1.5">
                        {why.missing_skills.map((s) => <SkillChip key={s.uri} label={s.label} tone="gap" />)}
                    </div>
                </div>
            )}
            {(why.notes.length > 0 || why.model) && (
                <div className="space-y-1.5 border-t pt-4 text-xs text-muted-foreground">
                    {why.model && <p>Model: {why.model}</p>}
                    {why.notes.map((n, i) => <p key={i}>{n}</p>)}
                </div>
            )}
        </div>
    );
}

export function WhyDrawer({ title, subtitle, why, children }: { title: string; subtitle?: string; why: Why; children?: React.ReactNode }) {
    return (
        <Dialog.Root>
            <Dialog.Trigger asChild>
                <button type="button" className="inline-flex items-center gap-1 text-[13px] font-medium text-primary hover:underline">
                    <FlowArrow size={14} /> Why this?
                </button>
            </Dialog.Trigger>
            <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 z-50 bg-background/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0" />
                <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col border-l bg-background shadow-2xl data-[state=open]:animate-in data-[state=open]:slide-in-from-right">
                    <div className="flex items-start justify-between gap-4 border-b p-5">
                        <div>
                            <Dialog.Title className="text-lg font-semibold leading-snug">{title}</Dialog.Title>
                            {subtitle && <Dialog.Description className="mt-1 text-sm text-muted-foreground">{subtitle}</Dialog.Description>}
                        </div>
                        <Dialog.Close className="rounded-md p-1.5 hover:bg-muted" aria-label="Close">
                            <X size={18} />
                        </Dialog.Close>
                    </div>
                    <div className="flex-1 space-y-6 overflow-y-auto p-5">
                        {children}
                        <WhyContent why={why} />
                    </div>
                </Dialog.Content>
            </Dialog.Portal>
        </Dialog.Root>
    );
}

// ---------- small data displays ----------

export function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: React.ReactNode }) {
    return (
        <div className="space-y-1">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="tabular text-2xl font-semibold tracking-tight">{value}</p>
            {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
        </div>
    );
}

export function FitBar({ value }: { value: number }) {
    return (
        <Hint text={`${pct(value)} of this posting's skills (weighted by how specific they are) match yours.`}>
            <span className="inline-flex items-center gap-2">
                <span className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
                    <span className="block h-full rounded-full bg-primary" style={{ width: `${Math.round(value * 100)}%` }} />
                </span>
                <span className="tabular text-xs text-muted-foreground">{pct(value)}</span>
            </span>
        </Hint>
    );
}
