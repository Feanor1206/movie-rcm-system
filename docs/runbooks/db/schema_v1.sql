-- =========================================================================
-- Dippie Animation Movie Recommendation System
-- Schema Migration: Version 1.0 (Production Reviewable DDL)
-- Target: PostgreSQL 14+ / H2 PostgreSQL Mode
-- Policy: Prod uses ddl-auto: validate; this script defines initial schema
-- =========================================================================

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    role VARCHAR(20) NOT NULL DEFAULT 'ROLE_USER',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- 2. Movies Catalog Table
CREATE TABLE IF NOT EXISTS movies (
    id VARCHAR(100) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    release_year INTEGER NOT NULL,
    rating DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    runtime VARCHAR(20),
    genres TEXT,
    description TEXT,
    poster VARCHAR(500),
    backdrop VARCHAR(500),
    video_url VARCHAR(500),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_movies_year ON movies (release_year);
CREATE INDEX IF NOT EXISTS idx_movies_rating ON movies (rating);

-- 3. Watchlist Items Table
CREATE TABLE IF NOT EXISTS watchlist_items (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    movie_id VARCHAR(100) NOT NULL,
    movie_title VARCHAR(255) NOT NULL,
    poster_url VARCHAR(500),
    added_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_watchlist_user_movie UNIQUE (user_id, movie_id),
    CONSTRAINT fk_watchlist_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist_items (user_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_movie ON watchlist_items (movie_id);

-- 4. Favorite Items Table
CREATE TABLE IF NOT EXISTS favorite_items (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    movie_id VARCHAR(100) NOT NULL,
    movie_title VARCHAR(255) NOT NULL,
    poster_url VARCHAR(500),
    added_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_movie_favorite UNIQUE (user_id, movie_id),
    CONSTRAINT fk_favorite_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_favorite_user ON favorite_items (user_id);
CREATE INDEX IF NOT EXISTS idx_favorite_movie ON favorite_items (movie_id);

-- 5. Movie Ratings Table
CREATE TABLE IF NOT EXISTS movie_ratings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    movie_id VARCHAR(100) NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 10),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_rating_user_movie UNIQUE (user_id, movie_id),
    CONSTRAINT fk_rating_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ratings_user ON movie_ratings (user_id);
CREATE INDEX IF NOT EXISTS idx_ratings_movie ON movie_ratings (movie_id);

-- =========================================================================
-- Rollback & Data Preservation Policy
-- =========================================================================
-- DO NOT execute DROP TABLE or destructive DDL during rollbacks.
-- Rollbacks must be performed via application code/configuration rollback.
-- All tables, schema definitions, and user interaction data (movie_ratings,
-- favorite_items, watchlist_items, users, movies) must be preserved intact.
