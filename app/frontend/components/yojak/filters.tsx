'use client';

import { cn } from '@/lib/utils';
import { EXP_BANDS, EXP_LABEL } from '@/lib/format';

export const STATES = [
    'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chandigarh', 'Chhattisgarh', 'Delhi', 'Goa', 'Gujarat',
    'Haryana', 'Himachal Pradesh', 'Jammu and Kashmir', 'Jharkhand', 'Karnataka', 'Kerala', 'Madhya Pradesh',
    'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Puducherry', 'Punjab', 'Rajasthan',
    'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
];

const TIER_HELP: Record<number, string> = {
    1: 'Tier 1: the eight HRA "X" metros',
    2: 'Tier 2: HRA "Y" cities',
    3: 'Tier 3: every other town',
};

export function TierToggle({ value, onChange }: { value: number[]; onChange: (v: number[]) => void }) {
    return (
        <fieldset className="space-y-1.5">
            <legend className="text-sm font-medium">City tier</legend>
            <div className="flex flex-wrap gap-1.5">
                {[1, 2, 3].map((t) => {
                    const on = value.includes(t);
                    return (
                        <button
                            key={t}
                            type="button"
                            aria-pressed={on}
                            title={TIER_HELP[t]}
                            onClick={() => onChange(on ? value.filter((x) => x !== t) : [...value, t].sort())}
                            className={cn(
                                'h-9 rounded-md border px-3 text-sm transition-colors',
                                on ? 'border-primary bg-accent text-accent-foreground' : 'bg-card text-muted-foreground hover:text-foreground',
                            )}
                        >
                            Tier {t}
                        </button>
                    );
                })}
            </div>
            <p className="text-xs text-muted-foreground">{value.length ? 'Only postings in the selected tiers.' : 'All tiers.'} Tiers follow the 7th CPC HRA city classes.</p>
        </fieldset>
    );
}

export function ExpSelect({ value, onChange, label = 'Experience' }: { value: string; onChange: (v: string) => void; label?: string }) {
    return (
        <div className="space-y-1.5">
            <label htmlFor="exp" className="text-sm font-medium">{label}</label>
            <select
                id="exp"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="h-10 w-full rounded-md border border-input bg-card px-3 text-sm"
            >
                <option value="">Any experience</option>
                {EXP_BANDS.map((b) => <option key={b} value={b}>{EXP_LABEL[b]}</option>)}
            </select>
        </div>
    );
}

export function StateSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
    return (
        <div className="space-y-1.5">
            <label htmlFor="state" className="text-sm font-medium">State</label>
            <select
                id="state"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="h-10 w-full rounded-md border border-input bg-card px-3 text-sm"
            >
                <option value="">All of India</option>
                {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
        </div>
    );
}

export function Segmented<T extends string>({ value, options, onChange, label }: {
    value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string;
}) {
    return (
        <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border bg-muted/50 p-0.5">
            {options.map((o) => (
                <button
                    key={o.value}
                    type="button"
                    role="radio"
                    aria-checked={value === o.value}
                    onClick={() => onChange(o.value)}
                    className={cn(
                        'rounded-md px-3 py-1.5 text-sm transition-colors',
                        value === o.value ? 'bg-card font-medium shadow-sm' : 'text-muted-foreground hover:text-foreground',
                    )}
                >
                    {o.label}
                </button>
            ))}
        </div>
    );
}
