#!/usr/bin/env node
/**
 * DRIVE-01 Automated Test Suite for Google Drive Media Mapping Tools
 *
 * Verifies mapping manifest schema integrity, conflict detection, path security,
 * mount physical file verification, and idempotency.
 *
 * Test Runner: Node.js built-in test runner (`node --test`)
 *
 * Usage:
 *   node --test scripts/drive_mapping_suite.cjs
 *   node scripts/drive_mapping_suite.cjs
 */

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { execFileSync } = require('node:child_process');

const {
  validateManifest,
  validateAsset,
  isSafeRelativePath,
  normalizeMountPath,
  checkMountFiles,
} = require('./preview_drive_media_mapping.cjs');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const FIXTURE_PATH = path.resolve(PROJECT_ROOT, 'docs/fixtures/drive_media_mapping.example.json');
const SCRIPT_PATH = path.resolve(__dirname, 'preview_drive_media_mapping.cjs');

describe('DRIVE-01: Drive Media Mapping & Validation Suite', () => {

  // Test 1: Manifest mẫu hợp lệ pass 100%
  it('1. Authoritative sample manifest passes 100% validation', () => {
    assert.ok(fs.existsSync(FIXTURE_PATH), `Fixture file must exist at ${FIXTURE_PATH}`);
    const result = validateManifest(FIXTURE_PATH);

    assert.equal(result.isValid, true, 'Default manifest must be completely valid');
    assert.equal(result.schemaErrors.length, 0, 'Must have zero schema errors');
    assert.equal(result.conflicts.length, 0, 'Must have zero conflicts');
    assert.equal(result.unsafePaths.length, 0, 'Must have zero unsafe paths');
    assert.equal(result.totalAssets, 12, 'Must contain 12 sample assets');
    assert.equal(result.validAssetsCount, 12, 'All 12 assets must be valid');

    // Also verify CLI execution directly
    const stdout = execFileSync(process.execPath, [SCRIPT_PATH, '--manifest', FIXTURE_PATH], {
      encoding: 'utf8',
    });
    assert.match(stdout, /VALIDATION PASSED/, 'CLI output must report VALIDATION PASSED');
    assert.match(stdout, /Total Assets:\s+12/, 'CLI must report 12 total assets');
  });

  // Test 2: Phát hiện lỗi schema (thiếu trường bắt buộc, sai kiểu dữ liệu)
  it('2. Detects schema violations (missing required fields, invalid data types)', () => {
    // 2.1 Missing required fields
    const missingAssetId = {
      movieId: 'm-test-2026',
      storageProvider: 'drive',
      relativePath: 'movies/m-test-2026/v1/feature.mp4',
      kind: 'feature',
      mimeType: 'video/mp4',
      byteLength: 1048576,
      version: 'v1',
      isPublic: true,
    };
    const r1 = validateAsset(missingAssetId, 1);
    assert.equal(r1.valid, false, 'Missing assetId must be flagged');
    assert.match(r1.errors[0], /"assetId" is required/);

    // 2.2 Invalid kind
    const invalidKind = {
      assetId: 'ast-test-01',
      movieId: 'm-test-2026',
      storageProvider: 'drive',
      relativePath: 'movies/m-test-2026/v1/feature.mp4',
      kind: 'bonus_clip',
      mimeType: 'video/mp4',
      byteLength: 1048576,
      version: 'v1',
      isPublic: true,
    };
    const r2 = validateAsset(invalidKind, 2);
    assert.equal(r2.valid, false, 'Invalid kind must be flagged');
    assert.match(r2.errors[0], /"kind" must be one of/);

    // 2.3 Invalid byteLength (negative, zero, float, string)
    const badLengths = [-100, 0, 1024.5, '500MB'];
    for (const bl of badLengths) {
      const assetBadLen = { ...invalidKind, kind: 'feature', byteLength: bl };
      const rLen = validateAsset(assetBadLen, 3);
      assert.equal(rLen.valid, false, `byteLength ${bl} must be flagged as invalid`);
      assert.match(rLen.errors[0], /"byteLength" must be a positive integer/);
    }

    // 2.4 Invalid isPublic (string instead of boolean)
    const badPublic = { ...invalidKind, kind: 'feature', byteLength: 1000, isPublic: 'true' };
    const rPub = validateAsset(badPublic, 4);
    assert.equal(rPub.valid, false, 'String isPublic must be flagged');
    assert.match(rPub.errors[0], /"isPublic" is required and must be a boolean/);

    // 2.5 Invalid storageProvider
    const badProvider = { ...invalidKind, kind: 'feature', byteLength: 1000, isPublic: true, storageProvider: 's3' };
    const rProv = validateAsset(badProvider, 5);
    assert.equal(rProv.valid, false, 'storageProvider other than drive must be flagged');
    assert.match(rProv.errors[0], /"storageProvider" must be "drive"/);

    // 2.6 Invalid mimeType
    const badMime = { ...invalidKind, kind: 'feature', byteLength: 1000, isPublic: true, storageProvider: 'drive', mimeType: 'image/png' };
    const rMime = validateAsset(badMime, 6);
    assert.equal(rMime.valid, false, 'Non-media MIME type must be flagged');
    assert.match(rMime.errors[0], /"mimeType" must be a valid media MIME type/);
  });

  // Test 3: Phát hiện xung đột trùng lặp assetId
  it('3. Detects duplicate assetId conflicts across manifest entries', () => {
    const duplicateAssetManifest = {
      schemaVersion: '1.0.0',
      assets: [
        {
          assetId: 'ast-identical-id',
          movieId: 'm-movie-alpha',
          storageProvider: 'drive',
          relativePath: 'movies/m-movie-alpha/v1/feature.mp4',
          kind: 'feature',
          mimeType: 'video/mp4',
          byteLength: 1000000,
          version: 'v1',
          isPublic: true,
        },
        {
          assetId: 'ast-identical-id', // Duplicate assetId!
          movieId: 'm-movie-beta',
          storageProvider: 'drive',
          relativePath: 'movies/m-movie-beta/v1/feature.mp4',
          kind: 'feature',
          mimeType: 'video/mp4',
          byteLength: 2000000,
          version: 'v1',
          isPublic: true,
        },
      ],
    };

    const result = validateManifest(duplicateAssetManifest);
    assert.equal(result.isValid, false, 'Manifest with duplicate assetId must be invalid');
    assert.equal(result.conflicts.length, 1, 'Must register 1 conflict');
    assert.equal(result.conflicts[0].type, 'DUPLICATE_ASSET_ID');
    assert.equal(result.conflicts[0].assetId, 'ast-identical-id');
    assert.match(result.conflicts[0].message, /Duplicate assetId "ast-identical-id"/);
  });

  // Test 4: Phát hiện xung đột trùng lặp (movieId, kind)
  it('4. Detects duplicate (movieId, kind) conflicts (two features for same movie)', () => {
    const duplicateMovieKindManifest = {
      schemaVersion: '1.0.0',
      assets: [
        {
          assetId: 'ast-feature-version-1',
          movieId: 'm-spirited-away-2001',
          storageProvider: 'drive',
          relativePath: 'movies/m-spirited-away-2001/v1/feature.mp4',
          kind: 'feature',
          mimeType: 'video/mp4',
          byteLength: 500000000,
          version: 'v1',
          isPublic: true,
        },
        {
          assetId: 'ast-feature-remastered',
          movieId: 'm-spirited-away-2001', // Same movie!
          storageProvider: 'drive',
          relativePath: 'movies/m-spirited-away-2001/v2/feature.mp4',
          kind: 'feature', // Same kind! Conflicting duplicate feature
          mimeType: 'video/mp4',
          byteLength: 600000000,
          version: 'v2',
          isPublic: true,
        },
      ],
    };

    const result = validateManifest(duplicateMovieKindManifest);
    assert.equal(result.isValid, false, 'Manifest with duplicate (movieId, kind) must be invalid');
    assert.equal(result.conflicts.length, 1, 'Must register 1 conflict');
    assert.equal(result.conflicts[0].type, 'DUPLICATE_MOVIE_KIND');
    assert.equal(result.conflicts[0].movieId, 'm-spirited-away-2001');
    assert.equal(result.conflicts[0].kind, 'feature');
    assert.match(result.conflicts[0].message, /Duplicate movie kind conflict/);
  });

  // Test 5: Chặn đường dẫn path traversal trong mapping
  it('5. Strictly rejects directory traversal and absolute paths in relativePath', () => {
    const dangerousPaths = [
      '../outside/feature.mp4',
      'movies/../../etc/shadow',
      'movies/sub/../../../secrets.mp4',
      '/var/media/feature.mp4',
      '\\server\\share\\feature.mp4',
      'C:\\Windows\\System32\\calc.exe',
      'D:/Class/movie-rcm-system/media/feature.mp4',
      'movies/null\0byte.mp4',
    ];

    for (const dp of dangerousPaths) {
      const check = isSafeRelativePath(dp);
      assert.equal(check.safe, false, `Path "${dp}" must be marked unsafe`);
      assert.ok(check.reason, `Path "${dp}" must include a rejection reason`);

      const testManifest = {
        assets: [
          {
            assetId: 'ast-traversal-test',
            movieId: 'm-test-movie',
            storageProvider: 'drive',
            relativePath: dp,
            kind: 'feature',
            mimeType: 'video/mp4',
            byteLength: 1048576,
            version: 'v1',
            isPublic: true,
          },
        ],
      };
      const res = validateManifest(testManifest);
      assert.equal(res.isValid, false, `Manifest with path "${dp}" must fail validation`);
      assert.ok(
        res.unsafePaths.length > 0 || res.schemaErrors.length > 0,
        `Path "${dp}" must trigger an unsafe path or schema error`
      );
    }
  });

  // Test 6: Chế độ --mount đối chiếu đúng kích thước tệp khi có fixture và báo lỗi khi thiếu
  it('6. Mode --mount correctly matches file sizes on mount and flags missing files', () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'drive-mount-test-'));

    try {
      // Setup file structure inside tempDir:
      // 1. Matched file: 100 bytes
      const file1Dir = path.join(tempDir, 'movies/m-spirited-away-2001/v1');
      fs.mkdirSync(file1Dir, { recursive: true });
      const file1Path = path.join(file1Dir, 'feature.mp4');
      fs.writeFileSync(file1Path, Buffer.alloc(100, 0xaa));

      // 2. Mismatched file: wrote 50 bytes, manifest expects 80 bytes
      const file2Path = path.join(file1Dir, 'trailer.mp4');
      fs.writeFileSync(file2Path, Buffer.alloc(50, 0xbb));

      // 3. Missing file: declared in manifest, but not created on disk
      const manifestWithMount = {
        assets: [
          {
            assetId: 'ast-verified',
            movieId: 'm-spirited-away-2001',
            storageProvider: 'drive',
            relativePath: 'movies/m-spirited-away-2001/v1/feature.mp4',
            kind: 'feature',
            mimeType: 'video/mp4',
            byteLength: 100, // matches 100 bytes!
            version: 'v1',
            isPublic: true,
          },
          {
            assetId: 'ast-mismatched',
            movieId: 'm-spirited-away-2001',
            storageProvider: 'drive',
            relativePath: 'movies/m-spirited-away-2001/v1/trailer.mp4',
            kind: 'trailer',
            mimeType: 'video/mp4',
            byteLength: 80, // on disk is 50 bytes!
            version: 'v1',
            isPublic: true,
          },
          {
            assetId: 'ast-missing',
            movieId: 'm-your-name-2016',
            storageProvider: 'drive',
            relativePath: 'movies/m-your-name-2016/v1/feature.mp4', // does not exist!
            kind: 'feature',
            mimeType: 'video/mp4',
            byteLength: 200,
            version: 'v1',
            isPublic: true,
          },
        ],
      };

      const result = validateManifest(manifestWithMount, { mountPath: tempDir });

      assert.equal(result.isValid, false, 'Mount with mismatches and missing files must not pass');
      assert.equal(result.mountReport.mountChecked, true, 'Mount audit must be recorded');
      assert.equal(result.mountReport.verified.length, 1, 'Exactly 1 file verified');
      assert.equal(result.mountReport.verified[0].assetId, 'ast-verified');
      assert.equal(result.mountReport.verified[0].byteLength, 100);

      assert.equal(result.mountReport.mismatches.length, 1, 'Exactly 1 size mismatch detected');
      assert.equal(result.mountReport.mismatches[0].assetId, 'ast-mismatched');
      assert.equal(result.mountReport.mismatches[0].expectedBytes, 80);
      assert.equal(result.mountReport.mismatches[0].actualBytes, 50);

      assert.equal(result.mountReport.missing.length, 1, 'Exactly 1 missing file detected');
      assert.equal(result.mountReport.missing[0].assetId, 'ast-missing');
      assert.equal(result.mountReport.missing[0].relativePath, 'movies/m-your-name-2016/v1/feature.mp4');

      // Test 6.2: All files exist and match sizes -> passes
      fs.writeFileSync(file2Path, Buffer.alloc(80, 0xbb)); // fix mismatch
      const file3Dir = path.join(tempDir, 'movies/m-your-name-2016/v1');
      fs.mkdirSync(file3Dir, { recursive: true });
      fs.writeFileSync(path.join(file3Dir, 'feature.mp4'), Buffer.alloc(200, 0xcc)); // create missing

      const cleanMountResult = validateManifest(manifestWithMount, { mountPath: tempDir });
      assert.equal(cleanMountResult.isValid, true, 'Clean mount with all files matching must pass');
      assert.equal(cleanMountResult.mountReport.verified.length, 3, 'All 3 files verified');
      assert.equal(cleanMountResult.mountReport.mismatches.length, 0);
      assert.equal(cleanMountResult.mountReport.missing.length, 0);

      // Test 6.3: Non-existent mount folder
      const nonExistentMount = path.join(tempDir, 'does-not-exist');
      const noMountResult = validateManifest(manifestWithMount, { mountPath: nonExistentMount });
      assert.equal(noMountResult.isValid, false, 'Non-existent mount path must fail');
      assert.ok(noMountResult.mountReport.mountError, 'Must report mount error');
    } finally {
      // Safe cleanup of temp directory
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  // Test 7: Tính lũy đẳng (idempotent): chạy nhiều lần cho cùng kết quả (so sánh sâu deep equality)
  it('7. Validation is purely idempotent across consecutive executions (deep equality)', () => {
    // Run 3 times on default fixture
    const run1 = validateManifest(FIXTURE_PATH);
    const run2 = validateManifest(FIXTURE_PATH);
    const run3 = validateManifest(FIXTURE_PATH);

    assert.deepStrictEqual(run1, run2, 'Run 1 and Run 2 results must be deeply identical');
    assert.deepStrictEqual(run2, run3, 'Run 2 and Run 3 results must be deeply identical');

    // Run 3 times on an invalid manifest
    const invalidManifest = {
      assets: [
        {
          assetId: 'ast-idem-test',
          movieId: 'm-movie-idem',
          storageProvider: 'drive',
          relativePath: 'movies/m-movie-idem/v1/feature.mp4',
          kind: 'feature',
          mimeType: 'video/mp4',
          byteLength: 5000,
          version: 'v1',
          isPublic: true,
        },
        {
          assetId: 'ast-idem-test', // duplicate
          movieId: 'm-movie-idem', // duplicate
          storageProvider: 'drive',
          relativePath: 'movies/m-movie-idem/v1/feature.mp4',
          kind: 'feature',
          mimeType: 'video/mp4',
          byteLength: 5000,
          version: 'v1',
          isPublic: true,
        },
      ],
    };

    const invRun1 = validateManifest(invalidManifest);
    const invRun2 = validateManifest(invalidManifest);
    const invRun3 = validateManifest(invalidManifest);

    assert.deepStrictEqual(invRun1, invRun2, 'Invalid run 1 and run 2 must be deeply identical');
    assert.deepStrictEqual(invRun2, invRun3, 'Invalid run 2 and run 3 must be deeply identical');
    assert.equal(invRun1.isValid, false);
    assert.equal(invRun1.conflicts.length, 2); // 1 DUPLICATE_ASSET_ID + 1 DUPLICATE_MOVIE_KIND

    // Also verify idempotency with mount verification
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'drive-idem-mount-'));
    try {
      const subDir = path.join(tempDir, 'movies/m-test/v1');
      fs.mkdirSync(subDir, { recursive: true });
      fs.writeFileSync(path.join(subDir, 'test.mp4'), Buffer.alloc(128, 0x11));

      const mountManifest = {
        assets: [
          {
            assetId: 'ast-idem-mount',
            movieId: 'm-test',
            storageProvider: 'drive',
            relativePath: 'movies/m-test/v1/test.mp4',
            kind: 'feature',
            mimeType: 'video/mp4',
            byteLength: 128,
            version: 'v1',
            isPublic: true,
          },
        ],
      };

      const mRun1 = validateManifest(mountManifest, { mountPath: tempDir });
      const mRun2 = validateManifest(mountManifest, { mountPath: tempDir });
      assert.deepStrictEqual(mRun1, mRun2, 'Mount validation runs must be deeply identical');
      assert.equal(mRun1.isValid, true);
      assert.equal(mRun1.mountReport.verified.length, 1);
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  // Test 8: Chặn triệt để NTFS Alternate Data Streams (ADS) và namespace thiết bị
  it('8. Strictly rejects NTFS Alternate Data Streams (ADS) and device namespace paths', () => {
    const adsPaths = [
      'clip.mp4:secret',
      'movies/m-test-2026/v1/feature.mp4:hidden_stream',
      'video.mp4:$DATA',
      ':leading_colon.mp4',
      'subfolder/:stream',
      'C:relative_drive.mp4',
      '\\\\.\\pipe\\test',
      '\\\\?\\C:\\Windows\\calc.exe',
    ];

    for (const ap of adsPaths) {
      const check = isSafeRelativePath(ap);
      assert.equal(check.safe, false, `ADS / device path "${ap}" must be marked unsafe`);
      assert.ok(check.reason, `ADS / device path "${ap}" must include rejection reason`);

      const testManifest = {
        assets: [
          {
            assetId: 'ast-ads-test',
            movieId: 'm-test-ads',
            storageProvider: 'drive',
            relativePath: ap,
            kind: 'feature',
            mimeType: 'video/mp4',
            byteLength: 1048576,
            version: 'v1',
            isPublic: true,
          },
        ],
      };

      const res = validateManifest(testManifest);
      assert.equal(res.isValid, false, `Manifest with ADS path "${ap}" must fail validation`);
      assert.ok(
        res.unsafePaths.length > 0 || res.schemaErrors.length > 0,
        `Manifest with ADS path "${ap}" must record unsafePaths or schemaErrors`
      );
    }
  });

  // Test 9: Chặn Windows junction / symlink trỏ ra ngoài mount root (Finding D6)
  it('9. Strictly rejects Windows junction and symlink boundary escapes outside mount root (Finding D6)', () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'regression-drive-mapping-junc-'));
    try {
      const mountRoot = path.join(tempDir, 'mount');
      const outsideDir = path.join(tempDir, 'outside');
      fs.mkdirSync(mountRoot, { recursive: true });
      fs.mkdirSync(outsideDir, { recursive: true });

      const outsideFile = path.join(outsideDir, 'clip.mp4');
      fs.writeFileSync(outsideFile, Buffer.alloc(123, 0x42));

      // Create real Windows junction pointing outside
      const junctionPath = path.join(mountRoot, 'escape');
      try {
        fs.symlinkSync(outsideDir, junctionPath, 'junction');
      } catch (err) {
        fs.symlinkSync(outsideDir, junctionPath, 'dir');
      }

      const escapeManifest = {
        assets: [
          {
            assetId: 'ast-junction-escape',
            movieId: 'm-review-test',
            storageProvider: 'drive',
            relativePath: 'escape/clip.mp4',
            kind: 'feature',
            mimeType: 'video/mp4',
            byteLength: 123,
            version: 'v1',
            isPublic: true,
          },
        ],
      };

      const result = validateManifest(escapeManifest, { mountPath: mountRoot });
      assert.equal(result.isValid, false, 'Manifest accessing file through junction escape must be invalid');
      assert.equal(result.mountReport.mountChecked, true);
      assert.equal(result.mountReport.verified.length, 0, 'Target escaping mount root must NEVER be verified');
      assert.equal(result.mountReport.mismatches.length, 1, 'Must record exactly 1 mismatch for junction escape');
      assert.match(
        result.mountReport.mismatches[0].error,
        /escapes mount root boundary via junction or symlink/
      );

      // Direct checkMountFiles verification
      const directCheck = checkMountFiles(escapeManifest.assets, mountRoot);
      assert.equal(directCheck.verified.length, 0, 'direct checkMountFiles must not verify outside file');
      assert.equal(directCheck.mismatches.length, 1, 'direct checkMountFiles must flag mismatch');
      assert.match(
        directCheck.mismatches[0].error,
        /escapes mount root boundary via junction or symlink/
      );
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

});
