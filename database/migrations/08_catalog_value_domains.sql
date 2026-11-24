DROP TEMPORARY TABLE IF EXISTS dippie_migration_08_dates;
DROP TEMPORARY TABLE IF EXISTS dippie_migration_08_guard;
CREATE TEMPORARY TABLE dippie_migration_08_dates (
    table_name VARCHAR(64) NOT NULL,
    row_id VARCHAR(100) NOT NULL,
    source_value VARCHAR(100) NOT NULL,
    canonical_value VARCHAR(26),
    PRIMARY KEY (table_name, row_id)
);

INSERT INTO dippie_migration_08_dates (table_name, row_id, source_value)
SELECT 'catalog_seasons', id, release_date FROM catalog_seasons
WHERE release_date IS NOT NULL AND EXISTS (
    SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE()
    AND table_name = 'catalog_seasons' AND column_name = 'release_date' AND data_type NOT IN ('date','datetime')
)
UNION ALL
SELECT 'catalog_episodes', id, release_date FROM catalog_episodes
WHERE release_date IS NOT NULL AND EXISTS (
    SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE()
    AND table_name = 'catalog_episodes' AND column_name = 'release_date' AND data_type NOT IN ('date','datetime')
)
UNION ALL
SELECT 'catalog_sources', id, retrieved_at FROM catalog_sources
WHERE retrieved_at IS NOT NULL AND EXISTS (
    SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE()
    AND table_name = 'catalog_sources' AND column_name = 'retrieved_at' AND data_type NOT IN ('date','datetime')
);

UPDATE dippie_migration_08_dates
SET canonical_value = CASE
    WHEN REGEXP_LIKE(source_value, '^[1-9][0-9]{3}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$', 'c') THEN
        CASE WHEN CAST(SUBSTRING(source_value, 9, 2) AS UNSIGNED) <= DAY(LAST_DAY(CONCAT(LEFT(source_value, 7), '-01')))
             THEN source_value END
    END
WHERE table_name IN ('catalog_seasons', 'catalog_episodes');

UPDATE dippie_migration_08_dates
SET canonical_value = CASE
    WHEN REGEXP_LIKE(source_value, '^[1-9][0-9]{3}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])[T ]([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]([.][0-9]{1,6})?(Z|[+-]([01][0-9]|2[0-3]):[0-5][0-9])?$', 'c') THEN
        CASE WHEN CAST(SUBSTRING(source_value, 9, 2) AS UNSIGNED) <= DAY(LAST_DAY(CONCAT(LEFT(source_value, 7), '-01')))
             THEN CONCAT(LEFT(source_value, 10), ' ', REGEXP_REPLACE(SUBSTRING(source_value, 12), 'Z$|[+-]([01][0-9]|2[0-3]):[0-5][0-9]$', '')) END
    END
WHERE table_name = 'catalog_sources';

UPDATE dippie_migration_08_dates
SET canonical_value = CASE
    WHEN LEFT(canonical_value, 10) = '1000-01-01'
         AND TIME_TO_SEC(SUBSTRING(canonical_value, 12)) < 60 * (
             60 * CAST(SUBSTRING(source_value, -5, 2) AS SIGNED) + CAST(RIGHT(source_value, 2) AS SIGNED)
         ) AND SUBSTRING(source_value, -6, 1) = '+' THEN NULL
    WHEN LEFT(canonical_value, 10) = '9999-12-31'
         AND TIME_TO_SEC(SUBSTRING(canonical_value, 12)) + 60 * (
             60 * CAST(SUBSTRING(source_value, -5, 2) AS SIGNED) + CAST(RIGHT(source_value, 2) AS SIGNED)
         ) >= 86400 AND SUBSTRING(source_value, -6, 1) = '-' THEN NULL
    ELSE DATE_FORMAT(TIMESTAMPADD(MINUTE,
        IF(SUBSTRING(source_value, -6, 1) = '+', -1, 1) *
        (60 * CAST(SUBSTRING(source_value, -5, 2) AS SIGNED) + CAST(RIGHT(source_value, 2) AS SIGNED)),
        CAST(canonical_value AS DATETIME(6))), '%Y-%m-%d %H:%i:%s.%f')
    END
WHERE table_name = 'catalog_sources' AND canonical_value IS NOT NULL
  AND REGEXP_LIKE(source_value, '[+-]([01][0-9]|2[0-3]):[0-5][0-9]$', 'c');

SELECT table_name, row_id,
       IF(table_name = 'catalog_sources', 'retrieved_at', 'release_date') AS column_name,
       source_value AS invalid_value
FROM dippie_migration_08_dates
WHERE canonical_value IS NULL
ORDER BY table_name, row_id;

CREATE TEMPORARY TABLE dippie_migration_08_guard (invalid_date_count_must_be_zero INT PRIMARY KEY);
INSERT INTO dippie_migration_08_guard VALUES (1);
INSERT INTO dippie_migration_08_guard
SELECT 1 FROM dippie_migration_08_dates WHERE canonical_value IS NULL LIMIT 1;
DROP TEMPORARY TABLE dippie_migration_08_guard;

UPDATE catalog_seasons AS target
JOIN dippie_migration_08_dates AS converted ON converted.row_id = target.id AND converted.table_name = 'catalog_seasons'
SET target.release_date = converted.canonical_value, target.updated_at = target.updated_at;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'catalog_seasons' AND column_name = 'release_date' AND data_type <> 'date'),
    'ALTER TABLE catalog_seasons MODIFY COLUMN release_date DATE NULL',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

UPDATE catalog_episodes AS target
JOIN dippie_migration_08_dates AS converted ON converted.row_id = target.id AND converted.table_name = 'catalog_episodes'
SET target.release_date = converted.canonical_value, target.updated_at = target.updated_at;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'catalog_episodes' AND column_name = 'release_date' AND data_type <> 'date'),
    'ALTER TABLE catalog_episodes MODIFY COLUMN release_date DATE NULL',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

UPDATE catalog_sources AS target
JOIN dippie_migration_08_dates AS converted ON converted.row_id = target.id AND converted.table_name = 'catalog_sources'
SET target.retrieved_at = converted.canonical_value, target.updated_at = target.updated_at;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'catalog_sources' AND column_name = 'retrieved_at' AND (data_type <> 'datetime' OR datetime_precision <> 6)),
    'ALTER TABLE catalog_sources MODIFY COLUMN retrieved_at DATETIME(6) NULL',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

DROP TEMPORARY TABLE dippie_migration_08_dates;

UPDATE catalog_seasons SET kind = 'regular', updated_at = updated_at WHERE HEX(kind) = HEX('standard');
UPDATE catalog_episodes SET kind = 'regular', updated_at = updated_at WHERE HEX(kind) IN (HEX('standard'), HEX('episode'));

UPDATE catalog_episodes
SET publication_status = CASE LOWER(JSON_UNQUOTE(JSON_EXTRACT(
    IF(JSON_VALID(record_json), record_json, '{}'), '$.status')))
    WHEN 'ready' THEN 'ready'
    WHEN 'archived' THEN 'archived'
    ELSE 'draft'
END,
    updated_at = updated_at
WHERE publication_status IS NULL;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'catalog_episodes' AND column_name = 'publication_status' AND (is_nullable = 'YES' OR column_default IS NULL)),
    'ALTER TABLE catalog_episodes MODIFY COLUMN publication_status VARCHAR(16) NOT NULL DEFAULT ''draft''',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_packages' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_packages' AND constraint_name = 'ck_catalog_package_status')),
    'ALTER TABLE catalog_packages ADD CONSTRAINT ck_catalog_package_status CHECK (HEX(status) IN (HEX(''COMMITTED'')))',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_snapshots' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_snapshots' AND constraint_name = 'ck_catalog_snapshot_status')),
    'ALTER TABLE catalog_snapshots ADD CONSTRAINT ck_catalog_snapshot_status CHECK (HEX(status) IN (HEX(''PENDING''), HEX(''BUILDING''), HEX(''READY''), HEX(''BLOCKED''), HEX(''SYNC_FAILED'')))',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_episodes' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_episodes' AND constraint_name = 'ck_catalog_episode_publication')),
    'ALTER TABLE catalog_episodes ADD CONSTRAINT ck_catalog_episode_publication CHECK (HEX(publication_status) IN (HEX(''draft''), HEX(''ready''), HEX(''archived'')))',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'users' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'users' AND constraint_name = 'ck_user_role')),
    'ALTER TABLE users ADD CONSTRAINT ck_user_role CHECK (HEX(role) IN (HEX(''ROLE_USER''), HEX(''ROLE_ADMIN'')))',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_media_assets' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_media_assets' AND constraint_name = 'ck_catalog_asset_policy')),
    'ALTER TABLE catalog_media_assets ADD CONSTRAINT ck_catalog_asset_policy CHECK (HEX(access_policy) IN (HEX(''private''), HEX(''authenticated''), HEX(''public'')))',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_media_assets' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_media_assets' AND constraint_name = 'ck_catalog_asset_content')),
    'ALTER TABLE catalog_media_assets ADD CONSTRAINT ck_catalog_asset_content CHECK (HEX(content_type) IN (HEX(''video''), HEX(''audio'')))',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_media_assets' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_media_assets' AND constraint_name = 'ck_catalog_asset_role')),
    'ALTER TABLE catalog_media_assets ADD CONSTRAINT ck_catalog_asset_role CHECK (HEX(role) IN (HEX(''feature''), HEX(''trailer''), HEX(''extra''), HEX(''opening''), HEX(''ending''), HEX(''dub''), HEX(''audio_description'')))',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_sources' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_sources' AND constraint_name = 'ck_catalog_source_kind')),
    'ALTER TABLE catalog_sources ADD CONSTRAINT ck_catalog_source_kind CHECK (HEX(kind) IN (HEX(''manual''), HEX(''official''), HEX(''external_catalog''), HEX(''subtitle''), HEX(''transcript''), HEX(''video_observation''), HEX(''model_output''), HEX(''other'')))',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_seasons' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_seasons' AND constraint_name = 'ck_catalog_season_kind')),
    'ALTER TABLE catalog_seasons ADD CONSTRAINT ck_catalog_season_kind CHECK (kind IS NULL OR HEX(kind) IN (HEX(''regular''), HEX(''specials''), HEX(''collection''), HEX(''unknown'')))',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_episodes' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_episodes' AND constraint_name = 'ck_catalog_episode_kind')),
    'ALTER TABLE catalog_episodes ADD CONSTRAINT ck_catalog_episode_kind CHECK (HEX(kind) IN (HEX(''regular''), HEX(''special''), HEX(''ova''), HEX(''ona''), HEX(''recap''), HEX(''short''), HEX(''pilot''), HEX(''movie''), HEX(''unknown'')))',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_text_tracks' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_text_tracks' AND constraint_name = 'ck_catalog_track_kind')),
    'ALTER TABLE catalog_text_tracks ADD CONSTRAINT ck_catalog_track_kind CHECK (HEX(kind) IN (HEX(''subtitle''), HEX(''transcript''), HEX(''ocr'')))',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'media_assets' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'media_assets' AND constraint_name = 'ck_media_kind')),
    'ALTER TABLE media_assets ADD CONSTRAINT ck_media_kind CHECK (HEX(kind) IN (HEX(''feature''), HEX(''trailer''), HEX(''extra''), HEX(''opening''), HEX(''ending''), HEX(''dub''), HEX(''audio_description'')))',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'movies' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'movies' AND constraint_name = 'ck_movie_rating_bounds')),
    'ALTER TABLE movies ADD CONSTRAINT ck_movie_rating_bounds CHECK (rating BETWEEN 0 AND 10)',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_series' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_series' AND constraint_name = 'ck_catalog_series_years')),
    'ALTER TABLE catalog_series ADD CONSTRAINT ck_catalog_series_years CHECK (release_year_start <= release_year_end)',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_media_assets' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_media_assets' AND constraint_name = 'ck_catalog_asset_size')),
    'ALTER TABLE catalog_media_assets ADD CONSTRAINT ck_catalog_asset_size CHECK (size_bytes >= 0)',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_media_assets' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_media_assets' AND constraint_name = 'ck_catalog_asset_duration')),
    'ALTER TABLE catalog_media_assets ADD CONSTRAINT ck_catalog_asset_duration CHECK (duration_ms > 0)',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_episodes' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_episodes' AND constraint_name = 'ck_catalog_episode_duration')),
    'ALTER TABLE catalog_episodes ADD CONSTRAINT ck_catalog_episode_duration CHECK (duration_ms > 0)',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_scenes' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_scenes' AND constraint_name = 'ck_catalog_scene_time_range')),
    'ALTER TABLE catalog_scenes ADD CONSTRAINT ck_catalog_scene_time_range CHECK (start_ms >= 0 AND end_ms > start_ms)',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'catalog_attribute_scales' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'catalog_attribute_scales' AND constraint_name = 'ck_catalog_scale_bounds')),
    'ALTER TABLE catalog_attribute_scales ADD CONSTRAINT ck_catalog_scale_bounds CHECK (minimum < maximum)',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;
