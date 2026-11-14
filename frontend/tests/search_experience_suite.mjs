import { labels } from './labels_fixture.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import ts from 'typescript';
import { fileURLToPath } from 'node:url';


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
      if (mod === '@/lib/labels') return labels;
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
          browseCatalog: mocks.browse || (async () => ({
            items: [],
            page: 0,
            size: 12,
            totalElements: 0,
            totalPages: 0,
            hasNext: false,
            hasPrevious: false,
          })),
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

test('Catalog search input has an accessible name', () => {
  const h = createSearchHarness();
  h.render();
  const input = findNodes(h.tree, (node) => node.props?.['data-testid'] === 'search-query-input')[0];
  assert.ok(input.props['aria-label']);
  h.unmount();
});

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
      if (mod === '@/lib/labels') return labels;
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


test('1. S1 (P2): Delayed router navigation does NOT overwrite user typing draft', async () => {
  const h = createSearchHarness('q=A');
  h.render();
  await h.settle();

  const inputNode = findNodes(h.tree, (n) => n.type === 'input')[0];
  assert.ok(inputNode, 'Search input must exist');
  assert.equal(inputNode.props.value, 'A', 'Initial input must match URL query A');

  inputNode.props.onChange({ target: { value: 'B' } });
  await h.settle();

  const firedDebounce = h.runTimer((t) => t.ms === 350);
  assert.ok(firedDebounce, 'Debounce timer of 350ms must fire');
  assert.deepEqual(h.pushes, ['/search?q=B'], 'Router push must record /search?q=B');

  findNodes(h.tree, (n) => n.type === 'input')[0].props.onChange({ target: { value: 'C' } });
  await h.settle();

  const draftBefore = findNodes(h.tree, (n) => n.type === 'input')[0].props.value;
  assert.equal(draftBefore, 'C');

  h.navigate('q=B');
  await h.settle();

  const draftAfter = findNodes(h.tree, (n) => n.type === 'input')[0].props.value;
  assert.equal(draftAfter, 'C', 'User typing of "C" must be preserved over delayed router "B"');

  h.runTimer((t) => t.ms === 350);
  assert.ok(h.pushes.includes('/search?q=C'), 'Subsequent debounce pushes draft C');
});

test('2. S1 (P2): External navigation (browser back/forward or deep link) syncs draft input', async () => {
  const h = createSearchHarness('q=original');
  h.render();
  await h.settle();

  assert.equal(findNodes(h.tree, (n) => n.type === 'input')[0].props.value, 'original');

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
    browse: async () => new Promise((resolve) => { resolveSearch = resolve; }),
  });
  h.render();
  await h.settle();

  assert.equal(findNodes(h.tree, (node) => node.props?.['data-testid'] === 'catalog-skeleton').length, 1);
  assert.equal(getText(h.tree).includes('Không tìm thấy phim phù hợp'), false);

  resolveSearch({ items: [], page: 0, size: 12, totalElements: 0, totalPages: 0, hasNext: false, hasPrevious: false });
  await h.settle();
  assert.ok(getText(h.tree).includes('Không tìm thấy phim phù hợp'));
  assert.ok(getText(h.tree).includes('Không có phim hoạt hình khớp'));
});

test('5. Catalog search: query navigation never labels old results as the new query', async () => {
  let resolveSecond;
  const page = (movie) => ({ items: [movie], page: 0, size: 12, totalElements: 1, totalPages: 1, hasNext: false, hasPrevious: false });
  const h = createSearchHarness('q=first', {
    browse: async (options) => {
      if (options.query === 'second') return new Promise((resolve) => { resolveSecond = resolve; });
      return page({ id: 'film-first', title: 'First Film', year: 2001, description: 'First' });
    },
  });
  h.render();
  await h.settle();
  assert.equal(findNodes(h.tree, (node) => node.props?.['data-result-id'] === 'film-first').length, 1);

  h.navigate('q=second');
  await h.settle();
  assert.equal(findNodes(h.tree, (node) => node.props?.['data-testid'] === 'catalog-skeleton').length, 1);
  assert.equal(getText(h.tree).includes('Không tìm thấy phim phù hợp'), false);

  resolveSecond(page({ id: 'film-second', title: 'Second Film', year: 2002, description: 'Second' }));
  await h.settle();
  assert.equal(findNodes(h.tree, (node) => node.props?.['data-result-id'] === 'film-second').length, 1);
});

test('6. Catalog list: renders standalone films and asks the server for the URL page', async () => {
  const films = Array.from({ length: 13 }, (_, index) => ({
    id: 'film-' + index,
    title: 'Film ' + index,
    description: 'Catalog synopsis ' + index,
    year: 2000 + index,
  }));
  let listCalls = 0;
  const h = createSearchHarness('page=1&size=2', {
    browse: async (options) => {
      listCalls++;
      const start = options.page * options.size;
      const items = films.slice(start, start + options.size);
      return {
        items,
        page: options.page,
        size: options.size,
        totalElements: films.length,
        totalPages: Math.ceil(films.length / options.size),
        hasNext: start + options.size < films.length,
        hasPrevious: options.page > 0,
      };
    },
  });
  h.render();
  await h.settle();

  const cards = findNodes(h.tree, (node) => node.props?.['data-testid'] === 'search-result-card');
  assert.equal(listCalls, 1);
  assert.equal(cards.length, 2, 'URL page and size select one server page');
  assert.equal(cards[0].props['data-result-id'], 'film-2');
  assert.equal(cards[0].props.href, '/movies/film-2');
  assert.ok(getText(cards[0]).includes('Catalog synopsis 2'));
  assert.ok(getText(cards[0]).includes('2002'));
  assert.equal(getText(h.tree).includes('Điểm cao nhất'), false, 'Sort controls stay off this screen');
});

test('7. Catalog search: API failure stays an error and retry can recover', async () => {
  let shouldFail = true;
  const h = createSearchHarness('q=jadoo', {
    browse: async () => {
      if (shouldFail) throw new Error('HTTP 503 catalog unavailable');
      return {
        items: [{ id: 'jadoo', title: 'Jadoo', year: 2010, description: 'A film' }],
        page: 0, size: 12, totalElements: 1, totalPages: 1, hasNext: false, hasPrevious: false,
      };
    },
  });
  h.render();
  await h.settle();

  assert.ok(getText(h.tree).includes('HTTP 503 catalog unavailable'));
  assert.equal(getText(h.tree).includes('Không tìm thấy phim phù hợp'), false);
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
  const page = (movie) => ({ items: [movie], page: 0, size: 12, totalElements: 1, totalPages: 1, hasNext: false, hasPrevious: false });
  const h = createSearchHarness('q=slow', {
    browse: async (options) => {
      if (options.query === 'slow') return new Promise((resolve) => { resolveSlow = resolve; });
      return new Promise((resolve) => { resolveFast = resolve; });
    },
  });
  h.render();
  await h.settle();

  h.navigate('q=fast');
  await h.settle();
  resolveFast(page({ id: 'film-fast', title: 'Fast Film', year: 2011, description: 'Fast' }));
  await h.settle();
  resolveSlow(page({ id: 'film-slow', title: 'Slow Film', year: 2010, description: 'Slow' }));
  await h.settle();

  assert.equal(findNodes(h.tree, (node) => node.props?.['data-result-id'] === 'film-fast').length, 1);
  assert.equal(findNodes(h.tree, (node) => node.props?.['data-result-id'] === 'film-slow').length, 0);
});

test('9. Catalog search: unmount cancels the active request', async () => {
  const h = createSearchHarness('q=cancel-test', {
    browse: async () => new Promise(() => {}),
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

  const imageNodes = findNodes(cardNode, (n) => n.type === 'next/image');
  assert.equal(imageNodes.length, 0, 'Must NOT render Image when poster is empty');

  const filmIcons = findNodes(cardNode, (n) => n.type === 'Film');
  assert.ok(filmIcons.length > 0, 'Placeholder must render Film icon');

  const cardText = getText(cardNode);
  assert.ok(cardText.includes('The Tale of Princess Kaguya'), 'Placeholder must display movie title');

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

  const unconfirmedBadge = findNodes(cardNode, (n) => n.props?.['data-testid'] === 'unconfirmed-badge')[0];
  assert.ok(unconfirmedBadge, 'Unconfirmed status badge must be present');
  assert.ok(getText(unconfirmedBadge).includes('Chưa xác nhận'));

  const watchlistBtn = findNodes(cardNode, (n) => n.type === 'button')[0];
  assert.ok(watchlistBtn, 'Watchlist toggle button must exist');
  assert.ok(
    watchlistBtn.props['aria-label'].includes('Chưa xác nhận lưu • Thử lưu lại Princess Mononoke vào danh sách xem')
  );
  assert.ok(
    watchlistBtn.props.title.includes('Chưa xác nhận lưu • Nhấn để thử lưu lại')
  );

  watchlistBtn.props.onClick({ preventDefault: () => {}, stopPropagation: () => {} });
  assert.deepEqual(toggleClicked, {
    id: 'anim-mononoke',
    title: 'Princess Mononoke',
    poster: 'https://cdn.example.com/mononoke.jpg',
  });
});

test('Genre and size navigation requests the matching catalog and hides stale results', async () => {
  const calls = [];
  let resolveNext;
  const page = (id) => ({ items: [{ id, title: id }], page: 0, size: 12, totalElements: 1, totalPages: 1, hasNext: false, hasPrevious: false });
  const h = createSearchHarness('q=film&genre=%20Adventure%20&size=12', {
    browse: (options) => {
      calls.push(options);
      if (calls.length === 1) return Promise.resolve(page('adventure-film'));
      return new Promise((resolve) => { resolveNext = resolve; });
    },
  });
  h.render();
  await h.settle();
  assert.equal(calls[0].genre, 'Adventure');
  assert.equal(calls[0].query, 'film');
  assert.equal(findNodes(h.tree, (node) => node.props?.['data-result-id'] === 'adventure-film').length, 1);
  assert.ok(getText(h.tree).includes('Phiêu lưu'));

  h.navigate('q=film&genre=Comedy&size=12');
  assert.equal(findNodes(h.tree, (node) => node.props?.['data-result-id'] === 'adventure-film').length, 0);
  await h.settle();
  assert.equal(calls[1].genre, 'Comedy');
  resolveNext(page('comedy-film'));
  await h.settle();
  assert.equal(findNodes(h.tree, (node) => node.props?.['data-result-id'] === 'comedy-film').length, 1);

  h.navigate('q=film&genre=Comedy&size=2');
  assert.equal(findNodes(h.tree, (node) => node.props?.['data-result-id'] === 'comedy-film').length, 0);
  await h.settle();
  assert.equal(calls[2].size, 2);
  h.unmount();
});


test('Vietnamese catalog labels preserve unknown values', () => {
  assert.equal(labels.genreLabel('Adventure'), 'Phiêu lưu');
  assert.equal(labels.genreLabel('Sci-Fi'), 'Khoa học viễn tưởng');
  assert.equal(labels.genreLabel('Unlisted'), 'Unlisted');
  assert.equal(labels.formatRuntime('1h 45m'), '1 giờ 45 phút');
  assert.equal(labels.formatRuntime('25m'), '25 phút');
  assert.equal(labels.formatRuntime('7m 25s'), '7 phút 25 giây');
  assert.equal(labels.formatRuntime('Series'), 'Series');
  assert.equal(labels.formatRuntime(), '');
  assert.equal(
    labels.movieSynopsis('Two estranged sisters cross an unmapped ocean in search of their father.'),
    'Hai chị em xa cách cùng vượt qua vùng biển chưa có trên bản đồ để tìm cha.',
  );
  assert.equal(labels.movieSynopsis('Mô tả do người dùng nhập.'), 'Mô tả do người dùng nhập.');
});

test('Empty genre results show Vietnamese while requesting the original genre', async () => {
  const calls = [];
  const h = createSearchHarness('genre=Adventure', {
    browse: (options) => {
      calls.push(options);
      return Promise.resolve(emptyPage());
    },
  });
  h.render();
  await h.settle();
  assert.equal(calls[0].genre, 'Adventure');
  assert.ok(getText(h.tree).includes('Không có phim hoạt hình thuộc thể loại Phiêu lưu.'));
  h.unmount();
});
