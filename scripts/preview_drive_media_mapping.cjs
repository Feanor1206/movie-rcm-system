#!/usr/bin/env node
/**
 * DRIVE-01 Preview & Validation Tool for Google Drive Media Mapping Manifests
 *
 * Strictly validate-only CLI tool that inspects, validates, and simulates
 * media mapping manifests before database ingestion.
 *
 * POLICIES & BOUNDARIES:
 *   - NEVER connects to, writes to, or modifies any live database or files.
 *   - Enforces strict JSON schema & type validation.
 *   - Enforces uniqueness of `assetId` and `(movieId, kind)` pairs.
 *   - Enforces strict path security: forbids absolute paths, Windows drives, UNC paths, and traversal (..).
 *   - When `--mount <path>` is provided, verifies physical file existence and exact byte length matching.
 *
 * Usage:
 *   node scripts/preview_drive_media_mapping.cjs
 *   node scripts/preview_drive_media_mapping.cjs --manifest docs/fixtures/drive_media_mapping.example.json
 *   node scripts/preview_drive_media_mapping.cjs --manifest <path> --mount M:\DippieMedia
 *   node scripts/preview_drive_media_mapping.cjs --json
 */

const fs = require('node:fs');
const path = require('node:path');

const DEFAULT_MANIFEST_PATH = path.resolve(__dirname, '../docs/fixtures/drive_media_mapping.example.json');
const ALLOWED_KINDS = new Set(['feature', 'trailer']);
const ALLOWED_PROVIDERS = new Set(['drive']);
const SAFE_ID_REGEX = /^[a-zA-Z0-9_\-\.]+$/;

/**
 * Checks whether a relative path is secure and does not attempt path traversal or escaping.
 *
 * @param {string} relPath
 * @returns {{ safe: boolean, reason?: string }}
 */
function isSafeRelativePath(relPath) {
  if (typeof relPath !== 'string' || relPath.trim() === '') {
    return { safe: false, reason: 'relativePath must be a non-empty string' };
  }
  if (relPath.includes('\0')) {
    return { safe: false, reason: 'relativePath contains forbidden null byte' };
  }
  // Forbid colon (prevents NTFS Alternate Data Streams, e.g. clip.mp4:secret, Windows drive prefixes, device paths)
  if (relPath.includes(':')) {
    return { safe: false, reason: 'relativePath contains forbidden colon (device path or NTFS Alternate Data Stream)' };
  }
  // Forbid Windows drive letter prefix (e.g. C:, D:)
  if (/^[a-zA-Z]:/.test(relPath)) {
    return { safe: false, reason: 'Absolute Windows drive path is forbidden' };
  }
  // Forbid Unix root, Windows UNC path, device namespaces
  if (relPath.startsWith('/') || relPath.startsWith('\\')) {
    return { safe: false, reason: 'Absolute or UNC path is forbidden' };
  }
  if (/^[/\\]{2}/.test(relPath) || /^[/\\]{2}[.?][/\\]/.test(relPath)) {
    return { safe: false, reason: 'Device namespace or UNC path is forbidden' };
  }
  // Check directory traversal segments
  const segments = relPath.split(/[/\\]/);
  for (const seg of segments) {
    if (seg === '..') {
      return { safe: false, reason: 'Path traversal (..) segment is forbidden' };
    }
  }
  // Check normalized representation
  const normalized = path.normalize(relPath).replace(/\\/g, '/');
  if (normalized.startsWith('../') || normalized === '..' || normalized.includes('/../')) {
    return { safe: false, reason: 'Path traversal escaping mount root is forbidden' };
  }
  if (path.isAbsolute(normalized)) {
    return { safe: false, reason: 'Normalized path resolves to an absolute path' };
  }
  return { safe: true };
}

/**
 * Validates a single media asset record against schema and safety rules.
 *
 * @param {any} asset
 * @param {number} index
 * @returns {{ valid: boolean, errors: string[] }}
 */
function validateAsset(asset, index) {
  const errors = [];
  const prefix = `[Asset #${index}]`;

  if (!asset || typeof asset !== 'object' || Array.isArray(asset)) {
    return { valid: false, errors: [`${prefix} Record must be a JSON object`] };
  }

  // 1. assetId
  if (typeof asset.assetId !== 'string' || asset.assetId.trim() === '') {
    errors.push(`${prefix} "assetId" is required and must be a non-empty string`);
  } else if (!SAFE_ID_REGEX.test(asset.assetId)) {
    errors.push(`${prefix} "assetId" contains invalid characters (allowed: alphanumeric, _, -, .)`);
  }

  // 2. movieId
  if (typeof asset.movieId !== 'string' || asset.movieId.trim() === '') {
    errors.push(`${prefix} "movieId" is required and must be a non-empty string`);
  } else if (!SAFE_ID_REGEX.test(asset.movieId)) {
    errors.push(`${prefix} "movieId" contains invalid characters (allowed: alphanumeric, _, -, .)`);
  }

  // 3. storageProvider
  if (typeof asset.storageProvider !== 'string' || asset.storageProvider.trim() === '') {
    errors.push(`${prefix} "storageProvider" is required`);
  } else if (!ALLOWED_PROVIDERS.has(asset.storageProvider)) {
    errors.push(`${prefix} "storageProvider" must be "drive" (got: "${asset.storageProvider}")`);
  }

  // 4. relativePath & path safety
  if (typeof asset.relativePath !== 'string' || asset.relativePath.trim() === '') {
    errors.push(`${prefix} "relativePath" is required and must be a non-empty string`);
  } else {
    const safety = isSafeRelativePath(asset.relativePath);
    if (!safety.safe) {
      errors.push(`${prefix} Unsafe relativePath: ${safety.reason} ("${asset.relativePath}")`);
    }
  }

  // 5. kind
  if (typeof asset.kind !== 'string' || asset.kind.trim() === '') {
    errors.push(`${prefix} "kind" is required`);
  } else if (!ALLOWED_KINDS.has(asset.kind)) {
    errors.push(`${prefix} "kind" must be one of [${Array.from(ALLOWED_KINDS).join(', ')}] (got: "${asset.kind}")`);
  }

  // 6. mimeType
  if (typeof asset.mimeType !== 'string' || asset.mimeType.trim() === '') {
    errors.push(`${prefix} "mimeType" is required and must be a non-empty string`);
  } else if (!asset.mimeType.startsWith('video/') && !asset.mimeType.startsWith('audio/')) {
    errors.push(`${prefix} "mimeType" must be a valid media MIME type starting with video/ or audio/ (got: "${asset.mimeType}")`);
  }

  // 7. byteLength
  if (typeof asset.byteLength !== 'number' || !Number.isInteger(asset.byteLength) || asset.byteLength <= 0) {
    errors.push(`${prefix} "byteLength" must be a positive integer greater than 0 (got: ${asset.byteLength})`);
  }

  // 8. version
  if (typeof asset.version !== 'string' || asset.version.trim() === '') {
    errors.push(`${prefix} "version" is required and must be a non-empty string`);
  }

  // 9. isPublic
  if (typeof asset.isPublic !== 'boolean') {
    errors.push(`${prefix} "isPublic" is required and must be a boolean (got: ${typeof asset.isPublic})`);
  }

  // 10. durationSeconds (optional)
  if (asset.durationSeconds !== undefined && asset.durationSeconds !== null) {
    if (typeof asset.durationSeconds !== 'number' || Number.isNaN(asset.durationSeconds) || asset.durationSeconds < 0) {
      errors.push(`${prefix} "durationSeconds" if provided must be a non-negative number`);
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

/**
 * Normalizes a mount directory path across Windows and POSIX systems.
 *
 * @param {string} mountPath
 * @returns {string}
 */
function normalizeMountPath(mountPath) {
  let resolved = path.resolve(mountPath);
  if (/^[a-zA-Z]:$/.test(mountPath)) {
    resolved = path.resolve(mountPath + '\\');
  }
  return resolved;
}

/**
 * Audits assets against physical files on a mounted directory.
 *
 * @param {any[]} assets
 * @param {string} mountPath
 * @returns {{ mountChecked: boolean, mountPath: string, verified: any[], mismatches: any[], missing: any[], mountError?: string }}
 */
function checkMountFiles(assets, mountPath) {
  if (!mountPath) {
    return { mountChecked: false, mountPath: '', verified: [], mismatches: [], missing: [] };
  }

  const normMount = normalizeMountPath(mountPath);
  if (!fs.existsSync(normMount)) {
    return {
      mountChecked: true,
      mountPath: normMount,
      verified: [],
      mismatches: [],
      missing: [],
      mountError: `Mount root path does not exist or is inaccessible: "${normMount}"`,
    };
  }

  let realRoot;
  try {
    realRoot = fs.realpathSync(normMount);
  } catch (rootErr) {
    return {
      mountChecked: true,
      mountPath: normMount,
      verified: [],
      mismatches: [],
      missing: [],
      mountError: `Cannot resolve canonical mount root path "${normMount}": ${rootErr.message}`,
    };
  }

  const normalizedRealRoot = path.normalize(realRoot);
  const rootPrefix = normalizedRealRoot.endsWith(path.sep) ? normalizedRealRoot : normalizedRealRoot + path.sep;

  const verified = [];
  const mismatches = [];
  const missing = [];

  for (const asset of assets) {
    if (!asset || typeof asset.relativePath !== 'string') continue;
    const safety = isSafeRelativePath(asset.relativePath);
    if (!safety.safe) continue;

    const fullPath = path.resolve(normMount, asset.relativePath);
    // Security check 1: Lexical containment
    const relToMount = path.relative(normMount, fullPath);
    if (relToMount.startsWith('..') || path.isAbsolute(relToMount)) {
      mismatches.push({
        assetId: asset.assetId,
        relativePath: asset.relativePath,
        error: 'Path escapes mount root boundary',
      });
      continue;
    }

    if (!fs.existsSync(fullPath)) {
      missing.push({
        assetId: asset.assetId,
        movieId: asset.movieId,
        relativePath: asset.relativePath,
        resolvedPath: fullPath,
      });
    } else {
      try {
        // Security check 2: Canonical / real path containment (junction / symlink traversal)
        let realTarget;
        try {
          realTarget = fs.realpathSync(fullPath);
        } catch (realErr) {
          mismatches.push({
            assetId: asset.assetId,
            relativePath: asset.relativePath,
            resolvedPath: fullPath,
            error: `Cannot resolve canonical target path: ${realErr.message}`,
          });
          continue;
        }

        const normalizedRealTarget = path.normalize(realTarget);
        const relCanonical = path.relative(normalizedRealRoot, normalizedRealTarget);

        const isContained = process.platform === 'win32'
          ? (normalizedRealTarget.toLowerCase().startsWith(rootPrefix.toLowerCase()) || normalizedRealTarget.toLowerCase() === normalizedRealRoot.toLowerCase())
          : (normalizedRealTarget.startsWith(rootPrefix) || normalizedRealTarget === normalizedRealRoot);

        if (!isContained || relCanonical.startsWith('..') || path.isAbsolute(relCanonical)) {
          mismatches.push({
            assetId: asset.assetId,
            relativePath: asset.relativePath,
            resolvedPath: fullPath,
            realTarget,
            error: 'Target escapes mount root boundary via junction or symlink',
          });
          continue;
        }

        const stat = fs.statSync(fullPath);
        if (!stat.isFile()) {
          mismatches.push({
            assetId: asset.assetId,
            relativePath: asset.relativePath,
            resolvedPath: fullPath,
            error: 'Target exists but is not a regular file (directory or special node)',
          });
        } else if (stat.size !== asset.byteLength) {
          mismatches.push({
            assetId: asset.assetId,
            relativePath: asset.relativePath,
            resolvedPath: fullPath,
            expectedBytes: asset.byteLength,
            actualBytes: stat.size,
            diffBytes: stat.size - asset.byteLength,
          });
        } else {
          verified.push({
            assetId: asset.assetId,
            movieId: asset.movieId,
            relativePath: asset.relativePath,
            resolvedPath: fullPath,
            byteLength: stat.size,
          });
        }
      } catch (err) {
        mismatches.push({
          assetId: asset.assetId,
          relativePath: asset.relativePath,
          resolvedPath: fullPath,
          error: `Error inspecting file: ${err.message}`,
        });
      }
    }
  }

  return {
    mountChecked: true,
    mountPath: normMount,
    verified,
    mismatches,
    missing,
  };
}

/**
 * Comprehensive manifest validation engine.
 *
 * @param {string | object} manifestInput - Path to manifest file or raw manifest object.
 * @param {{ mountPath?: string }} options
 * @returns {object} Validation result object
 */
function validateManifest(manifestInput, options = {}) {
  let manifestObj;
  let sourcePath = 'in-memory-object';

  if (typeof manifestInput === 'string') {
    sourcePath = path.resolve(manifestInput);
    if (!fs.existsSync(sourcePath)) {
      return {
        isValid: false,
        sourcePath,
        totalAssets: 0,
        validAssetsCount: 0,
        schemaErrors: [`Manifest file does not exist: "${sourcePath}"`],
        conflicts: [],
        unsafePaths: [],
        mountReport: { mountChecked: false },
      };
    }
    try {
      const raw = fs.readFileSync(sourcePath, 'utf8');
      manifestObj = JSON.parse(raw);
    } catch (parseErr) {
      return {
        isValid: false,
        sourcePath,
        totalAssets: 0,
        validAssetsCount: 0,
        schemaErrors: [`JSON Syntax Error in manifest: ${parseErr.message}`],
        conflicts: [],
        unsafePaths: [],
        mountReport: { mountChecked: false },
      };
    }
  } else if (manifestInput && typeof manifestInput === 'object') {
    manifestObj = manifestInput;
  } else {
    return {
      isValid: false,
      sourcePath,
      totalAssets: 0,
      validAssetsCount: 0,
      schemaErrors: ['Invalid input: manifest must be a file path or a parsed object'],
      conflicts: [],
      unsafePaths: [],
      mountReport: { mountChecked: false },
    };
  }

  // Extract assets array
  let assets = [];
  if (Array.isArray(manifestObj)) {
    assets = manifestObj;
  } else if (manifestObj && Array.isArray(manifestObj.assets)) {
    assets = manifestObj.assets;
  } else if (manifestObj && Array.isArray(manifestObj.records)) {
    assets = manifestObj.records;
  } else {
    return {
      isValid: false,
      sourcePath,
      totalAssets: 0,
      validAssetsCount: 0,
      schemaErrors: ['Manifest structure invalid: expected an array or an object with "assets" array'],
      conflicts: [],
      unsafePaths: [],
      mountReport: { mountChecked: false },
    };
  }

  const schemaErrors = [];
  const conflicts = [];
  const unsafePaths = [];
  const validAssets = [];

  const seenAssetIds = new Map();
  const seenMovieKinds = new Map();

  for (let i = 0; i < assets.length; i++) {
    const asset = assets[i];
    const validation = validateAsset(asset, i + 1);

    if (!validation.valid) {
      schemaErrors.push(...validation.errors);
      continue;
    }

    let hasIssue = false;

    // Check duplicate assetId
    if (seenAssetIds.has(asset.assetId)) {
      const prevIdx = seenAssetIds.get(asset.assetId);
      conflicts.push({
        type: 'DUPLICATE_ASSET_ID',
        assetId: asset.assetId,
        message: `Duplicate assetId "${asset.assetId}" found at index ${i + 1} (previously declared at index ${prevIdx})`,
      });
      hasIssue = true;
    } else {
      seenAssetIds.set(asset.assetId, i + 1);
    }

    // Check duplicate (movieId, kind) pair
    const movieKindKey = `${asset.movieId}::${asset.kind}`;
    if (seenMovieKinds.has(movieKindKey)) {
      const prevIdx = seenMovieKinds.get(movieKindKey);
      conflicts.push({
        type: 'DUPLICATE_MOVIE_KIND',
        movieId: asset.movieId,
        kind: asset.kind,
        message: `Duplicate movie kind conflict: movieId "${asset.movieId}" already has kind "${asset.kind}" at index ${prevIdx}`,
      });
      hasIssue = true;
    } else {
      seenMovieKinds.set(movieKindKey, i + 1);
    }

    // Check path security
    const safety = isSafeRelativePath(asset.relativePath);
    if (!safety.safe) {
      unsafePaths.push({
        assetId: asset.assetId,
        relativePath: asset.relativePath,
        reason: safety.reason,
      });
      hasIssue = true;
    }

    if (!hasIssue) {
      validAssets.push(asset);
    }
  }

  // Mount audit if requested
  const mountReport = checkMountFiles(validAssets, options.mountPath);

  const hasMountError = Boolean(
    mountReport.mountError ||
    (mountReport.mountChecked && (mountReport.missing.length > 0 || mountReport.mismatches.length > 0))
  );

  const isValid =
    schemaErrors.length === 0 &&
    conflicts.length === 0 &&
    unsafePaths.length === 0 &&
    !hasMountError &&
    assets.length > 0;

  return {
    isValid,
    sourcePath,
    totalAssets: assets.length,
    validAssetsCount: validAssets.length,
    schemaErrors,
    conflicts,
    unsafePaths,
    mountReport,
    validAssets,
  };
}

/**
 * CLI Runner with user-friendly formatting and exit code handling.
 */
function runCli() {
  const args = process.argv.slice(2);
  let manifestPath = DEFAULT_MANIFEST_PATH;
  let mountPath = null;
  let outputJson = false;
  let verbose = false;

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--manifest' && i + 1 < args.length) {
      manifestPath = args[++i];
    } else if (arg === '--mount' && i + 1 < args.length) {
      mountPath = args[++i];
    } else if (arg === '--json') {
      outputJson = true;
    } else if (arg === '--verbose' || arg === '-v') {
      verbose = true;
    } else if (arg === '--help' || arg === '-h') {
      console.log(`
DRIVE MEDIA MAPPING PREVIEW & VALIDATION TOOL (DRIVE-01)
Usage:
  node scripts/preview_drive_media_mapping.cjs [options]

Options:
  --manifest <path>  Path to mapping manifest JSON (default: docs/fixtures/drive_media_mapping.example.json)
  --mount <path>     Optional mounted directory to verify physical files against manifest (e.g. M:\\DippieMedia)
  --json             Output results as raw JSON
  --verbose, -v      Show verbose asset mapping list
  --help, -h         Show this help message

Policies:
  - Validate-only mode: NEVER writes to or alters any database or storage.
  - Strict path safety: prevents path traversal and absolute paths.
  - Uniqueness: validates assetId and (movieId, kind) tuple uniqueness.
`);
      process.exit(0);
    }
  }

  const result = validateManifest(manifestPath, { mountPath });

  if (outputJson) {
    console.log(JSON.stringify(result, null, 2));
    process.exit(result.isValid ? 0 : 1);
  }

  console.log('================================================================');
  console.log('   DRIVE MEDIA MAPPING PREVIEW & VALIDATION TOOL (DRIVE-01)    ');
  console.log('================================================================');
  console.log(`- Manifest Source: ${result.sourcePath}`);
  console.log(`- Mount Audit:     ${mountPath ? normalizeMountPath(mountPath) : 'Disabled (use --mount <path> to verify files)'}`);
  console.log(`- Total Assets:    ${result.totalAssets}`);
  console.log(`- Valid Assets:    ${result.validAssetsCount}`);
  console.log('----------------------------------------------------------------');

  if (verbose && result.validAssets && result.validAssets.length > 0) {
    console.log('\n[VALID ASSETS PREVIEW]');
    for (const a of result.validAssets) {
      const mb = (a.byteLength / (1024 * 1024)).toFixed(1);
      console.log(`  [OK] ${a.assetId.padEnd(32)} | ${a.movieId.padEnd(24)} | ${a.kind.padEnd(8)} | ${mb} MB | ${a.relativePath}`);
    }
  }

  if (result.schemaErrors.length > 0) {
    console.log('\n[SCHEMA VALIDATION ERRORS]');
    for (const err of result.schemaErrors) {
      console.log(`  ✖ ${err}`);
    }
  }

  if (result.conflicts.length > 0) {
    console.log('\n[CONFLICTS DETECTED]');
    for (const conf of result.conflicts) {
      console.log(`  ! [${conf.type}] ${conf.message}`);
    }
  }

  if (result.unsafePaths.length > 0) {
    console.log('\n[PATH SECURITY VIOLATIONS - REJECTED]');
    for (const p of result.unsafePaths) {
      console.log(`  ⛔ Asset "${p.assetId}": ${p.reason} (path: "${p.relativePath}")`);
    }
  }

  if (result.mountReport.mountChecked) {
    console.log('\n[MOUNT AUDIT REPORT]');
    if (result.mountReport.mountError) {
      console.log(`  ✖ Mount Error: ${result.mountReport.mountError}`);
    } else {
      console.log(`  ✔ Verified on Mount:     ${result.mountReport.verified.length} files`);
      console.log(`  ! Size Mismatches:       ${result.mountReport.mismatches.length} files`);
      console.log(`  ✖ Missing from Mount:    ${result.mountReport.missing.length} files`);

      if (result.mountReport.mismatches.length > 0) {
        console.log('\n  [SIZE MISMATCH DETAILS]');
        for (const m of result.mountReport.mismatches) {
          console.log(`    - ${m.assetId}: expected ${m.expectedBytes} bytes, found ${m.actualBytes} bytes on mount (${m.relativePath})`);
        }
      }

      if (result.mountReport.missing.length > 0) {
        console.log('\n  [MISSING FILE DETAILS]');
        for (const miss of result.mountReport.missing) {
          console.log(`    - ${miss.assetId}: "${miss.relativePath}" -> not found at "${miss.resolvedPath}"`);
        }
      }
    }
  }

  console.log('----------------------------------------------------------------');
  if (result.isValid) {
    console.log('Status: VALIDATION PASSED (100% compliant, 0 live changes written)');
    console.log('================================================================\n');
    process.exit(0);
  } else {
    console.log('Status: VALIDATION FAILED (Fix the above issues before applying mapping)');
    console.log('================================================================\n');
    process.exit(1);
  }
}

if (require.main === module) {
  runCli();
}

module.exports = {
  isSafeRelativePath,
  validateAsset,
  normalizeMountPath,
  checkMountFiles,
  validateManifest,
};
