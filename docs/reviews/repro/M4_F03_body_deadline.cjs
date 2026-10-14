// Native fetch stalled-body probe with production media service, isolated HTTP server.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
(async()=>{
 const file=path.resolve(__dirname,'../../../frontend/tests/media_descriptor_boundary_suite.mjs');
 let helpers=fs.readFileSync(file,'utf8').split("test('1. Payload")[0];
 helpers=helpers.replace('const __filename = fileURLToPath(import.meta.url);','const __filename = '+JSON.stringify(file)+';')
 .replace('const require = createRequire(import.meta.url);','const require = createRequire('+JSON.stringify(file)+');');
 helpers+='\nexport {loadMediaService};';
 const {loadMediaService}=await import('data:text/javascript;base64,'+Buffer.from(helpers).toString('base64'));
 const sockets=new Set();
 const server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'application/json'});res.flushHeaders();res.write('{"movieId":');});
 server.on('connection',s=>{sockets.add(s);s.on('close',()=>sockets.delete(s));});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{
   const service=loadMediaService((_url,options)=>fetch('http://127.0.0.1:'+server.address().port,options));
   for(const mode of ['internal-timeout','external-abort']){
     const caller=new AbortController();let timer;const start=Date.now();
     if(mode==='external-abort')timer=setTimeout(()=>caller.abort(),40);
     try{await service.getMediaDescriptor('fixture',{timeoutMs:mode==='internal-timeout'?100:1000,signal:caller.signal});throw Error('Unexpected success');}
     catch(e){const expected=mode==='internal-timeout'?'TimeoutError':'AbortError';console.log(JSON.stringify({mode,error:e.name,elapsedMs:Date.now()-start,expected}));if(e.name!==expected)throw e;}
     finally{clearTimeout(timer);}
   }
 }finally{for(const s of sockets)s.destroy();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1});
