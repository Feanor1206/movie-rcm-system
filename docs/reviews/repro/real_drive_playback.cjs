// Reviewer-only real Drive harness. Requires an accepted code gate and existing read-only mount.
// Never changes Drive contents. Only creates isolated local test output and owned processes.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const net = require('node:net');
const {spawn} = require('node:child_process');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../..');
const mount = process.argv[2];
if (!mount) throw new Error('Pass an already verified read-only mount root');
const evidence = path.join(root, 'docs/reviews/evidence/REAL_DRIVE');
fs.mkdirSync(evidence, {recursive:true});
const owned = [];
const delay = ms => new Promise(r=>setTimeout(r,ms));
async function port() {return new Promise((resolve,reject)=>{const s=net.createServer();s.on('error',reject);s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>resolve(p));});});}
function child(exe,args,options={}) {
  const p=spawn(exe,args,{windowsHide:true,cwd:root,stdio:['pipe','pipe','pipe'],...options}); owned.push(p); return p;
}
async function until(fn,label,ms=30000) {
  const end=Date.now()+ms;
  while(Date.now()<end){try{const v=await fn();if(v)return v;}catch{} await delay(100);}
  throw new Error('Timeout: '+label);
}
async function main(){
  const result={source:'Actual Google Drive read-only mount -> production Spring/H2 -> production Next player -> Chrome decoder',mount,startedAt:new Date().toISOString(),seeks:[]};
  let ws;
  try {
    result.bytes=fs.statSync(path.join(mount,'videoplayback.mp4')).size;
    const local=fs.mkdtempSync(path.join(os.tmpdir(),'codex-real-drive-'));
    result.localOutput=local;
    const cp=path.join(root,'backend/springboot/target/classes')+';'+path.join(root,'backend/springboot/target/test-classes')+';'+fs.readFileSync(path.join(root,'backend/springboot/target/cp.txt'),'utf8').trim();
    const java=child('C:/Program Files/Java/jdk-25.0.3/bin/java.exe',['--class-path',cp,path.join(__dirname,'RealDrivePlaybackServer.java'),mount,local]);
    let output='';const log=fs.createWriteStream(path.join(evidence,'spring.log'));
    java.stdout.on('data',b=>{output+=b.toString();log.write(b);});java.stderr.on('data',b=>log.write(b));
    const backend=await until(()=>{if(java.exitCode!==null)throw new Error('Spring exited');const m=output.match(/REAL_DRIVE_PORT=(\d+)/);return m&&Number(m[1]);},'isolated Spring ready',60000);
    const base=`http://127.0.0.1:${backend}`;
    result.backendPort=backend;
    const stream=base+'/api/media/stream/codex-real-drive-feature';
    const head=await fetch(stream,{method:'HEAD',signal:AbortSignal.timeout(15000)});
    assert.equal(head.status,200);assert.equal(Number(head.headers.get('content-length')),result.bytes);
    result.head={status:head.status,acceptRanges:head.headers.get('accept-ranges')};
    result.ranges=[];
    for(const start of [0,Math.floor(result.bytes/2),result.bytes-65536]){
      const end=start+65535,t0=performance.now();const res=await fetch(stream,{headers:{Range:`bytes=${start}-${end}`},signal:AbortSignal.timeout(15000)});
      assert.equal(res.status,206);assert.equal(res.headers.get('content-range'),`bytes ${start}-${end}/${result.bytes}`);
      const data=Buffer.from(await res.arrayBuffer());assert.equal(data.length,65536);
      const fd=fs.openSync(path.join(mount,'videoplayback.mp4'),'r');const expected=Buffer.alloc(data.length);try{assert.equal(fs.readSync(fd,expected,0,expected.length,start),expected.length);}finally{fs.closeSync(fd);}assert.deepEqual(data,expected);
      result.ranges.push({start,bytes:data.length,latencyMs:performance.now()-t0});
    }
    const frontPort=await port(),cdpPort=await port();
    const standalone=path.join(root,'frontend/.next/standalone');
    const next=child(process.execPath,[path.join(standalone,'server.js')],{cwd:standalone,env:{...process.env,PORT:String(frontPort),HOSTNAME:'127.0.0.1'}});
    next.stdout.resume();next.stderr.resume();
    await until(async()=>{const r=await fetch(`http://127.0.0.1:${frontPort}/`,{signal:AbortSignal.timeout(2000)});return r.ok;},'Next ready');
    const chrome=child('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless=new',`--remote-debugging-port=${cdpPort}`,`--user-data-dir=${path.join(local,'chrome')}`,'--autoplay-policy=no-user-gesture-required','--no-first-run','--disable-background-networking','--disable-extensions','--window-size=1280,800','about:blank']);
    chrome.stdout.resume();chrome.stderr.resume();
    const pages=await until(async()=>{const r=await fetch(`http://127.0.0.1:${cdpPort}/json/list`);const p=await r.json();return p.find(x=>x.type==='page');},'Chrome ready');
    ws=new WebSocket(pages.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true});});
    let id=0;const pending=new Map();result.browserResponses=[];
    function send(method,params={}){return new Promise((resolve,reject)=>{const n=++id;const timer=setTimeout(()=>{pending.delete(n);reject(new Error('CDP timeout '+method));},30000);pending.set(n,{resolve,reject,timer});ws.send(JSON.stringify({id:n,method,params}));});}
    ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(new Error(m.error.message)):p.resolve(m.result);}if(m.method==='Fetch.requestPaused'){const q=m.params;send('Fetch.continueRequest',{requestId:q.requestId,url:q.request.url.replace(/(localhost|127\.0\.0\.1):8080/,`127.0.0.1:${backend}`)}).catch(()=>{});}if(m.method==='Network.responseReceived'&&m.params.response.url.includes('/api/media/stream/')){result.browserResponses.push({url:m.params.response.url,status:m.params.response.status});}});
    async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
    await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
    await send('Fetch.enable',{patterns:[{urlPattern:'*localhost:8080/*'},{urlPattern:'*127.0.0.1:8080/*'}]});
    await send('Page.navigate',{url:`http://127.0.0.1:${frontPort}/movies/codex-real-drive-video`});
    await until(()=>evaluate(`!!document.querySelector('[data-testid="play-feature-btn"]:not(:disabled)')`),'production play button');
    const t0=performance.now();
    await evaluate(`document.querySelector('[data-testid="play-feature-btn"]').click()`);
    await until(()=>evaluate(`(()=>{const v=document.querySelector('video');return v&&v.videoWidth>0&&v.currentTime>1&&!v.paused;})()`),'actual decoded playback',45000);
    result.startupMs=performance.now()-t0;
    result.video=await evaluate(`(()=>{const v=document.querySelector('video');return {duration:v.duration,width:v.videoWidth,height:v.videoHeight,currentTime:v.currentTime,src:v.currentSrc};})()`);
    assert(Number.isFinite(result.video.duration)&&result.video.duration>5);
    for(const fraction of [.25,.6,.94]){
      const target=result.video.duration*fraction,t1=performance.now();
      await evaluate(`(()=>{const s=document.querySelector('[data-testid="video-timeline"]');if(!s)throw Error('timeline absent');const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;set.call(s,${target});s.dispatchEvent(new Event('input',{bubbles:true}));s.dispatchEvent(new Event('change',{bubbles:true}));})()`);
      await until(()=>evaluate(`(()=>{const v=document.querySelector('video');return !v.seeking&&Math.abs(v.currentTime-${target})<3&&v.readyState>=2;})()`),'UI seek '+fraction,30000);
      const frame=await evaluate(`new Promise((r,j)=>{const v=document.querySelector('video');const t=setTimeout(()=>j(Error('no decoded frame')),15000);v.requestVideoFrameCallback((n,m)=>{clearTimeout(t);r({mediaTime:m.mediaTime,presentedFrames:m.presentedFrames});});})`);
      result.seeks.push({fraction,target,latencyMs:performance.now()-t1,...frame});
    }
    await evaluate(`document.querySelector('[data-testid="video-play-pause-btn"]').click()`);assert(await evaluate('document.querySelector("video").paused'));
    await evaluate(`document.querySelector('[data-testid="video-play-pause-btn"]').click()`);await until(()=>evaluate('!document.querySelector("video").paused'),'resume');
    const shot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(evidence,'actual_drive_playback.png'),Buffer.from(shot.data,'base64'));
    await send('Emulation.setDeviceMetricsOverride',{width:375,height:667,deviceScaleFactor:1,mobile:true});
    await delay(250);
    result.mobile=await evaluate(`(()=>{const v=document.querySelector('video');return {width:innerWidth,height:innerHeight,videoWidth:v.videoWidth,currentTime:v.currentTime,controls:[...document.querySelectorAll('[data-testid="video-play-pause-btn"],[data-testid="video-volume-btn"],[data-testid="video-fullscreen-btn"]')].map(x=>{const r=x.getBoundingClientRect();return {testId:x.dataset.testid,width:r.width,height:r.height};})};})()`);
    assert(result.mobile.videoWidth>0);assert(result.mobile.controls.length>=2);
    assert(result.mobile.controls.every(x=>x.width>=44&&x.height>=44));
    const mobileShot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(evidence,'actual_drive_mobile.png'),Buffer.from(mobileShot.data,'base64'));
    assert(result.browserResponses.some(x=>x.status===206));result.pass=true;
  }catch(e){result.pass=false;result.error=e.stack;throw e;}
  finally{if(ws)ws.close();for(const p of owned.reverse()){if(p.stdin)p.stdin.end();if(p.exitCode===null)p.kill();}result.finishedAt=new Date().toISOString();fs.writeFileSync(path.join(evidence,'results.json'),JSON.stringify(result,null,2));}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
