DROP VIEW IF EXISTS v_genre_stats, v_user_watch_history, v_movie_rating_summary, v_published_episodes;

CREATE SQL SECURITY DEFINER VIEW v_published_episodes AS
SELECT e.id AS episode_id, e.title AS episode_title, e.number AS episode_number,
       s.id AS series_id, s.title AS series_title,
       t.id AS season_id, t.title AS season_title, t.number AS season_number,
       e.kind, e.release_date, e.duration_ms, e.updated_at
FROM catalog_episodes AS e
JOIN catalog_series AS s ON s.id = e.series_id
LEFT JOIN catalog_seasons AS t ON t.series_id = e.series_id AND t.id = e.season_id
WHERE e.publication_status = 'ready';

CREATE SQL SECURITY DEFINER VIEW v_genre_stats AS
SELECT g.id AS genre_id, g.labels_json,
       COALESCE(stats.episode_count, 0) AS episode_count,
       COALESCE(stats.total_duration_ms, 0) AS total_duration_ms
FROM catalog_genres AS g
LEFT JOIN (
    SELECT eg.genre_id, COUNT(*) AS episode_count, SUM(e.duration_ms) AS total_duration_ms
    FROM catalog_episodes AS e
    JOIN catalog_episode_genres AS eg ON eg.episode_id = e.id
    WHERE e.publication_status = 'ready'
    GROUP BY eg.genre_id
) AS stats ON stats.genre_id = g.id;

CREATE SQL SECURITY DEFINER VIEW v_user_watch_history AS
SELECT p.user_id, p.episode_id, e.title AS episode_title, e.series_id, s.title AS series_title,
       p.asset_id, p.position_ms, e.duration_ms, e.publication_status, p.updated_at
FROM watch_progress AS p
JOIN catalog_episodes AS e ON e.id = p.episode_id
JOIN catalog_series AS s ON s.id = e.series_id;

CREATE SQL SECURITY DEFINER VIEW v_movie_rating_summary AS
SELECT m.id AS movie_id, m.title AS movie_title,
       COUNT(r.id) AS rating_count, CAST(AVG(r.rating) AS DECIMAL(4,2)) AS average_rating
FROM movies AS m
LEFT JOIN movie_ratings AS r ON r.movie_id = m.id
GROUP BY m.id, m.title;
