import { API_URL, ApiError } from '@/lib/api';

/**
 * Hosted-demo mode. The Vercel deployment has no Python API (it needs Neo4j and ~1 GB of
 * models), so read-only views fall back to JSON snapshots exported by
 * scripts/export_static.py into public/data/. Interactive views show precomputed example
 * runs, labelled as such. Set NEXT_PUBLIC_STATIC_MODE=1 to force it, 0 to disable it.
 */
export function isStaticMode(): boolean {
    const forced = process.env.NEXT_PUBLIC_STATIC_MODE;
    if (forced === '1') return true;
    if (forced === '0') return false;
    if (typeof window === 'undefined') return false;
    const apiIsLocal = /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?/.test(API_URL);
    const pageIsLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);
    return apiIsLocal && !pageIsLocal;
}

export async function staticGet<T>(path: string): Promise<T> {
    const res = await fetch(`/data/${path}`);
    if (!res.ok) throw new ApiError(res.status === 404 ? 'Not in this snapshot' : `Snapshot request failed (${res.status})`, res.status);
    return (await res.json()) as T;
}

/** Try the live API; when it is unreachable (or in hosted-demo mode), read the snapshot instead. */
export async function withSnapshot<T>(live: () => Promise<T>, path: string): Promise<T> {
    if (isStaticMode()) return staticGet<T>(path);
    try {
        return await live();
    } catch (e) {
        if (e instanceof ApiError && e.status === null) return staticGet<T>(path);
        throw e;
    }
}

export const slug = (s: string | null | undefined) => (s ? s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') : 'all');
