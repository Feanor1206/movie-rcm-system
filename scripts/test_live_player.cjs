const { spawn } = require('child_process');
const fs = require('fs');

async function testPlayer() {
  const cdp = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', [
    '--headless=new',
    '--remote-debugging-port=9227',
    '--no-first-run',
    '--disable-gpu',
    '--autoplay-policy=no-user-gesture-required',
    '--window-size=1280,1000',
    'http://localhost:3000/movies/drive-videoplayback'
  ]);

  try {
    await new Promise(r => setTimeout(r, 4000));
    const pages = await fetch('http://127.0.0.1:9227/json/list').then(r => r.json());
    const page = pages.find(p => p.type === 'page');
    const ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise(r => ws.onopen = r);

    let id = 1;
    const send = (method, params = {}) => new Promise((resolve, reject) => {
      const cur = id++;
      const timer = setTimeout(() => reject(new Error('Timeout ' + method)), 30000);
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

    // Click play button
    const clickRes = await send('Runtime.evaluate', {
      expression: 'document.querySelector("[data-testid=\'play-feature-btn\']").click(); true;'
    });
    console.log('Play button clicked:', clickRes);

    // Wait 12 seconds for Google Drive stream to start and frame to render
    await new Promise(r => setTimeout(r, 12000));

    const snap = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('docs/reviews/evidence/live_shin_player_active.png', Buffer.from(snap.data, 'base64'));
    ws.close();
    console.log('PLAYER_ACTIVE_SCREENSHOT_OK');
  } finally {
    cdp.kill();
  }
}

testPlayer().catch(e => {
  console.error(e);
  process.exit(1);
});
