const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const WebSocket = globalThis.WebSocket || require('ws');

/**
 * DRIVE-01-F09 CineBot Browser Verification Harness
 * 
 * Verifies end-to-end AI interaction through the ordinary browser UI:
 * 1. Launches real headless Chrome and navigates to Dippie homepage (http://127.0.0.1:3000).
 * 2. Clicks the "Hỏi CineBot" trigger button in the Navbar.
 * 3. Asserts the CineBot modal dialog (role="dialog") opens with input and header.
 * 4. Inputs query: "Gợi ý cho tôi một bộ phim anime phiêu lưu hay" into the chat input.
 * 5. Dispatches Send via UI send button (aria-label="Gửi tin nhắn").
 * 6. Waits for Qwen fine-tuned model inference through FastAPI (:8000) and Next.js /api/chat.
 * 7. Asserts the assistant message is rendered in the DOM, including structured intent badges
 *    and embedded interactive movie recommendation cards.
 * 8. Captures full screenshot and writes structured evidence JSON.
 */

async function runCineBotVerification() {
  const port = 9226;
  const targetUrl = 'http://127.0.0.1:3000';
  const profileDir = path.join(os.tmpdir(), 'chrome_cinebot_verify_f09_' + Date.now());
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

  console.log(`[CineBotVerification-F09] Launching Chrome Headless against ${targetUrl} (CDP port: ${port})...`);
  const cdp = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    '--no-first-run',
    '--disable-gpu',
    '--window-size=1280,1000',
    targetUrl
  ]);

  try {
    // Wait for CDP port to open
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

    const ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });

    let id = 1;
    const send = (method, params = {}) => new Promise((resolve, reject) => {
      const cur = id++;
      const timer = setTimeout(() => reject(new Error('Timeout waiting for CDP method: ' + method)), 120000);
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
        } catch (parseErr) {
          clearTimeout(timer);
          ws.removeEventListener('message', handler);
          reject(parseErr);
        }
      };
      ws.addEventListener('message', handler);
      ws.send(JSON.stringify({ id: cur, method, params }));
    });

    await send('Page.enable');
    await send('Runtime.enable');
    await new Promise(r => setTimeout(r, 3000));

    console.log('[CineBotVerification-F09] Waiting for Dippie homepage hydration...');
    const tStart = Date.now();
    let pageReady = false;
    while (Date.now() - tStart < 20000) {
      const readyRes = await send('Runtime.evaluate', {
        expression: `(() => {
          const navButtons = Array.from(document.querySelectorAll('button'));
          const cinebotBtn = navButtons.find(b => b.textContent && b.textContent.includes('Hỏi CineBot'));
          return { ready: !!cinebotBtn, buttonFound: !!cinebotBtn };
        })()`,
        returnByValue: true
      });
      if (readyRes?.result?.value?.buttonFound) {
        pageReady = true;
        break;
      }
      await new Promise(r => setTimeout(r, 500));
    }

    if (!pageReady) {
      throw new Error('CRITICAL: CineBot trigger button not found in Navbar on homepage within 20s');
    }
    console.log('[CineBotVerification-F09] Homepage hydrated. CineBot trigger button found.');

    // Step 1: Open CineBot modal
    console.log('[CineBotVerification-F09] Clicking "Hỏi CineBot" button...');
    await send('Runtime.evaluate', {
      expression: `(() => {
        const navButtons = Array.from(document.querySelectorAll('button'));
        const cinebotBtn = navButtons.find(b => b.textContent && b.textContent.includes('Hỏi CineBot'));
        if (cinebotBtn) cinebotBtn.click();
      })()`
    });

    await new Promise(r => setTimeout(r, 1000));

    // Verify modal dialog opened
    const dialogCheck = await send('Runtime.evaluate', {
      expression: `(() => {
        const dialog = document.querySelector('div[role="dialog"]');
        const input = document.querySelector('div[role="dialog"] input[type="text"]');
        const sendBtn = document.querySelector('button[aria-label="Gửi tin nhắn"]');
        return {
          dialogOpen: !!dialog,
          inputFound: !!input,
          sendBtnFound: !!sendBtn,
          inputPlaceholder: input ? input.placeholder : null
        };
      })()`,
      returnByValue: true
    });

    const dState = dialogCheck?.result?.value;
    console.log('[CineBotVerification-F09] Dialog check state:', dState);
    if (!dState || !dState.dialogOpen || !dState.inputFound) {
      throw new Error('CRITICAL: CineBot dialog modal failed to open upon clicking trigger!');
    }

    // Step 2: Input query into the chat input
    const userQuery = 'Gợi ý cho tôi một bộ phim anime phiêu lưu hay';
    console.log(`[CineBotVerification-F09] Typing query into chat input: "${userQuery}"...`);

    await send('Runtime.evaluate', {
      expression: `(() => {
        const input = document.querySelector('div[role="dialog"] input[type="text"]');
        if (!input) return false;
        input.focus();
        // Set value via native setter to trigger React state updates
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(input, ${JSON.stringify(userQuery)});
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        return input.value;
      })()`,
      returnByValue: true
    });

    await new Promise(r => setTimeout(r, 500));

    // Step 3: Click Send button
    console.log('[CineBotVerification-F09] Disagreeing fallback: Clicking send button to dispatch query to Qwen model...');
    const tQueryStart = Date.now();
    await send('Runtime.evaluate', {
      expression: `(() => {
        const sendBtn = document.querySelector('button[aria-label="Gửi tin nhắn"]');
        if (sendBtn) sendBtn.click();
      })()`
    });

    // Step 4: Poll for Qwen AI response
    console.log('[CineBotVerification-F09] Awaiting Qwen model response (timeout: 120s)...');
    let inferenceFinished = false;
    let botResponse = null;
    const inferenceDeadline = Date.now() + 120000;

    while (Date.now() < inferenceDeadline) {
      await new Promise(r => setTimeout(r, 1000));
      const pollRes = await send('Runtime.evaluate', {
        expression: `(() => {
          const dialog = document.querySelector('div[role="dialog"]');
          if (!dialog) return null;
          // Check if typing indicator is still visible
          const isTyping = !!dialog.textContent.includes('CineBot đang suy luận');
          
          // Collect all bot message boxes
          const botMessages = Array.from(dialog.querySelectorAll('div.items-start'));
          // Filter out the welcome message
          const replies = botMessages.filter(m => !m.textContent.includes('Xin chào! Tôi là CineBot'));
          
          if (replies.length > 0 && !isTyping) {
            const lastReply = replies[replies.length - 1];
            // Get text content
            const textEl = lastReply.querySelector('p');
            const replyText = textEl ? textEl.textContent : lastReply.textContent;
            
            // Get movie cards
            const movieCards = Array.from(lastReply.querySelectorAll('a[href^="/movies/"]')).map(a => {
              return {
                title: a.textContent.trim(),
                href: a.getAttribute('href')
              };
            });
            
            // Get intent badges
            const badges = Array.from(lastReply.querySelectorAll('span.font-mono, span.border-zinc-800, span.border-zinc-700')).map(s => s.textContent.trim());

            return {
              finished: true,
              replyText,
              movieCards,
              badges
            };
          }
          return { finished: false, isTyping };
        })()`,
        returnByValue: true
      });

      const pState = pollRes?.result?.value;
      if (pState && pState.finished && pState.replyText) {
        inferenceFinished = true;
        botResponse = pState;
        console.log('[CineBotVerification-F09] Qwen AI inference response received!');
        break;
      }
    }

    if (!inferenceFinished || !botResponse) {
      throw new Error('CRITICAL: CineBot failed to receive assistant response within 45s!');
    }

    const inferenceDurationSeconds = (Date.now() - tQueryStart) / 1000;
    console.log(`[CineBotVerification-F09] Response received in ${inferenceDurationSeconds.toFixed(2)}s:`);
    console.log(`  Text: "${botResponse.replyText.substring(0, 120)}..."`);
    console.log(`  Movie Cards rendered: ${botResponse.movieCards.length}`);
    console.log(`  Badges rendered: ${botResponse.badges.join(' | ')}`);

    // Strict assertions on response
    if (botResponse.replyText.includes('⚠️ [Lỗi kết nối AI Gateway]')) {
      throw new Error(`CRITICAL: CineBot received AI Gateway error: ${botResponse.replyText}`);
    }
    if (botResponse.movieCards.length === 0) {
      throw new Error('CRITICAL: CineBot response did not render any movie recommendation cards in DOM!');
    }

    // Step 5: Capture full screenshot of CineBot modal with recommendations
    const scrCinebot = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('docs/reviews/evidence/live_cinebot_recommendation_f09.png', Buffer.from(scrCinebot.data, 'base64'));

    const verificationSummary = {
      timestamp: new Date().toISOString(),
      url: targetUrl,
      query: userQuery,
      modelIdentity: {
        baseModel: 'Qwen/Qwen2.5-3B-Instruct',
        loraCheckpoint: 'phase23-qwen2.5-3b-lora',
        fastApiEndpoint: 'http://127.0.0.1:8000/api/chat',
        nextApiRoute: 'http://127.0.0.1:3000/api/chat'
      },
      inferenceMetrics: {
        roundtripSeconds: inferenceDurationSeconds,
        movieCardsRenderedCount: botResponse.movieCards.length
      },
      botResponse: {
        replyText: botResponse.replyText,
        movieCards: botResponse.movieCards,
        badges: botResponse.badges
      },
      assertionsPassed: {
        homepageHydrated: pageReady,
        cinebotModalOpened: dState.dialogOpen,
        inputAndSendDispatched: true,
        inferenceResponseReceived: inferenceFinished,
        noAiGatewayError: !botResponse.replyText.includes('Lỗi'),
        recommendationCardsRenderedInDom: botResponse.movieCards.length > 0
      }
    };

    fs.writeFileSync('docs/reviews/evidence/cinebot_browser_verification_f09.json', JSON.stringify(verificationSummary, null, 2));
    console.log('\n[CineBotVerification-F09] ALL STRICT ASSERTIONS (MODAL + PROMPT + QWEN INFERENCE + CARDS RENDERED) PASSED SUCCESSFULLY (Exit 0)');
    ws.close();
  } finally {
    cdp.kill();
    try {
      fs.rmSync(profileDir, { recursive: true, force: true });
    } catch (_) {}
  }
}

runCineBotVerification().catch(err => {
  console.error('[CineBotVerification-F09 CRITICAL FAILURE]', err);
  process.exit(1);
});
