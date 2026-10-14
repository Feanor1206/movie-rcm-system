// Reviewer-only: execute the real descriptor service with an aborting transport,
// then observe the production MovieDetail via the handed hook harness.
const fs=require('node:fs'),path=require('node:path');
(async()=>{
  const file=path.resolve(__dirname,'../../../frontend/tests/media_playback_suite.mjs');
  let helpers=fs.readFileSync(file,'utf8').split("test('1. resolveStreamUrl")[0];
  helpers=helpers.replace('const __filename = fileURLToPath(import.meta.url);','const __filename = '+JSON.stringify(file)+';')
    .replace('const require = createRequire(import.meta.url);','const require = createRequire('+JSON.stringify(file)+');');
  helpers+='\nexport { createMovieDetailHarness, loadMediaService, findAll };';
  const {createMovieDetailHarness,loadMediaService,findAll}=await import('data:text/javascript;base64,'+Buffer.from(helpers).toString('base64'));
  const service=loadMediaService((_url,{signal})=>new Promise((_resolve,reject)=>{
    const abort=()=>reject(signal.reason || new DOMException('Aborted','AbortError'));
    if(signal.aborted)abort();else signal.addEventListener('abort',abort,{once:true});
  }));
  let outcome;
  const h=createMovieDetailHarness({getMediaDescriptor:id=>service.getMediaDescriptor(id,{timeoutMs:20}).catch(e=>{outcome=e.name;throw e})});
  const movie={id:'timeout-fixture',title:'Timeout fixture',genres:['Animation'],rating:8,year:2026,videoUrl:null};
  h.render(movie);await new Promise(r=>setTimeout(r,65));h.render(movie);
  const nodes=findAll(h.getTree(),()=>true);
  console.log(JSON.stringify({serviceError:outcome,alertPresent:nodes.some(n=>n.props?.role==='alert'),retryPresent:nodes.some(n=>n.props?.['data-testid']==='descriptor-retry-btn'),source:'production service timeout + production component via hook harness'}));
  h.unmount();
  for(const [scenario,payload] of [['missing-required-fields',{}],['wrong-movie-id',{movieId:'different-movie',hasFeature:false,hasTrailer:false}]]){
    const malformedService=loadMediaService(async()=>({ok:true,status:200,json:async()=>payload}));
    const check=createMovieDetailHarness({getMediaDescriptor:id=>malformedService.getMediaDescriptor(id)});
    check.render(movie);await new Promise(r=>setImmediate(r));check.render(movie);
    const observed=findAll(check.getTree(),()=>true);
    console.log(JSON.stringify({scenario,alertPresent:observed.some(n=>n.props?.role==='alert'),retryPresent:observed.some(n=>n.props?.['data-testid']==='descriptor-retry-btn')}));
    check.unmount();
  }
})().catch(e=>{console.error(e);process.exitCode=1});
