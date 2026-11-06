const {makeHarness,actor,ok,deferred}=require('./M1_runtime_repro.cjs');
const file='frontend/lib/context/WatchlistContext.tsx';
const user=id=>({...actor(id),handleSessionExpired:()=>{}});
async function main(){
 const results=[];
 {
  const auth={current:{user:null,token:null,status:'checking',isAuthenticated:false,handleSessionExpired:()=>{}}};
  const h=makeHarness(file,'WatchlistProvider',u=>Promise.resolve(ok(u.endsWith('watchlist')?[{movieId:'A-saved-film'}]:[])),auth);
  h.render();await h.settle();auth.current=user(1);h.render();await h.settle();
  results.push({scenario:'boot checking to verified A, backend nonempty',watchlist:[...h.value.watchlist],loading:h.value.isLibraryLoading,error:h.value.libraryError});
 }
 {
  const auth={current:user(1)};
  const h=makeHarness(file,'WatchlistProvider',u=>Promise.resolve(ok(u.endsWith('watchlist')?[{movieId:auth.current.user.id===1?'A-film':'B-saved-film'}]:[])),auth);
  h.render();await h.settle();auth.current=user(2);h.render();await h.settle();
  results.push({scenario:'A to B, backend B nonempty',watchlist:[...h.value.watchlist],loading:h.value.isLibraryLoading,error:h.value.libraryError});
 }
 {
  const oldBody=deferred();let refreshing=false;const auth={current:user(1)};
  const h=makeHarness(file,'WatchlistProvider',(u,o)=>o?.method?Promise.resolve(ok({movieId:'X'})):refreshing&&u.endsWith('watchlist')?Promise.resolve({ok:true,status:200,json:()=>oldBody.promise}):Promise.resolve(ok([])),auth);
  h.render();await h.settle();refreshing=true;const read=h.value.refetchLibrary();await h.settle();
  await h.value.toggleWatchlist('X');await h.settle();const before=[...h.value.watchlist];
  oldBody.resolve({success:true,data:[]});await read;await h.settle();
  results.push({scenario:'older refresh body arrives after successful add',before,after:[...h.value.watchlist]});
 }
 {
  const pending=deferred();const auth={current:user(1)};
  const h=makeHarness(file,'WatchlistProvider',(u,o)=>o?.method?pending.promise:Promise.resolve(ok(u.endsWith('watchlist')?[{movieId:'X'}]:[])),auth);
  h.render();await h.settle();const deletion=h.value.toggleWatchlist('X');await h.settle();await h.value.refetchLibrary();await h.settle();
  pending.resolve(ok(null));await deletion;await h.settle();
  results.push({scenario:'refresh during delete followed by delete success',watchlist:[...h.value.watchlist]});
 }
 console.log(JSON.stringify(results,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
