'use client';

import { DownloadSimple, X } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { SalaryRange, SkillChip, WhyDrawer } from './bits';
import { downloadCsv, num } from '@/lib/format';
import type { RoleMatch } from '@/services/yojak';

export function RoleComparison({ roles, example, onRemove, onClear }: {
    roles: RoleMatch[]; example: boolean; onRemove: (uri: string) => void; onClear: () => void;
}) {
    const exportComparison = () => downloadCsv('yojak-role-comparison.csv', roles.map((role) => ({
        source: example ? 'Saved example' : 'Live analysis',
        role: role.occupation_label,
        occupation_uri: role.occupation_uri,
        postings: role.postings,
        nco_family: role.nco_family,
        salary_p10_inr: role.salary?.sufficient ? role.salary.p10 : null,
        salary_p50_inr: role.salary?.sufficient ? role.salary.p50 : null,
        salary_p90_inr: role.salary?.sufficient ? role.salary.p90 : null,
        salary_support: role.salary?.n_support ?? 0,
        matched_skills: role.why.matched_skills.map((s) => s.label).join('; '),
        missing_skills: role.top_missing.map((s) => s.label).join('; '),
        caveat: 'Historical postings; skill alignment is not a hiring probability. Salary estimates require sufficient disclosed support.',
    })));

    return <section aria-label="Role comparison" className="space-y-4 border-y py-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
                <h2 className="text-lg font-semibold">Compare your options</h2>
                <p className="text-xs text-muted-foreground">{roles.length} of 3 roles selected{example ? ' · Saved example' : ''}</p>
            </div>
            <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" onClick={exportComparison}><DownloadSimple size={15} /> Export CSV</Button>
                <Button size="sm" variant="ghost" onClick={onClear}>Clear</Button>
            </div>
        </div>
        <div className="overflow-x-auto rounded-lg border" tabIndex={0} role="region" aria-label="Role comparison table">
            <table className="w-full min-w-[580px] table-fixed text-left text-sm">
                <caption className="sr-only">Selected roles, posting support, posted salary ranges, and skill gaps</caption>
                <thead className="bg-muted/50">
                    <tr><th scope="col" className="w-32 p-4 text-xs font-medium text-muted-foreground">Decision factors</th>
                        {roles.map((role) => <th key={role.occupation_uri} scope="col" className="p-4 align-top">
                            <div className="flex items-start justify-between gap-2">
                                <span className="break-words font-semibold capitalize">{role.occupation_label}</span>
                                <button type="button" className="shrink-0 rounded p-1 hover:bg-muted focus-visible:outline focus-visible:outline-2" title={`Remove ${role.occupation_label}`} aria-label={`Remove ${role.occupation_label} from comparison`} onClick={() => onRemove(role.occupation_uri)}><X size={15} /></button>
                            </div>
                        </th>)}
                    </tr>
                </thead>
                <tbody className="divide-y">
                    <tr><th scope="row" className="p-4 text-xs font-medium">Matched postings</th>{roles.map((role) => <td key={role.occupation_uri} className="p-4 tabular-nums">{num(role.postings)}</td>)}</tr>
                    <tr><th scope="row" className="p-4 text-xs font-medium">Annual posted pay</th>{roles.map((role) => <td key={role.occupation_uri} className="p-4 align-top"><SalaryRange salary={role.salary} /></td>)}</tr>
                    <tr><th scope="row" className="p-4 text-xs font-medium">Skills in common</th>{roles.map((role) => <td key={role.occupation_uri} className="p-4 align-top"><div className="flex flex-wrap gap-1.5">{role.why.matched_skills.length ? role.why.matched_skills.map((skill) => <SkillChip key={skill.uri} label={skill.label} tone="have" />) : <span className="text-muted-foreground">None listed</span>}</div></td>)}</tr>
                    <tr><th scope="row" className="p-4 text-xs font-medium">Skills to consider</th>{roles.map((role) => <td key={role.occupation_uri} className="p-4 align-top"><div className="flex flex-wrap gap-1.5">{role.top_missing.length ? role.top_missing.map((skill) => <SkillChip key={skill.uri} label={skill.label} tone="gap" />) : <span className="text-muted-foreground">No gaps listed</span>}</div></td>)}</tr>
                    <tr><th scope="row" className="p-4 text-xs font-medium">Evidence</th>{roles.map((role) => <td key={role.occupation_uri} className="p-4"><WhyDrawer title={role.occupation_label} subtitle="Why this role matches" why={role.why} /></td>)}</tr>
                </tbody>
            </table>
        </div>
    </section>;
}
