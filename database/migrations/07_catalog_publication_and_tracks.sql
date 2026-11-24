DROP TEMPORARY TABLE IF EXISTS dippie_migration_07_orphans;
DROP TEMPORARY TABLE IF EXISTS dippie_migration_07_guard;
CREATE TEMPORARY TABLE dippie_migration_07_orphans (
    table_name VARCHAR(64),
    row_id VARCHAR(100),
    reference_column VARCHAR(64),
    missing_id VARCHAR(100)
);
INSERT INTO dippie_migration_07_orphans
SELECT 'watchlist_items', CAST(child.id AS CHAR), 'movie_id', child.movie_id
FROM watchlist_items AS child LEFT JOIN movies AS parent ON parent.id = child.movie_id
WHERE child.movie_id IS NOT NULL AND parent.id IS NULL
UNION ALL
SELECT 'favorite_items', CAST(child.id AS CHAR), 'movie_id', child.movie_id
FROM favorite_items AS child LEFT JOIN movies AS parent ON parent.id = child.movie_id
WHERE child.movie_id IS NOT NULL AND parent.id IS NULL
UNION ALL
SELECT 'movie_ratings', CAST(child.id AS CHAR), 'movie_id', child.movie_id
FROM movie_ratings AS child LEFT JOIN movies AS parent ON parent.id = child.movie_id
WHERE child.movie_id IS NOT NULL AND parent.id IS NULL
UNION ALL
SELECT 'watch_progress', CAST(child.id AS CHAR), 'asset_id', child.asset_id
FROM watch_progress AS child LEFT JOIN catalog_media_assets AS parent ON parent.id = child.asset_id
WHERE child.asset_id IS NOT NULL AND parent.id IS NULL
UNION ALL
SELECT 'catalog_scenes', CAST(child.id AS CHAR), 'media_asset_id', child.media_asset_id
FROM catalog_scenes AS child LEFT JOIN catalog_media_assets AS parent ON parent.id = child.media_asset_id
WHERE child.media_asset_id IS NOT NULL AND parent.id IS NULL
UNION ALL
SELECT 'catalog_scenes', CAST(child.id AS CHAR), 'segment_id', child.segment_id
FROM catalog_scenes AS child LEFT JOIN catalog_segments AS parent ON parent.id = child.segment_id
WHERE child.segment_id IS NOT NULL AND parent.id IS NULL
UNION ALL
SELECT 'catalog_media_assets', CAST(child.id AS CHAR), 'related_asset_id', child.related_asset_id
FROM catalog_media_assets AS child LEFT JOIN catalog_media_assets AS parent ON parent.id = child.related_asset_id
WHERE child.related_asset_id IS NOT NULL AND parent.id IS NULL;

SELECT table_name, row_id, reference_column, missing_id
FROM dippie_migration_07_orphans
ORDER BY table_name, row_id, reference_column;

CREATE TEMPORARY TABLE dippie_migration_07_guard (
    orphan_count_must_be_zero INT PRIMARY KEY
);
INSERT INTO dippie_migration_07_guard VALUES (1);
INSERT INTO dippie_migration_07_guard
SELECT 1 FROM dippie_migration_07_orphans LIMIT 1;
DROP TEMPORARY TABLE dippie_migration_07_guard;
DROP TEMPORARY TABLE dippie_migration_07_orphans;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'catalog_episodes' AND column_name = 'publication_status'),
    'DO 0',
    'ALTER TABLE catalog_episodes ADD COLUMN publication_status VARCHAR(16)'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'catalog_episodes' AND index_name = 'idx_cat_ep_publication'),
    'DO 0',
    'ALTER TABLE catalog_episodes ADD INDEX idx_cat_ep_publication (publication_status)'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'catalog_segments' AND index_name = 'uq_cat_segment_position'),
    'DO 0',
    'ALTER TABLE catalog_segments ADD UNIQUE KEY uq_cat_segment_position (episode_id, position)'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'catalog_segments' AND constraint_name = 'ck_cat_segment_time_range'),
    'DO 0',
    'ALTER TABLE catalog_segments ADD CONSTRAINT ck_cat_segment_time_range CHECK ((episode_start_ms IS NULL AND episode_end_ms IS NULL) OR (episode_start_ms IS NOT NULL AND episode_end_ms IS NOT NULL AND episode_start_ms >= 0 AND episode_end_ms > episode_start_ms))'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'catalog_text_tracks' AND column_name = 'episode_id'),
    'DO 0',
    'ALTER TABLE catalog_text_tracks ADD COLUMN episode_id VARCHAR(100)'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'catalog_text_tracks' AND column_name = 'source_id'),
    'DO 0',
    'ALTER TABLE catalog_text_tracks ADD COLUMN source_id VARCHAR(100)'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'catalog_text_tracks' AND column_name = 'media_asset_id' AND is_nullable = 'YES'),
    'DO 0',
    'ALTER TABLE catalog_text_tracks MODIFY media_asset_id VARCHAR(100) NULL'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'catalog_text_tracks' AND index_name = 'idx_cat_track_episode'),
    'DO 0',
    'ALTER TABLE catalog_text_tracks ADD INDEX idx_cat_track_episode (episode_id)'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'catalog_text_tracks' AND constraint_name = 'fk_cat_track_episode'),
    'DO 0',
    'ALTER TABLE catalog_text_tracks ADD CONSTRAINT fk_cat_track_episode FOREIGN KEY (episode_id) REFERENCES catalog_episodes(id) ON DELETE CASCADE'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'catalog_text_tracks' AND constraint_name = 'fk_cat_track_source'),
    'DO 0',
    'ALTER TABLE catalog_text_tracks ADD CONSTRAINT fk_cat_track_source FOREIGN KEY (source_id) REFERENCES catalog_sources(id)'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'catalog_text_tracks' AND constraint_name = 'ck_cat_text_track_origin'),
    'DO 0',
    'ALTER TABLE catalog_text_tracks ADD CONSTRAINT ck_cat_text_track_origin CHECK (media_asset_id IS NOT NULL OR (episode_id IS NOT NULL AND source_id IS NOT NULL))'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

CREATE TABLE IF NOT EXISTS catalog_episode_characters (
    episode_id VARCHAR(100) NOT NULL,
    character_id VARCHAR(100) NOT NULL,
    PRIMARY KEY (episode_id, character_id),
    INDEX idx_cat_ep_character (character_id),
    FOREIGN KEY (episode_id) REFERENCES catalog_episodes(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES catalog_characters(id) ON DELETE CASCADE
);

INSERT INTO catalog_episode_characters (episode_id, character_id)
SELECT DISTINCT episode.id, taxonomy.id
FROM catalog_episodes AS episode
CROSS JOIN JSON_TABLE(
    IF(JSON_VALID(episode.character_ids_json), episode.character_ids_json, '[]'),
    '$[*]' COLUMNS(reference_id VARCHAR(100) PATH '$' NULL ON ERROR)
) AS linked
JOIN catalog_characters AS taxonomy ON CAST(taxonomy.id AS BINARY) = CAST(linked.reference_id AS BINARY)
WHERE episode.publication_status IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM catalog_episode_characters AS previous
      WHERE previous.episode_id = episode.id AND previous.character_id = taxonomy.id
  );

CREATE TABLE IF NOT EXISTS catalog_episode_genres (
    episode_id VARCHAR(100) NOT NULL,
    genre_id VARCHAR(100) NOT NULL,
    PRIMARY KEY (episode_id, genre_id),
    INDEX idx_cat_ep_genre (genre_id),
    FOREIGN KEY (episode_id) REFERENCES catalog_episodes(id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES catalog_genres(id) ON DELETE CASCADE
);

INSERT INTO catalog_episode_genres (episode_id, genre_id)
SELECT DISTINCT episode.id, taxonomy.id
FROM catalog_episodes AS episode
CROSS JOIN JSON_TABLE(
    IF(JSON_VALID(episode.genre_ids_json), episode.genre_ids_json, '[]'),
    '$[*]' COLUMNS(reference_id VARCHAR(100) PATH '$' NULL ON ERROR)
) AS linked
JOIN catalog_genres AS taxonomy ON CAST(taxonomy.id AS BINARY) = CAST(linked.reference_id AS BINARY)
WHERE episode.publication_status IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM catalog_episode_genres AS previous
      WHERE previous.episode_id = episode.id AND previous.genre_id = taxonomy.id
  );

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
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'watchlist_items' AND constraint_name = 'fk_watchlist_movie'),
    'DO 0',
    'ALTER TABLE watchlist_items ADD CONSTRAINT fk_watchlist_movie FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'favorite_items' AND constraint_name = 'fk_favorite_movie'),
    'DO 0',
    'ALTER TABLE favorite_items ADD CONSTRAINT fk_favorite_movie FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'movie_ratings' AND constraint_name = 'fk_rating_movie'),
    'DO 0',
    'ALTER TABLE movie_ratings ADD CONSTRAINT fk_rating_movie FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'watch_progress' AND constraint_name = 'fk_watch_progress_asset'),
    'DO 0',
    'ALTER TABLE watch_progress ADD CONSTRAINT fk_watch_progress_asset FOREIGN KEY (asset_id) REFERENCES catalog_media_assets(id) ON DELETE CASCADE'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'catalog_scenes' AND constraint_name = 'fk_scene_asset'),
    'DO 0',
    'ALTER TABLE catalog_scenes ADD CONSTRAINT fk_scene_asset FOREIGN KEY (media_asset_id) REFERENCES catalog_media_assets(id) ON DELETE CASCADE'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'catalog_scenes' AND constraint_name = 'fk_scene_segment'),
    'DO 0',
    'ALTER TABLE catalog_scenes ADD CONSTRAINT fk_scene_segment FOREIGN KEY (segment_id) REFERENCES catalog_segments(id) ON DELETE SET NULL'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'catalog_media_assets' AND constraint_name = 'fk_asset_related'),
    'DO 0',
    'ALTER TABLE catalog_media_assets ADD CONSTRAINT fk_asset_related FOREIGN KEY (related_asset_id) REFERENCES catalog_media_assets(id) ON DELETE SET NULL'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'watchlist_items' AND column_name = 'movie_title'),
    'ALTER TABLE watchlist_items DROP COLUMN movie_title',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'watchlist_items' AND column_name = 'poster_url'),
    'ALTER TABLE watchlist_items DROP COLUMN poster_url',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'favorite_items' AND column_name = 'movie_title'),
    'ALTER TABLE favorite_items DROP COLUMN movie_title',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'favorite_items' AND column_name = 'poster_url'),
    'ALTER TABLE favorite_items DROP COLUMN poster_url',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'movie_ratings' AND constraint_name = 'ck_movie_rating_range'),
    'DO 0',
    'ALTER TABLE movie_ratings ADD CONSTRAINT ck_movie_rating_range CHECK (rating >= 1 AND rating <= 10)'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'movie_ratings' AND constraint_name = 'movie_ratings_chk_1'),
    'ALTER TABLE movie_ratings DROP CHECK movie_ratings_chk_1',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'watch_progress' AND constraint_name = 'ck_watch_progress_position'),
    'DO 0',
    'ALTER TABLE watch_progress ADD CONSTRAINT ck_watch_progress_position CHECK (position_ms >= 0)'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'watch_progress' AND constraint_name = 'watch_progress_chk_1'),
    'ALTER TABLE watch_progress DROP CHECK watch_progress_chk_1',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

CREATE TABLE IF NOT EXISTS movie_genre_terms (
    name VARCHAR(255) COLLATE utf8mb4_bin PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS catalog_series_genres (
    series_id VARCHAR(100) NOT NULL,
    genre_id VARCHAR(100) NOT NULL,
    PRIMARY KEY (series_id, genre_id),
    INDEX idx_cat_series_genre (genre_id),
    CONSTRAINT fk_catalog_series_genres_series_id FOREIGN KEY (series_id) REFERENCES catalog_series(id) ON DELETE CASCADE,
    CONSTRAINT fk_catalog_series_genres_genre_id FOREIGN KEY (genre_id) REFERENCES catalog_genres(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS catalog_series_characters (
    series_id VARCHAR(100) NOT NULL,
    character_id VARCHAR(100) NOT NULL,
    PRIMARY KEY (series_id, character_id),
    INDEX idx_cat_series_character (character_id),
    CONSTRAINT fk_catalog_series_characters_series_id FOREIGN KEY (series_id) REFERENCES catalog_series(id) ON DELETE CASCADE,
    CONSTRAINT fk_catalog_series_characters_character_id FOREIGN KEY (character_id) REFERENCES catalog_characters(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS catalog_character_series (
    character_id VARCHAR(100) NOT NULL,
    series_id VARCHAR(100) NOT NULL,
    PRIMARY KEY (character_id, series_id),
    INDEX idx_cat_character_series (series_id),
    CONSTRAINT fk_catalog_character_series_character_id FOREIGN KEY (character_id) REFERENCES catalog_characters(id) ON DELETE CASCADE,
    CONSTRAINT fk_catalog_character_series_series_id FOREIGN KEY (series_id) REFERENCES catalog_series(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS movie_genres (
    movie_id VARCHAR(100) NOT NULL,
    genre_name VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
    PRIMARY KEY (movie_id, genre_name),
    INDEX idx_movie_genre_name (genre_name),
    CONSTRAINT fk_movie_genres_movie_id FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
    CONSTRAINT fk_movie_genres_genre_name FOREIGN KEY (genre_name) REFERENCES movie_genre_terms(name) ON DELETE CASCADE
);

INSERT INTO catalog_series_genres (series_id, genre_id)
SELECT DISTINCT owner.id, ref.id
FROM catalog_series AS owner
CROSS JOIN JSON_TABLE(
    IF(JSON_VALID(owner.genre_ids_json), owner.genre_ids_json, '[]'),
    '$[*]' COLUMNS(reference_id VARCHAR(100) PATH '$' NULL ON ERROR)
) AS linked
JOIN catalog_genres AS ref ON CAST(ref.id AS BINARY) = CAST(linked.reference_id AS BINARY)
WHERE NOT EXISTS (
    SELECT 1 FROM catalog_series_genres AS previous WHERE previous.series_id = owner.id AND previous.genre_id = ref.id
);

INSERT INTO catalog_series_characters (series_id, character_id)
SELECT DISTINCT owner.id, ref.id
FROM catalog_series AS owner
CROSS JOIN JSON_TABLE(
    IF(JSON_VALID(owner.character_ids_json), owner.character_ids_json, '[]'),
    '$[*]' COLUMNS(reference_id VARCHAR(100) PATH '$' NULL ON ERROR)
) AS linked
JOIN catalog_characters AS ref ON CAST(ref.id AS BINARY) = CAST(linked.reference_id AS BINARY)
WHERE NOT EXISTS (
    SELECT 1 FROM catalog_series_characters AS previous WHERE previous.series_id = owner.id AND previous.character_id = ref.id
);

INSERT INTO catalog_character_series (character_id, series_id)
SELECT DISTINCT owner.id, ref.id
FROM catalog_characters AS owner
CROSS JOIN JSON_TABLE(
    IF(JSON_VALID(owner.series_ids_json), owner.series_ids_json, '[]'),
    '$[*]' COLUMNS(reference_id VARCHAR(100) PATH '$' NULL ON ERROR)
) AS linked
JOIN catalog_series AS ref ON CAST(ref.id AS BINARY) = CAST(linked.reference_id AS BINARY)
WHERE NOT EXISTS (
    SELECT 1 FROM catalog_character_series AS previous WHERE previous.character_id = owner.id AND previous.series_id = ref.id
);

DROP TEMPORARY TABLE IF EXISTS dippie_movie_genre_backfill;
CREATE TEMPORARY TABLE dippie_movie_genre_backfill (
    movie_id VARCHAR(100) NOT NULL,
    genre_name VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
    PRIMARY KEY (movie_id, genre_name)
);
INSERT INTO dippie_movie_genre_backfill (movie_id, genre_name)
SELECT DISTINCT movies.id,
       LOWER(REGEXP_REPLACE(linked.genre_name, '^[[:space:]]+|[[:space:]]+$', '')) COLLATE utf8mb4_bin
FROM movies
CROSS JOIN JSON_TABLE(
    CONCAT('[', REPLACE(JSON_QUOTE(COALESCE(movies.genres,'')), ',', '","'), ']'),
    '$[*]' COLUMNS(genre_name VARCHAR(255) PATH '$' NULL ON ERROR)
) AS linked
WHERE REGEXP_REPLACE(linked.genre_name, '^[[:space:]]+|[[:space:]]+$', '') <> '';

INSERT INTO movie_genre_terms (name)
SELECT DISTINCT source.genre_name FROM dippie_movie_genre_backfill AS source
WHERE NOT EXISTS (SELECT 1 FROM movie_genre_terms AS previous WHERE previous.name = source.genre_name);

INSERT INTO movie_genres (movie_id, genre_name)
SELECT source.movie_id, source.genre_name FROM dippie_movie_genre_backfill AS source
WHERE NOT EXISTS (
    SELECT 1 FROM movie_genres AS previous WHERE previous.movie_id = source.movie_id
    AND previous.genre_name = source.genre_name
);
DROP TEMPORARY TABLE dippie_movie_genre_backfill;
