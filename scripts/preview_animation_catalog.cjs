/**
 * Animation Catalog Dry-Run & Preview Tool (M2 Gate Evidence)
 *
 * Simulates additive and idempotent catalog onboarding against an in-memory hardcoded
 * baseline fixture array (6 fiction movies from DataInitializer.java).
 *
 * NOTE: This tool strictly performs preview / dry-run analysis against the hardcoded baseline
 * and candidate fixture. It is NOT an importer and does NOT connect to or modify any live database.
 * Detects ADD, SKIP, and CONFLICT actions strictly by canonical ID.
 *
 * Usage:
 *   node scripts/preview_animation_catalog.cjs           # Runs preview against hardcoded baseline
 *   node scripts/preview_animation_catalog.cjs --test    # Runs automated dry-run test suite
 */

const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

const DEFAULT_FIXTURE_PATH = path.resolve(__dirname, '../docs/fixtures/animation_catalog_fixture.json');

// Default backend baseline seed (6 fiction movies from DataInitializer.java)
const BASELINE_FICTION_MOVIES = [
  { id: 'the-last-orbit', title: 'The Last Orbit', year: 2026, rating: 8.7, genres: ['Sci-Fi', 'Drama'] },
  { id: 'afterlight', title: 'Afterlight', year: 2025, rating: 8.3, genres: ['Drama', 'Mystery'] },
  { id: 'glass-horizon', title: 'Glass Horizon', year: 2026, rating: 8.1, genres: ['Thriller', 'Sci-Fi'] },
  { id: 'deep-blue', title: 'Deep Blue', year: 2024, rating: 7.9, genres: ['Adventure', 'Drama'] },
  { id: 'quiet-places', title: 'Quiet Places', year: 2025, rating: 8.5, genres: ['Romance', 'Drama'] },
  { id: 'nocturne', title: 'Nocturne', year: 2024, rating: 7.8, genres: ['Crime', 'Thriller'] },
];

function normalizeGenres(genres) {
  if (Array.isArray(genres)) return [...genres].map((g) => String(g).trim().toLowerCase()).sort();
  if (typeof genres === 'string') return genres.split(',').map((g) => g.trim().toLowerCase()).sort();
  return [];
}

function compareRecords(existing, candidate) {
  const differences = [];
  if (existing.title !== candidate.title) {
    differences.push({ field: 'title', existing: existing.title, candidate: candidate.title });
  }
  if (existing.year !== candidate.year) {
    differences.push({ field: 'year', existing: existing.year, candidate: candidate.year });
  }
  if (Math.abs(Number(existing.rating) - Number(candidate.rating)) > 0.01) {
    differences.push({ field: 'rating', existing: existing.rating, candidate: candidate.rating });
  }
  const existG = normalizeGenres(existing.genres);
  const candG = normalizeGenres(candidate.genres);
  if (existG.join(',') !== candG.join(',')) {
    differences.push({ field: 'genres', existing: existing.genres, candidate: candidate.genres });
  }
  return differences;
}

function dryRun(existingRecords, candidateRecords) {
  const existingMap = new Map();
  for (const m of existingRecords) {
    existingMap.set(m.id, m);
  }

  const adds = [];
  const skips = [];
  const conflicts = [];

  for (const candidate of candidateRecords) {
    if (!existingMap.has(candidate.id)) {
      adds.push(candidate);
    } else {
      const existing = existingMap.get(candidate.id);
      const diffs = compareRecords(existing, candidate);
      if (diffs.length === 0) {
        skips.push(candidate);
      } else {
        conflicts.push({
          candidate,
          existing,
          differences: diffs,
        });
      }
    }
  }

  return {
    totalCandidates: candidateRecords.length,
    adds,
    skips,
    conflicts,
  };
}

function runPreview(fixturePath = DEFAULT_FIXTURE_PATH, existingRecords = BASELINE_FICTION_MOVIES) {
  const raw = fs.readFileSync(fixturePath, 'utf8');
  const fixture = JSON.parse(raw);
  const candidates = fixture.records || [];

  console.log('================================================================');
  console.log('   ANIMATION CATALOG ONBOARDING PREVIEW / DRY-RUN (M2 GATE)    ');
  console.log('================================================================');
  console.log(`- Provenance: ${fixture.provenance}`);
  console.log(`- Description: ${fixture.sourceDescription}`);
  console.log(`- Policy: ${fixture.policy} (additive, no overwrite, no fuzzy matching)`);
  console.log(`- Target Comparison: Hardcoded in-memory baseline array (NOT live catalog / NOT importer)`);
  console.log(`- Baseline Records in Target: ${existingRecords.length}`);
  console.log(`- Candidate Records to Process: ${candidates.length}`);
  console.log('----------------------------------------------------------------');

  const result = dryRun(existingRecords, candidates);

  console.log(`\n[PREVIEW SUMMARY]`);
  console.log(`  + ADD (New animations to insert):      ${result.adds.length}`);
  console.log(`  = SKIP (Idempotent, already identical): ${result.skips.length}`);
  console.log(`  ! CONFLICT (Same ID, differing data):   ${result.conflicts.length}`);

  if (result.adds.length > 0) {
    console.log(`\n[PROPOSED ADDITIONS]`);
    for (const a of result.adds) {
      console.log(`  [ADD] ${a.id.padEnd(16)} | ${a.title.padEnd(32)} | ${a.year} | ${a.rating}/10 | [${a.genres.join(', ')}]`);
    }
  }

  if (result.conflicts.length > 0) {
    console.log(`\n[CONFLICTS DETECTED - OVERWRITE REFUSED]`);
    for (const c of result.conflicts) {
      console.log(`  [CONFLICT] ID: ${c.candidate.id}`);
      for (const d of c.differences) {
        console.log(`    - Field "${d.field}": target="${JSON.stringify(d.existing)}" vs candidate="${JSON.stringify(d.candidate)}"`);
      }
    }
  }

  console.log('----------------------------------------------------------------');
  console.log('Status: DRY-RUN COMPLETED (NO CHANGES WRITTEN TO DATABASE)');
  console.log('================================================================\n');

  return result;
}

function runSelfTests() {
  console.log('Running dry-run verification tests...');
  const fixture = JSON.parse(fs.readFileSync(DEFAULT_FIXTURE_PATH, 'utf8')).records;

  // Test 1: First run against clean fiction baseline -> All 6 animation items are ADDed
  const r1 = dryRun(BASELINE_FICTION_MOVIES, fixture);
  assert.equal(r1.adds.length, 6, 'First run must mark all 6 records as ADD');
  assert.equal(r1.skips.length, 0, 'First run has 0 skips');
  assert.equal(r1.conflicts.length, 0, 'First run has 0 conflicts');
  console.log('✔ Test 1: First run marks all 6 records as ADD');

  // Test 2: Idempotency (Second run against DB that already has the 6 animations)
  const populated = [...BASELINE_FICTION_MOVIES, ...fixture];
  const r2 = dryRun(populated, fixture);
  assert.equal(r2.adds.length, 0, 'Second run must NOT duplicate records (0 adds)');
  assert.equal(r2.skips.length, 6, 'Second run must SKIP all 6 existing identical records');
  assert.equal(r2.conflicts.length, 0, 'Second run has 0 conflicts');
  console.log('✔ Test 2: Idempotency: second run produces 0 adds and 6 skips');

  // Test 3: Conflict detection (Target has movie with same ID but different year/title)
  const conflictingTarget = [
    ...BASELINE_FICTION_MOVIES,
    { id: 'spirited-away', title: 'Spirited Away (Old Cut)', year: 1999, rating: 8.0, genres: ['Animation'] },
  ];
  const r3 = dryRun(conflictingTarget, fixture);
  assert.equal(r3.conflicts.length, 1, 'Conflicting metadata on same ID must be flagged as CONFLICT');
  assert.equal(r3.conflicts[0].candidate.id, 'spirited-away');
  assert.equal(r3.adds.length, 5, 'Remaining 5 non-conflicting records are added');
  console.log('✔ Test 3: Conflict detection correctly flags differing metadata without overwrite');

  console.log('All 3 dry-run tests passed successfully!\n');
}

if (process.argv.includes('--test')) {
  runSelfTests();
  runPreview();
} else {
  runPreview();
}

module.exports = { dryRun, runPreview, runSelfTests };
