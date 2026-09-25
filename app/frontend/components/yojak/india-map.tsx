'use client';

/**
 * India choropleth (d3-geo, plain SVG). State boundaries: DataMeet / Survey of India
 * derived GeoJSON, simplified by ml_pipeline/supply/geo_boundaries.py.
 */

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { geoMercator, geoPath } from 'd3-geo';
import { scaleQuantile } from 'd3-scale';
import type { Feature, FeatureCollection, Geometry } from 'geojson';
import { motion } from 'motion/react';
import { cn } from '@/lib/utils';

type Props = { name: string; source_name?: string };

const W = 560, H = 620;
const FILLS = ['fill-viz-1', 'fill-viz-2', 'fill-viz-3', 'fill-viz-4', 'fill-viz-5'];
const SWATCH = ['bg-viz-1', 'bg-viz-2', 'bg-viz-3', 'bg-viz-4', 'bg-viz-5'];

export function IndiaMap({ values, format, selected, onSelect, label, className }: {
    values: Record<string, number | null | undefined>;
    format: (v: number) => string;
    selected: string | null;
    onSelect: (state: string | null) => void;
    label: string;
    className?: string;
}) {
    const { data: geo } = useQuery({
        queryKey: ['india-geo'],
        queryFn: async () => (await fetch('/geo/india-states.json')).json() as Promise<FeatureCollection<Geometry, Props>>,
        staleTime: Infinity,
    });
    const [hover, setHover] = useState<{ name: string; x: number; y: number } | null>(null);

    const paths = useMemo(() => {
        if (!geo) return [];
        const proj = geoMercator().fitSize([W, H], geo);
        const path = geoPath(proj);
        return geo.features.map((f: Feature<Geometry, Props>, i) => ({ key: `${f.properties.name}-${i}`, name: f.properties.name, d: path(f) ?? '' }));
    }, [geo]);

    const finite = Object.values(values).filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
    const scale = useMemo(() => scaleQuantile<number>().domain(finite.length ? finite : [0, 1]).range([0, 1, 2, 3, 4]), [finite.join(',')]); // eslint-disable-line react-hooks/exhaustive-deps
    const thresholds = scale.quantiles();

    return (
        <div className={cn('relative', className)}>
            <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={`Map of India: ${label} by state`}>
                {paths.map((p) => {
                    const v = values[p.name];
                    const has = typeof v === 'number' && Number.isFinite(v);
                    return (
                        <motion.path
                            key={p.key}
                            d={p.d}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ duration: 0.5 }}
                            className={cn(
                                'cursor-pointer stroke-background stroke-[0.8] transition-[fill,opacity] duration-300',
                                has ? FILLS[scale(v as number)] : 'fill-muted',
                                selected && selected !== p.name && 'opacity-45',
                                selected === p.name && 'stroke-foreground stroke-[1.6]',
                            )}
                            onMouseMove={(e) => {
                                const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
                                setHover({ name: p.name, x: e.clientX - box.left, y: e.clientY - box.top });
                            }}
                            onMouseLeave={() => setHover(null)}
                            onClick={() => onSelect(selected === p.name ? null : p.name)}
                        >
                            <title>{p.name}</title>
                        </motion.path>
                    );
                })}
            </svg>
            {hover && (
                <div
                    className="pointer-events-none absolute z-10 rounded-md border bg-popover px-2.5 py-1.5 text-xs shadow-md"
                    style={{ left: Math.min(hover.x + 12, 420), top: hover.y + 12 }}
                >
                    <p className="font-medium">{hover.name}</p>
                    <p className="tabular text-muted-foreground">
                        {typeof values[hover.name] === 'number' && Number.isFinite(values[hover.name])
                            ? `${label}: ${format(values[hover.name] as number)}` : 'No value'}
                    </p>
                </div>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
                <span>{label}</span>
                {SWATCH.map((c, i) => (
                    <span key={c} className="flex items-center gap-1">
                        <span className={cn('h-2.5 w-4 rounded-sm', c)} />
                        {i === 0 ? `< ${fmt(thresholds[0], format)}` : i === 4 ? `≥ ${fmt(thresholds[3], format)}` : `${fmt(thresholds[i - 1], format)}–${fmt(thresholds[i], format)}`}
                    </span>
                ))}
                <span className="flex items-center gap-1"><span className="h-2.5 w-4 rounded-sm bg-muted" /> no value</span>
            </div>
        </div>
    );
}

function fmt(v: number | undefined, format: (v: number) => string) {
    return v === undefined || !Number.isFinite(v) ? '–' : format(v);
}
