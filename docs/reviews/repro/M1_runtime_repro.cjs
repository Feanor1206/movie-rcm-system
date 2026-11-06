// Reviewer-only harness: executes the actual TSX provider functions using a minimal
// deterministic hook adapter. No copied auth/library implementation, network or DB.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../../..');
const ts = require(path.join(root, 'frontend/node_modules/typescript'));
const turn = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; };
const ok = data => ({ok:true,status:200,json:async()=>({success:true,data})});
function makeHarness(file, provider, fetcher, auth) {
  const slots=[]; let index=0, effects=[], changed=false, value;
  const same = (a,b) => a && b && a.length===b.length && a.every((x,i)=>Object.is(x,b[i]));
  const hooks={
    createContext:()=>({Provider:'Provider'}), useContext:()=>null,
    useState(initial) { const i=index++; if(!slots[i]) slots[i]={v:typeof initial==='function'?initial():initial}; return [slots[i].v,v=>{slots[i].v=typeof v==='function'?v(slots[i].v):v;changed=true;}]; },
    useRef(initial) { const i=index++; if(!slots[i]) slots[i]={current:initial}; return slots[i]; },
    useCallback(fn,deps) { const i=index++; if(!slots[i] || !same(slots[i].deps,deps)) slots[i]={v:fn,deps}; return slots[i].v; },
    useEffect(fn,deps) { const i=index++; if(!slots[i] || !same(slots[i].deps,deps)) {const prev=slots[i]; slots[i]={deps,cleanup:prev?.cleanup};effects.push(()=>{slots[i].cleanup?.();slots[i].cleanup=fn();});} },
    createElement(type,props,...children) { return {type,props:{...props,children}}; }
  };
  const storage = new Map();
  const localStorage={getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,String(v)),removeItem:k=>storage.delete(k)};
  const timers = new Map(); let timerId=0;
  const module={exports:{}};
  const code=ts.transpileModule(fs.readFileSync(path.join(root,file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,esModuleInterop:true,target:ts.ScriptTarget.ES2020}}).outputText;
  const context={module,exports:module.exports,process:{env:{}},console,AbortController,DOMException,fetch:fetcher,window:{},localStorage,
    setTimeout:(fn,ms)=>{const id=++timerId;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id),
    require:name=> name==='react'?{__esModule:true,default:hooks,...hooks}:name==='./AuthContext'?{useAuth:()=>auth.current}:{} };
  vm.runInNewContext(code,context,{filename:file});
  function render() { index=0;changed=false; value=module.exports[provider]({children:null}).props.value; const pending=effects;effects=[];pending.forEach(fn=>fn());return value; }
  async function settle() { for(let i=0;i<6;i++){await turn(); if(changed || i===0)render();}return value; }
  return {render,settle,storage,get value(){return value;},timers};
}
const authFile='frontend/lib/context/AuthContext.tsx';
const libFile='frontend/lib/context/WatchlistContext.tsx';
const actor=id=>({user:{id,username:'user'+id},token:'token'+id,status:'authenticated',isAuthenticated:true});
async function main() {
  const findings=[];
  // Actual login: headers arrive, JSON body remains pending, logout, body arrives.
  {
    const body=deferred(); const h=makeHarness(authFile,'AuthProvider',async()=>({ok:true,status:200,json:()=>body.promise}));
    h.render();await h.settle();const login=h.value.login('alice',' raw password ');await turn();h.value.logout();await h.settle();
    body.resolve({success:true,data:{id:1,username:'alice',email:'a@example.test',token:'fake-test-token'}});await login;await h.settle();
    findings.push({scenario:'logout while response JSON is pending',status:h.value.status,storedToken:h.storage.has('dippie_auth_token')});
  }
  // Actual mutation failure from A executes after B has loaded.
  {
    const write=deferred();const auth={current:actor(1)};
    const h=makeHarness(libFile,'WatchlistProvider',(url,opts)=>opts?.method?write.promise:Promise.resolve(ok(url.endsWith('watchlist')?[{movieId:auth.current.user.id===1?'A-private-film':'B-film'}]:[])),auth);
    h.render();await h.settle();const mutation=h.value.toggleWatchlist('A-new-film');await h.settle();
    auth.current=actor(2);h.render();await h.settle();const before=[...h.value.watchlist];
    write.reject(new Error('A write failed late'));await mutation;await h.settle();
    findings.push({scenario:'A mutation fails after B loads',before,after:[...h.value.watchlist]});
  }
  // Two independent writes: X fails after Y succeeded, snapshot rollback erases Y.
  {
    const x=deferred();const auth={current:actor(1)};
    const h=makeHarness(libFile,'WatchlistProvider',(url,opts)=>!opts?.method?Promise.resolve(ok([])):JSON.parse(opts.body).movieId==='X'?x.promise:Promise.resolve(ok({})),auth);
    h.render();await h.settle();const writeX=h.value.toggleWatchlist('X');await h.settle();await h.value.toggleWatchlist('Y');await h.settle();
    const before=[...h.value.watchlist];x.reject(new Error('X fails'));await writeX;await h.settle();
    findings.push({scenario:'failed X rollback removes successful Y',before,after:[...h.value.watchlist]});
  }
  // Unavailable verification is treated as guest for mutations.
  {
    const auth={current:{...actor(1),status:'unavailable',isAuthenticated:false}};
    const h=makeHarness(libFile,'WatchlistProvider',()=>{throw new Error('unexpected fetch');},auth);
    h.render();await h.settle();await h.value.toggleWatchlist('account-click');await h.settle();
    findings.push({scenario:'unavailable session write',isGuestMode:h.value.isGuestMode,guestStorage:JSON.parse(h.storage.get('dippie_guest_library_v1'))});
  }
  // Auth payload validation: no username/email, non-string token still accepted.
  {
    const h=makeHarness(authFile,'AuthProvider',async()=>ok({id:'bad-id',token:{unexpected:true}}));h.render();await h.settle();
    await h.value.login('alice','password');await h.settle();
    findings.push({scenario:'invalid identity/token types',status:h.value.status,user:h.value.user});
  }
  // HTTP 401 mutation leaves session unchanged; there is no mutation timeout.
  {
    const auth={current:actor(1)};
    const h=makeHarness(libFile,'WatchlistProvider',(url,opts)=>opts?.method?Promise.resolve({ok:false,status:401}):Promise.resolve(ok([])),auth);
    h.render();await h.settle();await h.value.toggleWatchlist('X');await h.settle();
    findings.push({scenario:'library 401',authStatus:auth.current.status});
  }
  {
    const pending=deferred();const auth={current:actor(1)};let writes=0;
    const h=makeHarness(libFile,'WatchlistProvider',(url,opts)=>{if(opts?.method){writes++;return pending.promise;}return Promise.resolve(ok([]));},auth);
    h.render();await h.settle();const fn=h.value.toggleWatchlist;const a=fn('X');const b=fn('X');await h.settle();
    findings.push({scenario:'duplicate writes before rerender / mutation timeout',writes,activeTimerMs:[...h.timers.values()].map(x=>x.ms),pending:h.value.isActionPending('X')});
    pending.resolve(ok({}));await Promise.all([a,b]);
  }
  console.log(JSON.stringify(findings,null,2));
}
module.exports={makeHarness,actor,ok,deferred,turn};
if(require.main===module) main().catch(err=>{console.error(err);process.exitCode=1;});
