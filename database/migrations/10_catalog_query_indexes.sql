SET @catalog_ddl = IF(
    NOT EXISTS (SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'catalog_episodes'
              AND index_name = 'idx_cat_ep_status_series_duration'),
    'ALTER TABLE catalog_episodes ADD INDEX idx_cat_ep_status_series_duration (publication_status, series_id, duration_ms)',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'watchlist_items'
              AND index_name = 'idx_watchlist_user'),
    'ALTER TABLE watchlist_items DROP INDEX idx_watchlist_user',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'favorite_items'
              AND index_name = 'idx_favorite_user'),
    'ALTER TABLE favorite_items DROP INDEX idx_favorite_user',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'movie_ratings'
              AND index_name = 'idx_ratings_user'),
    'ALTER TABLE movie_ratings DROP INDEX idx_ratings_user',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'media_assets'
              AND index_name = 'idx_media_movie_id'),
    'ALTER TABLE media_assets DROP INDEX idx_media_movie_id',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;

SET @catalog_ddl = IF(
    EXISTS (SELECT 1 FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'media_assets'
              AND index_name = 'idx_media_movie_kind'),
    'ALTER TABLE media_assets DROP INDEX idx_media_movie_kind',
    'DO 0'
);
PREPARE catalog_ddl FROM @catalog_ddl;
EXECUTE catalog_ddl;
DEALLOCATE PREPARE catalog_ddl;
