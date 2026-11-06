// Reviewer-only actual-source checks. No server, model, browser or live DB.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../../frontend');
const ts = require(path.join(root, 'node_modules/typescript'));
let now = Date.now();
class TestDate extends Date { static now() { return now; } }
let helpers = fs.readFileSync(path.join(root, 'tests/m2_journey_suite.mjs'), 'utf8');
helpers = helpers.slice(helpers.indexOf('const homeFilePath'), helpers.indexOf("test('1. Home:"));
const profileStart = helpers.indexOf('function createProfileHarness(');
let profile = helpers.slice(profileStart);
profile = profile.replace('const context = {', 'const context = { Date: TestDate,');
profile = profile.replace('return { render, settle, get tree() { return tree; } };',
  'return { render, settle, setLibrary(next) { Object.assign(defaultWatchlist, next); render(); }, get tree() { return tree; } };');
helpers = helpers.slice(0, profileStart) + profile;
const box = { fs, path, vm, ts, root, TestDate, console, AbortController, setImmediate };
vm.runInNewContext(helpers + '\nglobalThis.review = {createDetailHarness, createProfileHarness, sampleMovie, findNodes, getText};', box);
const {createDetailHarness, createProfileHarness, sampleMovie, findNodes, getText} = box.review;
const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return {promise, resolve}; };

(async () => {
  const similar = deferred();
  let lookupResolved = false;
  const h = createDetailHarness('A', async id => { lookupResolved = true; return sampleMovie({id}); },
    () => similar.promise);
  h.render();
  await h.settle(); // A main lookup succeeded, similar rail is pending.
  const before = findNodes(h.tree, n => n.type === 'MovieDetail')[0];
  console.log(JSON.stringify({scenario: 'valid main lookup held behind pending optional similar rail', lookupResolved, mainDetailVisible: Boolean(before)}));
  assert.equal(lookupResolved, true);
  assert.equal(before, undefined, 'Reproduces hidden main movie until optional rail finishes');
  similar.resolve({items: []});
  await h.settle();
  assert.equal(findNodes(h.tree, n => n.type === 'MovieDetail')[0].props.movie.id, 'A');

  let calls = 0;
  const p = createProfileHarness({watchlist: ['X'], favorites: [], ratings: {}}, async id => {
    calls++;
    return calls === 1 ? sampleMovie({id, title: 'Old title'}) : null;
  });
  p.render(); await p.settle();
  now += 6 * 60 * 1000;
  p.setLibrary({watchlist: []}); await p.settle();
  p.setLibrary({watchlist: ['X']}); await p.settle();
  const card = findNodes(p.tree, n => n.type === 'MovieCard')[0];
  console.log(JSON.stringify({scenario: 'expired Profile metadata removed and re-added after 6 minutes', calls, renderedTitle: card?.props.movie.title}));
  assert.equal(calls, 1, 'Reproduces TTL bypass through remoteMovies');
  assert.equal(card?.props.movie.title, 'Old title');

  const heroModule = {exports: {}};
  const hooks = {createElement: (type, props, ...children) => ({type, props: {...props, children}})};
  const heroJs = ts.transpileModule(fs.readFileSync(path.join(root, 'features/home/components/EditorialHero.tsx'), 'utf8'), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true}
  }).outputText;
  vm.runInNewContext(heroJs, {module: heroModule, exports: heroModule.exports, require: name => {
    if (name === 'react') return {__esModule: true, default: hooks, ...hooks};
    if (name.includes('WatchlistContext')) return {useWatchlist: () => ({isWatchlisted: () => true, toggleWatchlist() {}, openChat() {}, isActionPending: () => false, isActionUnconfirmed: () => true, getActionIntent: () => 'add'})};
    if (name === 'lucide-react') return new Proxy({}, {get: (_, key) => key});
    return {__esModule: true, default: name};
  }});
  const hero = heroModule.exports.EditorialHero({movie: sampleMovie({id: 'X'})});
  const button = findNodes(hero, n => n.type === 'button' && n.props['aria-label'])[0];
  console.log(JSON.stringify({scenario: 'Hero uncertain ADD displays opposite intent', ariaLabel: button.props['aria-label'], text: getText(button)}));
  assert.equal(button.props['aria-label'], 'Xóa khỏi Watchlist');
  console.log('All 3 current defects reproduced (exit 0 means reproduction succeeded, not acceptance).');
})().catch(err => { console.error(err); process.exitCode = 1; });
