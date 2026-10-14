// Reviewer-only small temp fixture; no actual Drive or DB access.
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {checkMountFiles,isSafeRelativePath}=require('../../../scripts/preview_drive_media_mapping.cjs');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'codex-drive-mapping-'));
const root=path.join(temp,'mount'),outside=path.join(temp,'outside');
fs.mkdirSync(root);fs.mkdirSync(outside);fs.writeFileSync(path.join(outside,'clip.mp4'),'123');
fs.symlinkSync(outside,path.join(root,'escape'),'junction');
const result=checkMountFiles([{assetId:'review',movieId:'review',relativePath:'escape/clip.mp4',byteLength:3}],root);
console.log(JSON.stringify({outsideRootReportedVerified:result.verified.length===1,adsPathAccepted:isSafeRelativePath('clip.mp4:secret').safe,source:'production mapping checker on actual Windows junction'}));
