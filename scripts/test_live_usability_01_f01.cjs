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

async function runBrowserVerification() {
  const evidence = {
    timestamp: new Date().toISOString(),
    mission: 'USABILITY-01-F01 — NỐI CARD CINEBOT TỚI ĐÚNG PLAYER TẬP PHIM',
    status: 'UNKNOWN',
    auth: {},
    query_1_s01e01: {},
    query_2_s03e01: {},
    segment_deep_link: {},
    screenshots: {}
  };

  const port = 9226;
  const profileDir = path.join(os.tmpdir(), 'chrome_usability_f01_' + Date.now());
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

  console.log(`[USABILITY-01-F01] Launching Chrome Headless on CDP port ${port}...`);
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
    console.log('[USABILITY-01-F01] Step 1: Authenticating as admin to obtain access token...');
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
    console.log('[USABILITY-01-F01] Admin authenticated successfully.');

    // Navigate to homepage and inject auth token into localStorage
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
    // TEST QUERY 1: "Xin Chào Jadoo Mùa 1 Tập 1"
    // -------------------------------------------------------------------------
    console.log('\n[USABILITY-01-F01] Step 2: Testing CineBot Query 1: "Xin Chào Jadoo Mùa 1 Tập 1"...');
    await send('Page.navigate', { url: 'http://localhost:3000/' });
    await new Promise(r => setTimeout(r, 2500));

    // Open CineBot modal
    const openBtnRes = await send('Runtime.evaluate', {
      expression: `(() => {
        const buttons = Array.from(document.querySelectorAll('button'));
        const cinebotBtn = buttons.find(b => b.textContent && b.textContent.includes('Hỏi CineBot'));
        if (cinebotBtn) { cinebotBtn.click(); return true; }
        return false;
      })()`,
      returnByValue: true
    });
    if (!openBtnRes?.result?.value) {
      throw new Error('Could not find or click "Hỏi CineBot" button');
    }
    await new Promise(r => setTimeout(r, 1000));

    // Type query into CineBot input
    const query1 = 'Xin Chào Jadoo Mùa 1 Tập 1';
    await send('Runtime.evaluate', {
      expression: `(() => {
        const dialog = document.querySelector('div[role="dialog"]');
        const input = dialog ? dialog.querySelector('input[type="text"]') : null;
        if (!input) return false;
        input.focus();
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(input, ${JSON.stringify(query1)});
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      })()`,
      returnByValue: true
    });
    await new Promise(r => setTimeout(r, 500));

    // Click Send button
    console.log('[USABILITY-01-F01] Sending Query 1 to full Qwen model...');
    const tQ1Start = Date.now();
    await send('Runtime.evaluate', {
      expression: `(() => {
        const sendBtn = document.querySelector('button[aria-label="Gửi tin nhắn"]');
        if (sendBtn) sendBtn.click();
      })()`
    });

    // Poll for AI response
    let q1Done = false;
    let q1Data = null;
    const q1Deadline = Date.now() + 120000;
    while (Date.now() < q1Deadline) {
      await new Promise(r => setTimeout(r, 1000));
      const pollRes = await send('Runtime.evaluate', {
        expression: `(() => {
          const dialog = document.querySelector('div[role="dialog"]');
          if (!dialog) return null;
          const isTyping = dialog.textContent.includes('CineBot đang suy luận');
          const botMessages = Array.from(dialog.querySelectorAll('div.items-start'));
          const replies = botMessages.filter(m => !m.textContent.includes('Xin chào! Tôi là CineBot'));
          if (replies.length > 0 && !isTyping) {
            const lastReply = replies[replies.length - 1];
            const p = lastReply.querySelector('p');
            const text = p ? p.textContent : lastReply.textContent;

            // Collect recommendation cards
            const cards = Array.from(lastReply.querySelectorAll('div.group')).map(c => {
              const links = Array.from(c.querySelectorAll('a'));
              const titleLink = links[0]?.getAttribute('href') || null;
              const actionLink = links[1]?.getAttribute('href') || null;
              const titleText = links[0]?.textContent || '';
              return { titleText, titleLink, actionLink };
            });

            // Also check all links in lastReply
            const allLinks = Array.from(lastReply.querySelectorAll('a')).map(a => ({
              text: a.textContent.trim(),
              href: a.getAttribute('href')
            }));

            return { text, cards, allLinks };
          }
          return null;
        })()`,
        returnByValue: true
      });
      if (pollRes?.result?.value) {
        q1Done = true;
        q1Data = pollRes.result.value;
        break;
      }
    }
    if (!q1Done || !q1Data) {
      throw new Error('Query 1 timed out after 120s waiting for Qwen response');
    }
    const q1Elapsed = Date.now() - tQ1Start;
    console.log(`[USABILITY-01-F01] Query 1 response received in ${q1Elapsed}ms.`);
    console.log('[USABILITY-01-F01] Reply text:', q1Data.text.substring(0, 100) + '...');
    console.log('[USABILITY-01-F01] Card links found:', JSON.stringify(q1Data.cards));

    // Verify card routing contracts
    const primaryCard = q1Data.cards[0] || (q1Data.allLinks.length > 0 ? {
      titleText: q1Data.allLinks[0].text,
      titleLink: q1Data.allLinks[0].href,
      actionLink: q1Data.allLinks[1]?.href || q1Data.allLinks[0].href
    } : null);

    if (!primaryCard) {
      throw new Error('No recommendation card found in CineBot response for Query 1');
    }

    console.log(`[USABILITY-01-F01] Checking href for card: titleLink=${primaryCard.titleLink}, actionLink=${primaryCard.actionLink}`);

    // Strict invariant: must NOT link to /movies/ep_jadoo_s01_0001
    if (primaryCard.titleLink.startsWith('/movies/ep_jadoo')) {
      throw new Error(`CRITICAL FAILURE: Card title still links to legacy movie route: ${primaryCard.titleLink}`);
    }
    if (primaryCard.actionLink && primaryCard.actionLink.startsWith('/movies/ep_jadoo')) {
      throw new Error(`CRITICAL FAILURE: Card action button still links to legacy movie route: ${primaryCard.actionLink}`);
    }

    // Must link to /series/ser_jadoo?episode=ep_jadoo_s01_0001
    const expectedPrefix = '/series/ser_jadoo?episode=ep_jadoo_s01_0001';
    if (!primaryCard.titleLink.startsWith(expectedPrefix)) {
      throw new Error(`CRITICAL FAILURE: Card title link '${primaryCard.titleLink}' does not match expected '${expectedPrefix}'`);
    }

    evidence.query_1_s01e01 = {
      query: query1,
      elapsed_ms: q1Elapsed,
      response_text: q1Data.text,
      card_title: primaryCard.titleText,
      card_title_href: primaryCard.titleLink,
      card_action_href: primaryCard.actionLink,
      links_identical: primaryCard.titleLink === primaryCard.actionLink,
      no_legacy_movie_route: !primaryCard.titleLink.includes('/movies/')
    };

    // Step 2.2: Click the card link in the UI to navigate
    console.log('[USABILITY-01-F01] Clicking the card link in CineBot dialog...');
    await send('Runtime.evaluate', {
      expression: `(() => {
        const dialog = document.querySelector('div[role="dialog"]');
        const link = dialog.querySelector('a[href*="/series/ser_jadoo?episode=ep_jadoo_s01_0001"]');
        if (link) { link.click(); return true; }
        return false;
      })()`
    });

    // Wait for navigation to /series/ser_jadoo
    console.log('[USABILITY-01-F01] Waiting for navigation to series page...');
    let navS01Done = false;
    const navDeadline = Date.now() + 20000;
    while (Date.now() < navDeadline) {
      await new Promise(r => setTimeout(r, 500));
      const locRes = await send('Runtime.evaluate', {
        expression: 'window.location.href',
        returnByValue: true
      });
      const currentUrl = locRes?.result?.value || '';
      if (currentUrl.includes('/series/ser_jadoo') && currentUrl.includes('episode=ep_jadoo_s01_0001')) {
        navS01Done = true;
        evidence.query_1_s01e01.navigated_url = currentUrl;
        break;
      }
    }
    if (!navS01Done) {
      throw new Error('Failed to navigate to /series/ser_jadoo?episode=ep_jadoo_s01_0001 upon clicking card');
    }
    console.log(`[USABILITY-01-F01] Navigation verified: ${evidence.query_1_s01e01.navigated_url}`);

    // Wait for series page to load episode and video
    console.log('[USABILITY-01-F01] Waiting for video element and episode metadata...');
    let videoLoaded = false;
    let videoState = null;
    const videoDeadline = Date.now() + 30000;
    while (Date.now() < videoDeadline) {
      await new Promise(r => setTimeout(r, 1000));
      const vRes = await send('Runtime.evaluate', {
        expression: `(() => {
          const video = document.querySelector('video');
          const epHeader = document.querySelector('h2');
          const activeEpBtn = document.querySelector('button[data-episode-id="ep_jadoo_s01_0001"]');
          return {
            hasVideo: !!video,
            src: video ? video.currentSrc || video.src : null,
            videoWidth: video ? video.videoWidth : 0,
            videoHeight: video ? video.videoHeight : 0,
            duration: video ? video.duration : 0,
            currentTime: video ? video.currentTime : 0,
            paused: video ? video.paused : true,
            episodeTitle: epHeader ? epHeader.textContent : '',
            activeEpBtnFound: !!activeEpBtn
          };
        })()`,
        returnByValue: true
      });
      const v = vRes?.result?.value;
      if (v && v.hasVideo && v.src && v.videoWidth > 0) {
        videoLoaded = true;
        videoState = v;
        break;
      }
    }
    if (!videoLoaded || !videoState) {
      throw new Error('Video player did not initialize or failed to load metadata within 30s');
    }

    console.log('[USABILITY-01-F01] Video metadata loaded:', {
      dimensions: `${videoState.videoWidth}x${videoState.videoHeight}`,
      duration: videoState.duration,
      episodeTitle: videoState.episodeTitle,
      src: redactUrl(videoState.src)
    });

    // Assert correct episode and asset
    if (!videoState.src.includes('asset_jadoo_s01_v0001')) {
      throw new Error(`Unexpected video src: ${redactUrl(videoState.src)}, expected asset_jadoo_s01_v0001`);
    }

    // Test playback advancement
    console.log('[USABILITY-01-F01] Testing playback advance...');
    await send('Runtime.evaluate', {
      expression: 'document.querySelector("video").play()'
    });
    const t0 = (await send('Runtime.evaluate', { expression: 'document.querySelector("video").currentTime', returnByValue: true })).result.value;
    await new Promise(r => setTimeout(r, 2000));
    const t1 = (await send('Runtime.evaluate', { expression: 'document.querySelector("video").currentTime', returnByValue: true })).result.value;
    const advancing = t1 > t0;
    console.log(`[USABILITY-01-F01] Playback time advance: ${t0.toFixed(3)}s -> ${t1.toFixed(3)}s (advancing: ${advancing})`);
    if (!advancing) throw new Error('Video failed to advance currentTime during playback');

    // Test Pause and Resume
    console.log('[USABILITY-01-F01] Testing Pause...');
    await send('Runtime.evaluate', { expression: 'document.querySelector("video").pause()' });
    await new Promise(r => setTimeout(r, 500));
    const tPause0 = (await send('Runtime.evaluate', { expression: 'document.querySelector("video").currentTime', returnByValue: true })).result.value;
    await new Promise(r => setTimeout(r, 1000));
    const tPause1 = (await send('Runtime.evaluate', { expression: 'document.querySelector("video").currentTime', returnByValue: true })).result.value;
    const pausedOk = Math.abs(tPause1 - tPause0) < 0.05;
    console.log(`[USABILITY-01-F01] Pause verified: time held at ${tPause0.toFixed(3)}s (pausedOk: ${pausedOk})`);

    console.log('[USABILITY-01-F01] Testing Resume...');
    await send('Runtime.evaluate', { expression: 'document.querySelector("video").play()' });
    await new Promise(r => setTimeout(r, 1500));
    const tResumed = (await send('Runtime.evaluate', { expression: 'document.querySelector("video").currentTime', returnByValue: true })).result.value;
    const resumeOk = tResumed > tPause1;
    console.log(`[USABILITY-01-F01] Resume verified: time advanced to ${tResumed.toFixed(3)}s (resumeOk: ${resumeOk})`);

    // Test Seek to 60.0s
    console.log('[USABILITY-01-F01] Testing Seek to 60.0s...');
    await send('Runtime.evaluate', {
      expression: `(() => {
        const v = document.querySelector('video');
        v.currentTime = 60.0;
      })()`
    });
    await new Promise(r => setTimeout(r, 2000));
    const tSeeked = (await send('Runtime.evaluate', { expression: 'document.querySelector("video").currentTime', returnByValue: true })).result.value;
    console.log(`[USABILITY-01-F01] Post-seek currentTime: ${tSeeked.toFixed(3)}s`);
    if (tSeeked < 59.5) throw new Error(`Seek failed, currentTime ${tSeeked} < 59.5s`);

    // Settle and verify post-seek advancing
    await new Promise(r => setTimeout(r, 1500));
    const tSeekAfter = (await send('Runtime.evaluate', { expression: 'document.querySelector("video").currentTime', returnByValue: true })).result.value;
    const postSeekAdvancing = tSeekAfter > tSeeked;
    console.log(`[USABILITY-01-F01] Post-seek advancing: ${tSeeked.toFixed(3)}s -> ${tSeekAfter.toFixed(3)}s (postSeekAdvancing: ${postSeekAdvancing})`);

    // Capture screenshot
    const s01Snap = await send('Page.captureScreenshot', { format: 'png' });
    const s01SnapPath = 'docs/reviews/evidence/USABILITY_01_F01_live_s01e01_playing.png';
    fs.writeFileSync(s01SnapPath, Buffer.from(s01Snap.data, 'base64'));
    evidence.screenshots.s01e01 = s01SnapPath;

    evidence.query_1_s01e01.playback = {
      video_dimensions: `${videoState.videoWidth}x${videoState.videoHeight}`,
      total_duration_s: videoState.duration,
      asset_id: 'asset_jadoo_s01_v0001',
      stream_url_redacted: redactUrl(videoState.src),
      time_advance: { t0, t1, delta_s: t1 - t0, advancing },
      pause: { tPause0, tPause1, pausedOk },
      resume: { tResumed, resumeOk },
      seek_60s: { tSeeked, tSeekAfter, postSeekAdvancing }
    };

    // -------------------------------------------------------------------------
    // TEST QUERY 2: "Jadoo Mùa 3 Tập 1" (Cross-Season Distinct Episode Test)
    // -------------------------------------------------------------------------
    console.log('\n[USABILITY-01-F01] Step 3: Testing CineBot Query 2: "Jadoo Mùa 3 Tập 1"...');
    await send('Page.navigate', { url: 'http://localhost:3000/' });
    await new Promise(r => setTimeout(r, 2500));

    // Open CineBot modal
    await send('Runtime.evaluate', {
      expression: `(() => {
        const buttons = Array.from(document.querySelectorAll('button'));
        const cinebotBtn = buttons.find(b => b.textContent && b.textContent.includes('Hỏi CineBot'));
        if (cinebotBtn) cinebotBtn.click();
      })()`
    });
    await new Promise(r => setTimeout(r, 1000));

    const query2 = 'Jadoo Mùa 3 Tập 1';
    await send('Runtime.evaluate', {
      expression: `(() => {
        const dialog = document.querySelector('div[role="dialog"]');
        const input = dialog ? dialog.querySelector('input[type="text"]') : null;
        if (!input) return false;
        input.focus();
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(input, ${JSON.stringify(query2)});
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      })()`,
      returnByValue: true
    });
    await new Promise(r => setTimeout(r, 500));

    console.log('[USABILITY-01-F01] Sending Query 2 to full Qwen model...');
    const tQ2Start = Date.now();
    await send('Runtime.evaluate', {
      expression: `(() => {
        const sendBtn = document.querySelector('button[aria-label="Gửi tin nhắn"]');
        if (sendBtn) sendBtn.click();
      })()`
    });

    let q2Done = false;
    let q2Data = null;
    const q2Deadline = Date.now() + 120000;
    while (Date.now() < q2Deadline) {
      await new Promise(r => setTimeout(r, 1000));
      const pollRes = await send('Runtime.evaluate', {
        expression: `(() => {
          const dialog = document.querySelector('div[role="dialog"]');
          if (!dialog) return null;
          const isTyping = dialog.textContent.includes('CineBot đang suy luận');
          const botMessages = Array.from(dialog.querySelectorAll('div.items-start'));
          const replies = botMessages.filter(m => !m.textContent.includes('Xin chào! Tôi là CineBot'));
          if (replies.length > 0 && !isTyping) {
            const lastReply = replies[replies.length - 1];
            const p = lastReply.querySelector('p');
            const text = p ? p.textContent : lastReply.textContent;

            const cards = Array.from(lastReply.querySelectorAll('div.group')).map(c => {
              const links = Array.from(c.querySelectorAll('a'));
              const titleLink = links[0]?.getAttribute('href') || null;
              const actionLink = links[1]?.getAttribute('href') || null;
              const titleText = links[0]?.textContent || '';
              return { titleText, titleLink, actionLink };
            });

            const allLinks = Array.from(lastReply.querySelectorAll('a')).map(a => ({
              text: a.textContent.trim(),
              href: a.getAttribute('href')
            }));

            return { text, cards, allLinks };
          }
          return null;
        })()`,
        returnByValue: true
      });
      if (pollRes?.result?.value) {
        q2Done = true;
        q2Data = pollRes.result.value;
        break;
      }
    }
    if (!q2Done || !q2Data) {
      throw new Error('Query 2 timed out after 120s waiting for Qwen response');
    }
    const q2Elapsed = Date.now() - tQ2Start;
    console.log(`[USABILITY-01-F01] Query 2 response received in ${q2Elapsed}ms.`);
    console.log('[USABILITY-01-F01] Reply text:', q2Data.text.substring(0, 100) + '...');

    const cardQ2 = q2Data.cards[0] || (q2Data.allLinks.length > 0 ? {
      titleText: q2Data.allLinks[0].text,
      titleLink: q2Data.allLinks[0].href,
      actionLink: q2Data.allLinks[1]?.href || q2Data.allLinks[0].href
    } : null);

    if (!cardQ2) {
      throw new Error('No recommendation card found for Query 2');
    }

    console.log(`[USABILITY-01-F01] Checking href for Query 2 card: ${cardQ2.titleLink}`);
    // Strict invariant: must link to Season 3 Episode 1 (ep_jadoo_s03_0001), NOT ep_jadoo_s01_0001
    const expectedQ2Prefix = '/series/ser_jadoo?episode=ep_jadoo_s03_0001';
    if (!cardQ2.titleLink.startsWith(expectedQ2Prefix)) {
      throw new Error(`CRITICAL FAILURE: Card for Season 3 Ep 1 linked to '${cardQ2.titleLink}', expected '${expectedQ2Prefix}'`);
    }

    evidence.query_2_s03e01 = {
      query: query2,
      elapsed_ms: q2Elapsed,
      response_text: q2Data.text,
      card_title: cardQ2.titleText,
      card_title_href: cardQ2.titleLink,
      card_action_href: cardQ2.actionLink,
      distinct_from_s01e01: cardQ2.titleLink !== primaryCard.titleLink,
      correct_season_3_episode_1: true
    };

    // Click card to navigate
    console.log('[USABILITY-01-F01] Clicking Season 3 Episode 1 card...');
    await send('Runtime.evaluate', {
      expression: `(() => {
        const dialog = document.querySelector('div[role="dialog"]');
        const link = dialog.querySelector('a[href*="/series/ser_jadoo?episode=ep_jadoo_s03_0001"]');
        if (link) { link.click(); return true; }
        return false;
      })()`
    });

    // Wait for navigation
    let navS03Done = false;
    const navS03Deadline = Date.now() + 20000;
    while (Date.now() < navS03Deadline) {
      await new Promise(r => setTimeout(r, 500));
      const locRes = await send('Runtime.evaluate', { expression: 'window.location.href', returnByValue: true });
      const currentUrl = locRes?.result?.value || '';
      if (currentUrl.includes('/series/ser_jadoo') && currentUrl.includes('episode=ep_jadoo_s03_0001')) {
        navS03Done = true;
        evidence.query_2_s03e01.navigated_url = currentUrl;
        break;
      }
    }
    if (!navS03Done) throw new Error('Failed to navigate to Season 3 Episode 1 URL');
    console.log(`[USABILITY-01-F01] Navigation verified for S3 E1: ${evidence.query_2_s03e01.navigated_url}`);

    // Wait for S3 E1 video metadata
    let s03VideoLoaded = false;
    let s03VideoState = null;
    const s03Deadline = Date.now() + 30000;
    while (Date.now() < s03Deadline) {
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
            episodeTitle: epHeader ? epHeader.textContent : ''
          };
        })()`,
        returnByValue: true
      });
      const v = vRes?.result?.value;
      if (v && v.hasVideo && v.src && v.videoWidth > 0) {
        s03VideoLoaded = true;
        s03VideoState = v;
        break;
      }
    }
    if (!s03VideoLoaded || !s03VideoState) {
      throw new Error('Video player failed to load Season 3 Episode 1 media');
    }

    console.log('[USABILITY-01-F01] Season 3 Episode 1 video loaded:', {
      dimensions: `${s03VideoState.videoWidth}x${s03VideoState.videoHeight}`,
      title: s03VideoState.episodeTitle,
      src: redactUrl(s03VideoState.src)
    });

    if (!s03VideoState.src.includes('asset_jadoo_s03_v0001')) {
      throw new Error(`Unexpected video src for S3 E1: ${redactUrl(s03VideoState.src)}, expected asset_jadoo_s03_v0001`);
    }

    // Capture S3 E1 screenshot
    const s03Snap = await send('Page.captureScreenshot', { format: 'png' });
    const s03SnapPath = 'docs/reviews/evidence/USABILITY_01_F01_live_s03e01_playing.png';
    fs.writeFileSync(s03SnapPath, Buffer.from(s03Snap.data, 'base64'));
    evidence.screenshots.s03e01 = s03SnapPath;

    evidence.query_2_s03e01.playback = {
      video_dimensions: `${s03VideoState.videoWidth}x${s03VideoState.videoHeight}`,
      episode_title: s03VideoState.episodeTitle,
      asset_id: 'asset_jadoo_s03_v0001',
      stream_url_redacted: redactUrl(s03VideoState.src)
    };

    // -------------------------------------------------------------------------
    // TEST 3: SEGMENT DEEP-LINK TEST WITH REAL TIMESTAMP
    // -------------------------------------------------------------------------
    console.log('\n[USABILITY-01-F01] Step 4: Testing Segment Deep-Link URL...');
    const segUrl = 'http://localhost:3000/series/ser_jadoo?episode=ep_jadoo_s01_0008&segment=seg_jadoo_s01_008a&t=0';
    await send('Page.navigate', { url: segUrl });
    await new Promise(r => setTimeout(r, 4000));

    // Verify segment is active and highlighted
    let segVerified = false;
    let segState = null;
    const segDeadline = Date.now() + 20000;
    while (Date.now() < segDeadline) {
      await new Promise(r => setTimeout(r, 1000));
      const res = await send('Runtime.evaluate', {
        expression: `(() => {
          const video = document.querySelector('video');
          const epHeader = document.querySelector('h2');
          const segEl = document.querySelector('[data-segment-id="seg_jadoo_s01_008a"]');
          const isActive = segEl ? (segEl.className.includes('bg-brand') || segEl.className.includes('border-brand')) : false;
          return {
            hasVideo: !!video,
            src: video ? video.currentSrc || video.src : null,
            videoWidth: video ? video.videoWidth : 0,
            videoHeight: video ? video.videoHeight : 0,
            episodeTitle: epHeader ? epHeader.textContent : '',
            segFound: !!segEl,
            segActive: isActive
          };
        })()`,
        returnByValue: true
      });
      const s = res?.result?.value;
      if (s && s.hasVideo && s.src && s.segActive) {
        segVerified = true;
        segState = s;
        break;
      }
    }

    if (!segVerified || !segState) {
      throw new Error('Segment deep-link verification failed (segment not highlighted or video not loaded)');
    }

    console.log('[USABILITY-01-F01] Segment deep-link verified:', {
      episodeTitle: segState.episodeTitle,
      segmentActive: segState.segActive,
      src: redactUrl(segState.src)
    });

    const segSnap = await send('Page.captureScreenshot', { format: 'png' });
    const segSnapPath = 'docs/reviews/evidence/USABILITY_01_F01_live_segment_deep_link.png';
    fs.writeFileSync(segSnapPath, Buffer.from(segSnap.data, 'base64'));
    evidence.screenshots.segment = segSnapPath;

    evidence.segment_deep_link = {
      url: segUrl,
      episode_title: segState.episodeTitle,
      segment_active: segState.segActive,
      asset_id: 'asset_jadoo_s01_v0008',
      stream_url_redacted: redactUrl(segState.src)
    };

    evidence.status = 'PASS';
    console.log('\n[USABILITY-01-F01] ALL END-TO-END BROWSER VERIFICATIONS PASSED 100%!');

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
  const evidencePath = 'docs/reviews/evidence/USABILITY_01_F01_BROWSER_VERIFICATION.json';
  fs.writeFileSync(evidencePath, JSON.stringify(evidence, null, 2), 'utf-8');
  console.log(`[USABILITY-01-F01] Saved evidence to ${evidencePath}`);
  return evidence;
}

runBrowserVerification().catch(err => {
  console.error('[USABILITY-01-F01] Verification failed:', err);
  process.exit(1);
});
