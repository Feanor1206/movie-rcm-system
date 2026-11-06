// Independent build-byte audit. Recompute files each run, never trust a size table.
const fs=require('node:fs');
const path=require('node:path');
const zlib=require('node:zlib');
const crypto=require('node:crypto');
const build=path.resolve(__dirname,'../../../frontend/.next');
const manifest=JSON.parse(fs.readFileSync(path.join(build,'app-build-manifest.json'),'utf8'));
const routes={'/':'/page','/search':'/search/page','/movies/[id]':'/movies/[id]/page','/profile':'/profile/page'};
const result={buildId:fs.readFileSync(path.join(build,'BUILD_ID'),'utf8').trim(),method:'unique app /layout + route manifest JavaScript; raw bytes and sum of individually gzipped files; excludes CSS/polyfills/RSC/API, not HTTP wire bytes',routes:{}};
for(const [route,key] of Object.entries(routes)){
  if(!manifest.pages[key])throw new Error('Missing route manifest entry '+key);
  const names=[...new Set([...(manifest.pages['/layout']||[]),...manifest.pages[key]])].filter(n=>n.endsWith('.js'));
  const files=names.map(name=>{const bytes=fs.readFileSync(path.join(build,name));return {name,raw:bytes.length,gzip:zlib.gzipSync(bytes).length,sha256:crypto.createHash('sha256').update(bytes).digest('hex')};});
  result.routes[route]={raw:files.reduce((n,f)=>n+f.raw,0),gzip:files.reduce((n,f)=>n+f.gzip,0),budget:140*1024,files};
  result.routes[route].underBudget=result.routes[route].gzip<=result.routes[route].budget;
}
process.stdout.write(JSON.stringify(result,null,2)+'\n');
