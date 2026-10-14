import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, '..');

// Import mediaService functions
import { resolveStreamUrl, getMediaDescriptor } from '../lib/services/mediaService.ts';

const movieDetailSource = fs.readFileSync(
  path.join(root, 'features/movies/components/MovieDetail.tsx'),
  'utf8'
);

test('1. resolveStreamUrl correctly handles relative and absolute URLs', () => {
  // Absolute URLs remain intact
  assert.equal(
    resolveStreamUrl('https://example.com/stream/video.mp4'),
    'https://example.com/stream/video.mp4'
  );
  assert.equal(
    resolveStreamUrl('http://cdn.example.com/media/clip.mp4'),
    'http://cdn.example.com/media/clip.mp4'
  );

  // Relative URLs are prefixed with base host
  const relativeStream = resolveStreamUrl('/api/media/stream/ast-001');
  assert.ok(
    relativeStream.endsWith('/api/media/stream/ast-001'),
    'Must end with relative path'
  );
  assert.ok(
    relativeStream.startsWith('http://') || relativeStream.startsWith('https://'),
    'Must start with protocol'
  );
});

test('2. getMediaDescriptor normalizes valid descriptor response', async () => {
  const origFetch = globalThis.fetch;
  try {
    globalThis.fetch = async (url) => {
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

    const desc = await getMediaDescriptor('m1-test');
    assert.equal(desc.movieId, 'm1-test');
    assert.equal(desc.hasFeature, true);
    assert.equal(desc.hasTrailer, true);
    assert.ok(desc.feature);
    assert.equal(desc.feature.assetId, 'ast-feat-01');
    assert.ok(desc.feature.streamUrl.endsWith('/api/media/stream/ast-feat-01'));
    assert.ok(desc.trailer);
    assert.equal(desc.trailer.assetId, 'ast-trl-01');
  } finally {
    globalThis.fetch = origFetch;
  }
});

test('3. getMediaDescriptor rejects on server error', async () => {
  const origFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({
      ok: false,
      status: 404,
    });

    await assert.rejects(
      () => getMediaDescriptor('non-existent'),
      /Lỗi tải mô tả media \(404\)/
    );
  } finally {
    globalThis.fetch = origFetch;
  }
});

test('4. MovieDetail: Play buttons distinguish Feature ("Xem phim") from Trailer ("Xem trailer")', () => {
  // Feature button
  assert.ok(
    movieDetailSource.includes('data-testid="play-feature-btn"'),
    'MovieDetail must declare data-testid="play-feature-btn"'
  );
  assert.ok(
    movieDetailSource.includes('Xem phim'),
    'MovieDetail must render "Xem phim" for feature asset'
  );

  // Trailer button
  assert.ok(
    movieDetailSource.includes('data-testid="play-trailer-btn"'),
    'MovieDetail must declare data-testid="play-trailer-btn"'
  );
  assert.ok(
    movieDetailSource.includes('Xem trailer / giới thiệu') ||
      movieDetailSource.includes('Xem trailer'),
    'MovieDetail must render trailer button'
  );
});

test('5. MovieDetail: Video player controls, timeline scrubber, and touch targets >=44px', () => {
  // Timeline scrubber
  assert.ok(
    movieDetailSource.includes('data-testid="video-timeline"'),
    'MovieDetail must provide range scrubber timeline'
  );
  assert.ok(
    movieDetailSource.includes('data-testid="video-time-display"'),
    'MovieDetail must display current / total time'
  );

  // Play/Pause button
  assert.ok(
    movieDetailSource.includes('data-testid="video-play-pause-btn"'),
    'MovieDetail must provide play/pause control'
  );

  // Volume & Fullscreen controls
  assert.ok(
    movieDetailSource.includes('data-testid="video-volume-btn"'),
    'MovieDetail must provide volume / mute control'
  );
  assert.ok(
    movieDetailSource.includes('data-testid="video-fullscreen-btn"'),
    'MovieDetail must provide fullscreen control'
  );

  // Touch targets >= 44x44px
  const controlMinSizes = movieDetailSource.match(/min-h-\[44px\]/g) || [];
  assert.ok(
    controlMinSizes.length >= 6,
    `All interactive video player controls must enforce min-h-[44px] touch target (found ${controlMinSizes.length})`
  );
});

test('6. MovieDetail: Buffering spinner and error recovery with retry preserving currentTime', () => {
  // Buffering indicator
  assert.ok(
    movieDetailSource.includes('data-testid="video-buffering"'),
    'MovieDetail must provide buffering indicator'
  );

  // Error overlay & retry button
  assert.ok(
    movieDetailSource.includes('data-testid="video-retry-btn"'),
    'MovieDetail must provide error retry button'
  );

  // Retry logic preserves currentTime
  assert.ok(
    movieDetailSource.includes('setRetryTime(videoRef.current.currentTime)'),
    'Error handler must record retryTime from currentTime'
  );
  assert.ok(
    movieDetailSource.includes('videoRef.current.currentTime = retryTime'),
    'Retry handler must restore currentTime'
  );
});

test('7. MovieDetail: Video player keyboard shortcuts', () => {
  // Space: play/pause
  assert.ok(
    movieDetailSource.includes("e.key === ' '") || movieDetailSource.includes("e.code === 'Space'"),
    'Player must intercept Space key'
  );
  assert.ok(
    movieDetailSource.includes('togglePlayPause()'),
    'Space key must trigger togglePlayPause'
  );

  // ArrowLeft / ArrowRight: seeking
  assert.ok(
    movieDetailSource.includes("e.key === 'ArrowLeft'"),
    'Player must intercept ArrowLeft'
  );
  assert.ok(
    movieDetailSource.includes("e.key === 'ArrowRight'"),
    'Player must intercept ArrowRight'
  );

  // ArrowUp / ArrowDown: volume
  assert.ok(
    movieDetailSource.includes("e.key === 'ArrowUp'"),
    'Player must intercept ArrowUp'
  );
  assert.ok(
    movieDetailSource.includes("e.key === 'ArrowDown'"),
    'Player must intercept ArrowDown'
  );

  // M: mute
  assert.ok(
    movieDetailSource.includes("e.key === 'm'") || movieDetailSource.includes("e.key === 'M'"),
    'Player must intercept Mute key'
  );

  // F: fullscreen
  assert.ok(
    movieDetailSource.includes("e.key === 'f'") || movieDetailSource.includes("e.key === 'F'"),
    'Player must intercept Fullscreen key'
  );
});
