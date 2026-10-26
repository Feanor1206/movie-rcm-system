import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import ts from 'typescript';
import { fileURLToPath } from 'node:url';

/**
 * Search Experience & MovieCard Production Component Test Suite (Round 5 - S4)
 *
 * This test suite executes ACTUAL production components (SearchExperience.tsx and MovieCard.tsx)
 * via TypeScript transpile and a lightweight React execution harness.
 * It contains NO simulated search/catalog helpers (such as parseSearchExperienceUrl,
 * serializeSearchUrl, or synthetic mockFetch).
 */

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, '..');

const searchFilePath = path.join(root, 'features/search/components/SearchExperience.tsx');
const movieCardFilePath = path.join(root, 'features/movies/components/MovieCard.tsx');

const searchSource = fs.readFileSync(searchFilePath, 'utf8');
const movieCardSource = fs.readFileSync(movieCardFilePath, 'utf8');

const transpileOptions = {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    jsx: ts.JsxEmit.React,
    esModuleInterop: true,
    target: ts.ScriptTarget.ES2022,
  },
};

const searchTranspiled = ts.transpileModule(searchSource, transpileOptions).outputText;
const movieCardTranspiled = ts.transpileModule(movieCardSource, transpileOptions).outputText;

// Resolve the production navigation helper alongside the component under test.
const mediaRoutingModule = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.resolve(__dirname, '../lib/services/mediaRouting.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { exports: mediaRoutingModule.exports, module: mediaRoutingModule, URLSearchParams });

const turn = () => new Promise((resolve) => setImmediate(resolve));

function emptyPage(options = {}) {
  return {
    items: [],
    page: options.page || 0,
    size: options.size || 12,
    totalElements: 0,
    totalPages: 0,
    hasNext: false,
    hasPrevious: false,
  };
}

function sampleMovie(overrides = {}) {
  return {
    id: overrides.id || 'anim-movie-1',
    title: overrides.title || 'Spirited Away',
    overview: overrides.overview || 'A magical adventure',
    poster: overrides.poster !== undefined ? overrides.poster : 'https://image.example.com/poster.jpg',
    backdrop: 'https://image.example.com/backdrop.jpg',
    year: overrides.year || 2001,
    rating: overrides.rating || 8.6,
    genres: overrides.genres || ['Animation', 'Adventure'],
    runtime: overrides.runtime || '125 min',
    isAnimation: true,
    ...overrides,
  };
}

// Tree inspection helpers
function findNodes(node, pred, out = []) {
  if (!node) return out;
  if (Array.isArray(node)) {
    for (const child of node) findNodes(child, pred, out);
    return out;
  }
  if (typeof node === 'object') {
    if (pred(node)) out.push(node);
    findNodes(node.props?.children, pred, out);
  }
  return out;
}

function getText(node) {
  function collect(n) {
    if (Array.isArray(n)) return n.map(collect).join(' ');
    if (n && typeof n === 'object') return collect(n.props?.children);
    return typeof n === 'string' || typeof n === 'number' ? String(n) : '';
  }
  return collect(node).replace(/\s+/g, ' ').trim();
}

// Harness to execute actual SearchExperience.tsx
function createSearchHarness(initialUrl = '', catalogMocks = {}) {
  const mocks = typeof catalogMocks === 'function' ? {} : catalogMocks;
  let params = new URLSearchParams(initialUrl);
  let slots = [];
  let hookIndex = 0;
  let effects = [];
  let dirty = false;
  let tree = null;
  const pushes = [];
  const timers = new Map();
  let timerSeq = 0;
  const abortedSignals = [];

  const sameDeps = (a, b) => a && b && a.length === b.length && a.every((x, j) => Object.is(x, b[j]));

  const hooks = {
    useState(initial) {
      const idx = hookIndex++;
      if (!slots[idx]) {
        slots[idx] = { v: typeof initial === 'function' ? initial() : initial };
      }
      return [
        slots[idx].v,
        (updater) => {
          const next = typeof updater === 'function' ? updater(slots[idx].v) : updater;
          slots[idx].v = next;
          dirty = true;
        },
      ];
    },
    useRef(initial) {
      const idx = hookIndex++;
      if (!slots[idx]) {
        slots[idx] = { current: initial };
      }
      return slots[idx];
    },
    useMemo(factory, deps) {
      const idx = hookIndex++;
      if (!slots[idx] || !sameDeps(slots[idx].deps, deps)) {
        slots[idx] = { v: factory(), deps };
      }
      return slots[idx].v;
    },
    useCallback(fn, deps) {
      return hooks.useMemo(() => fn, deps);
    },
    useEffect(fn, deps) {
      const idx = hookIndex++;
      if (!slots[idx] || !sameDeps(slots[idx].deps, deps)) {
        const old = slots[idx];
        slots[idx] = { deps, cleanup: old?.cleanup };
        effects.push(() => {
          if (typeof slots[idx].cleanup === 'function') {
            slots[idx].cleanup();
          }
          slots[idx].cleanup = fn();
        });
      }
    },
    createElement(type, props, ...children) {
      const flatChildren = children.length === 1 ? children[0] : children.length > 1 ? children : undefined;
      return {
        type,
        props: {
          ...props,
          ...(flatChildren !== undefined ? { children: flatChildren } : {}),
        },
      };
    },
  };

  const router = {
    push: (u) => pushes.push(u),
  };

  class HarnessAbortController {
    constructor() {
      this.signal = { aborted: false, onabort: null };
    }
    abort() {
      this.signal.aborted = true;
      abortedSignals.push(this.signal);
      if (typeof this.signal.onabort === 'function') {
        this.signal.onabort();
      }
    }
  }

  const moduleObj = { exports: {} };
  const context = {
    module: moduleObj,
    exports: moduleObj.exports,
    URLSearchParams,
    AbortController: HarnessAbortController,
    console,
    setTimeout: (fn, ms) => {
      const id = ++timerSeq;
      timers.set(id, { fn, ms });
      return id;
    },
    clearTimeout: (id) => {
      timers.delete(id);
    },
    require: (mod) => {
      if (mod === 'react') return { __esModule: true, default: hooks, ...hooks };
      if (mod === 'next/navigation') {
        return {
          useSearchParams: () => params,
          useRouter: () => router,
          usePathname: () => '/search',
        };
      }
      if (mod.includes('mediaRouting')) return mediaRoutingModule.exports;
      if (mod.includes('catalogService')) {
        return {
          getCatalogSeriesList: mocks.seriesList || (async () => []),
          searchAnimationCatalog: mocks.search || (async () => []),
        };
      }
      if (mod.includes('WatchlistContext')) {
        return { useWatchlist: () => ({ openChat: () => {} }) };
      }
      if (mod === 'lucide-react') {
        return new Proxy({}, { get: (_, key) => key });
      }
      if (mod.includes('MovieCard')) {
        return {
          MovieCard: 'MovieCard',
        };
      }
      return {};
    },
  };

  vm.runInNewContext(searchTranspiled, context, { filename: searchFilePath });

  function render() {
    hookIndex = 0;
    dirty = false;
    tree = moduleObj.exports.SearchExperience();
    const pendingEffects = effects;
    effects = [];
    for (const ef of pendingEffects) {
      ef();
    }
    return tree;
  }

  async function settle(maxPasses = 8) {
    for (let pass = 0; pass < maxPasses; pass++) {
      await turn();
      if (dirty || pass === 0) {
        render();
      }
    }
    return tree;
  }

  function runTimer(predicate) {
    for (const [id, t] of timers.entries()) {
      if (!predicate || predicate(t)) {
        timers.delete(id);
        t.fn();
        return true;
      }
    }
    return false;
  }

  function unmount() {
    for (const slot of slots) {
      if (slot && typeof slot.cleanup === 'function') {
        slot.cleanup();
        slot.cleanup = null;
      }
    }
  }

  return {
    render,
    settle,
    pushes,
    timers,
    runTimer,
    unmount,
    abortedSignals,
    navigate: (newUrl) => {
      params = new URLSearchParams(newUrl);
      render();
    },
    get tree() {
      return tree;
    },
  };
}

// Harness to execute actual MovieCard.tsx
function renderActualMovieCard(movie, watchlistContext = {}) {
  let slots = [];
  let hookIndex = 0;

  const hooks = {
    useState(initial) {
      const idx = hookIndex++;
      if (!slots[idx]) slots[idx] = { v: typeof initial === 'function' ? initial() : initial };
      return [slots[idx].v, (next) => { slots[idx].v = next; }];
    },
    createElement(type, props, ...children) {
      const flat = children.length === 1 ? children[0] : children.length > 1 ? children : undefined;
      return {
        type,
        props: { ...props, ...(flat !== undefined ? { children: flat } : {}) },
      };
    },
  };

  const defaultWatchlist = {
    isWatchlisted: () => false,
    toggleWatchlist: () => {},
    isActionPending: () => false,
    isActionUnconfirmed: () => false,
    getActionIntent: () => null,
    ...watchlistContext,
  };

  const moduleObj = { exports: {} };
  const context = {
    module: moduleObj,
    exports: moduleObj.exports,
    console,
    require: (mod) => {
      if (mod === 'react') return { __esModule: true, default: hooks, ...hooks };
      if (mod === 'next/image') {
        return {
          default: 'next/image',
          __esModule: true,
        };
      }
      if (mod === 'next/link') {
        return {
          default: 'next/link',
          __esModule: true,
        };
      }
      if (mod === 'lucide-react') {
        return new Proxy({}, { get: (_, name) => name });
      }
      if (mod.includes('mediaRouting')) return mediaRoutingModule.exports;
      if (mod.includes('WatchlistContext')) {
        return { useWatchlist: () => defaultWatchlist };
      }
      return {};
    },
  };

  vm.runInNewContext(movieCardTranspiled, context, { filename: movieCardFilePath });
  hookIndex = 0;
  return moduleObj.exports.MovieCard({ movie, fluid: true });
}

// ============================================================================
// TEST SUITE: S1, S2, S3, S4 ON ACTUAL PRODUCTION CODE
// ============================================================================

test('1. S1 (P2): Delayed router navigation does NOT overwrite user typing draft', async () => {
  const h = createSearchHarness('q=A');
  h.render();
  await h.settle();

  const inputNode = findNodes(h.tree, (n) => n.type === 'input')[0];
  assert.ok(inputNode, 'Search input must exist');
  assert.equal(inputNode.props.value, 'A', 'Initial input must match URL query A');

  // User types 'B'
  inputNode.props.onChange({ target: { value: 'B' } });
  await h.settle();

  // 350ms debounce fires push to /search?q=B
  const firedDebounce = h.runTimer((t) => t.ms === 350);
  assert.ok(firedDebounce, 'Debounce timer of 350ms must fire');
  assert.deepEqual(h.pushes, ['/search?q=B'], 'Router push must record /search?q=B');

  // User types 'C' before router navigation to B finishes
  findNodes(h.tree, (n) => n.type === 'input')[0].props.onChange({ target: { value: 'C' } });
  await h.settle();

  const draftBefore = findNodes(h.tree, (n) => n.type === 'input')[0].props.value;
  assert.equal(draftBefore, 'C');

  // Delayed router navigation to B now arrives
  h.navigate('q=B');
  await h.settle();

  // Input draft MUST NOT be overwritten back to 'B'
  const draftAfter = findNodes(h.tree, (n) => n.type === 'input')[0].props.value;
  assert.equal(draftAfter, 'C', 'User typing of "C" must be preserved over delayed router "B"');

  // Subsequent debounce will now push 'C'
  h.runTimer((t) => t.ms === 350);
  assert.ok(h.pushes.includes('/search?q=C'), 'Subsequent debounce pushes draft C');
});

test('2. S1 (P2): External navigation (browser back/forward or deep link) syncs draft input', async () => {
  const h = createSearchHarness('q=original');
  h.render();
  await h.settle();

  assert.equal(findNodes(h.tree, (n) => n.type === 'input')[0].props.value, 'original');

  // External back button navigation to q=previous (no pending push in flight)
  h.navigate('q=previous');
  await h.settle();

  assert.equal(
    findNodes(h.tree, (n) => n.type === 'input')[0].props.value,
    'previous',
    'External navigation must sync draft input to URL parameter'
  );
});

test('3. S1 (P2): Clear button resets input draft and triggers push with query removed', async () => {
  const h = createSearchHarness('q=spirited');
  h.render();
  await h.settle();

  // Find the clear button (button with aria-label containing "Xóa từ khóa")
  const clearBtn = findNodes(h.tree, (n) => n.type === 'button' && n.props?.['aria-label'] === 'Xóa từ khóa')[0];
  assert.ok(clearBtn, 'Clear button must be rendered when input is non-empty');

  clearBtn.props.onClick();
  await h.settle();

  assert.equal(findNodes(h.tree, (n) => n.type === 'input')[0].props.value, '', 'Input must be cleared');
  assert.ok(
    h.pushes.some((u) => !u.includes('q=')),
    'Router push must remove q parameter upon clear'
  );
});

test('4. Catalog search: pending query does not render a false empty state', async () => {
  let resolveSearch;
  const h = createSearchHarness('q=new', {
    seriesList: async () => [],
    search: async () => new Promise((resolve) => { resolveSearch = resolve; }),
  });
  h.render();
  await h.settle();

  assert.equal(findNodes(h.tree, (node) => node.props?.['data-testid'] === 'catalog-skeleton').length, 1);
  assert.equal(getText(h.tree).includes('Không tìm thấy câu chuyện phù hợp'), false);

  resolveSearch([]);
  await h.settle();
  assert.ok(getText(h.tree).includes('Không tìm thấy câu chuyện phù hợp'));
  assert.ok(getText(h.tree).includes('Không có bộ, tập hoặc phân cảnh khớp'));
});

test('5. Catalog search: query navigation never labels old results as the new query', async () => {
  let resolveSecond;
  const h = createSearchHarness('q=first', {
    seriesList: async () => [],
    search: async (query) => {
      if (query === 'second') return new Promise((resolve) => { resolveSecond = resolve; });
      return [{ id: 'series-first', type: 'series', title: 'First Story', seriesId: 'series-first' }];
    },
  });
  h.render();
  await h.settle();
  assert.equal(findNodes(h.tree, (node) => node.props?.['data-result-id'] === 'series-first').length, 1);

  h.navigate('q=second');
  await h.settle();
  assert.equal(findNodes(h.tree, (node) => node.props?.['data-testid'] === 'catalog-skeleton').length, 1);
  assert.equal(getText(h.tree).includes('Không tìm thấy câu chuyện phù hợp'), false);

  resolveSecond([{ id: 'series-second', type: 'series', title: 'Second Story', seriesId: 'series-second' }]);
  await h.settle();
  assert.equal(findNodes(h.tree, (node) => node.props?.['data-result-id'] === 'series-second').length, 1);
});

test('6. Catalog list: renders SQL series only, paginates client-side, and explains legacy film filters', async () => {
  const series = Array.from({ length: 13 }, (_, index) => ({
    id: 'series-' + index,
    type: 'series',
    title: 'Story ' + index,
    seriesId: 'series-' + index,
    synopsis: 'Catalog synopsis ' + index,
    releaseYearStart: 2000 + index,
  }));
  let listCalls = 0;
  const h = createSearchHarness('page=1&size=2&sort=rating', {
    seriesList: async () => { listCalls++; return series; },
    search: async () => [],
  });
  h.render();
  await h.settle();

  const cards = findNodes(h.tree, (node) => node.props?.['data-testid'] === 'search-result-card');
  assert.equal(listCalls, 1);
  assert.equal(cards.length, 2, 'URL page and size slice the bounded catalog on the client');
  assert.equal(cards[0].props['data-result-id'], 'series-2');
  assert.equal(cards[0].props.href, '/series/series-2');
  assert.ok(getText(cards[0]).includes('Catalog synopsis 2'));
  assert.ok(getText(cards[0]).includes('2002'));
  assert.ok(getText(h.tree).includes('Bộ lọc phim cũ không áp dụng'));
  assert.equal(getText(h.tree).includes('Điểm cao nhất'), false, 'Unsupported movie sort controls are not shown');

  const clearOldFilters = findNodes(h.tree, (node) => node.type === 'button' && getText(node).includes('Xóa bộ lọc cũ'))[0];
  clearOldFilters.props.onClick();
  assert.ok(h.pushes.some((url) => !url.includes('sort=')), 'The old filter notice can clear stale movie URL fields');
});

test('7. Catalog search: API failure stays an error and retry can recover', async () => {
  let shouldFail = true;
  const h = createSearchHarness('q=jadoo', {
    seriesList: async () => [],
    search: async () => {
      if (shouldFail) throw new Error('HTTP 503 catalog unavailable');
      return [{ id: 'jadoo', type: 'series', title: 'Jadoo', seriesId: 'jadoo' }];
    },
  });
  h.render();
  await h.settle();

  assert.ok(getText(h.tree).includes('HTTP 503 catalog unavailable'));
  assert.equal(getText(h.tree).includes('Không tìm thấy câu chuyện phù hợp'), false);
  const retry = findNodes(h.tree, (node) => node.type === 'button' && getText(node).includes('Thử lại'))[0];
  assert.ok(retry);
  shouldFail = false;
  retry.props.onClick();
  await h.settle();
  assert.equal(findNodes(h.tree, (node) => node.props?.['data-result-id'] === 'jadoo').length, 1);
});

test('8. Catalog search: slow response cannot overwrite the latest query', async () => {
  let resolveSlow;
  let resolveFast;
  const h = createSearchHarness('q=slow', {
    seriesList: async () => [],
    search: async (query) => {
      if (query === 'slow') return new Promise((resolve) => { resolveSlow = resolve; });
      return new Promise((resolve) => { resolveFast = resolve; });
    },
  });
  h.render();
  await h.settle();

  h.navigate('q=fast');
  await h.settle();
  resolveFast([{ id: 'series-fast', type: 'series', title: 'Fast Story', seriesId: 'series-fast' }]);
  await h.settle();
  resolveSlow([{ id: 'series-slow', type: 'series', title: 'Slow Story', seriesId: 'series-slow' }]);
  await h.settle();

  assert.equal(findNodes(h.tree, (node) => node.props?.['data-result-id'] === 'series-fast').length, 1);
  assert.equal(findNodes(h.tree, (node) => node.props?.['data-result-id'] === 'series-slow').length, 0);
});

test('9. Catalog search: unmount cancels the active request', async () => {
  const h = createSearchHarness('q=cancel-test', {
    seriesList: async () => [],
    search: async () => new Promise(() => {}),
  });
  h.render();
  await h.settle();
  h.unmount();

  assert.ok(h.abortedSignals.some((signal) => signal.aborted), 'Unmount must abort in-flight catalog search');
});
test('10. S4 (P2): MovieCard renders fallback placeholder when poster is missing or empty', () => {
  const movieWithoutPoster = sampleMovie({
    id: 'anim-no-poster',
    title: 'The Tale of Princess Kaguya',
    poster: '',
  });

  const cardNode = renderActualMovieCard(movieWithoutPoster);

  // Must NOT render next/image
  const imageNodes = findNodes(cardNode, (n) => n.type === 'next/image');
  assert.equal(imageNodes.length, 0, 'Must NOT render Image when poster is empty');

  // Must render placeholder with Film icon and movie title
  const filmIcons = findNodes(cardNode, (n) => n.type === 'Film');
  assert.ok(filmIcons.length > 0, 'Placeholder must render Film icon');

  const cardText = getText(cardNode);
  assert.ok(cardText.includes('The Tale of Princess Kaguya'), 'Placeholder must display movie title');

  // Detail link points to canonical movie path
  const links = findNodes(cardNode, (n) => n.type === 'next/link');
  assert.ok(links.some((l) => l.props.href === '/movies/anim-no-poster'), 'Must link to /movies/anim-no-poster');
});

test('11. S4 (P2): MovieCard renders Next Image with correct src and alt when poster is valid', () => {
  const movieWithPoster = sampleMovie({
    id: 'anim-totoro',
    title: 'My Neighbor Totoro',
    poster: 'https://cdn.example.com/totoro.jpg',
  });

  const cardNode = renderActualMovieCard(movieWithPoster);

  const imageNodes = findNodes(cardNode, (n) => n.type === 'next/image');
  assert.equal(imageNodes.length, 1, 'Must render exactly one next/image component');
  assert.equal(imageNodes[0].props.src, 'https://cdn.example.com/totoro.jpg');
  assert.equal(imageNodes[0].props.alt, 'My Neighbor Totoro');

  // Film placeholder must NOT be rendered when poster is valid
  const filmIcons = findNodes(cardNode, (n) => n.type === 'Film');
  assert.equal(filmIcons.length, 0, 'Must not render Film fallback when valid poster exists');
});

test('12. S4 (P2): MovieCard renders unconfirmed watchlist status badge and executes retry action', () => {
  const movie = sampleMovie({
    id: 'anim-mononoke',
    title: 'Princess Mononoke',
    poster: 'https://cdn.example.com/mononoke.jpg',
  });

  let toggleClicked = null;

  const watchlistContext = {
    isWatchlisted: () => false,
    isActionPending: () => false,
    isActionUnconfirmed: (id, action) => id === 'anim-mononoke' && action === 'watchlist',
    getActionIntent: (id, action) => (id === 'anim-mononoke' && action === 'watchlist' ? 'add' : null),
    toggleWatchlist: (id, title, poster) => {
      toggleClicked = { id, title, poster };
    },
  };

  const cardNode = renderActualMovieCard(movie, watchlistContext);

  // Unconfirmed status badge
  const unconfirmedBadge = findNodes(cardNode, (n) => n.props?.['data-testid'] === 'unconfirmed-badge')[0];
  assert.ok(unconfirmedBadge, 'Unconfirmed status badge must be present');
  assert.ok(getText(unconfirmedBadge).includes('Chưa xác nhận'));

  // Watchlist button aria-label & title reflects retry intent
  const watchlistBtn = findNodes(cardNode, (n) => n.type === 'button')[0];
  assert.ok(watchlistBtn, 'Watchlist toggle button must exist');
  assert.ok(
    watchlistBtn.props['aria-label'].includes('Chưa xác nhận lưu • Thử lưu lại Princess Mononoke vào danh sách xem')
  );
  assert.ok(
    watchlistBtn.props.title.includes('Chưa xác nhận lưu • Nhấn để thử lưu lại')
  );

  // Click button triggers toggleWatchlist with exact movie details
  watchlistBtn.props.onClick({ preventDefault: () => {}, stopPropagation: () => {} });
  assert.deepEqual(toggleClicked, {
    id: 'anim-mononoke',
    title: 'Princess Mononoke',
    poster: 'https://cdn.example.com/mononoke.jpg',
  });
});
