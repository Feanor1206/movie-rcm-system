SELECT s.title AS series_title, se.title AS season_title, e.number, e.title AS episode_title, c.name AS character_name
FROM catalog_episodes AS e
JOIN catalog_series AS s ON s.id = e.series_id
LEFT JOIN catalog_seasons AS se ON se.series_id = e.series_id AND se.id = e.season_id
JOIN catalog_episode_characters AS ec ON ec.episode_id = e.id
JOIN catalog_characters AS c ON c.id = ec.character_id
WHERE e.publication_status = 'ready'
ORDER BY s.title, se.number, e.number, e.id, c.id
LIMIT 50;

SELECT s.id, s.title, COUNT(e.id) AS ready_episodes, ROUND(SUM(e.duration_ms) / 3600000, 1) AS total_hours
FROM catalog_series AS s
JOIN catalog_episodes AS e ON e.series_id = s.id
WHERE e.publication_status = 'ready'
GROUP BY s.id, s.title
HAVING COUNT(e.id) >= 20
ORDER BY ready_episodes DESC, s.id;

WITH series_duration AS (
    SELECT series_id, AVG(duration_ms) AS average_duration_ms
    FROM catalog_episodes
    WHERE publication_status = 'ready'
    GROUP BY series_id
)
SELECT e.id, e.title, e.duration_ms, e.series_id
FROM series_duration AS d
JOIN catalog_episodes AS e ON e.series_id = d.series_id
WHERE e.publication_status = 'ready' AND e.duration_ms > d.average_duration_ms
ORDER BY e.series_id, e.duration_ms DESC, e.id
LIMIT 50;

SELECT e.id, e.title
FROM catalog_episodes AS e
WHERE e.publication_status = 'ready'
  AND NOT EXISTS (
    SELECT 1 FROM catalog_episode_assets AS ea
    JOIN catalog_media_assets AS a ON a.id = ea.media_asset_id
    WHERE ea.episode_id = e.id AND a.content_type = 'video' AND a.role = 'feature'
      AND a.access_policy = 'public' AND a.enabled = 1
)
ORDER BY e.id
LIMIT 50;

SELECT u.id, u.username,
       (SELECT MAX(r.rating) FROM movie_ratings AS r WHERE r.user_id = u.id) AS highest_rating
FROM users AS u
WHERE EXISTS (SELECT 1 FROM movie_ratings AS r WHERE r.user_id = u.id AND r.rating >= 9)
  AND EXISTS (SELECT 1 FROM favorite_items AS f WHERE f.user_id = u.id)
ORDER BY u.id;

SELECT series_id, id, title, duration_ms,
       RANK() OVER (PARTITION BY series_id ORDER BY duration_ms DESC) AS duration_rank
FROM catalog_episodes
WHERE publication_status = 'ready' AND duration_ms IS NOT NULL
ORDER BY series_id, duration_rank, id
LIMIT 100;

SELECT p.user_id, e.series_id, e.id, e.number, p.updated_at,
       LAG(e.number) OVER (PARTITION BY p.user_id, e.series_id ORDER BY p.updated_at, p.id) AS previous_episode_number
FROM watch_progress AS p
JOIN catalog_episodes AS e ON e.id = p.episode_id
ORDER BY p.user_id, e.series_id, p.updated_at, p.id;

WITH genre_counts AS (
    SELECT eg.genre_id, COUNT(*) AS episode_count
    FROM catalog_episode_genres AS eg
    JOIN catalog_episodes AS e ON e.id = eg.episode_id AND e.publication_status = 'ready'
    GROUP BY eg.genre_id
)
SELECT genre_id, episode_count,
       ROUND(100 * episode_count / SUM(episode_count) OVER (), 2) AS share_pct
FROM genre_counts
ORDER BY episode_count DESC, genre_id;

WITH RECURSIVE minute_buckets AS (
    SELECT 0 AS bucket_start
    UNION ALL
    SELECT bucket_start + 5 FROM minute_buckets WHERE bucket_start < 55
), episode_counts AS (
    SELECT (duration_ms DIV 300000) * 5 AS bucket_start, COUNT(*) AS episode_count
    FROM catalog_episodes
    WHERE publication_status = 'ready' AND duration_ms < 3600000
    GROUP BY bucket_start
)
SELECT b.bucket_start, b.bucket_start + 5 AS bucket_end, COALESCE(c.episode_count, 0) AS episode_count
FROM minute_buckets AS b
LEFT JOIN episode_counts AS c ON c.bucket_start = b.bucket_start
ORDER BY b.bucket_start;

SELECT w.user_id, m.id AS movie_id, m.title FROM watchlist_items AS w JOIN movies AS m ON m.id = w.movie_id
UNION
SELECT f.user_id, m.id, m.title FROM favorite_items AS f JOIN movies AS m ON m.id = f.movie_id
ORDER BY user_id, movie_id;

SELECT r.movie_id, r.movie_title, r.rating_count, fn_movie_avg_rating(r.movie_id) AS average_rating
FROM v_movie_rating_summary AS r
WHERE r.rating_count > 0
ORDER BY average_rating DESC, r.rating_count DESC, r.movie_id
LIMIT 20;

WITH appearances AS (
    SELECT ec.character_id, COUNT(DISTINCT e.series_id) AS series_count, COUNT(*) AS episode_count
    FROM catalog_episodes AS e
    JOIN catalog_episode_characters AS ec ON ec.episode_id = e.id
    WHERE e.publication_status = 'ready'
    GROUP BY ec.character_id
    ORDER BY episode_count DESC, ec.character_id
    LIMIT 20
)
SELECT a.character_id, c.name, a.series_count, a.episode_count
FROM appearances AS a
JOIN catalog_characters AS c ON c.id = a.character_id
ORDER BY a.episode_count DESC, a.character_id;

SELECT e.id, e.title, e.release_date, s.title AS series_title, se.title AS season_title
FROM catalog_episodes AS e
JOIN catalog_series AS s ON s.id = e.series_id
LEFT JOIN catalog_seasons AS se ON se.series_id = e.series_id AND se.id = e.season_id
WHERE e.publication_status = 'ready' AND e.release_date IS NOT NULL
ORDER BY e.release_date DESC, e.id DESC
LIMIT 20;

WITH status_counts AS (
    SELECT publication_status, series_id, COUNT(*) AS episode_count
    FROM catalog_episodes
    GROUP BY publication_status, series_id
), series_counts AS (
    SELECT series_id, CAST(SUM(episode_count) AS UNSIGNED) AS episode_count,
           SUM(IF(publication_status = 'draft', episode_count, 0)) AS draft_count,
           SUM(IF(publication_status = 'ready', episode_count, 0)) AS ready_count,
           SUM(IF(publication_status = 'archived', episode_count, 0)) AS archived_count
    FROM status_counts
    GROUP BY series_id
    ORDER BY draft_count DESC, series_id
    LIMIT 20
)
SELECT s.id, s.title, c.episode_count, c.draft_count, c.ready_count, c.archived_count
FROM series_counts AS c
JOIN catalog_series AS s ON s.id = c.series_id
ORDER BY c.draft_count DESC, s.id;

SELECT a.id AS asset_id, a.role, COUNT(ea.episode_id) AS episode_count
FROM catalog_media_assets AS a
JOIN catalog_episode_assets AS ea ON ea.media_asset_id = a.id
GROUP BY a.id, a.role
HAVING COUNT(ea.episode_id) > 1
ORDER BY episode_count DESC, a.id
LIMIT 20;

SELECT e.episode_id, e.episode_title
FROM v_published_episodes AS e
WHERE NOT EXISTS (
    SELECT 1 FROM catalog_text_tracks AS t
    WHERE t.episode_id = e.episode_id AND t.kind IN ('subtitle', 'transcript')
) AND NOT EXISTS (
    SELECT 1 FROM catalog_episode_assets AS ea
    JOIN catalog_text_tracks AS t ON t.media_asset_id = ea.media_asset_id
    WHERE ea.episode_id = e.episode_id AND t.kind IN ('subtitle', 'transcript')
)
ORDER BY e.episode_id
LIMIT 50;

SELECT h.user_id, h.episode_id, h.position_ms,
       SUM(h.position_ms) OVER (PARTITION BY h.user_id ORDER BY h.updated_at, h.episode_id ROWS UNBOUNDED PRECEDING) AS cumulative_positions_ms
FROM v_user_watch_history AS h
ORDER BY h.user_id, h.updated_at, h.episode_id;

SELECT genre_id, episode_count, ROUND(total_duration_ms / 3600000, 2) AS total_hours
FROM v_genre_stats
WHERE episode_count > 0
ORDER BY episode_count DESC, genre_id
LIMIT 20;

SELECT e.episode_id, e.episode_title, COUNT(s.id) AS scene_count,
       SUM(s.end_ms - s.start_ms) AS scene_intervals_ms
FROM v_published_episodes AS e
JOIN catalog_scenes AS s ON s.episode_id = e.episode_id
GROUP BY e.episode_id, e.episode_title
ORDER BY scene_count DESC, e.episode_id
LIMIT 20;

SELECT record_id, operation, mysql_user, action_at,
       JSON_UNQUOTE(JSON_EXTRACT(old_values, '$.publication_status')) AS old_status,
       JSON_UNQUOTE(JSON_EXTRACT(new_values, '$.publication_status')) AS new_status
FROM audit_log
WHERE table_name = 'catalog_episodes'
ORDER BY action_at DESC, id DESC
LIMIT 20;
