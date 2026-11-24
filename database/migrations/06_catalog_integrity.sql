-- MySQL 8. Run against the existing Dippie schema.
SET @dippie_ddl = IF(
    EXISTS (
        SELECT 1 FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'catalog_seasons'
          AND index_name = 'uq_cat_season_series_id'
    ),
    'DO 0',
    'ALTER TABLE catalog_seasons ADD UNIQUE KEY uq_cat_season_series_id (series_id, id)'
);
PREPARE dippie_catalog_ddl FROM @dippie_ddl;
EXECUTE dippie_catalog_ddl;
DEALLOCATE PREPARE dippie_catalog_ddl;

SET @dippie_ddl = IF(
    EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_schema = DATABASE() AND table_name = 'catalog_episodes'
          AND constraint_name = 'fk_episode_season_same_series' AND constraint_type = 'FOREIGN KEY'
    ),
    'DO 0',
    'ALTER TABLE catalog_episodes ADD CONSTRAINT fk_episode_season_same_series FOREIGN KEY (series_id, season_id) REFERENCES catalog_seasons (series_id, id)'
);
PREPARE dippie_catalog_ddl FROM @dippie_ddl;
EXECUTE dippie_catalog_ddl;
DEALLOCATE PREPARE dippie_catalog_ddl;

CREATE TABLE IF NOT EXISTS catalog_episode_assets (
    episode_id VARCHAR(100) NOT NULL,
    media_asset_id VARCHAR(100) NOT NULL,
    PRIMARY KEY (episode_id, media_asset_id),
    INDEX idx_cat_episode_assets_media (media_asset_id),
    CONSTRAINT fk_cat_ep_asset_ep FOREIGN KEY (episode_id) REFERENCES catalog_episodes(id) ON DELETE CASCADE,
    CONSTRAINT fk_cat_ep_asset_media FOREIGN KEY (media_asset_id) REFERENCES catalog_media_assets(id) ON DELETE CASCADE
);
