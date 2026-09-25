'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { labellingService, type Candidate, type LabelTask, type PhraseItem, type SkillItem, type TitleItem } from '@/services/labelling';
import { catalogService } from '@/services/catalog';
import { getAdminToken, setAdminToken } from '@/lib/api';
import { useDebounce } from '@/hooks/use-debounce';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { cn } from '@/lib/utils';

const LABELLER_KEY = 'yojak.labeller';

function readLabeller(): string {
    try {
        return window.localStorage.getItem(LABELLER_KEY) ?? '';
    } catch {
        return '';
    }
}

export default function LabellingPage() {
    const [task, setTask] = useState<LabelTask>('skills');
    const [labeller, setLabeller] = useState('');
    const [token, setToken] = useState('');

    useEffect(() => {
        setLabeller(readLabeller());
        setToken(getAdminToken() ?? '');
    }, []);

    const saveLabeller = (v: string) => {
        setLabeller(v);
        try {
            window.localStorage.setItem(LABELLER_KEY, v);
        } catch {
            // storage blocked: the name just won't be remembered
        }
    };

    return (
        <div className="space-y-6 max-w-5xl">
            <header className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight">Gold labelling</h1>
                <p className="text-muted-foreground max-w-2xl">
                    These labels measure how accurately Yojak links Indian job-posting text to ESCO. The samples are
                    fixed and stratified; every answer is saved with your name. The model&apos;s suggestions are only
                    suggestions, so pick &ldquo;none&rdquo; whenever no candidate is right.
                </p>
            </header>

            <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-1.5">
                    <label htmlFor="labeller" className="text-sm font-medium">Your name</label>
                    <Input id="labeller" value={labeller} onChange={(e) => saveLabeller(e.target.value)} placeholder="e.g. Asha" />
                </div>
                <div className="space-y-1.5">
                    <label htmlFor="token" className="text-sm font-medium">Admin token</label>
                    <Input
                        id="token"
                        type="password"
                        value={token}
                        onChange={(e) => {
                            setToken(e.target.value);
                            setAdminToken(e.target.value || null);
                        }}
                        placeholder="ADMIN_TOKEN from .env (leave empty in local development)"
                    />
                </div>
            </div>

            <Tabs value={task} onValueChange={(v) => setTask(v as LabelTask)}>
                <TabsList>
                    <TabsTrigger value="skills">Skill links</TabsTrigger>
                    <TabsTrigger value="titles">Job titles</TabsTrigger>
                    <TabsTrigger value="multilingual">Hindi / Punjabi</TabsTrigger>
                </TabsList>
            </Tabs>

            {!labeller.trim() ? (
                <Alert>
                    <AlertDescription>Enter your name first; it is stored with each label.</AlertDescription>
                </Alert>
            ) : task === 'multilingual' ? (
                <PhraseGrid labeller={labeller.trim()} />
            ) : (
                <LinkLabeller task={task} labeller={labeller.trim()} />
            )}
        </div>
    );
}

function Progress({ done, total }: { done: number; total: number }) {
    const pct = total ? Math.round((done / total) * 100) : 0;
    return (
        <div className="flex items-center gap-3 text-sm">
            <span className="tabular-nums font-medium">{done} / {total} labelled</span>
            <div className="h-1.5 w-40 overflow-hidden rounded-full bg-muted">
                <div className="h-full bg-primary transition-all" style={{ width: `${pct}%` }} />
            </div>
        </div>
    );
}

function LinkLabeller({ task, labeller }: { task: 'skills' | 'titles'; labeller: string }) {
    const qc = useQueryClient();
    const { data, isLoading, error } = useQuery({
        queryKey: ['labelling', task],
        queryFn: () => labellingService.items<SkillItem | TitleItem>(task),
    });
    const [onlyOpen, setOnlyOpen] = useState(true);
    const [cursor, setCursor] = useState(0);
    const [search, setSearch] = useState('');
    const debounced = useDebounce(search, 300);

    const items = useMemo(
        () => (data?.items ?? []).filter((it) => !onlyOpen || !it.label),
        [data, onlyOpen],
    );
    const item = items[Math.min(cursor, Math.max(0, items.length - 1))];
    const key = item ? (task === 'skills' ? (item as SkillItem).tag : (item as TitleItem).jobId) : '';

    const save = useMutation({
        mutationFn: (gold_uri: string) => labellingService.save(task, { key, gold_uri, labeller }),
        onSuccess: () => {
            setSearch('');
            qc.invalidateQueries({ queryKey: ['labelling', task] });
            if (!onlyOpen) setCursor((c) => Math.min(c + 1, items.length - 1));
        },
    });

    const { data: searchHits } = useQuery({
        queryKey: ['labelling-search', task, debounced],
        queryFn: () =>
            task === 'skills' ? catalogService.searchSkills(debounced, 8) : catalogService.searchOccupations(debounced, 8),
        enabled: debounced.length > 1,
    });

    const onKey = useCallback(
        (e: KeyboardEvent) => {
            if (!item || save.isPending) return;
            const target = e.target as HTMLElement;
            if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;
            const n = Number(e.key);
            if (n >= 1 && n <= 9 && item.candidates[n - 1]) save.mutate(item.candidates[n - 1].uri);
            else if (e.key.toLowerCase() === 'n') save.mutate('NONE');
            else if (e.key.toLowerCase() === 'x' && task === 'skills') save.mutate('NOT_A_SKILL');
            else if (e.key === 'ArrowRight') setCursor((c) => Math.min(c + 1, items.length - 1));
            else if (e.key === 'ArrowLeft') setCursor((c) => Math.max(c - 1, 0));
        },
        [item, items.length, save, task],
    );

    useEffect(() => {
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [onKey]);

    if (isLoading) return <p className="text-muted-foreground">Loading sample...</p>;
    if (error) return <Alert variant="destructive"><AlertDescription>{(error as Error).message}</AlertDescription></Alert>;
    if (!data) return null;

    return (
        <section className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <Progress done={data.done} total={data.total} />
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                    <input type="checkbox" checked={onlyOpen} onChange={(e) => { setOnlyOpen(e.target.checked); setCursor(0); }} />
                    Show unlabelled only
                </label>
            </div>

            {!item ? (
                <Alert><AlertDescription>All items in this sample are labelled. Thank you.</AlertDescription></Alert>
            ) : (
                <div className="rounded-lg border p-5 space-y-4">
                    <div className="flex items-start justify-between gap-4">
                        <div className="space-y-1">
                            {task === 'skills' ? (
                                <>
                                    <p className="text-xs uppercase text-muted-foreground">Naukri skill tag</p>
                                    <h2 className="text-2xl font-semibold">{(item as SkillItem).tag}</h2>
                                    <p className="text-sm text-muted-foreground">
                                        Seen in {(item as SkillItem).freq} postings, e.g. {(item as SkillItem).example_titles || 'n/a'}
                                    </p>
                                </>
                            ) : (
                                <>
                                    <p className="text-xs uppercase text-muted-foreground">Job posting</p>
                                    <h2 className="text-2xl font-semibold">{(item as TitleItem).title}</h2>
                                    <p className="text-sm text-muted-foreground">
                                        {(item as TitleItem).companyName} · skills: {(item as TitleItem).tags_preview || 'none listed'}
                                    </p>
                                </>
                            )}
                        </div>
                        <span className="text-xs text-muted-foreground tabular-nums">
                            {Math.min(cursor, items.length - 1) + 1} of {items.length}
                        </span>
                    </div>

                    {item.label && (
                        <p className="text-sm">
                            Current label: <Badge variant="secondary">{item.label.gold_uri}</Badge> by {item.label.labeller}
                        </p>
                    )}

                    <ol className="grid gap-2">
                        {item.candidates.slice(0, 9).map((c: Candidate, i: number) => (
                            <li key={c.uri}>
                                <button
                                    type="button"
                                    disabled={save.isPending}
                                    onClick={() => save.mutate(c.uri)}
                                    className={cn(
                                        'w-full flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-left text-sm',
                                        'hover:bg-muted transition-colors disabled:opacity-50',
                                        item.label?.gold_uri === c.uri && 'border-primary',
                                    )}
                                >
                                    <span><kbd className="mr-2 text-xs text-muted-foreground">{i + 1}</kbd>{c.label}</span>
                                    <span className="text-xs text-muted-foreground tabular-nums">{c.score.toFixed(2)}</span>
                                </button>
                            </li>
                        ))}
                    </ol>

                    <div className="flex flex-wrap gap-2">
                        <Button variant="outline" onClick={() => save.mutate('NONE')} disabled={save.isPending}>
                            No ESCO match <kbd className="ml-2 text-xs opacity-60">N</kbd>
                        </Button>
                        {task === 'skills' && (
                            <Button variant="outline" onClick={() => save.mutate('NOT_A_SKILL')} disabled={save.isPending}>
                                Not a skill <kbd className="ml-2 text-xs opacity-60">X</kbd>
                            </Button>
                        )}
                        <Button variant="ghost" onClick={() => setCursor((c) => Math.max(c - 1, 0))}>Previous</Button>
                        <Button variant="ghost" onClick={() => setCursor((c) => Math.min(c + 1, items.length - 1))}>Skip</Button>
                    </div>

                    <div className="space-y-1.5">
                        <label htmlFor="other" className="text-sm font-medium">
                            None of these? Search ESCO for the right {task === 'skills' ? 'skill' : 'occupation'}
                        </label>
                        <Input id="other" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Type at least 2 letters" />
                        {searchHits && searchHits.length > 0 && (
                            <div className="grid gap-1 pt-1">
                                {searchHits.map((h) => (
                                    <button key={h.uri} type="button" onClick={() => save.mutate(h.uri)}
                                        className="text-left text-sm rounded px-2 py-1 hover:bg-muted">
                                        {h.label}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                    {save.error && (
                        <Alert variant="destructive"><AlertDescription>{(save.error as Error).message}</AlertDescription></Alert>
                    )}
                </div>
            )}
        </section>
    );
}

function PhraseGrid({ labeller }: { labeller: string }) {
    const qc = useQueryClient();
    const { data, isLoading, error } = useQuery({
        queryKey: ['labelling', 'multilingual'],
        queryFn: () => labellingService.items<PhraseItem>('multilingual'),
    });
    const save = useMutation({
        mutationFn: (v: { key: string; language: string; phrase: string }) =>
            labellingService.save('multilingual', { ...v, labeller }),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['labelling', 'multilingual'] }),
    });

    if (isLoading) return <p className="text-muted-foreground">Loading...</p>;
    if (error) return <Alert variant="destructive"><AlertDescription>{(error as Error).message}</AlertDescription></Alert>;
    if (!data) return null;
    const langs = Object.entries(data.languages ?? {});

    return (
        <section className="space-y-4">
            <Progress done={data.done} total={data.total} />
            <p className="text-sm text-muted-foreground max-w-2xl">
                Write how a job-seeker would naturally say each skill. Use everyday words, not a dictionary
                translation. Each cell saves when you leave it.
            </p>
            <div className="overflow-x-auto rounded-lg border">
                <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                        <tr>
                            <th className="p-2 text-left font-medium">ESCO skill</th>
                            {langs.map(([code, name]) => (
                                <th key={code} className="p-2 text-left font-medium">{name}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {data.items.map((it) => (
                            <tr key={it.skill_uri} className="border-t">
                                <td className="p-2 align-top">{it.english_label}</td>
                                {langs.map(([code]) => (
                                    <td key={code} className="p-2">
                                        <Input
                                            defaultValue={it.phrases[code] ?? ''}
                                            lang={code}
                                            aria-label={`${it.english_label} in ${code}`}
                                            onBlur={(e) => {
                                                const phrase = e.target.value.trim();
                                                if (phrase && phrase !== (it.phrases[code] ?? '')) {
                                                    save.mutate({ key: it.skill_uri, language: code, phrase });
                                                }
                                            }}
                                        />
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            {save.error && <Alert variant="destructive"><AlertDescription>{(save.error as Error).message}</AlertDescription></Alert>}
        </section>
    );
}
