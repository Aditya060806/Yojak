'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { geoMercator, geoPath } from 'd3-geo';
import type { FeatureCollection, Geometry } from 'geojson';
import { cn } from '@/lib/utils';

const W = 280, H = 310;

/** Decorative outline of India's states, drawn from the same boundary file as the Workforce map. */
export function IndiaSilhouette({ className }: { className?: string }) {
    const { data: geo } = useQuery({
        queryKey: ['india-geo'],
        queryFn: async () => (await fetch('/geo/india-states.json')).json() as Promise<FeatureCollection<Geometry, { name: string }>>,
        staleTime: Infinity,
    });
    const paths = useMemo(() => {
        if (!geo) return [];
        const path = geoPath(geoMercator().fitSize([W, H], geo));
        return geo.features.map((f, i) => ({ key: `${f.properties.name}-${i}`, d: path(f) ?? '' }));
    }, [geo]);
    return (
        <svg viewBox={`0 0 ${W} ${H}`} className={cn('text-primary', className)} aria-hidden>
            {paths.map((p, i) => (
                <path key={p.key} d={p.d} className="stroke-card stroke-[0.8]" fill="currentColor" fillOpacity={0.12 + (i % 5) * 0.06} />
            ))}
        </svg>
    );
}
