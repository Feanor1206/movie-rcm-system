const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../../..');
const ts=require(path.join(root,'frontend/node_modules/typescript'));
const src=fs.readFileSync(path.join(root,'frontend/lib/services/catalogService.ts'),'utf8');
const compiled=ts.transpileModule(src,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
function load(fetch){const module={exports:{}},timers=new Map();let timerId=0;const ctx={module,exports:module.exports,fetch,process:{env:{}},URLSearchParams,AbortController,setTimeout:(fn,ms)=>{const id=++timerId;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id)};vm.runInNewContext(compiled,ctx);return {api:module.exports,timers};}
async function main(){
 const results=[];
 {
  let resolveBody,requestSignal;const body=new Promise(r=>resolveBody=r),external=new AbortController();
  const h=load(async(u,o)=>{requestSignal=o.signal;return {ok:true,status:200,json:()=>body};});
  const request=h.api.browseCatalog({timeoutMs:50,signal:external.signal});
  for(let i=0;i<6;i++)await Promise.resolve();
  external.abort();
  results.push({scenario:'headers received, body pending, caller aborts',activeTimers:h.timers.size,transportAborted:requestSignal.aborted});
  resolveBody({success:true,data:{items:[],page:0,size:12,totalElements:0,totalPages:0,hasNext:false,hasPrevious:false}});await request;
 }
 {
  const h=load(async()=>({ok:true,status:200,json:async()=>({success:true,data:{}})}));
  results.push({scenario:'malformed paginated success accepted',result:await h.api.browseCatalog()});
  results.push({scenario:'missing movie fields normalized',result:h.api.normalizeCatalogMovie({})});
 }
 {
  const h=load(async()=>({ok:true,status:200,json:async()=>({success:true,data:{id:'other-movie',title:'Other',year:2001,rating:8,genres:['Animation']}})}));
  results.push({scenario:'requested movie ID not equal response movie ID',result:await h.api.getCatalogMovieById('requested-movie')});
 }
 console.log(JSON.stringify(results,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
