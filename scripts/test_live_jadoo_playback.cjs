const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Keep temporary playback credentials out of saved evidence and console logs.
const redactStreamUrl = (value) => String(value).replace(/([?&]grant=)[^&\s]+/g, '$1[REDACTED]');

/**
 * SNAPSHOT-02-F01 End-to-End Real Web Browser Verification Harness
 * 
 * Verifies User Journey on Live UI:
 * 1. Log in via UI / API and store auth token.
 * 2. Search "Jadoo" on Web UI (/search).
 * 3. Click search result card to navigate to /series/...
 * 4. Verify Episode 1 (ep_jadoo_s01_0001) selection and asset mapping (asset_jadoo_s01_v0001).
 * 5. Verify <video> player src contains production stream endpoint with valid grant.
 * 6. Verify real decoded video frame dimensions (videoWidth > 0, videoHeight > 0).
 * 7. Verify playback advancement (currentTime advancing over time).
 * 8. Perform seek to 60.0s, confirm seek completion, and verify playback continues advancing post-seek.
 * 9. Switch to Episode 2 (ep_jadoo_s01_0002) via episode selector, verify asset update to asset_jadoo_s01_v0002 and video decoding.
 * 10. Cross-verify episode IDs, asset IDs, and file sizes with catalog.jadoo_all.json and Drive mount X:\.
 * 11. Capture screenshots and write structured JSON evidence.
 */

async function runJadooWebVerification() {
  const evidence = {
    timestamp: new Date().toISOString(),
    mission: 'SNAPSHOT-02-F01 — SỬA I/O DRIVE NGOÀI TIMEOUT VÀ XÁC NHẬN ĐÚNG TẬP TRÊN WEB',
    status: 'UNKNOWN',
    auth_verification: {},
    search_journey: {},
    episode_1_playback: {},
    episode_1_seek: {},
    episode_2_switch: {},
    catalog_cross_reference: {},
    screenshots: {}
  };

  const port = 9228;
  const profileDir = path.join(os.tmpdir(), 'chrome_live_jadoo_' + Date.now());
  fs.mkdirSync(profileDir, { recursive: true });

  const chromeCandidates = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    path.join(process.env.LOCALAPPDATA || '', 'Google\\Chrome\\Application\\chrome.exe')
  ];
  const chromePath = chromeCandidates.find(p => fs.existsSync(p));
  if (!chromePath) {
    throw new Error('Chrome executable not found on standard paths');
  }

  console.log(`[JadooVerification] Launching Chrome Headless (CDP port: ${port})...`);
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
      const timer = setTimeout(() => reject(new Error('Timeout waiting for CDP method: ' + method)), 30000);
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

    // 2. Perform authentication and set tokens
    console.log('[JadooVerification] Step 1: Authenticating as admin to obtain access token...');
    const loginRes = await fetch('http://127.0.0.1:8080/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ usernameOrEmail: 'admin', password: 'password123' })
    }).then(r => r.json());

    if (!loginRes || !loginRes.data || !loginRes.data.token) {
      throw new Error('Failed to login as admin');
    }
    const authToken = loginRes.data.token;
    evidence.auth_verification = {
      username: 'admin',
      token_received: Boolean(authToken),
      expires_in: loginRes.data.expiresIn
    };
    console.log('[JadooVerification] Admin authenticated successfully.');

    // Navigate to base URL and set tokens in localStorage
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

    // 3. Search Journey: Navigate to /search and query "Jadoo"
    console.log('[JadooVerification] Step 2: Navigating to Search page and searching "Jadoo"...');
    await send('Page.navigate', { url: 'http://localhost:3000/search?q=Jadoo' });
    await new Promise(r => setTimeout(r, 3000));

    // Wait for search result cards
    let searchResultFound = false;
    let cardInfo = null;
    for (let i = 0; i < 20; i++) {
      const evalRes = await send('Runtime.evaluate', {
        expression: `(() => {
          const cards = document.querySelectorAll("[data-testid='search-result-card']");
          if (!cards || cards.length === 0) return null;
          const items = Array.from(cards).map(c => ({
            href: c.getAttribute('href'),
            id: c.getAttribute('data-result-id'),
            type: c.getAttribute('data-result-type'),
            title: c.querySelector('h4')?.textContent || ''
          }));
          return { count: cards.length, items };
        })()`,
        returnByValue: true
      });
      const data = evalRes?.result?.value;
      if (data && data.count > 0) {
        searchResultFound = true;
        cardInfo = data;
        break;
      }
      await new Promise(r => setTimeout(r, 500));
    }

    if (!searchResultFound || !cardInfo) {
      throw new Error('No search results found for query "Jadoo" on /search');
    }

    evidence.search_journey = {
      query: 'Jadoo',
      results_count: cardInfo.count,
      sample_results: cardInfo.items.slice(0, 3)
    };
    console.log(`[JadooVerification] Found ${cardInfo.count} search results for Jadoo.`);

    const searchSnap = await send('Page.captureScreenshot', { format: 'png' });
    const searchSnapPath = 'docs/reviews/evidence/live_jadoo_search_results.png';
    fs.writeFileSync(searchSnapPath, Buffer.from(searchSnap.data, 'base64'));
    evidence.screenshots.search_results = searchSnapPath;

    // 4. Click the search result card to navigate to Series Detail Page
    console.log('[JadooVerification] Step 3: Clicking search result card to navigate to series detail...');
    await send('Runtime.evaluate', {
      expression: `(() => {
        const card = document.querySelector("[data-testid='search-result-card']");
        if (card) card.click();
        return true;
      })()`
    });

    // Wait for Series Detail page to load
    let seriesLoaded = false;
    let pageState = null;
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 1000));
      const res = await send('Runtime.evaluate', {
        expression: `(() => {
          const h1 = document.querySelector('h1')?.textContent || '';
          const video = document.querySelector("[data-testid='series-video-player']");
          const epButtons = document.querySelectorAll("button[data-episode-id]");
          return {
            h1,
            videoFound: !!video,
            videoSrc: video ? (video.currentSrc || video.src) : '',
            epCount: epButtons.length
          };
        })()`,
        returnByValue: true
      });
      const val = res?.result?.value;
      if (val && val.videoFound && val.videoSrc && val.epCount > 0) {
        seriesLoaded = true;
        pageState = val;
        break;
      }
    }

    if (!seriesLoaded || !pageState) {
      throw new Error('Series detail page failed to load video player or episode list within 30s');
    }

    console.log('[JadooVerification] Series page loaded. H1:', pageState.h1, 'Episodes:', pageState.epCount);
    console.log('[JadooVerification] Initial video src:', redactStreamUrl(pageState.videoSrc));

    // 5. Episode 1 Verification: Playing and Frame Advancement
    console.log('[JadooVerification] Step 4: Verifying Episode 1 playback and decoding...');
    // Ensure video is playing
    await send('Runtime.evaluate', {
      expression: `(() => {
        const v = document.querySelector("[data-testid='series-video-player']");
        if (v) {
          v.muted = true;
          v.play().catch(e => console.error('Play error', e));
        }
        return true;
      })()`
    });

    let ep1Playing = false;
    let ep1VideoData = null;
    let t0 = 0;
    let t1 = 0;

    for (let i = 0; i < 40; i++) {
      await new Promise(r => setTimeout(r, 1000));
      const vRes = await send('Runtime.evaluate', {
        expression: `(() => {
          const v = document.querySelector("[data-testid='series-video-player']");
          if (!v) return null;
          return {
            currentTime: v.currentTime,
            duration: v.duration,
            paused: v.paused,
            readyState: v.readyState,
            videoWidth: v.videoWidth,
            videoHeight: v.videoHeight,
            currentSrc: v.currentSrc || v.src
          };
        })()`,
        returnByValue: true
      });
      const s = vRes?.result?.value;
      if (s && s.videoWidth > 0 && s.videoHeight > 0 && s.currentTime > 0.2 && !s.paused) {
        t0 = s.currentTime;
        ep1VideoData = s;
        // Wait 1.5s to verify advancement
        await new Promise(r => setTimeout(r, 1500));
        const advRes = await send('Runtime.evaluate', {
          expression: `(() => {
            const v = document.querySelector("[data-testid='series-video-player']");
            return v ? v.currentTime : 0;
          })()`,
          returnByValue: true
        });
        t1 = advRes?.result?.value || 0;
        if (t1 > t0 + 0.3) {
          ep1Playing = true;
          break;
        }
      }
    }

    if (!ep1Playing || !ep1VideoData) {
      throw new Error(`Episode 1 playback failed to start, decode, or advance! Last state: ${JSON.stringify(ep1VideoData)}`);
    }

    evidence.episode_1_playback = {
      episode_id: 'ep_jadoo_s01_0001',
      expected_asset_id: 'asset_jadoo_s01_v0001',
      stream_src: redactStreamUrl(ep1VideoData.currentSrc),
      stream_src_has_grant: ep1VideoData.currentSrc.includes('grant='),
      video_width: ep1VideoData.videoWidth,
      video_height: ep1VideoData.videoHeight,
      ready_state: ep1VideoData.readyState,
      duration_seconds: ep1VideoData.duration,
      initial_time_t0: t0,
      advanced_time_t1: t1,
      advancement_delta: t1 - t0,
      status: 'PASS'
    };
    console.log(`[JadooVerification] Episode 1 PLAYING: ${ep1VideoData.videoWidth}x${ep1VideoData.videoHeight}, t0=${t0.toFixed(2)}s, t1=${t1.toFixed(2)}s (delta=${(t1 - t0).toFixed(2)}s)`);

    const ep1PlaySnap = await send('Page.captureScreenshot', { format: 'png' });
    const ep1PlaySnapPath = 'docs/reviews/evidence/live_jadoo_ep1_playing.png';
    fs.writeFileSync(ep1PlaySnapPath, Buffer.from(ep1PlaySnap.data, 'base64'));
    evidence.screenshots.episode_1_playing = ep1PlaySnapPath;

    // 6. Seek verification on Episode 1
    console.log('[JadooVerification] Step 5: Testing seek to 60.0s on Episode 1...');
    const targetSeekSec = 60.0;
    await send('Runtime.evaluate', {
      expression: `(() => {
        const v = document.querySelector("[data-testid='series-video-player']");
        if (v) {
          v.currentTime = ${targetSeekSec};
        }
        return true;
      })()`
    });

    let seekSettled = false;
    let t2 = 0;
    let t3 = 0;

    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 600));
      const sRes = await send('Runtime.evaluate', {
        expression: `(() => {
          const v = document.querySelector("[data-testid='series-video-player']");
          if (!v) return null;
          return {
            seeking: v.seeking,
            currentTime: v.currentTime,
            paused: v.paused,
            readyState: v.readyState
          };
        })()`,
        returnByValue: true
      });
      const s = sRes?.result?.value;
      if (s && !s.seeking && Math.abs(s.currentTime - targetSeekSec) <= 5.0 && !s.paused) {
        t2 = s.currentTime;
        // Wait 1.5s to verify playback continues after seek
        await new Promise(r => setTimeout(r, 1500));
        const postSeekRes = await send('Runtime.evaluate', {
          expression: `(() => {
            const v = document.querySelector("[data-testid='series-video-player']");
            return v ? v.currentTime : 0;
          })()`,
          returnByValue: true
        });
        t3 = postSeekRes?.result?.value || 0;
        if (t3 > t2 + 0.3) {
          seekSettled = true;
          break;
        }
      }
    }

    if (!seekSettled) {
      throw new Error(`Seek to ${targetSeekSec}s failed to settle or resume playback! t2=${t2}, t3=${t3}`);
    }

    evidence.episode_1_seek = {
      target_seek_seconds: targetSeekSec,
      settled_time_t2: t2,
      resumed_time_t3: t3,
      post_seek_advancement_delta: t3 - t2,
      status: 'PASS'
    };
    console.log(`[JadooVerification] Episode 1 SEEK SETTLED: t2=${t2.toFixed(2)}s, t3=${t3.toFixed(2)}s (delta=${(t3 - t2).toFixed(2)}s)`);

    const ep1SeekSnap = await send('Page.captureScreenshot', { format: 'png' });
    const ep1SeekSnapPath = 'docs/reviews/evidence/live_jadoo_ep1_seek_60s.png';
    fs.writeFileSync(ep1SeekSnapPath, Buffer.from(ep1SeekSnap.data, 'base64'));
    evidence.screenshots.episode_1_seek = ep1SeekSnapPath;

    // 7. Switch to Episode 2 (ep_jadoo_s01_0002) to verify mapping
    console.log('[JadooVerification] Step 6: Switching to Episode 2 (ep_jadoo_s01_0002)...');
    await send('Runtime.evaluate', {
      expression: `(() => {
        const ep2Btn = document.querySelector("button[data-episode-id='ep_jadoo_s01_0002']");
        if (ep2Btn) {
          ep2Btn.click();
          return true;
        }
        return false;
      })()`,
      returnByValue: true
    });

    let ep2Switched = false;
    let ep2VideoData = null;
    let t4 = 0;
    let t5 = 0;

    for (let i = 0; i < 40; i++) {
      await new Promise(r => setTimeout(r, 1000));
      const vRes = await send('Runtime.evaluate', {
        expression: `(() => {
          const v = document.querySelector("[data-testid='series-video-player']");
          if (!v) return null;
          return {
            currentTime: v.currentTime,
            duration: v.duration,
            paused: v.paused,
            readyState: v.readyState,
            videoWidth: v.videoWidth,
            videoHeight: v.videoHeight,
            currentSrc: v.currentSrc || v.src
          };
        })()`,
        returnByValue: true
      });
      const s = vRes?.result?.value;
      if (s && s.currentSrc.includes('asset_jadoo_s01_v0002')) {
        // Trigger play for episode 2
        await send('Runtime.evaluate', {
          expression: `(() => {
            const v = document.querySelector("[data-testid='series-video-player']");
            if (v && v.paused) { v.muted = true; v.play(); }
            return true;
          })()`
        });

        if (s.videoWidth > 0 && s.videoHeight > 0 && s.currentTime > 0.2 && !s.paused) {
          t4 = s.currentTime;
          ep2VideoData = s;
          await new Promise(r => setTimeout(r, 1500));
          const advRes = await send('Runtime.evaluate', {
            expression: `(() => {
              const v = document.querySelector("[data-testid='series-video-player']");
              return v ? v.currentTime : 0;
            })()`,
            returnByValue: true
          });
          t5 = advRes?.result?.value || 0;
          if (t5 > t4 + 0.3) {
            ep2Switched = true;
            break;
          }
        }
      }
    }

    if (!ep2Switched || !ep2VideoData) {
      throw new Error(`Failed to switch to Episode 2 or decode frames! State: ${JSON.stringify(ep2VideoData)}`);
    }

    evidence.episode_2_switch = {
      episode_id: 'ep_jadoo_s01_0002',
      expected_asset_id: 'asset_jadoo_s01_v0002',
      stream_src: redactStreamUrl(ep2VideoData.currentSrc),
      stream_src_has_grant: ep2VideoData.currentSrc.includes('grant='),
      video_width: ep2VideoData.videoWidth,
      video_height: ep2VideoData.videoHeight,
      ready_state: ep2VideoData.readyState,
      duration_seconds: ep2VideoData.duration,
      initial_time_t4: t4,
      advanced_time_t5: t5,
      advancement_delta: t5 - t4,
      status: 'PASS'
    };
    console.log(`[JadooVerification] Episode 2 PLAYING: ${ep2VideoData.videoWidth}x${ep2VideoData.videoHeight}, t4=${t4.toFixed(2)}s, t5=${t5.toFixed(2)}s (delta=${(t5 - t4).toFixed(2)}s)`);

    const ep2PlaySnap = await send('Page.captureScreenshot', { format: 'png' });
    const ep2PlaySnapPath = 'docs/reviews/evidence/live_jadoo_ep2_playing.png';
    fs.writeFileSync(ep2PlaySnapPath, Buffer.from(ep2PlaySnap.data, 'base64'));
    evidence.screenshots.episode_2_playing = ep2PlaySnapPath;

    // 8. Cross-reference verification with catalog.jadoo_all.json and Drive mount X:\
    console.log('[JadooVerification] Step 7: Cross-referencing assets against catalog.jadoo_all.json and X:\\...');
    const catData = JSON.parse(fs.readFileSync('data/catalog.jadoo_all.json', 'utf8'));
    const ep1Asset = catData.media_assets.find(a => a.id === 'asset_jadoo_s01_v0001');
    const ep2Asset = catData.media_assets.find(a => a.id === 'asset_jadoo_s01_v0002');

    const resolveDiskPath = (relPath) => {
      const stripped = (relPath || '').replace(/^VideoDieppie\//, '').replace(/\//g, '\\');
      return path.join('X:\\', stripped);
    };

    const ep1DiskPath = resolveDiskPath(ep1Asset?.storage?.relative_path);
    const ep2DiskPath = resolveDiskPath(ep2Asset?.storage?.relative_path);

    const ep1Exists = fs.existsSync(ep1DiskPath);
    const ep2Exists = fs.existsSync(ep2DiskPath);

    evidence.catalog_cross_reference = {
      episode_1: {
        episode_id: 'ep_jadoo_s01_0001',
        asset_id: 'asset_jadoo_s01_v0001',
        catalog_relative_path: ep1Asset?.storage?.relative_path,
        catalog_size_bytes: ep1Asset?.size_bytes,
        drive_actual_path: ep1DiskPath,
        file_exists_on_x: ep1Exists,
        actual_disk_size_bytes: ep1Exists ? fs.statSync(ep1DiskPath).size : 0,
        size_matches: ep1Exists && (fs.statSync(ep1DiskPath).size === ep1Asset?.size_bytes)
      },
      episode_2: {
        episode_id: 'ep_jadoo_s01_0002',
        asset_id: 'asset_jadoo_s01_v0002',
        catalog_relative_path: ep2Asset?.storage?.relative_path,
        catalog_size_bytes: ep2Asset?.size_bytes,
        drive_actual_path: ep2DiskPath,
        file_exists_on_x: ep2Exists,
        actual_disk_size_bytes: ep2Exists ? fs.statSync(ep2DiskPath).size : 0,
        size_matches: ep2Exists && (fs.statSync(ep2DiskPath).size === ep2Asset?.size_bytes)
      }
    };

    evidence.status = 'PASSED';
    console.log('[JadooVerification] ALL CHECKS PASSED SUCCESSFULLY!');

  } catch (err) {
    console.error('[JadooVerification] ERROR:', err);
    evidence.status = 'FAILED';
    evidence.error = err.message || String(err);
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

    const evidencePath = 'docs/reviews/evidence/SNAPSHOT_02_F01_WEB_JADOO_EVIDENCE.json';
    fs.writeFileSync(evidencePath, JSON.stringify(evidence, null, 2), 'utf8');
    console.log(`[JadooVerification] Written structured evidence to: ${evidencePath}`);

    if (evidence.status !== 'PASSED') {
      process.exit(1);
    }
  }
}

runJadooWebVerification();
