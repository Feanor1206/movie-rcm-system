const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { gzipSync } = require('node:zlib');

const DIST = path.join(__dirname, '../frontend/dist');
const BUDGET = 140 * 1024;
const ROUTES = {
  '/': 'index.html',
  '/search': 'app/search/page.tsx',
  '/movies/[id]': 'app/movies/[id]/page.tsx',
  '/series/[id]': 'app/series/[id]/page.tsx',
  '/profile': 'app/profile/page.tsx',
  '/admin/import': 'app/admin/import/page.tsx',
};

function computeBuildBytes({ buildDir = DIST, budgetBytes = BUDGET, throwOnOverBudget = true } = {}) {
  const manifest = JSON.parse(fs.readFileSync(path.join(buildDir, '.vite/manifest.json'), 'utf8'));
  const routes = {};
  const sizes = new Map();
  const kib = (bytes) => Number((bytes / 1024).toFixed(2));

  for (const [route, manifestKey] of Object.entries(ROUTES)) {
    const chunks = new Set();
    const collect = (key) => {
      const entry = manifest[key];
      if (!entry?.file) throw new Error(`Thiếu bundle cho ${key}`);
      if (chunks.has(entry.file)) return;
      chunks.add(entry.file);
      for (const dependency of entry.imports || []) collect(dependency);
    };
    collect('index.html');
    collect(manifestKey);
    let rawBytes = 0;
    let gzipBytes = 0;
    for (const chunk of chunks) {
      if (!sizes.has(chunk)) {
        const source = fs.readFileSync(path.join(buildDir, chunk));
        sizes.set(chunk, [source.length, gzipSync(source).length]);
      }
      const [raw, compressed] = sizes.get(chunk);
      rawBytes += raw;
      gzipBytes += compressed;
    }
    const underBudget = gzipBytes <= budgetBytes;
    if (!underBudget && throwOnOverBudget) throw new Error(`${route} vượt ${kib(budgetBytes)} KiB: ${kib(gzipBytes)} KiB`);
    routes[route] = {
      route, manifestKey, rawBytes, gzipBytes, kib: kib(gzipBytes), budgetBytes,
      budgetKiB: kib(budgetBytes), underBudget, filesCount: chunks.size, files: [...chunks],
    };
  }
  return {
    timestamp: new Date().toISOString(), buildId: manifest['index.html'].file,
    budgetBytes, budgetKiB: kib(budgetBytes), methodology: 'JavaScript tải đầu theo manifest Vite, gzip từng tệp',
    routes, allUnderBudget: Object.values(routes).every((route) => route.underBudget),
  };
}

function runBuildBytesSelfTest() {
  const { routes } = computeBuildBytes();
  assert(Object.values(routes).every((route) => route.rawBytes > 0 && route.filesCount > 0));
  assert.throws(() => computeBuildBytes({ budgetBytes: 1 }), /vượt/);
  assert.equal(computeBuildBytes({ budgetBytes: 1, throwOnOverBudget: false }).allUnderBudget, false);
}

if (require.main === module) {
  if (process.argv.includes('--self-test')) runBuildBytesSelfTest();
  const { routes } = computeBuildBytes();
  for (const route of Object.values(routes)) console.log(`${route.route.padEnd(16)} ${route.kib.toFixed(2)} / ${route.budgetKiB} KiB gzip`);
}

module.exports = { computeBuildBytes, runBuildBytesSelfTest };
