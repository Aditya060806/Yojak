import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
    'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap transition-colors',
    {
        variants: {
            variant: {
                default: 'border-transparent bg-primary text-primary-foreground',
                secondary: 'border-transparent bg-secondary text-secondary-foreground',
                accent: 'border-transparent bg-accent text-accent-foreground',
                destructive: 'border-transparent bg-destructive text-destructive-foreground',
                outline: 'text-foreground',
                muted: 'border-transparent bg-muted text-muted-foreground',
                // Honesty labels: always visible, never decorative.
                synthetic: 'border-caution/40 bg-caution-muted text-caution-foreground uppercase tracking-wide text-[10px]',
                proxy: 'border-caution/40 bg-caution-muted text-caution-foreground',
            },
        },
        defaultVariants: { variant: 'default' },
    },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
    return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
