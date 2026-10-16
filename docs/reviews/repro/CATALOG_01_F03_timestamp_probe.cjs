// Execute the production TypeScript mapping helper only; no app/browser/HTTP.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../../..');
const ts = require(path.join(root, 'frontend/node_modules/typescript'));
const sourcePath = path.join(root, 'frontend/app/series/[id]/page.tsx');
const source = fs.readFileSync(sourcePath, 'utf8');
const tree = ts.createSourceFile(sourcePath, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const fn = tree.statements.find(n => ts.isFunctionDeclaration(n) && n.name?.text === 'resolveFileTimestamp');
if (!fn) throw new Error('Production helper missing');
const compiled = ts.transpileModule(fn.getText(tree), {compilerOptions: {target: ts.ScriptTarget.ES2022}}).outputText;
const context = vm.createContext({});
vm.runInContext(compiled, context);
const asset = {coverageJson: JSON.stringify([{episode_id:'ep1',source_in_ms:60000,source_out_ms:180000,episode_in_ms:0}])};
const unknown = {coverageJson: JSON.stringify([{episode_id:'ep1',source_in_ms:60000,source_out_ms:180000,episode_in_ms:null}])};
const result = {
  scene_file_timestamp: {input_ms:90000, expected_seconds:90, actual_seconds:context.resolveFileTimestamp(90000, asset),
    reason:'Production handleSeekScene passes file-timeline scene.startMs to logical-to-file helper'},
  unknown_logical_offset: {input_ms:30000, expected:'unresolved; do not seek', actual_seconds:context.resolveFileTimestamp(30000, unknown)},
  scope:'production helper transpiled in isolation; not browser decoder evidence'
};
fs.writeFileSync(path.join(root, 'docs/reviews/evidence/CATALOG_01_F03_timestamp_probe.json'), JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result,null,2));
