import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import ts from '../node_modules/typescript/lib/typescript.js';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(__dirname, '../lib/services/episodeNavigation.ts');
const source = fs.readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const moduleObject = { exports: {} };
vm.runInNewContext(compiled, { exports: moduleObject.exports, module: moduleObject });
const navigation = moduleObject.exports;

const seasons = [
  { id: 'season-2', seriesId: 'series', number: 2, title: 'Season 2' },
  { id: 'season-1', seriesId: 'series', number: 1, title: 'Season 1' },
];

const episodes = [
  { id: 's1-e10', seriesId: 'series', seasonId: 'season-1', number: 10, title: 'Ten' },
  { id: 's2-e1', seriesId: 'series', seasonId: 'season-2', number: 1, title: 'Season Two One' },
  { id: 's1-e2', seriesId: 'series', seasonId: 'season-1', number: 2, title: 'Two' },
  { id: 's1-e1', seriesId: 'series', seasonId: 'season-1', number: 1, title: 'One' },
  { id: 's2-e10', seriesId: 'series', seasonId: 'season-2', number: 10, title: 'Season Two Ten' },
];

test('Episode lists sort numerically, so episode 10 follows episode 2', () => {
  const sorted = navigation.getEpisodesForSeason(episodes, 'season-1');
  assert.deepEqual(Array.from(sorted, (episode) => episode.id), ['s1-e1', 's1-e2', 's1-e10']);
});

test('Duplicate episode numbers stay inside their own season and next/previous stop at boundaries', () => {
  const seasonTwo = navigation.getEpisodesForSeason(episodes, 'season-2');
  assert.deepEqual(Array.from(seasonTwo, (episode) => episode.id), ['s2-e1', 's2-e10']);
  assert.equal(navigation.getAdjacentEpisode(episodes, 'season-1', 's1-e10', 1), null);
  assert.equal(navigation.getAdjacentEpisode(episodes, 'season-2', 's2-e1', -1), null);
  assert.equal(navigation.getAdjacentEpisode(episodes, 'season-2', 's2-e1', 1)?.id, 's2-e10');
});

test('A deep-linked episode selects its actual season even when episode numbers repeat', () => {
  const selectedSeason = navigation.getInitialSeasonId(seasons, episodes, 's2-e1');
  const selectedEpisode = navigation.getInitialEpisode(episodes, selectedSeason, 's2-e1');
  assert.equal(selectedSeason, 'season-2');
  assert.equal(selectedEpisode?.id, 's2-e1');
});

test('Default selection uses the numerically first season and first ordered episode', () => {
  const selectedSeason = navigation.getInitialSeasonId(seasons, episodes);
  const selectedEpisode = navigation.getInitialEpisode(episodes, selectedSeason);
  assert.equal(selectedSeason, 'season-1');
  assert.equal(selectedEpisode?.id, 's1-e1');
});
