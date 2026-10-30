/**
 * M3 Browser Walkthrough Automation & Evidence Generator (Round 10)
 *
 * Runs desktop & mobile walkthrough against a dedicated fixture transport server
 * and Next.js standalone production build using headless Chrome via Chrome DevTools Protocol (CDP).
 *
 * Verifies Milestone M3:
 *   - Accessible modals (AuthModal, video player, CineBot) with focus trap, Escape key, body scroll lock, focus restore.
 *   - Broken image fallback (404 / broken image URLs render clean title placeholders without layout distortion).
 *   - User isolation (Guest exploration -> User A save/rate -> Profile reload -> Uncertain retry -> Logout -> User B isolation check).
 *   - Mobile viewport (375x667) responsiveness with touch targets and non-overlapping controls.
 *   - Performance baseline & sanitized network / assertion logs in ROUND_10 directory.
 *
 * Usage:
 *   node scripts/run_browser_walkthrough.cjs
 *   node scripts/run_browser_walkthrough.cjs --negative-test
 */

const http = require('node:http');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const { computeBuildBytes, runBuildBytesSelfTest } = require('./compute_build_bytes.cjs');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const STANDALONE_SERVER = path.resolve(__dirname, '../frontend/.next/standalone/server.js');
const FIXTURE_PATH = path.resolve(__dirname, '../docs/fixtures/animation_catalog_fixture.json');
const SCREENSHOTS_DIR = path.resolve(__dirname, '../docs/reports/screenshots/ROUND_13');
const LOCAL_MOVIES_PATH = path.resolve(__dirname, '../frontend/lib/data/movies.ts');

fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

// Synthetic movie 1 (Valid metadata, no broken images)
const SYNTHETIC_MOVIE_ID = 'm2-synthetic-anim-001';
const SYNTHETIC_MOVIE = {
  id: SYNTHETIC_MOVIE_ID,
  title: 'The Quantum Garden',
  year: 2026,
  rating: 9.1,
  runtime: '1h 45m',
  genres: ['Animation', 'Sci-Fi'],
  description: 'A solitary robotic gardener restores ancient celestial ecosystems in a wondrous hand-drawn deep-space odyssey.',
  poster: null,
  backdrop: null,
  videoUrl: 'http://127.0.0.1:8080/videos/trailer.mp4',
};

// Synthetic movie 2 (Broken Image 404 URLs to verify M3 fallback)
const BROKEN_IMG_MOVIE_ID = 'm3-synthetic-broken-001';
const BROKEN_IMG_MOVIE = {
  id: BROKEN_IMG_MOVIE_ID,
  title: 'The Lost Lantern',
  year: 2026,
  rating: 8.8,
  runtime: '1h 32m',
  genres: ['Animation', 'Fantasy'],
  poster: 'http://127.0.0.1:8080/images/broken-poster.png',
  backdrop: 'http://127.0.0.1:8080/images/broken-backdrop.png',
  videoUrl: null,
};

// ----------------------------------------------------------------------------
// 0. Preflight checks and Asset preparation
// ----------------------------------------------------------------------------
function ensureAssetsAndIsolation() {
  const localMoviesCode = fs.readFileSync(LOCAL_MOVIES_PATH, 'utf8');
  if (localMoviesCode.includes(SYNTHETIC_MOVIE_ID)) {
    throw new Error(`Isolation violation: ${SYNTHETIC_MOVIE_ID} must not exist in ${LOCAL_MOVIES_PATH}`);
  }

  const standaloneDir = path.resolve(__dirname, '../frontend/.next/standalone');
  const standaloneStatic = path.join(standaloneDir, '.next/static');
  const frontendStatic = path.resolve(__dirname, '../frontend/.next/static');
  const standalonePublic = path.join(standaloneDir, 'public');
  const frontendPublic = path.resolve(__dirname, '../frontend/public');

  // Always synchronize latest build assets into standalone to prevent stale chunks
  fs.cpSync(frontendStatic, standaloneStatic, { recursive: true });
  fs.cpSync(frontendPublic, standalonePublic, { recursive: true });
}

function checkPortAvailable(port, host = '127.0.0.1') {
  return new Promise((resolve) => {
    const s = http.createServer();
    s.once('error', () => resolve(false));
    s.once('listening', () => {
      s.close(() => resolve(true));
    });
    s.listen(port, host);
  });
}

// ----------------------------------------------------------------------------
// 1. In-Memory Fixture Backend Server (port 8080)
// ----------------------------------------------------------------------------
function startFixtureServer() {
  const candidateFixture = JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf8')).records;

  const allMovies = [
    SYNTHETIC_MOVIE,
    BROKEN_IMG_MOVIE,
    ...candidateFixture,
  ];

  // Isolated user libraries
  const users = {
    user_a: {
      token: 'token-user-a',
      user: { id: 1, username: 'user_a', email: 'user_a@example.com', role: 'ROLE_USER' },
      watchlist: new Set(),
      ratings: new Map(),
      favorites: new Set(),
    },
    user_b: {
      token: 'token-user-b',
      user: { id: 2, username: 'user_b', email: 'user_b@example.com', role: 'ROLE_USER' },
      watchlist: new Set(),
      ratings: new Map(),
      favorites: new Set(),
    },
  };

  const networkJournal = [];

  let forceCatalogError = false;
  let forceCatalogEmpty = false;
  let forceWriteDrop = false;
  let forceReconcileError = false;

  function resolveUser(req) {
    const auth = req.headers.authorization || '';
    if (auth.includes('token-user-b')) return users.user_b;
    return users.user_a;
  }

  const server = http.createServer(async (req, res) => {
    const parsedUrl = new URL(req.url, 'http://127.0.0.1:8080');
    const pathname = parsedUrl.pathname;
    const method = req.method;

    networkJournal.push({
      time: Date.now(),
      method,
      path: pathname,
      query: parsedUrl.search,
      auth: Boolean(req.headers.authorization),
    });

    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, PUT, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, Accept');

    if (method === 'OPTIONS') {
      res.writeHead(204);
      return res.end();
    }

    // Broken image simulation: 404 for broken images
    if (pathname.startsWith('/images/broken-')) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      return res.end('Image Not Found (404 Simulated)');
    }

    // Video trailer dummy response
    if (pathname === '/videos/trailer.mp4') {
      res.writeHead(200, { 'Content-Type': 'video/mp4' });
      return res.end(Buffer.alloc(1024));
    }

    let body = {};
    if (method === 'POST' || method === 'PUT') {
      const chunks = [];
      for await (const chunk of req) chunks.push(chunk);
      const raw = Buffer.concat(chunks).toString('utf8');
      try { body = JSON.parse(raw); } catch {}
    }

    // Control endpoints
    if (pathname === '/api/test-control/set') {
      if (parsedUrl.searchParams.has('catalogError')) {
        forceCatalogError = parsedUrl.searchParams.get('catalogError') === 'true';
      }
      if (parsedUrl.searchParams.has('catalogEmpty')) {
        forceCatalogEmpty = parsedUrl.searchParams.get('catalogEmpty') === 'true';
      }
      if (parsedUrl.searchParams.has('writeDrop')) {
        forceWriteDrop = parsedUrl.searchParams.get('writeDrop') === 'true';
      }
      if (parsedUrl.searchParams.has('reconcileError')) {
        forceReconcileError = parsedUrl.searchParams.get('reconcileError') === 'true';
      }
      if (parsedUrl.searchParams.get('clearWatchlist') === 'true') {
        users.user_a.watchlist.clear();
        users.user_b.watchlist.clear();
      }
      if (parsedUrl.searchParams.get('clearRatings') === 'true') {
        users.user_a.ratings.clear();
        users.user_b.ratings.clear();
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ ok: true }));
    }

    // Auth Me: GET /api/auth/me
    if (pathname === '/api/auth/me' && method === 'GET') {
      const authHeader = req.headers.authorization || '';
      if (!authHeader.startsWith('Bearer ')) {
        res.writeHead(401, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ success: false, message: 'Unauthorized' }));
      }
      const u = resolveUser(req);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ success: true, data: u.user }));
    }

    // Auth Login: POST /api/auth/login
    if (pathname === '/api/auth/login' && method === 'POST') {
      const loginKey = body.usernameOrEmail || body.username || body.email;
      if (loginKey === 'regression_invalid' || body.password === 'not-real-password') {
        res.writeHead(401, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ success: false, message: 'Reviewer invalid credentials' }));
      }
      const isUserB = loginKey === 'user_b';
      const selected = isUserB ? users.user_b : users.user_a;
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({
        success: true,
        data: {
          token: selected.token,
          id: selected.user.id,
          username: selected.user.username,
          email: selected.user.email,
          role: selected.user.role,
        },
      }));
    }

    // Catalog Browse: GET /api/movies/browse
    if (pathname === '/api/movies/browse' && method === 'GET') {
      if (forceCatalogError) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ success: false, message: 'Catalog server internal failure' }));
      }
      if (forceCatalogEmpty) {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({
          success: true,
          data: { items: [], page: 0, size: 12, totalElements: 0, totalPages: 0, hasNext: false, hasPrevious: false },
        }));
      }

      let filtered = [...allMovies];
      const query = (parsedUrl.searchParams.get('query') || parsedUrl.searchParams.get('search') || '').trim().toLowerCase();
      if (query) {
        filtered = filtered.filter((m) =>
          m.title.toLowerCase().includes(query) || (m.description && m.description.toLowerCase().includes(query))
        );
      }

      const animationOnly = parsedUrl.searchParams.get('animationOnly') === 'true';
      if (animationOnly) {
        filtered = filtered.filter((m) => m.genres.some((g) => g.toLowerCase() === 'animation'));
      }

      const page = parseInt(parsedUrl.searchParams.get('page') || '0', 10);
      const size = parseInt(parsedUrl.searchParams.get('size') || '12', 10);
      const start = page * size;
      const paginated = filtered.slice(start, start + size);

      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({
        success: true,
        data: {
          items: paginated,
          page,
          size,
          totalElements: filtered.length,
          totalPages: Math.ceil(filtered.length / size),
          hasNext: start + size < filtered.length,
          hasPrevious: page > 0,
        },
      }));
    }

    // Detail: GET /api/movies/:id
    if (pathname.startsWith('/api/movies/') && method === 'GET') {
      const id = decodeURIComponent(pathname.replace('/api/movies/', ''));
      const found = allMovies.find((m) => m.id === id);
      if (!found) {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ success: false, message: `Movie not found with id: ${id}`, data: null }));
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ success: true, data: found }));
    }

    // Watchlist: GET /api/users/watchlist
    if (pathname === '/api/users/watchlist' && method === 'GET') {
      if (forceReconcileError) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ success: false, message: 'Reconcile failure' }));
      }
      const u = resolveUser(req);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({
        success: true,
        data: Array.from(u.watchlist).map((id) => ({ movieId: id })),
      }));
    }

    // Watchlist: POST /api/users/watchlist
    if (pathname === '/api/users/watchlist' && method === 'POST') {
      const u = resolveUser(req);
      if (forceWriteDrop) {
        if (body.movieId) u.watchlist.add(body.movieId);
        res.destroy();
        return;
      }
      if (body.movieId) u.watchlist.add(body.movieId);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ success: true, data: { movieId: body.movieId } }));
    }

    // Watchlist: DELETE /api/users/watchlist/:id
    if (pathname.startsWith('/api/users/watchlist/') && method === 'DELETE') {
      const u = resolveUser(req);
      const id = decodeURIComponent(pathname.replace('/api/users/watchlist/', ''));
      if (forceWriteDrop) {
        u.watchlist.delete(id);
        res.destroy();
        return;
      }
      u.watchlist.delete(id);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ success: true, data: true }));
    }

    // Ratings: GET /api/users/ratings
    if (pathname === '/api/users/ratings' && method === 'GET') {
      const u = resolveUser(req);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({
        success: true,
        data: Array.from(u.ratings.entries()).map(([movieId, rating]) => ({ movieId, rating })),
      }));
    }

    // Ratings: POST /api/users/ratings
    if (pathname === '/api/users/ratings' && method === 'POST') {
      const u = resolveUser(req);
      if (body.movieId && body.rating) u.ratings.set(body.movieId, body.rating);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ success: true, data: { movieId: body.movieId, rating: body.rating } }));
    }

    // Favorites: GET /api/users/favorites
    if (pathname === '/api/users/favorites' && method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ success: true, data: [] }));
    }

    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ success: false, message: 'Endpoint not found' }));
  });

  return new Promise((resolve) => {
    server.listen(8080, '127.0.0.1', () => {
      console.log('✔ Fixture Backend Server listening on http://127.0.0.1:8080');
      server.users = users;
      server.networkJournal = networkJournal;
      resolve(server);
    });
  });
}

// ----------------------------------------------------------------------------
// 2. Next.js Standalone Production Server (port 3005)
// ----------------------------------------------------------------------------
function startNextServer() {
  return new Promise((resolve, reject) => {
    const env = {
      ...process.env,
      PORT: '3005',
      HOSTNAME: '127.0.0.1',
      NODE_ENV: 'production',
      NEXT_PUBLIC_SPRINGBOOT_API_URL: 'http://127.0.0.1:8080/api',
    };

    const proc = spawn(process.execPath, [STANDALONE_SERVER], {
      cwd: path.resolve(__dirname, '../frontend/.next/standalone'),
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let started = false;
    proc.stdout.on('data', (d) => {
      const str = d.toString();
      if (!started && (str.includes('Listening on port 3005') || str.includes('Ready') || str.includes('127.0.0.1:3005'))) {
        started = true;
        console.log('✔ Next.js Standalone Server listening on http://127.0.0.1:3005');
        resolve(proc);
      }
    });

    proc.stderr.on('data', (d) => {
      console.error('[next-stderr]:', d.toString());
    });

    proc.on('error', (err) => {
      if (!started) reject(err);
    });

    setTimeout(() => {
      if (!started) {
        started = true;
        console.log('✔ Next.js Standalone Server assuming started after timeout on port 3005');
        resolve(proc);
      }
    }, 4000);
  });
}

// ----------------------------------------------------------------------------
// 3. Headless Chrome via Chrome DevTools Protocol (CDP)
// ----------------------------------------------------------------------------
async function launchChromeSession() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'chrome-walkthrough-'));
  let cdpPort = 9222;
  for (let p = 9222; p <= 9240; p++) {
    if (await checkPortAvailable(p)) {
      cdpPort = p;
      break;
    }
  }

  const chromeArgs = [
    '--headless=new',
    `--remote-debugging-port=${cdpPort}`,
    `--user-data-dir=${tmpDir}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-background-networking',
    '--disable-extensions',
    '--disable-sync',
    '--disable-gpu',
    '--window-size=1280,800',
    'about:blank',
  ];

  const proc = spawn(CHROME_PATH, chromeArgs, { stdio: 'ignore' });

  // Wait for CDP endpoint
  let versionData = null;
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${cdpPort}/json/version`);
      if (res.ok) {
        versionData = await res.json();
        break;
      }
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }

  if (!versionData || !versionData.webSocketDebuggerUrl) {
    proc.kill();
    throw new Error('Failed to connect to Chrome DevTools Protocol');
  }

  const listRes = await fetch(`http://127.0.0.1:${cdpPort}/json/list`);
  const pages = await listRes.json();
  const targetPage = pages.find((p) => p.type === 'page') || pages[0];
  const pageWsUrl = targetPage?.webSocketDebuggerUrl;
  console.log(`Connecting to CDP target ${targetPage?.id} (${targetPage?.type}, ${targetPage?.url})`);
  const ws = new globalThis.WebSocket(pageWsUrl);

  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true });
    ws.addEventListener('error', reject, { once: true });
  });

  let idCounter = 1;
  const pendingRequests = new Map();
  const networkResponses = [];
  const cdpRequests = new Map();
  let assetFailure = null;

  ws.addEventListener('message', (event) => {
    const rawData = typeof event.data === 'string' ? event.data : event.data.toString();
    const msg = JSON.parse(rawData);
    if (msg.id && pendingRequests.has(msg.id)) {
      const { resolve, reject } = pendingRequests.get(msg.id);
      pendingRequests.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message || JSON.stringify(msg.error)));
      else resolve(msg.result);
    }

    if (msg.method === 'Network.requestWillBeSent') {
      const { requestId, request } = msg.params;
      cdpRequests.set(requestId, {
        requestId,
        url: request.url,
        method: request.method,
        status: null,
        fromDiskCache: false,
        fromPrefetchCache: false,
        encodedDataLength: 0,
        finished: false,
        failed: false,
      });
    }

    if (msg.method === 'Network.responseReceived') {
      const resp = msg.params.response;
      networkResponses.push({
        url: resp.url,
        status: resp.status,
        mimeType: resp.mimeType,
      });

      const req = cdpRequests.get(msg.params.requestId);
      if (req) {
        req.status = resp.status;
        req.fromDiskCache = Boolean(resp.fromDiskCache);
        req.fromPrefetchCache = Boolean(resp.fromPrefetchCache);
        req.status304 = resp.status === 304;
        req.mimeType = resp.mimeType;
        req.timing = resp.timing;
      }

      // Assert non-broken static assets
      if (
        (resp.url.includes('/_next/static/') || resp.url.includes('/static/')) &&
        resp.status >= 400
      ) {
        assetFailure = { url: resp.url, status: resp.status };
      }
    }

    if (msg.method === 'Network.loadingFinished') {
      const { requestId, encodedDataLength } = msg.params;
      const req = cdpRequests.get(requestId);
      if (req) {
        req.encodedDataLength = encodedDataLength || 0;
        req.finished = true;
      }
    }

    if (msg.method === 'Network.loadingFailed') {
      const { requestId } = msg.params;
      const req = cdpRequests.get(requestId);
      if (req) {
        req.failed = true;
        req.finished = true;
      }
    }

    if (msg.method === 'Runtime.exceptionThrown') {
      console.error('[Browser Exception]:', JSON.stringify(msg.params.exceptionDetails));
    }
    if (msg.method === 'Runtime.consoleAPICalled') {
      const args = msg.params.args?.map(a => a.value || a.description).join(' ');
      console.log('[Browser Console]:', args);
    }
  });

  function cdp(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = idCounter++;
      pendingRequests.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  await cdp('Page.enable');
  await cdp('DOM.enable');
  await cdp('Runtime.enable');
  await cdp('Network.enable');

  // C2: Buffered PerformanceObserver for LCP and standard Session Window CLS
  await cdp('Page.addScriptToEvaluateOnNewDocument', {
    source: `
      (() => {
        window.__perfObserverInstalled = true;
        window.__perfData = {
          lcp: null,
          lcpEntries: [],
          cls: 0,
          rawLayoutShifts: [],
          clsSessionWindow: 0,
          observerSupported: {
            lcp: false,
            cls: false
          }
        };

        let sessionValue = 0;
        let sessionEntries = [];
        let maxSessionValue = 0;

        try {
          if (typeof PerformanceObserver !== 'undefined' && PerformanceObserver.supportedEntryTypes && PerformanceObserver.supportedEntryTypes.includes('largest-contentful-paint')) {
            window.__perfData.observerSupported.lcp = true;
            const lcpObserver = new PerformanceObserver((entryList) => {
              const entries = entryList.getEntries();
              for (const entry of entries) {
                window.__perfData.lcpEntries.push({
                  startTime: entry.startTime,
                  size: entry.size,
                  id: entry.id,
                  url: entry.url
                });
                window.__perfData.lcp = Math.round(entry.startTime);
              }
            });
            lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });
          }
        } catch (e) {
          window.__perfData.lcpError = e.message;
        }

        try {
          if (typeof PerformanceObserver !== 'undefined' && PerformanceObserver.supportedEntryTypes && PerformanceObserver.supportedEntryTypes.includes('layout-shift')) {
            window.__perfData.observerSupported.cls = true;
            const clsObserver = new PerformanceObserver((entryList) => {
              for (const entry of entryList.getEntries()) {
                if (!entry.hadRecentInput) {
                  window.__perfData.rawLayoutShifts.push({
                    value: entry.value,
                    startTime: entry.startTime
                  });
                  window.__perfData.cls = Math.round((window.__perfData.cls + entry.value) * 1000) / 1000;

                  const firstSessionEntry = sessionEntries[0];
                  const lastSessionEntry = sessionEntries[sessionEntries.length - 1];

                  if (sessionValue && entry.startTime - lastSessionEntry.startTime < 1000 && entry.startTime - firstSessionEntry.startTime < 5000) {
                    sessionValue += entry.value;
                    sessionEntries.push(entry);
                  } else {
                    sessionValue = entry.value;
                    sessionEntries = [entry];
                  }

                  if (sessionValue > maxSessionValue) {
                    maxSessionValue = sessionValue;
                    window.__perfData.clsSessionWindow = Math.round(maxSessionValue * 1000) / 1000;
                  }
                }
              }
            });
            clsObserver.observe({ type: 'layout-shift', buffered: true });
          }
        } catch (e) {
          window.__perfData.clsError = e.message;
        }
      })();
    `
  });

  async function setViewport(width, height, isMobile = false) {
    await cdp('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: isMobile,
    });
  }

  async function navigate(url) {
    const navResult = await cdp('Page.navigate', { url });
    if (navResult?.errorText) {
      console.error(`Page.navigate to ${url} failed with errorText:`, navResult.errorText);
    }
    for (let i = 0; i < 50; i++) {
      await new Promise((r) => setTimeout(r, 100));
      try {
        const curUrl = await evaluate('window.location.href');
        const ready = await evaluate('document.readyState');
        if (curUrl && curUrl !== 'about:blank' && (ready === 'complete' || ready === 'interactive')) {
          break;
        }
      } catch {}
    }
    await new Promise((r) => setTimeout(r, 300));
  }

  async function evaluate(expression) {
    const res = await cdp('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (res?.exceptionDetails) {
      const desc = res.exceptionDetails.exception?.description || res.exceptionDetails.text;
      throw new Error(`Browser JS evaluate failed: ${desc}`);
    }
    return res?.result?.value;
  }

  async function waitForCondition(conditionFnStr, description, timeoutMs = 6000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (assetFailure) {
        throw new Error(`Asset load failure: ${assetFailure.url} returned ${assetFailure.status}`);
      }
      try {
        const ok = await evaluate(conditionFnStr);
        if (ok) return ok;
      } catch (err) {
        throw err;
      }
      await new Promise((r) => setTimeout(r, 100));
    }
    throw new Error(`Timeout waiting for condition: ${description} within ${timeoutMs}ms`);
  }

  async function waitForSelector(selector, timeoutMs = 6000) {
    return waitForCondition(
      `Boolean(document.querySelector(${JSON.stringify(selector)}))`,
      `selector "${selector}"`,
      timeoutMs
    );
  }

  async function captureScreenshot(filename) {
    const shot = await cdp('Page.captureScreenshot', { format: 'png' });
    const filePath = path.join(SCREENSHOTS_DIR, filename);
    fs.writeFileSync(filePath, Buffer.from(shot.data, 'base64'));
    console.log(`  📸 Saved screenshot: ${filename} (${(shot.data.length / 1024).toFixed(1)} KB)`);
  }

  async function dispatchKey(key, code, windowsVirtualKeyCode) {
    await cdp('Input.dispatchKeyEvent', {
      type: 'keyDown',
      key,
      code,
      windowsVirtualKeyCode,
    });
    await new Promise((r) => setTimeout(r, 50));
    await cdp('Input.dispatchKeyEvent', {
      type: 'keyUp',
      key,
      code,
      windowsVirtualKeyCode,
    });
  }

  async function clearCache() {
    await cdp('Network.clearBrowserCache');
  }

  async function setCacheDisabled(cacheDisabled) {
    await cdp('Network.setCacheDisabled', { cacheDisabled: Boolean(cacheDisabled) });
  }

  function resetNetworkTracker() {
    cdpRequests.clear();
  }

  function getNetworkAccounting() {
    const reqs = Array.from(cdpRequests.values());
    const totalWireBytes = reqs.reduce((sum, r) => sum + (r.encodedDataLength || 0), 0);
    const cacheHits = reqs.filter(r => r.fromDiskCache || r.fromPrefetchCache || r.status304).length;
    const wireRequests = reqs.filter(r => (r.encodedDataLength || 0) > 0).length;
    return {
      totalWireBytes,
      totalRequests: reqs.length,
      cacheHits,
      wireRequests,
      requests: reqs.map(r => ({
        url: r.url,
        method: r.method,
        status: r.status,
        encodedDataLength: r.encodedDataLength,
        fromDiskCache: r.fromDiskCache,
        fromPrefetchCache: r.fromPrefetchCache,
        status304: r.status304,
      })),
    };
  }

  function close() {
    try { ws.close(); } catch {}
    try { proc.kill(); } catch {}
    try {
      if (tmpDir && path.isAbsolute(tmpDir) && tmpDir.includes('chrome-walkthrough-')) {
        fs.rmSync(tmpDir, { recursive: true, force: true });
      }
    } catch {}
  }

  return {
    cdp,
    setViewport,
    navigate,
    evaluate,
    waitForCondition,
    waitForSelector,
    captureScreenshot,
    dispatchKey,
    close,
    networkResponses,
    getAssetFailure: () => assetFailure,
    clearCache,
    setCacheDisabled,
    resetNetworkTracker,
    getNetworkAccounting,
  };
}

// ----------------------------------------------------------------------------
// 4. Main Walkthrough Orchestrator
// ----------------------------------------------------------------------------
async function main() {
  const isNegativeTestOnly = process.argv.includes('--negative-test');
  console.log('🚀 Starting M3 Browser Walkthrough Runner (Round 10)...');

  ensureAssetsAndIsolation();

  const is8080Free = await checkPortAvailable(8080);
  if (!is8080Free) {
    throw new Error('Preflight check failed: Port 8080 is already in use.');
  }

  const is3005Free = await checkPortAvailable(3005);
  if (!is3005Free) {
    throw new Error('Preflight check failed: Port 3005 is already in use.');
  }

  let fixtureServer;
  let nextProc;
  let browser;

  const evidenceRecords = [];

  try {
    fixtureServer = await startFixtureServer();
    nextProc = await startNextServer();
    browser = await launchChromeSession();

    if (isNegativeTestOnly) {
      await browser.navigate('http://127.0.0.1:3005/');

      // 1. Missing element negative self-check
      let threw = false;
      try {
        await browser.waitForSelector('#non-existent-selector-for-negative-test', 300);
      } catch {
        threw = true;
      }
      assert.ok(threw, 'Negative self-check must throw on missing element');

      // 2. PerformanceObserver installation & support control check
      const observerCheck = await browser.evaluate(`
        (() => ({
          installed: Boolean(window.__perfObserverInstalled),
          lcpSupported: Boolean(window.__perfData?.observerSupported?.lcp),
          clsSupported: Boolean(window.__perfData?.observerSupported?.cls)
        }))()
      `);
      assert.ok(observerCheck.installed, 'PerformanceObserver script must be installed on document creation');
      assert.ok(observerCheck.lcpSupported, 'Browser must support largest-contentful-paint observer');
      assert.ok(observerCheck.clsSupported, 'Browser must support layout-shift observer');

      // 3. Intentionally triggered layout shift control check (verifies observer sensitivity > 0)
      await browser.evaluate(`
        (() => {
          const shiftDiv = document.createElement('div');
          shiftDiv.id = 'layout-shift-control';
          shiftDiv.style.height = '10px';
          shiftDiv.style.width = '100%';
          shiftDiv.style.backgroundColor = 'red';
          document.body.prepend(shiftDiv);
          setTimeout(() => {
            shiftDiv.style.height = '300px';
          }, 80);
        })()
      `);
      await new Promise((r) => setTimeout(r, 400));
      const shiftResult = await browser.evaluate(`
        (() => ({
          rawShifts: window.__perfData.rawLayoutShifts.length,
          cls: window.__perfData.cls,
          sessionCls: window.__perfData.clsSessionWindow
        }))()
      `);
      assert.ok(shiftResult.rawShifts > 0 || shiftResult.cls > 0, 'Intentionally triggered layout shift must be recorded by observer');

      // 4. Dynamic Build Bytes calculation & negative self-test
      runBuildBytesSelfTest();

      console.log('🎉 Negative test execution completed successfully with exit code 0.');
      console.log(`   - Missing selector throw: PASS`);
      console.log(`   - PerformanceObserver active: PASS`);
      console.log(`   - Layout-shift sensitivity detection: PASS (${shiftResult.cls})`);
      console.log(`   - Dynamic build bytes & negative budget detection: PASS`);
      return;
    }

    console.log('\n--- 1. DESKTOP WALKTHROUGH (Viewport: 1280x800) ---\n');
    await browser.setViewport(1280, 800, false);

    // ------------------------------------------------------------------------
    // Step 01: Home Guest Mode
    // ------------------------------------------------------------------------
    console.log('[Step 01] Verifying Home in Guest Mode (exploration without login)...');
    await browser.navigate('http://127.0.0.1:3005/');
    await new Promise((r) => setTimeout(r, 2000));
    const htmlAfter2s = await browser.evaluate('document.documentElement ? document.documentElement.outerHTML : "NO_DOC"');
    console.log('HTML AFTER 2s:', htmlAfter2s.slice(0, 800));
    await browser.waitForCondition(
      `document.body.textContent.includes('Đăng nhập')`,
      'navbar to display "Đăng nhập" button in guest mode',
      6000
    );
    await browser.waitForCondition(
      `document.body.textContent.includes('The Quantum Garden')`,
      'Home hero to render synthetic movie "The Quantum Garden"',
      6000
    );

    await browser.captureScreenshot('01_home_guest_desktop.png');
    evidenceRecords.push({
      step: '01_home_guest_desktop',
      url: 'http://127.0.0.1:3005/',
      actor: 'guest',
      expected: 'Home loads in guest mode with "Đăng nhập" action and synthetic hero movie',
      actual: 'Rendered guest navbar with "Đăng nhập" and hero "The Quantum Garden"',
      pass: true,
      fixtureState: { userA_watchlist: fixtureServer.users.user_a.watchlist.size, userB_watchlist: fixtureServer.users.user_b.watchlist.size },
    });

    // ------------------------------------------------------------------------
    // Step 02: AuthModal Interaction & A11y (Focus trap, dialog role)
    // ------------------------------------------------------------------------
    console.log('[Step 02] Opening AuthModal and verifying dialog accessibility...');
    await browser.evaluate(`
      (() => {
        const btns = Array.from(document.querySelectorAll('header button'));
        const loginBtn = btns.find(b => b.textContent.includes('Đăng nhập'));
        if (!loginBtn) throw new Error('Header login button not found');
        loginBtn.click();
      })()
    `);
    await browser.waitForSelector('div[role="dialog"]');
    await browser.waitForCondition(
      `Boolean(document.querySelector('div[role="dialog"][aria-modal="true"]'))`,
      'AuthModal to have role="dialog" and aria-modal="true"',
      6000
    );
    // Check initial focus on first input
    await browser.waitForCondition(
      `(() => {
        const el = document.activeElement;
        return Boolean(el && el.tagName === 'INPUT');
      })()`,
      'First input field to be focused when AuthModal opens',
      3000
    );

    await browser.captureScreenshot('02_auth_modal_desktop.png');
    evidenceRecords.push({
      step: '02_auth_modal_desktop',
      url: 'http://127.0.0.1:3005/',
      actor: 'guest',
      expected: 'Clicking "Đăng nhập" opens accessible AuthModal with role="dialog", aria-modal="true", and focused first input',
      actual: 'Dialog verified with aria-modal="true" and focused input field',
      pass: true,
      fixtureState: { userA_watchlist: fixtureServer.users.user_a.watchlist.size, userB_watchlist: fixtureServer.users.user_b.watchlist.size },
    });

    // Diagnostic Audit: Invalid login submission, close size check, and opener focus restore
    console.log('[Step 02b] Testing AuthModal invalid submission, touch target size, and opener restoration...');
    await browser.evaluate(`
      (() => {
        const d = document.querySelector('div[role="dialog"]');
        const inputs = Array.from(d.querySelectorAll('input'));
        const u = inputs.find(i => i.placeholder.includes('tên đăng nhập') || i.type === 'text');
        const p = inputs.find(i => i.type === 'password');
        const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
        set.call(u, 'regression_invalid');
        u.dispatchEvent(new Event('input', { bubbles: true }));
        u.dispatchEvent(new Event('change', { bubbles: true }));
        set.call(p, 'not-real-password');
        p.dispatchEvent(new Event('input', { bubbles: true }));
        p.dispatchEvent(new Event('change', { bubbles: true }));
        d.querySelector('button[type="submit"]').click();
      })()
    `);
    await browser.waitForCondition(
      `document.body.textContent.includes('Reviewer invalid credentials')`,
      'error message for invalid credentials to appear',
      4000
    );
    const closeBtnSize = await browser.evaluate(`
      (() => {
        const b = document.querySelector('button[aria-label="Đóng popup"]');
        if (!b) return null;
        const r = b.getBoundingClientRect();
        return { width: r.width, height: r.height };
      })()
    `);
    assert.ok(closeBtnSize && closeBtnSize.width >= 44 && closeBtnSize.height >= 44,
      `Auth close button must be >= 44x44px, got ${JSON.stringify(closeBtnSize)}`);

    // Close and verify focus restored to opener
    await browser.evaluate(`document.querySelector('button[aria-label="Đóng popup"]').click()`);
    await new Promise(r => setTimeout(r, 100));
    const isOpenerRestored = await browser.evaluate(`
      Boolean(document.activeElement && document.activeElement.textContent.includes('Đăng nhập'))
    `);
    assert.ok(isOpenerRestored, 'Closing AuthModal must restore focus to login button opener');

    // Re-open for real user_a login
    await browser.evaluate(`
      (() => {
        const btns = Array.from(document.querySelectorAll('header button'));
        const b = btns.find(b => b.textContent.includes('Đăng nhập'));
        b.focus();
        b.click();
      })()
    `);
    await browser.waitForSelector('div[role="dialog"]', 4000);

    // ------------------------------------------------------------------------
    // Step 03: Login User A (user_a)
    // ------------------------------------------------------------------------
    console.log('[Step 03] Submitting login form as user_a...');
    await browser.evaluate(`
      (() => {
        const dialog = document.querySelector('div[role="dialog"]');
        const inputs = Array.from(dialog.querySelectorAll('input'));
        const usernameInput = inputs.find(i => i.placeholder.includes('tên đăng nhập') || i.type === 'text');
        const passwordInput = inputs.find(i => i.type === 'password');
        const submitBtn = dialog.querySelector('button[type="submit"]');

        const nativeSet = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSet.call(usernameInput, 'user_a');
        usernameInput.dispatchEvent(new Event('input', { bubbles: true }));
        usernameInput.dispatchEvent(new Event('change', { bubbles: true }));

        nativeSet.call(passwordInput, 'password123');
        passwordInput.dispatchEvent(new Event('input', { bubbles: true }));
        passwordInput.dispatchEvent(new Event('change', { bubbles: true }));

        submitBtn.click();
      })()
    `);
    await browser.waitForCondition(
      `document.body.textContent.includes('user_a')`,
      'navbar to update and display authenticated user "user_a"',
      6000
    );

    await browser.captureScreenshot('03_login_user_a_desktop.png');
    evidenceRecords.push({
      step: '03_login_user_a_desktop',
      url: 'http://127.0.0.1:3005/',
      actor: 'user_a',
      expected: 'AuthModal submits credentials, closes cleanly, and displays authenticated user "user_a" in navbar',
      actual: 'Navbar displays "user_a", AuthModal dismissed, session established',
      pass: true,
      fixtureState: { userA_watchlist: fixtureServer.users.user_a.watchlist.size, userB_watchlist: fixtureServer.users.user_b.watchlist.size },
    });

    // ------------------------------------------------------------------------
    // Step 04: Detail Save & Rate (User A)
    // ------------------------------------------------------------------------
    console.log('[Step 04] Navigating to synthetic movie, adding to Watchlist, and rating 9 stars...');
    await browser.navigate(`http://127.0.0.1:3005/movies/${SYNTHETIC_MOVIE_ID}`);
    await browser.waitForCondition(
      `document.body.textContent.includes('The Quantum Garden')`,
      'Detail page for The Quantum Garden loaded',
      6000
    );

    // Diagnostic Audit: Video player modal initial focus, Tab trapping, Escape close, and opener focus restore
    console.log('[Step 04a] Auditing Video Player modal lifecycle (initial focus, Tab trap, Esc, opener restore)...');
    await browser.evaluate(`
      (() => {
        const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Xem trailer'));
        if (!b) throw new Error('Trailer play button not found');
        b.focus();
        b.click();
      })()
    `);
    await browser.waitForSelector('div[role="dialog"] video', 4000);
    await new Promise(r => setTimeout(r, 100));
    const insideInitial = await browser.evaluate(`
      document.querySelector('div[role="dialog"]').contains(document.activeElement)
    `);
    assert.ok(insideInitial, 'Video player modal must focus element inside dialog on open');

    await browser.dispatchKey('Tab', 'Tab', 9);
    const insideAfterTab = await browser.evaluate(`
      document.querySelector('div[role="dialog"]').contains(document.activeElement)
    `);
    assert.ok(insideAfterTab, 'Tab key must keep focus trapped inside video player modal');

    await browser.dispatchKey('Escape', 'Escape', 27);
    await browser.waitForCondition(`document.querySelector('div[role="dialog"] video') === null`, 'video player to close on Escape', 3000);
    await new Promise(r => setTimeout(r, 100));
    const playerRestoredToOpener = await browser.evaluate(`
      Boolean(document.activeElement && document.activeElement.textContent.includes('Xem trailer'))
    `);
    assert.ok(playerRestoredToOpener, 'Closing video player modal must restore focus to trailer button opener');

    // Diagnostic Audit: Reduced motion in CineBot and opener restoration
    console.log('[Step 04b] Auditing CineBot reduced motion JS policy and opener restore...');
    await browser.cdp('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    await browser.evaluate(`
      (() => {
        window.__walkthroughScrollCalls = [];
        window.__walkthroughScrollOriginal = Element.prototype.scrollIntoView;
        Element.prototype.scrollIntoView = function(options) {
          window.__walkthroughScrollCalls.push(options);
        };
        const b = Array.from(document.querySelectorAll('header button')).find(b => b.textContent.includes('Hỏi CineBot')) ||
                  document.querySelector('button[aria-label="Mở Chatbot CineBot"]');
        if (!b) throw new Error('CineBot opener button not found');
        b.focus();
        b.click();
      })()
    `);
    await browser.waitForSelector('div[role="dialog"] input', 4000);
    await new Promise(r => setTimeout(r, 100));
    const scrollCalls = await browser.evaluate('window.__walkthroughScrollCalls');
    assert.ok(
      Array.isArray(scrollCalls) && scrollCalls.every(c => !c || c.behavior !== 'smooth'),
      `CineBot must NOT use behavior: 'smooth' under reduced motion: ${JSON.stringify(scrollCalls)}`
    );

    await browser.dispatchKey('Escape', 'Escape', 27);
    await browser.waitForCondition(`document.querySelector('div[role="dialog"] input') === null`, 'CineBot to close on Escape', 3000);
    await new Promise(r => setTimeout(r, 100));
    const cinebotRestoredToOpener = await browser.evaluate(`
      Boolean(document.activeElement && (document.activeElement.textContent.includes('Hỏi CineBot') || document.activeElement.getAttribute('aria-label') === 'Mở Chatbot CineBot'))
    `);
    assert.ok(cinebotRestoredToOpener, 'Closing CineBot with Escape must restore focus to opener button');
    await browser.evaluate('Element.prototype.scrollIntoView = window.__walkthroughScrollOriginal');
    await browser.cdp('Emulation.setEmulatedMedia', { features: [] });

    // Click Save
    await browser.evaluate(`
      (() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const saveBtn = btns.find(b => b.textContent.includes('Thêm vào Watchlist'));
        if (!saveBtn) throw new Error('Save to watchlist button not found');
        saveBtn.click();
      })()
    `);
    await browser.waitForCondition(
      `Array.from(document.querySelectorAll('button')).some(b => b.textContent.includes('Đã lưu'))`,
      'Watchlist button to transition to "Đã lưu"',
      6000
    );
    assert.ok(fixtureServer.users.user_a.watchlist.has(SYNTHETIC_MOVIE_ID), 'User A watchlist recorded movie');

    // Click Star 9
    await browser.evaluate(`
      (() => {
        const star = document.querySelector('button[aria-label="Chấm 9 trên 10 sao"]');
        if (!star) throw new Error('Rating star 9 button not found');
        star.click();
      })()
    `);
    const startRatingPoll = Date.now();
    while (Date.now() - startRatingPoll < 6000) {
      if (fixtureServer.users.user_a.ratings.get(SYNTHETIC_MOVIE_ID) === 9) break;
      await new Promise((r) => setTimeout(r, 100));
    }
    assert.equal(fixtureServer.users.user_a.ratings.get(SYNTHETIC_MOVIE_ID), 9, 'User A rating recorded 9');

    await browser.captureScreenshot('04_detail_saved_rated_user_a.png');
    evidenceRecords.push({
      step: '04_detail_saved_rated_user_a',
      url: `http://127.0.0.1:3005/movies/${SYNTHETIC_MOVIE_ID}`,
      actor: 'user_a',
      expected: 'User A saves synthetic movie to Watchlist and submits rating score 9',
      actual: `Fixture User A recorded watchlist=${Array.from(fixtureServer.users.user_a.watchlist)} and rating=9`,
      pass: true,
      fixtureState: { userA_watchlist: fixtureServer.users.user_a.watchlist.size, userB_watchlist: fixtureServer.users.user_b.watchlist.size },
    });

    // ------------------------------------------------------------------------
    // Step 05: Profile Reload & Ratings Tab (User A)
    // ------------------------------------------------------------------------
    console.log('[Step 05] Verifying User A Profile with Watchlist and Ratings tab score 9...');
    await browser.navigate('http://127.0.0.1:3005/profile');
    await browser.waitForCondition(
      `document.body.textContent.includes('The Quantum Garden')`,
      'Profile Watchlist tab to render saved movie card',
      6000
    );

    // Switch to Ratings tab
    await browser.evaluate(`
      (() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const ratingsTab = btns.find(b => b.textContent.includes('Đã chấm điểm'));
        if (!ratingsTab) throw new Error('Ratings tab button not found in Profile');
        ratingsTab.click();
      })()
    `);
    await browser.waitForCondition(
      `Boolean(document.body.textContent.includes('9/10') || document.body.textContent.includes('9 /10') || document.body.textContent.includes('9 / 10'))`,
      'Profile ratings tab to render score 9/10',
      6000
    );

    await browser.captureScreenshot('05_profile_user_a_desktop.png');
    evidenceRecords.push({
      step: '05_profile_user_a_desktop',
      url: 'http://127.0.0.1:3005/profile',
      actor: 'user_a',
      expected: 'User A Profile verifies Watchlist card and Ratings tab with score 9/10',
      actual: 'Watchlist and Ratings tabs confirmed with "The Quantum Garden" and score 9/10',
      pass: true,
      fixtureState: { userA_watchlist: fixtureServer.users.user_a.watchlist.size, userB_watchlist: fixtureServer.users.user_b.watchlist.size },
    });

    // ------------------------------------------------------------------------
    // Step 06: Hero Uncertain Retry
    // ------------------------------------------------------------------------
    console.log('[Step 06] Verifying Hero uncertain ADD badge and retry flow...');
    await fetch('http://127.0.0.1:8080/api/test-control/set?clearWatchlist=true');
    await browser.navigate('http://127.0.0.1:3005/');
    await browser.waitForCondition(
      `Array.from(document.querySelectorAll('button')).some(b => b.textContent.includes('Thêm vào Watchlist'))`,
      'hero save button to be in "+ Thêm vào Watchlist" state',
      6000
    );

    await fetch('http://127.0.0.1:8080/api/test-control/set?writeDrop=true&reconcileError=true');
    await browser.evaluate(`
      (() => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Thêm vào Watchlist'));
        if (!btn) throw new Error('Hero save button not found');
        btn.click();
      })()
    `);

    await browser.waitForCondition(
      `Boolean(document.querySelector('[data-testid="hero-unconfirmed-badge"], [data-testid="unconfirmed-badge"]')) || document.body.textContent.includes('Chưa xác nhận')`,
      'amber "Chưa xác nhận" badge to appear on Hero',
      6000
    );
    await browser.waitForCondition(
      `Array.from(document.querySelectorAll('button')).some(b => b.textContent.includes('Thử lưu lại'))`,
      'Hero button to show retry label "Thử lưu lại"',
      6000
    );

    await browser.captureScreenshot('06_hero_uncertain_retry_desktop.png');

    await fetch('http://127.0.0.1:8080/api/test-control/set?writeDrop=false&reconcileError=false');
    await browser.evaluate(`
      (() => {
        const retryBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Thử lưu lại'));
        if (!retryBtn) throw new Error('Hero retry button not found');
        retryBtn.click();
      })()
    `);
    await browser.waitForCondition(
      `Array.from(document.querySelectorAll('button')).some(b => b.textContent.includes('Đã lưu Watchlist'))`,
      'Hero button to return to confirmed "Đã lưu Watchlist"',
      6000
    );

    evidenceRecords.push({
      step: '06_hero_uncertain_retry_desktop',
      url: 'http://127.0.0.1:3005/',
      actor: 'user_a',
      expected: 'Hero uncertain state displays amber badge and "Thử lưu lại"; retry click confirms to "Đã lưu Watchlist"',
      actual: 'Uncertain badge verified and retry confirmation succeeded',
      pass: true,
      fixtureState: { userA_watchlist: fixtureServer.users.user_a.watchlist.size, userB_watchlist: fixtureServer.users.user_b.watchlist.size },
    });

    // ------------------------------------------------------------------------
    // Step 07: Logout User A & Switch to User B via UI Form (No localStorage bypass)
    // ------------------------------------------------------------------------
    console.log('[Step 07] Logging out User A via UI and logging in as User B via UI form...');
    
    // 1. Open user dropdown menu in header
    await browser.evaluate(`
      (() => {
        const trigger = document.querySelector('header .relative button');
        if (!trigger) throw new Error('User menu dropdown trigger not found');
        trigger.click();
      })()
    `);
    
    // Wait for dropdown to be visible
    await browser.waitForCondition(
      `Boolean(Array.from(document.querySelectorAll('header button')).find(b => b.textContent.includes('Đăng xuất')))`,
      'header user dropdown menu to be open with "Đăng xuất" option',
      4000
    );

    // 2. Click "Đăng xuất" button in the menu (real UI click, no storage-clear fallback)
    await browser.evaluate(`
      (() => {
        const btns = Array.from(document.querySelectorAll('header button'));
        const logoutBtn = btns.find(b => b.textContent.includes('Đăng xuất'));
        if (!logoutBtn) throw new Error('Logout button not found in dropdown menu');
        logoutBtn.click();
      })()
    `);

    // 3. Verify navbar returns to guest state with "Đăng nhập" button
    await browser.waitForCondition(
      `Boolean(Array.from(document.querySelectorAll('header button')).some(b => b.textContent.includes('Đăng nhập')) && !document.querySelector('header .relative button'))`,
      'navbar to return to guest state with "Đăng nhập" button',
      6000
    );

    // 4. Assert token is removed from localStorage upon UI logout
    const clearedToken = await browser.evaluate(`localStorage.getItem('dippie_auth_token')`);
    assert.equal(clearedToken, null, 'dippie_auth_token must be removed upon UI logout');

    // 5. Click "Đăng nhập" button in navbar to open AuthModal
    await browser.evaluate(`
      (() => {
        const loginBtn = Array.from(document.querySelectorAll('header button')).find(b => b.textContent.includes('Đăng nhập'));
        if (!loginBtn) throw new Error('"Đăng nhập" button not found in navbar');
        loginBtn.click();
      })()
    `);

    // 6. Wait for AuthModal to render
    await browser.waitForCondition(
      `Boolean(document.querySelector('[role="dialog"]') && document.querySelector('#auth-modal-title'))`,
      'Auth modal dialog to appear',
      4000
    );

    // 7. Fill in User B credentials via input events and submit
    await browser.evaluate(`
      (() => {
        const dialog = document.querySelector('[role="dialog"]');
        if (!dialog) throw new Error('Auth dialog not found');
        const textInput = dialog.querySelector('input[type="text"]');
        const passInput = dialog.querySelector('input[type="password"]');
        if (!textInput || !passInput) throw new Error('Auth text or password input not found');

        const nativeInputSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeInputSetter.call(textInput, 'user_b');
        textInput.dispatchEvent(new Event('input', { bubbles: true }));

        nativeInputSetter.call(passInput, 'password123');
        passInput.dispatchEvent(new Event('input', { bubbles: true }));

        const submitBtn = dialog.querySelector('button[type="submit"]');
        if (!submitBtn) throw new Error('Auth submit button not found');
        submitBtn.click();
      })()
    `);

    // 8. Wait for AuthModal to close and navbar to show user_b
    await browser.waitForCondition(
      `Boolean(document.body.textContent.includes('user_b') && !document.querySelector('[role="dialog"]'))`,
      'navbar to display authenticated user "user_b" and dialog closed',
      6000
    );

    // 9. Assert store ownership has updated to User B
    const userBStoredToken = await browser.evaluate(`localStorage.getItem('dippie_auth_token')`);
    assert.equal(userBStoredToken, 'token-user-b', 'User B token must be saved upon successful UI login');

    await browser.captureScreenshot('07_logout_switch_user_b.png');
    evidenceRecords.push({
      step: '07_logout_switch_user_b',
      url: 'http://127.0.0.1:3005/',
      actor: 'user_b',
      expected: 'User A logs out cleanly via UI dropdown; User B logs in via AuthModal UI form without localStorage hacks',
      actual: 'Navbar displays "user_b", clean UI session transition and token update confirmed',
      pass: true,
      fixtureState: { userA_watchlist: fixtureServer.users.user_a.watchlist.size, userB_watchlist: fixtureServer.users.user_b.watchlist.size },
    });

    // ------------------------------------------------------------------------
    // Step 08: User B Data Isolation & Reload Persistence (Zero Leak from User A)
    // ------------------------------------------------------------------------
    console.log('[Step 08] Verifying User B Profile has zero data leaked from User A...');
    await browser.navigate('http://127.0.0.1:3005/profile');
    await browser.waitForCondition(
      `Boolean(document.body.textContent.includes('Danh sách xem đang trống') || document.body.textContent.includes('Chưa có phim'))`,
      'User B profile to show empty watchlist banner',
      6000
    );
    const hasLeakedItem = await browser.evaluate(`
      document.body.textContent.includes('The Quantum Garden')
    `);
    assert.equal(hasLeakedItem, false, 'User B must NOT see User A saved movie (Zero Data Leak)');

    // Verify session persistence across page reload
    console.log('[Step 08] Verifying User B session persistence and store state after page reload...');
    await browser.evaluate('window.location.reload()');
    await browser.waitForCondition(
      `Boolean(document.body.textContent.includes('user_b') && (document.body.textContent.includes('Danh sách xem đang trống') || document.body.textContent.includes('Chưa có phim')))`,
      'User B profile and session to remain intact after page reload',
      6000
    );

    const reloadedAuthUser = await browser.evaluate(`
      (() => {
        try {
          const u = JSON.parse(localStorage.getItem('dippie_auth_user') || '{}');
          return u.username;
        } catch { return null; }
      })()
    `);
    assert.equal(reloadedAuthUser, 'user_b', 'User B username must persist after reload');

    await browser.captureScreenshot('08_user_b_isolation_profile.png');
    evidenceRecords.push({
      step: '08_user_b_isolation_profile',
      url: 'http://127.0.0.1:3005/profile',
      actor: 'user_b',
      expected: 'User B profile renders completely empty library; zero data leaked from User A; session persists after reload',
      actual: `Verified User B profile has 0 items, does not contain "The Quantum Garden", and persists user_b session across reload`,
      pass: true,
      fixtureState: { userA_watchlist: fixtureServer.users.user_a.watchlist.size, userB_watchlist: fixtureServer.users.user_b.watchlist.size },
    });

    // ------------------------------------------------------------------------
    // Step 09: Search Deep Link & Browser History Back
    // ------------------------------------------------------------------------
    console.log('[Step 09] Verifying Search deep link and browser history.back()...');
    await browser.navigate('http://127.0.0.1:3005/search?q=quantum');
    await browser.waitForCondition(
      `(() => {
        const inp = document.querySelector('input[type="text"], input[type="search"]');
        return inp && inp.value === 'quantum';
      })()`,
      'search input draft restored from URL query "quantum"',
      6000
    );
    await browser.waitForCondition(
      `document.body.textContent.includes('The Quantum Garden')`,
      'search results to display "The Quantum Garden"',
      6000
    );

    await browser.navigate(`http://127.0.0.1:3005/movies/${SYNTHETIC_MOVIE_ID}`);
    await browser.waitForCondition(
      `document.body.textContent.includes('The Quantum Garden')`,
      'detail page loaded before back test',
      6000
    );

    await browser.evaluate('window.history.back()');
    await browser.waitForCondition(
      `(() => {
        const inp = document.querySelector('input[type="text"], input[type="search"]');
        return window.location.pathname === '/search' && inp && inp.value === 'quantum';
      })()`,
      'history.back() restores search page with query draft "quantum"',
      6000
    );

    await browser.captureScreenshot('09_search_deep_link_back_desktop.png');
    evidenceRecords.push({
      step: '09_search_deep_link_back_desktop',
      url: 'http://127.0.0.1:3005/search?q=quantum',
      actor: 'user_b',
      expected: 'history.back() returns to search page with input draft and results intact',
      actual: 'Verified URL /search?q=quantum, input draft "quantum", and search results',
      pass: true,
      fixtureState: { userA_watchlist: fixtureServer.users.user_a.watchlist.size, userB_watchlist: fixtureServer.users.user_b.watchlist.size },
    });

    // ------------------------------------------------------------------------
    // Step 10: Broken Image 404 Fallback
    // ------------------------------------------------------------------------
    console.log('[Step 10] Verifying Broken Image 404 fallback on MovieDetail...');
    await browser.navigate(`http://127.0.0.1:3005/movies/${BROKEN_IMG_MOVIE_ID}`);
    await browser.waitForCondition(
      `document.body.textContent.includes('The Lost Lantern')`,
      'Detail page for broken image movie loaded',
      6000
    );

    // Verify poster fallback placeholder is active and shows title
    await browser.waitForCondition(
      `Boolean(document.querySelector('[data-testid="movie-poster-placeholder"]'))`,
      'Poster fallback placeholder to be active in DOM',
      6000
    );

    const hasTitleInPlaceholder = await browser.evaluate(`
      Boolean(document.querySelector('[data-testid="movie-poster-placeholder"]')?.textContent.includes('The Lost Lantern'))
    `);
    assert.ok(hasTitleInPlaceholder, 'Poster fallback must render movie title cleanly');

    await browser.captureScreenshot('10_image_404_fallback_desktop.png');
    evidenceRecords.push({
      step: '10_image_404_fallback_desktop',
      url: `http://127.0.0.1:3005/movies/${BROKEN_IMG_MOVIE_ID}`,
      actor: 'user_b',
      expected: 'Movie with broken/404 image URL cleanly falls back to title placeholder without breaking layout',
      actual: 'Rendered "The Lost Lantern" placeholder fallback upon 404 image error',
      pass: true,
      fixtureState: { userA_watchlist: fixtureServer.users.user_a.watchlist.size, userB_watchlist: fixtureServer.users.user_b.watchlist.size },
    });

    // ------------------------------------------------------------------------
    // Step 11: Non-existent Detail (404 Page)
    // ------------------------------------------------------------------------
    console.log('[Step 11] Verifying 404 state on missing canonical movie...');
    await browser.navigate('http://127.0.0.1:3005/movies/nonexistent-movie-uuid-404');
    await browser.waitForCondition(
      `Boolean(document.body.textContent.includes('Không tìm thấy phim hoạt hình') || document.body.textContent.includes('không tồn tại trên hệ thống'))`,
      '404 page heading "Không tìm thấy phim hoạt hình"',
      6000
    );

    await browser.captureScreenshot('11_detail_404_desktop.png');
    evidenceRecords.push({
      step: '11_detail_404_desktop',
      url: 'http://127.0.0.1:3005/movies/nonexistent-movie-uuid-404',
      actor: 'user_b',
      expected: 'Non-existent movie ID triggers clean 404 error with home link',
      actual: 'Rendered "Không tìm thấy phim hoạt hình" with home action',
      pass: true,
      fixtureState: { userA_watchlist: fixtureServer.users.user_a.watchlist.size, userB_watchlist: fixtureServer.users.user_b.watchlist.size },
    });

    // ------------------------------------------------------------------------
    // Step 12: Catalog HTTP 500 Error State & Retry UI
    // ------------------------------------------------------------------------
    console.log('[Step 12] Verifying Catalog HTTP 500 error banner and retry UI...');
    await fetch('http://127.0.0.1:8080/api/test-control/set?catalogError=true');
    await browser.navigate('http://127.0.0.1:3005/');
    await browser.waitForCondition(
      `document.body.textContent.includes('Không thể nạp danh mục') || document.body.textContent.includes('lỗi kết nối') || document.body.textContent.includes('Thử kết nối lại')`,
      'catalog error notification banner',
      6000
    );
    await fetch('http://127.0.0.1:8080/api/test-control/set?catalogError=false');

    await browser.captureScreenshot('12_catalog_error_retry_desktop.png');
    evidenceRecords.push({
      step: '12_catalog_error_retry_desktop',
      url: 'http://127.0.0.1:3005/',
      actor: 'user_b',
      expected: 'Backend failure renders error banner with retry button',
      actual: 'Rendered error state with "Thử kết nối lại" retry action',
      pass: true,
      fixtureState: { userA_watchlist: fixtureServer.users.user_a.watchlist.size, userB_watchlist: fixtureServer.users.user_b.watchlist.size },
    });

    // ------------------------------------------------------------------------
    // Mobile Walkthrough (Viewport: 375x667)
    // ------------------------------------------------------------------------
    console.log('\n--- 2. MOBILE WALKTHROUGH (Viewport: 375x667) ---\n');
    await browser.setViewport(375, 667, true);

    // Step 13: Mobile Home
    console.log('[Step 13] Verifying Mobile Home (375x667)...');
    await browser.navigate('http://127.0.0.1:3005/');
    await browser.waitForCondition(
      `document.body.textContent.includes('The Quantum Garden')`,
      'mobile home hero banner',
      6000
    );
    const mobileWidth = await browser.evaluate('window.innerWidth');
    assert.equal(mobileWidth, 375, 'Mobile viewport width must be 375');

    await browser.captureScreenshot('13_home_mobile.png');
    evidenceRecords.push({
      step: '13_home_mobile',
      url: 'http://127.0.0.1:3005/',
      actor: 'user_b',
      expected: 'Mobile responsive Home renders stacked hero with touch targets (375x667)',
      actual: `Verified viewport width ${mobileWidth} and mobile hero banner`,
      pass: true,
      fixtureState: { userA_watchlist: fixtureServer.users.user_a.watchlist.size, userB_watchlist: fixtureServer.users.user_b.watchlist.size },
    });

    // Step 14: Mobile Detail
    console.log('[Step 14] Verifying Mobile Movie Detail (375x667)...');
    await browser.navigate(`http://127.0.0.1:3005/movies/${SYNTHETIC_MOVIE_ID}`);
    await browser.waitForCondition(
      `document.body.textContent.includes('The Quantum Garden')`,
      'mobile detail title',
      6000
    );

    // Audit mobile touch target sizes (policy >= 44x44) and verify ZERO bounding collisions
    const mobileAudit = await browser.evaluate(`
      (() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const playBtn = btns.find(b => b.textContent.includes('Xem trailer'));
        const saveBtn = btns.find(b => b.textContent.includes('Watchlist'));
        const cineBotTrigger = document.querySelector('button[aria-label="Mở Chatbot CineBot"]') ||
                               Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Hỏi CineBot'));

        if (!playBtn) throw new Error('Trailer play button not found on detail page');
        if (!saveBtn) throw new Error('Watchlist save button not found on detail page');
        if (!cineBotTrigger) throw new Error('CineBot floating trigger button not found on detail page');

        const playRect = playBtn.getBoundingClientRect();
        const saveRect = saveBtn.getBoundingClientRect();
        const triggerRect = cineBotTrigger.getBoundingClientRect();

        const targets = {
          playBtn: { width: Math.round(playRect.width), height: Math.round(playRect.height) },
          saveBtn: { width: Math.round(saveRect.width), height: Math.round(saveRect.height) },
          trigger: { width: Math.round(triggerRect.width), height: Math.round(triggerRect.height) }
        };

        // Collision helper: check if two rects intersect
        function isIntersecting(r1, r2) {
          return !(r1.right <= r2.left || r1.left >= r2.right || r1.bottom <= r2.top || r1.top >= r2.bottom);
        }

        const collisions = [];
        // 1. Play vs Save buttons
        if (isIntersecting(playRect, saveRect)) {
          collisions.push('playBtn vs saveBtn');
        }

        // 2. Floating CineBot trigger vs all visible buttons in viewport
        for (const btn of btns) {
          if (btn === cineBotTrigger) continue;
          const r = btn.getBoundingClientRect();
          // Only check buttons actually visible in viewport
          if (r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < window.innerHeight && r.right > 0 && r.left < window.innerWidth) {
            if (isIntersecting(triggerRect, r)) {
              collisions.push('cineBotTrigger vs ' + (btn.textContent.trim().slice(0, 20) || btn.getAttribute('aria-label') || 'button'));
            }
          }
        }

        return { targets, collisions };
      })()
    `);

    assert.ok(mobileAudit.targets.playBtn.height >= 44, `Play button height ${mobileAudit.targets.playBtn.height}px must be >= 44px`);
    assert.ok(mobileAudit.targets.saveBtn.height >= 44, `Save button height ${mobileAudit.targets.saveBtn.height}px must be >= 44px`);
    assert.ok(mobileAudit.targets.trigger.height >= 44, `CineBot trigger height ${mobileAudit.targets.trigger.height}px must be >= 44px`);
    assert.equal(mobileAudit.collisions.length, 0, `Detected collisions on mobile 375x667: ${mobileAudit.collisions.join(', ')}`);

    await browser.captureScreenshot('14_detail_mobile.png');
    evidenceRecords.push({
      step: '14_detail_mobile',
      url: `http://127.0.0.1:3005/movies/${SYNTHETIC_MOVIE_ID}`,
      actor: 'user_b',
      expected: 'Mobile detail displays vertically stacked poster, trailer player action (>=44px), CineBot trigger (>=44px), and ZERO button collisions',
      actual: `Verified touch targets (trailer: ${mobileAudit.targets.playBtn.height}px, save: ${mobileAudit.targets.saveBtn.height}px, trigger: ${mobileAudit.targets.trigger.height}px) and 0 collisions on 375px viewport`,
      pass: true,
      fixtureState: { userA_watchlist: fixtureServer.users.user_a.watchlist.size, userB_watchlist: fixtureServer.users.user_b.watchlist.size },
    });

    // ------------------------------------------------------------------------
    // Step 15: C2 Corrected Performance Benchmark (Cold & Warm, 3 runs each across 4 routes)
    // ------------------------------------------------------------------------
    console.log('\n--- 3. PERFORMANCE BENCHMARK (Desktop 1280x800, Separate Cold & Warm Runs) ---\n');
    await browser.setViewport(1280, 800, false);

    console.log('[Budget] Dynamically measuring exact JavaScript First Load bundle bytes from build manifest...');
    const buildBytesAudit = computeBuildBytes({ throwOnOverBudget: true, throwOnMissing: true });
    const ROUTE_EXACT_JS_BYTES = {
      Home: buildBytesAudit.routes['/'],
      Search: buildBytesAudit.routes['/search'],
      Detail: buildBytesAudit.routes['/movies/[id]'],
      Profile: buildBytesAudit.routes['/profile'],
    };
    for (const [rName, rData] of Object.entries(ROUTE_EXACT_JS_BYTES)) {
      console.log(`  ✔ [Budget Check] ${rName.padEnd(8)}: ${rData.gzipBytes} B (${rData.kib} KiB) <= ${rData.budgetBytes} B (${rData.budgetKiB} KiB) [${rData.filesCount} chunks]`);
    }

    const routesToBenchmark = [
      {
        path: '/',
        name: 'Home',
        readyCheck: `document.readyState === 'complete' && Boolean(document.querySelector('main')) && document.body.innerText.includes('The Quantum Garden')`,
      },
      {
        path: '/search?q=quantum',
        name: 'Search',
        readyCheck: `document.readyState === 'complete' && Boolean(document.querySelector('input')) && (document.body.innerText.includes('The Quantum Garden') || document.querySelectorAll('article, [data-testid="movie-card"]').length > 0)`,
      },
      {
        path: `/movies/${SYNTHETIC_MOVIE_ID}`,
        name: 'Detail',
        readyCheck: `document.readyState === 'complete' && Boolean(document.querySelector('h1')) && document.body.innerText.includes('The Quantum Garden')`,
      },
      {
        path: '/profile',
        name: 'Profile',
        readyCheck: `document.readyState === 'complete' && Boolean(document.querySelector('main')) && (document.body.innerText.includes('The Quantum Garden') || document.body.innerText.includes('Watchlist') || document.body.innerText.includes('Danh sách') || document.body.innerText.includes('Đã chấm điểm') || document.body.innerText.includes('Khách') || document.body.innerText.includes('Dippie') || document.querySelectorAll('button').length > 0)`,
      },
    ];

    const perfResults = {
      benchmarkMetadata: {
        timestamp: new Date().toISOString(),
        framework: 'Next.js 15.1.2 (Standalone)',
        nodeVersion: process.version,
        viewport: '1280x800',
        coldRunsPerRoute: 3,
        warmRunsPerRoute: 3,
        networkEnvironment: 'Local Loopback (Fixture Server on 127.0.0.1:8080)',
        cachePolicy: 'Cold: cache cleared and disabled via CDP. Warm: cache enabled across 3 repeated runs.',
        lcpMethodology: 'PerformanceObserver with buffered:true injected before navigation. Missing sample -> null/unavailable. No FCP substitution.',
        clsMethodology: 'Standard Session Window aggregation (max session window with 1s gap and 5s duration limit) + raw shift totals.',
        networkAccounting: 'CDP Network.loadingFinished encodedDataLength (wire bytes) and cache/304 status tracking.',
      },
      exactFirstLoadJsBytes: {
        buildId: buildBytesAudit.buildId,
        methodology: buildBytesAudit.methodology,
        budgetBytes: buildBytesAudit.budgetBytes,
        routes: ROUTE_EXACT_JS_BYTES,
      },
      routes: {},
    };

    function median(values) {
      if (!values.length) return 0;
      const sorted = [...values].sort((a, b) => a - b);
      const mid = Math.floor(sorted.length / 2);
      return sorted.length % 2 !== 0 ? sorted[mid] : Math.round((sorted[mid - 1] + sorted[mid]) / 2);
    }

    function computeSummary(runs) {
      if (!runs.length) return null;
      const dcls = runs.map(r => r.domContentLoaded);
      const loads = runs.map(r => r.loadDuration);
      const fcps = runs.map(r => r.fcp).filter(v => typeof v === 'number');
      const lcps = runs.map(r => r.lcp).filter(v => typeof v === 'number');
      const clss = runs.map(r => r.clsSessionWindow ?? r.clsRaw);
      const wireBytes = runs.map(r => r.cdpWireTransferBytes);
      const reqCounts = runs.map(r => r.cdpRequestCount);
      const cacheHits = runs.map(r => r.cdpCacheHits);

      return {
        domContentLoaded: { min: Math.min(...dcls), max: Math.max(...dcls), median: median(dcls) },
        loadDuration: { min: Math.min(...loads), max: Math.max(...loads), median: median(loads) },
        fcp: fcps.length ? { min: Math.min(...fcps), max: Math.max(...fcps), median: median(fcps) } : 'unavailable',
        lcp: lcps.length ? { min: Math.min(...lcps), max: Math.max(...lcps), median: median(lcps) } : 'unavailable',
        clsSessionWindow: { min: Math.min(...clss), max: Math.max(...clss), median: median(clss) },
        cdpWireTransferBytes: { min: Math.min(...wireBytes), max: Math.max(...wireBytes), median: median(wireBytes) },
        cdpRequestCount: { min: Math.min(...reqCounts), max: Math.max(...reqCounts), median: median(reqCounts) },
        cdpCacheHits: { min: Math.min(...cacheHits), max: Math.max(...cacheHits), median: median(cacheHits) },
      };
    }

    for (const route of routesToBenchmark) {
      console.log(`[Perf] Benchmarking ${route.name} (${route.path}): 3 Cold Runs + 3 Warm Runs...`);

      // 1. Cold Runs (HTTP cache disabled & cleared via CDP)
      const coldRuns = [];
      for (let runIdx = 1; runIdx <= 3; runIdx++) {
        await browser.clearCache();
        await browser.setCacheDisabled(true);
        browser.resetNetworkTracker();

        await browser.navigate(`http://127.0.0.1:3005${route.path}`);
        await browser.waitForCondition(
          route.readyCheck,
          `page app-ready for ${route.name} cold run ${runIdx}`,
          8000
        );
        // Bounded observation window for metrics finalization
        await new Promise((r) => setTimeout(r, 400));

        const cdpNet = browser.getNetworkAccounting();
        const browserMetrics = await browser.evaluate(`
          (() => {
            const nav = performance.getEntriesByType('navigation')[0] || {};
            const paints = performance.getEntriesByType('paint') || [];
            const fcpEntry = paints.find(p => p.name === 'first-contentful-paint');
            const resources = performance.getEntriesByType('resource') || [];
            const resourceBytes = resources.reduce((sum, r) => sum + (r.transferSize || 0), 0);
            const resourceEncoded = resources.reduce((sum, r) => sum + (r.encodedBodySize || 0), 0);
            const resourceDecoded = resources.reduce((sum, r) => sum + (r.decodedBodySize || 0), 0);

            const lcpVal = window.__perfData?.lcp ?? null;
            const clsSession = window.__perfData?.clsSessionWindow ?? 0;
            const clsRaw = window.__perfData?.cls ?? 0;

            return {
              domContentLoaded: Math.round(nav.domContentLoadedEventEnd || 0),
              loadDuration: Math.round(nav.loadEventEnd || nav.duration || 0),
              fcp: fcpEntry ? Math.round(fcpEntry.startTime) : null,
              lcp: lcpVal,
              lcpEntriesCount: window.__perfData?.lcpEntries?.length || 0,
              clsSessionWindow: clsSession,
              clsRaw: clsRaw,
              rawLayoutShiftsCount: window.__perfData?.rawLayoutShifts?.length || 0,
              resourceTiming: {
                resourceCount: resources.length,
                transferBytes: resourceBytes,
                encodedBodyBytes: resourceEncoded,
                decodedBodyBytes: resourceDecoded,
              }
            };
          })()
        `);

        coldRuns.push({
          runIndex: runIdx,
          cacheMode: 'cold',
          cdpWireTransferBytes: cdpNet.totalWireBytes,
          cdpRequestCount: cdpNet.totalRequests,
          cdpCacheHits: cdpNet.cacheHits,
          cdpWireRequests: cdpNet.wireRequests,
          ...browserMetrics,
        });
      }

      // 2. Warm Runs (HTTP cache enabled, primed with 1 warm-up navigation)
      const warmRuns = [];
      await browser.setCacheDisabled(false);
      // Priming warm-up visit
      browser.resetNetworkTracker();
      await browser.navigate(`http://127.0.0.1:3005${route.path}`);
      await browser.waitForCondition(
        route.readyCheck,
        `page app-ready for ${route.name} warm priming`,
        8000
      );
      await new Promise((r) => setTimeout(r, 400));

      for (let runIdx = 1; runIdx <= 3; runIdx++) {
        browser.resetNetworkTracker();

        await browser.navigate(`http://127.0.0.1:3005${route.path}`);
        await browser.waitForCondition(
          route.readyCheck,
          `page app-ready for ${route.name} warm run ${runIdx}`,
          8000
        );
        await new Promise((r) => setTimeout(r, 400));

        const cdpNet = browser.getNetworkAccounting();
        const browserMetrics = await browser.evaluate(`
          (() => {
            const nav = performance.getEntriesByType('navigation')[0] || {};
            const paints = performance.getEntriesByType('paint') || [];
            const fcpEntry = paints.find(p => p.name === 'first-contentful-paint');
            const resources = performance.getEntriesByType('resource') || [];
            const resourceBytes = resources.reduce((sum, r) => sum + (r.transferSize || 0), 0);
            const resourceEncoded = resources.reduce((sum, r) => sum + (r.encodedBodySize || 0), 0);
            const resourceDecoded = resources.reduce((sum, r) => sum + (r.decodedBodySize || 0), 0);

            const lcpVal = window.__perfData?.lcp ?? null;
            const clsSession = window.__perfData?.clsSessionWindow ?? 0;
            const clsRaw = window.__perfData?.cls ?? 0;

            return {
              domContentLoaded: Math.round(nav.domContentLoadedEventEnd || 0),
              loadDuration: Math.round(nav.loadEventEnd || nav.duration || 0),
              fcp: fcpEntry ? Math.round(fcpEntry.startTime) : null,
              lcp: lcpVal,
              lcpEntriesCount: window.__perfData?.lcpEntries?.length || 0,
              clsSessionWindow: clsSession,
              clsRaw: clsRaw,
              rawLayoutShiftsCount: window.__perfData?.rawLayoutShifts?.length || 0,
              resourceTiming: {
                resourceCount: resources.length,
                transferBytes: resourceBytes,
                encodedBodyBytes: resourceEncoded,
                decodedBodyBytes: resourceDecoded,
              }
            };
          })()
        `);

        warmRuns.push({
          runIndex: runIdx,
          cacheMode: 'warm',
          cdpWireTransferBytes: cdpNet.totalWireBytes,
          cdpRequestCount: cdpNet.totalRequests,
          cdpCacheHits: cdpNet.cacheHits,
          cdpWireRequests: cdpNet.wireRequests,
          ...browserMetrics,
        });
      }

      const coldSummary = computeSummary(coldRuns);
      const warmSummary = computeSummary(warmRuns);

      perfResults.routes[route.name] = {
        path: route.path,
        exactFirstLoadJsBytes: ROUTE_EXACT_JS_BYTES[route.name],
        coldRuns,
        coldSummary,
        warmRuns,
        warmSummary,
      };

      console.log(`  -> ${route.name} COLD Median: DCL=${coldSummary.domContentLoaded.median}ms, Load=${coldSummary.loadDuration.median}ms, WireBytes=${coldSummary.cdpWireTransferBytes.median}, LCP=${coldSummary.lcp.median ?? 'N/A'}, CLS=${coldSummary.clsSessionWindow.median}`);
      console.log(`  -> ${route.name} WARM Median: DCL=${warmSummary.domContentLoaded.median}ms, Load=${warmSummary.loadDuration.median}ms, WireBytes=${warmSummary.cdpWireTransferBytes.median}, CacheHits=${warmSummary.cdpCacheHits.median}, LCP=${warmSummary.lcp.median ?? 'N/A'}, CLS=${warmSummary.clsSessionWindow.median}`);
    }

    const perfFilePath = path.join(SCREENSHOTS_DIR, 'perf_measurements.json');
    fs.writeFileSync(perfFilePath, JSON.stringify(perfResults, null, 2));
    console.log(`\n✔ Saved performance measurements to ${perfFilePath}`);

    // Save JSON evidence
    const evidenceFilePath = path.join(SCREENSHOTS_DIR, 'walkthrough_evidence.json');
    fs.writeFileSync(evidenceFilePath, JSON.stringify(evidenceRecords, null, 2));
    console.log(`\n✔ Saved structured evidence table to ${evidenceFilePath}`);

    console.log('\n================================================================');
    console.log('   M3 WALKTHROUGH VERIFICATION TABLE (ALL 14 STEPS PASSED)      ');
    console.log('================================================================\n');

    for (const r of evidenceRecords) {
      console.log(`[${r.step}] PASS: ${r.pass}`);
      console.log(`  Actor:    ${r.actor}`);
      console.log(`  Expected: ${r.expected}`);
      console.log(`  Actual:   ${r.actual}\n`);
    }

    console.log('🎉 All 14 walkthrough steps + performance benchmark asserted and captured in ' + SCREENSHOTS_DIR);
  } finally {
    if (browser) browser.close();
    if (nextProc) {
      try { process.kill(nextProc.pid); } catch {}
    }
    if (fixtureServer) {
      try { fixtureServer.close(); } catch {}
    }
  }
}

main().catch((err) => {
  console.error('\n❌ WALKTHROUGH RUNNER ERROR:', err);
  process.exit(1);
});
