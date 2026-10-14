// Reviewer-only source execution. No application files, network or DB changes.
const {makeHarness,actor,ok,deferred,turn}=require('./M1_runtime_repro.cjs');
const file='frontend/lib/context/WatchlistContext.tsx';
async function main(){
 const results=[];
 // Old A request with 401 invokes expiry callback before any actor guard.
 {
  const pending=deferred();let expired=0;
  const auth={current:{...actor(1),handleSessionExpired:()=>expired++}};
  const h=makeHarness(file,'WatchlistProvider',(u,o)=>o?.method?pending.promise:Promise.resolve(ok([])),auth);
  h.render();await h.settle();const a=h.value.toggleWatchlist('X');await h.settle();
  auth.current={...actor(2),handleSessionExpired:()=>expired++};h.render();await h.settle();
  pending.resolve({ok:false,status:401});await a;await h.settle();
  results.push({scenario:'late A 401 after B authenticated',expiryCalls:expired});
 }
 // First value returned by provider render after actor changes still contains A.
 {
  const auth={current:{...actor(1),handleSessionExpired:()=>{}}};
  const h=makeHarness(file,'WatchlistProvider',u=>Promise.resolve(ok(u.endsWith('watchlist')?[{movieId:'A-private-film'}]:[])),auth);
  h.render();await h.settle();auth.current={...actor(2),handleSessionExpired:()=>{}};
  const firstB=h.render();results.push({scenario:'first B render before effect-driven rerender',watchlist:[...firstB.watchlist]});
 }
 // Same-actor refresh increments mutation generation, leaving UI pending stuck.
 {
  const pending=deferred();const auth={current:{...actor(1),handleSessionExpired:()=>{}}};
  const h=makeHarness(file,'WatchlistProvider',(u,o)=>o?.method?pending.promise:Promise.resolve(ok([])),auth);
  h.render();await h.settle();const a=h.value.toggleWatchlist('X');await h.settle();
  await h.value.refetchLibrary();await h.settle();pending.resolve(ok({movieId:'X'}));await a;await h.settle();
  results.push({scenario:'refresh while same-actor mutation pending',pending:h.value.isActionPending('X'),watchlist:[...h.value.watchlist]});
 }
 // Old A finally deletes B synchronous lock for the same key.
 {
  const aPending=deferred(),bPending=deferred();let bWrites=0;
  const auth={current:{...actor(1),handleSessionExpired:()=>{}}};
  const h=makeHarness(file,'WatchlistProvider',(u,o)=>!o?.method?Promise.resolve(ok([])):o.headers.Authorization==='Bearer token1'?aPending.promise:(bWrites++,bPending.promise),auth);
  h.render();await h.settle();const a=h.value.toggleWatchlist('X');await h.settle();
  auth.current={...actor(2),handleSessionExpired:()=>{}};h.render();await h.settle();
  const b=h.value.toggleWatchlist('X');await h.settle();aPending.reject(new Error('late A failed'));await a;await h.settle();
  const duplicate=h.value.toggleWatchlist('X');await h.settle();results.push({scenario:'A finally releases B same-item lock',bWrites});
  bPending.resolve(ok({movieId:'X'}));await Promise.all([b,duplicate]);
 }
 // Headers clear timeout while JSON remains deferred.
 {
  const body=deferred();const auth={current:{...actor(1),handleSessionExpired:()=>{}}};
  const h=makeHarness(file,'WatchlistProvider',(u,o)=>o?.method?Promise.resolve({ok:true,status:200,json:()=>body.promise}):Promise.resolve(ok([])),auth);
  h.render();await h.settle();const a=h.value.toggleWatchlist('X');await h.settle();
  results.push({scenario:'mutation body pending after headers',pending:h.value.isActionPending('X'),activeTimerMs:[...h.timers.values()].map(x=>x.ms)});
  body.resolve({success:true,data:{movieId:'X'}});await a;
 }
 console.log(JSON.stringify(results,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
