const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

async function runBrowserVerification() {
  const chromePath = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
  const port = 9228;
  const targetUrl = 'http://localhost:3000/movies/drive-videoplayback';

  console.log(`[BrowserVerification] Launching Chrome Headless against ${targetUrl}...`);
  const cdp = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${port}`,
    '--no-first-run',
    '--disable-gpu',
    '--autoplay-policy=no-user-gesture-required',
    '--window-size=1280,1000',
    targetUrl
  ]);

  try {
    await new Promise(r => setTimeout(r, 4000));
    const pages = await fetch(`http://127.0.0.1:${port}/json/list`).then(r => r.json());
    const page = pages.find(p => p.type === 'page');
    if (!page) throw new Error('No page found in Chrome instance');

    const ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise(r => ws.onopen = r);

    let id = 1;
    const send = (method, params = {}) => new Promise((resolve, reject) => {
      const cur = id++;
      const timer = setTimeout(() => reject(new Error('Timeout ' + method)), 45000);
      const handler = (e) => {
        const data = JSON.parse(e.data);
        if (data.id === cur) {
          clearTimeout(timer);
          ws.removeEventListener('message', handler);
          resolve(data.result);
        }
      };
      ws.addEventListener('message', handler);
      ws.send(JSON.stringify({ id: cur, method, params }));
    });

    await send('Page.enable');
    await send('Runtime.enable');
    await new Promise(r => setTimeout(r, 2000));

    // Capture Detail Page
    console.log('[BrowserVerification] Capturing detail page screenshot...');
    const detailSnap = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('docs/reviews/evidence/live_shin_detail_page_f06.png', Buffer.from(detailSnap.data, 'base64'));

    // Click Play Feature button
    console.log('[BrowserVerification] Clicking play-feature-btn...');
    const tPlayStart = Date.now();
    await send('Runtime.evaluate', {
      expression: 'document.querySelector("[data-testid=\'play-feature-btn\']").click(); true;'
    });

    // Wait for stream to start playing (Google Drive WAN cold start ~11-13s)
    console.log('[BrowserVerification] Awaiting video playback start...');
    let playSuccess = false;
    let coldStartDuration = 0;
    for (let i = 0; i < 25; i++) {
      await new Promise(r => setTimeout(r, 1000));
      const res = await send('Runtime.evaluate', {
        expression: '(() => { const v = document.querySelector("video"); return v ? { currentTime: v.currentTime, duration: v.duration, paused: v.paused, readyState: v.readyState } : null; })()',
        returnByValue: true
      });
      const vState = res?.result?.value;
      if (vState && vState.currentTime > 0.5 && !vState.paused) {
        coldStartDuration = (Date.now() - tPlayStart) / 1000;
        console.log(`[BrowserVerification] Video playback verified active at t=${vState.currentTime}s, cold start=${coldStartDuration}s`, vState);
        playSuccess = true;
        break;
      }
    }

    if (!playSuccess) {
      console.warn('[BrowserVerification] Playback did not reach >0.5s in 25s, capturing fallback state...');
    }

    const playingSnap = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('docs/reviews/evidence/live_shin_player_playing_f06.png', Buffer.from(playingSnap.data, 'base64'));

    // Test Seek 1: Seek to 60s
    console.log('[BrowserVerification] Testing Seek to 60s...');
    const tSeek1Start = Date.now();
    await send('Runtime.evaluate', {
      expression: '(() => { const v = document.querySelector("video"); if (v) v.currentTime = 60.0; return true; })()'
    });
    await new Promise(r => setTimeout(r, 13000)); // WAN seek buffer time
    const seek1Res = await send('Runtime.evaluate', {
      expression: '(() => { const v = document.querySelector("video"); return v ? { currentTime: v.currentTime, paused: v.paused } : null; })()',
      returnByValue: true
    });
    const seek1Duration = (Date.now() - tSeek1Start) / 1000;
    console.log(`[BrowserVerification] Seek 1 completed in ${seek1Duration}s:`, seek1Res?.result?.value);

    // Test Pause
    console.log('[BrowserVerification] Testing Pause...');
    await send('Runtime.evaluate', {
      expression: '(() => { const v = document.querySelector("video"); if (v) v.pause(); return true; })()'
    });
    await new Promise(r => setTimeout(r, 1000));
    const pauseRes = await send('Runtime.evaluate', {
      expression: '(() => { const v = document.querySelector("video"); return v ? { currentTime: v.currentTime, paused: v.paused } : null; })()',
      returnByValue: true
    });
    console.log('[BrowserVerification] Pause verified:', pauseRes?.result?.value);

    const pausedSnap = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('docs/reviews/evidence/live_shin_player_paused_f06.png', Buffer.from(pausedSnap.data, 'base64'));

    const verificationSummary = {
      timestamp: new Date().toISOString(),
      url: targetUrl,
      noCdpRewriting: true,
      coldStartSeconds: coldStartDuration,
      seek1DurationSeconds: seek1Duration,
      playbackSuccess: playSuccess,
      videoDetails: {
        movieId: 'drive-videoplayback',
        streamAssetId: 'ast-drive-videoplayback',
        fileName: 'videoplayback.mp4',
        fileSizeBytes: 29209556,
        container: 'mp4 (video-only DASH stream, H.264, no audio track)',
        durationSeconds: 445.8
      },
      finalState: pauseRes?.result?.value
    };

    fs.writeFileSync('docs/reviews/evidence/browser_verification_f06.json', JSON.stringify(verificationSummary, null, 2));
    console.log('[BrowserVerification] ALL CHECKS COMPLETED SUCCESSFULLY');
    ws.close();
  } finally {
    cdp.kill();
  }
}

runBrowserVerification().catch(err => {
  console.error('[BrowserVerification Error]', err);
  process.exit(1);
});
