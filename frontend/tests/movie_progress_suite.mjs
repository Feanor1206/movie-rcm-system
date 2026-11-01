import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

function load(window) {
  const module = { exports: {} };
  const source = fs.readFileSync(new URL('../lib/services/movieProgress.ts', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  vm.runInNewContext(code, { module, exports: module.exports, window, URLSearchParams, Date, JSON, console });
  return module.exports;
}

function memoryWindow(search = '') {
  const stored = new Map();
  return {
    stored,
    window: {
      localStorage: {
        getItem: (key) => stored.get(key) ?? null,
        setItem: (key, value) => stored.set(key, value),
        removeItem: (key) => stored.delete(key),
      },
      location: { search },
    },
  };
}

test('movie progress is stored and resumed by movie id', () => {
  const { window, stored } = memoryWindow();
  const progress = load(window);
  assert.equal(progress.listMovieProgress().length, 0);
  progress.saveMovieProgress({ movieId: 'totoro', title: 'Totoro', positionMs: 65000, durationMs: 120000 }, Date.parse('2026-11-01T03:00:00Z'));
  progress.saveMovieProgress({ movieId: 'spirited-away', title: 'Spirited Away', positionMs: 1000, durationMs: 900000, completed: true }, Date.parse('2026-11-01T04:00:00Z'));
  const saved = progress.getMovieProgress('totoro');
  assert.equal(saved.positionMs, 65000);
  assert.equal(progress.isUsableMovieProgress(saved), true);
  assert.equal(progress.isUsableMovieProgress(progress.getMovieProgress('spirited-away')), false);
  assert.equal(progress.buildMovieProgressHref(saved), '/movies/totoro?t=65000');
  assert.equal(stored.size, 1);
  for (let i = 0; i < 40; i++) {
    progress.saveMovieProgress({ movieId: `film-${i}`, title: `Film ${i}`, positionMs: 1000 }, Date.parse('2026-11-01T05:00:00Z') + i);
  }
  assert.equal(progress.listMovieProgress().length, 30);
});

test('a t query on the film page overrides the stored resume point', () => {
  const { window } = memoryWindow('?t=15000');
  const progress = load(window);
  progress.saveMovieProgress({ movieId: 'totoro', title: 'Totoro', positionMs: 65000, durationMs: 120000 });
  assert.equal(progress.readFilmResumeSeconds('totoro'), 15);
});
