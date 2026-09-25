import type { Config } from 'tailwindcss';

const hsl = (v: string) => `hsl(var(${v}) / <alpha-value>)`;

const config = {
    darkMode: ['class'],
    content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
    theme: {
        container: {
            center: true,
            padding: { DEFAULT: '1rem', md: '1.5rem', lg: '2rem' },
            screens: { '2xl': '1320px' },
        },
        extend: {
            fontFamily: {
                sans: ['var(--font-geist-sans)', 'var(--font-deva)', 'var(--font-guru)', 'system-ui', 'sans-serif'],
                mono: ['var(--font-geist-mono)', 'ui-monospace', 'monospace'],
            },
            colors: {
                border: hsl('--border'),
                input: hsl('--input'),
                ring: hsl('--ring'),
                background: hsl('--background'),
                foreground: hsl('--foreground'),
                primary: { DEFAULT: hsl('--primary'), foreground: hsl('--primary-foreground') },
                secondary: { DEFAULT: hsl('--secondary'), foreground: hsl('--secondary-foreground') },
                destructive: { DEFAULT: hsl('--destructive'), foreground: hsl('--destructive-foreground') },
                caution: { DEFAULT: hsl('--caution'), foreground: hsl('--caution-foreground'), muted: hsl('--caution-muted') },
                muted: { DEFAULT: hsl('--muted'), foreground: hsl('--muted-foreground') },
                accent: { DEFAULT: hsl('--accent'), foreground: hsl('--accent-foreground') },
                popover: { DEFAULT: hsl('--popover'), foreground: hsl('--popover-foreground') },
                card: { DEFAULT: hsl('--card'), foreground: hsl('--card-foreground') },
                viz: { 1: hsl('--viz-1'), 2: hsl('--viz-2'), 3: hsl('--viz-3'), 4: hsl('--viz-4'), 5: hsl('--viz-5') },
            },
            borderRadius: {
                lg: 'var(--radius)',
                md: 'calc(var(--radius) - 2px)',
                sm: 'calc(var(--radius) - 4px)',
                xl: 'calc(var(--radius) + 4px)',
            },
            keyframes: {
                'accordion-down': { from: { height: '0' }, to: { height: 'var(--radix-accordion-content-height)' } },
                'accordion-up': { from: { height: 'var(--radix-accordion-content-height)' }, to: { height: '0' } },
                shimmer: { '100%': { transform: 'translateX(100%)' } },
            },
            animation: {
                'accordion-down': 'accordion-down 0.2s ease-out',
                'accordion-up': 'accordion-up 0.2s ease-out',
            },
        },
    },
    plugins: [require('tailwindcss-animate')],
} satisfies Config;

export default config;
