-- =========================================================================
-- Dippie Animation Movie Recommendation System
-- Schema Migration: Version 1.0 (Production Reviewable DDL)
-- Target: MySQL 8.0+ / H2 MySQL Mode
-- Policy: Prod uses ddl-auto: validate; this script defines initial schema
-- =========================================================================

CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    role VARCHAR(20) NOT NULL DEFAULT 'ROLE_USER',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email UNIQUE (email),
    INDEX idx_users_username (username),
    INDEX idx_users_email (email)
);

CREATE TABLE IF NOT EXISTS movies (
    id VARCHAR(100) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    release_year INTEGER NOT NULL,
    rating DOUBLE NOT NULL DEFAULT 0.0,
    runtime VARCHAR(20),
    genres LONGTEXT,
    description LONGTEXT,
    poster VARCHAR(500),
    backdrop VARCHAR(500),
    video_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_movies_year (release_year),
    INDEX idx_movies_rating (rating)
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    movie_id VARCHAR(100) NOT NULL,
    movie_title VARCHAR(255) NOT NULL,
    poster_url VARCHAR(500),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_watchlist_user_movie UNIQUE (user_id, movie_id),
    CONSTRAINT fk_watchlist_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    INDEX idx_watchlist_user (user_id),
    INDEX idx_watchlist_movie (movie_id)
);

CREATE TABLE IF NOT EXISTS favorite_items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    movie_id VARCHAR(100) NOT NULL,
    movie_title VARCHAR(255) NOT NULL,
    poster_url VARCHAR(500),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_movie_favorite UNIQUE (user_id, movie_id),
    CONSTRAINT fk_favorite_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    INDEX idx_favorite_user (user_id),
    INDEX idx_favorite_movie (movie_id)
);

CREATE TABLE IF NOT EXISTS movie_ratings (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    movie_id VARCHAR(100) NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_rating_user_movie UNIQUE (user_id, movie_id),
    CONSTRAINT fk_rating_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    INDEX idx_ratings_user (user_id),
    INDEX idx_ratings_movie (movie_id)
);

CREATE TABLE IF NOT EXISTS media_assets (
    id VARCHAR(64) PRIMARY KEY,
    movie_id VARCHAR(100) NOT NULL,
    kind VARCHAR(20) NOT NULL,
    storage_provider VARCHAR(30) NOT NULL DEFAULT 'local',
    storage_key VARCHAR(100) DEFAULT 'local_main',
    relative_path VARCHAR(500) NOT NULL,
    version VARCHAR(50) NOT NULL DEFAULT 'v1',
    mime_type VARCHAR(100) NOT NULL DEFAULT 'video/mp4',
    byte_length BIGINT NOT NULL,
    duration_seconds DOUBLE,
    is_public BOOLEAN NOT NULL DEFAULT TRUE,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_media_movie FOREIGN KEY (movie_id) REFERENCES movies (id) ON DELETE CASCADE,
    CONSTRAINT uq_movie_kind_version UNIQUE (movie_id, kind, version),
    INDEX idx_media_movie_id (movie_id),
    INDEX idx_media_movie_kind (movie_id, kind)
);
