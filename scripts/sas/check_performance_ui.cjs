// Local-only browser verification. Screenshots contain private evaluation data.
const { createRequire } = require('node:module');
const path = require('node:path');
const fs = require('node:fs/promises');
const runtime = process.env.CODEX_NODE_MODULES;
if (!runtime) throw new Error('Set CODEX_NODE_MODULES to the bundled node_modules directory');
const { chromium } = createRequire(path.join(runtime, 'package.json'))('playwright');

(async () => {
    const browser = await chromium.launch({ headless: true, channel: 'msedge' });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const out = path.resolve('private_sas/performance_ui');
    await fs.mkdir(out, { recursive: true });
    const capture = async name => {
        await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
        await page.screenshot({ path: path.join(out, name), fullPage: true });
    };
    try {
        await page.goto('http://127.0.0.1:3000/model-performance');
        await page.getByText('40.7%', { exact: true }).waitFor({ timeout: 90000 });
        await page.getByRole('heading', { name: 'Test confusion matrix', exact: true }).waitFor();
        await capture('desktop.png');
        await page.getByLabel('Row percentages').check();
        if (!await page.getByLabel('Row percentages').isChecked()) throw new Error('Normalization control failed');
        await page.getByRole('tab', { name: 'Calibration', exact: true }).click();
        await page.getByRole('heading', { name: 'Token handling sensitivity', exact: true }).waitFor();
        await page.getByRole('rowheader', { name: 'Permissive' }).waitFor();
        await page.getByLabel('Group by').selectOption('quality_flag');
        await page.getByText('Insufficient support', { exact: true }).waitFor();
        await capture('calibration.png');
        await page.getByRole('tab', { name: 'Cohort research', exact: true }).click();
        await page.getByText('0.911', { exact: true }).waitFor();
        await page.getByText('0.968', { exact: true }).waitFor();
        await capture('cohorts.png');
        await page.setViewportSize({ width: 390, height: 844 });
        await page.getByRole('tab', { name: 'Salary model', exact: true }).click();
        await capture('mobile.png');
        await page.screenshot({ path: path.join(out, 'mobile-viewport.png') });
        if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) throw new Error('Page overflows mobile viewport');
        await page.getByRole('tab', { name: 'Calibration', exact: true }).click();
        await capture('mobile-calibration.png');
        if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) throw new Error('Calibration overflows mobile viewport');
        await page.route('**/sas/performance', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Private evaluation unavailable' }) }));
        await page.reload();
        await page.getByRole('heading', { name: 'Evaluation unavailable' }).waitFor();
        if (await page.getByText('40.7%', { exact: true }).count()) throw new Error('Stale metrics visible after unavailable response');
        await page.screenshot({ path: path.join(out, 'unavailable.png'), fullPage: true });
        if (errors.length) throw new Error(errors.join('\n'));
        console.log('Desktop, mobile, tabs, normalization, subgroup filters and unavailable state passed.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
