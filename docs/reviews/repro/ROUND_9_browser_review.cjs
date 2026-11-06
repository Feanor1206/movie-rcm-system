// Run the submitted browser harness unchanged except output directory redirection.
// Keep Gemini's frozen screenshots and evidence intact.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const Module = require('node:module');

async function checkDebugPort() {
  await new Promise((resolve, reject) => {
    const probe = http.createServer();
    probe.once('error', () => reject(new Error('Reviewer preflight: port 9222 busy; refusing to attach to another browser')));
    probe.listen(9222, '127.0.0.1', () => probe.close(resolve));
  });
}

checkDebugPort().then(() => {
  const filename = path.resolve(__dirname, '../../../scripts/run_browser_walkthrough.cjs');
  let source = fs.readFileSync(filename, 'utf8');
  const original = "const SCREENSHOTS_DIR = path.resolve(__dirname, '../docs/reports/screenshots/ROUND_9');";
  if (!source.includes(original)) throw new Error('Harness output declaration changed; inspect before running');
  const output = fs.mkdtempSync(path.join(os.tmpdir(), 'codex-round9-browser-review-'));
  console.log('Reviewer output directory: ' + output);
  source = source.replace(original, 'const SCREENSHOTS_DIR = ' + JSON.stringify(output) + ';');
  source = source.replace('async function captureScreenshot(filename) {', `async function captureScreenshot(filename) {
    await evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
    if (filename === '05_profile_desktop.png') {
      const measured = await evaluate(\`({url: location.href, hasRatingLabel: document.body.innerText.includes('Điểm của bạn:'), hasNine: document.body.innerText.includes('9/10'), tabs: Array.from(document.querySelectorAll('button')).filter(b => b.textContent.includes('Đã chấm điểm')).map(b => ({text: b.innerText, className: b.className}))})\`);
      fs.writeFileSync(path.join(SCREENSHOTS_DIR, 'review_profile_dom.json'), JSON.stringify(measured, null, 2));
      assert.ok(measured.hasRatingLabel && measured.hasNine, 'Reviewer: Profile must visibly render personal rating label and 9/10');
      assert.ok(measured.tabs.some(t => t.className.includes('border-brand')), 'Reviewer: Ratings tab must be selected');
    }
  `);
  source = source.replace('// Save JSON evidence', `// Save independent network evidence without secrets
    fs.writeFileSync(path.join(SCREENSHOTS_DIR, 'review_network.json'), JSON.stringify({requests: fixtureServer.networkJournal, responses: browser.networkResponses}, null, 2));
    // Save JSON evidence`);
  const loaded = new Module(filename, module);
  loaded.filename = filename;
  loaded.paths = Module._nodeModulePaths(path.dirname(filename));
  loaded._compile(source, filename);
}).catch(error => { console.error(error); process.exitCode = 1; });
