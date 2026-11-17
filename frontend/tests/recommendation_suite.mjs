import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from '../node_modules/typescript/lib/typescript.js';

function load(fetch) {
  const source = fs.readFileSync(new URL('../lib/services/recommendationService.ts', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(code, { module, exports: module.exports, fetch, process: { env: {} }, Error });
  return module.exports;
}

test('recommendations send the current bearer token and preserve media routing fields', async () => {
  let call;
  const service = load(async (url, options) => {
    call = { url, options };
    return { ok: true, json: async () => ({ recommendedMovies: [{ id: 'e1', title: 'Tập 1', item_type: 'episode', series_id: 's1' }], reasoning: 'Gợi ý' }) };
  });
  const result = await service.getRecommendations('token');
  assert.equal(call.url, '/api/recommend');
  assert.equal(call.options.headers.Authorization, 'Bearer token');
  assert.equal(result.movies[0].series_id, 's1');
  assert.equal(result.reasoning, 'Gợi ý');
});

test('recommendations reject malformed server responses', async () => {
  const service = load(async () => ({ ok: true, json: async () => ({ recommendedMovies: null }) }));
  await assert.rejects(service.getRecommendations(null));
});
