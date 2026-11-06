// Production assertions unchanged; preserve frozen artifacts and isolate fixture root.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),Module=require('node:module');
const file=path.resolve(__dirname,'../../../scripts/run_drive_media_walkthrough.cjs');
let source=fs.readFileSync(file,'utf8');
const output=fs.mkdtempSync(path.join(os.tmpdir(),'codex-drive-f03-browser-'));
for(const [before,after] of [
 ["const EVIDENCE_DIR = path.resolve(PROJECT_ROOT, process.env.DRIVE_EVIDENCE_DIR || 'docs/reports/drive/DRIVE_01_F02');",'const EVIDENCE_DIR = '+JSON.stringify(output)+';'],
 ["const DRIVE_MOUNT_DIR = path.resolve(PROJECT_ROOT, 'backend/springboot/target/test-drive-mount');",'const DRIVE_MOUNT_DIR = '+JSON.stringify(path.join(output,'mount-fixture'))+';']
]){if(!source.includes(before))throw Error('Handed declaration changed');source=source.replace(before,after);}
console.log('Reviewer output: '+output);
const loaded=new Module(file,module);loaded.filename=file;loaded.paths=Module._nodeModulePaths(path.dirname(file));loaded._compile(source,file);

