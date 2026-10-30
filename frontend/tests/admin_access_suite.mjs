import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

function compile(path) {
  return ts.transpileModule(fs.readFileSync(new URL(path, import.meta.url), 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true, target: ts.ScriptTarget.ES2022,
  } }).outputText;
}
function find(node, predicate) {
  if (!node || typeof node !== 'object') return null;
  if (Array.isArray(node)) return node.map((child) => find(child, predicate)).find(Boolean) || null;
  return predicate(node) ? node : find(node.props?.children, predicate);
}

test('Admin screen gates requests and supports retry after a partial load failure', async () => {
  let auth = { status: 'guest', user: null, token: null, openAuthModal() {}, retryVerify() {} };
  let slots = [], index = 0, effects = [], requests = [], failHistory = true;
  const react = {
    useState(initial) { const i = index++; if (!(i in slots)) slots[i] = { value: typeof initial === 'function' ? initial() : initial }; return [slots[i].value, (v) => { slots[i].value = typeof v === 'function' ? v(slots[i].value) : v; }]; },
    useEffect(effect, deps) { const i = index++, prev = slots[i]; if (!prev || deps.some((v, j) => !Object.is(v, prev.deps[j]))) { slots[i] = { deps, cleanup: prev?.cleanup }; effects.push(() => { slots[i].cleanup?.(); slots[i].cleanup = effect(); }); } },
    createElement(type, props, ...children) { return { type, props: { ...props, children } }; },
  };
  const module = { exports: {} };
  vm.runInNewContext(compile('../app/admin/import/page.tsx'), { module, exports: module.exports, AbortController,
    require(name) {
      if (name === 'react') return react;
      if (name.includes('AuthContext')) return { useAuth: () => auth };
      if (name.includes('catalogService')) return {
        getCatalogSeriesList: async (_, signal) => { requests.push(signal); return []; },
        getImportHistory: async (_, signal) => { requests.push(signal); if (failHistory) throw Error('offline'); return []; },
        getCatalogSnapshots: async (_, signal) => { requests.push(signal); return []; },
      };
      return {};
    },
  });
  const render = () => { index = 0; effects = []; const tree = module.exports.default(); for (const effect of effects) effect(); return tree; };
  const settle = async () => { let tree; for (let i = 0; i < 3; i++) { tree = render(); await new Promise(setImmediate); } return render(); };
  let tree = await settle();
  assert.equal(requests.length, 0);
  assert.ok(find(tree, (n) => n.props?.['data-testid'] === 'admin-sign-in'));
  auth = { ...auth, status: 'authenticated', token: 'user-token', user: { role: 'ROLE_USER' } };
  tree = await settle();
  assert.equal(requests.length, 0);
  assert.ok(find(tree, (n) => n.props?.['data-testid'] === 'admin-forbidden'));
  auth = { ...auth, token: 'admin-token', user: { role: 'ROLE_ADMIN' } };
  tree = await settle();
  assert.equal(requests.length, 3);
  assert.ok(find(tree, (n) => n.props?.['data-testid'] === 'history-error'));
  assert.doesNotMatch(JSON.stringify(find(tree, (n) => n.props?.['data-testid'] === 'history-error')), /Chưa có lịch sử/);
  failHistory = false;
  find(tree, (n) => n.props?.['data-testid'] === 'history-error').props.children[0].props.onRetry();
  tree = await settle();
  assert.equal(requests.length, 6);
  assert.equal(find(tree, (n) => n.props?.['data-testid'] === 'history-error'), null);
  auth = { ...auth, status: 'guest', user: null, token: null };
  await settle();
  assert.ok(requests.slice(-3).every((signal) => signal.aborted));
});

test('Admin history and snapshots reject HTTP errors instead of reporting empty lists', async () => {
  const module = { exports: {} };
  vm.runInNewContext(compile('../lib/services/catalogService.ts'), { module, exports: module.exports,
    process: { env: {} }, fetch: async () => ({ ok: false, status: 403 }), AbortController, setTimeout, clearTimeout,
  });
  await assert.rejects(module.exports.getImportHistory(), /403/);
  await assert.rejects(module.exports.getCatalogSnapshots(), /403/);
});

test('Validation preserves structured 400 errors and rejects authorization failures', async () => {
  let response = { ok: false, status: 400, json: async () => ({ valid: false, errors: [{ message: 'invalid package' }] }) };
  const module = { exports: {} };
  vm.runInNewContext(compile('../lib/services/catalogService.ts'), { module, exports: module.exports,
    process: { env: {} }, fetch: async () => response, AbortController, setTimeout, clearTimeout,
  });
  assert.equal((await module.exports.validateCatalogPackage({})).errors[0].message, 'invalid package');
  response = { ok: false, status: 403, json: async () => ({}) };
  await assert.rejects(module.exports.validateCatalogPackage({}), /403/);
});

test('Admin history and snapshot loads time out while a response body stalls', async () => {
  const module = { exports: {} };
  vm.runInNewContext(compile('../lib/services/catalogService.ts'), { module, exports: module.exports,
    process: { env: {} }, AbortController, setTimeout, clearTimeout,
    fetch: async (_, { signal }) => ({ ok: true, json: () => new Promise((_, reject) => signal.addEventListener('abort', () => reject(new Error('aborted')))) }),
  });
  for (const name of ['getImportHistory', 'getCatalogSnapshots']) {
    await assert.rejects(module.exports[name]('/api', undefined, 20), (err) => err.isTimeout === true);
  }
});

test('Editing a catalog while validation is pending cannot authorize the edited payload', async () => {
  let slots = [], index = 0, resolveValidation, imports = 0;
  const react = {
    useState(initial) { const i = index++; if (!(i in slots)) slots[i] = { value: typeof initial === 'function' ? initial() : initial }; return [slots[i].value, (v) => { slots[i].value = typeof v === 'function' ? v(slots[i].value) : v; }]; },
    useRef(initial) { const i = index++; return slots[i] ||= { current: initial }; },
    createElement(type, props, ...children) { return { type, props: { ...props, children } }; },
  };
  const module = { exports: {} };
  vm.runInNewContext(compile('../features/admin/components/CatalogImportModal.tsx'), { module, exports: module.exports,
    require(name) {
      if (name === 'react') return react;
      if (name.includes('catalogService')) return {
        validateCatalogPackage: () => new Promise((resolve) => { resolveValidation = resolve; }),
        importCatalogPackage: async () => { imports++; return {}; },
      };
      return {};
    },
  });
  const render = () => { index = 0; return module.exports.CatalogImportModal({}); };
  let tree = render();
  const node = (id) => find(tree, (n) => n.props?.['data-testid'] === id);
  node('catalog-json-textarea').props.onChange({ target: { value: '{"version":1}' } }); tree = render();
  const pending = node('catalog-validate-button').props.onClick(); tree = render();
  node('catalog-json-textarea').props.onChange({ target: { value: '{"version":2}' } }); tree = render();
  resolveValidation({ valid: true, contentHash: 'old', errors: [] }); await pending; tree = render();
  await node('catalog-import-button').props.onClick(); tree = render();
  assert.equal(imports, 0);
  assert.ok(node('catalog-import-error'));
});
