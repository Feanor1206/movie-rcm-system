DROP PROCEDURE IF EXISTS sp_add_favorite;
DROP PROCEDURE IF EXISTS sp_next_episode;
DROP PROCEDURE IF EXISTS sp_publish_episode;

DELIMITER $$

CREATE PROCEDURE sp_add_favorite(IN user_key BIGINT, IN movie_key VARCHAR(100))
MODIFIES SQL DATA
SQL SECURITY INVOKER
BEGIN
    DECLARE favorite_key BIGINT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    INSERT INTO favorite_items (user_id, movie_id)
    VALUES (user_key, movie_key)
    ON DUPLICATE KEY UPDATE id = id;
    SELECT id INTO favorite_key
    FROM favorite_items WHERE user_id = user_key AND movie_id = movie_key;
    COMMIT;

    SELECT f.id, f.user_id, f.movie_id, m.title AS movie_title, m.poster AS poster_url, f.added_at
    FROM favorite_items AS f JOIN movies AS m ON m.id = f.movie_id
    WHERE f.id = favorite_key;
END$$

CREATE PROCEDURE sp_next_episode(IN user_key BIGINT, IN series_key VARCHAR(100))
READS SQL DATA
SQL SECURITY INVOKER
BEGIN
    SELECT e.episode_id, e.episode_title, e.season_number, e.episode_number,
           COALESCE(p.position_ms, 0) AS resume_position_ms
    FROM v_published_episodes AS e
    LEFT JOIN watch_progress AS p ON p.user_id = user_key AND p.episode_id = e.episode_id
    WHERE e.series_id = series_key
      AND (p.id IS NULL OR e.duration_ms IS NULL OR p.position_ms < e.duration_ms)
    ORDER BY CASE WHEN p.position_ms > 0 THEN p.updated_at END DESC,
             e.season_number IS NULL, e.season_number, e.episode_number IS NULL, e.episode_number, e.episode_id
    LIMIT 1;
END$$

CREATE PROCEDURE sp_publish_episode(IN episode_key VARCHAR(100))
MODIFIES SQL DATA
SQL SECURITY INVOKER
BEGIN
    DECLARE metadata_ready BOOLEAN DEFAULT FALSE;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    SELECT COALESCE(TRIM(title) <> '' AND TRIM(synopsis) <> '' AND number > 0 AND duration_ms > 0, FALSE)
    INTO metadata_ready
    FROM catalog_episodes WHERE id = episode_key FOR UPDATE;

    IF NOT metadata_ready OR NOT EXISTS (SELECT 1 FROM catalog_episode_genres WHERE episode_id = episode_key) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Episode metadata requires title, synopsis, number, duration and a genre.';
    END IF;

    UPDATE catalog_episodes
    SET publication_status = 'ready',
        record_json = JSON_SET(
            CASE WHEN JSON_VALID(record_json) THEN
                CASE WHEN JSON_TYPE(record_json) = 'OBJECT' THEN record_json ELSE JSON_OBJECT() END
            ELSE JSON_OBJECT() END,
            '$.status', 'ready'
        )
    WHERE id = episode_key AND publication_status <> 'ready';
    COMMIT;
END$$

DELIMITER ;
