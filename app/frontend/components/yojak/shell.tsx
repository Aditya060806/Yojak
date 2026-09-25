'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';
import { AnimatePresence, motion } from 'motion/react';
import { List, Moon, Sun, X } from '@phosphor-icons/react';
import { cn } from '@/lib/utils';

export const NAV = [
    { href: '/student', label: 'Students' },
    { href: '/recruiter', label: 'Recruiters' },
    { href: '/institution', label: 'Institutions' },
    { href: '/workforce', label: 'Workforce' },
    { href: '/evidence', label: 'Evidence' },
    { href: '/explore', label: 'Explore' },
];

export function Logo({ className }: { className?: string }) {
    return (
        <Link href="/" className={cn('group flex items-baseline gap-2', className)} aria-label="Yojak home">
            <span className="text-[19px] font-semibold tracking-tight">Yojak</span>
            <span lang="hi" className="text-sm text-muted-foreground transition-colors group-hover:text-primary">
                योजक
            </span>
        </Link>
    );
}

export function ThemeToggle() {
    const { resolvedTheme, setTheme } = useTheme();
    const [mounted, setMounted] = useState(false);
    useEffect(() => setMounted(true), []);
    const dark = mounted && resolvedTheme === 'dark';
    return (
        <button
            type="button"
            onClick={() => setTheme(dark ? 'light' : 'dark')}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
        >
            {mounted ? dark ? <Sun size={18} /> : <Moon size={18} /> : <span className="h-[18px] w-[18px]" />}
        </button>
    );
}

export function SiteHeader() {
    const pathname = usePathname();
    const [open, setOpen] = useState(false);
    useEffect(() => setOpen(false), [pathname]);
    return (
        <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur-md supports-[backdrop-filter]:bg-background/70">
            <div className="container flex h-16 items-center gap-8">
                <Logo />
                <nav className="hidden items-center gap-1 lg:flex" aria-label="Main">
                    {NAV.map((n) => {
                        const active = pathname === n.href || pathname.startsWith(n.href + '/');
                        return (
                            <Link
                                key={n.href}
                                href={n.href}
                                className={cn(
                                    'relative rounded-md px-3 py-2 text-sm transition-colors',
                                    active ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
                                )}
                            >
                                {n.label}
                                {active && (
                                    <motion.span
                                        layoutId="nav-underline"
                                        className="absolute inset-x-3 -bottom-[13px] h-0.5 rounded-full bg-primary"
                                        transition={{ type: 'spring', stiffness: 400, damping: 34 }}
                                    />
                                )}
                            </Link>
                        );
                    })}
                </nav>
                <div className="ml-auto flex items-center gap-1">
                    <Link href="/admin" className="hidden rounded-md px-3 py-2 text-sm text-muted-foreground hover:text-foreground lg:block">
                        Admin
                    </Link>
                    <ThemeToggle />
                    <button
                        type="button"
                        className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-muted lg:hidden"
                        onClick={() => setOpen((o) => !o)}
                        aria-expanded={open}
                        aria-label="Menu"
                    >
                        {open ? <X size={20} /> : <List size={20} />}
                    </button>
                </div>
            </div>
            <AnimatePresence>
                {open && (
                    <motion.nav
                        initial={{ opacity: 0, y: -8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.18 }}
                        className="border-t bg-background lg:hidden"
                        aria-label="Mobile"
                    >
                        <div className="container grid gap-1 py-3">
                            {[...NAV, { href: '/admin', label: 'Admin' }].map((n) => (
                                <Link
                                    key={n.href}
                                    href={n.href}
                                    className={cn(
                                        'rounded-md px-3 py-2.5 text-[15px]',
                                        pathname.startsWith(n.href) ? 'bg-muted font-medium' : 'text-muted-foreground',
                                    )}
                                >
                                    {n.label}
                                </Link>
                            ))}
                        </div>
                    </motion.nav>
                )}
            </AnimatePresence>
        </header>
    );
}

export function SiteFooter() {
    return (
        <footer className="mt-24 border-t">
            <div className="container grid gap-8 py-12 text-sm md:grid-cols-[1.4fr_1fr_1fr]">
                <div className="space-y-3">
                    <Logo />
                    <p className="max-w-sm text-muted-foreground">
                        Built for Build for Bharat 2.0. Every number on this site is generated by a script in the repository
                        and can be traced to its source data.
                    </p>
                </div>
                <div className="space-y-2">
                    <p className="font-medium">Data</p>
                    <ul className="space-y-1.5 text-muted-foreground">
                        <li>ESCO v1.2, European Commission (CC BY 4.0)</li>
                        <li>Naukri postings via Kaggle (CC BY-NC-SA 4.0)</li>
                        <li>AISHE 2021-22  -  PLFS 2023-24  -  NCVET</li>
                        <li>GeoNames  -  Survey of India (DataMeet)</li>
                    </ul>
                </div>
                <div className="space-y-2">
                    <p className="font-medium">Project</p>
                    <ul className="space-y-1.5 text-muted-foreground">
                        <li><Link className="hover:text-foreground" href="/evidence">Evidence and limitations</Link></li>
                        <li><Link className="hover:text-foreground" href="/roadmap">ESCO roadmap to an occupation</Link></li>
                        <li><Link className="hover:text-foreground" href="/recommendations">ESCO occupation matcher (SkillAlign)</Link></li>
                        <li>Fork of SkillAlign (MIT)</li>
                        <li>Graph model from our Vyuha project</li>
                        <li>No endorsement by the EU or the Government of India is implied</li>
                    </ul>
                </div>
            </div>
        </footer>
    );
}
