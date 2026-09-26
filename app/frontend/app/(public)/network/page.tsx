'use client';

import dynamic from 'next/dynamic';
import { PageIntro } from '@/components/yojak/bits';

const Constellation = dynamic(() => import('@/components/yojak/constellation').then((m) => m.Constellation), { ssr: false });

export default function NetworkPage() {
    return <div className="container">
        <PageIntro title="Skill intelligence" lead="Explore the relationships between skills and occupations in Indian job postings." />
        <div className="mb-4 flex flex-wrap gap-5 text-xs text-muted-foreground"><span className="inline-flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-primary" />Skills</span><span className="inline-flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-amber-600" />Occupations</span><span>Historical posting snapshot</span></div>
        <Constellation expanded />
    </div>;
}
