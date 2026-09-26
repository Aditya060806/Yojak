import Link from 'next/link';
import { ArrowRight, Compass } from '@phosphor-icons/react/dist/ssr';
import { Button } from '@/components/ui/button';

export default function NotFound() {
    return <main className="container flex min-h-[75dvh] flex-col items-center justify-center gap-5 text-center">
        <Compass size={44} weight="light" className="text-primary" />
        <p className="text-xs font-medium text-muted-foreground">Yojak / 404</p>
        <h1 className="text-3xl font-semibold">This path doesn&apos;t lead anywhere.</h1>
        <p className="max-w-md text-sm leading-relaxed text-muted-foreground">The page may have moved. Find your next opportunity from your workspace.</p>
        <Button asChild><Link href="/">Back to Yojak <ArrowRight size={16} /></Link></Button>
    </main>;
}
