import { Sidebar } from '@/components/layout/sidebar';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
    return (
        <div className="min-h-[100dvh] lg:flex">
            <Sidebar />
            <main className="min-w-0 flex-1 px-4 py-8 md:px-8 lg:px-10 lg:py-10">
                <div className="mx-auto max-w-6xl">{children}</div>
            </main>
        </div>
    );
}
