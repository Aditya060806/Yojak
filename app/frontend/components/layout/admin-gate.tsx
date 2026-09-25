'use client';

import { LiveOnly, useStaticMode } from '@/components/yojak/bits';

/** Admin tools read and write the live graph; the hosted demo has no API. */
export function AdminGate({ children }: { children: React.ReactNode }) {
    const demo = useStaticMode();
    return demo ? <LiveOnly what="The admin area" /> : <>{children}</>;
}
