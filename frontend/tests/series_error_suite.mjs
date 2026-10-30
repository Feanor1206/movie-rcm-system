import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

function find(node, predicate) {
  if (!node || typeof node !== 'object') return null;
  if (Array.isArray(node)) return node.map((child) => find(child, predicate)).find(Boolean) || null;
  return predicate(node) ? node : find(node.props?.children, predicate);
}

test('Episode loading failure offers retry instead of claiming a missing video', async () => {
  const source = fs.readFileSync(new URL('../app/series/[id]/page.tsx', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true, target: ts.ScriptTarget.ES2022,
  } }).outputText;
  let slots = [], index = 0, effects = [], calls = 0;
  const episode = { id: 'ep1', title: 'Episode 1', seasonId: 'season1', number: 1 };
  const react = {
    useState(initial) { const i = index++; if (!(i in slots)) slots[i] = { value: typeof initial === 'function' ? initial() : initial }; return [slots[i].value, (v) => { slots[i].value = typeof v === 'function' ? v(slots[i].value) : v; }]; },
    useRef(initial) { const i = index++; return slots[i] ||= { current: initial }; },
    useEffect(effect, deps) {
      const i = index++, previous = slots[i];
      if (!previous || deps.some((v, j) => !Object.is(v, previous.deps[j]))) {
        slots[i] = { deps, cleanup: previous?.cleanup };
        effects.push(() => { slots[i].cleanup?.(); slots[i].cleanup = effect(); });
      }
    },
    createElement(type, props, ...children) { return { type, props: { ...props, children } }; },
  };
  const module = { exports: {} };
  vm.runInNewContext(code, { module, exports: module.exports, AbortController, URL, console,
    require(name) {
      if (name === 'react') return react;
      if (name === 'next/navigation') return { useParams: () => ({ id: 'series1' }), useSearchParams: () => new URLSearchParams() };
      if (name.includes('catalogService')) return {
        getCatalogSeriesDetail: async () => ({ series: { title: 'Series' }, seasons: [{ id: 'season1', number: 1 }], episodes: [episode] }),
        getCatalogEpisodeDetail: async () => { if (++calls === 1) throw new Error('network'); return { episode, mediaAssets: [], scenes: [], segments: [] }; },
      };
      if (name.includes('episodeNavigation')) return {
        sortCatalogSeasons: (seasons) => seasons, getInitialSeasonId: () => 'season1', getInitialEpisode: () => episode,
        getEpisodesForSeason: (episodes) => episodes, getAdjacentEpisode: () => null,
      };
      if (name.includes('useWatchProgress')) return { useWatchProgress: () => ({ records: [], saveProgress() {} }) };
      if (name.includes('watchProgressService')) return { readAutoNextPreference: () => false, isUsableResumeProgress: () => false };
      return {};
    },
  });
  const render = () => { index = 0; effects = []; const tree = module.exports.default(); for (const effect of effects) effect(); return tree; };
  const settle = async () => { let tree; for (let i = 0; i < 5; i++) { tree = render(); await new Promise(setImmediate); } return render(); };
  let tree = await settle();
  const retry = find(tree, (n) => n.props?.['data-testid'] === 'retry-episode');
  assert.ok(retry, 'episode failure should provide a retry action');
  assert.doesNotMatch(JSON.stringify(tree), /chưa có luồng video Google Drive/);
  retry.props.onClick();
  tree = await settle();
  assert.equal(calls, 2);
  assert.equal(find(tree, (n) => n.props?.['data-testid'] === 'retry-episode'), null);
  assert.match(JSON.stringify(tree), /chưa có.*video/i);
});
