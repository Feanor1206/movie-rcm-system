/**
 * M4-F02 Media Streaming Walkthrough & Real Spring Boot Benchmark Harness
 *
 * Runs browser playback assertions via Chrome DevTools Protocol (CDP) against:
 *   1. Spring Boot M4WalkthroughServer (isolated H2 in-memory DB, temp media root, observable permits)
 *   2. Next.js Standalone Production Build
 *
 * Verifies Milestone M4-F02 Findings:
 *   - F1: Media descriptor error, retry button, recovery, no false catalog absence
 *   - F2: Bounded local streams, observable cleanup, HTTP 429 overload resilience
 *   - F3: Real browser controls (play/pause, timeline scrubber), >=44px mobile touch targets,
 *         before/after disk snapshots, truthful latency labeling
 *
 * Screenshots saved to: docs/reports/screenshots/M4_F02/
 * Benchmark output saved to: docs/reports/m4_f02_benchmark_results.json
 */

const http = require('node:http');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const { performance } = require('node:perf_hooks');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const JAVA_PATH = 'C:\\Program Files\\Java\\jdk-25.0.3\\bin\\java.exe';
const STANDALONE_DIR = path.resolve(PROJECT_ROOT, 'frontend/.next/standalone');
const STANDALONE_SERVER = path.resolve(STANDALONE_DIR, 'server.js');
const MEDIA_FILE = path.resolve(PROJECT_ROOT, 'backend/springboot/target/test-media/synthetic/walkthrough_feature.mp4');
const SCREENSHOTS_DIR = path.resolve(PROJECT_ROOT, 'docs/reports/screenshots/M4_F02');
const BENCHMARK_OUT = path.resolve(PROJECT_ROOT, 'docs/reports/m4_f02_benchmark_results.json');

fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

function snapshotDirectory(dirPath) {
  const entries = [];
  if (!fs.existsSync(dirPath)) return entries;
  function scan(cur) {
    const items = fs.readdirSync(cur, { withFileTypes: true });
    for (const it of items) {
      const full = path.join(cur, it.name);
      if (it.isDirectory()) {
        scan(full);
      } else if (it.isFile()) {
        const stat = fs.statSync(full);
        const content = fs.readFileSync(full);
        const hash = crypto.createHash('sha256').update(content).digest('hex');
        entries.push({
          relativePath: path.relative(dirPath, full).replace(/\\/g, '/'),
          sizeBytes: stat.size,
          sha256: hash,
        });
      }
    }
  }
  scan(dirPath);
  return entries.sort((a, b) => a.relativePath.localeCompare(b.relativePath));
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

async function findFreePort(startPort = 3100) {
  for (let p = startPort; p < startPort + 500; p++) {
    if (await checkPortAvailable(p)) return p;
  }
  throw new Error(`Could not find a free port starting from ${startPort}`);
}

function syncStandaloneAssets() {
  const standaloneStatic = path.join(STANDALONE_DIR, '.next/static');
  const frontendStatic = path.resolve(PROJECT_ROOT, 'frontend/.next/static');
  const standalonePublic = path.join(STANDALONE_DIR, 'public');
  const frontendPublic = path.resolve(PROJECT_ROOT, 'frontend/public');

  if (fs.existsSync(frontendStatic)) {
    fs.mkdirSync(standaloneStatic, { recursive: true });
    fs.cpSync(frontendStatic, standaloneStatic, { recursive: true });
  }
  if (fs.existsSync(frontendPublic)) {
    fs.mkdirSync(standalonePublic, { recursive: true });
    fs.cpSync(frontendPublic, standalonePublic, { recursive: true });
  }
}

// ----------------------------------------------------------------------------
// 1. Spring Boot Isolated Server Process
// ----------------------------------------------------------------------------
function startSpringBootServer() {
  return new Promise((resolve, reject) => {
    const cpPath = path.resolve(PROJECT_ROOT, 'backend/springboot/target/cp.txt');
    if (!fs.existsSync(cpPath)) {
      return reject(new Error('backend/springboot/target/cp.txt not found. Run mvnw test-compile first.'));
    }
    const mavenCp = fs.readFileSync(cpPath, 'utf8').trim();
    const fullCp = `target/classes;target/test-classes;${mavenCp}`;

    console.log('🚀 Launching Spring Boot M4WalkthroughServer...');
    const proc = spawn(
      JAVA_PATH,
      [
        '-cp', fullCp,
        '-Dwalkthrough.media.root=target/test-media',
        'com.dippie.moviercm.M4WalkthroughServer'
      ],
      {
        cwd: path.resolve(PROJECT_ROOT, 'backend/springboot'),
        stdio: ['pipe', 'pipe', 'pipe']
      }
    );

    let started = false;
    let backendPort = null;
    let stdoutBuffer = '';

    proc.stdout.on('data', (d) => {
      const text = d.toString();
      stdoutBuffer += text;
      const match = text.match(/WALKTHROUGH_BACKEND_PORT=(\d+)/);
      if (match && !started) {
        started = true;
        backendPort = parseInt(match[1], 10);
        console.log(`✔ Spring Boot M4WalkthroughServer ready on port ${backendPort}`);
        resolve({ proc, port: backendPort });
      }
    });

    proc.stderr.on('data', (d) => {
      const text = d.toString();
      if (!started && text.includes('Exception')) {
        console.error('[Spring stderr]:', text);
      }
    });

    proc.on('exit', (code) => {
      if (!started) {
        reject(new Error(`Spring Boot exited prematurely with code ${code}. Output: ${stdoutBuffer.slice(-500)}`));
      }
    });

    setTimeout(() => {
      if (!started) {
        proc.kill();
        reject(new Error(`Timeout waiting for Spring Boot server to start after 30s. Output: ${stdoutBuffer.slice(-500)}`));
      }
    }, 30000);
  });
}

// ----------------------------------------------------------------------------
// 2. Next.js Standalone Production Server Process
// ----------------------------------------------------------------------------
function startNextServer(nextPort, springBootPort) {
  return new Promise((resolve, reject) => {
    syncStandaloneAssets();

    console.log(`🚀 Launching Next.js Standalone server on port ${nextPort}...`);
    const proc = spawn(process.execPath, [STANDALONE_SERVER], {
      cwd: STANDALONE_DIR,
      env: {
        ...process.env,
        PORT: String(nextPort),
        HOSTNAME: '127.0.0.1',
        NODE_ENV: 'production',
        NEXT_PUBLIC_SPRINGBOOT_API_URL: `http://127.0.0.1:${springBootPort}/api`,
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let started = false;
    proc.stdout.on('data', (d) => {
      const str = d.toString();
      if (!started && (str.includes(`Listening on port ${nextPort}`) || str.includes('Ready') || str.includes(`127.0.0.1:${nextPort}`))) {
        started = true;
        console.log(`✔ Next.js Standalone Server listening on http://127.0.0.1:${nextPort}`);
        resolve(proc);
      }
    });

    proc.stderr.on('data', (d) => {
      console.error('[Next.js stderr]:', d.toString());
    });

    proc.on('error', (err) => {
      if (!started) reject(err);
    });

    setTimeout(() => {
      if (!started) {
        started = true;
        console.log(`✔ Next.js Standalone assuming started on port ${nextPort}`);
        resolve(proc);
      }
    }, 5000);
  });
}

// ----------------------------------------------------------------------------
// 3. CDP Browser Client with Transparent Port Proxying
// ----------------------------------------------------------------------------
async function launchChromeWithCDP(springBootPort, cdpPort) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'chrome-m4-f01-'));
  const chromeArgs = [
    '--headless=new',
    `--remote-debugging-port=${cdpPort}`,
    `--user-data-dir=${tmpDir}`,
    '--autoplay-policy=no-user-gesture-required',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-background-networking',
    '--disable-extensions',
    '--disable-sync',
    '--disable-gpu',
    '--window-size=1280,800',
    'about:blank',
  ];

  console.log(`🚀 Launching Headless Chrome on CDP port ${cdpPort}...`);
  const chromeProc = spawn(CHROME_PATH, chromeArgs, { stdio: 'ignore' });

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
    chromeProc.kill();
    throw new Error('Failed to connect to Chrome DevTools Protocol endpoint');
  }

  const listRes = await fetch(`http://127.0.0.1:${cdpPort}/json/list`);
  const pages = await listRes.json();
  const targetPage = pages.find((p) => p.type === 'page') || pages[0];
  const pageWsUrl = targetPage.webSocketDebuggerUrl;

  const ws = new globalThis.WebSocket(pageWsUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true });
    ws.addEventListener('error', reject, { once: true });
  });

  let idCounter = 1;
  const pendingRequests = new Map();
  const interceptedRequests = [];

  ws.addEventListener('message', async (event) => {
    const raw = typeof event.data === 'string' ? event.data : event.data.toString();
    const msg = JSON.parse(raw);

    if (msg.id && pendingRequests.has(msg.id)) {
      const { resolve, reject, timer } = pendingRequests.get(msg.id);
      clearTimeout(timer);
      pendingRequests.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message || JSON.stringify(msg.error)));
      else resolve(msg.result);
    }

    // Intercept outgoing HTTP calls from browser targeting port 8080 and reroute to our isolated Spring Boot port
    if (msg.method === 'Fetch.requestPaused') {
      const { requestId, request } = msg.params;
      const originalUrl = request.url;
      let targetUrl = originalUrl;

      if (originalUrl.includes('localhost:8080') || originalUrl.includes('127.0.0.1:8080')) {
        targetUrl = originalUrl.replace(/(localhost|127\.0\.0\.1):8080/, `127.0.0.1:${springBootPort}`);
        interceptedRequests.push({
          method: request.method,
          originalUrl,
          targetUrl,
          rangeHeader: request.headers?.Range || request.headers?.range || null,
          time: Date.now(),
        });
        console.log(`[CDP Fetch] ${request.method} ${originalUrl} -> ${targetUrl} (Range: ${request.headers?.Range || request.headers?.range || 'none'})`);
      }

      try {
        const continueParams = { requestId };
        if (targetUrl !== originalUrl) {
          continueParams.url = targetUrl;
        }
        ws.send(JSON.stringify({
          id: idCounter++,
          method: 'Fetch.continueRequest',
          params: continueParams
        }));
      } catch (err) {
        console.error('Error forwarding intercepted fetch request:', err.message);
      }
    }

    if (msg.method === 'Runtime.consoleAPICalled') {
      const args = msg.params.args?.map(a => a.value !== undefined ? a.value : a.description).join(' ');
      console.log('[Browser Console]:', args);
    }
    if (msg.method === 'Runtime.exceptionThrown') {
      console.error('[Browser Exception]:', JSON.stringify(msg.params.exceptionDetails));
    }
  });

  ws.addEventListener('close', () => {
    for (const [id, { reject, timer }] of pendingRequests.entries()) {
      clearTimeout(timer);
      reject(new Error(`CDP WebSocket closed while request ${id} was pending`));
    }
    pendingRequests.clear();
  });

  ws.addEventListener('error', (err) => {
    for (const [id, { reject, timer }] of pendingRequests.entries()) {
      clearTimeout(timer);
      reject(new Error(`CDP WebSocket error: ${err?.message || 'unknown'}`));
    }
    pendingRequests.clear();
  });

  function cdp(method, params = {}, timeoutMs = 15000) {
    return new Promise((resolve, reject) => {
      const id = idCounter++;
      const timer = setTimeout(() => {
        if (pendingRequests.has(id)) {
          pendingRequests.delete(id);
          reject(new Error(`CDP command '${method}' timed out after ${timeoutMs}ms`));
        }
      }, timeoutMs);

      pendingRequests.set(id, { resolve, reject, timer });
      try {
        ws.send(JSON.stringify({ id, method, params }));
      } catch (err) {
        clearTimeout(timer);
        pendingRequests.delete(id);
        reject(err);
      }
    });
  }

  await cdp('Page.enable');
  await cdp('DOM.enable');
  await cdp('Runtime.enable');
  await cdp('Network.enable');

  // Enable Fetch request routing
  await cdp('Fetch.enable', {
    patterns: [
      { urlPattern: 'http://localhost:8080/*' },
      { urlPattern: 'http://127.0.0.1:8080/*' },
    ]
  });

  async function evaluate(expression, timeoutMs = 15000) {
    const res = await cdp('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    }, timeoutMs);
    if (res?.exceptionDetails) {
      const desc = res.exceptionDetails.exception?.description || res.exceptionDetails.text;
      throw new Error(`Browser JS evaluate failed: ${desc}`);
    }
    return res?.result?.value;
  }

  async function waitForCondition(conditionFnStr, description, timeoutMs = 10000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      try {
        const val = await evaluate(conditionFnStr);
        if (val) return val;
      } catch {}
      await new Promise((r) => setTimeout(r, 100));
    }
    throw new Error(`Timeout waiting for condition: ${description} (${timeoutMs}ms)`);
  }

  async function setViewport(width, height, isMobile = false) {
    await cdp('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: isMobile,
    });
  }

  async function navigate(url) {
    await cdp('Page.navigate', { url });
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 100));
      try {
        const curUrl = await evaluate('window.location.href');
        const ready = await evaluate('document.readyState');
        if (curUrl && curUrl !== 'about:blank' && (ready === 'complete' || ready === 'interactive')) {
          break;
        }
      } catch {}
    }
    await new Promise((r) => setTimeout(r, 400));
  }

  async function captureScreenshot(filename) {
    const shot = await cdp('Page.captureScreenshot', { format: 'png' });
    const targetFile = path.join(SCREENSHOTS_DIR, filename);
    fs.writeFileSync(targetFile, Buffer.from(shot.data, 'base64'));
    console.log(`  📸 Screenshot saved: ${filename} (${(shot.data.length / 1024).toFixed(1)} KiB)`);
  }

  async function dispatchKey(key, code, windowsVirtualKeyCode) {
    await cdp('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode });
    await new Promise((r) => setTimeout(r, 50));
    await cdp('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode });
  }

  return {
    proc: chromeProc,
    ws,
    cdp,
    tmpDir,
    evaluate,
    waitForCondition,
    setViewport,
    navigate,
    captureScreenshot,
    dispatchKey,
    interceptedRequests,
  };
}

// ----------------------------------------------------------------------------
// 4. HTTP Helper for Spring Boot Endpoints
// ----------------------------------------------------------------------------
function requestHttp(urlStr, options = {}) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(urlStr);
    const reqOpts = {
      method: options.method || 'GET',
      hostname: parsed.hostname,
      port: parsed.port,
      path: parsed.pathname + parsed.search,
      headers: options.headers || {},
    };

    const startTime = performance.now();
    let firstByteTime = null;

    const req = http.request(reqOpts, (res) => {
      const chunks = [];
      res.on('data', (c) => {
        if (firstByteTime === null) {
          firstByteTime = performance.now();
        }
        chunks.push(c);
      });
      res.on('end', () => {
        const endTime = performance.now();
        const bodyBuffer = Buffer.concat(chunks);
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          body: bodyBuffer,
          ttfbMs: firstByteTime !== null ? Number((firstByteTime - startTime).toFixed(2)) : 0,
          totalDurationMs: Number((endTime - startTime).toFixed(2)),
          bytesReceived: bodyBuffer.length,
        });
      });
    });

    req.on('error', reject);
    if (options.timeoutMs) {
      req.setTimeout(options.timeoutMs, () => {
        req.destroy(new Error(`Request timed out after ${options.timeoutMs}ms`));
      });
    }

    if (options.body) {
      req.write(options.body);
    }
    req.end();
  });
}

function computeStats(arr) {
  if (!arr || arr.length === 0) return { min: 0, avg: 0, p95: 0, max: 0, count: 0 };
  const sorted = [...arr].sort((a, b) => a - b);
  const sum = sorted.reduce((acc, v) => acc + v, 0);
  const avg = sum / sorted.length;
  const min = sorted[0];
  const max = sorted[sorted.length - 1];
  const p95Index = Math.min(Math.floor(sorted.length * 0.95), sorted.length - 1);
  const p95 = sorted[p95Index];
  return {
    min: Number(min.toFixed(2)),
    avg: Number(avg.toFixed(2)),
    p95: Number(p95.toFixed(2)),
    max: Number(max.toFixed(2)),
    count: sorted.length,
  };
}

// ----------------------------------------------------------------------------
// 5. Main Execution: Browser Walkthrough & Spring HTTP Benchmark
// ----------------------------------------------------------------------------
async function main() {
  console.log('================================================================');
  console.log('   M4-F02 Browser Media Walkthrough & Spring Boot Benchmark     ');
  console.log('================================================================');

  let springProcess = null;
  let nextProcess = null;
  let chromeSession = null;
  let springPort = null;
  let nextPort = null;
  let cdpPort = null;

  const testMediaDir = path.resolve(PROJECT_ROOT, 'backend/springboot/target/test-media');
  const diskBeforeSnapshot = snapshotDirectory(testMediaDir);
  console.log(`Initial disk snapshot taken: ${diskBeforeSnapshot.length} files tracked in ${testMediaDir}`);

  try {
    // 0. Allocate ports
    nextPort = await findFreePort(3100);
    cdpPort = await findFreePort(9230);

    // 1. Start Spring Boot Walkthrough Server
    const springRes = await startSpringBootServer();
    springProcess = springRes.proc;
    springPort = springRes.port;

    // Verify Spring Boot health
    const health = await requestHttp(`http://127.0.0.1:${springPort}/api/health`);
    assert.equal(health.statusCode, 200, 'Spring Boot health check must return 200');
    console.log('✔ Spring Boot health check confirmed: 200 UP');

    // 2. Start Next.js Standalone
    nextProcess = await startNextServer(nextPort, springPort);

    // Warm up Next.js route before browser navigation
    console.log('Pre-warming Next.js movie route...');
    try {
      await requestHttp(`http://127.0.0.1:${nextPort}/movies/m4-walkthrough-movie`, { timeoutMs: 15000 });
    } catch {}

    // 3. Launch Chrome with CDP
    chromeSession = await launchChromeWithCDP(springPort, cdpPort);
    const { evaluate, waitForCondition, setViewport, navigate, captureScreenshot, dispatchKey, interceptedRequests } = chromeSession;

    // ------------------------------------------------------------------------
    // Part A: Browser Playback Assertions & Screenshot Capture
    // ------------------------------------------------------------------------
    console.log('\n--- Part A: Desktop Playback Walkthrough ---');
    await setViewport(1280, 800, false);

    const movieUrl = `http://127.0.0.1:${nextPort}/movies/m4-walkthrough-movie`;
    console.log(`Navigating to ${movieUrl}...`);
    await navigate(movieUrl);

    // A1. Verify movie title rendered
    await waitForCondition(
      `document.body.innerText.includes("Walkthrough Cinema Special")`,
      'Movie title "Walkthrough Cinema Special" visible on page',
      20000
    );
    console.log('✔ Movie title rendered on page');

    // A2. Verify "Xem phim" feature button is rendered and enabled
    await waitForCondition(
      `(() => {
        const btn = document.querySelector('button[aria-label="Xem phim"]') ||
                    Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Xem phim'));
        return btn && !btn.disabled;
      })()`,
      'Feature "Xem phim" button visible and enabled',
      6000
    );
    console.log('✔ Feature "Xem phim" button active');

    // A3. Open player modal by clicking "Xem phim"
    console.log('Clicking "Xem phim" to initiate playback modal...');
    await evaluate(`(() => {
      const btn = document.querySelector('button[aria-label="Xem phim"]') ||
                  Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Xem phim'));
      btn.click();
    })()`);

    // A4. Wait for video element and active playback progression
    await waitForCondition(
      `Boolean(document.querySelector('video'))`,
      'HTML5 video element mounted in DOM',
      6000
    );
    console.log('✔ Video element mounted in player modal');

    // Diagnostic & play trigger via UI control if paused
    const initialStatus = await evaluate(`(() => {
      const v = document.querySelector('video');
      window.__m4StalledCount = 0;
      window.__m4WaitingCount = 0;
      if (v) {
        v.addEventListener('stalled', () => { window.__m4StalledCount++; });
        v.addEventListener('waiting', () => { window.__m4WaitingCount++; });
      }
      return {
        src: v?.src,
        currentSrc: v?.currentSrc,
        paused: v?.paused,
        currentTime: v?.currentTime,
        duration: v?.duration,
        readyState: v?.readyState,
        networkState: v?.networkState,
      };
    })()`);
    console.log('Initial video element status:', JSON.stringify(initialStatus));

    if (initialStatus.paused) {
      console.log('Video paused by browser autoplay policy - clicking UI play button...');
      await evaluate(`(() => {
        const playBtn = document.querySelector('button[data-testid="video-play-pause-btn"]');
        if (playBtn) playBtn.click();
        else document.querySelector('video')?.play().catch(() => {});
      })()`);
    }

    // Measure raw browser presentation timing
    const frameTiming = await evaluate(`new Promise((resolve, reject) => {
      const v = document.querySelector('video');
      if (!v) return reject(new Error('HTML5 video element not found for presentation timing'));
      const t0 = performance.now();
      let timer = null;

      const onFrame = (now, metadata) => {
        clearTimeout(timer);
        resolve({
          method: 'requestVideoFrameCallback',
          latencyMs: Math.round(performance.now() - t0),
          presentationTime: metadata.presentationTime,
        });
      };

      const onPlaying = () => {
        clearTimeout(timer);
        resolve({
          method: 'playing_event',
          latencyMs: Math.round(performance.now() - t0),
        });
      };

      timer = setTimeout(() => {
        v.removeEventListener('playing', onPlaying);
        reject(new Error('Timeout waiting for video presentation frame (8000ms). readyState=' + v.readyState + ', networkState=' + v.networkState));
      }, 8000);

      if ('requestVideoFrameCallback' in v) {
        v.requestVideoFrameCallback(onFrame);
      } else {
        v.addEventListener('playing', onPlaying, { once: true });
      }
    })`, 10000);
    console.log(`Browser video presentation timing: ${JSON.stringify(frameTiming)}`);

    // Wait for video currentTime to advance past 1.0s (proves real frames decoding)
    console.log('Waiting for video decoding and currentTime > 1.0s...');
    await waitForCondition(
      `(() => {
        const v = document.querySelector('video');
        return v && !v.paused && v.currentTime > 1.0;
      })()`,
      'Video playback running with currentTime > 1.0s',
      12000
    );
    const initialPlayTime = await evaluate(`document.querySelector('video').currentTime`);
    console.log(`✔ Real video playback verified! currentTime: ${initialPlayTime.toFixed(2)}s`);

    // Verify Spring Boot received HTTP 206 Range request
    const streamRequests = interceptedRequests.filter(r => r.originalUrl.includes('/api/media/stream/ast-walkthrough-feat'));
    assert(streamRequests.length > 0, 'Browser must have issued stream request to Spring Boot media endpoint');
    console.log(`✔ Verified ${streamRequests.length} HTTP stream requests routed to Spring Boot`);

    // Screenshot 1: Desktop Playing
    await captureScreenshot('01_desktop_playback_playing.png');

    // A5. Measure 3 Browser Seeks across positions via UI timeline
    console.log('\nMeasuring 3 Browser Seeks via UI timeline scrubber control...');
    const browserSeekRuns = [];
    const targetSeekPositions = [5.0, 10.0, 15.0];

    for (let i = 0; i < targetSeekPositions.length; i++) {
      const targetSec = targetSeekPositions[i];
      const seekPerf = await evaluate(`new Promise((resolve, reject) => {
        const timeline = document.querySelector('input[data-testid="video-timeline"]');
        const v = document.querySelector('video');
        if (!timeline) return reject(new Error('Timeline element input[data-testid="video-timeline"] not found'));
        if (!v) return reject(new Error('HTML5 video element not found'));

        const t0 = performance.now();
        let seekingFired = false;
        let timer = null;

        const onSeeking = () => {
          seekingFired = true;
        };

        const onSeeked = () => {
          cleanup();
          resolve({
            latencyMs: Math.round(performance.now() - t0),
            seekingObserved: seekingFired,
            currentTimeAfter: v.currentTime,
            sliderValueAfter: parseFloat(timeline.value),
          });
        };

        function cleanup() {
          clearTimeout(timer);
          v.removeEventListener('seeking', onSeeking);
          v.removeEventListener('seeked', onSeeked);
        }

        v.addEventListener('seeking', onSeeking, { once: true });
        v.addEventListener('seeked', onSeeked, { once: true });

        timer = setTimeout(() => {
          cleanup();
          const diagnostics = {
            targetSec: ${targetSec},
            readyState: v.readyState,
            networkState: v.networkState,
            currentTime: v.currentTime,
            duration: v.duration,
            paused: v.paused,
            seeking: v.seeking,
            seekingFired,
            sliderValue: timeline.value,
            mediaError: v.error ? { code: v.error.code, message: v.error.message } : null,
          };
          reject(new Error('Seek to ' + ${targetSec} + 's timed out after 8000ms. Diagnostics: ' + JSON.stringify(diagnostics)));
        }, 8000);

        // Controlled React input dispatch via native HTMLInputElement value setter
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        if (nativeSetter) {
          nativeSetter.call(timeline, "${targetSec}");
        } else {
          timeline.value = "${targetSec}";
        }
        timeline.dispatchEvent(new Event('input', { bubbles: true }));
        timeline.dispatchEvent(new Event('change', { bubbles: true }));
      })`, 10000);

      browserSeekRuns.push(seekPerf.latencyMs);
      console.log(`  Seek to ${targetSec}s: latency = ${seekPerf.latencyMs} ms, seekingObserved = ${seekPerf.seekingObserved}, currentTime = ${seekPerf.currentTimeAfter.toFixed(2)}s, slider = ${seekPerf.sliderValueAfter}`);

      assert(seekPerf.currentTimeAfter >= targetSec - 0.5, `currentTime after seek (${seekPerf.currentTimeAfter}) must reflect target (${targetSec})`);

      await waitForCondition(
        `(() => {
          const v = document.querySelector('video');
          return v && !v.seeking && v.currentTime >= ${targetSec - 0.2};
        })()`,
        `Video continuous after seek to ${targetSec}s`,
        8000
      );
    }
    const browserSeekStats = computeStats(browserSeekRuns);
    console.log(`  Browser Seek Latency Stats: min=${browserSeekStats.min}ms, avg=${browserSeekStats.avg}ms, p95=${browserSeekStats.p95}ms, max=${browserSeekStats.max}ms`);

    // Wait for continuous playback past 15.3s
    await waitForCondition(
      `(() => {
        const v = document.querySelector('video');
        return v && !v.seeking && v.currentTime > 15.3;
      })()`,
      'Continuous playback past 15.3s',
      8000
    );
    const seekTime = await evaluate(`document.querySelector('video').currentTime`);
    console.log(`✔ Continuous post-seek playback verified! currentTime: ${seekTime.toFixed(2)}s`);

    // Screenshot 2: Desktop Seek Near End
    await captureScreenshot('02_desktop_seek_near_end.png');

    // A6. Pause & Resume verification via UI button
    console.log('Testing Pause / Resume via UI button...');
    await evaluate(`(() => {
      const btn = document.querySelector('button[data-testid="video-play-pause-btn"]');
      btn.click();
    })()`);
    await waitForCondition(
      `(() => {
        const v = document.querySelector('video');
        const btn = document.querySelector('button[data-testid="video-play-pause-btn"]');
        return v && v.paused === true && (btn?.getAttribute('aria-label') === 'Phát video' || btn?.querySelector('svg'));
      })()`,
      'Video paused and UI button reflected paused state',
      4000
    );
    console.log('✔ Video paused via UI button click');

    await evaluate(`(() => {
      const btn = document.querySelector('button[data-testid="video-play-pause-btn"]');
      btn.click();
    })()`);
    await waitForCondition(
      `(() => {
        const v = document.querySelector('video');
        const btn = document.querySelector('button[data-testid="video-play-pause-btn"]');
        return v && v.paused === false && (btn?.getAttribute('aria-label') === 'Tạm dừng video' || btn?.querySelector('svg'));
      })()`,
      'Video resumed and UI button reflected playing state',
      4000
    );
    console.log('✔ Video resumed via UI button click');

    // A7. Error & Retry Recovery
    console.log('Triggering controlled playback error to verify retry recovery...');
    const timeBeforeError = await evaluate(`document.querySelector('video').currentTime`);
    console.log(`Current playback position before fault: ${timeBeforeError.toFixed(2)}s`);

    // Setup: Dispatch controlled error event on media element (labeled fault setup)
    await evaluate(`(() => {
      const v = document.querySelector('video');
      v.dispatchEvent(new Event('error'));
    })()`);

    // Verify error overlay appears with retry button
    await waitForCondition(
      `(() => {
        const retryBtn = document.querySelector('button[data-testid="video-retry-btn"]') ||
                         Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Thử lại'));
        return Boolean(retryBtn);
      })()`,
      'Error overlay with "Thử lại" button',
      5000
    );
    console.log('✔ Error state displayed with Retry button');

    // Click "Thử lại"
    console.log('Clicking "Thử lại" and observing app natural recovery (NO test harness intervention)...');
    await evaluate(`(() => {
      const retryBtn = document.querySelector('button[data-testid="video-retry-btn"]') ||
                       Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Thử lại'));
      retryBtn.click();
    })()`);

    // Strictly observational wait predicate: NO v.play() or currentTime manipulation in predicate!
    await waitForCondition(
      `(() => {
        const v = document.querySelector('video');
        if (!v) return false;
        return !v.paused && v.currentTime >= ${timeBeforeError - 0.8};
      })()`,
      `Video restored near ${timeBeforeError.toFixed(2)}s and resumed playing naturally by app`,
      12000
    );
    const recoveredTime = await evaluate(`document.querySelector('video').currentTime`);
    console.log(`✔ Playback retry recovery verified! Restored time: ${recoveredTime.toFixed(2)}s`);

    // Collect observed stall events
    const observedStalls = await evaluate(`(() => ({
      stalledEvents: window.__m4StalledCount || 0,
      waitingEvents: window.__m4WaitingCount || 0,
    }))()`);
    console.log(`Observed media element events: ${JSON.stringify(observedStalls)}`);

    // Screenshot 3: Retry Recovery
    await captureScreenshot('03_desktop_retry_recovery.png');

    // A8. Close Modal & Focus Restoration
    console.log('Testing Modal close and focus restoration via Escape key...');
    await dispatchKey('Escape', 'Escape', 27);
    await waitForCondition(`document.querySelector('video') === null`, 'Modal closed', 4000);
    const activeBtnText = await evaluate(`document.activeElement?.innerText || document.activeElement?.getAttribute('aria-label') || ''`);
    assert(activeBtnText.includes('Xem phim'), 'Opener "Xem phim" button must receive focus after modal closes');
    console.log('✔ Modal closed and focus properly restored to opener button');

    // ------------------------------------------------------------------------
    // Part B: Mobile Viewport 375px Verification
    // ------------------------------------------------------------------------
    console.log('\n--- Part B: Mobile 375px Playback Walkthrough ---');
    await setViewport(375, 667, true);

    console.log('Re-opening video player on mobile viewport...');
    await evaluate(`(() => {
      const btn = document.querySelector('button[aria-label="Xem phim"]') ||
                  Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Xem phim'));
      btn.click();
    })()`);

    await waitForCondition(`Boolean(document.querySelector('video'))`, 'Mobile video player open', 5000);

    // Comprehensive Mobile Touch Target & Collision Audit
    const mobileAudit = await evaluate(`(() => {
      function getInfo(selector, name) {
        const el = document.querySelector(selector);
        if (!el) return null;
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return {
          name,
          selector,
          ariaLabel: el.getAttribute('aria-label') || '',
          testId: el.getAttribute('data-testid') || '',
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          top: Math.round(rect.top),
          bottom: Math.round(rect.bottom),
          visible: rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none',
        };
      }

      const close = getInfo('button[aria-label="Đóng trình phát"]', 'close_button');
      const playPause = getInfo('button[data-testid="video-play-pause-btn"]', 'play_pause_button');
      const volume = getInfo('button[data-testid="video-volume-btn"]', 'volume_button');
      const fullscreen = getInfo('button[data-testid="video-fullscreen-btn"]', 'fullscreen_button');
      const timeline = getInfo('input[data-testid="video-timeline"]', 'timeline_scrubber');

      const buttons = [close, playPause, volume, fullscreen].filter(Boolean);
      const allControls = [close, playPause, volume, fullscreen, timeline].filter(Boolean);

      // Collision checks between all button pairs in the control bar
      const collisions = [];
      const barButtons = [playPause, volume, fullscreen].filter(Boolean);
      for (let i = 0; i < barButtons.length; i++) {
        for (let j = i + 1; j < barButtons.length; j++) {
          const a = barButtons[i];
          const b = barButtons[j];
          const overlap = !(a.right <= b.left || a.left >= b.right || a.bottom <= b.top || a.top >= b.bottom);
          if (overlap) {
            collisions.push({ a: a.name, b: b.name });
          }
        }
      }

      return {
        controls: allControls,
        buttons,
        collisions,
      };
    })()`);

    console.log('Mobile controls audit:');
    for (const c of mobileAudit.controls) {
      console.log(`  - ${c.name} (${c.selector}): ${c.width}x${c.height}px, visible=${c.visible}`);
      if (c.name !== 'timeline_scrubber') {
        assert(c.width >= 44 && c.height >= 44, `Control ${c.name} must meet >= 44x44px touch target (got ${c.width}x${c.height}px)`);
      } else {
        assert(c.height >= 44 && c.width >= 100, `Timeline must meet min height >= 44px and width >= 100px (got ${c.width}x${c.height}px)`);
      }
      assert(c.visible, `Control ${c.name} must be visible in layout`);
    }

    assert.equal(mobileAudit.collisions.length, 0, `Player controls must not have layout collisions (found: ${JSON.stringify(mobileAudit.collisions)})`);
    console.log('✔ All mobile controls satisfy >= 44x44px touch targets with 0 layout collisions');

    // Screenshot 4: Mobile Playback
    await captureScreenshot('04_mobile_playback_375px.png');

    // Close mobile modal
    await dispatchKey('Escape', 'Escape', 27);
    await waitForCondition(`document.querySelector('video') === null`, 'Mobile modal closed', 4000);
    console.log('✔ Mobile modal closed');

    // ------------------------------------------------------------------------
    // Part C: Real Spring Boot HTTP Range & Concurrency Benchmark
    // ------------------------------------------------------------------------
    console.log('\n--- Part C: Real Spring Boot HTTP Media Benchmark ---');
    const assetId = 'ast-walkthrough-feat';
    const streamUrl = `http://127.0.0.1:${springPort}/api/media/stream/${assetId}`;

    // Verify raw file size and byte integrity
    const fileBytes = fs.readFileSync(MEDIA_FILE);
    const totalFileLength = fileBytes.length;
    console.log(`Synthetic Media Asset: ${MEDIA_FILE} (${totalFileLength} bytes, ${(totalFileLength / 1024).toFixed(1)} KiB)`);

    // 1. Startup Latency (Range: bytes=0-65535, 3 runs)
    console.log('\n[Benchmark 1/6] Measuring Startup Latency (Initial 64 KiB Range Chunk, 3 runs)...');
    const startupRuns = [];
    for (let r = 1; r <= 3; r++) {
      const res = await requestHttp(streamUrl, {
        headers: { Range: 'bytes=0-65535' },
      });
      assert.equal(res.statusCode, 206, `Run ${r} must return HTTP 206 Partial Content`);
      assert.equal(res.bytesReceived, 65536, `Run ${r} chunk length must equal 65536 bytes`);
      // Byte integrity check: first 32 bytes match MP4 header
      assert(res.body.subarray(0, 32).equals(fileBytes.subarray(0, 32)), 'Initial bytes must match disk asset');
      startupRuns.push(res.ttfbMs);
      console.log(`  Run ${r}: TTFB = ${res.ttfbMs} ms, Duration = ${res.totalDurationMs} ms`);
    }
    const startupStats = computeStats(startupRuns);
    console.log(`  Startup TTFB Stats: min=${startupStats.min}ms, avg=${startupStats.avg}ms, p95=${startupStats.p95}ms, max=${startupStats.max}ms`);

    // 2. Mid & End Seek Latency (3 runs each)
    console.log('\n[Benchmark 2/6] Measuring Seek Chunk Latencies across positions (3 runs each)...');
    const midSeekRuns = [];
    const endSeekRuns = [];

    for (let r = 1; r <= 3; r++) {
      // Mid seek: bytes=150000-215535
      const midRes = await requestHttp(streamUrl, {
        headers: { Range: 'bytes=150000-215535' },
      });
      assert.equal(midRes.statusCode, 206);
      assert(midRes.body.subarray(0, 32).equals(fileBytes.subarray(150000, 150032)));
      midSeekRuns.push(midRes.ttfbMs);

      // End seek: bytes=250000- (to EOF)
      const endRes = await requestHttp(streamUrl, {
        headers: { Range: 'bytes=250000-' },
      });
      assert.equal(endRes.statusCode, 206);
      assert(endRes.body.subarray(0, 32).equals(fileBytes.subarray(250000, 250032)));
      endSeekRuns.push(endRes.ttfbMs);

      console.log(`  Run ${r}: Mid Seek TTFB = ${midRes.ttfbMs} ms | End Seek TTFB = ${endRes.ttfbMs} ms`);
    }
    const midSeekStats = computeStats(midSeekRuns);
    const endSeekStats = computeStats(endSeekRuns);

    // 3. Single Stream Full Asset Throughput (3 runs)
    console.log('\n[Benchmark 3/6] Measuring Single Stream Full Playback Throughput (3 runs)...');
    const singleThroughputRuns = [];
    for (let r = 1; r <= 3; r++) {
      const res = await requestHttp(streamUrl, {
        headers: { Range: `bytes=0-${totalFileLength - 1}` },
      });
      assert.equal(res.statusCode, 206);
      assert.equal(res.bytesReceived, totalFileLength);
      const durationSec = res.totalDurationMs / 1000;
      const throughputMBs = Number(((totalFileLength / (1024 * 1024)) / durationSec).toFixed(2));
      singleThroughputRuns.push(throughputMBs);
      console.log(`  Run ${r}: Duration = ${res.totalDurationMs} ms, Throughput = ${throughputMBs} MB/s`);
    }
    const singleThroughputStats = computeStats(singleThroughputRuns);

    // 4. Concurrency: 3 Parallel Streams (3 runs)
    console.log('\n[Benchmark 4/6] Measuring Concurrency: 3 Parallel Streams (3 runs)...');
    const parallelRuns = [];
    for (let r = 1; r <= 3; r++) {
      const t0 = performance.now();
      const promises = [1, 2, 3].map(() =>
        requestHttp(streamUrl, {
          headers: { Range: `bytes=0-${totalFileLength - 1}` },
        })
      );
      const results = await Promise.all(promises);
      const t1 = performance.now();
      const batchDurationSec = (t1 - t0) / 1000;

      for (const res of results) {
        assert.equal(res.statusCode, 206);
        assert.equal(res.bytesReceived, totalFileLength);
      }

      const totalBytes = totalFileLength * 3;
      const aggregateMBs = Number(((totalBytes / (1024 * 1024)) / batchDurationSec).toFixed(2));
      const avgStreamTTFB = Number((results.reduce((s, x) => s + x.ttfbMs, 0) / 3).toFixed(2));

      parallelRuns.push({
        batchDurationMs: Number((t1 - t0).toFixed(2)),
        aggregateMBs,
        avgStreamTTFB,
      });

      console.log(`  Run ${r}: 3 Parallel Streams finished in ${(t1 - t0).toFixed(1)} ms. Aggregate Throughput: ${aggregateMBs} MB/s, Avg TTFB: ${avgStreamTTFB} ms`);
    }
    const parallelAggregateStats = computeStats(parallelRuns.map(x => x.aggregateMBs));
    const parallelTtfbStats = computeStats(parallelRuns.map(x => x.avgStreamTTFB));

    // 5. Client Abrupt Disconnect & Observable Stream Cleanup (F2 Counter & Overload 429)
    console.log('\n[Benchmark 5/6] Testing Client Abrupt Disconnect & Stream Permit Cleanup (F2 Observable Counter)...');
    // 5a. Verify baseline active stream count is 0
    const metricsBaseline = await requestHttp(`http://127.0.0.1:${springPort}/api/test/media/metrics`);
    const baselineData = JSON.parse(metricsBaseline.body.toString());
    console.log('Baseline MediaStream metrics:', baselineData);
    assert.equal(baselineData.activeStreams, 0, 'Baseline active stream count must be 0');

    // 5b. Initiate gated read to hold 1 stream active
    console.log('Arming test stream gate and initiating active stream...');
    await requestHttp(`http://127.0.0.1:${springPort}/api/test/media/gate/arm`, { method: 'POST' });

    let activeWhileStreaming = -1;
    let overload429Verified = false;

    // Start stream 1 in background (will pause at gate after acquiring permit)
    const streamReq = http.request(streamUrl, {
      headers: { Range: 'bytes=0-' },
    });
    streamReq.on('error', () => {}); // Catch abort error on client destroy
    streamReq.end();

    // Poll counter to verify activeStreams === 1
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 100));
      const m = await requestHttp(`http://127.0.0.1:${springPort}/api/test/media/metrics`);
      const data = JSON.parse(m.body.toString());
      if (data.activeStreams >= 1) {
        activeWhileStreaming = data.activeStreams;
        break;
      }
    }
    console.log(`Active streams while connection is open: ${activeWhileStreaming}`);
    assert(activeWhileStreaming >= 1, 'Active stream counter must reflect active connection (>= 1)');

    // 5c. Test Stream Concurrency Limit & Overload 429 while stream 1 holds permit
    console.log('Testing Stream Concurrency Limit & Overload 429 while stream 1 is active...');
    await requestHttp(`http://127.0.0.1:${springPort}/api/test/media/max-concurrent-streams?limit=1`, { method: 'POST' });
    const res2 = await requestHttp(streamUrl, { headers: { Range: 'bytes=0-65535' } });
    console.log(`Overload response for stream 2: HTTP ${res2.statusCode}`);
    if (res2.statusCode === 429) {
      assert.equal(res2.headers['retry-after'], '5', 'HTTP 429 must include Retry-After: 5');
      assert(res2.headers['cache-control']?.includes('no-store'), 'HTTP 429 must include Cache-Control: no-store');
      overload429Verified = true;
    }
    assert(overload429Verified, 'Server must return HTTP 429 when max concurrent streams limit is exceeded');
    console.log('✔ Stream concurrency limit & HTTP 429 overload verified');

    // Reset max concurrent streams back to 10
    await requestHttp(`http://127.0.0.1:${springPort}/api/test/media/max-concurrent-streams?limit=10`, { method: 'POST' });

    // 5d. Abruptly sever client 1 socket and release gate
    console.log('Severing stream 1 socket and releasing gate...');
    streamReq.destroy();
    await requestHttp(`http://127.0.0.1:${springPort}/api/test/media/gate/release`, { method: 'POST' });

    // 5e. Poll counter to verify active streams return to 0 (finally block executed)
    console.log('Verifying active stream counter returns to baseline (0) after disconnect...');
    let activeAfterDisconnect = -1;
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 100));
      const m = await requestHttp(`http://127.0.0.1:${springPort}/api/test/media/metrics`);
      const data = JSON.parse(m.body.toString());
      activeAfterDisconnect = data.activeStreams;
      if (activeAfterDisconnect === 0) break;
    }
    console.log(`Active streams after disconnect: ${activeAfterDisconnect}`);
    assert.equal(activeAfterDisconnect, 0, 'Active stream count must return to 0 after client disconnect');
    console.log('✔ Observable permit release confirmed: stream counter successfully returned to 0');

    // Verify Spring Boot health immediately after disconnect
    const healthAfterDisconnect = await requestHttp(`http://127.0.0.1:${springPort}/api/health`);
    assert.equal(healthAfterDisconnect.statusCode, 200, 'Server must remain 200 UP after client disconnect and overload');
    console.log('✔ Spring Boot successfully recovered with 200 UP');

    // 6. Verify Read-Only Storage Integrity via Before/After Disk Snapshot
    console.log('\n[Benchmark 6/6] Verifying Read-Only Storage Integrity via Before/After Disk Snapshot...');
    const diskAfterSnapshot = snapshotDirectory(testMediaDir);
    assert.equal(diskBeforeSnapshot.length, diskAfterSnapshot.length, 'File count in test-media root must not change');
    for (let i = 0; i < diskBeforeSnapshot.length; i++) {
      const b = diskBeforeSnapshot[i];
      const a = diskAfterSnapshot[i];
      assert.equal(b.relativePath, a.relativePath, `File path mismatch at index ${i}`);
      assert.equal(b.sizeBytes, a.sizeBytes, `File size changed for ${b.relativePath}: was ${b.sizeBytes}, now ${a.sizeBytes}`);
      assert.equal(b.sha256, a.sha256, `SHA-256 changed for ${b.relativePath}: was ${b.sha256}, now ${a.sha256}`);
    }
    console.log(`✔ Read-only disk integrity confirmed: 0 mutations across ${diskBeforeSnapshot.length} monitored files in test-media root`);

    // ------------------------------------------------------------------------
    // Part D: Output Benchmark Results JSON
    // ------------------------------------------------------------------------
    const finalReport = {
      benchmarkMetadata: {
        timestamp: new Date().toISOString(),
        milestone: 'M4-F02',
        environment: `Local Spring Boot Isolated HTTP Server (port ${springPort}) + Next.js Standalone (port ${nextPort}) + Chrome CDP`,
        runtime: {
          node: process.version,
          java: 'Java 25 (compiled with --release 17)',
          os: `${os.type()} ${os.release()} ${os.arch()}`,
        },
        syntheticAsset: {
          path: MEDIA_FILE,
          totalBytes: totalFileLength,
          format: 'video/mp4 (H.264 / AAC faststart, 20s)',
        },
        storageAdapter: 'LocalMediaStorageAdapter (Read-Only, no directory creation, no parent fallbacks)',
        admissionPolicy: {
          defaultMaxConcurrentStreams: 10,
          overloadStatusCode: 429,
          overloadHeaders: {
            'Retry-After': '5',
            'Cache-Control': 'no-store, no-cache, must-revalidate',
          },
        },
      },
      browserWalkthrough: {
        desktop: {
          initialPlayTime: Number(initialPlayTime.toFixed(2)),
          seekTime: Number(seekTime.toFixed(2)),
          recoveredTime: Number(recoveredTime.toFixed(2)),
          controlsInteracted: [
            'button[data-testid="video-play-pause-btn"]',
            'input[data-testid="video-timeline"]',
            'button[data-testid="video-retry-btn"]',
          ],
          screenshots: [
            'docs/reports/screenshots/M4_F02/01_desktop_playback_playing.png',
            'docs/reports/screenshots/M4_F02/02_desktop_seek_near_end.png',
            'docs/reports/screenshots/M4_F02/03_desktop_retry_recovery.png',
          ],
        },
        mobile375px: {
          viewport: '375x667',
          touchTargetPolicyMinPx: 44,
          controlsAudited: mobileAudit.controls,
          collisionsDetected: mobileAudit.collisions,
          touchTargetsCompliant: true,
          screenshot: 'docs/reports/screenshots/M4_F02/04_mobile_playback_375px.png',
        },
        browserPlaybackPerformance: {
          startupToFirstFrameLatency: {
            method: frameTiming.method,
            latencyMs: frameTiming.latencyMs,
          },
          seekToFrameLatency: {
            runsMs: browserSeekRuns,
            stats: browserSeekStats,
            unit: 'ms',
          },
          playbackStallsObserved: observedStalls,
          clientMemoryUsage: 'unavailable (requires OS-level memory profiler; not estimated)',
        },
      },
      springBootHttpBenchmark: {
        springBootHttpChunkTtfbInitial64KiB: {
          description: 'HTTP TTFB of initial 64 KiB Range chunk from Spring Boot server (does not represent browser video decode startup)',
          runs: startupRuns,
          stats: startupStats,
          unit: 'ms',
        },
        springBootHttpChunkTtfbMidSeek: {
          description: 'HTTP TTFB of mid-file Range chunk (bytes=150000-215535)',
          runs: midSeekRuns,
          stats: midSeekStats,
          unit: 'ms',
        },
        springBootHttpChunkTtfbEndSeek: {
          description: 'HTTP TTFB of end-file Range chunk (bytes=250000-)',
          runs: endSeekRuns,
          stats: endSeekStats,
          unit: 'ms',
        },
        singleStreamHttpDownloadThroughput: {
          description: 'Full asset (296 KiB) HTTP Range download throughput on local loopback TCP',
          runs: singleThroughputRuns,
          stats: singleThroughputStats,
          unit: 'MB/s',
        },
        concurrency3HttpStreamBatchTransfer: {
          description: '3 concurrent HTTP Range stream downloads on loopback TCP (evaluates server batch IO transfer, not 3 concurrent human viewers)',
          runs: parallelRuns,
          aggregateThroughputStats: parallelAggregateStats,
          avgStreamTtfbStats: parallelTtfbStats,
          unit: 'MB/s aggregate, ms TTFB',
        },
        clientDisconnectAndPermitCleanup: {
          baselineActiveStreams: 0,
          activeStreamsWhileStreaming: activeWhileStreaming,
          activeStreamsAfterDisconnect: activeAfterDisconnect,
          permitCleanupObserved: true,
          overload429Verified,
          serverHealthAfterDisconnect: 'UP (200 OK)',
        },
        monitoredDirectoryDiskSnapshot: {
          monitoredDirectory: 'backend/springboot/target/test-media',
          beforeFiles: diskBeforeSnapshot.map(f => ({ path: f.relativePath, sizeBytes: f.sizeBytes, sha256: f.sha256 })),
          afterFiles: diskAfterSnapshot.map(f => ({ path: f.relativePath, sizeBytes: f.sizeBytes, sha256: f.sha256 })),
          mutationsDetected: 0,
          readOnlyPreserved: true,
          scopeLimitation: 'Filesystem mutation verification strictly scoped to backend test-media root. OS-wide disk writes are not tracked without kernel-level filesystem auditing.',
        },
      },
      observationsAndHonestLimitations: [
        'Local loopback TCP socket latency is typically under 10ms for warm connections; actual network streaming across WAN will be dominated by RTT, packet loss, and client bandwidth.',
        'Spring Boot 64 KiB bounded buffer streams data iteratively to prevent heap spikes during large concurrent reads.',
        'Stream concurrency is bounded to 10 permits by default (configurable via app.media.max-concurrent-streams); requests exceeding the limit receive HTTP 429 with Retry-After: 5.',
        'Browser seek latency measures time to seeked / video frame render, distinct from raw HTTP chunk TTFB.',
        'Active stream permits are tracked via AtomicInteger in MediaStreamService and verified to return to 0 upon client disconnection.',
        'Google Drive streaming remains in BLOCKED_EXTERNAL_INPUT status as rclone / Google Drive mounting requires external user credentials.',
      ],
    };

    fs.writeFileSync(BENCHMARK_OUT, JSON.stringify(finalReport, null, 2), 'utf8');
    console.log(`\n✔ Benchmark results successfully written to ${BENCHMARK_OUT}`);

    console.log('\n================================================================');
    console.log('       ALL M4-F02 WALKTHROUGH & BENCHMARK CHECKS PASSED         ');
    console.log('================================================================');

  } finally {
    function killProcessTree(proc) {
      if (!proc || !proc.pid) return;
      try {
        if (process.platform === 'win32') {
          require('node:child_process').spawnSync('taskkill', ['/pid', String(proc.pid), '/T', '/F'], { stdio: 'ignore' });
        } else {
          proc.kill('SIGKILL');
        }
      } catch {}
    }

    console.log('\nCleaning up processes and temporary resources...');
    if (chromeSession) {
      try { chromeSession.ws.close(); } catch {}
      killProcessTree(chromeSession.proc);
      try { fs.rmSync(chromeSession.tmpDir, { recursive: true, force: true }); } catch {}
    }
    if (nextProcess) {
      killProcessTree(nextProcess);
    }
    if (springProcess) {
      try { springProcess.stdin.write('\n'); } catch {}
      killProcessTree(springProcess);
    }
    console.log('✔ Cleanup complete.');
  }
}

main().catch((err) => {
  console.error('\n❌ WALKTHROUGH FAILED:', err);
  process.exit(1);
});
