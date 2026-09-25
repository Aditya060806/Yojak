'use client';

/**
 * The skill constellation: the most-listed ESCO skills in Indian postings, joined when
 * postings list them together far more often than chance (lift), plus the occupations
 * they characterise. Data comes from /graph/constellation; layout is ForceAtlas2, drawn
 * with sigma (WebGL). Hovering a node lights up its neighbourhood.
 */

import { useEffect, useRef, useState } from 'react';
import { useTheme } from 'next-themes';
import { useQuery } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'motion/react';
import Graph from 'graphology';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import type Sigma from 'sigma';
import { yojak, type Constellation as Data, type ConstellationNode } from '@/services/yojak';
import { num } from '@/lib/format';
import { cn } from '@/lib/utils';

type Palette = { skill: string; occupation: string; edge: string; edgeStrong: string; dim: string; label: string; card: string; border: string };

/** CSS token "184 72% 27%" -> "rgba(r, g, b, a)" (sigma only parses hex and rgb). */
function tokenColor(name: string, alpha = 1): string {
    const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    const [h, s, l] = raw.split(/\s+/).map((v) => parseFloat(v));
    if ([h, s, l].some((v) => Number.isNaN(v))) return `rgba(128, 128, 128, ${alpha})`;
    const S = s / 100, L = l / 100;
    const k = (n: number) => (n + h / 30) % 12;
    const a = S * Math.min(L, 1 - L);
    const f = (n: number) => L - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
    return `rgba(${Math.round(f(0) * 255)}, ${Math.round(f(8) * 255)}, ${Math.round(f(4) * 255)}, ${alpha})`;
}

function palette(): Palette {
    return {
        skill: tokenColor('--viz-4'),
        occupation: tokenColor('--caution'),
        edge: tokenColor('--muted-foreground', 0.16),
        edgeStrong: tokenColor('--primary', 0.75),
        dim: tokenColor('--muted-foreground', 0.18),
        label: tokenColor('--foreground', 0.86),
        card: tokenColor('--card'),
        border: tokenColor('--border'),
    };
}

/** Deterministic pseudo-random start positions so the layout is the same on every visit. */
function seeded(i: number) {
    const x = Math.sin(i * 12.9898) * 43758.5453;
    return x - Math.floor(x);
}

function buildGraph(data: Data): Graph {
    const g = new Graph({ type: 'undirected', multi: false });
    const maxP = Math.max(...data.nodes.map((n) => n.postings), 1);
    data.nodes.forEach((n, i) => {
        const angle = seeded(i) * Math.PI * 2;
        const r = 0.2 + seeded(i + 999) * 0.8;
        g.addNode(n.id, {
            label: n.label,
            kind: n.kind,
            postings: n.postings,
            uri: n.uri,
            x: Math.cos(angle) * r,
            y: Math.sin(angle) * r,
            size: (n.kind === 'occupation' ? 3.2 : 2.2) + 9 * Math.sqrt(n.postings / maxP),
        });
    });
    for (const e of data.edges) {
        if (!g.hasNode(e.source) || !g.hasNode(e.target) || g.hasEdge(e.source, e.target)) continue;
        g.addEdge(e.source, e.target, { weight: Math.max(0.1, e.weight), postings: e.postings, kind: e.kind });
    }
    // Isolated nodes drift to the rim; drop them so the picture shows structure, not noise.
    g.forEachNode((n) => { if (g.degree(n) === 0) g.dropNode(n); });
    forceAtlas2.assign(g, {
        iterations: 400,
        settings: { ...forceAtlas2.inferSettings(g), gravity: 1.2, scalingRatio: 6, barnesHutOptimize: true, strongGravityMode: false },
    });
    return g;
}

export function Constellation({ className, interactive = true }: { className?: string; interactive?: boolean }) {
    const container = useRef<HTMLDivElement>(null);
    const sigmaRef = useRef<Sigma | null>(null);
    const { resolvedTheme } = useTheme();
    const [hovered, setHovered] = useState<(ConstellationNode & { degree: number }) | null>(null);
    const { data, isError } = useQuery({ queryKey: ['constellation'], queryFn: yojak.constellation, staleTime: Infinity });

    useEffect(() => {
        if (!data || !container.current) return;
        let disposed = false;
        let renderer: Sigma | null = null;
        (async () => {
            const { default: SigmaCtor } = await import('sigma');
            if (disposed || !container.current) return;
            const g = buildGraph(data);
            const pal = palette();
            let hover: string | null = null;
            let neighbours = new Set<string>();
            renderer = new SigmaCtor(g, container.current, {
                renderLabels: true,
                labelFont: getComputedStyle(document.body).fontFamily || 'system-ui, sans-serif',
                labelSize: 12,
                labelWeight: '500',
                labelColor: { color: pal.label },
                labelDensity: 0.35,
                labelGridCellSize: 90,
                labelRenderedSizeThreshold: 7,
                defaultEdgeColor: pal.edge,
                zIndex: true,
                stagePadding: 24,
                minCameraRatio: 0.35,
                maxCameraRatio: 1.6,
                enableCameraZooming: interactive,
                enableCameraPanning: interactive,
                defaultDrawNodeHover: (ctx, d, settings) => {
                    const size = settings.labelSize;
                    ctx.font = `600 ${size}px ${settings.labelFont}`;
                    const text = d.label ?? '';
                    const w = ctx.measureText(text).width + 14;
                    const h = size + 10;
                    const x = d.x + d.size + 6, y = d.y - h / 2;
                    ctx.fillStyle = pal.card;
                    ctx.strokeStyle = pal.border;
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.roundRect(x, y, w, h, 6);
                    ctx.fill();
                    ctx.stroke();
                    ctx.fillStyle = pal.label;
                    ctx.fillText(text, x + 7, d.y + size / 3);
                },
                nodeReducer: (node, attrs) => {
                    const base = { ...attrs, color: attrs.kind === 'occupation' ? pal.occupation : pal.skill };
                    if (!hover) return base;
                    if (node === hover) return { ...base, highlighted: true, zIndex: 2 };
                    if (neighbours.has(node)) return { ...base, zIndex: 1, forceLabel: true };
                    return { ...base, color: pal.dim, label: '', zIndex: 0 };
                },
                edgeReducer: (edge, attrs) => {
                    if (!hover) return { ...attrs, color: pal.edge, size: 0.6 };
                    const [s, t] = g.extremities(edge);
                    return s === hover || t === hover
                        ? { ...attrs, color: pal.edgeStrong, size: 1.4, zIndex: 1 }
                        : { ...attrs, hidden: true };
                },
            });
            renderer.on('enterNode', ({ node }) => {
                hover = node;
                neighbours = new Set(g.neighbors(node));
                const a = g.getNodeAttributes(node);
                setHovered({ id: node, label: a.label, kind: a.kind, uri: a.uri, postings: a.postings, degree: g.degree(node) });
                renderer?.refresh({ skipIndexation: true });
            });
            renderer.on('leaveNode', () => {
                hover = null;
                neighbours = new Set();
                setHovered(null);
                renderer?.refresh({ skipIndexation: true });
            });
            sigmaRef.current = renderer;
        })();
        return () => {
            disposed = true;
            renderer?.kill();
            sigmaRef.current = null;
        };
        // Re-create on theme change so every colour comes from the active tokens.
    }, [data, resolvedTheme, interactive]);

    return (
        <div className={cn('relative', className)}>
            <div ref={container} className="absolute inset-0" aria-label="Network of skills and occupations in Indian job postings" role="img" />
            {!data && !isError && (
                <div className="absolute inset-0 flex items-center justify-center">
                    <motion.div
                        className="h-24 w-24 rounded-full border border-primary/30"
                        animate={{ scale: [0.9, 1.1, 0.9], opacity: [0.4, 0.9, 0.4] }}
                        transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
                    />
                </div>
            )}
            {isError && (
                <div className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
                    Start the API to see the skill network.
                </div>
            )}
            <AnimatePresence>
                {hovered && (
                    <motion.div
                        key={hovered.id}
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 6 }}
                        transition={{ duration: 0.15 }}
                        className="pointer-events-none absolute bottom-4 left-4 max-w-[280px] rounded-lg border bg-card/95 px-3.5 py-2.5 text-sm shadow-lg backdrop-blur"
                    >
                        <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                            {hovered.kind === 'occupation' ? 'ESCO occupation' : 'ESCO skill'}
                        </p>
                        <p className="font-medium leading-snug">{hovered.label}</p>
                        <p className="mt-1 text-xs text-muted-foreground tabular">
                            {num(hovered.postings)} postings · {hovered.degree} links
                        </p>
                    </motion.div>
                )}
            </AnimatePresence>
            {data && (
                <div className="pointer-events-none absolute right-4 top-4 flex gap-3 rounded-md border bg-card/80 px-2.5 py-1.5 text-[11px] text-muted-foreground backdrop-blur">
                    <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-viz-4" /> skill</span>
                    <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-caution" /> occupation</span>
                </div>
            )}
        </div>
    );
}
