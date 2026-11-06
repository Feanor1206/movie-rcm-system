// Reviewer adapter executes actual SearchExperience; no copy of search logic.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../../..'),ts=require(path.join(root,'frontend/node_modules/typescript'));
const file=path.join(root,'frontend/features/search/components/SearchExperience.tsx');
const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,esModuleInterop:true,target:ts.ScriptTarget.ES2022}}).outputText;
const turn=()=>new Promise(r=>setImmediate(r));
const page=()=>({items:[],page:0,size:12,totalElements:0,totalPages:0,hasNext:false,hasPrevious:false});
function harness(url,browse){
 let params=new URLSearchParams(url),slots=[],i=0,effects=[],dirty=false,tree;const pushes=[],timers=new Map();let tid=0;
 const same=(a,b)=>a&&b&&a.length===b.length&&a.every((x,j)=>Object.is(x,b[j]));
 const hooks={
  useState(v){const n=i++;if(!slots[n])slots[n]={v:typeof v==='function'?v():v};return [slots[n].v,x=>{slots[n].v=typeof x==='function'?x(slots[n].v):x;dirty=true;}];},
  useRef(v){const n=i++;return slots[n]||(slots[n]={current:v});},
  useMemo(fn,deps){const n=i++;if(!slots[n]||!same(slots[n].deps,deps))slots[n]={v:fn(),deps};return slots[n].v;},
  useCallback(fn,deps){return hooks.useMemo(()=>fn,deps);},
  useEffect(fn,deps){const n=i++;if(!slots[n]||!same(slots[n].deps,deps)){const old=slots[n];slots[n]={deps,cleanup:old?.cleanup};effects.push(()=>{slots[n].cleanup?.();slots[n].cleanup=fn();});}},
  createElement(type,props,...children){return {type,props:{...props,children}};}
 };
 const router={push:u=>pushes.push(u)},module={exports:{}};
 const ctx={module,exports:module.exports,URLSearchParams,AbortController,console,setTimeout:(fn,ms)=>{const n=++tid;timers.set(n,{fn,ms});return n;},clearTimeout:n=>timers.delete(n),require:n=>{
  if(n==='react')return {__esModule:true,default:hooks,...hooks};
  if(n==='next/navigation')return {useSearchParams:()=>params,useRouter:()=>router,usePathname:()=>'/search'};
  if(n.includes('catalogService'))return {browseCatalog:browse};
  if(n.includes('WatchlistContext'))return {useWatchlist:()=>({openChat:()=>{}})};
  if(n==='lucide-react')return new Proxy({},{get:(_,key)=>key});
  if(n.includes('MovieCard'))return {MovieCard:'MovieCard'};
  return {};
 }};
 vm.runInNewContext(code,ctx,{filename:file});
 function render(){i=0;dirty=false;tree=module.exports.SearchExperience();const pending=effects;effects=[];pending.forEach(fn=>fn());return tree;}
 async function settle(){for(let n=0;n<6;n++){await turn();if(dirty||n===0)render();}return tree;}
 return {render,settle,pushes,timers,navigate:u=>{params=new URLSearchParams(u);render();},get tree(){return tree;}};
}
function find(node,pred,out=[]){if(!node)return out;if(Array.isArray(node)){node.forEach(x=>find(x,pred,out));return out;}if(typeof node==='object'){if(pred(node))out.push(node);find(node.props?.children,pred,out);}return out;}
function text(node){if(Array.isArray(node))return node.map(text).join(' ');if(node&&typeof node==='object')return text(node.props?.children);return typeof node==='string'||typeof node==='number'?String(node):'';}
async function main(){const results=[];
 {
  const h=harness('q=A',async()=>page());h.render();await h.settle();
  find(h.tree,n=>n.type==='input')[0].props.onChange({target:{value:'B'}});await h.settle();
  const timer=[...h.timers.entries()].find(([,t])=>t.ms===350);h.timers.delete(timer[0]);timer[1].fn();
  find(h.tree,n=>n.type==='input')[0].props.onChange({target:{value:'C'}});await h.settle();
  const before=find(h.tree,n=>n.type==='input')[0].props.value;
  h.navigate('q=B');await h.settle();
  results.push({scenario:'delayed router update B arrives after user typed C',pushes:h.pushes,before,after:find(h.tree,n=>n.type==='input')[0].props.value});
 }
 {
  const h=harness('q=old',o=>o.query==='new'?new Promise(()=>{}):Promise.resolve(page()));h.render();await h.settle();
  h.navigate('q=new');await h.settle();const rendered=text(h.tree);
  results.push({scenario:'old empty data while new query pending',showsNoResultsForNew:rendered.includes('Không có phim hoạt hình nào khớp với từ khóa "new".'),showsLoading:rendered.includes('Đang cập nhật')});
 }
 {
  let options;const h=harness('q=film&yearMin=2000&yearMax=2005&size=2',async o=>{options=o;return page();});h.render();await h.settle();
  results.push({scenario:'year and size URL options sent to browseCatalog',yearMin:options.yearMin??null,yearMax:options.yearMax??null,size:options.size});
 }
 console.log(JSON.stringify(results,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
