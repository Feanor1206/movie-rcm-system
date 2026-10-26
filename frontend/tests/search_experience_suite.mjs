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
function createSearchHarness(initialUrl = '', browseMock) {
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
          browseCatalog: browseMock,
          searchAnimationCatalog: async () => [],
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
  const h = createSearchHarness('q=A', async () => emptyPage());
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
  const h = createSearchHarness('q=original', async () => emptyPage());
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
  const h = createSearchHarness('q=spirited', async () => emptyPage());
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

test('4. S2 (P2): Snapshot query key binding prevents false no-results on pending query transition', async () => {
  let pendingResolve;
  const mockBrowse = async (options) => {
    if (options.query === 'new') {
      return new Promise((resolve) => {
        pendingResolve = resolve;
      });
    }
    return emptyPage();
  };

  const h = createSearchHarness('q=old', mockBrowse);
  h.render();
  await h.settle();

  // Initial empty result for 'old'
  let treeText = getText(h.tree);
  assert.ok(treeText.includes('Không có phim hoạt hình nào khớp với từ khóa "old"'));

  // User navigates to 'new' (which remains pending)
  h.navigate('q=new');
  await h.settle();

  treeText = getText(h.tree);
  // S2 Requirement: MUST NOT show no-results message for 'new' while query is pending
  const showsNoResultsForNew = treeText.includes('Không có phim hoạt hình nào khớp với từ khóa "new"');
  assert.equal(
    showsNoResultsForNew,
    false,
    'Must NOT display no-results for "new" before its fetch response completes'
  );

  // Must indicate updating/loading state
  const showsLoadingOrUpdating =
    treeText.includes('Đang cập nhật') ||
    findNodes(h.tree, (n) => n.props?.['data-testid'] === 'catalog-skeleton').length > 0;
  assert.ok(showsLoadingOrUpdating, 'Must display loading/updating indicator while new query is pending');

  // Once new query completes with empty results, only then render no-results for 'new'
  pendingResolve(emptyPage({ query: 'new' }));
  await h.settle();

  treeText = getText(h.tree);
  assert.ok(
    treeText.includes('Không có phim hoạt hình nào khớp với từ khóa "new"'),
    'Now that fetch completed, empty message for "new" is legitimately displayed'
  );
});

test('5. S2 (P2): Query transition from results to pending preserves previous results labeled as updating', async () => {
  const ghibliPage = {
    items: [
      sampleMovie({ id: 'm-totoro', title: 'My Neighbor Totoro' }),
      sampleMovie({ id: 'm-mononoke', title: 'Princess Mononoke' }),
    ],
    page: 0,
    size: 12,
    totalElements: 2,
    totalPages: 1,
    hasNext: false,
    hasPrevious: false,
  };

  let resolveDisney;
  const mockBrowse = async (options) => {
    if (options.query === 'disney') {
      return new Promise((resolve) => {
        resolveDisney = resolve;
      });
    }
    return ghibliPage;
  };

  const h = createSearchHarness('q=ghibli', mockBrowse);
  h.render();
  await h.settle();

  // Ghibli results are visible
  let renderedCards = findNodes(h.tree, (n) => n.type === 'MovieCard');
  assert.equal(renderedCards.length, 2);
  assert.equal(renderedCards[0].props.movie.title, 'My Neighbor Totoro');

  // Navigate to 'disney' (pending)
  h.navigate('q=disney');
  await h.settle();

  // While pending, updating indicator is shown
  assert.ok(getText(h.tree).includes('Đang cập nhật'), 'Indicator "Đang cập nhật" must appear');

  // Resolve disney with 1 item
  resolveDisney({
    items: [sampleMovie({ id: 'm-aladdin', title: 'Aladdin' })],
    page: 0,
    size: 12,
    totalElements: 1,
    totalPages: 1,
    hasNext: false,
    hasPrevious: false,
  });
  await h.settle();

  renderedCards = findNodes(h.tree, (n) => n.type === 'MovieCard');
  assert.equal(renderedCards.length, 1);
  assert.equal(renderedCards[0].props.movie.title, 'Aladdin');
});

test('6. S3 (P2): URL yearMin, yearMax, and size parameters are parsed, validated, and forwarded to browseCatalog', async () => {
  let capturedOptions = null;
  const mockBrowse = async (options) => {
    capturedOptions = options;
    return emptyPage();
  };

  const url = 'q=spirited&genres=Adventure,Family&yearMin=1995&yearMax=2010&size=24&sort=year&direction=asc&page=1';
  const h = createSearchHarness(url, mockBrowse);
  h.render();
  await h.settle();

  assert.ok(capturedOptions, 'browseCatalog must be invoked');
  assert.equal(capturedOptions.query, 'spirited');
  assert.deepEqual([...capturedOptions.genres], ['Adventure', 'Family']);
  assert.equal(capturedOptions.yearMin, 1995, 'yearMin must be forwarded');
  assert.equal(capturedOptions.yearMax, 2010, 'yearMax must be forwarded');
  assert.equal(capturedOptions.size, 24, 'size must be forwarded');
  assert.equal(capturedOptions.sort, 'year');
  assert.equal(capturedOptions.direction, 'asc');
  assert.equal(capturedOptions.page, 1);
  assert.equal(capturedOptions.animationOnly, true, 'animationOnly must be enforced');

  // Verify active filters summary in the UI
  const treeText = getText(h.tree);
  assert.ok(treeText.includes('Từ năm: 1995'), 'Active filter summary must show yearMin');
  assert.ok(treeText.includes('Đến năm: 2010'), 'Active filter summary must show yearMax');
  assert.ok(treeText.includes('Cỡ trang: 24'), 'Active filter summary must show page size');
});

test('7. S3 (P2): Invalid year range (yearMin > yearMax) renders warning and resets cleanly', async () => {
  let browseCalled = false;
  const mockBrowse = async () => {
    browseCalled = true;
    return emptyPage();
  };

  // yearMin (2020) > yearMax (2000)
  const h = createSearchHarness('q=totoro&yearMin=2020&yearMax=2000', mockBrowse);
  h.render();
  await h.settle();

  const treeText = getText(h.tree);
  assert.ok(
    treeText.includes('Khoảng năm không hợp lệ'),
    'UI must render invalid year range warning'
  );
  assert.equal(browseCalled, false, 'Invalid year range must not send broken query to backend');

  // Clicking clear filters button in error banner resets invalid parameters
  const clearBtn = findNodes(
    h.tree,
    (n) => n.type === 'button' && getText(n).includes('Xóa bộ lọc')
  )[0];
  assert.ok(clearBtn, 'Clear filters button must exist');

  clearBtn.props.onClick();
  await h.settle();

  assert.ok(
    h.pushes.some((u) => !u.includes('yearMin') && !u.includes('yearMax')),
    'Clear filters button pushes URL without invalid year parameters'
  );
});

test('8. S4 (P2): Generation guard - Slow response A does NOT overwrite subsequent response B', async () => {
  let resolveA;
  let resolveB;

  const mockBrowse = async (options) => {
    if (options.query === 'slow') {
      return new Promise((resolve) => {
        resolveA = resolve;
      });
    }
    if (options.query === 'fast') {
      return new Promise((resolve) => {
        resolveB = resolve;
      });
    }
    return emptyPage();
  };

  const h = createSearchHarness('q=slow', mockBrowse);
  h.render();
  await h.settle();

  // User immediately switches to 'fast'
  h.navigate('q=fast');
  await h.settle();

  // Fast resolves first with B data
  resolveB({
    items: [sampleMovie({ id: 'm-fast', title: 'Fast Movie' })],
    page: 0,
    size: 12,
    totalElements: 1,
    totalPages: 1,
    hasNext: false,
    hasPrevious: false,
  });
  await h.settle();

  let cards = findNodes(h.tree, (n) => n.type === 'MovieCard');
  assert.equal(cards.length, 1);
  assert.equal(cards[0].props.movie.title, 'Fast Movie');

  // Slow A now resolves late with A data
  resolveA({
    items: [sampleMovie({ id: 'm-slow', title: 'Slow Movie' })],
    page: 0,
    size: 12,
    totalElements: 1,
    totalPages: 1,
    hasNext: false,
    hasPrevious: false,
  });
  await h.settle();

  // Generation guard MUST discard late A; UI remains Fast Movie
  cards = findNodes(h.tree, (n) => n.type === 'MovieCard');
  assert.equal(cards.length, 1);
  assert.equal(cards[0].props.movie.title, 'Fast Movie', 'Slow response A must NOT overwrite response B');
});

test('9. S4 (P2): Cancellation and cleanup on unmount', async () => {
  const h = createSearchHarness('q=cancel-test', async () => new Promise(() => {}));
  h.render();
  await h.settle();

  // Unmount component
  h.unmount();

  // All active AbortControllers must be signaled
  assert.ok(
    h.abortedSignals.some((s) => s.aborted === true),
    'Unmount must abort in-flight catalog fetch request'
  );
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
