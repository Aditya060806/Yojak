'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';
import * as Tooltip from '@radix-ui/react-tooltip';
import { MotionConfig } from 'motion/react';
import { ReactNode, useState } from 'react';

export default function Providers({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
        () =>
            new QueryClient({
                defaultOptions: {
                    queries: { staleTime: 5 * 60 * 1000, retry: 1, refetchOnWindowFocus: false },
                },
            }),
    );

    return (
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
            <MotionConfig reducedMotion="user">
                <Tooltip.Provider delayDuration={200}>
                    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
                </Tooltip.Provider>
            </MotionConfig>
        </ThemeProvider>
    );
}
