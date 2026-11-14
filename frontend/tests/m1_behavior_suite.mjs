import { labels } from './labels_fixture.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '../..');
const require = createRequire(import.meta.url);
const ts = require(path.resolve(__dirname, '../node_modules/typescript'));

const authFile = path.resolve(__dirname, '../lib/context/AuthContext.tsx');
const libFile = path.resolve(__dirname, '../lib/context/WatchlistContext.tsx');
const movieCardFile = path.resolve(__dirname, '../features/movies/components/MovieCard.tsx');
const movieDetailFile = path.resolve(__dirname, '../features/movies/components/MovieDetail.tsx');
const profileOverviewFile = path.resolve(__dirname, '../features/profile/components/ProfileOverview.tsx');

const mediaRoutingModule = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.resolve(__dirname, '../lib/services/mediaRouting.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { exports: mediaRoutingModule.exports, module: mediaRoutingModule, URLSearchParams });

function renderComponent(filePath, componentName, contextVal, authVal, props = {}, initialStates = []) {
  const rawCode = fs.readFileSync(filePath, 'utf8');
  const code = ts.transpileModule(rawCode, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true, target: ts.ScriptTarget.ES2020 },
  }).outputText;

  let stateIdx = 0;
  const hooks = {
    useState: (init) => {
      const idx = stateIdx++;
      const val = initialStates[idx] !== undefined ? initialStates[idx] : (typeof init === 'function' ? init() : init);
      return [val, () => {}];
    },
    useEffect: () => {},
    useMemo: (fn) => fn(),
    useCallback: (fn) => fn,
    useRef: (init) => ({ current: init }),
  };

  const module = { exports: {} };
  const context = {
    module,
    exports: module.exports,
    process: { env: {} },
    require: (name) => {
      if (name === '@/lib/labels') return labels;
      if (name === 'next/dynamic') return { __esModule: true, default: () => () => null };
      if (name === 'react') return { createElement: (t, p, ...c) => ({ type: t, props: { ...(p || {}), children: c.length === 1 ? c[0] : c } }), ...hooks };
      if (name === 'next/image') return { default: (p) => ({ type: 'img', props: p }) };
      if (name === 'next/link') return { default: (p) => ({ type: 'a', props: p }) };
      if (name === 'lucide-react') return new Proxy({}, { get: (_, prop) => (p) => ({ type: String(prop), props: p }) });
      if (name.includes('mediaRouting')) return mediaRoutingModule.exports;
      if (name.includes('WatchlistContext')) return { useWatchlist: () => contextVal };
      if (name.includes('AuthContext')) return { useAuth: () => authVal };
      if (name.includes('MovieSection')) return { MovieSection: () => null };
      if (name.includes('MovieCard')) return { MovieCard: (p) => ({ type: 'MovieCard', props: p }) };
      if (name.includes('movies')) return { movies: [] };
      return {};
    },
  };

  vm.runInNewContext(code, context, { filename: filePath });
  return module.exports[componentName](props);
}

function findElements(node, predicate, acc = []) {
  if (!node) return acc;
  if (predicate(node)) acc.push(node);
  if (node.props?.children) {
    const children = Array.isArray(node.props.children) ? node.props.children : [node.props.children];
    children.forEach((c) => findElements(c, predicate, acc));
  }
  return acc;
}

const turn = () => new Promise((resolve) => setImmediate(resolve));
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
};
const ok = (data) => ({ ok: true, status: 200, json: async () => ({ success: true, data }) });

function makeHarness(file, provider, fetcher, authContextRef) {
  const slots = [];
  let index = 0;
  let effects = [];
  let changed = false;
  let value;

  const same = (a, b) => a && b && a.length === b.length && a.every((x, i) => Object.is(x, b[i]));

  const hooks = {
    createContext: () => ({ Provider: 'Provider' }),
    useContext: () => null,
    useState(initial) {
      const i = index++;
      if (!slots[i]) slots[i] = { v: typeof initial === 'function' ? initial() : initial };
      return [
        slots[i].v,
        (v) => {
          slots[i].v = typeof v === 'function' ? v(slots[i].v) : v;
          changed = true;
        },
      ];
    },
    useRef(initial) {
      const i = index++;
      if (!slots[i]) slots[i] = { current: initial };
      return slots[i];
    },
    useCallback(fn, deps) {
      const i = index++;
      if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { v: fn, deps };
      return slots[i].v;
    },
    useEffect(fn, deps) {
      const i = index++;
      if (!slots[i] || !same(slots[i].deps, deps)) {
        const prev = slots[i];
        slots[i] = { deps, cleanup: prev?.cleanup };
        effects.push(() => {
          slots[i].cleanup?.();
          slots[i].cleanup = fn();
        });
      }
    },
    useMemo(fn, deps) {
      const i = index++;
      if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { v: fn(), deps };
      return slots[i].v;
    },
    createElement(type, props, ...children) {
      return { type, props: { ...props, children } };
    },
  };

  const storage = new Map();
  const localStorage = {
    getItem: (k) => storage.get(k) ?? null,
    setItem: (k, v) => storage.set(k, String(v)),
    removeItem: (k) => storage.delete(k),
    clear: () => storage.clear(),
  };

  const timers = new Map();
  let timerId = 0;
  const module = { exports: {} };

  const rawCode = fs.readFileSync(file, 'utf8');
  const code = ts.transpileModule(rawCode, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.React,
      esModuleInterop: true,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText;

  const context = {
    module,
    exports: module.exports,
    process: { env: {} },
    console,
    AbortController,
    DOMException,
    fetch: fetcher,
    window: {},
    localStorage,
    setTimeout: (fn, ms) => {
      const id = ++timerId;
      timers.set(id, { fn, ms });
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
    require: (name) => {
      if (name === '@/lib/labels') return labels;
      if (name === 'next/dynamic') return { __esModule: true, default: () => () => null };
      if (name === 'react') return { __esModule: true, default: hooks, ...hooks };
      if (name === './AuthContext') return { useAuth: () => authContextRef.current };
      return {};
    },
  };

  vm.runInNewContext(code, context, { filename: file });

  function render() {
    index = 0;
    changed = false;
    const res = module.exports[provider]({ children: null });
    value = res.props.value;
    const pending = effects;
    effects = [];
    pending.forEach((fn) => fn());
    return value;
  }

  async function settle() {
    for (let i = 0; i < 8; i++) {
      await turn();
      if (changed || i === 0) render();
    }
    return value;
  }

  return { render, settle, storage, get value() { return value; }, timers };
}

const makeActor = (id, overrides = {}) => ({
  user: { id, username: `user${id}`, email: `user${id}@example.test`, role: 'ROLE_USER' },
  token: `token${id}`,
  status: 'authenticated',
  isAuthenticated: true,
  handleSessionExpired: () => {},
  ...overrides,
});

test('1. Auth login sends verbatim raw password with spaces', async () => {
  let capturedBody = null;
  const h = makeHarness(authFile, 'AuthProvider', async (url, opts) => {
    if (opts?.body) capturedBody = JSON.parse(opts.body);
    return ok({
      id: 1,
      token: 'valid-token',
      username: 'alice',
      email: 'alice@example.test',
      role: 'ROLE_USER',
    });
  });

  h.render();
  await h.settle();

  const res = await h.value.login('alice', '  raw password with spaces  ');
  assert.equal(res.success, true);
  assert.equal(capturedBody.password, '  raw password with spaces  ');
  assert.equal(capturedBody.usernameOrEmail, 'alice');
});

test('2. R1 (P1): Logout while response JSON is pending does NOT resurrect session', async () => {
  const body = deferred();
  const h = makeHarness(authFile, 'AuthProvider', async () => ({
    ok: true,
    status: 200,
    json: () => body.promise,
  }));

  h.render();
  await h.settle();

  const loginPromise = h.value.login('alice', 'secret');
  await turn();

  h.value.logout();
  await h.settle();
  assert.equal(h.value.status, 'guest');
  assert.equal(h.storage.has('dippie_auth_token'), false);

  body.resolve({
    success: true,
    data: { id: 1, username: 'alice', email: 'alice@example.test', token: 'stale-token' },
  });
  await loginPromise;
  await h.settle();

  assert.equal(h.value.status, 'guest');
  assert.equal(h.value.user, null);
  assert.equal(h.storage.has('dippie_auth_token'), false);
});

test('3. R1: Runtime validation rejects malformed auth payloads', async () => {
  const h = makeHarness(authFile, 'AuthProvider', async () =>
    ok({ id: 'bad-id', token: { unexpected: true } })
  );

  h.render();
  await h.settle();

  const res = await h.value.login('alice', 'password');
  await h.settle();

  assert.equal(res.success, false);
  assert.equal(h.value.status, 'guest');
  assert.equal(h.value.user, null);
});

test('4. F1 (P1): Late A 401 response after B login does NOT trigger handleSessionExpired on B', async () => {
  const aWrite = deferred();
  let bExpiredCalls = 0;
  const auth = {
    current: {
      ...makeActor(1),
      handleSessionExpired: () => {},
    },
  };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => (opts?.method ? aWrite.promise : Promise.resolve(ok([]))),
    auth
  );

  h.render();
  await h.settle();

  const aOp = h.value.toggleWatchlist('movie-a');
  await h.settle();

  auth.current = {
    ...makeActor(2),
    handleSessionExpired: () => {
      bExpiredCalls++;
    },
  };
  h.render();
  await h.settle();

  aWrite.resolve({ ok: false, status: 401, json: async () => ({}) });
  await aOp;
  await h.settle();

  assert.equal(bExpiredCalls, 0);
  assert.equal(auth.current.status, 'authenticated');
});

test('5. F1 (P1): Old A finally does NOT release B synchronous lock for the same item', async () => {
  const aPending = deferred();
  const bPending = deferred();
  let bWrites = 0;

  const auth = { current: makeActor(1) };
  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => {
      if (!opts?.method) return Promise.resolve(ok([]));
      if (opts.headers.Authorization === 'Bearer token1') return aPending.promise;
      bWrites++;
      return bPending.promise;
    },
    auth
  );

  h.render();
  await h.settle();

  const aOp = h.value.toggleWatchlist('X');
  await h.settle();

  auth.current = makeActor(2);
  h.render();
  await h.settle();

  const bOp1 = h.value.toggleWatchlist('X');
  await h.settle();
  assert.equal(bWrites, 1);

  aPending.reject(new Error('A failed late'));
  await aOp1Catch(aOp);
  await h.settle();

  const bOp2 = h.value.toggleWatchlist('X');
  await h.settle();

  assert.equal(bWrites, 1);
  assert.equal(await bOp2, false);

  bPending.resolve(ok({ movieId: 'X' }));
  await bOp1;
  await h.settle();

  async function aOp1Catch(p) {
    try {
      await p;
    } catch {}
  }
});

test('6. F2 (P1): First render of User B derives empty state before passive effects flush', async () => {
  const auth = { current: makeActor(1) };
  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url) => Promise.resolve(ok(url.endsWith('watchlist') ? [{ movieId: 'A-private-film' }] : [])),
    auth
  );

  h.render();
  await h.settle();

  assert.deepEqual([...h.value.watchlist], ['A-private-film']);

  auth.current = makeActor(2);

  const firstB = h.render();

  assert.deepEqual([...firstB.watchlist], []);
  assert.equal(firstB.isWatchlisted('A-private-film'), false);
});

test('7. F3 (P2): Same-actor refresh does NOT invalidate pending mutation or leave pending stuck', async () => {
  const writeX = deferred();
  const auth = { current: makeActor(1) };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => (opts?.method ? writeX.promise : Promise.resolve(ok([]))),
    auth
  );

  h.render();
  await h.settle();

  const opX = h.value.toggleWatchlist('X');
  await h.settle();

  const refetch = h.value.refetchLibrary();
  await h.settle();

  writeX.resolve(ok({ movieId: 'X' }));
  await opX;
  await refetch;
  await h.settle();

  assert.equal(h.value.isActionPending('X'), false);
  assert.deepEqual([...h.value.watchlist], ['X']);
});

test('8. F4 (P2): Slow JSON body parsing after headers triggers timeout and aborts', async () => {
  const slowBody = deferred();
  const auth = { current: makeActor(1) };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => {
      if (opts?.method) {
        if (opts?.signal) {
          opts.signal.addEventListener('abort', () => {
            slowBody.reject(new DOMException('The operation was aborted', 'AbortError'));
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => slowBody.promise,
        });
      }
      return Promise.resolve(ok([]));
    },
    auth
  );

  h.render();
  await h.settle();

  const op = h.value.toggleWatchlist('slow-movie');
  await h.settle();

  const timerEntries = [...h.timers.entries()];
  assert.ok(timerEntries.length > 0, 'Timeout must remain active during body parsing');

  const [timerId, timerObj] = timerEntries[0];
  timerObj.fn();
  h.timers.delete(timerId);

  await op;
  await h.settle();

  assert.equal(h.value.isActionPending('slow-movie'), false);
});

test('9. R3: Targeted rollback: X failure retains successfully added Y', async () => {
  const writeX = deferred();
  const auth = { current: makeActor(1) };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => {
      if (!opts?.method) return Promise.resolve(ok([]));
      const body = JSON.parse(opts.body);
      if (body.movieId === 'X') return writeX.promise;
      return Promise.resolve(ok({}));
    },
    auth
  );

  h.render();
  await h.settle();

  const opX = h.value.toggleWatchlist('X');
  await h.settle();

  const opY = h.value.toggleWatchlist('Y');
  await h.settle();
  await opY;

  assert.deepEqual([...h.value.watchlist].sort(), ['X', 'Y']);

  writeX.reject(new Error('X failed'));
  await opX;
  await h.settle();

  assert.deepEqual([...h.value.watchlist], ['Y']);
});

test('10. R4: Unavailable sessions do NOT write to guest storage', async () => {
  const auth = { current: makeActor(1, { status: 'unavailable', isAuthenticated: false, user: null }) };
  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    () => { throw new Error('Unexpected fetch in unavailable state'); },
    auth
  );

  h.render();
  await h.settle();

  assert.equal(h.value.isGuestMode, false);

  const res = await h.value.toggleWatchlist('account-click');
  await h.settle();

  assert.equal(res, false);
  assert.equal(h.storage.has('dippie_guest_library_v1'), false);
});

test('11. R7: removeRating removes rating and sends DELETE request without mutating watchlist', async () => {
  let deletedMovieId = null;
  const auth = { current: makeActor(1) };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => {
      if (opts?.method === 'DELETE' && url.includes('/ratings/')) {
        deletedMovieId = url.split('/').pop();
        return Promise.resolve(ok({}));
      }
      return Promise.resolve(
        ok(url.endsWith('ratings') ? [{ movieId: 'film-abc', rating: 9 }] : [])
      );
    },
    auth
  );

  h.render();
  await h.settle();
  assert.equal(h.value.ratings['film-abc'], 9);

  const res = await h.value.removeRating('film-abc', 'Film ABC');
  await h.settle();

  assert.equal(res, true);
  assert.equal(deletedMovieId, 'film-abc');
  assert.equal(h.value.ratings['film-abc'], undefined);
  assert.deepEqual([...h.value.watchlist], []);
});

test('12. G1 (P1): Boot checking to verified A restores nonempty library (watchlist, favorites, ratings)', async () => {
  const auth = {
    current: {
      user: null,
      token: null,
      status: 'checking',
      isAuthenticated: false,
      handleSessionExpired: () => {},
    },
  };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url) => {
      if (url.endsWith('/watchlist')) return Promise.resolve(ok([{ movieId: 'A-film' }]));
      if (url.endsWith('/favorites')) return Promise.resolve(ok([{ movieId: 'A-fav' }]));
      if (url.endsWith('/ratings')) return Promise.resolve(ok([{ movieId: 'A-rate', rating: 10 }]));
      return Promise.resolve(ok([]));
    },
    auth
  );

  h.render();
  await h.settle();

  assert.equal(h.value.isLibraryLoading, true);
  assert.deepEqual([...h.value.watchlist], []);

  auth.current = {
    ...makeActor(1),
    handleSessionExpired: () => {},
  };

  h.render();
  await h.settle();

  assert.equal(h.value.isLibraryLoading, false);
  assert.equal(h.value.libraryError, null);
  assert.deepEqual([...h.value.watchlist], ['A-film']);
  assert.deepEqual([...h.value.favorites], ['A-fav']);
  assert.equal(h.value.ratings['A-rate'], 10);
});

test('13. G1 (P1): A -> logout -> B loads B nonempty library without leaking A library', async () => {
  let currentUser = 1;
  const auth = {
    current: {
      ...makeActor(1),
      handleSessionExpired: () => {},
    },
  };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url) => {
      const isUser1 = currentUser === 1;
      if (url.endsWith('/watchlist')) return Promise.resolve(ok([{ movieId: isUser1 ? 'A-film' : 'B-film' }]));
      if (url.endsWith('/favorites')) return Promise.resolve(ok([{ movieId: isUser1 ? 'A-fav' : 'B-fav' }]));
      if (url.endsWith('/ratings')) return Promise.resolve(ok([{ movieId: isUser1 ? 'A-rate' : 'B-rate', rating: isUser1 ? 9 : 8 }]));
      return Promise.resolve(ok([]));
    },
    auth
  );

  h.render();
  await h.settle();

  assert.deepEqual([...h.value.watchlist], ['A-film']);
  assert.deepEqual([...h.value.favorites], ['A-fav']);

  currentUser = 0;
  auth.current = {
    user: null,
    token: null,
    status: 'guest',
    isAuthenticated: false,
    handleSessionExpired: () => {},
  };
  h.render();
  await h.settle();

  assert.deepEqual([...h.value.watchlist], []);
  assert.deepEqual([...h.value.favorites], []);

  currentUser = 2;
  auth.current = {
    ...makeActor(2),
    handleSessionExpired: () => {},
  };
  h.render();
  await h.settle();

  assert.deepEqual([...h.value.watchlist], ['B-film']);
  assert.deepEqual([...h.value.favorites], ['B-fav']);
  assert.equal(h.value.ratings['B-rate'], 8);
  assert.equal(h.value.ratings['A-rate'], undefined);
});

test('14. G2 (P2): Older refresh body arriving after successful add preserves newly added items', async () => {
  const oldBody = deferred();
  let refreshing = false;
  const auth = {
    current: {
      ...makeActor(1),
      handleSessionExpired: () => {},
    },
  };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => {
      if (opts?.method) return Promise.resolve(ok({ movieId: 'X' }));
      if (refreshing && url.endsWith('watchlist')) {
        return Promise.resolve({ ok: true, status: 200, json: () => oldBody.promise });
      }
      return Promise.resolve(ok([]));
    },
    auth
  );

  h.render();
  await h.settle();

  refreshing = true;
  const readPromise = h.value.refetchLibrary();
  await h.settle();

  const addRes = await h.value.toggleWatchlist('X');
  await h.settle();
  assert.equal(addRes, true);
  assert.deepEqual([...h.value.watchlist], ['X']);

  oldBody.resolve({ success: true, data: [] });
  await readPromise;
  await h.settle();

  assert.deepEqual([...h.value.watchlist], ['X']);
});

test('15. G2 (P2): Refresh during delete followed by delete success keeps item deleted', async () => {
  const pendingDelete = deferred();
  const auth = {
    current: {
      ...makeActor(1),
      handleSessionExpired: () => {},
    },
  };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => {
      if (opts?.method) return pendingDelete.promise;
      return Promise.resolve(ok(url.endsWith('watchlist') ? [{ movieId: 'X' }] : []));
    },
    auth
  );

  h.render();
  await h.settle();
  assert.deepEqual([...h.value.watchlist], ['X']);

  const delPromise = h.value.toggleWatchlist('X');
  await h.settle();

  const refetchPromise = h.value.refetchLibrary();
  await h.settle();

  pendingDelete.resolve(ok(null));
  await delPromise;
  await refetchPromise;
  await h.settle();

  assert.deepEqual([...h.value.watchlist], []);
});

test('16. G2 (P2): Rating update is protected against stale read returning old score', async () => {
  const oldBody = deferred();
  let refreshing = false;
  const auth = {
    current: {
      ...makeActor(1),
      handleSessionExpired: () => {},
    },
  };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => {
      if (opts?.method) return Promise.resolve(ok({ movieId: 'M', rating: 9 }));
      if (refreshing && url.endsWith('ratings')) {
        return Promise.resolve({ ok: true, status: 200, json: () => oldBody.promise });
      }
      return Promise.resolve(ok(url.endsWith('ratings') ? [{ movieId: 'M', rating: 5 }] : []));
    },
    auth
  );

  h.render();
  await h.settle();
  assert.equal(h.value.ratings['M'], 5);

  refreshing = true;
  const refreshPromise = h.value.refetchLibrary();
  await h.settle();

  await h.value.rateMovie('M', 9);
  await h.settle();
  assert.equal(h.value.ratings['M'], 9);

  oldBody.resolve({ success: true, data: [{ movieId: 'M', rating: 5 }] });
  await refreshPromise;
  await h.settle();

  assert.equal(h.value.ratings['M'], 9);
});

test('17. G3 (P2): Unknown write outcome (network error) triggers background reconcile', async () => {
  let backendWatchlist = [];
  let failFirstPost = true;
  const auth = {
    current: {
      ...makeActor(1),
      handleSessionExpired: () => {},
    },
  };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => {
      if (opts?.method === 'POST') {
        if (failFirstPost) {
          failFirstPost = false;
          backendWatchlist = ['committed-item'];
          throw new TypeError('Failed to fetch');
        }
      }
      return Promise.resolve(ok(url.endsWith('watchlist') ? backendWatchlist.map((id) => ({ movieId: id })) : []));
    },
    auth
  );

  h.render();
  await h.settle();

  const res = await h.value.toggleWatchlist('committed-item');
  await h.settle();

  assert.equal(res, false);

  assert.deepEqual([...h.value.watchlist], ['committed-item']);
});

test('18. H1 (P2): Read initiated while write was pending cannot overwrite subsequent commit when read body arrives late', async () => {
  const writeDeferred = deferred();
  const readDeferred = deferred();
  let refreshing = false;
  const auth = {
    current: {
      ...makeActor(1),
      handleSessionExpired: () => {},
    },
  };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => {
      if (opts?.method) return writeDeferred.promise;
      if (refreshing && url.endsWith('watchlist')) {
        return Promise.resolve({ ok: true, status: 200, json: () => readDeferred.promise });
      }
      return Promise.resolve(ok([]));
    },
    auth
  );

  h.render();
  await h.settle();
  assert.deepEqual([...h.value.watchlist], []);

  const mutationPromise = h.value.toggleWatchlist('X');
  await h.settle();

  refreshing = true;
  const readPromise = h.value.refetchLibrary();
  await h.settle();

  writeDeferred.resolve(ok({ movieId: 'X' }));
  await mutationPromise;
  await h.settle();
  assert.deepEqual([...h.value.watchlist], ['X']);

  readDeferred.resolve({ success: true, data: [] });
  await readPromise;
  await h.settle();

  assert.deepEqual([...h.value.watchlist], ['X']);
});

test('19. H2 (P2): Unknown outcome on write network loss marks operation uncertain and retrying toggle maintains POST intent', async () => {
  let backend = [];
  let failReconcile = false;
  const methods = [];
  const auth = {
    current: {
      ...makeActor(1),
      handleSessionExpired: () => {},
    },
  };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => {
      if (opts?.method === 'POST') {
        methods.push('POST');
        if (methods.length === 1) {
          backend = ['X'];
          failReconcile = true;
          throw new TypeError('Connection reset after commit');
        }
        backend = ['X'];
        return Promise.resolve(ok({ movieId: 'X' }));
      }
      if (opts?.method === 'DELETE') {
        methods.push('DELETE');
        backend = [];
        return Promise.resolve(ok(null));
      }
      if (failReconcile) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve(ok(backend.map((id) => ({ movieId: id }))));
    },
    auth
  );

  h.render();
  await h.settle();

  const firstRes = await h.value.toggleWatchlist('X');
  await h.settle();

  assert.equal(firstRes, false);
  assert.equal(h.value.isActionPending('X', 'watchlist'), false);
  assert.equal(h.value.isActionUnconfirmed('X', 'watchlist'), true);
  assert.deepEqual([...h.value.watchlist], ['X']);

  const retryRes = await h.value.toggleWatchlist('X');
  await h.settle();

  assert.equal(retryRes, true);
  assert.deepEqual(methods, ['POST', 'POST']);
  assert.deepEqual(backend, ['X']);
  assert.deepEqual([...h.value.watchlist], ['X']);
  assert.equal(h.value.isActionUnconfirmed('X', 'watchlist'), false);
});

test('20. H2 (P2): Unknown outcome on DELETE maintains delete intent on retry without inverting to POST', async () => {
  let backend = ['Y'];
  let failReconcile = false;
  const methods = [];
  const auth = {
    current: {
      ...makeActor(1),
      handleSessionExpired: () => {},
    },
  };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => {
      if (opts?.method === 'POST') {
        methods.push('POST');
        backend = ['Y'];
        return Promise.resolve(ok({ movieId: 'Y' }));
      }
      if (opts?.method === 'DELETE') {
        methods.push('DELETE');
        if (methods.length === 1) {
          backend = [];
          failReconcile = true;
          throw new TypeError('Connection lost on delete');
        }
        backend = [];
        return Promise.resolve(ok(null));
      }
      if (failReconcile) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve(ok(backend.map((id) => ({ movieId: id }))));
    },
    auth
  );

  h.render();
  await h.settle();
  assert.deepEqual([...h.value.watchlist], ['Y']);

  const firstDel = await h.value.toggleWatchlist('Y');
  await h.settle();

  assert.equal(firstDel, false);
  assert.equal(h.value.isActionPending('Y', 'watchlist'), false);
  assert.equal(h.value.isActionUnconfirmed('Y', 'watchlist'), true);

  const retryDel = await h.value.toggleWatchlist('Y');
  await h.settle();

  assert.equal(retryDel, true);
  assert.deepEqual(methods, ['DELETE', 'DELETE']);
  assert.deepEqual(backend, []);
  assert.deepEqual([...h.value.watchlist], []);
  assert.equal(h.value.isActionUnconfirmed('Y', 'watchlist'), false);
});

test('21. UI H2: MovieCard renders unconfirmed ADD badge/label and click triggers retry POST, returning to normal on confirm', async () => {
  let backend = [];
  let failReconcile = false;
  const methods = [];
  const auth = {
    current: {
      ...makeActor(1),
      handleSessionExpired: () => {},
    },
  };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => {
      if (opts?.method === 'POST') {
        methods.push('POST');
        if (methods.length === 1) {
          backend = ['X'];
          failReconcile = true;
          throw new TypeError('Lost response after commit');
        }
        backend = ['X'];
        return Promise.resolve(ok({ movieId: 'X' }));
      }
      if (failReconcile) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve(ok(backend.map((id) => ({ movieId: id }))));
    },
    auth
  );

  h.render();
  await h.settle();

  await h.value.toggleWatchlist('X', 'Movie X');
  await h.settle();

  assert.equal(h.value.isActionUnconfirmed('X', 'watchlist'), true);
  assert.equal(h.value.getActionIntent('X', 'watchlist'), 'add');

  let cardTree = renderComponent(movieCardFile, 'MovieCard', h.value, auth.current, {
    movie: { id: 'X', title: 'Movie X', poster: '', rating: 8, genres: ['Action'], runtime: '90m' },
  });

  let badges = findElements(cardTree, (n) => n.props?.['data-testid'] === 'unconfirmed-badge');
  let buttons = findElements(cardTree, (n) => n.type === 'button');

  assert.equal(badges.length, 1);

  assert.match(buttons[0].props['aria-label'], /Chưa xác nhận lưu • Thử lưu lại Movie X vào danh sách xem/);
  assert.match(buttons[0].props.title, /Chưa xác nhận lưu • Nhấn để thử lưu lại/);
  assert.match(buttons[0].props.className, /bg-amber-400/);

  buttons[0].props.onClick({ preventDefault: () => {}, stopPropagation: () => {} });
  await h.settle();

  assert.deepEqual(methods, ['POST', 'POST']);
  assert.equal(h.value.isActionUnconfirmed('X', 'watchlist'), false);

  cardTree = renderComponent(movieCardFile, 'MovieCard', h.value, auth.current, {
    movie: { id: 'X', title: 'Movie X', poster: '', rating: 8, genres: ['Action'], runtime: '90m' },
  });

  badges = findElements(cardTree, (n) => n.props?.['data-testid'] === 'unconfirmed-badge');
  buttons = findElements(cardTree, (n) => n.type === 'button');

  assert.equal(badges.length, 0);
  assert.match(buttons[0].props['aria-label'], /Xóa Movie X khỏi danh sách xem/);
  assert.match(buttons[0].props.className, /bg-brand/);
});

test('22. UI H2: MovieCard renders unconfirmed DELETE label and click triggers retry DELETE, returning to normal on confirm', async () => {
  let backend = ['Y'];
  let failReconcile = false;
  const methods = [];
  const auth = {
    current: {
      ...makeActor(1),
      handleSessionExpired: () => {},
    },
  };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => {
      if (opts?.method === 'DELETE') {
        methods.push('DELETE');
        if (methods.length === 1) {
          backend = [];
          failReconcile = true;
          throw new TypeError('Lost response on delete');
        }
        backend = [];
        return Promise.resolve(ok(null));
      }
      if (failReconcile) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve(ok(backend.map((id) => ({ movieId: id }))));
    },
    auth
  );

  h.render();
  await h.settle();

  await h.value.toggleWatchlist('Y', 'Movie Y');
  await h.settle();

  assert.equal(h.value.isActionUnconfirmed('Y', 'watchlist'), true);
  assert.equal(h.value.getActionIntent('Y', 'watchlist'), 'remove');

  let cardTree = renderComponent(movieCardFile, 'MovieCard', h.value, auth.current, {
    movie: { id: 'Y', title: 'Movie Y', poster: '', rating: 8, genres: ['Action'], runtime: '90m' },
  });

  let buttons = findElements(cardTree, (n) => n.type === 'button');

  assert.match(buttons[0].props['aria-label'], /Chưa xác nhận xóa • Thử xóa lại Movie Y khỏi danh sách xem/);
  assert.match(buttons[0].props.title, /Chưa xác nhận xóa • Nhấn để thử xóa lại/);
  assert.match(buttons[0].props.className, /bg-amber-400/);

  buttons[0].props.onClick({ preventDefault: () => {}, stopPropagation: () => {} });
  await h.settle();

  assert.deepEqual(methods, ['DELETE', 'DELETE']);
  assert.equal(h.value.isActionUnconfirmed('Y', 'watchlist'), false);

  cardTree = renderComponent(movieCardFile, 'MovieCard', h.value, auth.current, {
    movie: { id: 'Y', title: 'Movie Y', poster: '', rating: 8, genres: ['Action'], runtime: '90m' },
  });

  buttons = findElements(cardTree, (n) => n.type === 'button');
  assert.match(buttons[0].props['aria-label'], /Thêm Movie Y vào danh sách xem/);
});

test('23. UI H2: MovieDetail renders unconfirmed Watchlist, Favorite, and Rating with explicit retry buttons and handles new rating selection', async () => {
  let ratedScore = null;
  let favoriteClicked = false;
  let watchlistClicked = false;

  const mockContext = {
    isWatchlisted: () => true,
    toggleWatchlist: () => { watchlistClicked = true; return Promise.resolve(true); },
    isFavorite: () => false,
    toggleFavorite: () => { favoriteClicked = true; return Promise.resolve(true); },
    getRating: () => 9,
    rateMovie: (id, score) => { ratedScore = score; return Promise.resolve(true); },
    removeRating: () => Promise.resolve(true),
    isActionPending: () => false,
    isActionUnconfirmed: (id, act) => true,
    getActionIntent: (id, act) => {
      if (act === 'watchlist') return 'add';
      if (act === 'favorite') return 'remove';
      if (act === 'rating') return 'rate';
      return null;
    },
    getUnconfirmedRating: (id) => 9,
    openChat: () => {},
  };

  const detailTree = renderComponent(movieDetailFile, 'MovieDetail', mockContext, {}, {
    movie: {
      id: 'M1',
      title: 'Movie 1',
      poster: '',
      backdrop: '',
      rating: 8.5,
      genres: ['Sci-Fi'],
      year: 2024,
      runtime: '130m',
      description: 'Overview',
    },
    similarMovies: [],
  });

  const watchlistBtn = findElements(detailTree, (n) => n.type === 'button' && n.props?.['aria-label']?.includes('Danh sách xem'))[0];
  assert.match(watchlistBtn.props['aria-label'], /Chưa xác nhận lưu • Thử lưu lại vào Danh sách xem/);
  assert.match(watchlistBtn.props.className, /border-amber-400/);

  watchlistBtn.props.onClick();
  assert.equal(watchlistClicked, true);

  const favBtn = findElements(detailTree, (n) => n.type === 'button' && n.props?.['aria-label']?.includes('Yêu thích'))[0];
  assert.match(favBtn.props['aria-label'], /Chưa xác nhận bỏ thích • Thử xóa lại khỏi Yêu thích/);
  assert.match(favBtn.props.className, /border-amber-400/);

  favBtn.props.onClick();
  assert.equal(favoriteClicked, true);

  const ratingBanner = findElements(detailTree, (n) => n.props?.['data-testid'] === 'rating-unconfirmed-banner')[0];
  assert.ok(ratingBanner);

  const retryRatingBtn = findElements(ratingBanner, (n) => n.type === 'button')[0];
  assert.equal(retryRatingBtn.props['aria-label'], 'Thử lưu lại điểm đánh giá');
  retryRatingBtn.props.onClick();
  assert.equal(ratedScore, 9);

  const star6Btn = findElements(detailTree, (n) => n.type === 'button' && n.props?.['aria-label'] === 'Chấm 6 trên 10 sao')[0];
  assert.ok(star6Btn);
  star6Btn.props.onClick();
  assert.equal(ratedScore, 6);
});

test('24. UI H2: ProfileOverview renders persistent library error banner and orphan retry actions for Watchlist, Favorites, and Ratings', async () => {
  let refetched = false;
  let removedTab = null;

  const mockContext = {
    watchlist: ['orphan-1'],
    favorites: ['orphan-2'],
    ratings: { 'orphan-3': 7 },
    openChat: () => {},
    isLibraryLoading: false,
    libraryError: 'Không thể tải toàn bộ thư viện cá nhân từ máy chủ.',
    refetchLibrary: () => { refetched = true; return Promise.resolve(); },
    isGuestMode: false,
    toggleWatchlist: (id) => { removedTab = 'watchlist'; return Promise.resolve(true); },
    toggleFavorite: (id) => { removedTab = 'favorites'; return Promise.resolve(true); },
    removeRating: (id) => { removedTab = 'ratings'; return Promise.resolve(true); },
    isActionPending: () => false,
    isActionUnconfirmed: (id, act) => true,
    getActionIntent: (id, act) => (act === 'watchlist' ? 'add' : act === 'favorite' ? 'remove' : 'remove_rating'),
  };

  const profileTree = renderComponent(
    profileOverviewFile,
    'ProfileOverview',
    mockContext,
    {
      user: { fullName: 'Alex', email: 'alex@example.com' },
      status: 'authenticated',
      openAuthModal: () => {},
      retryVerify: () => {},
    },
    {},
    ['watchlist', { 'orphan-1': { status: 'not_found' } }]
  );

  const errorBanner = findElements(profileTree, (n) => n.props?.['data-testid'] === 'library-error-banner')[0];
  assert.ok(errorBanner);

  const retryBannerBtn = findElements(errorBanner, (n) => n.type === 'button')[0];
  retryBannerBtn.props.onClick();
  assert.equal(refetched, true);

  const orphanButtons = findElements(profileTree, (n) => n.type === 'button' && n.props?.['aria-label']?.includes('Chưa xác nhận'));
  assert.ok(orphanButtons.length > 0);
  assert.match(orphanButtons[0].props['aria-label'], /Chưa xác nhận lưu • Thử lưu lại/);

  orphanButtons[0].props.onClick();
  assert.equal(removedTab, 'watchlist');
});

test('25. UI H2: ProfileOverview rating retry with production provider executes POST rating without deleting, and respects remove intent and confirmed transition across found/error/not_found rows', async () => {
  let backendRating = 5;
  let failReconcile = false;
  const methods = [];
  const auth = {
    current: {
      ...makeActor(1),
      handleSessionExpired: () => {},
    },
  };

  const h = makeHarness(
    libFile,
    'WatchlistProvider',
    (url, opts) => {
      if (opts?.method === 'POST') {
        methods.push('POST');
        backendRating = JSON.parse(opts.body).rating;
        if (methods.length === 1) {
          failReconcile = true;
          throw new TypeError('Lost response after rating commit');
        }
        return Promise.resolve(ok({ movieId: 'M', rating: backendRating }));
      }
      if (opts?.method === 'DELETE') {
        methods.push('DELETE');
        backendRating = null;
        return Promise.resolve(ok(null));
      }
      if (failReconcile) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve(ok(url.endsWith('ratings') ? (backendRating !== null ? [{ movieId: 'M', rating: backendRating }] : []) : []));
    },
    auth
  );

  h.render();
  await h.settle();

  await h.value.rateMovie('M', 9, 'Movie M');
  await h.settle();

  assert.equal(h.value.isActionUnconfirmed('M', 'rating'), true);
  assert.equal(h.value.getActionIntent('M', 'rating'), 'rate');
  assert.equal(h.value.getUnconfirmedRating('M'), 9);

  let profileTree = renderComponent(
    profileOverviewFile,
    'ProfileOverview',
    h.value,
    auth.current,
    {},
    ['ratings', { M: { status: 'found', movie: { id: 'M', title: 'Movie M', genres: [] } } }]
  );

  let retryBtn = findElements(
    profileTree,
    (n) => n.type === 'button' && n.props?.['aria-label'] === 'Chưa xác nhận điểm • Thử lưu lại điểm đánh giá'
  )[0];
  assert.ok(retryBtn, 'Expected retry rating button in found row');

  await retryBtn.props.onClick();
  await h.settle();

  assert.deepEqual(methods, ['POST', 'POST']);
  assert.equal(backendRating, 9);
  assert.equal(h.value.isActionUnconfirmed('M', 'rating'), false);

  profileTree = renderComponent(
    profileOverviewFile,
    'ProfileOverview',
    h.value,
    auth.current,
    {},
    ['ratings', { M: { status: 'found', movie: { id: 'M', title: 'Movie M', genres: [] } } }]
  );

  let deleteBtn = findElements(
    profileTree,
    (n) => n.type === 'button' && n.props?.['aria-label'] === 'Xóa đánh giá'
  )[0];
  assert.ok(deleteBtn, 'Expected confirmed delete button');

  await deleteBtn.props.onClick();
  await h.settle();

  assert.deepEqual(methods, ['POST', 'POST', 'DELETE']);
  assert.equal(backendRating, null);

  const mockContextRemove = {
    ...h.value,
    ratings: { 'err-1': 8, 'orphan-1': 7 },
    isActionUnconfirmed: () => true,
    getActionIntent: () => 'remove_rating',
    getUnconfirmedRating: () => undefined,
  };

  const errorProfileTree = renderComponent(
    profileOverviewFile,
    'ProfileOverview',
    mockContextRemove,
    auth.current,
    {},
    ['ratings', { 'err-1': { status: 'error' }, 'orphan-1': { status: 'not_found' } }]
  );

  const errorRemoveBtns = findElements(
    errorProfileTree,
    (n) => n.type === 'button' && n.props?.['aria-label'] === 'Chưa xác nhận xóa • Thử xóa lại điểm đánh giá'
  );
  assert.ok(errorRemoveBtns.length >= 2, 'Expected retry remove buttons for error and orphan rows');

  await errorRemoveBtns[0].props.onClick();
  await h.settle();
  assert.equal(methods[methods.length - 1], 'DELETE');
});




test('Favorite retries an uncertain add and rolls back a definite failure', async () => {
  const requests = [];
  let failReads = false;
  const auth = { current: { ...makeActor(1), handleSessionExpired: () => {} } };
  const h = makeHarness(libFile, 'WatchlistProvider', (url, opts) => {
    if (opts?.method) {
      requests.push({ url, method: opts.method, body: opts.body });
      if (requests.length === 1) {
        failReads = true;
        throw new TypeError('Connection lost');
      }
      if (requests.length === 3) return Promise.resolve({ ok: false, status: 500 });
      return Promise.resolve(ok(null));
    }
    return Promise.resolve(failReads ? { ok: false, status: 500 } : ok([]));
  }, auth);

  h.render();
  await h.settle();
  assert.equal(await h.value.toggleFavorite('a/b', 'Film', 'poster'), false);
  await h.settle();
  assert.equal(h.value.getActionIntent('a/b', 'favorite'), 'add');
  assert.deepEqual([...h.value.favorites], ['a/b']);
  assert.equal(await h.value.toggleFavorite('a/b', 'Film', 'poster'), true);
  await h.settle();
  assert.equal(h.value.isActionUnconfirmed('a/b', 'favorite'), false);
  assert.equal(await h.value.toggleFavorite('a/b', 'Film'), false);
  await h.settle();
  assert.deepEqual([...h.value.favorites], ['a/b']);
  assert.deepEqual(requests.map((request) => request.method), ['POST', 'POST', 'DELETE']);
  assert.ok(requests[0].url.endsWith('/users/favorites'));
  assert.ok(requests[2].url.endsWith('/users/favorites/a%2Fb'));
  assert.deepEqual(JSON.parse(requests[0].body), { movieId: 'a/b', movieTitle: 'Film', posterUrl: 'poster' });
  assert.equal(h.value.toasts.at(-1).message, 'Không thể cập nhật Yêu thích. Vui lòng thử lại.');
});
