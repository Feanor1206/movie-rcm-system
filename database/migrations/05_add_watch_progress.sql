-- Migration 05: Add durable, account-scoped episode playback progress (MySQL 8.0)
CREATE TABLE IF NOT EXISTS watch_progress (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    episode_id VARCHAR(100) NOT NULL,
    asset_id VARCHAR(100) NOT NULL,
    position_ms BIGINT NOT NULL CHECK (position_ms >= 0),
    opt_lock_version BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_watch_progress_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_watch_progress_episode FOREIGN KEY (episode_id) REFERENCES catalog_episodes(id) ON DELETE CASCADE,
    CONSTRAINT uq_watch_progress_user_episode UNIQUE (user_id, episode_id),
    INDEX idx_watch_progress_user_updated (user_id, updated_at)
);
