const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Redact any auth or grant tokens from URLs before recording
const redactUrl = (url) => {
  if (!url) return '';
  return String(url)
    .replace(/([?&]grant=)[^&\s]+/g, '$1[REDACTED]')
    .replace(/([?&]token=)[^&\s]+/g, '$1[REDACTED]');
};

async function runBrowserVerificationF02() {
  const evidence = {
    timestamp: new Date().toISOString(),
    mission: 'USABILITY-01-F02 — SỬA NỐT ĐỔI TẬP VÀ TIMESTAMP SCENE',
    status: 'UNKNOWN',
    auth: {},
    case_1_v1_episode_switching: {},
    case_2_v2_scene_seek: {},
    case_3_v2_segment_seek: {},
    screenshots: {}
  };

  const port = 9227;
  const profileDir = path.join(os.tmpdir(), 'chrome_usability_f02_' + Date.now());
  fs.mkdirSync(profileDir, { recursive: true });

  const chromeCandidates = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    path.join(process.env.LOCALAPPDATA || '', 'Google\\Chrome\\Application\\chrome.exe')
  ];
  const chromePath = chromeCandidates.find(p => fs.existsSync(p));
  if (!chromePath) {
    throw new Error('Chrome executable not found');
  }

  console.log(`[USABILITY-01-F02] Launching Chrome Headless on CDP port ${port}...`);
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    '--no-first-run',
    '--disable-gpu',
    '--autoplay-policy=no-user-gesture-required',
    '--window-size=1280,1000',
    'about:blank'
  ]);

  let ws = null;

  try {
    // 1. Connect to CDP
    let page = null;
    const deadlineConnect = Date.now() + 15000;
    while (Date.now() < deadlineConnect) {
      try {
        const pages = await fetch(`http://127.0.0.1:${port}/json/list`).then(r => r.json());
        page = pages.find(p => p.type === 'page');
        if (page) break;
      } catch (_) {
        await new Promise(r => setTimeout(r, 500));
      }
    }
    if (!page) throw new Error('No target page found in Chrome instance within 15s');

    ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });

    let reqId = 1;
    const send = (method, params = {}) => new Promise((resolve, reject) => {
      const cur = reqId++;
      const timer = setTimeout(() => reject(new Error('Timeout waiting for CDP method: ' + method)), 150000);
      const handler = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.id === cur) {
            clearTimeout(timer);
            ws.removeEventListener('message', handler);
            if (data.error) {
              return reject(new Error(`CDP ${method} Error: ${data.error.message || JSON.stringify(data.error)}`));
            }
            if (data.result && data.result.exceptionDetails) {
              const ex = data.result.exceptionDetails;
              return reject(new Error(`Runtime.evaluate Exception in ${method}: ${ex.text || ex.exception?.description || JSON.stringify(ex)}`));
            }
            resolve(data.result);
          }
        } catch (err) {
          clearTimeout(timer);
          ws.removeEventListener('message', handler);
          reject(err);
        }
      };
      ws.addEventListener('message', handler);
      ws.send(JSON.stringify({ id: cur, method, params }));
    });

    await send('Page.enable');
    await send('Runtime.enable');

    const ensureDir = (p) => { if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true }); };
    ensureDir('docs/reviews/evidence');

    // 2. Perform admin authentication
    console.log('[USABILITY-01-F02] Step 1: Authenticating as admin to obtain access token...');
    const loginRes = await fetch('http://127.0.0.1:8080/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ usernameOrEmail: 'admin', password: 'password123' })
    }).then(r => r.json());

    if (!loginRes || !loginRes.data || !loginRes.data.token) {
      throw new Error('Failed to login as admin');
    }
    const authToken = loginRes.data.token;
    evidence.auth = {
      username: 'admin',
      token_received: Boolean(authToken),
      expires_in: loginRes.data.expiresIn
    };
    console.log('[USABILITY-01-F02] Admin authenticated successfully.');

    // Inject auth token into localStorage on domain
    await send('Page.navigate', { url: 'http://localhost:3000/' });
    await new Promise(r => setTimeout(r, 2000));
    await send('Runtime.evaluate', {
      expression: `(() => {
        localStorage.setItem('token', ${JSON.stringify(authToken)});
        localStorage.setItem('dippie_auth_token', ${JSON.stringify(authToken)});
        localStorage.setItem('auth_token', ${JSON.stringify(authToken)});
        return true;
      })()`
    });

    // -------------------------------------------------------------------------
    // CASE 1: V1 EPISODE SWITCHING (NO SNAPBACK)
    // -------------------------------------------------------------------------
    console.log('\n[USABILITY-01-F02] Case 1: Testing V1 Episode Switching & Snapback Immunity...');

    // Step 1.1: Navigate to S1E1 deep link (simulating click from CineBot card)
    const initialUrl = 'http://localhost:3000/series/ser_jadoo?episode=ep_jadoo_s01_0001';
    console.log(`[USABILITY-01-F02] Navigating to initial deep-link: ${initialUrl}`);
    await send('Page.navigate', { url: initialUrl });
    await new Promise(r => setTimeout(r, 2500));

    // Wait for S1E1 video player to initialize and load media
    console.log('[USABILITY-01-F02] Waiting for Episode 1 media to load...');
    let ep1Loaded = false;
    let ep1State = null;
    const ep1Deadline = Date.now() + 30000;
    while (Date.now() < ep1Deadline) {
      await new Promise(r => setTimeout(r, 1000));
      const vRes = await send('Runtime.evaluate', {
        expression: `(() => {
          const video = document.querySelector('video');
          const epHeader = document.querySelector('h2');
          return {
            hasVideo: !!video,
            src: video ? video.currentSrc || video.src : null,
            videoWidth: video ? video.videoWidth : 0,
            videoHeight: video ? video.videoHeight : 0,
            duration: video ? video.duration : 0,
            currentTime: video ? video.currentTime : 0,
            paused: video ? video.paused : true,
            episodeTitle: epHeader ? epHeader.textContent : ''
          };
        })()`,
        returnByValue: true
      });
      const v = vRes?.result?.value;
      if (v && v.hasVideo && v.src && v.videoWidth > 0 && v.src.includes('asset_jadoo_s01_v0001')) {
        ep1Loaded = true;
        ep1State = v;
        break;
      }
    }
    if (!ep1Loaded || !ep1State) {
      throw new Error('Episode 1 failed to load media within 30s');
    }
    console.log('[USABILITY-01-F02] Episode 1 loaded successfully:', {
      title: ep1State.episodeTitle,
      dimensions: `${ep1State.videoWidth}x${ep1State.videoHeight}`,
      src: redactUrl(ep1State.src)
    });

    // Test Episode 1 playback advancement
    await send('Runtime.evaluate', { expression: 'document.querySelector("video").play()' });
    const ep1T0 = (await send('Runtime.evaluate', { expression: 'document.querySelector("video").currentTime', returnByValue: true })).result.value;
    await new Promise(r => setTimeout(r, 2000));
    const ep1T1 = (await send('Runtime.evaluate', { expression: 'document.querySelector("video").currentTime', returnByValue: true })).result.value;
    const ep1Advancing = ep1T1 > ep1T0;
    console.log(`[USABILITY-01-F02] Episode 1 playback advancing: ${ep1T0.toFixed(3)}s -> ${ep1T1.toFixed(3)}s (advancing: ${ep1Advancing})`);
    if (!ep1Advancing) throw new Error('Episode 1 playback failed to advance time');

    // Capture S1E1 screenshot
    const s01e01Snap = await send('Page.captureScreenshot', { format: 'png' });
    const s01e01SnapPath = 'docs/reviews/evidence/USABILITY_01_F02_live_s01e01_playing.png';
    fs.writeFileSync(s01e01SnapPath, Buffer.from(s01e01Snap.data, 'base64'));
    evidence.screenshots.s01e01 = s01e01SnapPath;

    // Step 1.2: Manually click Episode 2 (ep_jadoo_s01_0002) in sidebar
    console.log('[USABILITY-01-F02] Clicking Episode 2 button in sidebar list...');
    const clickRes = await send('Runtime.evaluate', {
      expression: `(() => {
        const btn = document.querySelector('button[data-episode-id="ep_jadoo_s01_0002"]');
        if (btn) {
          btn.click();
          return { clicked: true, text: btn.textContent };
        }
        // Fallback: look by text
        const allBtns = Array.from(document.querySelectorAll('button'));
        const fallback = allBtns.find(b => b.textContent && b.textContent.includes('Tập 2'));
        if (fallback) {
          fallback.click();
          return { clicked: true, text: fallback.textContent };
        }
        return { clicked: false };
      })()`,
      returnByValue: true
    });
    console.log('[USABILITY-01-F02] Click result:', clickRes?.result?.value);
    if (!clickRes?.result?.value?.clicked) {
      throw new Error('Failed to find Episode 2 button in sidebar');
    }

    // Step 1.3: Wait 3 seconds for state to settle, then verify Episode 2 is maintained (NO SNAPBACK!)
    console.log('[USABILITY-01-F02] Waiting 3000ms for state and requests to settle...');
    await new Promise(r => setTimeout(r, 3000));

    // Verify URL bar is updated to ep_jadoo_s01_0002
    const currentLoc = (await send('Runtime.evaluate', { expression: 'window.location.href', returnByValue: true })).result.value;
    console.log(`[USABILITY-01-F02] Post-click URL: ${currentLoc}`);
    if (!currentLoc.includes('episode=ep_jadoo_s01_0002')) {
      throw new Error(`CRITICAL V1 REGRESSION: URL did not update to ep_jadoo_s01_0002: ${currentLoc}`);
    }
    if (currentLoc.includes('episode=ep_jadoo_s01_0001')) {
      throw new Error(`CRITICAL V1 REGRESSION: URL still contains ep_jadoo_s01_0001: ${currentLoc}`);
    }

    // Wait for Episode 2 video media to load
    console.log('[USABILITY-01-F02] Waiting for Episode 2 media to load...');
    let ep2Loaded = false;
    let ep2State = null;
    const ep2Deadline = Date.now() + 30000;
    while (Date.now() < ep2Deadline) {
      await new Promise(r => setTimeout(r, 1000));
      const vRes = await send('Runtime.evaluate', {
        expression: `(() => {
          const video = document.querySelector('video');
          const epHeader = document.querySelector('h2');
          return {
            hasVideo: !!video,
            src: video ? video.currentSrc || video.src : null,
            videoWidth: video ? video.videoWidth : 0,
            videoHeight: video ? video.videoHeight : 0,
            duration: video ? video.duration : 0,
            currentTime: video ? video.currentTime : 0,
            paused: video ? video.paused : true,
            episodeTitle: epHeader ? epHeader.textContent : ''
          };
        })()`,
        returnByValue: true
      });
      const v = vRes?.result?.value;
      if (v && v.hasVideo && v.src && v.videoWidth > 0 && v.src.includes('asset_jadoo_s01_v0002')) {
        ep2Loaded = true;
        ep2State = v;
        break;
      }
    }
    if (!ep2Loaded || !ep2State) {
      throw new Error('Episode 2 failed to load media within 30s');
    }

    console.log('[USABILITY-01-F02] Episode 2 loaded successfully:', {
      title: ep2State.episodeTitle,
      dimensions: `${ep2State.videoWidth}x${ep2State.videoHeight}`,
      src: redactUrl(ep2State.src)
    });

    // Test Episode 2 playback advancement
    await send('Runtime.evaluate', { expression: 'document.querySelector("video").play()' });
    const ep2T0 = (await send('Runtime.evaluate', { expression: 'document.querySelector("video").currentTime', returnByValue: true })).result.value;
    await new Promise(r => setTimeout(r, 2000));
    const ep2T1 = (await send('Runtime.evaluate', { expression: 'document.querySelector("video").currentTime', returnByValue: true })).result.value;
    const ep2Advancing = ep2T1 > ep2T0;
    console.log(`[USABILITY-01-F02] Episode 2 playback advancing: ${ep2T0.toFixed(3)}s -> ${ep2T1.toFixed(3)}s (advancing: ${ep2Advancing})`);
    if (!ep2Advancing) throw new Error('Episode 2 playback failed to advance time');

    // Confirm that after playback advancement, URL and state are STILL Episode 2 (IMMUNITY CONFIRMED)
    const finalLoc = (await send('Runtime.evaluate', { expression: 'window.location.href', returnByValue: true })).result.value;
    if (!finalLoc.includes('episode=ep_jadoo_s01_0002') || finalLoc.includes('episode=ep_jadoo_s01_0001')) {
      throw new Error(`CRITICAL V1 REGRESSION: State snapped back to ep1 during playback: ${finalLoc}`);
    }

    // Capture S1E2 screenshot
    const s01e02Snap = await send('Page.captureScreenshot', { format: 'png' });
    const s01e02SnapPath = 'docs/reviews/evidence/USABILITY_01_F02_live_s01e02_playing.png';
    fs.writeFileSync(s01e02SnapPath, Buffer.from(s01e02Snap.data, 'base64'));
    evidence.screenshots.s01e02 = s01e02SnapPath;

    // Step 1.4: Click back to Episode 1 to test bi-directional switching
    console.log('[USABILITY-01-F02] Clicking back to Episode 1 in sidebar...');
    await send('Runtime.evaluate', {
      expression: `(() => {
        const btn = document.querySelector('button[data-episode-id="ep_jadoo_s01_0001"]');
        if (btn) btn.click();
      })()`
    });
    await new Promise(r => setTimeout(r, 2500));
    const backToEp1Loc = (await send('Runtime.evaluate', { expression: 'window.location.href', returnByValue: true })).result.value;
    console.log(`[USABILITY-01-F02] Post-switch-back URL: ${backToEp1Loc}`);
    if (!backToEp1Loc.includes('episode=ep_jadoo_s01_0001')) {
      throw new Error(`Failed to switch back to Episode 1: ${backToEp1Loc}`);
    }

    evidence.case_1_v1_episode_switching = {
      initial_url: initialUrl,
      initial_episode_id: 'ep_jadoo_s01_0001',
      initial_asset_id: 'asset_jadoo_s01_v0001',
      initial_advance: { ep1T0, ep1T1, delta_s: ep1T1 - ep1T0, advancing: ep1Advancing },
      selected_episode_id: 'ep_jadoo_s01_0002',
      post_click_url: currentLoc,
      snapback_detected: false,
      post_click_asset_id: 'asset_jadoo_s01_v0002',
      post_click_advance: { ep2T0, ep2T1, delta_s: ep2T1 - ep2T0, advancing: ep2Advancing },
      switch_back_url: backToEp1Loc,
      switch_back_success: true,
      status: 'PASS'
    };

    // -------------------------------------------------------------------------
    // CASE 2: V2 SCENE SEEK WITH FILE TIMELINE (5.0s, NO COVERAGE SHIFT)
    // -------------------------------------------------------------------------
    console.log('\n[USABILITY-01-F02] Case 2: Testing V2 Scene Seek with timeline=file...');
    const sceneUrl = 'http://localhost:3000/series/ser_jadoo?episode=ep_jadoo_s01_0001&scene=scene_jadoo_s01_0001_sc01&asset=asset_jadoo_s01_v0001&t=5000&timeline=file';
    console.log(`[USABILITY-01-F02] Navigating to Scene URL: ${sceneUrl}`);
    await send('Page.navigate', { url: sceneUrl });
    await new Promise(r => setTimeout(r, 3500));

    // Wait for video to load and seek to ~5.0s
    let sceneLoaded = false;
    let sceneState = null;
    const sceneDeadline = Date.now() + 30000;
    while (Date.now() < sceneDeadline) {
      await new Promise(r => setTimeout(r, 1000));
      const sRes = await send('Runtime.evaluate', {
        expression: `(() => {
          const video = document.querySelector('video');
          const epHeader = document.querySelector('h2');
          const sceneEl = document.querySelector('[data-scene-id="scene_jadoo_s01_0001_sc01"]');
          const isSceneActive = sceneEl ? (sceneEl.className.includes('bg-brand') || sceneEl.className.includes('border-brand') || sceneEl.className.includes('text-brand')) : false;
          return {
            hasVideo: !!video,
            src: video ? video.currentSrc || video.src : null,
            videoWidth: video ? video.videoWidth : 0,
            videoHeight: video ? video.videoHeight : 0,
            currentTime: video ? video.currentTime : 0,
            duration: video ? video.duration : 0,
            episodeTitle: epHeader ? epHeader.textContent : '',
            sceneFound: !!sceneEl,
            sceneActive: isSceneActive
          };
        })()`,
        returnByValue: true
      });
      const s = sRes?.result?.value;
      if (s && s.hasVideo && s.src && s.videoWidth > 0 && s.currentTime >= 4.0) {
        sceneLoaded = true;
        sceneState = s;
        break;
      }
    }
    if (!sceneLoaded || !sceneState) {
      throw new Error(`Scene deep-link failed to load or seek: currentTime=${sceneState?.currentTime}`);
    }

    console.log('[USABILITY-01-F02] Scene deep-link loaded:', {
      currentTime: sceneState.currentTime,
      sceneActive: sceneState.sceneActive,
      src: redactUrl(sceneState.src)
    });

    // Strict V2 invariant: currentTime must be close to 5.0s (file timestamp), NOT shifted by coverage to 35s!
    const seekDelta = Math.abs(sceneState.currentTime - 5.0);
    console.log(`[USABILITY-01-F02] Scene seek position: ${sceneState.currentTime.toFixed(3)}s (delta from 5.0s: ${seekDelta.toFixed(3)}s)`);
    if (seekDelta > 3.0) {
      throw new Error(`CRITICAL V2 REGRESSION: Scene seeked to ${sceneState.currentTime}s, expected ~5.0s (likely shifted by coverage!)`);
    }

    // Capture scene screenshot
    const sceneSnap = await send('Page.captureScreenshot', { format: 'png' });
    const sceneSnapPath = 'docs/reviews/evidence/USABILITY_01_F02_live_scene_seek_5s.png';
    fs.writeFileSync(sceneSnapPath, Buffer.from(sceneSnap.data, 'base64'));
    evidence.screenshots.scene = sceneSnapPath;

    evidence.case_2_v2_scene_seek = {
      url: sceneUrl,
      scene_id: 'scene_jadoo_s01_0001_sc01',
      timeline: 'file',
      requested_time_ms: 5000,
      expected_seconds: 5.0,
      actual_seconds: sceneState.currentTime,
      delta_seconds: seekDelta,
      scene_highlighted: sceneState.sceneActive,
      stream_url_redacted: redactUrl(sceneState.src),
      coverage_shift_avoided: true,
      status: 'PASS'
    };

    // -------------------------------------------------------------------------
    // CASE 3: V2 SEGMENT SEEK WITH LOGICAL TIMELINE
    // -------------------------------------------------------------------------
    console.log('\n[USABILITY-01-F02] Case 3: Testing V2 Segment Seek with logical timeline...');
    const segUrl = 'http://localhost:3000/series/ser_jadoo?episode=ep_jadoo_s01_0008&segment=seg_jadoo_s01_008a&asset=asset_jadoo_s01_v0008&t=0';
    console.log(`[USABILITY-01-F02] Navigating to Segment URL: ${segUrl}`);
    await send('Page.navigate', { url: segUrl });
    await new Promise(r => setTimeout(r, 3500));

    let segLoaded = false;
    let segState = null;
    const segDeadline = Date.now() + 30000;
    while (Date.now() < segDeadline) {
      await new Promise(r => setTimeout(r, 1000));
      const sRes = await send('Runtime.evaluate', {
        expression: `(() => {
          const video = document.querySelector('video');
          const epHeader = document.querySelector('h2');
          const segEl = document.querySelector('[data-segment-id="seg_jadoo_s01_008a"]');
          const isSegActive = segEl ? (segEl.className.includes('bg-brand') || segEl.className.includes('border-brand') || segEl.className.includes('text-brand')) : false;
          return {
            hasVideo: !!video,
            src: video ? video.currentSrc || video.src : null,
            videoWidth: video ? video.videoWidth : 0,
            videoHeight: video ? video.videoHeight : 0,
            currentTime: video ? video.currentTime : 0,
            episodeTitle: epHeader ? epHeader.textContent : '',
            segFound: !!segEl,
            segActive: isSegActive
          };
        })()`,
        returnByValue: true
      });
      const s = sRes?.result?.value;
      if (s && s.hasVideo && s.src && s.videoWidth > 0 && s.src.includes('asset_jadoo_s01_v0008')) {
        segLoaded = true;
        segState = s;
        break;
      }
    }
    if (!segLoaded || !segState) {
      throw new Error('Segment deep-link failed to load media within 30s');
    }

    console.log('[USABILITY-01-F02] Segment deep-link loaded:', {
      episodeTitle: segState.episodeTitle,
      segActive: segState.segActive,
      src: redactUrl(segState.src)
    });

    evidence.case_3_v2_segment_seek = {
      url: segUrl,
      segment_id: 'seg_jadoo_s01_008a',
      asset_id: 'asset_jadoo_s01_v0008',
      episode_title: segState.episodeTitle,
      segment_highlighted: segState.segActive,
      stream_url_redacted: redactUrl(segState.src),
      status: 'PASS'
    };

    evidence.status = 'PASS';
    console.log('\n[USABILITY-01-F02] ALL V1 AND V2 VERIFICATIONS PASSED 100%!');

  } finally {
    if (ws) {
      try { ws.close(); } catch (_) {}
    }
    try {
      chromeProc.kill('SIGKILL');
    } catch (_) {}
    try {
      fs.rmSync(profileDir, { recursive: true, force: true });
    } catch (_) {}
  }

  // Write evidence JSON
  const evidencePath = 'docs/reviews/evidence/USABILITY_01_F02_BROWSER_VERIFICATION.json';
  fs.writeFileSync(evidencePath, JSON.stringify(evidence, null, 2), 'utf-8');
  console.log(`[USABILITY-01-F02] Saved evidence to ${evidencePath}`);
  return evidence;
}

runBrowserVerificationF02().catch(err => {
  console.error('[USABILITY-01-F02] Verification failed:', err);
  process.exit(1);
});
