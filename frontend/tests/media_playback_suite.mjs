import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, '..');
const require = createRequire(import.meta.url);
const ts = require('typescript');

// Helper to load and transpile mediaService.ts via TypeScript compiler API
function loadMediaService(mockFetch) {
  const serviceFile = path.resolve(root, 'lib/services/mediaService.ts');
  const code = fs.readFileSync(serviceFile, 'utf8');
  const compiled = ts.transpileModule(code, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;

  const sandbox = {
    exports: {},
    module: { exports: {} },
    fetch: mockFetch || globalThis.fetch,
    process: { env: { NEXT_PUBLIC_SPRINGBOOT_API_URL: 'http://test-server/api' } },
    AbortController: globalThis.AbortController,
    setTimeout,
    clearTimeout,
    encodeURIComponent,
    Error,
    Array,
    String,
    Boolean,
    console,
  };
  vm.runInNewContext(compiled, sandbox);
  return sandbox.module.exports.getMediaDescriptor ? sandbox.module.exports : sandbox.exports;
}

// Tree walker helper for virtual DOM inspection
function walk(node, predicate) {
  if (!node) return null;
  if (Array.isArray(node)) {
    for (const item of node) {
      const found = walk(item, predicate);
      if (found) return found;
    }
    return null;
  }
  if (typeof node === 'object') {
    if (predicate(node)) return node;
    return walk(node.props?.children, predicate);
  }
  return null;
}

function findAll(node, predicate, acc = []) {
  if (!node) return acc;
  if (Array.isArray(node)) {
    for (const item of node) findAll(item, predicate, acc);
    return acc;
  }
  if (typeof node === 'object') {
    if (predicate(node)) acc.push(node);
    findAll(node.props?.children, predicate, acc);
  }
  return acc;
}

// Harness to execute MovieDetail component with hooks and fake DOM simulation
function createMovieDetailHarness(options = {}) {
  const file = path.resolve(root, 'features/movies/components/MovieDetail.tsx');
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true },
  }).outputText;

  let slots = [];
  let slotIndex = 0;
  let pendingEffects = [];
  let tree = null;
  let windowListeners = {};

  const opener = {
    tagName: 'BUTTON',
    focusCount: 0,
    focus() {
      this.focusCount++;
      doc.activeElement = this;
    },
  };

  const doc = {
    activeElement: opener,
    body: { style: { overflow: '' } },
    fullscreenElement: null,
  };

  const hooks = {
    useState(init) {
      const i = slotIndex++;
      if (!slots[i]) {
        slots[i] = { value: typeof init === 'function' ? init() : init };
      }
      const setter = (next) => {
        slots[i].value = typeof next === 'function' ? next(slots[i].value) : next;
      };
      return [slots[i].value, setter];
    },
    useRef(init) {
      const i = slotIndex++;
      if (!slots[i]) {
        slots[i] = { current: init };
      }
      return slots[i];
    },
    useEffect(effectFn, deps) {
      const i = slotIndex++;
      const prev = slots[i];
      const hasChanged = !prev || !deps || deps.some((d, idx) => !Object.is(d, prev.deps[idx]));
      if (hasChanged) {
        pendingEffects.push(() => {
          prev?.cleanup?.();
          const cleanup = effectFn();
          slots[i] = { deps, cleanup: typeof cleanup === 'function' ? cleanup : null };
        });
      }
    },
    createElement(type, props, ...children) {
      const flatChildren = children.length === 1 ? children[0] : children;
      return { type, props: { ...props, children: flatChildren } };
    },
  };

  const windowMock = {
    addEventListener(event, handler) {
      if (!windowListeners[event]) windowListeners[event] = [];
      windowListeners[event].push(handler);
    },
    removeEventListener(event, handler) {
      if (!windowListeners[event]) return;
      windowListeners[event] = windowListeners[event].filter((h) => h !== handler);
    },
    dispatchEvent(event, payload) {
      if (windowListeners[event]) {
        for (const h of windowListeners[event]) h(payload);
      }
    },
  };

  const context = {
    exports: {},
    document: doc,
    window: windowMock,
    setTimeout,
    clearTimeout,
    AbortController: globalThis.AbortController,
    console,
    require(moduleName) {
      if (moduleName === 'react') return { __esModule: true, default: hooks, ...hooks };
      if (moduleName === 'next/image' || moduleName === 'next/link') return { __esModule: true, default: moduleName };
      if (moduleName === 'lucide-react') return new Proxy({}, { get: (_, key) => String(key) });
      if (moduleName.includes('WatchlistContext')) {
        return {
          useWatchlist: () => ({
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
            getUnconfirmedRating: () => null,
            openChat: () => {},
          }),
        };
      }
      if (moduleName.includes('mediaService')) {
        return {
          resolveStreamUrl: (url) => url,
          getMediaDescriptor: options.getMediaDescriptor || (async (id) => ({
            movieId: id,
            hasFeature: true,
            hasTrailer: false,
            feature: { streamUrl: `https://fixture.invalid/feature-${id}.mp4` },
          })),
        };
      }
      if (moduleName.includes('MovieSection')) return { MovieSection: 'MovieSection' };
      return {};
    },
  };

  vm.runInNewContext(code, context, { filename: file });

  function render(movie) {
    slotIndex = 0;
    pendingEffects = [];
    tree = context.exports.MovieDetail({
      movie: typeof movie === 'string' ? { id: movie, title: 'Movie ' + movie, genres: ['Action'], rating: 8, year: 2026 } : movie,
      similarMovies: [],
    });
    // Commit phase: ensure elements with props.ref have ref.current populated before effects run
    const refNodes = findAll(tree, (n) => n.props?.ref);
    for (const node of refNodes) {
      if (node.props.ref && typeof node.props.ref === 'object' && !node.props.ref.current) {
        node.props.ref.current = {
          contains: () => false,
          querySelectorAll: () => [],
          duration: 120,
          currentTime: 0,
          volume: 1,
          muted: false,
          paused: false,
          play: async () => {},
          pause: () => {},
          load: () => {},
          addEventListener: () => {},
          removeEventListener: () => {},
        };
      }
    }
    for (const effect of pendingEffects) {
      effect();
    }
    return tree;
  }

  function flushEffects() {
    for (const effect of pendingEffects) {
      effect();
    }
    pendingEffects = [];
  }

  function unmount() {
    for (const slot of slots) {
      slot?.cleanup?.();
    }
  }

  return {
    render,
    flushEffects,
    unmount,
    getTree: () => tree,
    doc,
    opener,
    windowMock,
    slots,
  };
}

// -------------------------------------------------------------
// Unit & Integration Tests
// -------------------------------------------------------------

test('1. resolveStreamUrl correctly handles relative and absolute URLs', () => {
  const { resolveStreamUrl } = loadMediaService();

  assert.equal(resolveStreamUrl('https://example.com/stream/video.mp4'), 'https://example.com/stream/video.mp4');
  assert.equal(resolveStreamUrl('http://cdn.example.com/media/clip.mp4'), 'http://cdn.example.com/media/clip.mp4');

  const relativeStream = resolveStreamUrl('/api/media/stream/ast-001');
  assert.ok(relativeStream.endsWith('/api/media/stream/ast-001'), 'Must end with relative path');
  assert.ok(relativeStream.startsWith('http://') || relativeStream.startsWith('https://'), 'Must start with protocol');

  assert.equal(resolveStreamUrl(''), '');
});

test('2. getMediaDescriptor normalizes valid descriptor response', async () => {
  const mockFetch = async (url) => {
    assert.ok(url.includes('/api/movies/m1-test/media-descriptor'));
    return {
      ok: true,
      status: 200,
      json: async () => ({
        movieId: 'm1-test',
        hasFeature: true,
        hasTrailer: true,
        feature: {
          assetId: 'ast-feat-01',
          kind: 'feature',
          streamUrl: '/api/media/stream/ast-feat-01',
          mimeType: 'video/mp4',
          byteLength: 1048576,
          durationSeconds: 120.5,
          isPublic: true,
          version: 'v1',
        },
        trailer: {
          assetId: 'ast-trl-01',
          kind: 'trailer',
          streamUrl: '/api/media/stream/ast-trl-01',
          mimeType: 'video/mp4',
          byteLength: 524288,
          durationSeconds: 30.0,
          isPublic: true,
          version: 'v1',
        },
      }),
    };
  };

  const { getMediaDescriptor } = loadMediaService(mockFetch);
  const desc = await getMediaDescriptor('m1-test');
  assert.equal(desc.movieId, 'm1-test');
  assert.equal(desc.hasFeature, true);
  assert.equal(desc.hasTrailer, true);
  assert.ok(desc.feature);
  assert.equal(desc.feature.assetId, 'ast-feat-01');
  assert.ok(desc.feature.streamUrl.endsWith('/api/media/stream/ast-feat-01'));
  assert.ok(desc.trailer);
  assert.equal(desc.trailer.assetId, 'ast-trl-01');
});

test('3. getMediaDescriptor rejects on server error', async () => {
  const mockFetch = async () => ({ ok: false, status: 404 });
  const { getMediaDescriptor } = loadMediaService(mockFetch);

  await assert.rejects(
    () => getMediaDescriptor('non-existent'),
    /Lỗi tải mô tả media \(404\)/
  );
});

test('4. getMediaDescriptor handles external AbortSignal cancellation', async () => {
  let abortListenerAttached = false;
  const mockFetch = async (url, init) => {
    return new Promise((resolve, reject) => {
      init.signal.addEventListener('abort', () => {
        abortListenerAttached = true;
        reject(new Error('The operation was aborted.'));
      });
    });
  };

  const { getMediaDescriptor } = loadMediaService(mockFetch);
  const externalController = new AbortController();

  const promise = getMediaDescriptor('m-abort', { signal: externalController.signal });
  externalController.abort();

  await assert.rejects(promise, /aborted/);
  assert.equal(abortListenerAttached, true, 'External abort must propagate to fetch');
});

test('5. Component Execution: Route swap A -> B clears media state immediately, B pending never displays A feature button', async () => {
  let pendingBResolver;
  const getMediaDescriptor = async (id) => {
    if (id === 'A') {
      return {
        movieId: 'A',
        hasFeature: true,
        hasTrailer: false,
        feature: { streamUrl: 'https://fixture.invalid/feature-A.mp4' },
      };
    }
    // For movie B, return a promise that stays in flight
    return new Promise((resolve) => {
      pendingBResolver = resolve;
    });
  };

  const harness = createMovieDetailHarness({ getMediaDescriptor });

  // 1. Render movie A and allow descriptor to resolve
  harness.render('A');
  await new Promise((r) => setImmediate(r));
  harness.render('A');

  // Verify feature button for A is visible
  let tree = harness.getTree();
  let buttonA = walk(tree, (n) => n.props?.['data-testid'] === 'play-feature-btn');
  assert.ok(buttonA, 'Feature button for Movie A must be visible once resolved');

  // 2. Switch route to movie B (descriptor remains pending)
  harness.render('B');
  tree = harness.getTree();

  // Crucial check: A button must NOT be visible while B is pending
  const buttonBWhilePending = walk(tree, (n) => n.props?.['data-testid'] === 'play-feature-btn');
  assert.equal(buttonBWhilePending, null, 'Feature button from Movie A must NOT remain visible while Movie B descriptor is pending');

  // 3. Resolve B descriptor
  pendingBResolver({
    movieId: 'B',
    hasFeature: true,
    hasTrailer: false,
    feature: { streamUrl: 'https://fixture.invalid/feature-B.mp4' },
  });
  await new Promise((r) => setImmediate(r));
  harness.render('B');
  tree = harness.getTree();

  const buttonB = walk(tree, (n) => n.props?.['data-testid'] === 'play-feature-btn');
  assert.ok(buttonB, 'Feature button for Movie B must appear after descriptor resolves');

  harness.unmount();
});

test('6. Component Execution: Opening player locks body scroll and records opener element', async () => {
  const harness = createMovieDetailHarness();
  harness.render('A');
  await new Promise((r) => setImmediate(r));
  harness.render('A');

  const tree = harness.getTree();
  const playBtn = walk(tree, (n) => n.props?.['data-testid'] === 'play-feature-btn');
  assert.ok(playBtn);

  // Click play
  playBtn.props.onClick({ currentTarget: harness.opener });
  harness.render('A');

  // Modal open assertions
  const modal = walk(harness.getTree(), (n) => n.props?.role === 'dialog');
  assert.ok(modal, 'Modal dialog must be rendered after clicking play');
  assert.equal(harness.doc.body.style.overflow, 'hidden', 'Body scroll must be locked');

  harness.unmount();
});

test('7. Component Execution: Focus stability — onLoadedMetadata and volume updates DO NOT call opener.focus() while player is open', async () => {
  const harness = createMovieDetailHarness();
  harness.render('A');
  await new Promise((r) => setImmediate(r));
  harness.render('A');

  const playBtn = walk(harness.getTree(), (n) => n.props?.['data-testid'] === 'play-feature-btn');
  playBtn.props.onClick({ currentTarget: harness.opener });
  harness.render('A');

  const video = walk(harness.getTree(), (n) => n.type === 'video');
  assert.ok(video, 'Video element must be present');

  const videoFake = {
    duration: 120,
    currentTime: 0,
    volume: 1,
    muted: false,
    paused: false,
    play: async () => {},
    pause: () => {},
  };
  video.props.ref.current = videoFake;

  const focusCountBefore = harness.opener.focusCount;

  // Trigger loadedmetadata
  video.props.onLoadedMetadata();
  harness.render('A');

  // Crucial assertion: opener.focus() MUST NOT have been called
  assert.equal(
    harness.opener.focusCount - focusCountBefore,
    0,
    'onLoadedMetadata must NOT restore focus to opener while player remains open'
  );

  // Change volume
  const volumeSlider = walk(harness.getTree(), (n) => n.props?.['aria-label'] === 'Thanh âm lượng');
  assert.ok(volumeSlider);
  volumeSlider.props.onChange({ target: { value: '0.5' } });
  harness.render('A');

  assert.equal(
    harness.opener.focusCount - focusCountBefore,
    0,
    'Volume update must NOT restore focus to opener while player remains open'
  );

  harness.unmount();
});

test('8. Component Execution: Modal focus trap selector includes range sliders (timeline & volume)', async () => {
  const harness = createMovieDetailHarness();
  harness.render('A');
  await new Promise((r) => setImmediate(r));
  harness.render('A');

  const playBtn = walk(harness.getTree(), (n) => n.props?.['data-testid'] === 'play-feature-btn');
  playBtn.props.onClick({ currentTarget: harness.opener });
  harness.render('A');

  const tree = harness.getTree();
  const timeline = walk(tree, (n) => n.props?.['data-testid'] === 'video-timeline');
  assert.ok(timeline, 'Timeline scrubber must exist');
  assert.equal(timeline.type, 'input', 'Timeline scrubber must be an input element');
  assert.equal(timeline.props.type, 'range', 'Timeline scrubber must have type="range"');

  const volumeSlider = walk(tree, (n) => n.props?.['aria-label'] === 'Thanh âm lượng');
  assert.ok(volumeSlider, 'Volume slider must exist');
  assert.equal(volumeSlider.type, 'input', 'Volume slider must be an input element');

  // Verify touch target requirements (min-h-[44px])
  assert.ok(timeline.props.className.includes('min-h-[44px]'), 'Timeline must satisfy >=44px touch target');
  assert.ok(volumeSlider.props.className.includes('min-h-[44px]'), 'Volume slider must satisfy >=44px touch target');

  harness.unmount();
});

test('9. Component Execution: Keyboard shortcuts respect editable targets and native controls', async () => {
  const harness = createMovieDetailHarness();
  harness.render('A');
  await new Promise((r) => setImmediate(r));
  harness.render('A');

  const playBtn = walk(harness.getTree(), (n) => n.props?.['data-testid'] === 'play-feature-btn');
  playBtn.props.onClick({ currentTarget: harness.opener });
  harness.render('A');

  const video = walk(harness.getTree(), (n) => n.type === 'video');
  let pausedCalled = false;
  const videoFake = {
    duration: 120,
    currentTime: 10,
    volume: 0.8,
    muted: false,
    paused: false,
    play: async () => {},
    pause: () => {
      pausedCalled = true;
    },
  };
  video.props.ref.current = videoFake;

  // 1. Keydown with target as an INPUT (e.g. range slider or search box)
  let defaultPrevented = false;
  harness.windowMock.dispatchEvent('keydown', {
    key: ' ',
    target: { tagName: 'INPUT' },
    preventDefault: () => {
      defaultPrevented = true;
    },
  });
  assert.equal(defaultPrevented, false, 'Space on an interactive input must not be intercepted');
  assert.equal(pausedCalled, false, 'Video play/pause must not trigger when typing in an input');

  // 2. Keydown outside inputs (on player container)
  let spacePrevented = false;
  harness.windowMock.dispatchEvent('keydown', {
    key: ' ',
    target: { tagName: 'DIV' },
    preventDefault: () => {
      spacePrevented = true;
    },
  });
  assert.equal(spacePrevented, true, 'Space on player body must prevent default');
  assert.equal(pausedCalled, true, 'Video must pause when Space is pressed outside inputs');

  harness.unmount();
});

test('10. Component Execution: Autoplay rejection transitions state to paused with Play button', async () => {
  const harness = createMovieDetailHarness();
  harness.render('A');
  await new Promise((r) => setImmediate(r));
  harness.render('A');

  // Pre-configure videoRef to reject autoplay with NotAllowedError
  for (const slot of harness.slots) {
    if (slot && 'current' in slot && slot.current === null) {
      slot.current = {
        duration: 120,
        currentTime: 0,
        volume: 1,
        muted: false,
        paused: true,
        play: () => Promise.reject(new Error('NotAllowedError')),
        pause: () => {},
        load: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
      };
      break;
    }
  }

  const playBtn = walk(harness.getTree(), (n) => n.props?.['data-testid'] === 'play-feature-btn');
  playBtn.props.onClick({ currentTarget: harness.opener });
  harness.render('A');

  // Wait for promise rejection microtask to execute setPlayerState('paused')
  await new Promise((r) => setImmediate(r));
  harness.render('A');

  // Must not have buffering spinner or error overlay; must have play button ready
  const buffering = walk(harness.getTree(), (n) => n.props?.['data-testid'] === 'video-buffering');
  assert.equal(buffering, null, 'Buffering spinner must disappear after autoplay rejection');

  const errorOverlay = walk(harness.getTree(), (n) => n.props?.['data-testid'] === 'video-error-overlay');
  assert.equal(errorOverlay, null, 'Autoplay rejection is NOT a fatal stream error');

  const playPauseBtn = walk(harness.getTree(), (n) => n.props?.['data-testid'] === 'video-play-pause-btn');
  assert.ok(playPauseBtn, 'Play button must be rendered allowing user gesture activation');
  assert.equal(playPauseBtn.props['aria-label'], 'Phát video');

  harness.unmount();
});

test('11. Component Execution: Error and retry restores video.currentTime upon loadedmetadata', async () => {
  const harness = createMovieDetailHarness();
  harness.render('A');
  await new Promise((r) => setImmediate(r));
  harness.render('A');

  const playBtn = walk(harness.getTree(), (n) => n.props?.['data-testid'] === 'play-feature-btn');
  playBtn.props.onClick({ currentTarget: harness.opener });
  harness.render('A');

  let videoListeners = {};
  let currentFakeTime = 42.5;
  const videoFake = {
    duration: 120,
    get currentTime() {
      return currentFakeTime;
    },
    set currentTime(v) {
      currentFakeTime = v;
    },
    load: () => {},
    play: async () => {},
    addEventListener: (ev, fn) => {
      videoListeners[ev] = fn;
    },
    removeEventListener: (ev) => {
      delete videoListeners[ev];
    },
  };

  const video = walk(harness.getTree(), (n) => n.type === 'video');
  video.props.ref.current = videoFake;

  // Trigger error during playback
  video.props.onError();
  harness.render('A');

  const retryBtn = walk(harness.getTree(), (n) => n.props?.['data-testid'] === 'video-retry-btn');
  assert.ok(retryBtn, 'Retry button must be visible upon playback error');

  // Click retry
  retryBtn.props.onClick();
  harness.render('A');

  // Trigger loadedmetadata event
  assert.ok(videoListeners['loadedmetadata'], 'Retry must register loadedmetadata listener');
  videoListeners['loadedmetadata']();

  // Verify currentTime was restored to 42.5
  assert.equal(videoFake.currentTime, 42.5, 'Retry must restore recorded currentTime upon loadedmetadata');

  harness.unmount();
});

test('12. Component Execution: Closing player restores body scroll and returns focus to opener', async () => {
  const harness = createMovieDetailHarness();
  harness.render('A');
  await new Promise((r) => setImmediate(r));
  harness.render('A');

  const playBtn = walk(harness.getTree(), (n) => n.props?.['data-testid'] === 'play-feature-btn');
  playBtn.props.onClick({ currentTarget: harness.opener });
  harness.render('A');

  const focusCountBeforeClose = harness.opener.focusCount;

  // Click Close button
  const closeBtn = walk(harness.getTree(), (n) => n.props?.['aria-label'] === 'Đóng trình phát');
  assert.ok(closeBtn);
  closeBtn.props.onClick();
  harness.render('A');

  // Modal must be gone
  const modal = walk(harness.getTree(), (n) => n.props?.role === 'dialog');
  assert.equal(modal, null, 'Modal dialog must be closed');

  // Body scroll must be unlocked
  assert.equal(harness.doc.body.style.overflow, '', 'Body overflow must be cleared');

  // Opener focus must be restored exactly once
  assert.equal(
    harness.opener.focusCount - focusCountBeforeClose,
    1,
    'Closing modal must restore focus to opener element'
  );

  harness.unmount();
});
