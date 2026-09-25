import { SiteFooter, SiteHeader } from '@/components/yojak/shell';

export default function PublicLayout({ children }: { children: React.ReactNode }) {
    return (
        <div className="flex min-h-[100dvh] flex-col">
            <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2">
                Skip to content
            </a>
            <SiteHeader />
            <main id="main" className="flex-1">{children}</main>
            <SiteFooter />
        </div>
    );
}
