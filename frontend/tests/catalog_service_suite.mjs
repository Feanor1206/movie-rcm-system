import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from '../node_modules/typescript/lib/typescript.js';
import fs from 'node:fs';
import vm from 'node:vm';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const serviceFile = path.resolve(__dirname, '../lib/services/catalogService.ts');

function loadService(mockFetch) {
  const code = fs.readFileSync(serviceFile, 'utf8');
  const compiled = ts.transpileModule(code, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;

  const timers = new Map();
  let timerId = 0;

  const sandbox = {
    exports: {},
    module: { exports: {} },
    fetch: mockFetch,
    process: { env: { NEXT_PUBLIC_SPRINGBOOT_API_URL: 'http://test-server/api' } },
    URLSearchParams,
    AbortController,
    setTimeout: (fn, ms) => {
      const id = ++timerId;
      timers.set(id, setTimeout(fn, ms));
      return id;
    },
    clearTimeout: (id) => {
      const t = timers.get(id);
      if (t) clearTimeout(t);
      timers.delete(id);
    },
    Error,
    Array,
    String,
    Boolean,
    console,
  };
  vm.runInNewContext(compiled, sandbox);
  const api = sandbox.module.exports.browseCatalog ? sandbox.module.exports : sandbox.exports;
  return { api, timers };
}

test('1. Catalog Client: browseCatalog constructs correct query string and normalizes PageResponse', async () => {
  let requestedUrl = '';
  const mockFetch = async (url) => {
    requestedUrl = url;
    return {
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        message: 'Movies retrieved successfully',
        data: {
          items: [
            {
              id: 'spirited-away',
              title: 'Spirited Away',
              year: 2001,
              rating: 8.6,
              runtime: '2h 05m',
              genres: ['Animation', 'Adventure'],
              description: 'Magical bathhouse',
              poster: 'https://img/poster.jpg',
              backdrop: null,
              videoUrl: null,
            },
          ],
          page: 0,
          size: 12,
          totalElements: 1,
          totalPages: 1,
          hasNext: false,
          hasPrevious: false,
        },
      }),
    };
  };

  const { api } = loadService(mockFetch);
  const result = await api.browseCatalog({
    query: 'magical',
    genre: 'Animation',
    genres: ['Animation', 'Adventure'],
    animationOnly: true,
    yearMin: 2000,
    yearMax: 2025,
    sort: 'rating',
    direction: 'desc',
    page: 0,
    size: 12,
  });

  assert.ok(requestedUrl.includes('/movies/browse?'));
  assert.ok(requestedUrl.includes('query=magical'));
  assert.ok(requestedUrl.includes('genre=Animation'));
  assert.ok(requestedUrl.includes('genres=Animation%2CAdventure'));
  assert.ok(requestedUrl.includes('animationOnly=true'));
  assert.ok(requestedUrl.includes('yearMin=2000'));
  assert.ok(requestedUrl.includes('yearMax=2025'));
  assert.ok(requestedUrl.includes('sort=rating'));
  assert.ok(requestedUrl.includes('direction=desc'));
  assert.ok(requestedUrl.includes('page=0'));
  assert.ok(requestedUrl.includes('size=12'));

  assert.equal(result.totalElements, 1);
  assert.equal(result.items[0].id, 'spirited-away');
  assert.equal(result.items[0].backdrop, '');
  assert.equal(result.items[0].videoUrl, undefined);
});

test('2. C1: External abort after headers received while body is pending aborts transport and throws cancellation', async () => {
  let requestSignal;
  let resolveBody;
  const bodyPromise = new Promise((resolve) => {
    resolveBody = resolve;
  });

  const mockFetch = async (url, opts) => {
    requestSignal = opts.signal;
    return {
      ok: true,
      status: 200,
      json: () =>
        new Promise((resolve, reject) => {
          opts.signal.addEventListener('abort', () => {
            const err = new Error('The operation was aborted');
            err.name = 'AbortError';
            reject(err);
          });
          bodyPromise.then(resolve, reject);
        }),
    };
  };

  const external = new AbortController();
  const { api, timers } = loadService(mockFetch);

  const request = api.browseCatalog({ timeoutMs: 500, signal: external.signal });

  // Wait for headers to be received and body to become pending
  for (let i = 0; i < 6; i++) await Promise.resolve();

  // Caller intentionally aborts
  external.abort();

  assert.equal(requestSignal.aborted, true, 'Transport signal must be aborted');

  await assert.rejects(
    async () => {
      await request;
    },
    (err) => {
      assert.equal(err.name, 'AbortError');
      assert.equal(err.isCanceled, true);
      assert.equal(err.status, 499);
      return true;
    }
  );

  assert.equal(timers.size, 0, 'Active timers must be cleaned up in finally');
});

test('3. C1: Slow body triggers timeout and cleans up timers', async () => {
  const hangingBodyPromise = new Promise(() => {});
  const mockFetch = async (url, opts) => {
    return {
      ok: true,
      status: 200,
      json: () =>
        new Promise((_, reject) => {
          opts.signal.addEventListener('abort', () => {
            const err = new Error('Timeout');
            err.name = 'AbortError';
            reject(err);
          });
        }),
    };
  };

  const { api, timers } = loadService(mockFetch);
  await assert.rejects(
    async () => {
      await api.browseCatalog({ timeoutMs: 40 });
    },
    (err) => {
      assert.equal(err.name, 'CatalogApiError');
      assert.equal(err.status, 408);
      assert.equal(err.isTimeout, true);
      return true;
    }
  );

  assert.equal(timers.size, 0, 'Timeout timer must be cleaned up in finally');
});

test('4. C1: Pre-aborted external signal rejects immediately without setting timer', async () => {
  let fetchCalled = false;
  const mockFetch = async () => {
    fetchCalled = true;
    return { ok: true, status: 200, json: async () => ({}) };
  };

  const external = new AbortController();
  external.abort();

  const { api, timers } = loadService(mockFetch);
  await assert.rejects(
    async () => {
      await api.browseCatalog({ signal: external.signal });
    },
    (err) => {
      assert.equal(err.name, 'AbortError');
      assert.equal(err.isCanceled, true);
      assert.equal(err.status, 499);
      return true;
    }
  );

  assert.equal(fetchCalled, false, 'Fetch must not be called for pre-aborted signal');
  assert.equal(timers.size, 0, 'No timer should be active');
});

test('5. C2: Malformed paginated payload (data={} or missing items) throws 502', async () => {
  const mockFetch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({ success: true, data: {} }), // malformed: missing items array
  });

  const { api } = loadService(mockFetch);
  await assert.rejects(
    async () => {
      await api.browseCatalog();
    },
    (err) => {
      assert.equal(err.name, 'CatalogApiError');
      assert.equal(err.status, 502);
      assert.match(err.message, /thiếu mảng items/);
      return true;
    }
  );
});

test('6. C2: normalizeCatalogMovie rejects missing required fields and never fabricates phantom zeros', () => {
  const { api } = loadService(async () => {});

  // Missing id
  assert.throws(
    () => api.normalizeCatalogMovie({ title: 'T', year: 2020, rating: 8 }),
    (err) => {
      assert.equal(err.status, 502);
      assert.match(err.message, /ID bắt buộc/);
      return true;
    }
  );

  // Missing title
  assert.throws(
    () => api.normalizeCatalogMovie({ id: 'm1', year: 2020, rating: 8 }),
    (err) => {
      assert.equal(err.status, 502);
      assert.match(err.message, /tiêu đề bắt buộc/);
      return true;
    }
  );

  // Missing/invalid year
  assert.throws(
    () => api.normalizeCatalogMovie({ id: 'm1', title: 'T', rating: 8 }),
    (err) => {
      assert.equal(err.status, 502);
      assert.match(err.message, /năm phát hành/);
      return true;
    }
  );

  // Missing/invalid rating
  assert.throws(
    () => api.normalizeCatalogMovie({ id: 'm1', title: 'T', year: 2020 }),
    (err) => {
      assert.equal(err.status, 502);
      assert.match(err.message, /điểm đánh giá/);
      return true;
    }
  );

  // Valid movie normalizes cleanly
  const valid = api.normalizeCatalogMovie({
    id: 'spirited-away',
    title: 'Spirited Away',
    year: 2001,
    rating: 8.6,
    genres: ['Animation'],
  });
  assert.equal(valid.id, 'spirited-away');
  assert.equal(valid.year, 2001);
  assert.equal(valid.rating, 8.6);
});

test('7. C2: getCatalogMovieById verifies response ID matches requested canonical ID', async () => {
  const mockFetch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      success: true,
      data: {
        id: 'other-movie',
        title: 'Other Movie',
        year: 2020,
        rating: 8.0,
        genres: ['Drama'],
      },
    }),
  });

  const { api } = loadService(mockFetch);
  await assert.rejects(
    async () => {
      await api.getCatalogMovieById('requested-movie');
    },
    (err) => {
      assert.equal(err.name, 'CatalogApiError');
      assert.equal(err.status, 502);
      assert.match(err.message, /không khớp với ID yêu cầu/);
      return true;
    }
  );

  // Literal ID verification: case difference (REQUESTED-MOVIE vs requested-movie) must be rejected
  const mockFetchCase = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      success: true,
      data: {
        id: 'REQUESTED-MOVIE',
        title: 'Case Movie',
        year: 2020,
        rating: 8.0,
        genres: ['Drama'],
      },
    }),
  });
  const { api: apiCase } = loadService(mockFetchCase);
  await assert.rejects(
    async () => {
      await apiCase.getCatalogMovieById('requested-movie');
    },
    (err) => {
      assert.equal(err.status, 502);
      assert.match(err.message, /không khớp với ID yêu cầu/);
      return true;
    }
  );
});

test('8. C2: getCatalogMovieById returns null on 404 HTML body without syntax error', async () => {
  const mockFetch = async () => ({
    ok: false,
    status: 404,
    // HTML body from Tomcat/Nginx that would throw SyntaxError if json() was called
    json: async () => {
      throw new SyntaxError('Unexpected token < in JSON at position 0');
    },
  });

  const { api } = loadService(mockFetch);
  const result = await api.getCatalogMovieById('nonexistent-movie');
  assert.equal(result, null, '404 HTML response must resolve to null');
});

test('9. C2: Search/Query precedence: blank query falls back to search parameter', async () => {
  let requestedUrl = '';
  const mockFetch = async (url) => {
    requestedUrl = url;
    return {
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        data: {
          items: [],
          page: 0,
          size: 10,
          totalElements: 0,
          totalPages: 0,
          hasNext: false,
          hasPrevious: false,
        },
      }),
    };
  };

  const { api } = loadService(mockFetch);

  // Blank query with valid search -> falls back to search
  await api.browseCatalog({ query: '   ', search: 'anime' });
  assert.ok(requestedUrl.includes('query=anime'), 'Blank query must fall back to search');

  // Both present and query non-empty -> query takes precedence
  await api.browseCatalog({ query: 'spirited', search: 'anime' });
  assert.ok(requestedUrl.includes('query=spirited'), 'Non-empty query takes precedence over search');
});

test('10. Catalog API: series list validates and maps real catalog fields', async () => {
  let requestedUrl = '';
  const { api } = loadService(async (url, options) => {
    requestedUrl = url;
    assert.equal(options.method, 'GET');
    return {
      ok: true,
      status: 200,
      json: async () => [{
        id: 'jadoo',
        title: 'Jadoo',
        synopsis: 'A catalog synopsis.',
        releaseYearStart: 2000,
        releaseYearEnd: 2005,
        genreIdsJson: '["comedy"]',
      }],
    };
  });

  const result = await api.getCatalogSeriesList();
  assert.equal(requestedUrl, 'http://test-server/api/catalog/series');
  assert.equal(result.length, 1);
  assert.equal(result[0].id, 'jadoo');
  assert.equal(result[0].title, 'Jadoo');
  assert.equal(result[0].synopsis, 'A catalog synopsis.');
  assert.equal(result[0].releaseYearStart, 2000);
  assert.equal(result[0].releaseYearEnd, 2005);
  assert.equal(result[0].genreIdsJson, '["comedy"]');
});

test('11. Catalog API: series list preserves HTTP and malformed-data errors', async () => {
  const { api: failedApi } = loadService(async () => ({
    ok: false,
    status: 503,
    json: async () => ({}),
  }));
  await assert.rejects(failedApi.getCatalogSeriesList(), (error) => error.status === 503);

  const { api: malformedApi } = loadService(async () => ({
    ok: true,
    status: 200,
    json: async () => [{ id: '', title: 'No ID' }],
  }));
  await assert.rejects(malformedApi.getCatalogSeriesList(), (error) => error.status === 502);
});

test('12. Catalog API: search encodes queries and validates result type', async () => {
  let requestedUrl = '';
  const { api } = loadService(async (url) => {
    requestedUrl = url;
    return {
      ok: true,
      status: 200,
      json: async () => [{ id: 'ep-1', type: 'episode', title: 'Episode 1', seriesId: 'jadoo' }],
    };
  });
  const result = await api.searchAnimationCatalog('Jadoo & friends');
  assert.ok(requestedUrl.endsWith('/catalog/search?q=Jadoo%20%26%20friends'));
  assert.equal(result[0].seriesId, 'jadoo');

  const { api: malformedApi } = loadService(async () => ({
    ok: true,
    status: 200,
    json: async () => [{ id: 'x', type: 'movie', title: 'Legacy film' }],
  }));
  await assert.rejects(malformedApi.searchAnimationCatalog('movie'), (error) => error.status === 502);
});

test('13. Catalog API: list request propagates caller cancellation', async () => {
  const external = new AbortController();
  const { api } = loadService(async (_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
  }));
  const pending = api.getCatalogSeriesList(undefined, external.signal, 500);
  external.abort();
  await assert.rejects(pending, (error) => error.isCanceled === true);
});
