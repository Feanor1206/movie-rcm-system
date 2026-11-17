-- =========================================================================
-- Dippie Cinema Database Migration: Add favorite_items Table (MySQL 8.0)
-- =========================================================================

CREATE TABLE IF NOT EXISTS favorite_items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    movie_id VARCHAR(100) NOT NULL,
    movie_title VARCHAR(255) NOT NULL,
    poster_url VARCHAR(500),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_favorite_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_user_movie_favorite UNIQUE (user_id, movie_id),
    INDEX idx_favorite_user (user_id),
    INDEX idx_favorite_movie (movie_id)
);
