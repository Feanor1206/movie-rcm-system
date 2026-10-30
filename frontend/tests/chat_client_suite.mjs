import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

test('Resetting a pending chat discards its reply and allows a new conversation', async () => {
  const source = fs.readFileSync(new URL('../features/chat/components/CineBot.tsx', import.meta.url), 'utf8');
  const componentCode = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React, esModuleInterop: true,
  } }).outputText;
  let slots = [], index = 0, tree;
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
  const requests = [];
  const module = { exports: {} };
  vm.runInNewContext(componentCode, { module, exports: module.exports, console, Date, AbortController, setTimeout, clearTimeout,
    require(name) {
      if (name === 'react') return react;
      if (name === '@/lib/services/chatService') return { sendChatMessage: (text, history, options) => new Promise((resolve) => requests.push({ resolve, options })) };
      if (name === '@/lib/context/WatchlistContext') return { useWatchlist: () => ({ isWatchlisted: () => false, toggleWatchlist() {} }) };
      if (name === '@/lib/context/AuthContext') return { useAuth: () => ({ status: 'guest', user: null, token: null }) };
      return {};
    },
  });
  const render = () => { index = 0; tree = module.exports.CineBot({ isOpen: true, onClose() {} }); if (typeof tree?.type === 'function') { index = 0; tree = tree.type(tree.props); } };
  const nodes = (node, predicate) => !node || typeof node !== 'object' ? [] : [
    ...(predicate(node) ? [node] : []), ...((node.props?.children || []).flatMap((child) => Array.isArray(child) ? child.flatMap((item) => nodes(item, predicate)) : nodes(child, predicate))),
  ];
  const button = (label) => nodes(tree, (node) => node.type === 'button' && node.props['aria-label'] === label)[0];
  const input = () => nodes(tree, (node) => node.type === 'input')[0];
  render();
  input().props.onChange({ target: { value: 'First question' } }); render();
  button('Gửi tin nhắn').props.onClick(); render();
  button('Làm mới cuộc trò chuyện').props.onClick(); render();
  assert.equal(requests[0].options.signal.aborted, true);
  assert.equal(input().props.disabled, false);
  input().props.onChange({ target: { value: 'Second question' } }); render();
  button('Gửi tin nhắn').props.onClick(); render();
  assert.notEqual(requests[0].options.sessionId, requests[1].options.sessionId);
  requests[0].resolve({ text: 'Old reply' }); await new Promise(setImmediate); render();
  assert.equal(input().props.disabled, true, 'old request must not unlock the new request');
  requests[1].resolve({ text: 'New reply' }); await new Promise(setImmediate); render();
  assert.doesNotMatch(JSON.stringify(tree), /Old reply/);
  assert.match(JSON.stringify(tree), /New reply/);
  input().props.onChange({ target: { value: 'Follow-up' } }); render();
  button('Gửi tin nhắn').props.onClick(); render();
  assert.equal(requests[1].options.sessionId, requests[2].options.sessionId);
  requests[2].resolve({ text: 'Follow-up reply' }); await new Promise(setImmediate);
});

test('Chat changes actor without exposing old messages or reusing the session', async () => {
  const source = fs.readFileSync(new URL('../features/chat/components/CineBot.tsx', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React, esModuleInterop: true } }).outputText;
  let slots = [], index = 0, actor = { status: 'guest', user: null, token: null }, key, cleanup;
  const requests = [];
  const react = {
    useState(initial) { const i = index++; if (!(i in slots)) slots[i] = typeof initial === 'function' ? initial() : initial; return [slots[i], (v) => { slots[i] = typeof v === 'function' ? v(slots[i]) : v; }]; },
    useRef(initial) { const i = index++; return slots[i] ||= { current: initial }; },
    useEffect(fn, deps) { if (deps.length === 0 && !cleanup) cleanup = fn(); },
    createElement(type, props, ...children) { return { type, props: { ...props, children } }; },
  };
  const module = { exports: {} };
  vm.runInNewContext(code, { module, exports: module.exports, console, Date, AbortController, setTimeout, clearTimeout,
    require(name) {
      if (name === 'react') return react;
      if (name === '@/lib/context/AuthContext') return { useAuth: () => actor };
      if (name === '@/lib/context/WatchlistContext') return { useWatchlist: () => ({ isWatchlisted: () => false, toggleWatchlist() {} }) };
      if (name === '@/lib/services/chatService') return { sendChatMessage: (text, history, options) => new Promise((resolve) => requests.push({ resolve, options })) };
      return {};
    },
  });
  let tree;
  const render = (isOpen = true) => {
    index = 0;
    const root = module.exports.CineBot({ isOpen, onClose() {} });
    if (typeof root?.type === 'function') {
      if (root.props.key !== key) { cleanup?.(); cleanup = undefined; slots = []; key = root.props.key; }
      index = 0; tree = root.type(root.props);
    } else tree = root;
  };
  const nodes = (node, predicate) => !node || typeof node !== 'object' ? [] : Array.isArray(node) ? node.flatMap((n) => nodes(n, predicate)) : [...(predicate(node) ? [node] : []), ...nodes(node.props?.children, predicate)];
  const input = () => nodes(tree, (n) => n.type === 'input')[0];
  const send = () => nodes(tree, (n) => n.props?.['aria-label'] === 'Gửi tin nhắn')[0].props.onClick();
  render(); input().props.onChange({ target: { value: 'Private guest question' } }); render(); send(); render();
  render(false); render();
  assert.match(JSON.stringify(tree), /Private guest question/);
  actor = { status: 'authenticated', user: { id: 8 }, token: 'account-token' }; render();
  assert.equal(requests[0].options.signal.aborted, true);
  assert.doesNotMatch(JSON.stringify(tree), /Private guest question/);
  input().props.onChange({ target: { value: 'Account question' } }); render(); send(); render();
  assert.notEqual(requests[0].options.sessionId, requests[1].options.sessionId);
  requests[0].resolve({ text: 'Old private reply' }); await new Promise(setImmediate); render();
  assert.doesNotMatch(JSON.stringify(tree), /Old private reply/);
  actor = { status: 'checking', user: null, token: null }; render();
  assert.equal(requests[1].options.signal.aborted, true);
  assert.doesNotMatch(JSON.stringify(tree), /Account question/);
});

test('Oversized messages show an error without entering history', async () => {
  // Exercise the component's event handlers, including non-browser input events.
  const source = fs.readFileSync(new URL('../features/chat/components/CineBot.tsx', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React, esModuleInterop: true } }).outputText;
  let slots = [], index = 0, requests = [];
  const react = { useState(v) { const i = index++; if (!(i in slots)) slots[i] = typeof v === 'function' ? v() : v; return [slots[i], (n) => { slots[i] = typeof n === 'function' ? n(slots[i]) : n; }]; }, useRef(v) { const i = index++; return slots[i] ||= { current: v }; }, useEffect() {}, createElement(type, props, ...children) { return { type, props: { ...props, children } }; } };
  const module = { exports: {} };
  vm.runInNewContext(code, { module, exports: module.exports, console, Date, AbortController, setTimeout, clearTimeout, require(name) {
    if (name === 'react') return react;
    if (name === '@/lib/context/AuthContext') return { useAuth: () => ({ status: 'guest', user: null, token: null }) };
    if (name === '@/lib/context/WatchlistContext') return { useWatchlist: () => ({ isWatchlisted: () => false, toggleWatchlist() {} }) };
    if (name === '@/lib/services/chatService') return { sendChatMessage: (text, history) => { requests.push({ text, history }); return new Promise(() => {}); } };
    return {};
  } });
  let tree;
  const render = () => { index = 0; tree = module.exports.CineBot({ isOpen: true, onClose() {} }); if (typeof tree?.type === 'function') { index = 0; tree = tree.type(tree.props); } };
  const nodes = (n, p) => !n || typeof n !== 'object' ? [] : Array.isArray(n) ? n.flatMap((x) => nodes(x, p)) : [...(p(n) ? [n] : []), ...nodes(n.props?.children, p)];
  const input = () => nodes(tree, (n) => n.type === 'input')[0];
  const send = () => nodes(tree, (n) => n.props?.['aria-label'] === 'Gửi tin nhắn')[0].props.onClick();
  render(); assert.equal(input().props.maxLength, 4000);
  input().props.onChange({ target: { value: 'x'.repeat(4001) } }); render(); send(); render();
  assert.equal(requests.length, 0);
  assert.ok(nodes(tree, (n) => n.props?.role === 'alert').length);
  input().props.onChange({ target: { value: 'Valid question' } }); render(); send(); render();
  assert.equal(requests.length, 1);
  assert.ok(requests[0].history.every((m) => m.text.length <= 4000));
});

test('Chat client sends the session, cancellation signal, and bounded recent history', async () => {
  const source = fs.readFileSync(new URL('../lib/services/chatService.ts', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  let sent;
  vm.runInNewContext(code, { module, exports: module.exports, fetch: async (url, init) => {
    sent = { url, init, body: JSON.parse(init.body) };
    return { ok: true, json: async () => ({ text: 'ok' }) };
  } });
  const controller = new AbortController();
  const history = Array.from({ length: 30 }, (_, i) => ({ sender: 'user', text: `message ${i}` }));
  await module.exports.sendChatMessage('last', history, { sessionId: 'conversation-1', signal: controller.signal });
  assert.equal(sent.body.sessionId, 'conversation-1');
  assert.equal(sent.init.signal, controller.signal);
  assert.equal(sent.body.messages.length, 20);
  assert.equal(sent.body.messages[0].content, 'message 10');
});
