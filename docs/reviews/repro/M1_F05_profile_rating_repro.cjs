const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {makeHarness,actor,ok}=require('./M1_runtime_repro.cjs');
const root=path.resolve(__dirname,'../../..');
const ts=require(path.join(root,'frontend/node_modules/typescript'));
const suite=fs.readFileSync(path.join(root,'frontend/tests/m1_behavior_suite.mjs'),'utf8');
// Reuse the component adapter, not a copy of the Profile implementation.
const adapter=suite.slice(suite.indexOf('function renderComponent('),suite.indexOf('const turn ='));
const sandbox={fs,ts,vm};vm.runInNewContext(adapter,sandbox);
async function main(){
 let backendRating=5,failRead=false;const methods=[];
 const auth={current:{...actor(1),handleSessionExpired:()=>{}}};
 const h=makeHarness('frontend/lib/context/WatchlistContext.tsx','WatchlistProvider',(url,opts)=>{
  if(opts?.method==='POST'){methods.push('POST');backendRating=JSON.parse(opts.body).rating;failRead=true;throw new TypeError('Lost response after rating commit');}
  if(opts?.method==='DELETE'){methods.push('DELETE');backendRating=null;return Promise.resolve(ok(null));}
  if(failRead)return Promise.resolve({ok:false,status:500});
  return Promise.resolve(ok(url.endsWith('ratings')?[{movieId:'M',rating:backendRating}]:[]));
 },auth);
 h.render();await h.settle();await h.value.rateMovie('M',9);await h.settle();
 const tree=sandbox.renderComponent(path.join(root,'frontend/features/profile/components/ProfileOverview.tsx'),'ProfileOverview',h.value,auth.current,{},['ratings',{M:{status:'found',movie:{id:'M',title:'Movie M',genres:[]}}}]);
 const button=sandbox.findElements(tree,n=>n.type==='button'&&n.props?.['aria-label']==='Chưa xác nhận điểm • Thử lưu lại điểm đánh giá')[0];
 if(!button)throw new Error('Expected retry-rating button not rendered');
 await button.props.onClick();await h.settle();
 console.log(JSON.stringify({label:button.props['aria-label'],methods,finalBackendRating:backendRating},null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
