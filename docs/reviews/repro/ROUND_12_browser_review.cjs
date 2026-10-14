// Rerun handed browser/negative checks without overwriting frozen evidence.
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const Module=require('node:module');
const http=require('node:http');
(async()=>{
  for(const port of [8080,3005,9222])await new Promise((resolve,reject)=>{const probe=http.createServer();probe.once('error',()=>reject(new Error('Reviewer preflight: occupied port '+port)));probe.listen(port,'127.0.0.1',()=>probe.close(resolve));});
  const filename=path.resolve(__dirname,'../../../scripts/run_browser_walkthrough.cjs');
  let source=fs.readFileSync(filename,'utf8');
  const declaration="const SCREENSHOTS_DIR = path.resolve(__dirname, '../docs/reports/screenshots/ROUND_12');";
  if(!source.includes(declaration))throw new Error('Output declaration changed');
  const output=fs.mkdtempSync(path.join(os.tmpdir(),'codex-round12-browser-'));
  console.log('Reviewer output directory: '+output);
  source=source.replace(declaration,'const SCREENSHOTS_DIR = '+JSON.stringify(output)+';');
  const loaded=new Module(filename,module);loaded.filename=filename;loaded.paths=Module._nodeModulePaths(path.dirname(filename));loaded._compile(source,filename);
})().catch(error=>{console.error(error);process.exitCode=1;});
