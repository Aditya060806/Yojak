import type { Metadata, Viewport } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import { Noto_Sans_Devanagari, Noto_Sans_Gurmukhi } from 'next/font/google';
import './globals.css';
import Providers from './providers';
import { cn } from '@/lib/utils';

const deva = Noto_Sans_Devanagari({ subsets: ['devanagari'], variable: '--font-deva', display: 'swap', weight: ['400', '500', '600'] });
const guru = Noto_Sans_Gurmukhi({ subsets: ['gurmukhi'], variable: '--font-guru', display: 'swap', weight: ['400', '500', '600'] });

export const metadata: Metadata = {
    title: { default: 'Yojak · skill and job intelligence for India', template: '%s · Yojak' },
    description:
        'Yojak links Indian job postings to the ESCO skills taxonomy to show which roles fit you, the fewest skills that open the most jobs, and honest salary ranges.',
};

export const viewport: Viewport = {
    themeColor: [
        { media: '(prefers-color-scheme: light)', color: '#fafaf9' },
        { media: '(prefers-color-scheme: dark)', color: '#0c0c0e' },
    ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" suppressHydrationWarning>
            <body className={cn('min-h-[100dvh] font-sans', GeistSans.variable, GeistMono.variable, deva.variable, guru.variable)}>
                <Providers>{children}</Providers>
            </body>
        </html>
    );
}
