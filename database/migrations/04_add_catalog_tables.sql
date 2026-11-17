-- Migration 04: Add catalog collections tables for dippie.catalog.v1 (Milestone CATALOG-01)
-- OPTIMIZED VERSION: JSON Datatypes, Normalized Junction Tables, Audit Separation

-- ==========================================================
-- 0. AUDIT LOGS (Giải quyết Data Bloat)
-- Lưu trữ raw data của tất cả các entity thay vì nhét vào bảng chính
-- ==========================================================
CREATE TABLE IF NOT EXISTS catalog_audit_logs (
    entity_id VARCHAR(36) NOT NULL,
    entity_type VARCHAR(50) NOT NULL, -- vd: 'series', 'episode', 'character'
    record_data JSON,
    raw_data JSON,
    PRIMARY KEY (entity_id, entity_type)
);
-- Migration 04: Add catalog collections tables for dippie.catalog.v1 (MySQL 8.0)

CREATE TABLE IF NOT EXISTS catalog_packages (
    id VARCHAR(36) PRIMARY KEY,
    version VARCHAR(50) NOT NULL,
    revision INT NOT NULL,
    default_language VARCHAR(20) NOT NULL,
    import_mode VARCHAR(50) NOT NULL,
    reference_scope VARCHAR(50) NOT NULL,
    name VARCHAR(200),
    description LONGTEXT,
    content_hash VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    error_message LONGTEXT,
    opt_lock_version BIGINT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS catalog_genres (
    id VARCHAR(36) PRIMARY KEY,
    labels JSON NOT NULL,
    aliases JSON,
    description TEXT,
    id VARCHAR(100) PRIMARY KEY,
    labels_json LONGTEXT NOT NULL,
    aliases_json LONGTEXT,
    description LONGTEXT,
    record_json LONGTEXT,
    raw_json LONGTEXT,
    revision INT NOT NULL DEFAULT 1,
    opt_lock_version BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS catalog_attribute_scales (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    definition TEXT,
    minimum DOUBLE PRECISION NOT NULL,
    maximum DOUBLE PRECISION NOT NULL,
    levels JSON NOT NULL,
    version VARCHAR(50),
    source_ids JSON,
    definition LONGTEXT,
    minimum DOUBLE NOT NULL,
    maximum DOUBLE NOT NULL,
    levels_json LONGTEXT NOT NULL,
    version VARCHAR(50),
    source_ids_json LONGTEXT,
    record_json LONGTEXT,
    raw_json LONGTEXT,
    revision INT NOT NULL DEFAULT 1,
    opt_lock_version BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS catalog_sources (
    id VARCHAR(36) PRIMARY KEY,
    kind VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    uri VARCHAR(1000),
    note LONGTEXT,
    retrieved_at VARCHAR(100),
    record_json LONGTEXT,
    raw_json LONGTEXT,
    revision INT NOT NULL DEFAULT 1,
    opt_lock_version BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS catalog_series (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    original_title VARCHAR(255),
    aliases JSON,
    synopsis TEXT,
    translations JSON,
    keywords JSON,
    themes JSON,
    origin_countries JSON,
    original_languages JSON,
    release_year_start SMALLINT,
    release_year_end SMALLINT,
    release_status VARCHAR(50),
    artworks JSON,
    attributes JSON,
    ratings JSON,
    advisories JSON,
    credits JSON,
    external_ids JSON,
    aliases_json LONGTEXT,
    synopsis LONGTEXT,
    translations_json LONGTEXT,
    genre_ids_json LONGTEXT,
    keywords_json LONGTEXT,
    themes_json LONGTEXT,
    origin_countries_json LONGTEXT,
    original_languages_json LONGTEXT,
    release_year_start INT,
    release_year_end INT,
    release_status VARCHAR(50),
    character_ids_json LONGTEXT,
    artworks_json LONGTEXT,
    attributes_json LONGTEXT,
    ratings_json LONGTEXT,
    advisories_json LONGTEXT,
    credits_json LONGTEXT,
    external_ids_json LONGTEXT,
    record_json LONGTEXT,
    raw_json LONGTEXT,
    revision INT NOT NULL DEFAULT 1,
    opt_lock_version BIGINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_cat_series_title (title)
);

CREATE TABLE IF NOT EXISTS catalog_seasons (
    id VARCHAR(36) PRIMARY KEY,
    series_id VARCHAR(36) NOT NULL,
    number INT,
    title VARCHAR(255) NOT NULL,
    synopsis LONGTEXT,
    kind VARCHAR(50),
    translations JSON,
    release_date VARCHAR(50),
    artworks JSON,
    attributes JSON,
    translations_json LONGTEXT,
    release_date VARCHAR(50),
    artworks_json LONGTEXT,
    attributes_json LONGTEXT,
    record_json LONGTEXT,
    raw_json LONGTEXT,
    revision INT NOT NULL DEFAULT 1,
    opt_lock_version BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_season_series FOREIGN KEY (series_id) REFERENCES catalog_series(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS catalog_episodes (
    id VARCHAR(36) PRIMARY KEY,
    series_id VARCHAR(36) NOT NULL,
    season_id VARCHAR(36),
    number INT,
    title VARCHAR(255) NOT NULL,
    aliases JSON,
    synopsis TEXT,
    translations JSON,
    kind VARCHAR(50) NOT NULL,
    release_date VARCHAR(50),
    duration_ms BIGINT,
    primary_language VARCHAR(50),
    orders JSON,
    links JSON,
    plot_facts JSON,
    keywords JSON,
    themes JSON,
    attributes JSON,
    ratings JSON,
    artworks JSON,
    credits JSON,
    aliases_json LONGTEXT,
    synopsis LONGTEXT,
    translations_json LONGTEXT,
    kind VARCHAR(50) NOT NULL,
    release_date VARCHAR(50),
    duration_ms BIGINT,
    genre_ids_json LONGTEXT,
    primary_language VARCHAR(50),
    orders_json LONGTEXT,
    links_json LONGTEXT,
    character_ids_json LONGTEXT,
    plot_facts_json LONGTEXT,
    keywords_json LONGTEXT,
    themes_json LONGTEXT,
    attributes_json LONGTEXT,
    ratings_json LONGTEXT,
    artworks_json LONGTEXT,
    credits_json LONGTEXT,
    record_json LONGTEXT,
    raw_json LONGTEXT,
    revision INT NOT NULL DEFAULT 1,
    opt_lock_version BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_episode_series FOREIGN KEY (series_id) REFERENCES catalog_series(id) ON DELETE CASCADE,
    INDEX idx_cat_ep_series (series_id),
    INDEX idx_cat_ep_season (season_id)
);

-- 7.8 Segments
CREATE TABLE IF NOT EXISTS catalog_segments (
    id VARCHAR(36) PRIMARY KEY,
    episode_id VARCHAR(36) NOT NULL,
    position INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    aliases JSON,
    synopsis TEXT,
    translations JSON,
    primary_language VARCHAR(50),
    plot_facts JSON,
    keywords JSON,
    themes JSON,
    attributes JSON,
    episode_start_ms BIGINT,
    episode_end_ms BIGINT,
    aliases_json LONGTEXT,
    synopsis LONGTEXT,
    translations_json LONGTEXT,
    primary_language VARCHAR(50),
    character_ids_json LONGTEXT,
    plot_facts_json LONGTEXT,
    keywords_json LONGTEXT,
    themes_json LONGTEXT,
    attributes_json LONGTEXT,
    episode_start_ms BIGINT,
    episode_end_ms BIGINT,
    record_json LONGTEXT,
    raw_json LONGTEXT,
    revision INT NOT NULL DEFAULT 1,
    opt_lock_version BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_segment_episode FOREIGN KEY (episode_id) REFERENCES catalog_episodes(id) ON DELETE CASCADE,
    INDEX idx_cat_seg_ep (episode_id)
);

CREATE TABLE IF NOT EXISTS catalog_characters (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    aliases JSON,
    description TEXT,
    role VARCHAR(50),
    traits JSON,
    relationships JSON,
    voice_credits JSON,
    artworks JSON,
    id VARCHAR(100) PRIMARY KEY,
    series_ids_json LONGTEXT,
    name VARCHAR(255) NOT NULL,
    aliases_json LONGTEXT,
    description LONGTEXT,
    role VARCHAR(50),
    traits_json LONGTEXT,
    relationships_json LONGTEXT,
    voice_credits_json LONGTEXT,
    artworks_json LONGTEXT,
    record_json LONGTEXT,
    raw_json LONGTEXT,
    revision INT NOT NULL DEFAULT 1,
    opt_lock_version BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ==========================================================
-- BẢNG TRUNG GIAN (JUNCTION TABLES) - Thay thế cho mảng ID JSON
-- ==========================================================

CREATE TABLE IF NOT EXISTS catalog_series_genres (
    series_id VARCHAR(36) NOT NULL,
    genre_id VARCHAR(36) NOT NULL,
    PRIMARY KEY (series_id, genre_id),
    CONSTRAINT fk_csg_series FOREIGN KEY (series_id) REFERENCES catalog_series(id) ON DELETE CASCADE,
    CONSTRAINT fk_csg_genre FOREIGN KEY (genre_id) REFERENCES catalog_genres(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS catalog_series_characters (
    series_id VARCHAR(36) NOT NULL,
    character_id VARCHAR(36) NOT NULL,
    PRIMARY KEY (series_id, character_id),
    CONSTRAINT fk_csc_series FOREIGN KEY (series_id) REFERENCES catalog_series(id) ON DELETE CASCADE,
    CONSTRAINT fk_csc_char FOREIGN KEY (character_id) REFERENCES catalog_characters(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS catalog_episode_characters (
    episode_id VARCHAR(36) NOT NULL,
    character_id VARCHAR(36) NOT NULL,
    PRIMARY KEY (episode_id, character_id),
    CONSTRAINT fk_cec_ep FOREIGN KEY (episode_id) REFERENCES catalog_episodes(id) ON DELETE CASCADE,
    CONSTRAINT fk_cec_char FOREIGN KEY (character_id) REFERENCES catalog_characters(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS catalog_segment_characters (
    segment_id VARCHAR(36) NOT NULL,
    character_id VARCHAR(36) NOT NULL,
    PRIMARY KEY (segment_id, character_id),
    CONSTRAINT fk_cseg_seg FOREIGN KEY (segment_id) REFERENCES catalog_segments(id) ON DELETE CASCADE,
    CONSTRAINT fk_cseg_char FOREIGN KEY (character_id) REFERENCES catalog_characters(id) ON DELETE CASCADE
);

-- ==========================================================
-- MEDIA & TRACKS
-- ==========================================================

-- 7.10 Media Assets
CREATE TABLE IF NOT EXISTS catalog_media_assets (
    id VARCHAR(36) PRIMARY KEY,
    content_type VARCHAR(50) NOT NULL DEFAULT 'video',
    role VARCHAR(50) NOT NULL DEFAULT 'feature',
    edition_label VARCHAR(100),
    spoken_languages JSON,
    embedded_subtitle_languages JSON,
    spoken_languages_json LONGTEXT,
    embedded_subtitle_languages_json LONGTEXT,
    storage_provider VARCHAR(50) NOT NULL,
    storage_key VARCHAR(100) NOT NULL,
    relative_path VARCHAR(500) NOT NULL,
    drive_file_id VARCHAR(255),
    drive_folder_id VARCHAR(255),
    size_bytes BIGINT,
    sha256 VARCHAR(100),
    duration_ms BIGINT,
    technical JSON,
    coverage JSON,
    related_asset_id VARCHAR(36),
    access_policy VARCHAR(50) NOT NULL DEFAULT 'public',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    technical_json LONGTEXT,
    coverage_json LONGTEXT,
    related_asset_id VARCHAR(100),
    access_policy VARCHAR(50) NOT NULL DEFAULT 'public',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    record_json LONGTEXT,
    raw_json LONGTEXT,
    revision INT NOT NULL DEFAULT 1,
    opt_lock_version BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS catalog_text_tracks (
    id VARCHAR(36) PRIMARY KEY,
    media_asset_id VARCHAR(36) NOT NULL,
    language VARCHAR(50) NOT NULL,
    kind VARCHAR(50) NOT NULL,
    label VARCHAR(255),
    format VARCHAR(50) NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    external_file JSON,
    cues JSON,
    provenance JSON,
    external_file_json LONGTEXT,
    cues_json LONGTEXT,
    provenance_json LONGTEXT,
    record_json LONGTEXT,
    raw_json LONGTEXT,
    revision INT NOT NULL DEFAULT 1,
    opt_lock_version BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_text_track_asset FOREIGN KEY (media_asset_id) REFERENCES catalog_media_assets(id) ON DELETE CASCADE,
    INDEX idx_cat_track_asset (media_asset_id)
);

CREATE TABLE IF NOT EXISTS catalog_scenes (
    id VARCHAR(36) PRIMARY KEY,
    media_asset_id VARCHAR(36),
    episode_id VARCHAR(36) NOT NULL,
    segment_id VARCHAR(36),
    start_ms BIGINT NOT NULL,
    end_ms BIGINT NOT NULL,
    title VARCHAR(255),
    summary TEXT,
    visual_description TEXT,
    visual_tags JSON,
    sound_events JSON,
    transcript_cue_ids JSON,
    keywords JSON,
    themes JSON,
    attributes JSON,
    provenance JSON,
    summary LONGTEXT,
    visual_description LONGTEXT,
    visual_tags_json LONGTEXT,
    sound_events_json LONGTEXT,
    transcript_cue_ids_json LONGTEXT,
    character_ids_json LONGTEXT,
    keywords_json LONGTEXT,
    themes_json LONGTEXT,
    attributes_json LONGTEXT,
    provenance_json LONGTEXT,
    record_json LONGTEXT,
    raw_json LONGTEXT,
    revision INT NOT NULL DEFAULT 1,
    opt_lock_version BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_scene_episode FOREIGN KEY (episode_id) REFERENCES catalog_episodes(id) ON DELETE CASCADE,
    INDEX idx_cat_scene_ep (episode_id),
    INDEX idx_cat_scene_asset (media_asset_id)
);

CREATE TABLE IF NOT EXISTS catalog_scene_characters (
    scene_id VARCHAR(36) NOT NULL,
    character_id VARCHAR(36) NOT NULL,
    PRIMARY KEY (scene_id, character_id),
    CONSTRAINT fk_scn_c_scene FOREIGN KEY (scene_id) REFERENCES catalog_scenes(id) ON DELETE CASCADE,
    CONSTRAINT fk_scn_c_char FOREIGN KEY (character_id) REFERENCES catalog_characters(id) ON DELETE CASCADE
);

-- 7.13 Canonical Database Catalog Snapshots
CREATE TABLE IF NOT EXISTS catalog_snapshots (
    id VARCHAR(36) PRIMARY KEY,
    snapshot_version BIGINT NOT NULL,
    content_hash VARCHAR(100) NOT NULL,
    total_items INT NOT NULL,
    status VARCHAR(50) NOT NULL,
    retry_count INT DEFAULT 0,
    error_message LONGTEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_cat_snap_status (status),
    UNIQUE INDEX uq_cat_snap_version (snapshot_version)
);

-- ==========================================================
-- INDEXES THIẾT YẾU CHO TỐI ƯU TRUY VẤN
-- ==========================================================
CREATE INDEX IF NOT EXISTS idx_cat_series_title ON catalog_series (title);
CREATE INDEX IF NOT EXISTS idx_cat_series_year ON catalog_series (release_year_start DESC);
CREATE INDEX IF NOT EXISTS idx_cat_series_status ON catalog_series (release_status);
CREATE INDEX IF NOT EXISTS idx_cat_ep_series ON catalog_episodes (series_id);
CREATE INDEX IF NOT EXISTS idx_cat_ep_season ON catalog_episodes (season_id);
CREATE INDEX IF NOT EXISTS idx_cat_seg_ep ON catalog_segments (episode_id);
CREATE INDEX IF NOT EXISTS idx_cat_scene_ep ON catalog_scenes (episode_id);
CREATE INDEX IF NOT EXISTS idx_cat_scene_asset ON catalog_scenes (media_asset_id);
CREATE INDEX IF NOT EXISTS idx_cat_track_asset ON catalog_text_tracks (media_asset_id);
CREATE INDEX IF NOT EXISTS idx_cat_snap_status ON catalog_snapshots (status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cat_snap_version ON catalog_snapshots (snapshot_version);
