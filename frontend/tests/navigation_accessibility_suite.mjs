import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

function renderComponent(path, exportName, mocks) {
  const source = fs.readFileSync(new URL(path, import.meta.url), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true, target: ts.ScriptTarget.ES2022,
  } }).outputText;
  let slots = [], index = 0;
  const react = {
    useState(initial) {
      const i = index++;
      if (!(i in slots)) slots[i] = typeof initial === 'function' ? initial() : initial;
      return [slots[i], (value) => { slots[i] = typeof value === 'function' ? value(slots[i]) : value; }];
    },
    useRef(initial) { const i = index++; return slots[i] ||= { current: initial }; },
    useEffect() {},
    createElement(type, props, ...children) { return { type, props: { ...props, children } }; },
  };
  const module = { exports: {} };
  vm.runInNewContext(code, { module, exports: module.exports, require(name) {
    return name === 'react' ? react : mocks[name] || {};
  } });
  return () => { index = 0; return module.exports[exportName](); };
}

function nodes(node, predicate) {
  if (!node || typeof node !== 'object') return [];
  if (Array.isArray(node)) return node.flatMap((child) => nodes(child, predicate));
  return [...(predicate(node) ? [node] : []), ...nodes(node.props?.children, predicate)];
}

test('Authenticated mobile navigation offers logout and closes after use', () => {
  let logouts = 0;
  const render = renderComponent('../components/layout/Navbar.tsx', 'Navbar', {
    'next/navigation': { usePathname: () => '/' },
    '@/lib/context/WatchlistContext': { useWatchlist: () => ({ watchlist: [], openChat() {} }) },
    '@/lib/context/AuthContext': { useAuth: () => ({ isAuthenticated: true, user: { username: 'user' }, logout: () => logouts++ }) },
  });
  let tree = render();
  nodes(tree, (n) => n.props?.['aria-label'] === 'Mở menu')[0].props.onClick();
  tree = render();
  const mobileMenu = nodes(tree, (n) => n.props?.id === 'mobile-navigation')[0];
  const logout = nodes(mobileMenu, (n) => n.type === 'button' && n.props?.['data-testid'] === 'mobile-logout')[0];
  assert.ok(logout, 'mobile menu should contain a logout action');
  logout.props.onClick();
  assert.equal(logouts, 1);
  assert.equal(nodes(render(), (n) => n.props?.id === 'mobile-navigation').length, 0);
});

test('Every visible authentication input has a programmatically associated label', () => {
  for (const mode of ['login', 'register']) {
    const render = renderComponent('../features/auth/components/AuthModal.tsx', 'AuthModal', {
      '@/lib/context/AuthContext': { useAuth: () => ({ isAuthModalOpen: true, authModalMode: mode }) },
      '@/lib/context/WatchlistContext': { useWatchlist: () => ({ showToast() {} }) },
    });
    const tree = render();
    const inputs = nodes(tree, (n) => n.type === 'input');
    const labels = nodes(tree, (n) => n.type === 'label');
    for (const input of inputs) {
      assert.ok(input.props.id && labels.some((label) => label.props.htmlFor === input.props.id), `${mode}: ${input.props.type} input needs a label`);
    }
  }
});
