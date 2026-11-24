DROP FUNCTION IF EXISTS fn_movie_avg_rating;
DROP FUNCTION IF EXISTS fn_episode_progress_pct;

DELIMITER $$

CREATE FUNCTION fn_movie_avg_rating(movie_key VARCHAR(100))
RETURNS DECIMAL(4,2)
READS SQL DATA
SQL SECURITY INVOKER
BEGIN
    DECLARE average_rating DECIMAL(4,2);
    SELECT AVG(r.rating) INTO average_rating
    FROM movie_ratings AS r WHERE r.movie_id = movie_key;
    RETURN average_rating;
END$$

CREATE FUNCTION fn_episode_progress_pct(user_key BIGINT, episode_key VARCHAR(100))
RETURNS DECIMAL(5,2)
READS SQL DATA
SQL SECURITY INVOKER
BEGIN
    DECLARE progress_pct DECIMAL(5,2);
    SELECT COALESCE(MAX(LEAST(100, 100.0 * p.position_ms / NULLIF(e.duration_ms, 0))), 0)
    INTO progress_pct
    FROM watch_progress AS p
    JOIN catalog_episodes AS e ON e.id = p.episode_id
    WHERE p.user_id = user_key AND p.episode_id = episode_key;
    RETURN progress_pct;
END$$

DELIMITER ;
