'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CircleNotch, MagnifyingGlass } from '@phosphor-icons/react';
import { catalogService } from '@/services/catalog';
import { useDebounce } from '@/hooks/use-debounce';
import type { AutocompleteOption } from '@/types';

/** Search ESCO occupations by name (preferred and alternative labels). */
export function OccupationSearch({ onSelect, placeholder = 'Search occupations, e.g. accountant', id = 'occupation-search', label = 'Target occupation' }: {
    onSelect: (o: AutocompleteOption) => void; placeholder?: string; id?: string; label?: string;
}) {
    const [query, setQuery] = useState('');
    const [open, setOpen] = useState(false);
    const debounced = useDebounce(query, 250);
    const { data, isFetching } = useQuery({
        queryKey: ['occupation-search', debounced],
        queryFn: () => catalogService.searchOccupations(debounced, 8),
        enabled: debounced.trim().length > 1,
    });
    return (
        <div className="space-y-1.5">
            <label htmlFor={id} className="text-sm font-medium">{label}</label>
            <div className="relative">
                <MagnifyingGlass size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                    id={id}
                    value={query}
                    onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
                    onFocus={() => setOpen(true)}
                    onBlur={() => setTimeout(() => setOpen(false), 150)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && data?.length) { e.preventDefault(); onSelect(data[0]); setQuery(''); setOpen(false); }
                    }}
                    placeholder={placeholder}
                    autoComplete="off"
                    className="h-10 w-full rounded-md border border-input bg-card pl-9 pr-9 text-sm placeholder:text-muted-foreground/80"
                />
                {isFetching && <CircleNotch size={16} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-muted-foreground" />}
                {open && debounced.length > 1 && data && (
                    <ul role="listbox" className="absolute z-30 mt-1 max-h-72 w-full overflow-auto rounded-md border bg-popover p-1 shadow-lg">
                        {data.length === 0 && <li className="px-3 py-2 text-sm text-muted-foreground">No ESCO occupation matches that.</li>}
                        {data.map((o) => (
                            <li key={o.uri}>
                                <button
                                    type="button"
                                    onMouseDown={(e) => { e.preventDefault(); onSelect(o); setQuery(''); setOpen(false); }}
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
    );
}
