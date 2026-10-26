import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from '../node_modules/typescript/lib/typescript.js';

const record = (extra = {}) => ({ episodeId: 'ep1', seriesId: 'series1', seriesTitle: 'Jadoo', seasonId: 'season1', seasonNumber: 1,
  seasonTitle: 'Mùa 1', episodeNumber: 1, episodeTitle: 'Tập một', assetId: 'asset1', positionMs: 60000,
  durationMs: 1000000, completed: false, version: 0, updatedAt: '2026-10-27T00:00:00Z', ...extra });
const draft = (extra = {}) => ({ ...record(), ...extra });
const reply = (data, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => ({ success: true, data }) });
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
function load(file, globals = {}) {
  const module = { exports: {} };
  const source = fs.readFileSync(new URL(file, import.meta.url), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  vm.runInNewContext(code, { module, exports: module.exports, process: { env: {} }, console, AbortController,
    URLSearchParams, setTimeout, clearTimeout, fetch: async () => { throw Error('Unexpected network'); }, ...globals });
  return module.exports;
}
function environment(fetch) {
  const stored = new Map();
  const window = { localStorage: { getItem: key => stored.get(key) ?? null, setItem: (key, val) => stored.set(key, val), removeItem: key => stored.delete(key) } };
  return { stored, service: load('../lib/services/watchProgressService.ts', { window, fetch }) };
}
function hookHarness(auth, service) {
  const slots = []; let cursor = 0; let pending = []; let authValue = auth;
  const same = (a,b) => a && b && a.length === b.length && a.every((v,i) => Object.is(v,b[i]));
  const react = {
    useState(init) { const i = cursor++; if (!slots[i]) slots[i] = { value: typeof init === 'function' ? init() : init };
      return [slots[i].value, val => { slots[i].value = typeof val === 'function' ? val(slots[i].value) : val; }]; },
    useRef(value) { const i = cursor++; return slots[i] ||= { current: value }; },
    useCallback(fn, deps) { const i = cursor++; if (!slots[i] || !same(slots[i].deps,deps)) slots[i] = { fn, deps }; return slots[i].fn; },
    useEffect(fn,deps) { const i = cursor++; if (!slots[i] || !same(slots[i].deps,deps)) {
      pending.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: fn() }; });
    } },
  };
  const hook = load('../lib/hooks/useWatchProgress.ts', { require: name => name === 'react' ? react : name.includes('AuthContext')
    ? { useAuth: () => authValue } : service });
  return { render(nextAuth = authValue) { authValue = nextAuth; cursor = 0; const output = hook.useWatchProgress();
    const effects = pending; pending = []; effects.forEach(fn => fn()); return output; },
    close() { slots.forEach(slot => slot?.cleanup?.()); } };
}
const guest = { status: 'guest', token: null, user: null, handleSessionExpired() {} };
const account = (id, token) => ({ ...guest, status: 'authenticated', user: { id }, token });

test('Guest storage is defensive, bounded and persists file identity without touching account API', () => {
  const { service, stored } = environment();
  stored.set(service.GUEST_WATCH_PROGRESS_KEY, '{invalid');
  assert.equal(service.getGuestWatchProgress().length, 0);
  for (let i=0;i<35;i++) service.saveGuestWatchProgress(draft({ episodeId: `ep${i}` }), Date.now()+i);
  assert.equal(service.getGuestWatchProgress().length, 30);
  assert.equal(service.getGuestWatchProgress()[0].episodeId, 'ep34');
  const href = service.buildWatchProgressHref(record());
  const url = new URL(href, 'http://localhost');
  assert.equal(url.searchParams.get('asset'), 'asset1');
  assert.equal(url.searchParams.get('t'), '60000');
  assert.equal(url.searchParams.get('timeline'), 'file');
  assert.equal(service.isUsableResumeProgress(record({ completed: true })), false);
  assert.equal(service.isUsableResumeProgress(record({ positionMs: 1000000 })), false);
  assert.throws(() => service.saveGuestWatchProgress(draft({ positionMs: NaN })));
  assert.throws(() => service.saveGuestWatchProgress(draft({ positionMs: -1 })));
  assert.equal(service.readAutoNextPreference(), false);
  service.writeAutoNextPreference(true); assert.equal(service.readAutoNextPreference(), true);
});

test('Account requests use Authorization, strict integer positions and explicit version, never URL tokens', async () => {
  const calls = [];
  const { service } = environment(async (url, opts) => { calls.push({url,opts}); return reply(record({version:1})); });
  await service.saveWatchProgress('secret', 'ep1', draft({ positionMs: 12345 }), 0);
  assert.equal(calls[0].opts.headers.Authorization, 'Bearer secret');
  assert.ok(!calls[0].url.includes('secret'));
  assert.deepEqual(JSON.parse(calls[0].opts.body), {assetId:'asset1',positionMs:12345,expectedVersion:0});
  await assert.rejects(service.saveWatchProgress('secret','ep1',draft({positionMs:1.5}),0));
  await assert.rejects(service.saveWatchProgress('secret','ep1',draft(),-2));
  assert.equal(calls.length,1);
});

test('Network timeout and caller cancellation finish even when fetch ignores abort', async () => {
  const { service } = environment(() => new Promise(() => {}));
  await assert.rejects(service.listWatchProgress('secret',{timeoutMs:10}), error => error.isTimeout);
  const controller = new AbortController();
  const request = service.listWatchProgress('secret',{signal:controller.signal}); controller.abort();
  await assert.rejects(request, error => error.isCanceled);
});

test('Switching account hides old records immediately and late reply cannot enter the new scope', async () => {
  const waiting = [];
  const { service, stored } = environment((url, opts) => new Promise(resolve => waiting.push({resolve,signal:opts.signal})));
  const h = hookHarness(account(1,'one'),service);
  h.render(); await tick();
  h.render(account(2,'two')); await tick();
  assert.equal(waiting[0].signal.aborted,true);
  waiting[0].resolve(reply([record({episodeTitle:'Private user one'})]));
  waiting[1].resolve(reply([])); await tick(); await tick();
  assert.equal(h.render().records.length,0);
  assert.equal(stored.size,0);
  h.close();
});

test('Guest records are not merged into the account, and logout never writes account rows to local storage', async () => {
  const { service, stored } = environment(async () => reply([]));
  service.saveGuestWatchProgress(draft()); const original = stored.get(service.GUEST_WATCH_PROGRESS_KEY);
  const h = hookHarness(guest,service); h.render(); assert.equal(h.render().records.length,1);
  h.render(account(1,'one')); await tick(); assert.equal(h.render().records.length,0);
  h.render(guest); assert.equal(h.render().records.length,1);
  assert.equal(stored.get(service.GUEST_WATCH_PROGRESS_KEY),original); h.close();
});

test('409 keeps the newer SQL point instead of automatically replaying a stale save over it', async () => {
  let puts = 0;
  const { service } = environment(async (url, opts) => {
    if (opts.method === 'PUT') { puts++; return reply(null,409); }
    return reply(url.endsWith('/ep1') ? record({positionMs:400000,version:4}) : [record({version:3})]);
  });
  const h = hookHarness(account(1,'one'),service); h.render(); await tick();
  const result = await h.render().saveProgress(draft({positionMs:80000}));
  assert.equal(result,null); assert.equal(puts,1);
  const output = h.render(); assert.equal(output.records[0].positionMs,400000); assert.match(output.error,/cửa sổ khác/); h.close();
});

test('Two local saves serialize their optimistic SQL versions', async () => {
  const versions = []; let version = 0;
  const { service } = environment(async (url, opts) => {
    if (opts.method === 'PUT') { const payload = JSON.parse(opts.body); versions.push(payload.expectedVersion);
      await tick(); return reply(record({positionMs:payload.positionMs,version:++version})); }
    return reply([record()]);
  });
  const h = hookHarness(account(1,'one'),service); h.render(); await tick();
  const output = h.render(); await Promise.all([output.saveProgress(draft({positionMs:70000})),output.saveProgress(draft({positionMs:80000}))]);
  assert.deepEqual(versions,[0,1]); assert.equal(h.render().records[0].positionMs,80000); h.close();
});
