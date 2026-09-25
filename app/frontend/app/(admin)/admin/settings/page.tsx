'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTheme } from 'next-themes';
import { CheckCircle, Warning } from '@phosphor-icons/react';
import api, { API_URL, getAdminToken, setAdminToken } from '@/lib/api';
import { Segmented } from '@/components/yojak/filters';
import { Panel, Section } from '@/components/yojak/bits';
import { Button } from '@/components/ui/button';

export default function SettingsPage() {
    const [token, setToken] = useState('');
    const [saved, setSaved] = useState(false);
    const { theme, setTheme } = useTheme();
    const [mounted, setMounted] = useState(false);
    useEffect(() => { setToken(getAdminToken() ?? ''); setMounted(true); }, []);
    const health = useQuery({
        queryKey: ['health'],
        queryFn: async () => (await api.get<{ status: string; version: string; neo4j: { connected: boolean } }>('/health')).data,
        refetchInterval: 15_000,
    });

    return (
        <div className="space-y-10">
            <div className="space-y-1.5">
                <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
                <p className="text-muted-foreground">Settings for this browser tab. Nothing here is sent anywhere except the Yojak API.</p>
            </div>

            <Section title="Admin token" description="Needed for write actions (occupation notes, gold labels). Kept in this tab's session storage only; closing the tab forgets it.">
                <Panel className="flex flex-col gap-3 sm:flex-row sm:items-end">
                    <div className="flex-1 space-y-1.5">
                        <label htmlFor="token" className="text-sm font-medium">ADMIN_TOKEN</label>
                        <input id="token" type="password" autoComplete="off" value={token}
                               onChange={(e) => { setToken(e.target.value); setSaved(false); }}
                               placeholder="The value of ADMIN_TOKEN in the server's .env"
                               className="h-10 w-full rounded-md border border-input bg-card px-3 font-mono text-sm" />
                    </div>
                    <div className="flex gap-2">
                        <Button onClick={() => { setAdminToken(token || null); setSaved(true); }}>Save</Button>
                        <Button variant="outline" onClick={() => { setAdminToken(null); setToken(''); setSaved(true); }}>Forget</Button>
                    </div>
                </Panel>
                {saved && <p className="text-sm text-muted-foreground">{token ? 'Saved for this tab.' : 'Token removed.'}</p>}
            </Section>

            <Section title="API connection">
                <Panel className="space-y-2 text-sm">
                    <p><span className="text-muted-foreground">Address: </span><code className="font-mono">{API_URL}</code></p>
                    <p className="flex items-center gap-2">
                        {health.data ? <CheckCircle size={16} weight="fill" className="text-primary" /> : <Warning size={16} className="text-caution" />}
                        {health.isLoading ? 'Checking…' : health.data ? `Yojak API ${health.data.version}: ${health.data.status} · Neo4j ${health.data.neo4j.connected ? 'connected' : 'not connected'}` : 'API not reachable'}
                    </p>
                    <p className="text-xs text-muted-foreground">Set NEXT_PUBLIC_API_URL in app/frontend/.env.local to point the app at another server.</p>
                </Panel>
            </Section>

            <Section title="Appearance">
                {mounted && (
                    <Segmented<string> label="Theme" value={theme ?? 'system'} onChange={setTheme}
                                       options={[{ value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }, { value: 'system', label: 'System' }]} />
                )}
            </Section>
        </div>
    );
}
