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

function loadMediaService(mockFetch, overrides = {}) {
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
    DOMException: globalThis.DOMException,
    setTimeout: overrides.setTimeout || setTimeout,
    clearTimeout: overrides.clearTimeout || clearTimeout,
    encodeURIComponent,
    Error,
    Array,
    String,
    Boolean,
    console,
    ...overrides.sandboxExtras,
  };
  vm.runInNewContext(compiled, sandbox);
  return sandbox.module.exports.getMediaDescriptor ? sandbox.module.exports : sandbox.exports;
}

// -------------------------------------------------------------
// Media Descriptor Boundary Test Suite (M4-F03)
// -------------------------------------------------------------

test('1. Payload 200 hợp lệ trả về descriptor chuẩn', async () => {
  // Test 1a: Direct payload with relative and absolute stream URLs
  const mockFetchDirect = async (url) => {
    assert.ok(url.includes('/api/movies/m-valid-1/media-descriptor'));
    return {
      ok: true,
      status: 200,
      json: async () => ({
        movieId: 'm-valid-1',
        hasFeature: true,
        hasTrailer: true,
        feature: {
          assetId: 'ast-f1',
          kind: 'feature',
          streamUrl: '/media/stream/f1.mp4',
          mimeType: 'video/mp4',
          byteLength: 2048000,
          durationSeconds: 120,
          isPublic: true,
          version: 'v1',
        },
        trailer: {
          assetId: 'ast-t1',
          kind: 'trailer',
          streamUrl: 'https://cdn.example.com/trailer.mp4',
          mimeType: 'video/mp4',
          byteLength: 512000,
          durationSeconds: 30,
          isPublic: true,
          version: 'v1',
        },
      }),
    };
  };

  const serviceDirect = loadMediaService(mockFetchDirect);
  const desc1 = await serviceDirect.getMediaDescriptor('m-valid-1');

  assert.equal(desc1.movieId, 'm-valid-1');
  assert.equal(desc1.hasFeature, true);
  assert.equal(desc1.hasTrailer, true);
  assert.ok(desc1.feature);
  assert.equal(desc1.feature.kind, 'feature');
  assert.equal(desc1.feature.streamUrl, 'http://test-server/media/stream/f1.mp4');
  assert.ok(desc1.trailer);
  assert.equal(desc1.trailer.kind, 'trailer');
  assert.equal(desc1.trailer.streamUrl, 'https://cdn.example.com/trailer.mp4');

  // Test 1b: Wrapped ApiResponse payload ({ data: ... })
  const mockFetchWrapped = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      success: true,
      data: {
        movieId: 'm-valid-2',
        hasFeature: true,
        hasTrailer: false,
        feature: {
          assetId: 'ast-f2',
          kind: 'feature',
          streamUrl: 'http://cdn.example.com/movie.mp4',
          mimeType: 'video/mp4',
          byteLength: 1024,
          isPublic: true,
          version: 'v1',
        },
      },
    }),
  });

  const serviceWrapped = loadMediaService(mockFetchWrapped);
  const desc2 = await serviceWrapped.getMediaDescriptor('m-valid-2');
  assert.equal(desc2.movieId, 'm-valid-2');
  assert.equal(desc2.hasFeature, true);
  assert.equal(desc2.hasTrailer, false);
  assert.equal(desc2.feature.streamUrl, 'http://cdn.example.com/movie.mp4');
  assert.equal(desc2.trailer, null);
});

test('2. Payload valid empty (hasFeature: false, hasTrailer: false) trả về hợp lệ', async () => {
  // Test direct valid empty
  const mockFetchEmpty = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      movieId: 'm-empty',
      hasFeature: false,
      hasTrailer: false,
    }),
  });

  const serviceEmpty = loadMediaService(mockFetchEmpty);
  const descEmpty = await serviceEmpty.getMediaDescriptor('m-empty');

  assert.equal(descEmpty.movieId, 'm-empty');
  assert.equal(descEmpty.hasFeature, false);
  assert.equal(descEmpty.hasTrailer, false);
  assert.equal(descEmpty.feature, null);
  assert.equal(descEmpty.trailer, null);

  // Test wrapped valid empty with null feature/trailer
  const mockFetchWrappedEmpty = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      data: {
        movieId: 'm-empty-wrapped',
        hasFeature: false,
        hasTrailer: false,
        feature: null,
        trailer: null,
      },
    }),
  });

  const serviceWrappedEmpty = loadMediaService(mockFetchWrappedEmpty);
  const descWrapped = await serviceWrappedEmpty.getMediaDescriptor('m-empty-wrapped');

  assert.equal(descWrapped.movieId, 'm-empty-wrapped');
  assert.equal(descWrapped.hasFeature, false);
  assert.equal(descWrapped.hasTrailer, false);
  assert.equal(descWrapped.feature, null);
  assert.equal(descWrapped.trailer, null);
});

test('3. Timeout nội bộ ném TimeoutError (options.signal không abort)', async () => {
  let fetchAborted = false;
  const mockFetchHanging = async (url, init) => {
    return new Promise((resolve, reject) => {
      init.signal.addEventListener('abort', () => {
        fetchAborted = true;
        reject(new DOMException('The operation was aborted.', 'AbortError'));
      });
    });
  };

  const service = loadMediaService(mockFetchHanging);

  await assert.rejects(
    async () => {
      await service.getMediaDescriptor('m-timeout', { timeoutMs: 30 });
    },
    (err) => {
      assert.equal(err.name, 'TimeoutError', 'Must be named TimeoutError');
      assert.equal(err.message, 'Hết thời gian tải mô tả media', 'Message must match Vietnamese timeout notice');
      assert.equal(err.isTimeout, true, 'isTimeout property must be true');
      assert.ok(err instanceof DOMException, 'Must be an instance of DOMException');
      return true;
    }
  );

  assert.equal(fetchAborted, true, 'Internal timeout must abort controller signal');
});

test('4. External abort ném AbortError và dọn dẹp timer', async () => {
  let timerCleared = false;
  let listenerRemoved = false;
  let fetchAborted = false;

  const originalClearTimeout = clearTimeout;
  const trackingClearTimeout = (id) => {
    timerCleared = true;
    return originalClearTimeout(id);
  };

  const mockFetch = async (url, init) => {
    return new Promise((resolve, reject) => {
      init.signal.addEventListener('abort', () => {
        fetchAborted = true;
        reject(new DOMException('The operation was aborted.', 'AbortError'));
      });
    });
  };

  const service = loadMediaService(mockFetch, { clearTimeout: trackingClearTimeout });
  const externalController = new AbortController();

  const originalRemoveListener = externalController.signal.removeEventListener.bind(externalController.signal);
  externalController.signal.removeEventListener = (...args) => {
    listenerRemoved = true;
    return originalRemoveListener(...args);
  };

  // Case 4a: Abort while fetch is in-flight
  const promise = service.getMediaDescriptor('m-abort', {
    timeoutMs: 10000,
    signal: externalController.signal,
  });

  // Trigger external abort
  externalController.abort();

  await assert.rejects(
    promise,
    (err) => {
      assert.equal(err.name, 'AbortError', 'Must be named AbortError');
      assert.notEqual(err.isTimeout, true, 'isTimeout must not be set on external abort');
      assert.ok(err instanceof DOMException, 'Must be an instance of DOMException');
      return true;
    }
  );

  assert.equal(fetchAborted, true, 'Fetch must have received abort signal');
  assert.equal(timerCleared, true, 'clearTimeout must be called in finally block');
  assert.equal(listenerRemoved, true, 'removeEventListener must be called in finally block');

  // Case 4b: Signal already aborted before calling getMediaDescriptor
  const preAbortedController = new AbortController();
  preAbortedController.abort();

  await assert.rejects(
    async () => {
      await service.getMediaDescriptor('m-pre-abort', { signal: preAbortedController.signal });
    },
    (err) => {
      assert.equal(err.name, 'AbortError');
      assert.ok(err instanceof DOMException);
      return true;
    }
  );
});

test('5. Payload 200 rỗng `{}` ném lỗi validation', async () => {
  const mockFetchEmptyObject = async () => ({
    ok: true,
    status: 200,
    json: async () => ({}),
  });

  const service = loadMediaService(mockFetchEmptyObject);

  await assert.rejects(
    async () => {
      await service.getMediaDescriptor('m-empty-payload');
    },
    (err) => {
      assert.equal(err.message, 'Dữ liệu mô tả media không khớp mã phim');
      return true;
    }
  );

  // Also test wrapped empty object { data: {} }
  const mockFetchWrappedEmpty = async () => ({
    ok: true,
    status: 200,
    json: async () => ({ data: {} }),
  });

  const serviceWrapped = loadMediaService(mockFetchWrappedEmpty);

  await assert.rejects(
    async () => {
      await serviceWrapped.getMediaDescriptor('m-empty-payload-2');
    },
    (err) => {
      assert.equal(err.message, 'Dữ liệu mô tả media không khớp mã phim');
      return true;
    }
  );
});

test('6. Mismatched movieId ném lỗi validation', async () => {
  const mockFetchMismatch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      movieId: 'server-movie-xyz',
      hasFeature: false,
      hasTrailer: false,
    }),
  });

  const service = loadMediaService(mockFetchMismatch);

  await assert.rejects(
    async () => {
      await service.getMediaDescriptor('client-movie-abc');
    },
    (err) => {
      assert.equal(err.message, 'Dữ liệu mô tả media không khớp mã phim');
      return true;
    }
  );
});

test('7. hasFeature không phải boolean ném lỗi validation', async () => {
  // Case 7a: hasFeature is string 'true'
  const mockFetchStringBoolean = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      movieId: 'm-bool-test',
      hasFeature: 'true',
      hasTrailer: false,
    }),
  });

  const service1 = loadMediaService(mockFetchStringBoolean);
  await assert.rejects(
    async () => {
      await service1.getMediaDescriptor('m-bool-test');
    },
    (err) => {
      assert.equal(err.message, 'Thiếu hoặc sai trường hasFeature/hasTrailer');
      return true;
    }
  );

  // Case 7b: hasFeature is undefined
  const mockFetchMissingFeature = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      movieId: 'm-bool-test',
      hasTrailer: false,
    }),
  });

  const service2 = loadMediaService(mockFetchMissingFeature);
  await assert.rejects(
    async () => {
      await service2.getMediaDescriptor('m-bool-test');
    },
    (err) => {
      assert.equal(err.message, 'Thiếu hoặc sai trường hasFeature/hasTrailer');
      return true;
    }
  );

  // Case 7c: hasTrailer is number 1
  const mockFetchNumberTrailer = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      movieId: 'm-bool-test',
      hasFeature: false,
      hasTrailer: 1,
    }),
  });

  const service3 = loadMediaService(mockFetchNumberTrailer);
  await assert.rejects(
    async () => {
      await service3.getMediaDescriptor('m-bool-test');
    },
    (err) => {
      assert.equal(err.message, 'Thiếu hoặc sai trường hasFeature/hasTrailer');
      return true;
    }
  );
});

test('8. feature có streamUrl rỗng ném lỗi validation', async () => {
  // Case 8a: feature has empty streamUrl
  const mockFetchEmptyStreamUrl = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      movieId: 'm-feat-test',
      hasFeature: true,
      hasTrailer: false,
      feature: {
        assetId: 'ast-empty',
        kind: 'feature',
        streamUrl: '',
      },
    }),
  });

  const service1 = loadMediaService(mockFetchEmptyStreamUrl);
  await assert.rejects(
    async () => {
      await service1.getMediaDescriptor('m-feat-test');
    },
    (err) => {
      assert.equal(err.message, 'Dữ liệu feature không hợp lệ');
      return true;
    }
  );

  // Case 8b: feature has whitespace-only streamUrl
  const mockFetchWhitespaceStreamUrl = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      movieId: 'm-feat-test',
      hasFeature: true,
      hasTrailer: false,
      feature: {
        assetId: 'ast-empty',
        kind: 'feature',
        streamUrl: '    ',
      },
    }),
  });

  const service2 = loadMediaService(mockFetchWhitespaceStreamUrl);
  await assert.rejects(
    async () => {
      await service2.getMediaDescriptor('m-feat-test');
    },
    (err) => {
      assert.equal(err.message, 'Dữ liệu feature không hợp lệ');
      return true;
    }
  );

  // Case 8c: hasFeature is true but feature is missing or null
  const mockFetchNullFeature = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      movieId: 'm-feat-test',
      hasFeature: true,
      hasTrailer: false,
      feature: null,
    }),
  });

  const service3 = loadMediaService(mockFetchNullFeature);
  await assert.rejects(
    async () => {
      await service3.getMediaDescriptor('m-feat-test');
    },
    (err) => {
      assert.equal(err.message, 'Dữ liệu feature không hợp lệ');
      return true;
    }
  );

  // Case 8d: feature has invalid kind
  const mockFetchWrongKind = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      movieId: 'm-feat-test',
      hasFeature: true,
      hasTrailer: false,
      feature: {
        assetId: 'ast-wrong',
        kind: 'trailer',
        streamUrl: 'https://cdn.example.com/video.mp4',
      },
    }),
  });

  const service4 = loadMediaService(mockFetchWrongKind);
  await assert.rejects(
    async () => {
      await service4.getMediaDescriptor('m-feat-test');
    },
    (err) => {
      assert.equal(err.message, 'Dữ liệu feature không hợp lệ');
      return true;
    }
  );
});

test('9. Server 500/503 ném Error', async () => {
  // Test 500 Internal Server Error
  const mockFetch500 = async () => ({
    ok: false,
    status: 500,
  });

  const service500 = loadMediaService(mockFetch500);
  await assert.rejects(
    async () => {
      await service500.getMediaDescriptor('m-500');
    },
    (err) => {
      assert.ok(err instanceof Error);
      assert.match(err.message, /Lỗi tải mô tả media \(500\)/);
      return true;
    }
  );

  // Test 503 Service Unavailable
  const mockFetch503 = async () => ({
    ok: false,
    status: 503,
  });

  const service503 = loadMediaService(mockFetch503);
  await assert.rejects(
    async () => {
      await service503.getMediaDescriptor('m-503');
    },
    (err) => {
      assert.ok(err instanceof Error);
      assert.match(err.message, /Lỗi tải mô tả media \(503\)/);
      return true;
    }
  );
});
