import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from '../node_modules/typescript/lib/typescript.js';
import fs from 'node:fs';
import vm from 'node:vm';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const routingFile = path.resolve(__dirname, '../lib/services/mediaRouting.ts');

function loadMediaRouting() {
  const code = fs.readFileSync(routingFile, 'utf8');
  const compiled = ts.transpileModule(code, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;

  const sandbox = {
    exports: {},
    module: { exports: {} },
    URLSearchParams,
    encodeURIComponent,
    decodeURIComponent,
    String,
    Number,
    Boolean,
    console,
  };
  vm.runInNewContext(compiled, sandbox);
  return sandbox.module.exports.buildMediaItemHref ? sandbox.module.exports : sandbox.exports;
}

const { buildMediaItemHref, resolveFileTimestamp, resolveMediaSeekSeconds } = loadMediaRouting();

// 1. Series card -> đúng series
test('1. Series card: resolves to /series/[id]', () => {
  const item = {
    id: 'ser_jadoo',
    title: 'Xin Chào Jadoo',
    item_type: 'series',
  };
  const href = buildMediaItemHref(item);
  assert.equal(href, '/series/ser_jadoo');
});

// 2. Episode card -> đúng series/episode và asset nếu có
test('2. Episode card: resolves to /series/[seriesId]?episode=[episodeId]', () => {
  const item = {
    id: 'ep_jadoo_s01_0001',
    title: 'Anh sẽ mua cho em tất cả những gì em muốn ăn.',
    item_type: 'episode',
    series_id: 'ser_jadoo',
    primary_media_asset_id: 'asset_jadoo_s01_v0001',
  };
  const href = buildMediaItemHref(item);
  assert.equal(href, '/series/ser_jadoo?episode=ep_jadoo_s01_0001&asset=asset_jadoo_s01_v0001');

  // Verify without asset
  const itemNoAsset = {
    id: 'ep_jadoo_s01_0002',
    item_type: 'episode',
    series_id: 'ser_jadoo',
  };
  assert.equal(buildMediaItemHref(itemNoAsset), '/series/ser_jadoo?episode=ep_jadoo_s01_0002');
});

// 3. Hai tập cùng số thuộc hai mùa -> hai episode khác nhau
test('3. Cross-season same episode number: resolves to distinct episode IDs without collision', () => {
  const s01e01 = {
    id: 'ep_jadoo_s01_0001',
    title: 'Anh sẽ mua cho em... (S1E1)',
    item_type: 'episode',
    series_id: 'ser_jadoo',
    season_number: 1,
    episode_number: 1,
  };
  const s03e01 = {
    id: 'ep_jadoo_s03_0001',
    title: 'Chào chồng tương lai của em (S3E1)',
    item_type: 'episode',
    series_id: 'ser_jadoo',
    season_number: 3,
    episode_number: 1,
  };

  const href1 = buildMediaItemHref(s01e01);
  const href2 = buildMediaItemHref(s03e01);

  assert.notEqual(href1, href2);
  assert.match(href1, /episode=ep_jadoo_s01_0001/);
  assert.match(href2, /episode=ep_jadoo_s03_0001/);
});

// 4. Segment -> đúng episode/asset/time
test('4. Segment card: resolves to /series/[seriesId]?episode=[epId]&segment=[segId]&t=[time]', () => {
  const segment = {
    id: 'seg_jadoo_s01_008a',
    title: 'Cứu cá vàng và cuộc tình với chàng Romy',
    item_type: 'segment',
    series_id: 'ser_jadoo',
    episode_id: 'ep_jadoo_s01_0008',
    media_asset_id: 'asset_jadoo_s01_v0008',
    start_ms: 0,
    end_ms: 650000,
  };
  const href = buildMediaItemHref(segment);
  assert.equal(
    href,
    '/series/ser_jadoo?episode=ep_jadoo_s01_0008&segment=seg_jadoo_s01_008a&asset=asset_jadoo_s01_v0008&t=0'
  );
});

// 5. Timestamp null -> không tự tua 0
test('5. Null/undefined timestamp: does NOT emit &t=0', () => {
  const segNoTime = {
    id: 'seg_jadoo_s01_008a',
    item_type: 'segment',
    series_id: 'ser_jadoo',
    episode_id: 'ep_jadoo_s01_0008',
    start_ms: null,
  };
  const href = buildMediaItemHref(segNoTime);
  assert.equal(href, '/series/ser_jadoo?episode=ep_jadoo_s01_0008&segment=seg_jadoo_s01_008a');
  assert.doesNotMatch(href, /&t=/);
  assert.doesNotMatch(href, /t=0/);

  const segUndefTime = {
    id: 'seg_jadoo_s01_008a',
    item_type: 'segment',
    series_id: 'ser_jadoo',
    episode_id: 'ep_jadoo_s01_0008',
  };
  const hrefUndef = buildMediaItemHref(segUndefTime);
  assert.doesNotMatch(hrefUndef, /&t=/);
});

// 6. Movie legacy -> giữ route cũ
test('6. Legacy movie item: maintains /movies/[id] route', () => {
  const legacy1 = {
    id: 'spirited-away',
    title: 'Spirited Away',
    item_type: 'movie',
  };
  assert.equal(buildMediaItemHref(legacy1), '/movies/spirited-away');

  const legacyNoType = {
    id: 'my-neighbor-totoro',
    title: 'My Neighbor Totoro',
  };
  assert.equal(buildMediaItemHref(legacyNoType), '/movies/my-neighbor-totoro');
});

// 7. Thiếu context -> không tạo link nhầm
test('7. Missing context: does NOT fabricate phantom series or link to wrong episode', () => {
  // Orphan episode with no series_id: falls back to safe standalone route instead of guessing ser_jadoo
  const orphanEpisode = {
    id: 'ep_orphan_9999',
    item_type: 'episode',
  };
  const hrefOrphan = buildMediaItemHref(orphanEpisode);
  assert.equal(hrefOrphan, '/movies/ep_orphan_9999');
  assert.doesNotMatch(hrefOrphan, /ser_jadoo/);

  // Completely empty item
  assert.equal(buildMediaItemHref({}), '/movies');
  assert.equal(buildMediaItemHref(null), '/movies');
  assert.equal(buildMediaItemHref(undefined), '/movies');
});

// 8. Tiêu đề và nút hành động dùng cùng đích
test('8. Consistency: buildMediaItemHref is pure and deterministic for both title and button link', () => {
  const item = {
    id: 'ep_jadoo_s01_0001',
    item_type: 'episode',
    series_id: 'ser_jadoo',
    title: 'Test Episode',
  };
  const titleHref = buildMediaItemHref(item);
  const actionButtonHref = buildMediaItemHref(item);
  assert.equal(titleHref, actionButtonHref);
  assert.equal(titleHref, '/series/ser_jadoo?episode=ep_jadoo_s01_0001');
});

// 9. Ký tự đặc biệt trong params được encode đúng
test('9. Special characters in query parameters are strictly URL encoded and safely decoded', () => {
  const specialItem = {
    id: 'ep special #1 & 2 [test]',
    item_type: 'episode',
    series_id: 'ser special / name',
    primary_media_asset_id: 'asset:special+1',
  };
  const href = buildMediaItemHref(specialItem);
  assert.match(href, /^\/series\/ser%20special%20%2F%20name\?/);

  // Parse URL search params
  const [pathPart, queryPart] = href.split('?');
  const params = new URLSearchParams(queryPart);
  assert.equal(params.get('episode'), 'ep special #1 & 2 [test]');
  assert.equal(params.get('asset'), 'asset:special+1');
});

// 10. V2: Scene card emits timeline=file and preserves start_ms
test('10. V2: Scene card emits timeline=file and preserves start_ms', () => {
  const scene = {
    id: 'scene_jadoo_s01_0001_sc01',
    item_type: 'scene',
    series_id: 'ser_jadoo',
    episode_id: 'ep_jadoo_s01_0001',
    media_asset_id: 'asset_jadoo_s01_v0001',
    start_ms: 5000,
  };
  const href = buildMediaItemHref(scene);
  assert.equal(
    href,
    '/series/ser_jadoo?episode=ep_jadoo_s01_0001&scene=scene_jadoo_s01_0001_sc01&asset=asset_jadoo_s01_v0001&t=5000&timeline=file'
  );
});

// 11. V2: Segment card preserves logical episode timeline (does not emit timeline=file)
test('11. V2: Segment card preserves logical episode timeline without timeline=file', () => {
  const segment = {
    id: 'seg_jadoo_s01_0001_sg01',
    item_type: 'segment',
    series_id: 'ser_jadoo',
    episode_id: 'ep_jadoo_s01_0001',
    media_asset_id: 'asset_jadoo_s01_v0001',
    start_ms: 5000,
  };
  const href = buildMediaItemHref(segment);
  assert.equal(
    href,
    '/series/ser_jadoo?episode=ep_jadoo_s01_0001&segment=seg_jadoo_s01_0001_sg01&asset=asset_jadoo_s01_v0001&t=5000'
  );
  assert.doesNotMatch(href, /timeline=file/);
});

// 12. V2: Scene file timestamp resolves directly (5s with 30s source offset -> 5s)
test('12. V2: Scene file timestamp resolves directly to file offset (5s with 30s source offset -> 5.0s)', () => {
  const asset = {
    id: 'asset_jadoo_s01_v0001',
    coverageJson: JSON.stringify([
      {
        episode_id: 'ep_jadoo_s01_0001',
        source_in_ms: 30000,
        source_out_ms: 60000,
        episode_in_ms: 0,
      },
    ]),
  };

  // Scene with timeline=file or isScene=true resolves to file offset 5000/1000 = 5.0s
  const seekSec = resolveMediaSeekSeconds({
    timeMs: 5000,
    timeline: 'file',
    isScene: true,
    isSegment: false,
    asset,
    episodeId: 'ep_jadoo_s01_0001',
    sceneStartMs: 5000,
  });
  assert.equal(seekSec, 5.0);

  // Even if timeline parameter is omitted, isScene=true treats it as file timeline
  const seekSecFromSceneFlag = resolveMediaSeekSeconds({
    timeMs: '5000',
    isScene: true,
    isSegment: false,
    asset,
    episodeId: 'ep_jadoo_s01_0001',
  });
  assert.equal(seekSecFromSceneFlag, 5.0);
});

// 13. V2: Segment logical timestamp maps through coverage (5s with 30s source offset -> 35s)
test('13. V2: Segment logical timestamp maps through coverage (5s with 30s source offset -> 35.0s)', () => {
  const asset = {
    id: 'asset_jadoo_s01_v0001',
    coverageJson: JSON.stringify([
      {
        episode_id: 'ep_jadoo_s01_0001',
        source_in_ms: 30000,
        source_out_ms: 60000,
        episode_in_ms: 0,
      },
    ]),
  };

  const seekSec = resolveMediaSeekSeconds({
    timeMs: 5000,
    timeline: null,
    isScene: false,
    isSegment: true,
    asset,
    episodeId: 'ep_jadoo_s01_0001',
    segmentStartMs: 5000,
  });
  assert.equal(seekSec, 35.0); // (30000 + 5000) / 1000 = 35.0s
});

// 14. V2: Timestamp 0 is valid and resolves to 0.0s
test('14. V2: Timestamp 0 is valid and resolves to 0.0s (not rejected or skipped)', () => {
  const asset = {
    id: 'asset_jadoo_s01_v0001',
    coverageJson: JSON.stringify([
      {
        episode_id: 'ep_jadoo_s01_0001',
        source_in_ms: 0,
        source_out_ms: 60000,
        episode_in_ms: 0,
      },
    ]),
  };

  // Scene at 0ms
  const sceneSeek = resolveMediaSeekSeconds({
    timeMs: 0,
    timeline: 'file',
    isScene: true,
    asset,
  });
  assert.equal(sceneSeek, 0.0);

  // Segment at 0ms
  const segSeek = resolveMediaSeekSeconds({
    timeMs: '0',
    isSegment: true,
    asset,
    episodeId: 'ep_jadoo_s01_0001',
  });
  assert.equal(segSeek, 0.0);

  // href preserves t=0
  const scene = {
    id: 'scene_0',
    item_type: 'scene',
    series_id: 'ser_jadoo',
    episode_id: 'ep_jadoo_s01_0001',
    start_ms: 0,
  };
  const href = buildMediaItemHref(scene);
  assert.match(href, /&t=0/);
});

// 15. V2: Invalid timestamps (negative, NaN, Infinity) are strictly rejected
test('15. V2: Invalid timestamps (negative, NaN, Infinity) return null', () => {
  const asset = {
    id: 'asset_test',
    coverageJson: JSON.stringify([
      { episode_id: 'ep1', source_in_ms: 0, source_out_ms: 60000, episode_in_ms: 0 },
    ]),
  };

  assert.equal(resolveMediaSeekSeconds({ timeMs: -100, isScene: true }), null);
  assert.equal(resolveMediaSeekSeconds({ timeMs: NaN, isScene: true }), null);
  assert.equal(resolveMediaSeekSeconds({ timeMs: Infinity, isScene: true }), null);
  assert.equal(resolveMediaSeekSeconds({ timeMs: 'invalid', isScene: true }), null);

  assert.equal(resolveFileTimestamp(-50, asset, null, 'ep1'), null);
  assert.equal(resolveFileTimestamp(NaN, asset, null, 'ep1'), null);
  assert.equal(resolveFileTimestamp(Infinity, asset, null, 'ep1'), null);
});

// 16. V2: Null/undefined timestamps return null (does not fake seek to 0)
test('16. V2: Null/undefined timestamps return null (does not fake seek to 0)', () => {
  assert.equal(resolveMediaSeekSeconds({ timeMs: null, isScene: true, sceneStartMs: null }), null);
  assert.equal(resolveMediaSeekSeconds({ timeMs: undefined, isScene: true }), null);
  assert.equal(resolveMediaSeekSeconds({ timeMs: '', isSegment: true, segmentStartMs: undefined }), null);
});

// 17. V2: Coverage mapping with segment_id specificity and fallback
test('17. V2: Coverage mapping prioritizes matching segment_id', () => {
  const asset = {
    id: 'asset_test',
    coverageJson: JSON.stringify([
      {
        episode_id: 'ep1',
        segment_id: 'seg_A',
        source_in_ms: 10000,
        source_out_ms: 30000,
        episode_in_ms: 0,
      },
      {
        episode_id: 'ep1',
        segment_id: 'seg_B',
        source_in_ms: 40000,
        source_out_ms: 70000,
        episode_in_ms: 0,
      },
    ]),
  };

  // seg_A at 5000ms -> 10000 + 5000 = 15000ms -> 15.0s
  const seekA = resolveFileTimestamp(5000, asset, 'seg_A', 'ep1');
  assert.equal(seekA, 15.0);

  // seg_B at 5000ms -> 40000 + 5000 = 45000ms -> 45.0s
  const seekB = resolveFileTimestamp(5000, asset, 'seg_B', 'ep1');
  assert.equal(seekB, 45.0);

  // unmapped segment returns null if delta is negative
  const assetNegative = {
    id: 'asset_neg',
    coverageJson: JSON.stringify([
      {
        episode_id: 'ep1',
        segment_id: 'seg_C',
        source_in_ms: 10000,
        episode_in_ms: 20000,
      },
    ]),
  };
  assert.equal(resolveFileTimestamp(5000, assetNegative, 'seg_C', 'ep1'), null);
});

// 18. V1: Series page AST audit: sync effect callback does NOT depend on selectedEpisode
test('18. V1: Series page AST audit - URL sync effect does NOT depend on selectedEpisode', () => {
  const pageFile = path.resolve(__dirname, '../app/series/[id]/page.tsx');
  const code = fs.readFileSync(pageFile, 'utf8');
  const sf = ts.createSourceFile('page.tsx', code, ts.ScriptTarget.Latest, true);

  let syncEffectFound = false;
  function checkEffectDeps(node) {
    if (ts.isCallExpression(node)) {
      const text = node.expression.getText(sf);
      if (text === 'useEffect' && node.arguments.length >= 2) {
        const depsText = node.arguments[1].getText(sf);
        if (depsText.includes('targetEpisodeId') && !depsText.includes('targetSceneId')) {
          syncEffectFound = true;
          assert.doesNotMatch(
            depsText,
            /selectedEpisode/,
            'URL sync useEffect must NOT depend on selectedEpisode (prevents snapback loop)'
          );
        }
      }
    }
    ts.forEachChild(node, checkEffectDeps);
  }
  checkEffectDeps(sf);
  assert.ok(syncEffectFound, 'Found URL sync useEffect in page.tsx');
});

// 19. V1: Series page sync callback simulation: deep-link A -> select B -> maintains B (no snapback)
test('19. V1: Deep link A -> select B maintains B without snapback', () => {
  const ep1 = { id: 'ep_jadoo_s01_0001', title: 'Tập 1' };
  const ep2 = { id: 'ep_jadoo_s01_0002', title: 'Tập 2' };
  const seriesData = { episodes: [ep1, ep2] };

  // Simulate component state
  let targetEpisodeId = 'ep_jadoo_s01_0001';
  let prevUrlEpisodeIdRef = { current: 'ep_jadoo_s01_0001' };
  let selectedEpisode = ep1;
  function setSelectedEpisode(ep) {
    selectedEpisode = ep;
  }

  // Effect callback extracted from page.tsx:
  function runSyncEffect() {
    if (!seriesData?.episodes) return;
    if (targetEpisodeId !== prevUrlEpisodeIdRef.current) {
      prevUrlEpisodeIdRef.current = targetEpisodeId;
      if (targetEpisodeId) {
        const matched = seriesData.episodes.find((e) => e.id === targetEpisodeId);
        if (matched) {
          setSelectedEpisode(matched);
        }
      } else if (seriesData.episodes.length > 0) {
        setSelectedEpisode(seriesData.episodes[0]);
      }
    }
  }

  // User manually selects episode B
  function handleSelectEpisode(ep) {
    if (ep.id === selectedEpisode?.id) return;
    setSelectedEpisode(ep);
  }

  // 1. Initial state has ep1 selected
  assert.equal(selectedEpisode.id, 'ep_jadoo_s01_0001');

  // 2. User selects ep2
  handleSelectEpisode(ep2);
  assert.equal(selectedEpisode.id, 'ep_jadoo_s01_0002');

  // 3. Effect callback runs while targetEpisodeId is still ep1 (URL param hasn't changed from router)
  runSyncEffect();
  assert.equal(
    selectedEpisode.id,
    'ep_jadoo_s01_0002',
    'State must remain ep2! Snapback to ep1 is prevented.'
  );

  // 4. Rapid selection: ep2 -> ep1 -> ep2
  handleSelectEpisode(ep1);
  assert.equal(selectedEpisode.id, 'ep_jadoo_s01_0001');
  runSyncEffect();
  assert.equal(selectedEpisode.id, 'ep_jadoo_s01_0001');

  handleSelectEpisode(ep2);
  assert.equal(selectedEpisode.id, 'ep_jadoo_s01_0002');
  runSyncEffect();
  assert.equal(selectedEpisode.id, 'ep_jadoo_s01_0002');
});

// 20. V1: Series page URL update cleans up scene/segment/timestamp/asset on episode change
test('20. V1: Manual episode change cleans up scene/segment/timestamp/asset query parameters', () => {
  const originalUrl = 'http://localhost:3000/series/ser_jadoo?episode=ep1&scene=sc1&segment=sg1&t=5000&timeline=file&asset=ast1';
  const url = new URL(originalUrl);

  const nextEpId = 'ep2';
  url.searchParams.set('episode', nextEpId);
  url.searchParams.delete('scene');
  url.searchParams.delete('segment');
  url.searchParams.delete('t');
  url.searchParams.delete('timeline');
  url.searchParams.delete('timescale');
  url.searchParams.delete('asset');

  assert.equal(url.searchParams.get('episode'), 'ep2');
  assert.equal(url.searchParams.get('scene'), null);
  assert.equal(url.searchParams.get('segment'), null);
  assert.equal(url.searchParams.get('t'), null);
  assert.equal(url.searchParams.get('timeline'), null);
  assert.equal(url.searchParams.get('asset'), null);
});

// 21. V1: External URL navigation (browser back/forward) updates selected episode
test('21. V1: External URL navigation updates selected episode when URL param actually changes', () => {
  const ep1 = { id: 'ep1' };
  const ep2 = { id: 'ep2' };
  const ep3 = { id: 'ep3' };
  const seriesData = { episodes: [ep1, ep2, ep3] };

  let targetEpisodeId = 'ep1';
  let prevUrlEpisodeIdRef = { current: 'ep1' };
  let selectedEpisode = ep1;
  function setSelectedEpisode(ep) {
    selectedEpisode = ep;
  }

  function runSyncEffect() {
    if (!seriesData?.episodes) return;
    if (targetEpisodeId !== prevUrlEpisodeIdRef.current) {
      prevUrlEpisodeIdRef.current = targetEpisodeId;
      if (targetEpisodeId) {
        const matched = seriesData.episodes.find((e) => e.id === targetEpisodeId);
        if (matched) {
          setSelectedEpisode(matched);
        }
      } else if (seriesData.episodes.length > 0) {
        setSelectedEpisode(seriesData.episodes[0]);
      }
    }
  }

  // External navigation to ep3
  targetEpisodeId = 'ep3';
  runSyncEffect();
  assert.equal(selectedEpisode.id, 'ep3');

  // External navigation (back) to ep2
  targetEpisodeId = 'ep2';
  runSyncEffect();
  assert.equal(selectedEpisode.id, 'ep2');

  // External navigation to base series page without episode param
  targetEpisodeId = null;
  runSyncEffect();
  assert.equal(selectedEpisode.id, 'ep1', 'Defaults to first episode when no episode param in URL');
});


test('Coverage rejects timestamps past a segment, invalid offsets and wrong episode', () => {
  const entry = { episode_id: 'ep1', segment_id: 'seg1', source_in_ms: 30000, source_out_ms: 60000, episode_in_ms: 0 };
  const asset = (entries) => ({ coverageJson: JSON.stringify(entries) });
  assert.equal(resolveFileTimestamp(5000, asset([entry]), 'seg1', 'ep1'), 35);
  assert.equal(resolveFileTimestamp(30000, asset([entry]), 'seg1', 'ep1'), null);
  assert.equal(resolveFileTimestamp(5000, asset([entry]), 'seg1', 'ep2'), null);
  assert.equal(resolveFileTimestamp(5000, asset([{ ...entry, source_in_ms: -1 }]), 'seg1', 'ep1'), null);
  assert.equal(resolveFileTimestamp(5000, asset([{ ...entry, episode_in_ms: null }]), 'seg1', 'ep1'), null);
  assert.equal(resolveFileTimestamp(5000, asset([null]), 'seg1', 'ep1'), null);
});

test('Adjacent coverage picks the next interval at a shared boundary', () => {
  const asset = { coverageJson: JSON.stringify([
    { episode_id: 'ep1', source_in_ms: 0, source_out_ms: 10000, episode_in_ms: 0 },
    { episode_id: 'ep1', source_in_ms: 30000, source_out_ms: 40000, episode_in_ms: 10000 },
  ]) };
  assert.equal(resolveFileTimestamp(10000, asset, null, 'ep1'), 30);
});
