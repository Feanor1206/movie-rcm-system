'use strict';

/**
 * Dynamic JavaScript First Load Budget Guard and Metric Engine.
 * Recomputes actual route bundle sizes from Next.js build manifest and disk artifacts.
 * Never relies on hardcoded size constants.
 */

const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const crypto = require('node:crypto');
const os = require('node:os');

const DEFAULT_BUDGET_BYTES = 140 * 1024; // 143,360 bytes = 140 KiB

const DEFAULT_ROUTES = {
  '/': '/page',
  '/search': '/search/page',
  '/movies/[id]': '/movies/[id]/page',
  '/profile': '/profile/page',
};

/**
 * Computes exact JS bundle bytes for target routes from Next.js build output.
 * Deduplicates shared chunks across layout and route pages.
 *
 * @param {Object} options
 * @param {string} [options.buildDir] - Path to .next build directory
 * @param {Object} [options.routes] - Map of route URL to manifest page key
 * @param {number} [options.budgetBytes] - Maximum allowable gzip bytes per route (default 143,360)
 * @param {boolean} [options.throwOnOverBudget] - Throw if any route exceeds budget (default true)
 * @param {boolean} [options.throwOnMissing] - Throw if manifest or chunk files are missing (default true)
 * @returns {Object} Audit result with build metadata, per-route metrics and files
 */
function computeBuildBytes(options = {}) {
  const buildDir = options.buildDir
    ? path.resolve(options.buildDir)
    : path.resolve(__dirname, '../frontend/.next');
  const routes = options.routes || DEFAULT_ROUTES;
  const budgetBytes = options.budgetBytes ?? DEFAULT_BUDGET_BYTES;
  const throwOnOverBudget = options.throwOnOverBudget ?? true;
  const throwOnMissing = options.throwOnMissing ?? true;

  const manifestPath = path.join(buildDir, 'app-build-manifest.json');
  if (!fs.existsSync(manifestPath)) {
    if (throwOnMissing) {
      throw new Error(`Missing manifest: Expected app-build-manifest.json at ${manifestPath}`);
    }
    return null;
  }

  let manifest;
  try {
    manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  } catch (err) {
    throw new Error(`Failed to parse ${manifestPath}: ${err.message}`);
  }

  if (!manifest || typeof manifest.pages !== 'object') {
    throw new Error(`Invalid manifest structure: missing "pages" object in ${manifestPath}`);
  }

  const buildIdPath = path.join(buildDir, 'BUILD_ID');
  const buildId = fs.existsSync(buildIdPath)
    ? fs.readFileSync(buildIdPath, 'utf8').trim()
    : 'unknown';

  const result = {
    timestamp: new Date().toISOString(),
    buildId,
    budgetBytes,
    budgetKiB: Number((budgetBytes / 1024).toFixed(2)),
    methodology: 'unique app /layout + route manifest JavaScript; raw bytes and sum of individually gzipped files; excludes CSS/polyfills/RSC/API, not HTTP wire bytes',
    routes: {},
    allUnderBudget: true,
  };

  const layoutChunks = Array.isArray(manifest.pages['/layout'])
    ? manifest.pages['/layout']
    : [];

  for (const [routePath, manifestKey] of Object.entries(routes)) {
    if (!manifest.pages[manifestKey]) {
      if (throwOnMissing) {
        throw new Error(`Missing route manifest entry: Route "${routePath}" key "${manifestKey}" not found in app-build-manifest.json`);
      }
      continue;
    }

    const routeChunks = Array.isArray(manifest.pages[manifestKey])
      ? manifest.pages[manifestKey]
      : [];

    // Deduplicate unique JavaScript chunks across layout and page
    const chunkNames = [...new Set([...layoutChunks, ...routeChunks])].filter((name) =>
      name.endsWith('.js')
    );

    const files = [];
    let routeRawBytes = 0;
    let routeGzipBytes = 0;

    for (const chunkName of chunkNames) {
      const chunkPath = path.join(buildDir, chunkName);
      if (!fs.existsSync(chunkPath)) {
        if (throwOnMissing) {
          throw new Error(`Missing build file: Required chunk "${chunkName}" not found on disk at ${chunkPath}`);
        }
        continue;
      }

      const fileBuffer = fs.readFileSync(chunkPath);
      const rawSize = fileBuffer.length;
      const gzipSize = zlib.gzipSync(fileBuffer).length;
      const sha256 = crypto.createHash('sha256').update(fileBuffer).digest('hex');

      files.push({
        name: chunkName.replace(/\\/g, '/'),
        raw: rawSize,
        gzip: gzipSize,
        sha256,
      });

      routeRawBytes += rawSize;
      routeGzipBytes += gzipSize;
    }

    const isUnder = routeGzipBytes <= budgetBytes;
    if (!isUnder) {
      result.allUnderBudget = false;
      if (throwOnOverBudget) {
        throw new Error(
          `Route "${routePath}" exceeded budget: ${routeGzipBytes} gzip bytes > ${budgetBytes} budget bytes (${(routeGzipBytes / 1024).toFixed(2)} KiB > ${(budgetBytes / 1024).toFixed(2)} KiB)`
        );
      }
    }

    result.routes[routePath] = {
      route: routePath,
      manifestKey,
      rawBytes: routeRawBytes,
      gzipBytes: routeGzipBytes,
      kib: Number((routeGzipBytes / 1024).toFixed(2)),
      budgetBytes,
      budgetKiB: Number((budgetBytes / 1024).toFixed(2)),
      underBudget: isUnder,
      filesCount: files.length,
      files,
    };
  }

  return result;
}

/**
 * Self-test suite verifying dynamic budget calculations and contract assertions:
 * - Negative test 1: Missing manifest throws error.
 * - Negative test 2: Missing route manifest entry throws error.
 * - Negative test 3: Missing chunk file on disk throws error.
 * - Negative test 4: Over-budget detection on tiny budget throws / flags underBudget: false.
 * - Positive test 5: Real build measurement verification passes.
 */
function runBuildBytesSelfTest() {
  console.log('🧪 Starting compute_build_bytes Self-Test Suite...');

  const tmpRoot = path.join(os.tmpdir(), `build-bytes-test-${Date.now()}`);
  fs.mkdirSync(tmpRoot, { recursive: true });

  try {
    // 1. Negative Test: Missing manifest
    let threwMissingManifest = false;
    try {
      computeBuildBytes({ buildDir: path.join(tmpRoot, 'empty') });
    } catch (err) {
      if (err.message.includes('Missing manifest: Expected app-build-manifest.json')) {
        threwMissingManifest = true;
      } else {
        throw err;
      }
    }
    if (!threwMissingManifest) {
      throw new Error('Self-test failed: Missing manifest must throw an explicit error');
    }
    console.log('  ✔ Negative Test 1 (Missing manifest detection): PASS');

    // 2. Negative Test: Missing route manifest entry
    const fixtureDir = path.join(tmpRoot, 'fixture');
    fs.mkdirSync(fixtureDir, { recursive: true });
    fs.writeFileSync(path.join(fixtureDir, 'BUILD_ID'), 'test-build-123\n');
    fs.writeFileSync(
      path.join(fixtureDir, 'app-build-manifest.json'),
      JSON.stringify({ pages: { '/layout': [] } })
    );

    let threwMissingRoute = false;
    try {
      computeBuildBytes({ buildDir: fixtureDir });
    } catch (err) {
      if (err.message.includes('Missing route manifest entry')) {
        threwMissingRoute = true;
      } else {
        throw err;
      }
    }
    if (!threwMissingRoute) {
      throw new Error('Self-test failed: Missing route manifest entry must throw an explicit error');
    }
    console.log('  ✔ Negative Test 2 (Missing route manifest entry): PASS');

    // 3. Negative Test: Missing chunk file on disk
    fs.writeFileSync(
      path.join(fixtureDir, 'app-build-manifest.json'),
      JSON.stringify({
        pages: {
          '/layout': ['static/chunks/ghost-chunk.js'],
          '/page': ['static/chunks/ghost-page.js'],
        },
      })
    );

    let threwMissingChunk = false;
    try {
      computeBuildBytes({
        buildDir: fixtureDir,
        routes: { '/': '/page' },
      });
    } catch (err) {
      if (err.message.includes('Missing build file: Required chunk')) {
        threwMissingChunk = true;
      } else {
        throw err;
      }
    }
    if (!threwMissingChunk) {
      throw new Error('Self-test failed: Missing chunk file on disk must throw an explicit error');
    }
    console.log('  ✔ Negative Test 3 (Missing chunk file detection): PASS');

    // 4. Negative Test: Over-budget detection on tiny budget
    const chunkDir = path.join(fixtureDir, 'static', 'chunks');
    fs.mkdirSync(chunkDir, { recursive: true });
    const dummyContent = 'console.log("hello world from movie recommendation system bundle");'.repeat(20);
    fs.writeFileSync(path.join(chunkDir, 'ghost-chunk.js'), dummyContent);
    fs.writeFileSync(path.join(chunkDir, 'ghost-page.js'), dummyContent);

    // 4a. Without throw: underBudget must be false
    const overResult = computeBuildBytes({
      buildDir: fixtureDir,
      routes: { '/': '/page' },
      budgetBytes: 50, // Tiny budget (50 bytes)
      throwOnOverBudget: false,
    });
    if (overResult.routes['/'].underBudget !== false || overResult.allUnderBudget !== false) {
      throw new Error('Self-test failed: Tiny budget must mark underBudget=false');
    }

    // 4b. With throw: must throw over-budget error
    let threwOverBudget = false;
    try {
      computeBuildBytes({
        buildDir: fixtureDir,
        routes: { '/': '/page' },
        budgetBytes: 50,
        throwOnOverBudget: true,
      });
    } catch (err) {
      if (err.message.includes('exceeded budget')) {
        threwOverBudget = true;
      } else {
        throw err;
      }
    }
    if (!threwOverBudget) {
      throw new Error('Self-test failed: Tiny budget with throwOnOverBudget must throw error');
    }
    console.log('  ✔ Negative Test 4 (Over-budget detection with tiny budget): PASS');

    // 5. Positive Test: Real build measurement verification
    const realResult = computeBuildBytes({ throwOnOverBudget: true });
    if (!realResult || !realResult.allUnderBudget) {
      throw new Error('Self-test failed: Real build failed budget check');
    }
    for (const [r, metrics] of Object.entries(realResult.routes)) {
      if (!metrics.underBudget || metrics.gzipBytes > DEFAULT_BUDGET_BYTES) {
        throw new Error(`Self-test failed: Route ${r} exceeded budget (${metrics.gzipBytes} > ${DEFAULT_BUDGET_BYTES})`);
      }
      if (metrics.filesCount === 0 || metrics.rawBytes === 0) {
        throw new Error(`Self-test failed: Route ${r} has 0 files or 0 raw bytes`);
      }
    }
    console.log('  ✔ Positive Test 5 (Real build manifest and chunk measurement): PASS');
    console.log(`     - Build ID: ${realResult.buildId}`);
    for (const [r, m] of Object.entries(realResult.routes)) {
      console.log(`     - ${r.padEnd(14)}: Raw=${String(m.rawBytes).padStart(6)} bytes | Gzip=${String(m.gzipBytes).padStart(6)} bytes (${m.kib} KiB / 140 KiB)`);
    }

    console.log('🎉 All compute_build_bytes self-tests PASSED successfully.\n');
    return true;
  } finally {
    try {
      fs.rmSync(tmpRoot, { recursive: true, force: true });
    } catch {}
  }
}

// CLI Execution Entrypoint
if (require.main === module) {
  const isNegativeTest = process.argv.includes('--negative-test');
  if (isNegativeTest) {
    try {
      runBuildBytesSelfTest();
      process.exit(0);
    } catch (err) {
      console.error('❌ Self-test failed:', err.message);
      process.exit(1);
    }
  }

  try {
    const result = computeBuildBytes({ throwOnOverBudget: true });
    console.log('================================================================');
    console.log('       NEXT.JS DYNAMIC ROUTE JS FIRST-LOAD BUDGET AUDIT         ');
    console.log('================================================================');
    console.log(`Build ID:    ${result.buildId}`);
    console.log(`Timestamp:   ${result.timestamp}`);
    console.log(`Methodology: ${result.methodology}`);
    console.log(`Budget:      ${result.budgetBytes} bytes (${result.budgetKiB} KiB)`);
    console.log('----------------------------------------------------------------');
    for (const [routePath, metrics] of Object.entries(result.routes)) {
      console.log(
        `${routePath.padEnd(16)} | Raw: ${String(metrics.rawBytes).padStart(7)} B | Gzip: ${String(metrics.gzipBytes).padStart(6)} B (${metrics.kib.toFixed(2)} KiB) | Status: ${metrics.underBudget ? '✔ PASS' : '✖ FAIL'} (${metrics.filesCount} chunks)`
      );
    }
    console.log('================================================================');
    process.exit(0);
  } catch (err) {
    console.error('❌ Budget check failed:', err.message);
    process.exit(1);
  }
}

module.exports = {
  computeBuildBytes,
  runBuildBytesSelfTest,
  DEFAULT_BUDGET_BYTES,
  DEFAULT_ROUTES,
};
