/** Indian-style rupee amounts: 450000 -> "₹4.5 L", 12000000 -> "₹1.2 Cr". */
export function inr(value: number | null | undefined, digits = 1): string {
    if (value === null || value === undefined || !Number.isFinite(value)) return '–';
    const abs = Math.abs(value);
    const sign = value < 0 ? '−' : '';
    if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(digits)} Cr`;
    if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(digits)} L`;
    if (abs >= 1e3) return `${sign}₹${(abs / 1e3).toFixed(0)}K`;
    return `${sign}₹${abs.toFixed(0)}`;
}

export function pct(value: number | null | undefined, digits = 0): string {
    if (value === null || value === undefined || !Number.isFinite(value)) return '–';
    return `${(value * 100).toFixed(digits)}%`;
}

export function num(value: number | null | undefined, digits = 0): string {
    if (value === null || value === undefined || !Number.isFinite(value)) return '–';
    return value.toLocaleString('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function titleCase(s: string): string {
    return s.charAt(0).toUpperCase() + s.slice(1);
}

export const TIER_LABEL: Record<number, string> = { 1: 'Tier 1', 2: 'Tier 2', 3: 'Tier 3' };
export const EXP_BANDS = ['0-1', '1-3', '3-6', '6-10', '10+'] as const;
export const EXP_LABEL: Record<string, string> = {
    '0-1': 'Fresher (0-1 yrs)',
    '1-3': '1-3 yrs',
    '3-6': '3-6 yrs',
    '6-10': '6-10 yrs',
    '10+': '10+ yrs',
};

/** ISCO-08 sub-major groups most common in the postings (official ILO titles). */
export const ISCO2: Record<string, string> = {
    '12': 'Administrative and commercial managers',
    '13': 'Production and specialised services managers',
    '21': 'Science and engineering professionals',
    '22': 'Health professionals',
    '23': 'Teaching professionals',
    '24': 'Business and administration professionals',
    '25': 'Information and communications technology professionals',
    '26': 'Legal, social and cultural professionals',
    '31': 'Science and engineering associate professionals',
    '32': 'Health associate professionals',
    '33': 'Business and administration associate professionals',
    '35': 'Information and communications technicians',
    '41': 'General and keyboard clerks',
    '42': 'Customer services clerks',
    '43': 'Numerical and material recording clerks',
    '52': 'Sales workers',
    '72': 'Metal, machinery and related trades workers',
    '74': 'Electrical and electronic trades workers',
};

/** Download rows as a CSV file (client side). */
export function downloadCsv(filename: string, rows: Record<string, string | number | null | undefined>[]) {
    if (!rows.length) return;
    const cols = Object.keys(rows[0]);
    const esc = (v: unknown) => {
        const s = v === null || v === undefined ? '' : String(v);
        return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const body = [cols.join(','), ...rows.map((r) => cols.map((c) => esc(r[c])).join(','))].join('\n');
    const url = URL.createObjectURL(new Blob(['\ufeff' + body], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}
