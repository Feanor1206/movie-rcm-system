// Execute production MovieDetail using the handed hook harness; no browser claim.
const fs=require('node:fs'),path=require('node:path');
(async()=>{
  const file=path.resolve(__dirname,'../../../frontend/tests/media_playback_suite.mjs');
  let helpers=fs.readFileSync(file,'utf8').split("test('1. resolveStreamUrl")[0];
  helpers=helpers.replace('const __filename = fileURLToPath(import.meta.url);','const __filename = '+JSON.stringify(file)+';')
    .replace('const require = createRequire(import.meta.url);','const require = createRequire('+JSON.stringify(file)+');');
  helpers+='\nexport { createMovieDetailHarness, walk, findAll };';
  const {createMovieDetailHarness,findAll}=await import('data:text/javascript;base64,'+Buffer.from(helpers).toString('base64'));
  for(const legacy of [false,true]){
    let calls=0;
    const h=createMovieDetailHarness({getMediaDescriptor:async()=>{calls++;throw Error('fixture HTTP503')}});
    const movie={id:'A',title:'Movie A',genres:['Animation'],year:2026,rating:8,videoUrl:legacy?'https://fixture.invalid/legacy.mp4':null};
    h.render(movie);await new Promise(r=>setImmediate(r));h.render(movie);await new Promise(r=>setImmediate(r));h.render(movie);
    const nodes=findAll(h.getTree(),()=>true),buttons=nodes.filter(n=>n.type==='button');
    function text(n){if(n==null)return '';if(Array.isArray(n))return n.map(text).join(' ');if(typeof n==='object')return text(n.props?.children);return String(n)}
    console.log(JSON.stringify({legacy,descriptorCalls:calls,featureButton:buttons.some(n=>n.props?.['data-testid']==='play-feature-btn'),trailerButton:buttons.some(n=>n.props?.['data-testid']==='play-trailer-btn'),retryControls:buttons.filter(n=>/thử lại|tải lại|kết nối lại/i.test(text(n))).length,errorMessagePresent:nodes.some(n=>n.props?.role==='alert')}));
    h.unmount();
  }
})().catch(e=>{console.error(e);process.exitCode=1});
