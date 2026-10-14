// Preserve frozen Gemini output; only redirect screenshot/benchmark paths.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),Module=require('node:module');
const file=path.resolve(__dirname,'../../../scripts/run_m4_media_walkthrough.cjs');
let source=fs.readFileSync(file,'utf8');
const output=fs.mkdtempSync(path.join(os.tmpdir(),'codex-m4-f02-browser-'));
const screen="const SCREENSHOTS_DIR = path.resolve(PROJECT_ROOT, 'docs/reports/screenshots/M4_F02');";
const metrics="const BENCHMARK_OUT = path.resolve(PROJECT_ROOT, 'docs/reports/m4_f02_benchmark_results.json');";
if(!source.includes(screen)||!source.includes(metrics))throw Error('Handed output declarations changed');
source=source.replace(screen,'const SCREENSHOTS_DIR = '+JSON.stringify(output)+';')
 .replace(metrics,'const BENCHMARK_OUT = '+JSON.stringify(path.join(output,'benchmark.json'))+';');
console.log('Reviewer output: '+output);
const loaded=new Module(file,module);loaded.filename=file;loaded.paths=Module._nodeModulePaths(path.dirname(file));
loaded._compile(source,file);

