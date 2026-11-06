// Additional reviewer fault injection. Production UI/client unchanged.
// CDP holds or fulfills descriptor requests only; native fetch/abort and UI retry run normally.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),Module=require('node:module');
const file=path.resolve(__dirname,'../../../scripts/run_m4_media_walkthrough.cjs');
let source=fs.readFileSync(file,'utf8');
// Reviewer-only startup allowance; original 4-second poll failed before UI tests.
source=source.replace('for (let i = 0; i < 40; i++) {','for (let i = 0; i < 150; i++) {');
const output=fs.mkdtempSync(path.join(os.tmpdir(),'codex-m4-f03-faults-'));
source=source.replace("const SCREENSHOTS_DIR = path.resolve(PROJECT_ROOT, 'docs/reports/screenshots/M4_F03');",'const SCREENSHOTS_DIR = '+JSON.stringify(output)+';')
 .replace("const BENCHMARK_OUT = path.resolve(PROJECT_ROOT, 'docs/reports/m4_f03_benchmark_results.json');",'const BENCHMARK_OUT = '+JSON.stringify(path.join(output,'benchmark.json'))+';')
 .replace("const PROJECT_ROOT =",'let reviewerDescriptorFault = null;\nconst PROJECT_ROOT =');
const paused='const originalUrl = request.url;';
if(!source.includes(paused))throw Error('Fetch event marker changed');
source=source.replace(paused,paused+String.raw`
      if (reviewerDescriptorFault && originalUrl.includes('/media-descriptor')) {
        if (reviewerDescriptorFault === 'timeout') return; // deliberately hold network request until native client abort
        const payload = reviewerDescriptorFault === 'malformed' ? {} : {movieId:'wrong-review-fixture',hasFeature:false,hasTrailer:false};
        ws.send(JSON.stringify({id:idCounter++,method:'Fetch.fulfillRequest',params:{requestId,responseCode:200,responseHeaders:[{name:'Content-Type',value:'application/json'},{name:'Access-Control-Allow-Origin',value:'*'}],body:Buffer.from(JSON.stringify(payload)).toString('base64')}}));
        return;
      }
`);
const marker='// A3. Open player modal by clicking';
if(!source.includes(marker))throw Error('Happy path marker changed');
source=source.replace(marker,String.raw`
    const reviewerFaultResults=[];
    for(const fault of ['timeout','malformed','mismatch']) {
      reviewerDescriptorFault=fault;
      const start=Date.now();
      await navigate(movieUrl);
      await waitForCondition("Boolean(document.querySelector('[role=alert]') && document.querySelector('[data-testid=descriptor-retry-btn]'))",'reviewer '+fault+' visible error/retry',12000);
      assert.equal(await evaluate("Boolean(document.querySelector('[data-testid=play-feature-btn]'))"),false,'Invalid descriptor must not advertise feature');
      const failureElapsed=Date.now()-start;
      reviewerDescriptorFault=null;
      await evaluate("document.querySelector('[data-testid=descriptor-retry-btn]').click()");
      await waitForCondition("Boolean(document.querySelector('[data-testid=play-feature-btn]')) && !document.querySelector('[role=alert]')",'reviewer '+fault+' retry recovery',8000);
      reviewerFaultResults.push({fault,errorAndRetry:true,featureAbsentOnFailure:true,recoveredByUiRetry:true,failureElapsedMs:failureElapsed});
      console.log('REVIEWER_BROWSER_FAULT '+JSON.stringify(reviewerFaultResults[reviewerFaultResults.length-1]));
    }
    fs.writeFileSync(path.join(SCREENSHOTS_DIR,'descriptor_faults.json'),JSON.stringify(reviewerFaultResults,null,2));
    // A3. Open player modal by clicking
`);
console.log('Reviewer additional fault output: '+output);
const loaded=new Module(file,module);loaded.filename=file;loaded.paths=Module._nodeModulePaths(path.dirname(file));loaded._compile(source,file);
