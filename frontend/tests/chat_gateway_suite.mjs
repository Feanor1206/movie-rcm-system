import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const code = ts.transpileModule(fs.readFileSync(new URL('../app/api/chat/route.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

function gateway(fetch) {
  const module = { exports: {} };
  vm.runInNewContext(code, { module, exports: module.exports, process: { env: {} }, AbortSignal,
    fetch, require: () => ({ NextResponse: { json: (body, options = {}) => ({ body, status: options.status || 200 }) } }),
  });
  return module.exports.POST;
}

test('Chat validates JSON and empty questions before contacting the model', async () => {
  const post = gateway(() => assert.fail('No upstream call expected'));
  assert.equal((await post({ json: async () => { throw Error('invalid'); } })).status, 400);
  for (const body of [null, [], { message: 42 }, { message: '  ' }]) {
    assert.equal((await post({ json: async () => body })).status, 400);
  }
});

test('Chat forwards content history, preserves busy status, and does not leak backend errors', async () => {
  let sent;
  const post = gateway(async (_, init) => {
    sent = JSON.parse(init.body);
    assert(init.signal instanceof AbortSignal);
    return { ok: false, status: 429, text: () => assert.fail('Private error body must not be exposed') };
  });
  const response = await post({ json: async () => ({ messages: [{ role: 'user', content: 'Jadoo tập 2' }] }) });
  assert.equal(sent.query, 'Jadoo tập 2');
  assert.equal(response.status, 429);
  assert.match(response.body.text, /đang bận/);
});

test('Offline chat offers catalog search with 503 and no internal details', async () => {
  const response = await gateway(async () => { throw Error('secret host and stack'); })({ json: async () => ({ message: 'Jadoo' }) });
  assert.equal(response.status, 503);
  assert.match(response.body.text, /Kho phim/);
  assert.doesNotMatch(response.body.text, /secret|localhost|8000|stack/);
  assert.equal(response.body.recommendedMovies.length, 0);
});

test('Successful chat keeps canonical episode cards and pipeline diagnostics', async () => {
  const payload = { text: 'Tập 2', recommendedMovies: [{ id: 'ep2' }], pipelineStages: { rankedCount: 1 } };
  const response = await gateway(async () => ({ ok: true, json: async () => payload }))({ json: async () => ({ message: 'Jadoo tập 2' }) });
  assert.equal(response.status, 200);
  assert.equal(response.body.recommendedMovies[0].id, 'ep2');
  assert.equal(response.body.pipelineStages.rankedCount, 1);
});
