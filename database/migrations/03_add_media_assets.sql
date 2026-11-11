-- Migration 03: Add media_assets table for streaming and playback (MySQL 8.0)

CREATE TABLE IF NOT EXISTS media_assets (
    id VARCHAR(64) PRIMARY KEY,
    movie_id VARCHAR(100) NOT NULL,
    kind VARCHAR(20) NOT NULL,
    storage_provider VARCHAR(30) NOT NULL DEFAULT 'local',
    storage_key VARCHAR(100),
    relative_path VARCHAR(500) NOT NULL,
    version VARCHAR(50) NOT NULL DEFAULT 'v1',
    mime_type VARCHAR(100) NOT NULL DEFAULT 'video/mp4',
    byte_length BIGINT NOT NULL,
    duration_seconds DOUBLE,
    is_public BOOLEAN NOT NULL DEFAULT TRUE,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_media_movie FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
    CONSTRAINT uq_movie_kind_version UNIQUE (movie_id, kind, version),
    INDEX idx_media_movie_id (movie_id),
    INDEX idx_media_movie_kind (movie_id, kind)
);
