const {makeHarness,actor,ok,deferred}=require('./M1_runtime_repro.cjs');
const file='frontend/lib/context/WatchlistContext.tsx';
const user=()=>({...actor(1),handleSessionExpired:()=>{}});
async function main(){
 const results=[];
 {
  const write=deferred(),body=deferred();let refreshing=false;const auth={current:user()};
  const h=makeHarness(file,'WatchlistProvider',(u,o)=>o?.method?write.promise:refreshing&&u.endsWith('watchlist')?Promise.resolve({ok:true,status:200,json:()=>body.promise}):Promise.resolve(ok([])),auth);
  h.render();await h.settle();const mutation=h.value.toggleWatchlist('X');await h.settle();
  refreshing=true;const read=h.value.refetchLibrary();await h.settle();
  write.resolve(ok({movieId:'X'}));await mutation;await h.settle();const before=[...h.value.watchlist];
  body.resolve({success:true,data:[]});await read;await h.settle();
  results.push({scenario:'write pending -> read starts -> write commits -> old read body arrives',before,after:[...h.value.watchlist]});
 }
 {
  let backend=[],failReconcile=false;const methods=[];const auth={current:user()};
  const h=makeHarness(file,'WatchlistProvider',(u,o)=>{
   if(o?.method==='POST'){methods.push('POST');backend=['X'];failReconcile=true;throw new TypeError('Response lost after commit');}
   if(o?.method==='DELETE'){methods.push('DELETE');backend=[];return Promise.resolve(ok(null));}
   if(failReconcile)return Promise.resolve({ok:false,status:500});
   return Promise.resolve(ok([]));
  },auth);
  h.render();await h.settle();await h.value.toggleWatchlist('X');await h.settle();
  const failedReconcile={watchlist:[...h.value.watchlist],pending:h.value.isActionPending('X'),error:h.value.libraryError};
  await h.value.toggleWatchlist('X');await h.settle();
  results.push({scenario:'committed add loses response, reconcile fails, user retries toggle',failedReconcile,methods,finalBackend:backend});
 }
 console.log(JSON.stringify(results,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
