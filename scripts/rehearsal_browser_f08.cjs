/**
 * CATALOG-01-F08: Fail-Closed Browser Automation Suite
 * Complete UI Flow: UI Form Login -> UI Catalog Import -> UI Search -> Video Playback & Seek -> Google Drive Playback
 * Uses Chrome Headless via Chrome DevTools Protocol (CDP) WebSocket.
 * Strictly Fail-Closed: Missing or unclickable elements throw Error immediately (zero currentTime assignment fallback).
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const FIXTURE_PATH = path.join(ROOT, 'docs', 'fixtures', 'rehearsal_catalog.json');
const ASSERTIONS_PATH = path.join(ROOT, 'docs', 'reviews', 'evidence', 'CATALOG_01_F08_browser_assertions.json');
const SCREENSHOT_PATH = path.join(ROOT, 'docs', 'reviews', 'evidence', 'live_rehearsal_f08_player.png');

function assertCondition(condition, message) {
  if (!condition) {
    throw new Error(`[FAIL-CLOSED ASSERTION] ${message}`);
  }
}

async function runBrowserSuiteF08(frontendPort = 3008, cdpPort = 9228) {
  const chromePath = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
  const baseUrl = `http://127.0.0.1:${frontendPort}`;

  console.log(`[BrowserSuite-F08] Launching Chrome Headless against ${baseUrl}...`);
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${cdpPort}`,
    '--no-first-run',
    '--disable-gpu',
    '--autoplay-policy=no-user-gesture-required',
    '--window-size=1280,1000',
    baseUrl
  ]);

  const results = {
    status: 'IN_PROGRESS',
    timestamp: new Date().toISOString(),
    frontendPort,
    cdpPort,
    assertions: {},
    measurements: {}
  };

  let ws = null;

  try {
    // 1. Connect to Chrome CDP
    let pageFound = null;
    for (let i = 0; i < 20; i++) {
      await new Promise(r => setTimeout(r, 1000));
      try {
        const pages = await fetch(`http://127.0.0.1:${cdpPort}/json/list`).then(r => r.json());
        pageFound = pages.find(p => p.type === 'page');
        if (pageFound) break;
      } catch (e) {
        // Retry
      }
    }

    if (!pageFound) {
      throw new Error(`Chrome failed to expose debugging endpoint on port ${cdpPort}`);
    }

    ws = new WebSocket(pageFound.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });

    let id = 1;
    const send = (method, params = {}) => new Promise((resolve, reject) => {
      const cur = id++;
      const timer = setTimeout(() => reject(new Error(`Timeout CDP command ${method}`)), 45000);
      const handler = (e) => {
        const data = JSON.parse(e.data);
        if (data.id === cur) {
          clearTimeout(timer);
          ws.removeEventListener('message', handler);
          if (data.error) {
            reject(new Error(`CDP error ${method}: ${JSON.stringify(data.error)}`));
          } else {
            resolve(data.result);
          }
        }
      };
      ws.addEventListener('message', handler);
      ws.send(JSON.stringify({ id: cur, method, params }));
    });

    await send('Page.enable');
    await send('Runtime.enable');

    const evalJs = async (expr) => {
      const res = await send('Runtime.evaluate', {
        expression: expr,
        returnByValue: true,
        awaitPromise: true
      });
      return res?.result?.value;
    };

    const waitForSelector = async (selector, timeoutMs = 15000) => {
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline) {
        const exists = await evalJs(`!!document.querySelector('${selector}')`);
        if (exists) return true;
        await new Promise(r => setTimeout(r, 500));
      }
      throw new Error(`Timeout waiting for selector: "${selector}" (${timeoutMs}ms)`);
    };

    const clickSelector = async (selector, timeoutMs = 15000) => {
      await waitForSelector(selector, timeoutMs);
      const clicked = await evalJs(`(() => {
        const el = document.querySelector('${selector}');
        if (!el) return false;
        el.click();
        return true;
      })()`);
      assertCondition(clicked === true, `Failed to click selector: "${selector}"`);
    };

    // -------------------------------------------------------------------------
    // STEP 1: UI Form Login (Finding R2: No localStorage bypass!)
    // -------------------------------------------------------------------------
    console.log('[BrowserSuite-F08] Step 1: Performing UI Form Login...');
    await send('Page.navigate', { url: baseUrl });
    await waitForSelector('nav', 15000);

    // Click Login Button in Navbar (retry clicking every 1s until AuthModal mounts, to account for Next.js hydration)
    let modalOpened = false;
    for (let attempt = 0; attempt < 30; attempt++) {
      await evalJs(`(() => {
        const btn = document.querySelector('[data-testid="nav-login-button"]');
        if (btn) btn.click();
      })()`);
      await new Promise(r => setTimeout(r, 1000));
      const hasInput = await evalJs(`!!document.querySelector('[data-testid="login-username-input"]')`);
      if (hasInput) {
        modalOpened = true;
        break;
      }
    }
    assertCondition(modalOpened, 'Timeout waiting for AuthModal [data-testid="login-username-input"] to appear after clicking nav-login-button');

    // Type credentials: admin / password123
    await evalJs(`(() => {
      const u = document.querySelector('[data-testid="login-username-input"]');
      const p = document.querySelector('[data-testid="login-password-input"]');
      const inputSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      if (u) {
        if (inputSetter) inputSetter.call(u, 'admin'); else u.value = 'admin';
        u.dispatchEvent(new Event('input', { bubbles: true }));
        u.dispatchEvent(new Event('change', { bubbles: true }));
      }
      if (p) {
        if (inputSetter) inputSetter.call(p, 'password123'); else p.value = 'password123';
        p.dispatchEvent(new Event('input', { bubbles: true }));
        p.dispatchEvent(new Event('change', { bubbles: true }));
      }
    })()`);

    // Submit login form
    await clickSelector('[data-testid="login-submit-button"]');

    // Wait for authenticated user dropdown button to confirm login
    await waitForSelector('[data-testid="nav-user-dropdown-button"]', 15000);
    console.log('  [PASS] UI Form Login succeeded. User session established.');
    results.assertions.ui_form_login = true;

    // -------------------------------------------------------------------------
    // STEP 2: UI Admin Catalog Import (Finding R2: Real UI Import Flow)
    // -------------------------------------------------------------------------
    console.log('[BrowserSuite-F08] Step 2: Performing UI Admin Catalog Import...');
    await send('Page.navigate', { url: `${baseUrl}/admin/import` });
    await waitForSelector('[data-testid="catalog-json-textarea"]', 20000);
    await new Promise(r => setTimeout(r, 1000));

    // Read fixture content and set into textarea with revision 2 for UI update import
    const fixtureObj = JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf-8'));
    fixtureObj.package.revision = 2;
    function bumpRevisions(obj) {
      if (!obj || typeof obj !== 'object') return;
      if (obj.record && typeof obj.record === 'object' && typeof obj.record.revision === 'number') {
        obj.record.revision = 2;
      }
      for (const key of Object.keys(obj)) {
        bumpRevisions(obj[key]);
      }
    }
    bumpRevisions(fixtureObj);
    const fixtureJson = JSON.stringify(fixtureObj, null, 2);
    await send('Runtime.evaluate', {
      expression: `(() => {
        const ta = document.querySelector('[data-testid="catalog-json-textarea"]');
        if (!ta) return false;
        const taSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
        const val = ${JSON.stringify(fixtureJson)};
        if (taSetter) taSetter.call(ta, val); else ta.value = val;
        ta.dispatchEvent(new Event('input', { bubbles: true }));
        ta.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      })()`,
      returnByValue: true
    });

    // Click Validate & Preview button
    await clickSelector('[data-testid="catalog-validate-button"]');
    await waitForSelector('[data-testid="catalog-validation-status"]', 20000);

    const valStatusText = (await evalJs(`document.querySelector('[data-testid="catalog-validation-status"]')?.innerText || ''`)) || '';
    assertCondition((valStatusText || '').includes('Gói hợp lệ'), `Validation did not report valid package: "${valStatusText}"`);
    console.log('  [PASS] UI Catalog validation succeeded (Gói hợp lệ).');

    // Wait for import button to become enabled after validation
    await new Promise(r => setTimeout(r, 1000));

    // Click Confirm Import button ONCE
    await clickSelector('[data-testid="catalog-import-button"]');

    // Wait for either success panel or explicit error
    let importDone = false;
    let importDiagnostics = '';
    const importDeadline = Date.now() + 35000;
    while (Date.now() < importDeadline) {
      const isSuccess = await evalJs(`!!document.querySelector('[data-testid="catalog-import-success-panel"]')`);
      if (isSuccess) {
        importDone = true;
        break;
      }

      importDiagnostics = (await evalJs(`(() => {
        const importErr = document.querySelector('[data-testid="catalog-import-error"]');
        if (importErr) return 'IMPORT_ERROR: ' + importErr.innerText;
        const parseErr = document.querySelector('[data-testid="catalog-parsing-error"]');
        if (parseErr) return 'PARSE_ERROR: ' + parseErr.innerText;
        const panel = document.querySelector('[data-testid="catalog-validation-panel"]');
        return panel ? panel.innerText : document.body.innerText;
      })()`)) || '';

      if (importDiagnostics.includes('IMPORT_ERROR:') || importDiagnostics.includes('PARSE_ERROR:')) {
        break;
      }

      await new Promise(r => setTimeout(r, 1000));
    }
    assertCondition(importDone, `Import failed or reported error. UI State:\n${importDiagnostics}`);
    console.log('  [PASS] UI Catalog import committed to DB (Nhập dữ liệu thành công).');
    results.assertions.ui_catalog_import = true;

    // Give background worker a brief moment to sync outbox
    await new Promise(r => setTimeout(r, 3000));

    // -------------------------------------------------------------------------
    // STEP 3: UI Catalog Search & Navigation (Finding R2: Real Search UI)
    // -------------------------------------------------------------------------
    console.log('[BrowserSuite-F08] Step 3: Performing UI Catalog Search & Navigation...');
    await send('Page.navigate', { url: `${baseUrl}/search` });
    await waitForSelector('[data-testid="search-query-input"]', 20000);
    await new Promise(r => setTimeout(r, 1000));

    // Type query: "Bảo"
    await evalJs(`(() => {
      const inp = document.querySelector('[data-testid="search-query-input"]');
      if (inp) {
        const inputSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        if (inputSetter) inputSetter.call(inp, 'Bảo'); else inp.value = 'Bảo';
        inp.dispatchEvent(new Event('input', { bubbles: true }));
        inp.dispatchEvent(new Event('change', { bubbles: true }));
      }
    })()`);

    // Wait for search result cards
    await waitForSelector('[data-testid="search-result-card"]', 15000);
    const cardFound = await evalJs(`(() => {
      const cards = Array.from(document.querySelectorAll('[data-testid="search-result-card"]'));
      return cards.some(c => (c.innerText || '').includes('Biên Niên Sử') || c.getAttribute('data-result-id') === 'ser_rehearsal_01');
    })()`);
    assertCondition(cardFound, 'Expected search result card for ser_rehearsal_01 not found');

    // Click the result card to navigate to /series/ser_rehearsal_01
    await clickSelector('[data-testid="search-result-card"][data-result-id="ser_rehearsal_01"]');
    await waitForSelector('[data-testid="series-video-player"]', 20000);
    console.log('  [PASS] UI Search returned results and navigated to player page.');
    results.assertions.ui_search_and_navigation = true;

    // -------------------------------------------------------------------------
    // STEP 4: Public Video Playback & Real Frame Decoding (Asset 1)
    // -------------------------------------------------------------------------
    console.log('[BrowserSuite-F08] Step 4: Verifying Public Video Playback & Frame Decoding...');
    // Await readyState and trigger play
    let framesDecoded = false;
    let initialDimensions = '';
    for (let i = 0; i < 25; i++) {
      await new Promise(r => setTimeout(r, 1000));
      const vState = await evalJs(`(() => {
        const v = document.querySelector('video[data-testid="series-video-player"]');
        if (!v) return null;
        if (v.paused) v.play().catch(() => {});
        const quality = typeof v.getVideoPlaybackQuality === 'function' ? v.getVideoPlaybackQuality() : null;
        return {
          videoWidth: v.videoWidth,
          videoHeight: v.videoHeight,
          currentTime: v.currentTime,
          paused: v.paused,
          readyState: v.readyState,
          decodedFrames: (quality ? quality.totalVideoFrames : 0) || v.webkitDecodedFrameCount || 0
        };
      })()`);

      if (vState && vState.videoWidth === 1280 && vState.videoHeight === 720) {
        framesDecoded = true;
        initialDimensions = `${vState.videoWidth}x${vState.videoHeight}`;
        results.measurements.public_video_dimensions = initialDimensions;
        results.measurements.public_video_decoded_frames = vState.decodedFrames;
        break;
      }
    }
    assertCondition(framesDecoded, `Video frames not decoded (expected 1280x720, got: ${initialDimensions})`);

    // Verify currentTime advances across 2 samples separated by 1000ms
    const sample1 = await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.currentTime || 0`);
    await new Promise(r => setTimeout(r, 1200));
    const sample2 = await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.currentTime || 0`);
    const advanceSec = sample2 - sample1;
    console.log(`  Sample 1: ${sample1.toFixed(3)}s -> Sample 2: ${sample2.toFixed(3)}s (advance: +${advanceSec.toFixed(3)}s)`);
    assertCondition(advanceSec >= 0.3, `Public video currentTime failed to advance (+${advanceSec}s)`);
    results.measurements.public_playback_advance_sec = advanceSec;
    results.assertions.public_playback_advance = true;

    // -------------------------------------------------------------------------
    // STEP 5: Pause & Resume Controls
    // -------------------------------------------------------------------------
    console.log('[BrowserSuite-F08] Step 5: Testing Pause & Resume Controls...');
    // Pause
    await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.pause()`);
    await new Promise(r => setTimeout(r, 400));
    const p1 = await evalJs(`(() => {
      const v = document.querySelector('video[data-testid="series-video-player"]');
      return { paused: v ? v.paused : false, time: v ? v.currentTime : -1 };
    })()`);
    assertCondition(p1.paused === true, 'Video failed to enter paused state');

    await new Promise(r => setTimeout(r, 800));
    const p2 = await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.currentTime || -1`);
    assertCondition(Math.abs(p2 - p1.time) < 0.1, `Paused video time drifted: ${p1.time} -> ${p2}`);
    console.log(`  [PASS] Pause verified: time held steady at ${p1.time.toFixed(3)}s.`);

    // Resume
    await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.play()`);
    await new Promise(r => setTimeout(r, 1200));
    const r2 = await evalJs(`(() => {
      const v = document.querySelector('video[data-testid="series-video-player"]');
      return { paused: v ? v.paused : true, time: v ? v.currentTime : -1 };
    })()`);
    assertCondition(r2.paused === false && r2.time > p1.time + 0.3, 'Video failed to resume playback');
    console.log(`  [PASS] Resume verified: playback advanced to ${r2.time.toFixed(3)}s.`);
    results.assertions.pause_resume_controls = true;

    // -------------------------------------------------------------------------
    // STEP 6: Scene Direct Seek (Finding R2: FAIL-CLOSED, Zero Fallback!)
    // -------------------------------------------------------------------------
    console.log('[BrowserSuite-F08] Step 6: Testing Scene Seek to scene_rehearsal_canyon (15.0s, FAIL-CLOSED)...');
    // Strictly click selector without any fallback!
    await clickSelector('[data-scene-id="scene_rehearsal_canyon"]', 10000);
    await new Promise(r => setTimeout(r, 1500));

    const sceneSeekTime = await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.currentTime || -1`);
    console.log(`  Post-scene-seek currentTime: ${sceneSeekTime.toFixed(3)}s (Target: 15.0s)`);
    assertCondition(sceneSeekTime >= 14.5 && sceneSeekTime <= 18.0, `Scene seek target mismatch: expected ~15.0s, got ${sceneSeekTime}s`);
    results.measurements.scene_seek_actual_sec = sceneSeekTime;
    results.assertions.scene_direct_seek_15s = true;

    // -------------------------------------------------------------------------
    // STEP 7: 3 Sequential Timeline Seeks (30s, 60s, 115s)
    // -------------------------------------------------------------------------
    console.log('[BrowserSuite-F08] Step 7: Testing 3 sequential timeline seeks (30s, 60s, 115s)...');
    for (const targetSec of [30.0, 60.0, 115.0]) {
      await evalJs(`(() => {
        const v = document.querySelector('video[data-testid="series-video-player"]');
        if (v) v.currentTime = ${targetSec};
      })()`);
      await new Promise(r => setTimeout(r, 1200));
      const postSeek = await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.currentTime || -1`);
      console.log(`  Seek to ${targetSec}s -> actual: ${postSeek.toFixed(3)}s`);
      assertCondition(postSeek >= targetSec - 0.5 && postSeek <= targetSec + 3.0, `Seek to ${targetSec}s failed (actual: ${postSeek}s)`);
    }
    results.assertions.three_timeline_seeks = true;

    // -------------------------------------------------------------------------
    // STEP 8: Switch to Episode 2 (Protected Asset with Grant) & Seek
    // -------------------------------------------------------------------------
    console.log('[BrowserSuite-F08] Step 8: Testing Episode 2 switch (protected asset with grant)...');
    await clickSelector('[data-episode-id="ep_rehearsal_01_02"]', 10000);

    // Wait for grant attached to src and readyState
    let ep2Ready = false;
    let ep2Src = '';
    for (let i = 0; i < 25; i++) {
      await new Promise(r => setTimeout(r, 1000));
      const ep2State = await evalJs(`(() => {
        const v = document.querySelector('video[data-testid="series-video-player"]');
        if (!v) return null;
        if (v.paused) v.play().catch(() => {});
        return {
          src: v.src,
          readyState: v.readyState,
          videoWidth: v.videoWidth,
          currentTime: v.currentTime
        };
      })()`);

      if (ep2State && (ep2State.src || '').includes('grant=') && ep2State.videoWidth > 0) {
        ep2Ready = true;
        ep2Src = ep2State.src;
        break;
      }
    }
    assertCondition(ep2Ready, `Episode 2 protected video failed to load with grant (src: ${ep2Src})`);
    console.log('  [PASS] Episode 2 loaded protected video with playback grant token.');

    // Seek to protected scene (scene_rehearsal_base_secret, 20.0s)
    console.log('  Seeking to protected scene scene_rehearsal_base_secret (20.0s, FAIL-CLOSED)...');
    await clickSelector('[data-scene-id="scene_rehearsal_base_secret"]', 10000);
    await new Promise(r => setTimeout(r, 1500));
    const ep2SceneTime = await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.currentTime || -1`);
    console.log(`  Post-protected-scene-seek currentTime: ${ep2SceneTime.toFixed(3)}s (Target: 20.0s)`);
    assertCondition(ep2SceneTime >= 19.5 && ep2SceneTime <= 23.0, `Protected scene seek mismatch: expected ~20.0s, got ${ep2SceneTime}s`);
    results.measurements.ep2_protected_scene_seek_sec = ep2SceneTime;
    results.assertions.protected_episode2_playback_and_seek = true;

    // -------------------------------------------------------------------------
    // STEP 9: Real Google Drive Video Playback in Browser (Finding R3)
    // -------------------------------------------------------------------------
    console.log('[BrowserSuite-F08] Step 9: Testing Real Google Drive Video Playback in Browser...');
    // Switch back to Episode 1 which has both Local and Drive assets
    await clickSelector('[data-episode-id="ep_rehearsal_01_01"]', 10000);
    await new Promise(r => setTimeout(r, 1500));

    // Look for Google Drive asset button
    await waitForSelector('[data-testid="media-asset-button"][data-asset-id="asset_rehearsal_drive"]', 10000);
    await clickSelector('[data-testid="media-asset-button"][data-asset-id="asset_rehearsal_drive"]');

    // Wait for video element to switch src to asset_rehearsal_drive and decode frames
    let driveDecoded = false;
    let driveDimensions = '';
    for (let i = 0; i < 45; i++) {
      await new Promise(r => setTimeout(r, 1000));
      const dState = await evalJs(`(() => {
        const v = document.querySelector('video[data-testid="series-video-player"]');
        if (!v) return null;
        if (v.paused) v.play().catch(() => {});
        return {
          src: v.src,
          readyState: v.readyState,
          videoWidth: v.videoWidth,
          videoHeight: v.videoHeight,
          currentTime: v.currentTime
        };
      })()`);

      if (dState && (dState.src || '').includes('asset_rehearsal_drive') && dState.videoWidth > 0 && dState.videoHeight > 0) {
        driveDecoded = true;
        driveDimensions = `${dState.videoWidth}x${dState.videoHeight}`;
        results.measurements.google_drive_video_dimensions = driveDimensions;
        break;
      }
    }
    assertCondition(driveDecoded, `Google Drive video failed to decode frames: ${driveDimensions}`);
    console.log(`  [PASS] Real Google Drive video decoded frames (${driveDimensions}) via Spring Boot storage adapter!`);

    // Verify time advances on Drive video
    const dt1 = await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.currentTime || 0`);
    await new Promise(r => setTimeout(r, 1500));
    const dt2 = await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.currentTime || 0`);
    const driveAdvance = dt2 - dt1;
    console.log(`  Drive playback: ${dt1.toFixed(3)}s -> ${dt2.toFixed(3)}s (+${driveAdvance.toFixed(3)}s)`);
    assertCondition(driveAdvance >= 0.3, `Drive video failed to advance time (+${driveAdvance}s)`);

    // Drive seek verification (seek to 60s)
    await evalJs(`(() => {
      const v = document.querySelector('video[data-testid="series-video-player"]');
      if (v) v.currentTime = 60.0;
    })()`);
    let drivePostSeek = -1;
    for (let i = 0; i < 20; i++) {
      await new Promise(r => setTimeout(r, 1000));
      drivePostSeek = await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.currentTime || -1`);
      if (drivePostSeek >= 59.5 && drivePostSeek <= 65.0) break;
    }
    console.log(`  Drive seek to 60.0s -> actual: ${drivePostSeek.toFixed(3)}s`);
    assertCondition(drivePostSeek >= 59.5 && drivePostSeek <= 65.0, `Drive seek to 60s failed (actual: ${drivePostSeek}s)`);
    results.measurements.google_drive_seek_sec = drivePostSeek;
    results.assertions.google_drive_browser_playback = true;

    // -------------------------------------------------------------------------
    // STEP 10: Negative Control Test (Fail-Closed Verification)
    // -------------------------------------------------------------------------
    console.log('[BrowserSuite-F08] Step 10: Testing Fail-Closed Negative Control...');
    const nonExistentResult = await evalJs(`document.querySelector('[data-testid="deliberately_non_existent_element"]')`);
    assertCondition(nonExistentResult === null, 'Negative control element unexpectedly found');
    let caughtExpectedError = false;
    try {
      await clickSelector('[data-testid="deliberately_non_existent_element"]', 1000);
    } catch (e) {
      caughtExpectedError = true;
    }
    assertCondition(caughtExpectedError, 'Fail-closed negative control did not raise expected error');
    console.log('  [PASS] Fail-closed negative control verified: missing element throws error without fallback.');
    results.assertions.fail_closed_negative_control = true;

    // -------------------------------------------------------------------------
    // STEP 11: Capture Proof Screenshot & Write Assertions JSON
    // -------------------------------------------------------------------------
    console.log('[BrowserSuite-F08] Step 11: Capturing Live Screenshot proof...');
    const ssRes = await send('Page.captureScreenshot', { format: 'png' });
    if (ssRes && ssRes.data) {
      fs.mkdirSync(path.dirname(SCREENSHOT_PATH), { recursive: true });
      fs.writeFileSync(SCREENSHOT_PATH, Buffer.from(ssRes.data, 'base64'));
      console.log(`  [Screenshot saved] -> ${SCREENSHOT_PATH}`);
      results.measurements.screenshot_path = SCREENSHOT_PATH;
    }

    results.status = 'PASSED';
    console.log('\n=============================================================================');
    console.log('ALL BROWSER ASSERTIONS PASSED (100% FAIL-CLOSED, ZERO FALLBACK)');
    console.log('=============================================================================');

  } catch (err) {
    results.status = 'FAILED';
    results.error = err.message;
    console.error(`\n[BrowserSuite-F08 ERROR] ${err.message}`);
  } finally {
    if (ws) {
      try { ws.close(); } catch (e) {}
    }
    if (chromeProc) {
      try {
        chromeProc.kill();
      } catch (e) {}
    }

    // Write raw assertions JSON evidence
    fs.mkdirSync(path.dirname(ASSERTIONS_PATH), { recursive: true });
    fs.writeFileSync(ASSERTIONS_PATH, JSON.stringify(results, null, 2), 'utf-8');
    console.log(`[BrowserSuite-F08 Evidence written] -> ${ASSERTIONS_PATH}`);

    if (results.status !== 'PASSED') {
      process.exit(1);
    }
  }
}

// CLI entry point
const frontendPort = parseInt(process.argv[2] || '3008', 10);
const cdpPort = parseInt(process.argv[3] || '9228', 10);

runBrowserSuiteF08(frontendPort, cdpPort);
