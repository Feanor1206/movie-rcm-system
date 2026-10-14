// Reviewer-only wrapper: redirect frozen evidence, add targeted DOM diagnostics.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const Module = require('node:module');

async function reviewerAuthAudit(browser) {
  await browser.evaluate(`(() => {
    const d=document.querySelector('[role="dialog"]');
    const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    for (const [selector,value] of [['input[type="text"]','codex_invalid'],['input[type="password"]','not-real-password']]) {
      const input=d.querySelector(selector); set.call(input,value);
      input.dispatchEvent(new Event('input',{bubbles:true})); input.dispatchEvent(new Event('change',{bubbles:true}));
    }
    d.querySelector('button[type="submit"]').click();
  })()`);
  await browser.waitForCondition(`document.body.textContent.includes('Reviewer invalid credentials')`, 'expected test login failure');
  const closeSize = await browser.evaluate(`(() => {const b=document.querySelector('button[aria-label="Đóng popup"]');const r=b.getBoundingClientRect();return {width:r.width,height:r.height};})()`);
  await browser.evaluate(`document.querySelector('button[aria-label="Đóng popup"]').click()`);
  await new Promise(r=>setTimeout(r,100));
  const restored = await browser.evaluate(`document.activeElement===window.__reviewLoginOpener`);
  reviewDiagnostics.push({scenario:'Auth failed submit then close', restoredToOpener:restored, closeSize});
  await browser.evaluate(`(() => {const b=Array.from(document.querySelectorAll('header button')).find(b=>b.textContent.includes('Đăng nhập'));b.focus();window.__reviewLoginOpener=b;b.click();})()`);
  await browser.waitForSelector('[role="dialog"]');
  await new Promise(r=>setTimeout(r,100));
}

async function reviewerDetailAudit(browser) {
  await browser.evaluate(`(() => {const b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Xem trailer'));if(!b)throw new Error('Expected trailer button');b.focus();window.__reviewPlay=b;b.click();})()`);
  await browser.waitForSelector('[role="dialog"] video');
  await new Promise(r=>setTimeout(r,100));
  const insideInitial = await browser.evaluate(`document.querySelector('[role="dialog"]').contains(document.activeElement)`);
  await browser.dispatchKey('Tab','Tab',9);
  const insideAfterTab = await browser.evaluate(`document.querySelector('[role="dialog"]').contains(document.activeElement)`);
  reviewDiagnostics.push({scenario:'Player open and Tab',insideInitial,insideAfterTab});
  await browser.dispatchKey('Escape','Escape',27);
  await browser.cdp('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  await browser.evaluate(`(() => {window.__reviewScrollCalls=[];window.__reviewScrollOriginal=Element.prototype.scrollIntoView;Element.prototype.scrollIntoView=function(options){window.__reviewScrollCalls.push(options);};const b=Array.from(document.querySelectorAll('header button')).find(b=>b.textContent.includes('Hỏi CineBot'));b.focus();window.__reviewChatOpener=b;b.click();})()`);
  await browser.waitForSelector('[role="dialog"] input');
  await new Promise(r=>setTimeout(r,100));
  const scrollCalls = await browser.evaluate('window.__reviewScrollCalls');
  await browser.dispatchKey('Escape','Escape',27);
  await new Promise(r=>setTimeout(r,100));
  const restored = await browser.evaluate('document.activeElement===window.__reviewChatOpener');
  reviewDiagnostics.push({scenario:'CineBot reduce-motion and close',scrollCalls,restoredToOpener:restored});
  await browser.evaluate('Element.prototype.scrollIntoView=window.__reviewScrollOriginal');
  await browser.cdp('Emulation.setEmulatedMedia',{features:[]});
}

async function main() {
  await new Promise((resolve,reject)=>{const probe=http.createServer();probe.once('error',()=>reject(new Error('9222 occupied; do not attach')));probe.listen(9222,'127.0.0.1',()=>probe.close(resolve));});
  const filename=path.resolve(__dirname,'../../../scripts/run_browser_walkthrough.cjs');
  let source=fs.readFileSync(filename,'utf8');
  const declaration="const SCREENSHOTS_DIR = path.resolve(__dirname, '../docs/reports/screenshots/ROUND_10');";
  if(!source.includes(declaration)) throw new Error('Review output marker changed');
  const output=fs.mkdtempSync(path.join(os.tmpdir(),'codex-round10-review-'));
  console.log('Reviewer output directory: '+output);
  source=source.replace(declaration,'const SCREENSHOTS_DIR = '+JSON.stringify(output)+';');
  // Add one rejected-credentials case to fixture only, exercising production modal.
  const loginMarker="const isUserB = body.username === 'user_b';";
  if(!source.includes(loginMarker)) throw new Error('Fixture login marker changed');
  source=source.replace(loginMarker,"if(body.usernameOrEmail==='codex_invalid'){res.writeHead(401,{'Content-Type':'application/json'});return res.end(JSON.stringify({success:false,message:'Reviewer invalid credentials'}));}\n"+loginMarker);
  source=source.replace('loginBtn.click();','loginBtn.focus(); window.__reviewLoginOpener=loginBtn; loginBtn.click();');
  const loginStep="console.log('[Step 03] Submitting login form as user_a...');";
  source=source.replace(loginStep,'await reviewerAuthAudit(browser);\n'+loginStep);
  source=source.replace("await browser.captureScreenshot('04_detail_saved_rated_user_a.png');", "await reviewerDetailAudit(browser); fs.writeFileSync(path.join(SCREENSHOTS_DIR,'review_diagnostics.json'),JSON.stringify(reviewDiagnostics,null,2)); await browser.captureScreenshot('04_detail_saved_rated_user_a.png');");
  source=source.replace("await browser.captureScreenshot('14_detail_mobile.png');",`{
      const collisions=await browser.evaluate(\`(() => {const all=Array.from(document.querySelectorAll('button'));const f=all.find(b=>b.className.includes('fixed')&&b.textContent.includes('Hỏi CineBot'));if(!f)return [];const a=f.getBoundingClientRect();return all.filter(b=>b!==f).map(b=>({label:b.getAttribute('aria-label')||b.textContent.trim(),r:b.getBoundingClientRect()})).filter(({r})=>r.width&&r.height&&r.top<innerHeight&&r.bottom>0&&a.left<r.right&&a.right>r.left&&a.top<r.bottom&&a.bottom>r.top).map(({label,r})=>({label,width:r.width,height:r.height}));})()\`);
      reviewDiagnostics.push({scenario:'Floating trigger overlaps controls at 375px',collisions});
    fs.writeFileSync(path.join(SCREENSHOTS_DIR,'review_diagnostics.json'),JSON.stringify(reviewDiagnostics,null,2));
    await browser.captureScreenshot('14_detail_mobile.png');
  }`);
  source=source.replace('await reviewerAuthAudit(browser);', "await reviewerAuthAudit(browser); fs.writeFileSync(path.join(SCREENSHOTS_DIR,'review_diagnostics.json'),JSON.stringify(reviewDiagnostics,null,2));");
  source='const reviewDiagnostics=[];\n'+reviewerAuthAudit.toString()+'\n'+reviewerDetailAudit.toString()+'\n'+source;
  const loaded=new Module(filename,module);loaded.filename=filename;loaded.paths=Module._nodeModulePaths(path.dirname(filename));loaded._compile(source,filename);
}
main().catch(e=>{console.error(e);process.exitCode=1;});
