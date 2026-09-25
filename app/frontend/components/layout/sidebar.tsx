'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ArrowLeft, Gauge, GearSix, List, Note, Pulse, Tag, X } from '@phosphor-icons/react';
import { Logo, ThemeToggle } from '@/components/yojak/shell';
import { cn } from '@/lib/utils';

const ROUTES = [
    { href: '/admin', label: 'Overview', icon: Gauge },
    { href: '/admin/health', label: 'System health', icon: Pulse },
    { href: '/admin/labelling', label: 'Gold labelling', icon: Tag },
    { href: '/admin/notes', label: 'Occupation notes', icon: Note },
    { href: '/admin/settings', label: 'Settings', icon: GearSix },
];

export function Sidebar() {
    const pathname = usePathname();
    const [open, setOpen] = useState(false);
    useEffect(() => setOpen(false), [pathname]);

    return (
        <>
            <div className="sticky top-0 z-40 flex h-14 items-center justify-between border-b bg-background/85 px-4 backdrop-blur lg:hidden">
                <Logo />
                <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label="Admin menu"
                        className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-muted">
                    {open ? <X size={20} /> : <List size={20} />}
                </button>
            </div>
            {open && <div className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm lg:hidden" onClick={() => setOpen(false)} />}
            <aside
                className={cn(
                    'fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r bg-card px-3 py-5 transition-transform duration-300 lg:sticky lg:top-0 lg:h-[100dvh] lg:translate-x-0',
                    open ? 'translate-x-0' : '-translate-x-full',
                )}
            >
                <div className="flex items-center justify-between px-2">
                    <Logo />
                    <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Admin</span>
                </div>
                <nav className="mt-8 space-y-0.5" aria-label="Admin">
                    {ROUTES.map(({ href, label, icon: Icon }) => {
                        const active = pathname === href;
                        return (
                            <Link key={href} href={href}
                                  className={cn('flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                                      active ? 'bg-accent font-medium text-accent-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>
                                <Icon size={18} weight={active ? 'fill' : 'regular'} /> {label}
                            </Link>
                        );
                    })}
                </nav>
                <div className="mt-auto flex items-center justify-between px-2">
                    <Link href="/" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
                        <ArrowLeft size={14} /> Back to Yojak
                    </Link>
                    <ThemeToggle />
                </div>
            </aside>
        </>
    );
}
