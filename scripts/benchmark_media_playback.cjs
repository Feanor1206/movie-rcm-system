/**
 * Milestone M4: Media Playback & Local Storage Benchmark Script
 *
 * Measures:
 *   1. Startup latency (time to initial frame/chunk, cold vs warm)
 *   2. Seek latency across multiple positions (min, avg, p95, max)
 *   3. Buffer stalls / underruns simulation
 *   4. Concurrent streaming throughput & latency (1, 3, 5 parallel streams)
 *
 * Outputs:
 *   docs/reports/media_benchmark_results.json
 */

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { performance } = require('node:perf_hooks');


const PROJECT_ROOT = path.resolve(__dirname, '..');
const SYNTHETIC_DIR = path.join(PROJECT_ROOT, 'media', 'synthetic');
const FEATURE_FILE = path.join(SYNTHETIC_DIR, 'feature_test.mp4');
const TRAILER_FILE = path.join(SYNTHETIC_DIR, 'trailer_test.mp4');
const RESULTS_FILE = path.join(PROJECT_ROOT, 'docs', 'reports', 'media_benchmark_results.json');

// Helper to compute stats
function computeStats(arr) {
  if (!arr || arr.length === 0) return { min: 0, avg: 0, p95: 0, max: 0, count: 0 };
  const sorted = [...arr].sort((a, b) => a - b);
  const sum = sorted.reduce((acc, v) => acc + v, 0);
  const avg = sum / sorted.length;
  const min = sorted[0];
  const max = sorted[sorted.length - 1];
  const p95Index = Math.min(Math.floor(sorted.length * 0.95), sorted.length - 1);
  const p95 = sorted[p95Index];
  return {
    min: Number(min.toFixed(2)),
    avg: Number(avg.toFixed(2)),
    p95: Number(p95.toFixed(2)),
    max: Number(max.toFixed(2)),
    count: sorted.length,
  };
}

// Start embedded RFC 9110 ranged media server for deterministic benchmark
function createBenchmarkServer(featureBuffer, trailerBuffer) {
  return http.createServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');

    if (url.pathname === '/api/movies/the-last-orbit/media-descriptor') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(
        JSON.stringify({
          movieId: 'the-last-orbit',
          hasFeature: true,
          hasTrailer: true,
          feature: {
            assetId: 'ast-orbit-feat',
            kind: 'feature',
            streamUrl: '/api/media/stream/ast-orbit-feat',
            mimeType: 'video/mp4',
            byteLength: featureBuffer.length,
            durationSeconds: 10.0,
            version: 'v1',
            isPublic: true,
          },
          trailer: {
            assetId: 'ast-orbit-trl',
            kind: 'trailer',
            streamUrl: '/api/media/stream/ast-orbit-trl',
            mimeType: 'video/mp4',
            byteLength: trailerBuffer.length,
            durationSeconds: 3.0,
            version: 'v1',
            isPublic: true,
          },
        })
      );
      return;
    }

    let buffer = null;
    let version = 'v1';
    let assetId = '';
    if (url.pathname.includes('ast-orbit-feat')) {
      buffer = featureBuffer;
      assetId = 'ast-orbit-feat';
    } else if (url.pathname.includes('ast-orbit-trl')) {
      buffer = trailerBuffer;
      assetId = 'ast-orbit-trl';
    }

    if (!buffer) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found');
      return;
    }

    const totalLength = buffer.length;
    res.setHeader('Accept-Ranges', 'bytes');
    res.setHeader('ETag', `"${assetId}-${version}"`);
    res.setHeader('Cache-Control', 'public, max-age=3600');
    res.setHeader('Content-Type', 'video/mp4');

    if (req.method === 'HEAD') {
      res.setHeader('Content-Length', totalLength);
      res.writeHead(200);
      res.end();
      return;
    }

    const rangeHeader = req.headers['range'];
    if (!rangeHeader) {
      res.setHeader('Content-Length', totalLength);
      res.writeHead(200);
      res.end(buffer);
      return;
    }

    const rangeMatch = rangeHeader.match(/bytes=(\d+)-(\d*)/);
    if (!rangeMatch) {
      res.setHeader('Content-Range', `bytes */${totalLength}`);
      res.writeHead(416);
      res.end();
      return;
    }

    const start = parseInt(rangeMatch[1], 10);
    const end = rangeMatch[2] ? parseInt(rangeMatch[2], 10) : totalLength - 1;

    if (start >= totalLength || start > end) {
      res.setHeader('Content-Range', `bytes */${totalLength}`);
      res.writeHead(416);
      res.end();
      return;
    }

    const clampedEnd = Math.min(end, totalLength - 1);
    const chunkLength = clampedEnd - start + 1;

    res.setHeader('Content-Range', `bytes ${start}-${clampedEnd}/${totalLength}`);
    res.setHeader('Content-Length', chunkLength);
    res.writeHead(206);
    res.end(buffer.subarray(start, clampedEnd + 1));
  });
}

function makeRangedRequest(port, path, rangeHeader) {
  return new Promise((resolve, reject) => {
    const startTime = performance.now();
    const headers = {};
    if (rangeHeader) {
      headers['Range'] = rangeHeader;
    }

    const req = http.request(
      {
        hostname: '127.0.0.1',
        port,
        path,
        method: 'GET',
        headers,
      },
      (res) => {
        let bytesReceived = 0;
        res.on('data', (chunk) => {
          bytesReceived += chunk.length;
        });
        res.on('end', () => {
          const duration = performance.now() - startTime;
          resolve({
            statusCode: res.statusCode,
            bytesReceived,
            duration,
            headers: res.headers,
          });
        });
      }
    );

    req.on('error', reject);
    req.end();
  });
}

async function runBenchmark() {
  console.log('=== DIPIE CINEMA - M4 LOCAL MEDIA PLAYBACK BENCHMARK ===');

  if (!fs.existsSync(FEATURE_FILE) || !fs.existsSync(TRAILER_FILE)) {
    throw new Error('Synthetic media files not found in media/synthetic. Generate them first.');
  }

  const featureBuffer = fs.readFileSync(FEATURE_FILE);
  const trailerBuffer = fs.readFileSync(TRAILER_FILE);
  console.log(`- Loaded feature fixture: ${featureBuffer.length} bytes (${(featureBuffer.length / 1024).toFixed(1)} KiB)`);
  console.log(`- Loaded trailer fixture: ${trailerBuffer.length} bytes (${(trailerBuffer.length / 1024).toFixed(1)} KiB)`);

  const server = createBenchmarkServer(featureBuffer, trailerBuffer);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  console.log(`- Benchmark streaming server listening on 127.0.0.1:${port}`);

  try {
    // 1. Startup Latency Benchmark (Cold vs Warm)
    console.log('\n[1/4] Measuring Startup Latency (Initial Chunk 0-65535)...');
    const coldRes = await makeRangedRequest(port, '/api/media/stream/ast-orbit-feat', 'bytes=0-65535');
    assert.equal(coldRes.statusCode, 206);
    const coldStartupMs = Number(coldRes.duration.toFixed(2));

    const warmSamples = [];
    for (let i = 0; i < 20; i++) {
      const warmRes = await makeRangedRequest(port, '/api/media/stream/ast-orbit-feat', 'bytes=0-65535');
      assert.equal(warmRes.statusCode, 206);
      warmSamples.push(warmRes.duration);
    }
    const warmStats = computeStats(warmSamples);
    console.log(`  - Cold startup: ${coldStartupMs} ms`);
    console.log(`  - Warm startup: min=${warmStats.min}ms, avg=${warmStats.avg}ms, p95=${warmStats.p95}ms, max=${warmStats.max}ms`);

    // 2. Seek Latency Benchmark
    console.log('\n[2/4] Measuring Seek Latency Across Key Timeline Positions...');
    const totalBytes = featureBuffer.length;
    const seekPoints = [
      { label: '25% (offset ~34KB)', offset: Math.floor(totalBytes * 0.25) },
      { label: '50% (offset ~69KB)', offset: Math.floor(totalBytes * 0.50) },
      { label: '75% (offset ~103KB)', offset: Math.floor(totalBytes * 0.75) },
      { label: '90% (offset ~124KB)', offset: Math.floor(totalBytes * 0.90) },
    ];

    const seekSamples = [];
    for (const point of seekPoints) {
      for (let i = 0; i < 5; i++) {
        const res = await makeRangedRequest(
          port,
          '/api/media/stream/ast-orbit-feat',
          `bytes=${point.offset}-${Math.min(point.offset + 32768, totalBytes - 1)}`
        );
        assert.equal(res.statusCode, 206);
        seekSamples.push(res.duration);
      }
    }
    const seekStats = computeStats(seekSamples);
    console.log(`  - Seek Latency (${seekSamples.length} samples): min=${seekStats.min}ms, avg=${seekStats.avg}ms, p95=${seekStats.p95}ms, max=${seekStats.max}ms`);

    // 3. Stalls / Buffer Underrun Measurement
    console.log('\n[3/4] Measuring Buffer Stalls & Underruns during Real-Time Delivery Simulation...');
    let stallCount = 0;
    let totalChunkDeliveryMs = 0;
    const chunkSize = 32768; // 32 KiB chunks
    const chunkCount = Math.ceil(totalBytes / chunkSize);
    // 10s video of ~138KB -> average bitrate ~13.8 KB/s -> 32KB represents ~2.3 seconds of playback time
    const simulatedPlaybackTimePerChunkMs = 2300;

    for (let c = 0; c < chunkCount; c++) {
      const start = c * chunkSize;
      const end = Math.min(start + chunkSize - 1, totalBytes - 1);
      const res = await makeRangedRequest(port, '/api/media/stream/ast-orbit-feat', `bytes=${start}-${end}`);
      assert.equal(res.statusCode, 206);
      totalChunkDeliveryMs += res.duration;
      // If delivery time exceeds buffered video duration, stall occurs
      if (res.duration > simulatedPlaybackTimePerChunkMs) {
        stallCount++;
      }
    }
    console.log(`  - Chunks delivered: ${chunkCount}`);
    console.log(`  - Total delivery duration: ${totalChunkDeliveryMs.toFixed(2)} ms for 10.0s video`);
    console.log(`  - Playback buffer underruns / stalls: ${stallCount} (0 expected)`);

    // 4. Concurrent Streams Benchmark (1, 3, 5 Streams)
    console.log('\n[4/4] Measuring Concurrent Stream Performance (1, 3, 5 streams)...');
    const concurrencyLevels = [1, 3, 5];
    const concurrencyResults = {};

    for (const level of concurrencyLevels) {
      const requestsPerClient = 10;
      const clientPromises = [];
      const latencies = [];
      let totalBytesLevel = 0;
      const levelStart = performance.now();

      for (let client = 0; client < level; client++) {
        clientPromises.push(
          (async () => {
            for (let reqIdx = 0; reqIdx < requestsPerClient; reqIdx++) {
              // Alternate between feature and trailer range chunks
              const isFeat = reqIdx % 2 === 0;
              const path = isFeat ? '/api/media/stream/ast-orbit-feat' : '/api/media/stream/ast-orbit-trl';
              const range = isFeat ? 'bytes=1000-33767' : 'bytes=500-16883';
              const res = await makeRangedRequest(port, path, range);
              assert.equal(res.statusCode, 206);
              latencies.push(res.duration);
              totalBytesLevel += res.bytesReceived;
            }
          })()
        );
      }

      await Promise.all(clientPromises);
      const levelDurationSec = (performance.now() - levelStart) / 1000;
      const throughputMBs = Number(((totalBytesLevel / (1024 * 1024)) / levelDurationSec).toFixed(2));
      const stats = computeStats(latencies);

      concurrencyResults[level] = {
        concurrentStreams: level,
        totalRequests: latencies.length,
        totalBytesTransferred: totalBytesLevel,
        totalDurationSeconds: Number(levelDurationSec.toFixed(3)),
        throughputMBPerSec: throughputMBs,
        latencyMs: stats,
      };

      console.log(`  - ${level} stream(s): ${latencies.length} reqs, ${throughputMBs} MB/s, avg latency=${stats.avg}ms, p95=${stats.p95}ms, max=${stats.max}ms`);
    }

    const finalReport = {
      timestamp: new Date().toISOString(),
      environment: {
        nodeVersion: process.version,
        platform: process.platform,
        arch: process.arch,
      },
      fixtures: {
        featureByteLength: totalBytes,
        trailerByteLength: trailerBuffer.length,
      },
      startupLatency: {
        coldStartupMs,
        warmStartupMs: warmStats,
      },
      seekLatencyMs: seekStats,
      playbackStalls: {
        chunksStreamed: chunkCount,
        stallCount,
        deliveryVsRealtimeFactor: Number((totalBytes / totalChunkDeliveryMs * 1000 / (totalBytes / 10)).toFixed(2)),
      },
      concurrencyBenchmark: concurrencyResults,
    };

    fs.writeFileSync(RESULTS_FILE, JSON.stringify(finalReport, null, 2), 'utf8');
    console.log(`\n✔ Benchmark completed successfully! Results written to:`);
    console.log(`  ${RESULTS_FILE}`);

    return finalReport;
  } finally {
    server.close();
  }
}

if (require.main === module) {
  runBenchmark().catch((err) => {
    console.error('Benchmark failed:', err);
    process.exit(1);
  });
}

module.exports = { runBenchmark };
