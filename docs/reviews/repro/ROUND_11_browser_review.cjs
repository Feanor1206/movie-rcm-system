// Preserve submitted artifacts. Run actual harness with independent observer diagnostics.
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const Module=require('node:module');
const http=require('node:http');

(async()=>{
  await new Promise((resolve,reject)=>{const p=http.createServer();p.once('error',()=>reject(new Error('9222 occupied; refusing external CDP attach')));p.listen(9222,'127.0.0.1',()=>p.close(resolve));});
  const filename=path.resolve(__dirname,'../../../scripts/run_browser_walkthrough.cjs');
  let source=fs.readFileSync(filename,'utf8');
  const marker="const SCREENSHOTS_DIR = path.resolve(__dirname, '../docs/reports/screenshots/ROUND_11');";
  if(!source.includes(marker))throw new Error('Review source marker changed');
  const out=fs.mkdtempSync(path.join(os.tmpdir(),'codex-round11-review-'));
  console.log('Reviewer output directory: '+out);
  source=source.replace(marker,'const SCREENSHOTS_DIR = '+JSON.stringify(out)+';');
  source=source.replace("await cdp('Page.enable');",`await cdp('Page.enable');
    await cdp('Page.addScriptToEvaluateOnNewDocument',{source: \`window.__reviewPerf={lcp:null,shifts:[]};
      new PerformanceObserver(list=>{for(const e of list.getEntries())window.__reviewPerf.lcp=e.startTime;}).observe({type:'largest-contentful-paint',buffered:true});
      new PerformanceObserver(list=>{for(const e of list.getEntries())if(!e.hadRecentInput)window.__reviewPerf.shifts.push({time:e.startTime,value:e.value});}).observe({type:'layout-shift',buffered:true});\`});`);
  const metrics='              totalTransferBytes,';
  if(!source.includes(metrics))throw new Error('Review metrics marker changed');
  source=source.replace(metrics,`              totalTransferBytes,
              reviewerObserver: window.__reviewPerf || null,
              reviewerEntryCounts: {lcp:lcpEntries.length,cls:clsEntries.length},
              reviewerResources: resources.map(r=>({url:r.name,transfer:r.transferSize,encoded:r.encodedBodySize,decoded:r.decodedBodySize})),`);
  const shot="await browser.captureScreenshot('14_detail_mobile.png');";
  source=source.replace(shot,`const reviewedMobile=[];
    for(const scrollY of [0,200,400,600]) {
      await browser.evaluate('window.scrollTo(0,'+scrollY+')');
      await new Promise(resolve=>setTimeout(resolve,100));
      const data=await browser.evaluate(\`(() => {const f=document.querySelector('button[aria-label="Mở Chatbot CineBot"]');if(!f)return {missing:true};const a=f.getBoundingClientRect();return {scrollY:window.scrollY,overlaps:Array.from(document.querySelectorAll('button')).filter(b=>b!==f).map(b=>({label:b.getAttribute('aria-label')||b.textContent.trim(),r:b.getBoundingClientRect()})).filter(({r})=>r.width&&r.height&&r.top<innerHeight&&r.bottom>0&&r.left<a.right&&r.right>a.left&&r.top<a.bottom&&r.bottom>a.top).map(({label})=>label)};})()\`);
      reviewedMobile.push(data);
    }
    fs.writeFileSync(path.join(SCREENSHOTS_DIR,'review_mobile_scroll.json'),JSON.stringify(reviewedMobile,null,2));
    await browser.evaluate('window.scrollTo(0,0)');
    ${shot}`);
  const loaded=new Module(filename,module);loaded.filename=filename;loaded.paths=Module._nodeModulePaths(path.dirname(filename));loaded._compile(source,filename);
})().catch(e=>{console.error(e);process.exitCode=1;});
