/**
 * A small Markdown renderer for the reports Yojak generates itself (EVALUATION.md,
 * phase0_audit.md): headings, paragraphs, lists, pipe tables, fenced code, block quotes,
 * **bold**, *italic*, `code`, [links](url) and <sub>. Input is our own generated text; it
 * is rendered as React elements, never as raw HTML.
 */

import * as React from 'react';
import { cn } from '@/lib/utils';

function inline(text: string, key = 0): React.ReactNode[] {
    const out: React.ReactNode[] = [];
    const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*|\[[^\]]+\]\([^)]+\)|<sub>[\s\S]*?<\/sub>)/g;
    let last = 0;
    let m: RegExpExecArray | null;
    let i = 0;
    while ((m = re.exec(text))) {
        if (m.index > last) out.push(text.slice(last, m.index));
        const t = m[0];
        const k = `${key}-${i++}`;
        if (t.startsWith('**')) out.push(<strong key={k} className="font-semibold text-foreground">{inline(t.slice(2, -2), i)}</strong>);
        else if (t.startsWith('`')) out.push(<code key={k} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.86em]">{t.slice(1, -1)}</code>);
        else if (t.startsWith('<sub>')) out.push(<span key={k} className="block text-xs text-muted-foreground">{inline(t.slice(5, -6), i)}</span>);
        else if (t.startsWith('[')) {
            const [, label, href] = t.match(/\[([^\]]+)\]\(([^)]+)\)/) ?? [];
            const safe = /^(https?:|\/|#|\.\.?\/)/.test(href ?? '') ? href : undefined;
            out.push(<a key={k} href={safe} className="text-primary underline-offset-2 hover:underline" target={safe?.startsWith('http') ? '_blank' : undefined} rel="noreferrer">{label}</a>);
        } else out.push(<em key={k}>{inline(t.slice(1, -1), i)}</em>);
        last = m.index + t.length;
    }
    if (last < text.length) out.push(text.slice(last));
    return out;
}

const cells = (line: string) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());

export function Markdown({ source, className }: { source: string; className?: string }) {
    const lines = source.replace(/\r\n/g, '\n').split('\n');
    const blocks: React.ReactNode[] = [];
    let i = 0;
    while (i < lines.length) {
        const line = lines[i];
        const key = `b${i}`;
        if (!line.trim()) { i++; continue; }
        if (line.startsWith('```')) {
            const body: string[] = [];
            i++;
            while (i < lines.length && !lines[i].startsWith('```')) body.push(lines[i++]);
            i++;
            blocks.push(<pre key={key} className="overflow-x-auto rounded-lg border bg-muted/50 p-4 font-mono text-xs leading-relaxed">{body.join('\n')}</pre>);
            continue;
        }
        const h = line.match(/^(#{1,4})\s+(.*)$/);
        if (h) {
            const level = h[1].length;
            const cls = ['text-2xl font-semibold tracking-tight', 'mt-10 text-xl font-semibold tracking-tight border-t pt-8', 'mt-6 text-base font-semibold', 'mt-4 text-sm font-semibold'][level - 1];
            const Tag = (`h${Math.min(level + 1, 6)}`) as keyof JSX.IntrinsicElements;
            const id = h[2].toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
            blocks.push(<Tag key={key} id={id} className={cls}>{inline(h[2])}</Tag>);
            i++;
            continue;
        }
        if (line.trim().startsWith('|') && i + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(lines[i + 1])) {
            const head = cells(line);
            const align = cells(lines[i + 1]).map((c) => (c.endsWith(':') ? 'text-right' : 'text-left'));
            i += 2;
            const rows: string[][] = [];
            while (i < lines.length && lines[i].trim().startsWith('|')) rows.push(cells(lines[i++]));
            blocks.push(
                <div key={key} className="overflow-x-auto rounded-lg border">
                    <table className="w-full text-sm">
                        {head.some(Boolean) && (
                            <thead className="bg-muted/50 text-xs text-muted-foreground">
                                <tr>{head.map((c, j) => <th key={j} className={cn('px-3 py-2 font-medium', align[j])}>{inline(c)}</th>)}</tr>
                            </thead>
                        )}
                        <tbody className="divide-y">
                            {rows.map((r, ri) => (
                                <tr key={ri}>{r.map((c, j) => <td key={j} className={cn('tabular px-3 py-2 align-top', align[j])}>{inline(c)}</td>)}</tr>
                            ))}
                        </tbody>
                    </table>
                </div>,
            );
            continue;
        }
        if (line.startsWith('>')) {
            const body: string[] = [];
            while (i < lines.length && lines[i].startsWith('>')) body.push(lines[i++].replace(/^>\s?/, ''));
            blocks.push(<blockquote key={key} className="border-l-2 border-primary/50 pl-4 text-sm text-muted-foreground">{inline(body.join(' '))}</blockquote>);
            continue;
        }
        if (/^\s*[-*]\s+/.test(line)) {
            const items: string[] = [];
            while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*[-*]\s+/, ''));
            blocks.push(<ul key={key} className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed">{items.map((t, j) => <li key={j}>{inline(t)}</li>)}</ul>);
            continue;
        }
        const para: string[] = [];
        while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|```|>|\s*[-*]\s+|\s*\|)/.test(lines[i])) para.push(lines[i++]);
        if (!para.length) { i++; continue; }
        blocks.push(<p key={key} className="text-sm leading-relaxed text-foreground/90">{inline(para.join(' '))}</p>);
    }
    return <div className={cn('space-y-4', className)}>{blocks}</div>;
}
