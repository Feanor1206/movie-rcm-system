#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const EPISODES = [
  { id: 'ep_jadoo_s01_0001', assetId: 'asset_jadoo_s01_v0001', label: 'episode-1' },
  { id: 'ep_jadoo_s01_0002', assetId: 'asset_jadoo_s01_v0002', label: 'episode-2' },
];
const DEFAULT_OUTPUT_DIR = path.resolve(process.cwd(), 'target', 'preview-restart-evidence');
const REQUEST_TIMEOUT_MS = 12_000;

function parseArgs(argv) {
  const options = { phase: '', outputDir: DEFAULT_OUTPUT_DIR, port: 9337, baseUrl: 'http://127.0.0.1:3000' };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--phase') options.phase = argv[++i] || '';
    else if (arg === '--output-dir') options.outputDir = path.resolve(argv[++i] || '');
    else if (arg === '--port') options.port = Number(argv[++i]);
    else if (arg === '--base-url') options.baseUrl = argv[++i] || options.baseUrl;
    else if (arg === '--help') {
      console.log('Usage: node scripts/verify_preview_restart.cjs --phase before|after [--output-dir DIR] [--port 9337] [--base-url URL]');
      process.exit(0);
    } else {
      throw new Error(`Unknown option: ${arg}`);
    }
  }
  if (!['before', 'after'].includes(options.phase)) throw new Error('--phase must be before or after');
  if (!Number.isInteger(options.port) || options.port < 1 || options.port > 65535) throw new Error('--port must be a valid TCP port');
  const base = new URL(options.baseUrl);
  if (!['http:', 'https:'].includes(base.protocol)) throw new Error('--base-url must use http or https');
  options.baseUrl = base.origin;
  return options;
}

function redact(value) {
  return String(value ?? '')
    .replace(/([?&](?:grant|token|access_token|id_token)=)[^&#\s]*/gi, '$1[REDACTED]')
    .replace(/(Bearer\s+)[^\s]*/gi, '$1[REDACTED]');
}

function safeError(error) {
  return redact(error?.message || error || 'Unknown failure').slice(0, 1200);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

class CdpClient {
  constructor(url) {
    this.url = url;
    this.nextId = 1;
    this.pending = new Map();
    this.ws = null;
  }

  async connect() {
    if (typeof WebSocket !== 'function') throw new Error('Node.js WebSocket is unavailable; use Node.js 22 or newer');
    this.ws = new WebSocket(this.url);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Timed out connecting to Chrome CDP')), REQUEST_TIMEOUT_MS);
      this.ws.addEventListener('open', () => { clearTimeout(timer); resolve(); }, { once: true });
      this.ws.addEventListener('error', () => { clearTimeout(timer); reject(new Error('Could not connect to Chrome CDP')); }, { once: true });
    });
    this.ws.addEventListener('message', (event) => {
      let message;
      try { message = JSON.parse(String(event.data)); } catch { return; }
      if (!message.id || !this.pending.has(message.id)) return;
      const { resolve, reject, timer } = this.pending.get(message.id);
      clearTimeout(timer);
      this.pending.delete(message.id);
      if (message.error) reject(new Error(`Chrome CDP command failed: ${message.error.message || 'unknown error'}`));
      else resolve(message.result || {});
    });
    this.ws.addEventListener('close', () => {
      for (const { reject, timer } of this.pending.values()) {
        clearTimeout(timer);
        reject(new Error('Chrome CDP connection closed'));
      }
      this.pending.clear();
    });
  }

  request(method, params = {}, sessionId) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return Promise.reject(new Error('Chrome CDP is not connected'));
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Chrome CDP timed out: ${method}`));
      }, REQUEST_TIMEOUT_MS);
      this.pending.set(id, { resolve, reject, timer });
      this.ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    });
  }

  close() {
    try { this.ws?.close(); } catch { /* best-effort transport cleanup */ }
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  fs.mkdirSync(options.outputDir, { recursive: true });

  const evidence = {
    phase: options.phase,
    status: 'RUNNING',
    startedAt: new Date().toISOString(),
    frontend: options.baseUrl,
    browser: { cdpPort: options.port, isolatedContext: true, authentication: 'guest' },
    checks: [],
    episodes: EPISODES.map((episode) => ({ episodeId: episode.id, assetId: episode.assetId })),
    screenshots: {},
  };
  const evidencePath = path.join(options.outputDir, `preview-restart-${options.phase}.json`);
  let cdp;
  let browserContextId;
  let targetId;
  let pageSessionId;

  const check = (name, detail) => evidence.checks.push({ name, ...detail });
  const evaluate = async (expression) => {
    const response = await cdp.request('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
      userGesture: true,
    }, pageSessionId);
    if (response.exceptionDetails) throw new Error(`Page evaluation failed (${response.exceptionDetails.text || 'exception'})`);
    return response.result?.value;
  };
  const waitFor = async (name, expression, predicate, timeoutMs = 45_000) => {
    const end = Date.now() + timeoutMs;
    let last;
    while (Date.now() < end) {
      last = await evaluate(expression);
      if (predicate(last)) return last;
      await sleep(400);
    }
    throw new Error(`Timed out waiting for ${name}${last ? ` (${JSON.stringify(last)})` : ''}`);
  };
  const screenshot = async (name) => {
    if (name.includes('episode')) await evaluate(`document.querySelector('[data-testid="series-video-player"]')?.scrollIntoView({block:'center'})`);
    const result = await cdp.request('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }, pageSessionId);
    const file = path.join(options.outputDir, `preview-restart-${options.phase}-${name}.png`);
    fs.writeFileSync(file, Buffer.from(result.data, 'base64'));
    evidence.screenshots[name] = file;
  };
  const playerState = () => evaluate(`(() => {
    const v = document.querySelector('[data-testid="series-video-player"]');
    return v ? { currentSrc: v.currentSrc || v.src, currentTime: v.currentTime, duration: v.duration,
      paused: v.paused, seeking: v.seeking, readyState: v.readyState, videoWidth: v.videoWidth, videoHeight: v.videoHeight } : null;
  })()`);

  try {
    const versionResponse = await fetch(`http://127.0.0.1:${options.port}/json/version`, { signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) });
    if (!versionResponse.ok) throw new Error(`Chrome CDP returned HTTP ${versionResponse.status}`);
    const version = await versionResponse.json();
    if (!version.webSocketDebuggerUrl) throw new Error('Chrome CDP did not provide a browser WebSocket URL');
    cdp = new CdpClient(version.webSocketDebuggerUrl);
    await cdp.connect();

    const context = await cdp.request('Target.createBrowserContext', { disposeOnDetach: true });
    browserContextId = context.browserContextId;
    if (!browserContextId) throw new Error('Chrome did not create an isolated browser context');
    const target = await cdp.request('Target.createTarget', { url: 'about:blank', browserContextId });
    targetId = target.targetId;
    if (!targetId) throw new Error('Chrome did not create a test page in the isolated context');
    const attached = await cdp.request('Target.attachToTarget', { targetId, flatten: true });
    pageSessionId = attached.sessionId;
    await cdp.request('Page.enable', {}, pageSessionId);
    await cdp.request('Runtime.enable', {}, pageSessionId);
    await cdp.request('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false }, pageSessionId);

    await cdp.request('Page.navigate', { url: `${options.baseUrl}/` }, pageSessionId);
    const authState = await waitFor('guest homepage', `(() => ({
      ready: document.readyState !== 'loading',
      title: document.title,
      authStorageKeys: Object.keys(localStorage).filter((key) => /token|auth/i.test(key)),
      authCookieNames: document.cookie.split(';').map((part) => part.split('=')[0].trim()).filter((key) => /token|auth/i.test(key))
    }))()`, (state) => state?.ready && Boolean(state.title));
    if (authState.authStorageKeys.length || authState.authCookieNames.length) throw new Error('Isolated browser context unexpectedly contains authentication state');
    check('guest-context', { status: 'PASS', authStorageKeys: authState.authStorageKeys.length, authCookies: authState.authCookieNames.length });

    await cdp.request('Runtime.evaluate', {
      expression: `(() => {
        const link = document.querySelector('a[href="/search"]');
        if (!link) return false;
        link.click();
        return true;
      })()`, returnByValue: true, userGesture: true,
    }, pageSessionId);
    await waitFor('search route', 'location.pathname', (pathname) => pathname === '/search');
    const inputResult = await evaluate(`(() => {
      const input = document.querySelector('[data-testid="search-query-input"]');
      if (!input) return false;
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      setter.call(input, 'Jadoo');
      input.dispatchEvent(new Event('input', { bubbles: true }));
      return true;
    })()`);
    if (!inputResult) throw new Error('Search input was not available on the search page');
    const searchResult = await waitFor('Jadoo search result', `(() => Array.from(document.querySelectorAll('[data-testid="search-result-card"]')).map((card) => ({
      id: card.getAttribute('data-result-id'), type: card.getAttribute('data-result-type'), title: card.querySelector('h4')?.textContent?.trim() || ''
    })))()`, (items) => Array.isArray(items) && items.some((item) => item.id === 'ser_jadoo' && item.type === 'series'));
    check('guest-search', { status: 'PASS', query: 'Jadoo', resultCount: searchResult.length, seriesId: 'ser_jadoo' });
    await screenshot('search');

    const clickedSeries = await evaluate(`(() => {
      const card = document.querySelector('[data-testid="search-result-card"][data-result-id="ser_jadoo"][data-result-type="series"]');
      if (!card) return false;
      card.click();
      return true;
    })()`);
    if (!clickedSeries) throw new Error('Jadoo series result could not be selected');
    await waitFor('Jadoo series route', 'location.pathname', (pathname) => pathname === '/series/ser_jadoo');
    await waitFor('Jadoo season 1 button', `document.querySelector('[data-season-id="sea_jadoo_s01"]')?.getAttribute('data-season-id') || ''`, (id) => id === 'sea_jadoo_s01');
    const seasonClicked = await evaluate(`(() => {
      const button = document.querySelector('[data-season-id="sea_jadoo_s01"]');
      if (!button) return false;
      button.click();
      return true;
    })()`);
    if (!seasonClicked) throw new Error('Jadoo season 1 could not be selected');
    await waitFor('Jadoo season 1 selected', `document.querySelector('[data-season-id="sea_jadoo_s01"]')?.getAttribute('aria-pressed') || ''`, (pressed) => pressed === 'true');
    check('season-selection', { status: 'PASS', seriesId: 'ser_jadoo', seasonId: 'sea_jadoo_s01' });
    await waitFor('episode 1 button', `document.querySelector('[data-episode-id="${EPISODES[0].id}"]')?.getAttribute('data-episode-id') || ''`, (id) => id === EPISODES[0].id);

    async function selectEpisode(episode) {
      const clicked = await evaluate(`(() => {
        const button = document.querySelector('[data-episode-id="${episode.id}"]');
        if (!button) return false;
        button.click();
        return true;
      })()`);
      if (!clicked) throw new Error(`Episode ${episode.id} could not be selected`);
      await waitFor(`${episode.id} selected`, `document.querySelector('[data-episode-id="${episode.id}"]')?.getAttribute('aria-pressed') || ''`, (pressed) => pressed === 'true');
      await waitFor(`${episode.assetId} media mapping`, `(() => {
        const button = document.querySelector('[data-testid="media-asset-button"][data-asset-id="${episode.assetId}"]');
        const video = document.querySelector('[data-testid="series-video-player"]');
        return { assetButton: Boolean(button), currentSrc: video?.currentSrc || video?.src || '' };
      })()`, (value) => value?.assetButton && value.currentSrc.includes(episode.assetId), 60_000);
      const started = await evaluate(`(async () => {
        const v = document.querySelector('[data-testid="series-video-player"]');
        if (!v) return false;
        v.muted = true;
        try { await v.play(); return true; } catch { return false; }
      })()`);
      if (!started) throw new Error(`${episode.id} could not start playback`);
      const decoded = await waitFor(`${episode.id} decoded playback`, `(() => {
        const v = document.querySelector('[data-testid="series-video-player"]');
        return v ? { currentSrc: v.currentSrc || v.src, currentTime: v.currentTime, duration: v.duration,
          paused: v.paused, readyState: v.readyState, videoWidth: v.videoWidth, videoHeight: v.videoHeight } : null;
      })()`, (value) => value && value.currentSrc.includes(episode.assetId) && value.videoWidth > 0 && value.videoHeight > 0
        && value.currentTime > 0.1 && !value.paused, 90_000);
      const before = decoded.currentTime;
      await sleep(1200);
      const after = await playerState();
      if (!after || after.currentTime <= before + 0.2) throw new Error(`${episode.id} decoded but playback time did not advance`);
      check(`${episode.label}-playback`, {
        status: 'PASS', episodeId: episode.id, assetId: episode.assetId,
        currentSrc: (() => { const url = new URL(decoded.currentSrc); return redact(url.origin + url.pathname); })(),
        videoWidth: decoded.videoWidth, videoHeight: decoded.videoHeight, readyState: decoded.readyState,
        timeBefore: before, timeAfter: after.currentTime, advanceSeconds: after.currentTime - before,
      });
      return decoded;
    }

    await selectEpisode(EPISODES[0]);
    await screenshot('episode-1-playing');

    const pauseResult = await evaluate(`(() => { const v = document.querySelector('[data-testid="series-video-player"]'); if (!v) return false; v.pause(); return true; })()`);
    if (!pauseResult) throw new Error('Video element was not available to pause');
    await waitFor('pause', `document.querySelector('[data-testid="series-video-player"]')?.paused`, (paused) => paused === true, 5_000);
    await evaluate(`(() => { const v = document.querySelector('[data-testid="series-video-player"]'); if (!v) return false; v.muted = true; v.play().catch(() => {}); return true; })()`);
    await waitFor('resume', `document.querySelector('[data-testid="series-video-player"]')?.paused`, (paused) => paused === false, 8_000);
    const resumeStart = (await playerState()).currentTime;
    await sleep(1000);
    const resumed = await playerState();
    if (!resumed || resumed.currentTime <= resumeStart + 0.2) throw new Error('Playback did not advance after resume');
    check('pause-resume', { status: 'PASS', paused: true, resumed: true, timeBefore: resumeStart, timeAfter: resumed.currentTime });

    const targetSeekSeconds = Math.min(8, Math.max(1, (resumed.duration || 20) - 2));
    await evaluate(`(() => { const v = document.querySelector('[data-testid="series-video-player"]'); if (!v) return false; v.currentTime = ${targetSeekSeconds}; v.play().catch(() => {}); return true; })()`);
    const seeked = await waitFor('episode 1 seek settle', `(() => {
      const v = document.querySelector('[data-testid="series-video-player"]');
      return v ? { currentTime: v.currentTime, seeking: v.seeking, paused: v.paused } : null;
    })()`, (value) => value && !value.seeking && !value.paused && Math.abs(value.currentTime - targetSeekSeconds) <= 2.5, 20_000);
    await sleep(1100);
    const seekAdvanced = await playerState();
    if (!seekAdvanced || seekAdvanced.currentTime <= seeked.currentTime + 0.2) throw new Error('Episode 1 did not advance after seeking');
    check('episode-1-seek', { status: 'PASS', episodeId: EPISODES[0].id, assetId: EPISODES[0].assetId, targetSeconds: targetSeekSeconds, settledSeconds: seeked.currentTime, advancedSeconds: seekAdvanced.currentTime });
    await screenshot('episode-1-seek');

    await selectEpisode(EPISODES[1]);
    await screenshot('episode-2-playing');
    if (options.phase === 'before') {
      // Real decoder seeks, including the end of the Drive file; no synthetic video fixtures.
      const seekTargets = [60, 240, Math.max(1, (await playerState()).duration - 20)];
      for (const seconds of seekTargets) {
        await evaluate(`(() => { const v=document.querySelector('video'); v.currentTime=${seconds}; v.play().catch(()=>{}); })()`);
        const settled = await waitFor(`seek ${seconds}`, `(() => {const v=document.querySelector('video');return {t:v.currentTime,seeking:v.seeking,ready:v.readyState};})()`,
          v => !v.seeking && v.ready>=3 && Math.abs(v.t-seconds)<3, 35_000);
        await sleep(1000);
        const after = await playerState();
        if (after.currentTime <= settled.t+.2) throw new Error('Decoder did not advance after Drive seek');
        check('drive-file-seek', {status:'PASS', episodeId:EPISODES[1].id,targetSeconds:seconds,settledSeconds:settled.t,advancedSeconds:after.currentTime});
      }
      await evaluate(`(() => { const v=document.querySelector('video'); v.currentTime=60; v.play().catch(()=>{}); })()`);
      await waitFor('resume checkpoint', `document.querySelector('video')?.currentTime`, t=>t>=60 && t<65, 25_000);
      await sleep(1200);
      await evaluate(`document.querySelector('video').pause()`);
      const local = await evaluate(`JSON.parse(localStorage.getItem('dippie_guest_watch_progress_v1') || '[]')`);
      const saved = local.find(r=>r.episodeId===EPISODES[1].id);
      if (!saved || saved.assetId!==EPISODES[1].assetId || saved.positionMs<60000 || saved.completed) throw new Error('Guest progress did not save exact episode/file time');
      await cdp.request('Page.reload', {}, pageSessionId);
      await waitFor('explicit resume choice', `Boolean(document.querySelector('[data-testid="resume-choice"]'))`, Boolean, 45_000);
      await evaluate(`Array.from(document.querySelectorAll('[data-testid="resume-choice"] button')).find(b=>b.textContent==='Xem tiếp').click()`);
      await waitFor('resume exact file time', `(() => {const v=document.querySelector('video');return v?{t:v.currentTime,src:v.currentSrc,paused:v.paused}:null;})()`,
        v=>v && v.src.includes(EPISODES[1].assetId) && v.t>=59 && !v.paused,30_000);
      check('guest-resume-reload',{status:'PASS',episodeId:saved.episodeId,assetId:saved.assetId,positionMs:saved.positionMs});

      await selectEpisode(EPISODES[0]);
      await evaluate(`(() => { const box=document.querySelector('input[type="checkbox"]');if(!box.checked)box.click(); const v=document.querySelector('video');v.currentTime=v.duration-1.5;v.play().catch(()=>{}); })()`);
      await waitFor('next episode countdown', `Boolean(document.querySelector('[data-testid="next-countdown"]'))`,Boolean,35_000);
      await evaluate(`document.querySelector('[data-testid="next-countdown"] button').click()`);
      await sleep(1300);
      if (await evaluate(`Boolean(document.querySelector('[data-testid="next-countdown"]'))`)) throw new Error('Countdown cancel did not hold');
      check('auto-next-cancel',{status:'PASS'});
      await evaluate(`(() => {const v=document.querySelector('video');v.currentTime=v.duration-1.5;v.play().catch(()=>{});})()`);
      await waitFor('automatic episode 2', `document.querySelector('[data-episode-id="${EPISODES[1].id}"]')?.getAttribute('aria-pressed')`,v=>v==='true',40_000);
      await waitFor('automatic episode 2 decoder', `(() => {const v=document.querySelector('video');return v?{t:v.currentTime,src:v.currentSrc,w:v.videoWidth,paused:v.paused}:null;})()`,
        v=>v && v.src.includes(EPISODES[1].assetId) && v.w>0 && v.t>.2 && !v.paused,40_000);
      check('auto-next-within-season',{status:'PASS',episodeId:EPISODES[1].id,assetId:EPISODES[1].assetId});
      await screenshot('episode-auto-next');
      await cdp.request('Emulation.setDeviceMetricsOverride',{width:375,height:900,deviceScaleFactor:1,mobile:true},pageSessionId);
      const width=await evaluate(`({viewport:innerWidth,content:document.documentElement.scrollWidth})`);
      if(width.content>width.viewport+1) throw new Error('Mobile horizontal overflow');
      check('mobile-width',{status:'PASS',...width}); await screenshot('mobile-episode');
    } else {
      await evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Đăng nhập').click()`);
      await waitFor('one loaded login dialog', `document.querySelectorAll('[role="dialog"]').length`, n=>n===1);
      await evaluate(`(() => {const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
        for(const [selector,value] of [['[data-testid="login-username-input"]','user'],['[data-testid="login-password-input"]','password123']]) {
          const input=document.querySelector(selector);setter.call(input,value);input.dispatchEvent(new Event('input',{bubbles:true}));
        }
        document.querySelector('[data-testid="login-submit-button"]').click();
      })()`);
      await waitFor('account login', `Boolean(localStorage.getItem('dippie_auth_token')) && !document.querySelector('[role="dialog"]')`,Boolean,20_000);
      await cdp.request('Page.navigate',{url:options.baseUrl+'/'},pageSessionId);
      const href=await waitFor('SQL continue watching shelf', `Array.from(document.querySelectorAll('[data-testid="continue-card"]')).map(a=>a.getAttribute('href'))`,
        values=>values?.some(href=>href.includes('ep_jadoo_s01_0001')));
      check('account-continue-watching',{status:'PASS',episodeId:EPISODES[0].id,restoredSqlProgress:href.some(link=>link.includes(EPISODES[0].id))});
      await evaluate(`document.querySelector('[aria-label="Mở Chatbot CineBot"]').click()`);
      await waitFor('deferred chat dialog', `Boolean(document.querySelector('[role="dialog"]'))`,Boolean);
      check('deferred-dialogs',{status:'PASS',loginDialogCount:1,chatOpened:true,modelCalled:false});
    }
    evidence.series = { id: 'ser_jadoo', title: 'Xin Chào Jadoo' };
    evidence.status = 'PASSED';
  } catch (error) {
    evidence.status = 'FAILED';
    evidence.error = safeError(error);
    if (cdp && pageSessionId) {
      try { await screenshot('failure'); } catch { /* page may already be closed */ }
    }
  } finally {
    evidence.finishedAt = new Date().toISOString();
    try {
      if (targetId) await cdp.request('Target.closeTarget', { targetId });
    } catch { /* only the harness-owned target is closed */ }
    try {
      if (browserContextId) await cdp.request('Target.disposeBrowserContext', { browserContextId });
    } catch { /* only the harness-owned context is disposed */ }
    cdp?.close();
    fs.writeFileSync(evidencePath, JSON.stringify(evidence, null, 2), 'utf8');
    console.log(`Preview restart ${options.phase}: ${evidence.status}`);
    console.log(`Evidence: ${evidencePath}`);
    if (evidence.status !== 'PASSED') process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(`Preview restart verification setup failed: ${safeError(error)}`);
  process.exitCode = 1;
});
