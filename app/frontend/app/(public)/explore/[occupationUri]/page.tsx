'use client';

import Link from 'next/link';
import { CaretRight } from '@phosphor-icons/react';
import { OccupationDetail } from '@/components/features/occupations/occupation-detail';
import { LiveOnly, useStaticMode } from '@/components/yojak/bits';

export default function OccupationDetailPage({ params }: { params: { occupationUri: string } }) {
    const demo = useStaticMode();
    return (
        <div className="container space-y-6 pt-8">
            <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Link href="/explore" className="hover:text-foreground">Explore</Link>
                <CaretRight size={12} />
                <span className="text-foreground">Occupation</span>
            </nav>
            {demo ? <LiveOnly what="Occupation profiles" /> : <OccupationDetail occupationUri={params.occupationUri} />}
        </div>
    );
}
