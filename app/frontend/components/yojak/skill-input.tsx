'use client';

import { useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { MagnifyingGlass, Sparkle, UploadSimple, Translate, CircleNotch } from '@phosphor-icons/react';
import { catalogService } from '@/services/catalog';
import { yojak, type Extraction, type SkillRef } from '@/services/yojak';
import { useDebounce } from '@/hooks/use-debounce';
import { SkillChip } from '@/components/yojak/bits';
import { cn } from '@/lib/utils';

const LANG_NAME: Record<string, string> = { en: 'English', hi: 'Hindi', pa: 'Punjabi', 'hi-Latn': 'Hindi (romanised)' };

export interface SkillInputValue {
    skills: SkillRef[];
}

/**
 * Pick skills three ways: search ESCO, describe them in your own words (English, Hindi,
 * Punjabi or romanised Hindi), or drop a resume / JD / syllabus file. Extracted skills are
 * added as chips; the phrases that couldn't be linked are shown, not silently dropped.
 */
export function SkillInput({
    value,
    onChange,
    placeholder = 'e.g. Excel, Tally, customer service, spoken English',
    textLabel = 'Or describe your skills in your own words',
    fileLabel = 'Upload a resume',
    allowText = true,
    allowFile = true,
    textPlaceholder = 'Python aur Excel aata hai, customer service ka 2 saal ka anubhav · मुझे अकाउंटिंग आती है',
    emptyLabel = 'Your skills will appear here',
    textRows = 3,
}: {
    value: SkillRef[];
    onChange: (skills: SkillRef[]) => void;
    placeholder?: string;
    textLabel?: string;
    fileLabel?: string;
    allowText?: boolean;
    allowFile?: boolean;
    textPlaceholder?: string;
    emptyLabel?: string;
    textRows?: number;
}) {
    const [query, setQuery] = useState('');
    const [open, setOpen] = useState(false);
    const [text, setText] = useState('');
    const [last, setLast] = useState<Extraction | null>(null);
    const debounced = useDebounce(query, 250);
    const fileRef = useRef<HTMLInputElement>(null);

    const { data: options, isFetching } = useQuery({
        queryKey: ['skill-search', debounced],
        queryFn: () => catalogService.searchSkills(debounced, 8),
        enabled: debounced.trim().length > 1,
    });

    const add = (items: SkillRef[]) => {
        const seen = new Set(value.map((s) => s.uri));
        const next = [...value];
        for (const s of items) if (!seen.has(s.uri)) { next.push({ uri: s.uri, label: s.label }); seen.add(s.uri); }
        onChange(next);
    };

    const extractText = useMutation({
        mutationFn: () => yojak.extractText(text),
        onSuccess: (r) => { setLast(r); add(r.skills); },
    });
    const extractFile = useMutation({
        mutationFn: (f: File) => yojak.extractFile(f),
        onSuccess: (r) => { setLast(r); add(r.skills); },
    });

    return (
        <div className="space-y-4">
            <div className="space-y-1.5">
                <label htmlFor="skill-search" className="text-sm font-medium">Search skills</label>
                <div className="relative">
                    <MagnifyingGlass size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                    <input
                        id="skill-search"
                        value={query}
                        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
                        onFocus={() => setOpen(true)}
                        onBlur={() => setTimeout(() => setOpen(false), 150)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && options?.length) { e.preventDefault(); add([options[0]]); setQuery(''); }
                        }}
                        placeholder={placeholder}
                        autoComplete="off"
                        className="h-10 w-full rounded-md border border-input bg-card pl-9 pr-9 text-sm placeholder:text-muted-foreground/80"
                    />
                    {isFetching && <CircleNotch size={16} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-muted-foreground" />}
                    {open && debounced.length > 1 && options && (
                        <ul role="listbox" className="absolute z-30 mt-1 max-h-72 w-full overflow-auto rounded-md border bg-popover p-1 shadow-lg">
                            {options.length === 0 && <li className="px-3 py-2 text-sm text-muted-foreground">No ESCO skill matches that. Try describing it below.</li>}
                            {options.map((o) => (
                                <li key={o.uri}>
                                    <button
                                        type="button"
                                        onMouseDown={(e) => { e.preventDefault(); add([o]); setQuery(''); }}
                                        className="w-full rounded px-3 py-2 text-left text-sm hover:bg-muted"
                                    >
                                        {o.label}
                                    </button>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            </div>

            {allowText && (
                <div className="space-y-1.5">
                    <label htmlFor="skill-text" className="flex items-center gap-1.5 text-sm font-medium">
                        <Translate size={15} /> {textLabel}
                    </label>
                    <textarea
                        id="skill-text"
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        rows={textRows}
                        placeholder={textPlaceholder}
                        className="w-full resize-y rounded-md border border-input bg-card px-3 py-2 text-sm leading-relaxed placeholder:text-muted-foreground/80"
                    />
                    <div className="flex flex-wrap items-center gap-2">
                        <button
                            type="button"
                            onClick={() => extractText.mutate()}
                            disabled={!text.trim() || extractText.isPending}
                            className="inline-flex h-9 items-center gap-1.5 rounded-md border bg-card px-3 text-sm font-medium hover:bg-muted disabled:opacity-50"
                        >
                            {extractText.isPending ? <CircleNotch size={15} className="animate-spin" /> : <Sparkle size={15} />}
                            Find skills in this text
                        </button>
                        {allowFile && (
                            <>
                                <input
                                    ref={fileRef}
                                    type="file"
                                    accept=".pdf,.docx,.txt"
                                    className="sr-only"
                                    onChange={(e) => { const f = e.target.files?.[0]; if (f) extractFile.mutate(f); e.target.value = ''; }}
                                />
                                <button
                                    type="button"
                                    onClick={() => fileRef.current?.click()}
                                    disabled={extractFile.isPending}
                                    className="inline-flex h-9 items-center gap-1.5 rounded-md border bg-card px-3 text-sm font-medium hover:bg-muted disabled:opacity-50"
                                >
                                    {extractFile.isPending ? <CircleNotch size={15} className="animate-spin" /> : <UploadSimple size={15} />}
                                    {fileLabel}
                                </button>
                            </>
                        )}
                        <span className="text-xs text-muted-foreground">PDF, DOCX or text · read in memory, not stored</span>
                    </div>
                    {(extractText.error || extractFile.error) && (
                        <p role="alert" className="text-sm text-destructive">{((extractText.error || extractFile.error) as Error).message}</p>
                    )}
                </div>
            )}

            {last && (
                <p className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
                    Read as <span className="font-medium text-foreground">{LANG_NAME[last.language] ?? last.language}</span>: linked{' '}
                    {last.skills.length} ESCO skill{last.skills.length === 1 ? '' : 's'}
                    {last.unlinked_phrases.length > 0 && (
                        <> · couldn&apos;t link: {last.unlinked_phrases.slice(0, 6).join(', ')}{last.unlinked_phrases.length > 6 ? '…' : ''}</>
                    )}
                </p>
            )}

            <div className={cn('flex min-h-[44px] flex-wrap content-start gap-1.5 rounded-lg border border-dashed p-2', value.length && 'border-solid bg-muted/30')}>
                {value.length === 0 ? (
                    <span className="px-1 py-1.5 text-sm text-muted-foreground">{emptyLabel}</span>
                ) : (
                    value.map((s) => (
                        <SkillChip key={s.uri} label={s.label} tone="have" onRemove={() => onChange(value.filter((x) => x.uri !== s.uri))} />
                    ))
                )}
            </div>
        </div>
    );
}
