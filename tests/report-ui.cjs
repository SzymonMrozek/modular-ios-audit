const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { execFileSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'modular-audit-ui-'));
const report = path.join(temporary, 'report.html');
execFileSync(process.env.PYTHON || 'python3', [path.join(root, 'scripts/prepare_report.py'), path.join(root, 'tests/fixtures/audit.json'), path.join(root, 'assets/report-template.html'), '--output', report, '--no-open']);
const url = pathToFileURL(report).href;
const outputs = path.join(root, 'test-results');
fs.mkdirSync(outputs, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE_PATH ? { executablePath: process.env.BROWSER_EXECUTABLE_PATH } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url);
    assert.equal(await page.locator('.principle:visible').count(), 0);
    assert.equal(await page.locator('.verdict .gate').count(), 0);
    assert.equal(await page.locator('[aria-label="Overall risk band"]').innerText(), 'LOW');
    assert.match(await page.locator('.verdict h2').innerText(), /Risk 2\.0% · 4\/65 modules involved/);
    assert.equal(await page.locator('.top-problems li').count(), 2);
    assert.equal(await page.locator('.top-problems li a').first().getAttribute('href'), '#p1-f1');
    const diff = await page.locator('.diff-file').evaluateAll(files => files.map(f => f.outerHTML));
    assert(diff.length > 0);
    const snapshot = await page.locator('.diff-file').evaluateAll(files => files.flatMap(file => {
      const before = JSON.parse(file.dataset.before).split('\n'), after = JSON.parse(file.dataset.after).split('\n');
      return [...file.querySelectorAll('.diff-line:not(.hunk)')].flatMap(row => {
        const text = row.querySelector('code').textContent;
        return [row.dataset.old && text !== before[Number(row.dataset.old) - 1] ? 'old mismatch' : '', row.dataset.new && text !== after[Number(row.dataset.new) - 1] ? 'new mismatch' : ''].filter(Boolean);
      });
    }));
    assert.deepEqual(snapshot, []);
    await page.screenshot({ path: path.join(outputs, 'overview.png') });
    if (process.argv.includes('--screenshots')) {
      fs.mkdirSync(path.join(root, 'docs'), { recursive: true });
      await page.screenshot({ path: path.join(root, 'docs/report-overview.png') });
    }
    await page.locator('[data-principle-link][href="#p2"]').click();
    assert.equal(await page.locator('.principle:visible').count(), 1);
    assert.equal(await page.locator('#p2>.minor-issues').evaluate(e => e.open), false);
    await page.locator('#p2>.minor-issues>summary').click();
    await page.locator('#p2-f1-resolved').check();
    assert.equal(await page.locator('#p2-f1').getAttribute('data-disposition'), 'resolved');
    assert.equal(await page.locator('.decision-controls input:not([type=checkbox]),.decision-controls select').count(), 0);
    await page.locator('#p2-f1-invalid').check();
    assert.equal(await page.locator('#p2-f1-resolved').isChecked(), false);
    await page.locator('#p2-f1-accepted').focus();
    await page.keyboard.press('Space');
    assert.equal(await page.locator('#p2-f1-accepted').isChecked(), true);
    assert.equal(await page.locator('#p2-f1-invalid').isChecked(), false);
    await page.locator('[data-scores-link]').click();
    assert.match(await page.locator('.verdict h2').innerText(), /Risk 1\.5%/);
    await page.reload();
    assert.equal(await page.locator('#p2-f1-accepted').isChecked(), true);
    await page.locator('.audit-controls>summary').click();
    const pendingDownload = page.waitForEvent('download');
    await page.locator('[data-export]').click();
    const download = await pendingDownload, choices = path.join(temporary, 'choices.json');
    await download.saveAs(choices);
    assert.equal(JSON.parse(fs.readFileSync(choices)).decisions['p2-f1'].status, 'accepted');
    await page.locator('[data-reset]').click();
    assert.match(await page.locator('.verdict h2').innerText(), /Risk 2\.0%/);
    await page.locator('[data-import]').setInputFiles(choices);
    await page.waitForFunction(() => document.getElementById('p2-f1-accepted').checked);
    await page.locator('[data-reset]').click();
    await page.locator('[data-module-scope]').selectOption(['Modules/PhotoEditor']);
    await page.locator('[data-apply-scope]').click();
    assert.match(await page.locator('.score-overall').innerText(), /64\/65 modules/);
    await page.locator('[data-reset]').click();
    await page.goto(url + '#p2-f1-fix');
    await page.waitForFunction(() => document.getElementById('p2-f1').open && document.querySelector('#p2>.minor-issues').open);
    await page.locator('#p2-f1-fix').waitFor({state: 'visible', timeout: 5000});
    await page.goto(url + '#p2-f1-evidence');
    await page.waitForFunction(() => document.getElementById('p2-f1-evidence').open);
    await page.locator('[data-scores-link]').click();
    await page.goBack();
    await page.waitForFunction(() => !document.getElementById('p2').hidden && document.getElementById('p2-f1-evidence').open);
    await page.setViewportSize({ width: 390, height: 844 });
    for (const hash of ['#scores', '#p2', '#p2-f1-fix']) {
      await page.goto(url + hash);
      await page.waitForTimeout(100);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, hash);
    }
    await page.screenshot({ path: path.join(outputs, 'mobile-issue.png') });
    assert.deepEqual(await page.locator('.diff-file').evaluateAll(files => files.map(f => f.outerHTML)), diff);
    assert.deepEqual(errors, []);
    const fallback = await browser.newPage({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } });
    await fallback.goto(url);
    assert.equal(await fallback.locator('.verdict .gate').count(), 0);
    assert.equal(await fallback.locator('[aria-label="Overall risk band"]').innerText(), 'LOW');
    await fallback.locator('#p2-f1>summary').click();
    await fallback.locator('#p2-f1-fix').waitFor({state: 'visible', timeout: 5000});
    assert.equal(await fallback.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    console.log('UI passed: source fidelity, average/bands, navigation, checkboxes, persistence, export/import, exclusions, desktop/mobile and no-JS fallback.');
  } finally {
    await browser.close();
    fs.rmSync(temporary, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
