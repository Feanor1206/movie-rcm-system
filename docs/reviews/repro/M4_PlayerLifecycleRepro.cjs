// Reviewer source-execution repro; fake DOM/media refs, not browser playback evidence.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ts=require(path.resolve(__dirname,'../../../frontend/node_modules/typescript'));
const file=path.resolve(__dirname,'../../../frontend/features/movies/components/MovieDetail.tsx');
const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,esModuleInterop:true}}).outputText;
let slots=[],index=0,effects=[],tree;
const turn=()=>new Promise(r=>setImmediate(r));
const opener={focusCount:0,focus(){this.focusCount++}};
const doc={activeElement:opener,body:{style:{overflow:''}},fullscreenElement:null};
const hooks={
 useState(v){const i=index++;if(!slots[i])slots[i]={value:typeof v==='function'?v():v};return [slots[i].value,x=>slots[i].value=typeof x==='function'?x(slots[i].value):x]},
 useRef(v){const i=index++;return slots[i]||(slots[i]={current:v})},
 useEffect(fn,deps){const i=index++;const prev=slots[i];if(!prev||!deps||deps.some((d,k)=>!Object.is(d,prev.deps[k]))){effects.push(()=>{prev?.cleanup?.();slots[i]={deps,cleanup:fn()}})}},
 createElement(type,props,...children){return {type,props:{...props,children:children.length===1?children[0]:children}}}
};
const context={exports:{},document:doc,window:{addEventListener(){},removeEventListener(){}},setTimeout,clearTimeout,console,
 require(name){if(name==='react')return {__esModule:true,default:hooks,...hooks};if(name==='next/image'||name==='next/link')return {__esModule:true,default:name};
 if(name==='lucide-react')return new Proxy({},{get:(_,key)=>String(key)});
 if(name.includes('WatchlistContext'))return {useWatchlist:()=>({isWatchlisted:()=>false,isFavorite:()=>false,getRating:()=>null,isActionPending:()=>false,isActionUnconfirmed:()=>false,getActionIntent:()=>null,getUnconfirmedRating:()=>null})};
 if(name.includes('mediaService'))return {getMediaDescriptor:async id=>id==='A'?{movieId:'A',hasFeature:true,hasTrailer:false,feature:{streamUrl:'https://fixture.invalid/feature-A.mp4'}}:await new Promise(()=>{})};
 if(name.includes('MovieSection'))return {MovieSection:'MovieSection'};return {};
 }};
vm.runInNewContext(code,context,{filename:file});
function walk(node,pred){if(!node)return null;if(Array.isArray(node)){for(const n of node){const found=walk(n,pred);if(found)return found;}return null;}if(typeof node==='object'){if(pred(node))return node;return walk(node.props?.children,pred);}return null;}
function render(id){index=0;effects=[];tree=context.exports.MovieDetail({movie:{id,title:'Movie '+id,genres:['Animation'],rating:8,year:2026},similarMovies:[]});for(const effect of effects)effect();return tree;}
(async()=>{
 render('A');await turn();render('A');
 render('B'); // B descriptor remains in flight; production component is reused.
 const button=walk(tree,n=>n.props?.['data-testid']==='play-feature-btn');
 console.log('REPRO movie=B pendingDescriptor featureButtonFromAStillVisible='+!!button);
 if(button){button.props.onClick({currentTarget:opener});render('B');const video=walk(tree,n=>n.type==='video');console.log('REPRO movie=B videoSrc='+video?.props.src);
 if(video){video.props.ref.current={duration:120,currentTime:0};const before=opener.focusCount;video.props.onLoadedMetadata();render('B');console.log('REPRO playerStillOpen='+!!walk(tree,n=>n.type==='video')+' openerFocusCallsDuringMetadata='+(opener.focusCount-before));}}
 for(const slot of slots)slot?.cleanup?.();
})().catch(e=>{console.error(e);process.exitCode=1});
