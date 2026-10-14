import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import ts from 'typescript';
import { fileURLToPath } from 'node:url';

/**
 * M2 Catalog UI Cutover Journey Test Suite (Round 6)
 *
 * Tests actual production components across Home, Movie Detail, and Profile:
 * 1. Home Page: animationOnly constraint, loading skeleton, error retry, empty catalog state.
 * 2. Movie Detail Page: canonical ID resolution (200, real 404, 5xx/timeout with retry, deterministic similar rail).
 * 3. Movie Detail Media Fallbacks: safe backdrop, poster placeholder, video playback capability strictly on valid data.
 * 4. Profile Overview: shared catalog client hydration for all canonical IDs, bounded metadata cache, orphan vs network error.
 * 5. Cross-surface journey: consistent canonical ID between Home, Detail, and Profile library.
 */

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, '..');

const homeFilePath = path.join(root, 'app/page.tsx');
const detailPageFilePath = path.join(root, 'app/movies/[id]/page.tsx');
const movieDetailCompFilePath = path.join(root, 'features/movies/components/MovieDetail.tsx');
const profileOverviewFilePath = path.join(root, 'features/profile/components/ProfileOverview.tsx');
const editorialHeroCompFilePath = path.join(root, 'features/home/components/EditorialHero.tsx');
const watchlistProviderFilePath = path.join(root, 'lib/context/WatchlistContext.tsx');

const transpileOptions = {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    jsx: ts.JsxEmit.React,
    esModuleInterop: true,
    target: ts.ScriptTarget.ES2022,
  },
};

const homeTranspiled = ts.transpileModule(fs.readFileSync(homeFilePath, 'utf8'), transpileOptions).outputText;
const detailPageTranspiled = ts.transpileModule(fs.readFileSync(detailPageFilePath, 'utf8'), transpileOptions).outputText;
const movieDetailCompTranspiled = ts.transpileModule(fs.readFileSync(movieDetailCompFilePath, 'utf8'), transpileOptions).outputText;
const profileOverviewTranspiled = ts.transpileModule(fs.readFileSync(profileOverviewFilePath, 'utf8'), transpileOptions).outputText;
const editorialHeroTranspiled = ts.transpileModule(fs.readFileSync(editorialHeroCompFilePath, 'utf8'), transpileOptions).outputText;
const watchlistProviderTranspiled = ts.transpileModule(fs.readFileSync(watchlistProviderFilePath, 'utf8'), transpileOptions).outputText;

const turn = () => new Promise((resolve) => setImmediate(resolve));

function sampleMovie(overrides = {}) {
  return {
    id: overrides.id || 'anim-totoro',
    title: overrides.title || 'My Neighbor Totoro',
    overview: overrides.overview || 'Two girls move to the country and discover friendly spirits',
    description: overrides.description || overrides.overview || 'Two girls move to the country and discover friendly spirits',
    poster: overrides.poster !== undefined ? overrides.poster : 'https://image.example.com/totoro.jpg',
    backdrop: overrides.backdrop !== undefined ? overrides.backdrop : 'https://image.example.com/totoro-backdrop.jpg',
    year: overrides.year || 1988,
    rating: overrides.rating || 8.2,
    genres: overrides.genres || ['Animation', 'Family', 'Fantasy'],
    runtime: overrides.runtime || '86 min',
    videoUrl: overrides.videoUrl !== undefined ? overrides.videoUrl : 'https://video.example.com/trailer.mp4',
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

// Harness to execute actual HomePage
function createHomeHarness(browseCatalogMock) {
  let slots = [];
  let hookIndex = 0;
  let effects = [];
  let dirty = false;
  let tree = null;
  const sameDeps = (a, b) => a && b && a.length === b.length && a.every((x, j) => Object.is(x, b[j]));

  const hooks = {
    useState(initial) {
      const idx = hookIndex++;
      if (!slots[idx]) slots[idx] = { v: typeof initial === 'function' ? initial() : initial };
      return [
        slots[idx].v,
        (updater) => {
          slots[idx].v = typeof updater === 'function' ? updater(slots[idx].v) : updater;
          dirty = true;
        },
      ];
    },
    useRef(initial) {
      const idx = hookIndex++;
      if (!slots[idx]) slots[idx] = { current: initial };
      return slots[idx];
    },
    useMemo(factory, deps) {
      const idx = hookIndex++;
      if (!slots[idx] || !sameDeps(slots[idx].deps, deps)) slots[idx] = { v: factory(), deps };
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
          if (typeof slots[idx].cleanup === 'function') slots[idx].cleanup();
          slots[idx].cleanup = fn();
        });
      }
    },
    createElement(type, props, ...children) {
      const flat = children.length === 1 ? children[0] : children.length > 1 ? children : undefined;
      return { type, props: { ...props, ...(flat !== undefined ? { children: flat } : {}) } };
    },
  };

  const moduleObj = { exports: {} };
  const context = {
    module: moduleObj,
    exports: moduleObj.exports,
    console,
    AbortController,
    require: (mod) => {
      if (mod === 'react') return { __esModule: true, default: hooks, ...hooks };
      if (mod === 'next/link') return { default: 'next/link', __esModule: true };
      if (mod === 'next/image') return { default: 'next/image', __esModule: true };
      if (mod === 'lucide-react') return new Proxy({}, { get: (_, k) => k });
      if (mod.includes('Navbar') || mod.includes('Footer')) {
        return { Navbar: () => ({ type: 'Navbar' }), Footer: () => ({ type: 'Footer' }) };
      }
      if (mod.includes('EditorialHero')) {
        return {
          EditorialHero: 'EditorialHero',
        };
      }
      if (mod.includes('MovieSection')) {
        return {
          MovieSection: 'MovieSection',
        };
      }
      if (mod.includes('catalogService')) {
        return { browseCatalog: browseCatalogMock };
      }
      if (mod.includes('WatchlistContext')) {
        return { useWatchlist: () => ({ openChat: () => {}, watchlist: ['totoro'] }) };
      }
      return {};
    },
  };

  vm.runInNewContext(homeTranspiled, context, { filename: homeFilePath });

  function render() {
    hookIndex = 0;
    dirty = false;
    tree = moduleObj.exports.default();
    const pending = effects;
    effects = [];
    for (const ef of pending) ef();
    return tree;
  }

  async function settle(maxPasses = 8) {
    for (let pass = 0; pass < maxPasses; pass++) {
      await turn();
      if (dirty || pass === 0) render();
    }
    return tree;
  }

  return { render, settle, get tree() { return tree; } };
}

// Harness to execute actual MovieDetailPage
function createDetailHarness(requestedId, getCatalogMovieByIdMock, browseCatalogMock) {
  let slots = [];
  let hookIndex = 0;
  let effects = [];
  let dirty = false;
  let tree = null;
  const sameDeps = (a, b) => a && b && a.length === b.length && a.every((x, j) => Object.is(x, b[j]));

  const hooks = {
    useState(initial) {
      const idx = hookIndex++;
      if (!slots[idx]) slots[idx] = { v: typeof initial === 'function' ? initial() : initial };
      return [
        slots[idx].v,
        (updater) => {
          slots[idx].v = typeof updater === 'function' ? updater(slots[idx].v) : updater;
          dirty = true;
        },
      ];
    },
    useRef(initial) {
      const idx = hookIndex++;
      if (!slots[idx]) slots[idx] = { current: initial };
      return slots[idx];
    },
    useMemo(factory, deps) {
      const idx = hookIndex++;
      if (!slots[idx] || !sameDeps(slots[idx].deps, deps)) slots[idx] = { v: factory(), deps };
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
          if (typeof slots[idx].cleanup === 'function') slots[idx].cleanup();
          slots[idx].cleanup = fn();
        });
      }
    },
    createElement(type, props, ...children) {
      const flat = children.length === 1 ? children[0] : children.length > 1 ? children : undefined;
      return { type, props: { ...props, ...(flat !== undefined ? { children: flat } : {}) } };
    },
  };

  const moduleObj = { exports: {} };
  const context = {
    module: moduleObj,
    exports: moduleObj.exports,
    console,
    AbortController,
    require: (mod) => {
      if (mod === 'react') return { __esModule: true, default: hooks, ...hooks };
      if (mod === 'next/navigation') {
        return {
          useParams: () => ({ id: requestedId }),
          useRouter: () => ({ push: () => {} }),
          usePathname: () => `/movies/${requestedId}`,
        };
      }
      if (mod === 'next/link') return { default: 'next/link', __esModule: true };
      if (mod === 'next/image') return { default: 'next/image', __esModule: true };
      if (mod === 'lucide-react') return new Proxy({}, { get: (_, k) => k });
      if (mod.includes('Navbar') || mod.includes('Footer')) {
        return { Navbar: () => ({ type: 'Navbar' }), Footer: () => ({ type: 'Footer' }) };
      }
      if (mod.includes('MovieDetail')) {
        return {
          MovieDetail: 'MovieDetail',
        };
      }
      if (mod.includes('catalogService')) {
        return {
          getCatalogMovieById: getCatalogMovieByIdMock,
          browseCatalog: browseCatalogMock || (async () => ({ items: [] })),
        };
      }
      return {};
    },
  };

  vm.runInNewContext(detailPageTranspiled, context, { filename: detailPageFilePath });

  function render() {
    hookIndex = 0;
    dirty = false;
    tree = moduleObj.exports.default();
    const pending = effects;
    effects = [];
    for (const ef of pending) ef();
    return tree;
  }

  async function settle(maxPasses = 8) {
    for (let pass = 0; pass < maxPasses; pass++) {
      await turn();
      if (dirty || pass === 0) render();
    }
    return tree;
  }

  return { render, settle, get tree() { return tree; } };
}

// Harness to execute actual MovieDetail component
function renderMovieDetail(movie, similarMovies = [], watchlistContext = {}) {
  let slots = [];
  let hookIndex = 0;
  const hooks = {
    useState(initial) {
      const idx = hookIndex++;
      if (!slots[idx]) slots[idx] = { v: typeof initial === 'function' ? initial() : initial };
      return [slots[idx].v, (val) => { slots[idx].v = val; }];
    },
    useRef(initial) {
      const idx = hookIndex++;
      if (!slots[idx]) slots[idx] = { current: initial };
      return slots[idx];
    },
    createElement(type, props, ...children) {
      const flat = children.length === 1 ? children[0] : children.length > 1 ? children : undefined;
      return { type, props: { ...props, ...(flat !== undefined ? { children: flat } : {}) } };
    },
  };

  const defaultWatchlist = {
    isWatchlisted: () => false,
    toggleWatchlist: () => {},
    isFavorite: () => false,
    toggleFavorite: () => {},
    getRating: () => null,
    rateMovie: () => {},
    removeRating: () => {},
    isActionPending: () => false,
    isActionUnconfirmed: () => false,
    getActionIntent: () => null,
    getUnconfirmedRating: () => undefined,
    openChat: () => {},
    ...watchlistContext,
  };

  const moduleObj = { exports: {} };
  const context = {
    module: moduleObj,
    exports: moduleObj.exports,
    console,
    require: (mod) => {
      if (mod === 'react') return { __esModule: true, default: hooks, ...hooks };
      if (mod === 'next/image') return { default: 'next/image', __esModule: true };
      if (mod === 'next/link') return { default: 'next/link', __esModule: true };
      if (mod === 'lucide-react') return new Proxy({}, { get: (_, k) => k });
      if (mod.includes('WatchlistContext')) return { useWatchlist: () => defaultWatchlist };
      if (mod.includes('MovieSection')) return { MovieSection: 'MovieSection' };
      return {};
    },
  };

  vm.runInNewContext(movieDetailCompTranspiled, context, { filename: movieDetailCompFilePath });
  hookIndex = 0;
  return moduleObj.exports.MovieDetail({ movie, similarMovies });
}

// Harness to execute actual EditorialHero component
function renderEditorialHero(movie, watchlistContext = {}) {
  let slots = [];
  let hookIndex = 0;
  const hooks = {
    useState(initial) {
      const idx = hookIndex++;
      if (!slots[idx]) slots[idx] = { v: typeof initial === 'function' ? initial() : initial };
      return [slots[idx].v, (val) => { slots[idx].v = val; }];
    },
    useRef(initial) {
      const idx = hookIndex++;
      if (!slots[idx]) slots[idx] = { current: initial };
      return slots[idx];
    },
    createElement(type, props, ...children) {
      const flat = children.length === 1 ? children[0] : children.length > 1 ? children : undefined;
      return { type, props: { ...props, ...(flat !== undefined ? { children: flat } : {}) } };
    },
  };

  const defaultWatchlist = {
    isWatchlisted: () => false,
    toggleWatchlist: () => {},
    openChat: () => {},
    isActionPending: () => false,
    isActionUnconfirmed: () => false,
    getActionIntent: () => null,
    getUnconfirmedRating: () => undefined,
    ...watchlistContext,
  };

  const moduleObj = { exports: {} };
  const context = {
    module: moduleObj,
    exports: moduleObj.exports,
    console,
    require: (mod) => {
      if (mod === 'react') return { __esModule: true, default: hooks, ...hooks };
      if (mod === 'next/image') return { default: 'next/image', __esModule: true };
      if (mod === 'next/link') return { default: 'next/link', __esModule: true };
      if (mod === 'lucide-react') return new Proxy({}, { get: (_, k) => k });
      if (mod.includes('WatchlistContext')) return { useWatchlist: () => defaultWatchlist };
      return {};
    },
  };

  vm.runInNewContext(editorialHeroTranspiled, context, { filename: editorialHeroCompFilePath });
  hookIndex = 0;
  return moduleObj.exports.EditorialHero({ movie });
}

// Harness to execute actual ProfileOverview component
function createProfileHarness(initialLibrary, getCatalogMovieByIdMock, customClock = null) {
  let slots = [];
  let hookIndex = 0;
  let effects = [];
  let dirty = false;
  let tree = null;
  const sameDeps = (a, b) => a && b && a.length === b.length && a.every((x, j) => Object.is(x, b[j]));

  const hooks = {
    useState(initial) {
      const idx = hookIndex++;
      if (!slots[idx]) slots[idx] = { v: typeof initial === 'function' ? initial() : initial };
      return [
        slots[idx].v,
        (updater) => {
          slots[idx].v = typeof updater === 'function' ? updater(slots[idx].v) : updater;
          dirty = true;
        },
      ];
    },
    useRef(initial) {
      const idx = hookIndex++;
      if (!slots[idx]) slots[idx] = { current: initial };
      return slots[idx];
    },
    useMemo(factory, deps) {
      const idx = hookIndex++;
      if (!slots[idx] || !sameDeps(slots[idx].deps, deps)) slots[idx] = { v: factory(), deps };
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
          if (typeof slots[idx].cleanup === 'function') slots[idx].cleanup();
          slots[idx].cleanup = fn();
        });
      }
    },
    createElement(type, props, ...children) {
      const flat = children.length === 1 ? children[0] : children.length > 1 ? children : undefined;
      return { type, props: { ...props, ...(flat !== undefined ? { children: flat } : {}) } };
    },
  };

  const currentLibrary = {
    watchlist: initialLibrary.watchlist || [],
    favorites: initialLibrary.favorites || [],
    ratings: initialLibrary.ratings || {},
    openChat: () => {},
    isLibraryLoading: false,
    libraryError: null,
    refetchLibrary: () => {},
    isGuestMode: false,
    toggleWatchlist: () => {},
    toggleFavorite: () => {},
    rateMovie: () => {},
    removeRating: () => {},
    isActionPending: () => false,
    isActionUnconfirmed: () => false,
    getActionIntent: () => null,
    getUnconfirmedRating: () => undefined,
    showToast: () => {},
    ...initialLibrary.watchlistContext,
  };

  const defaultAuth = {
    user: { id: 'user-1', email: 'test@example.com' },
    status: 'authenticated',
    openAuthModal: () => {},
    retryVerify: () => {},
  };

  const moduleObj = { exports: {} };
  const context = {
    module: moduleObj,
    exports: moduleObj.exports,
    console,
    AbortController,
    ...(customClock ? { Date: customClock } : {}),
    require: (mod) => {
      if (mod === 'react') return { __esModule: true, default: hooks, ...hooks };
      if (mod === 'next/link') return { default: 'next/link', __esModule: true };
      if (mod === 'next/image') return { default: 'next/image', __esModule: true };
      if (mod === 'lucide-react') return new Proxy({}, { get: (_, k) => k });
      if (mod.includes('MovieCard')) return { MovieCard: 'MovieCard' };
      if (mod.includes('WatchlistContext')) return { useWatchlist: () => currentLibrary };
      if (mod.includes('AuthContext')) return { useAuth: () => defaultAuth };
      if (mod.includes('catalogService')) {
        return {
          getCatalogMovieById: getCatalogMovieByIdMock,
        };
      }
      return {};
    },
  };

  vm.runInNewContext(profileOverviewTranspiled, context, { filename: profileOverviewFilePath });

  // Clear cache between test runs
  if (typeof moduleObj.exports.clearProfileMetadataCache === 'function') {
    moduleObj.exports.clearProfileMetadataCache();
  }

  function render() {
    hookIndex = 0;
    dirty = false;
    tree = moduleObj.exports.ProfileOverview();
    const pending = effects;
    effects = [];
    for (const ef of pending) ef();
    return tree;
  }

  async function settle(maxPasses = 8) {
    for (let pass = 0; pass < maxPasses; pass++) {
      await turn();
      if (dirty || pass === 0) render();
    }
    return tree;
  }

  function setLibrary(next) {
    Object.assign(currentLibrary, next);
    dirty = true;
    render();
  }

  return { render, settle, setLibrary, get tree() { return tree; } };
}

// ============================================================================
// TEST CASES: ROUND 6 CUTOVER & JOURNEY INTEGRATION
// ============================================================================

test('1. Home: Enforces animationOnly=true across all queries, handles empty and error states', async () => {
  const capturedQueries = [];

  // 1A. Success Case: Verify animationOnly=true constraint on all queries
  const mockBrowse = async (options) => {
    capturedQueries.push(options);
    return {
      items: [sampleMovie({ id: 'totoro', title: 'My Neighbor Totoro' })],
      page: 0,
      size: 10,
      totalElements: 1,
      totalPages: 1,
      hasNext: false,
      hasPrevious: false,
    };
  };

  const h = createHomeHarness(mockBrowse);
  h.render();
  await h.settle();

  assert.ok(capturedQueries.length >= 3, 'Must issue queries for top rated, recent, and genres');
  for (const q of capturedQueries) {
    assert.equal(q.animationOnly, true, 'Every Home rail query must enforce animationOnly=true');
  }

  const heroNodes = findNodes(h.tree, (n) => n.type === 'EditorialHero');
  assert.equal(heroNodes.length, 1, 'EditorialHero must be rendered from top backend record');
  assert.equal(heroNodes[0].props.movie.title, 'My Neighbor Totoro');

  // 1B. Empty State: Backend returns 0 animation items
  const emptyHarness = createHomeHarness(async () => ({
    items: [],
    page: 0,
    size: 10,
    totalElements: 0,
    totalPages: 0,
    hasNext: false,
    hasPrevious: false,
  }));
  emptyHarness.render();
  await emptyHarness.settle();

  const emptyText = getText(emptyHarness.tree);
  assert.ok(
    emptyText.includes('Hiện chưa có tác phẩm hoạt hình nào trong danh mục tiêu điểm của máy chủ'),
    'Must display informative empty state when animation catalog has no records'
  );

  // 1C. Error State: Backend network failure
  let retryTriggered = false;
  const errorHarness = createHomeHarness(async () => {
    if (retryTriggered) {
      return {
        items: [sampleMovie({ id: 'm-retry', title: 'Retry Animation' })],
        page: 0,
        size: 10,
        totalElements: 1,
        totalPages: 1,
        hasNext: false,
        hasPrevious: false,
      };
    }
    throw new Error('Máy chủ danh mục không phản hồi');
  });
  errorHarness.render();
  await errorHarness.settle();

  const errorText = getText(errorHarness.tree);
  assert.ok(
    errorText.includes('Không thể nạp danh mục hoạt hình'),
    'Must render error state when catalog service is down'
  );

  // Retry button
  const retryBtn = findNodes(errorHarness.tree, (n) => n.type === 'button' && getText(n).includes('Thử kết nối lại'))[0];
  assert.ok(retryBtn, 'Retry button must be provided');
  retryTriggered = true;
  retryBtn.props.onClick();
  await errorHarness.settle();

  assert.ok(findNodes(errorHarness.tree, (n) => n.type === 'EditorialHero').length === 1, 'Retry loads data');
});

test('2. Detail: Canonical ID lookup, real 404 vs server error, and deterministic similar rail (D1 decoupled)', async () => {
  // 2A. Valid 200 Movie: Main detail renders immediately while similar rail is pending!
  let similarDeferredResolve;
  const pendingSimilarPromise = new Promise((resolve) => {
    similarDeferredResolve = resolve;
  });

  let mainLookupResolved = false;
  let similarQuery = null;
  const mockBrowse = async (options) => {
    similarQuery = options;
    return pendingSimilarPromise;
  };

  const validHarness = createDetailHarness(
    'spirited-away',
    async (id) => {
      mainLookupResolved = true;
      return sampleMovie({ id: 'spirited-away', title: 'Spirited Away', genres: ['Animation', 'Fantasy'] });
    },
    mockBrowse
  );
  validHarness.render();
  await validHarness.settle();

  // D1 Verification: Main detail must be visible immediately even while similar rail is pending!
  assert.equal(mainLookupResolved, true, 'Main lookup resolved');
  const immediateDetailNodes = findNodes(validHarness.tree, (n) => n.type === 'MovieDetail');
  assert.equal(immediateDetailNodes.length, 1, 'D1: MovieDetail must be visible immediately while similar rail is pending');
  assert.equal(immediateDetailNodes[0].props.movie.id, 'spirited-away');

  // Now resolve similar rail
  similarDeferredResolve({
    items: [sampleMovie({ id: 'kaguya', title: 'The Tale of Princess Kaguya' })],
    page: 0,
    size: 6,
    totalElements: 1,
    totalPages: 1,
  });
  await validHarness.settle();

  const finalDetailNodes = findNodes(validHarness.tree, (n) => n.type === 'MovieDetail');
  assert.equal(finalDetailNodes.length, 1);
  assert.equal(finalDetailNodes[0].props.movie.id, 'spirited-away');
  assert.equal(similarQuery?.animationOnly, true, 'Similar rail query must enforce animationOnly');

  // 2B. Similar rail failure (timeout/500) must NOT turn main detail into error or 404
  const failureSimilarHarness = createDetailHarness(
    'spirited-away',
    async (id) => sampleMovie({ id: 'spirited-away', title: 'Spirited Away' }),
    async () => {
      throw new Error('Similar service timeout');
    }
  );
  failureSimilarHarness.render();
  await failureSimilarHarness.settle();

  const afterFailureNodes = findNodes(failureSimilarHarness.tree, (n) => n.type === 'MovieDetail');
  assert.equal(afterFailureNodes.length, 1, 'Main detail must remain visible when similar rail throws');
  assert.equal(getText(failureSimilarHarness.tree).includes('Không thể kết nối'), false, 'Similar failure must not trigger page error banner');

  // 2C. Real 404: Nonexistent movie returns null from getCatalogMovieById
  const notFoundHarness = createDetailHarness('nonexistent-id', async () => null);
  notFoundHarness.render();
  await notFoundHarness.settle();

  const notFoundText = getText(notFoundHarness.tree);
  assert.ok(notFoundText.includes('Không tìm thấy phim hoạt hình'), 'Must render dedicated 404 message');
  assert.ok(notFoundText.includes('nonexistent-id'), 'Must display requested canonical ID in 404 view');

  // 2D. 5xx/Timeout Server Error: Must NOT render fake 404, must render error banner with retry
  let detailRetryTriggered = false;
  const errorDetailHarness = createDetailHarness('failing-movie', async () => {
    if (detailRetryTriggered) {
      return sampleMovie({ id: 'failing-movie', title: 'Recovered Movie' });
    }
    throw new Error('Lỗi kết nối máy chủ 500');
  });
  errorDetailHarness.render();
  await errorDetailHarness.settle();

  const detailErrorText = getText(errorDetailHarness.tree);
  assert.ok(detailErrorText.includes('Không thể kết nối đến máy chủ'), 'Must show server connection error banner');
  assert.equal(detailErrorText.includes('Không tìm thấy phim hoạt hình'), false, 'Server error must NOT be masked as 404');

  const detailRetryBtn = findNodes(errorDetailHarness.tree, (n) => n.type === 'button' && getText(n).includes('Thử kết nối lại'))[0];
  assert.ok(detailRetryBtn, 'Must render retry button on server error');
  detailRetryTriggered = true;
  detailRetryBtn.props.onClick();
  await errorDetailHarness.settle();

  assert.equal(findNodes(errorDetailHarness.tree, (n) => n.type === 'MovieDetail').length, 1);
});

test('3. MovieDetail: Safe media fallbacks (missing backdrop, missing poster, and video playback capability)', () => {
  // 3A. Movie with missing backdrop and missing poster
  const minimalMovie = sampleMovie({
    id: 'minimal-movie',
    title: 'Minimal Anime',
    backdrop: '',
    poster: '',
    videoUrl: '', // No video
  });

  const nodeMinimal = renderMovieDetail(minimalMovie);

  // Must NOT render next/image with empty src
  const images = findNodes(nodeMinimal, (n) => n.type === 'next/image');
  assert.equal(images.length, 0, 'Must NOT render next/image with empty poster or backdrop');

  // Poster placeholder renders Film icon and movie title
  const filmIcons = findNodes(nodeMinimal, (n) => n.type === 'Film');
  assert.ok(filmIcons.length > 0, 'Must render Film placeholder icon when poster is empty');

  // Trailer button must NOT be rendered when videoUrl is empty
  const playButtons = findNodes(nodeMinimal, (n) => n.type === 'button' && getText(n).includes('Xem trailer'));
  assert.equal(playButtons.length, 0, 'Must NOT render play trailer button when videoUrl is empty');

  // 3B. Movie with valid backdrop, poster, and videoUrl
  const fullMovie = sampleMovie({
    id: 'full-movie',
    title: 'Full Anime',
    backdrop: 'https://img.com/backdrop.jpg',
    poster: 'https://img.com/poster.jpg',
    videoUrl: 'https://video.com/trailer.mp4',
  });

  const nodeFull = renderMovieDetail(fullMovie);
  const fullImages = findNodes(nodeFull, (n) => n.type === 'next/image');
  assert.equal(fullImages.length, 2, 'Must render backdrop and poster images when valid');
  assert.equal(fullImages[0].props.src, 'https://img.com/backdrop.jpg');
  assert.equal(fullImages[1].props.src, 'https://img.com/poster.jpg');

  // Trailer play button is present when videoUrl is valid
  const fullPlayButtons = findNodes(nodeFull, (n) => n.type === 'button' && getText(n).includes('Xem trailer'));
  assert.equal(fullPlayButtons.length, 1, 'Trailer play button rendered when videoUrl exists');
});

test('4. EditorialHero: Preserves M1 pending feedback and uncertain retry intent (D2)', () => {
  const heroMovie = sampleMovie({ id: 'hero-anim', title: 'Hero Animation' });
  let toggleCalledWith = null;

  // 4A. Uncertain ADD (commit POST succeeded on server but response lost; reconcile pending)
  const heroAddNode = renderEditorialHero(heroMovie, {
    isWatchlisted: () => true, // optimistic state in library
    isActionPending: () => false,
    isActionUnconfirmed: (id, act) => id === 'hero-anim' && (!act || act === 'watchlist'),
    getActionIntent: (id, act) => (id === 'hero-anim' && (!act || act === 'watchlist') ? 'add' : null),
    toggleWatchlist: (id, title, poster) => { toggleCalledWith = { id, title, poster }; },
  });

  const addButton = findNodes(heroAddNode, (n) => n.type === 'button' && n.props['aria-label'])[0];
  assert.ok(addButton, 'Must render watchlist button');
  assert.ok(addButton.props['aria-label'].includes('Thử lưu lại'), 'Aria label must preserve ADD intent');
  assert.equal(addButton.props['aria-label'].includes('Xóa khỏi Watchlist'), false, 'Must NOT show remove label on add retry');
  assert.ok(getText(addButton).includes('Thử lưu lại'), 'Button text must show Thử lưu lại');

  const addBadge = findNodes(heroAddNode, (n) => n.props?.['data-testid'] === 'hero-unconfirmed-badge')[0];
  assert.ok(addBadge, 'Must render unconfirmed badge');

  addButton.props.onClick();
  assert.equal(toggleCalledWith?.id, 'hero-anim', 'Clicking button calls toggleWatchlist');

  // 4B. Uncertain REMOVE (commit DELETE succeeded on server but response lost; reconcile pending)
  toggleCalledWith = null;
  const heroRemoveNode = renderEditorialHero(heroMovie, {
    isWatchlisted: () => false, // optimistic state removed
    isActionPending: () => false,
    isActionUnconfirmed: (id, act) => id === 'hero-anim' && (!act || act === 'watchlist'),
    getActionIntent: (id, act) => (id === 'hero-anim' && (!act || act === 'watchlist') ? 'remove' : null),
    toggleWatchlist: (id, title, poster) => { toggleCalledWith = { id, title, poster }; },
  });

  const removeButton = findNodes(heroRemoveNode, (n) => n.type === 'button' && n.props['aria-label'])[0];
  assert.ok(removeButton.props['aria-label'].includes('Thử xóa lại'), 'Aria label must preserve REMOVE intent');
  assert.equal(removeButton.props['aria-label'].includes('Thêm vào Watchlist'), false, 'Must NOT show add label on remove retry');
  assert.ok(getText(removeButton).includes('Thử xóa lại'), 'Button text must show Thử xóa lại');

  removeButton.props.onClick();
  assert.equal(toggleCalledWith?.id, 'hero-anim', 'Clicking button calls toggleWatchlist to retry remove');

  // 4C. In-flight Pending state
  const heroPendingNode = renderEditorialHero(heroMovie, {
    isWatchlisted: () => false,
    isActionPending: () => true,
    isActionUnconfirmed: () => false,
    getActionIntent: () => null,
  });

  const pendingButton = findNodes(heroPendingNode, (n) => n.type === 'button' && n.props['aria-label'])[0];
  assert.equal(pendingButton.props.disabled, true, 'Pending button must be disabled to prevent duplicate submissions');
  assert.ok(getText(pendingButton).includes('Đang cập nhật'), 'Pending button must display in-flight loading text');

  // 4D. Confirmed state returns to normal toggle
  const heroConfirmedNode = renderEditorialHero(heroMovie, {
    isWatchlisted: () => true,
    isActionPending: () => false,
    isActionUnconfirmed: () => false,
    getActionIntent: () => null,
  });
  const confirmedButton = findNodes(heroConfirmedNode, (n) => n.type === 'button' && n.props['aria-label'])[0];
  assert.equal(confirmedButton.props['aria-label'], 'Xóa khỏi Watchlist');
  assert.ok(getText(confirmedButton).includes('Đã lưu Watchlist'));
});

test('5. Profile: Enforces 5-min TTL, clears stale IDs on library update, and preserves items on network error (D3)', async () => {
  let fakeNow = Date.now();
  class TestDate extends Date {
    static now() { return fakeNow; }
  }

  let calls = 0;
  const mockApi = async (id) => {
    calls++;
    if (calls === 1) return sampleMovie({ id, title: 'Old Title V1' });
    if (calls === 2) return null; // 404 on re-fetch
    throw new Error('Network error 503');
  };

  const p = createProfileHarness({ watchlist: ['movie-x'], favorites: [], ratings: {} }, mockApi, TestDate);
  p.render();
  await p.settle();

  assert.equal(calls, 1, 'Initial fetch of movie-x');
  const card1 = findNodes(p.tree, (n) => n.type === 'MovieCard')[0];
  assert.equal(card1?.props.movie.title, 'Old Title V1');

  // Advance fake clock by 6 minutes (> 5 minutes TTL)
  fakeNow += 6 * 60 * 1000;

  // Remove item from library -> state cleanup
  p.setLibrary({ watchlist: [] });
  await p.settle();

  // Re-add item to library -> TTL expired, MUST re-fetch from API!
  p.setLibrary({ watchlist: ['movie-x'] });
  await p.settle();

  assert.equal(calls, 2, 'D3: Re-adding item after TTL expiry must trigger fresh API fetch');

  // Call 2 returned null (404 orphan)
  const cardAfter404 = findNodes(p.tree, (n) => n.type === 'MovieCard')[0];
  assert.equal(cardAfter404, undefined, 'Orphan 404 item must NOT render valid MovieCard');
  assert.ok(getText(p.tree).includes('Không có trong catalog (404)'), 'Must render orphan 404 message');

  // 5B. Test Network error on re-fetch: MUST NOT delete library item or treat as 404
  calls = 2; // Next call will throw 503
  fakeNow += 6 * 60 * 1000;
  p.setLibrary({ watchlist: [] });
  await p.settle();
  p.setLibrary({ watchlist: ['movie-x'] });
  await p.settle();

  assert.ok(getText(p.tree).includes('Không thể kết nối máy chủ để tải thông tin phim'), 'Network error marked as connection error');
  assert.ok(getText(p.tree).includes('Thử tải lại'), 'Network error provides retry button');
});

test('6. Cross-surface consistency: Canonical ID and attributes match across Home, Detail, and Profile', async () => {
  const canonicalMovie = sampleMovie({
    id: 'totoro',
    title: 'My Neighbor Totoro',
    year: 1988,
    rating: 8.2,
    genres: ['Animation', 'Family'],
  });

  // Home renders canonical ID 'totoro'
  const home = createHomeHarness(async () => ({
    items: [canonicalMovie],
    page: 0,
    size: 10,
    totalElements: 1,
    totalPages: 1,
    hasNext: false,
    hasPrevious: false,
  }));
  home.render();
  await home.settle();

  const hero = findNodes(home.tree, (n) => n.type === 'EditorialHero')[0];
  assert.ok(hero, 'Home must render EditorialHero');
  assert.equal(hero.props.movie.id, 'totoro');

  // Detail renders exact same canonical ID 'totoro'
  const detail = createDetailHarness('totoro', async () => canonicalMovie);
  detail.render();
  await detail.settle();

  const movieDetail = findNodes(detail.tree, (n) => n.type === 'MovieDetail')[0];
  assert.ok(movieDetail, 'Detail must render MovieDetail');
  assert.equal(movieDetail.props.movie.id, 'totoro');
  assert.equal(movieDetail.props.movie.title, 'My Neighbor Totoro');

  // Profile resolves exact same canonical ID 'totoro' from backend
  const profile = createProfileHarness(
    { watchlist: ['totoro'], favorites: [], ratings: {} },
    async (id) => (id === 'totoro' ? canonicalMovie : null)
  );
  profile.render();
  await profile.settle();

  const profileCard = findNodes(profile.tree, (n) => n.type === 'MovieCard')[0];
  assert.ok(profileCard, 'Profile must render MovieCard for totoro');
  assert.equal(profileCard.props.movie.id, 'totoro');
  assert.equal(profileCard.props.movie.title, 'My Neighbor Totoro');
});

test('7. End-to-End M2 User Journey: Home -> Save/Rate -> Provider Persist -> Reload Profile (Cross-surface integration)', async () => {
  // 1. Fake persisted backend store
  const persistedWatchlist = new Set();
  const persistedRatings = new Map();

  // 2. Persisted transport interceptor
  const persistedFetcher = async (url, options = {}) => {
    const method = options.method || 'GET';
    const parsedUrl = new URL(url, 'http://localhost');
    const pathname = parsedUrl.pathname;

    // GET /users/watchlist
    if (pathname.includes('/users/watchlist') && method === 'GET') {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          success: true,
          data: Array.from(persistedWatchlist).map((id) => ({ movieId: id })),
        }),
      };
    }
    // POST /users/watchlist
    if (pathname.includes('/users/watchlist') && method === 'POST') {
      const body = JSON.parse(options.body || '{}');
      persistedWatchlist.add(body.movieId);
      return {
        ok: true,
        status: 200,
        json: async () => ({ success: true, data: { movieId: body.movieId, movieTitle: body.movieTitle } }),
      };
    }
    // DELETE /users/watchlist/:id
    if (pathname.includes('/users/watchlist/') && method === 'DELETE') {
      const parts = pathname.split('/');
      const id = decodeURIComponent(parts[parts.length - 1]);
      persistedWatchlist.delete(id);
      return {
        ok: true,
        status: 200,
        json: async () => ({ success: true, data: true }),
      };
    }
    // GET /users/ratings
    if (pathname.includes('/users/ratings') && method === 'GET') {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          success: true,
          data: Array.from(persistedRatings.entries()).map(([movieId, rating]) => ({ movieId, rating })),
        }),
      };
    }
    // POST /users/ratings
    if (pathname.includes('/users/ratings') && method === 'POST') {
      const body = JSON.parse(options.body || '{}');
      persistedRatings.set(body.movieId, body.rating);
      return {
        ok: true,
        status: 200,
        json: async () => ({ success: true, data: { movieId: body.movieId, rating: body.rating } }),
      };
    }
    // GET /users/favorites
    if (pathname.includes('/users/favorites') && method === 'GET') {
      return {
        ok: true,
        status: 200,
        json: async () => ({ success: true, data: [] }),
      };
    }

    return {
      ok: false,
      status: 404,
      json: async () => ({ success: false, message: 'Not found' }),
    };
  };

  // Helper to mount production WatchlistProvider with persisted fetcher
  function mountProductionProvider(fetcher) {
    let slots = [];
    let hookIndex = 0;
    let effects = [];
    let changed = false;
    let value = null;
    const same = (a, b) => a && b && a.length === b.length && a.every((x, i) => Object.is(x, b[i]));

    const hooks = {
      createContext: () => ({ Provider: 'Provider' }),
      useContext: () => null,
      useState(initial) {
        const i = hookIndex++;
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
        const i = hookIndex++;
        if (!slots[i]) slots[i] = { current: initial };
        return slots[i];
      },
      useCallback(fn, deps) {
        const i = hookIndex++;
        if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { v: fn, deps };
        return slots[i].v;
      },
      useEffect(fn, deps) {
        const i = hookIndex++;
        if (!slots[i] || !same(slots[i].deps, deps)) {
          const prev = slots[i];
          slots[i] = { deps, cleanup: prev?.cleanup };
          effects.push(() => {
            prev?.cleanup?.();
            slots[i].cleanup = fn();
          });
        }
      },
      useMemo(fn, deps) {
        const i = hookIndex++;
        if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { v: fn(), deps };
        return slots[i].v;
      },
      createElement(type, props, ...children) {
        return { type, props: { ...props, children } };
      },
    };

    const moduleObj = { exports: {} };
    const storage = new Map();
    const context = {
      module: moduleObj,
      exports: moduleObj.exports,
      process: { env: {} },
      console,
      AbortController,
      DOMException,
      fetch: fetcher,
      window: {},
      localStorage: {
        getItem: (k) => storage.get(k) || null,
        setItem: (k, v) => storage.set(k, String(v)),
        removeItem: (k) => storage.delete(k),
      },
      setTimeout: (fn) => setTimeout(fn, 0),
      clearTimeout: (id) => clearTimeout(id),
      require: (name) => {
        if (name === 'react') return { __esModule: true, default: hooks, ...hooks };
        if (name.includes('AuthContext')) {
          return {
            useAuth: () => ({
              isAuthenticated: true,
              token: 'jwt-test-token',
              user: { id: 'user-journey-1', username: 'animator' },
              status: 'authenticated',
            }),
          };
        }
        if (name.includes('AuthModal')) return { AuthModal: () => null };
        if (name.includes('CineBot')) return { CineBot: () => null, CineBotFloatingTrigger: () => null };
        if (name === 'lucide-react') return new Proxy({}, { get: () => () => null });
        return {};
      },
    };

    vm.runInNewContext(watchlistProviderTranspiled, context, { filename: watchlistProviderFilePath });

    function render() {
      hookIndex = 0;
      changed = false;
      const res = moduleObj.exports.WatchlistProvider({ children: null });
      value = res.props.value;
      const pending = effects;
      effects = [];
      for (const ef of pending) ef();
      return value;
    }

    async function settle(maxPasses = 8) {
      for (let pass = 0; pass < maxPasses; pass++) {
        await turn();
        if (changed || pass === 0) render();
      }
      return value;
    }

    render();
    return { render, settle, get value() { return value; } };
  }

  // --- Step 1: User discovers Spirited Away on Home / Hero and saves to Watchlist ---
  const session1 = mountProductionProvider(persistedFetcher);
  await session1.settle();

  const canonicalMovie = sampleMovie({
    id: 'spirited-away',
    title: 'Spirited Away',
    year: 2001,
    rating: 8.6,
  });

  // Action 1: Add to Watchlist via production provider
  await session1.value.toggleWatchlist(canonicalMovie.id, canonicalMovie.title, canonicalMovie.poster);
  await session1.settle();

  assert.ok(persistedWatchlist.has('spirited-away'), 'Persisted transport must record spirited-away in watchlist');
  assert.equal(session1.value.isWatchlisted('spirited-away'), true, 'Provider visible state must confirm watchlist');

  // --- Step 2: User navigates to Detail page and rates movie 9/10 ---
  await session1.value.rateMovie('spirited-away', 9, 'Spirited Away');
  await session1.settle();

  assert.equal(persistedRatings.get('spirited-away'), 9, 'Persisted transport must record rating 9 for spirited-away');
  assert.equal(session1.value.getRating('spirited-away'), 9, 'Provider visible state must confirm rating 9');

  // --- Step 3: Simulate browser reload / provider remount for the user ---
  const session2 = mountProductionProvider(persistedFetcher);
  await session2.settle();

  assert.equal(session2.value.isWatchlisted('spirited-away'), true, 'Reloaded provider must restore watchlist from backend');
  assert.equal(session2.value.getRating('spirited-away'), 9, 'Reloaded provider must restore rating from backend');

  // --- Step 4: ProfileOverview mounts under reloaded provider and resolves catalog metadata ---
  const profileHarness = createProfileHarness(
    {
      watchlist: session2.value.watchlist,
      favorites: session2.value.favorites,
      ratings: session2.value.ratings,
      watchlistContext: session2.value,
    },
    async (id) => (id === 'spirited-away' ? canonicalMovie : null)
  );

  profileHarness.render();
  await profileHarness.settle();

  // Watchlist tab renders MovieCard for spirited-away with exact canonical metadata
  const profileCards = findNodes(profileHarness.tree, (n) => n.type === 'MovieCard');
  assert.equal(profileCards.length, 1, 'Profile must render MovieCard for persisted item');
  assert.equal(profileCards[0].props.movie.id, 'spirited-away');
  assert.equal(profileCards[0].props.movie.title, 'Spirited Away');
  assert.equal(profileCards[0].props.movie.year, 2001);
});

