SELECT e.id, e.title, e.duration_ms, e.series_id
FROM catalog_episodes AS e
WHERE e.publication_status = 'ready'
  AND e.duration_ms > (
    SELECT AVG(sibling.duration_ms)
    FROM catalog_episodes AS sibling
    WHERE sibling.series_id = e.series_id AND sibling.publication_status = 'ready'
)
ORDER BY e.series_id, e.duration_ms DESC, e.id
LIMIT 50;

WITH RECURSIVE minute_buckets AS (
    SELECT 0 AS bucket_start
    UNION ALL
    SELECT bucket_start + 5 FROM minute_buckets WHERE bucket_start < 55
)
SELECT b.bucket_start, b.bucket_start + 5 AS bucket_end, COUNT(e.id) AS episode_count
FROM minute_buckets AS b
LEFT JOIN catalog_episodes AS e
    ON e.duration_ms >= b.bucket_start * 60000
   AND e.duration_ms < (b.bucket_start + 5) * 60000
   AND e.publication_status = 'ready'
GROUP BY b.bucket_start
ORDER BY b.bucket_start;

SELECT ec.character_id, c.name, COUNT(DISTINCT e.series_id) AS series_count, COUNT(*) AS episode_count
FROM catalog_episode_characters AS ec
JOIN catalog_characters AS c ON c.id = ec.character_id
JOIN catalog_episodes AS e ON e.id = ec.episode_id
WHERE e.publication_status = 'ready'
GROUP BY ec.character_id, c.name
ORDER BY episode_count DESC, ec.character_id
LIMIT 20;

SELECT s.id, s.title, COUNT(e.id) AS episode_count,
       SUM(e.publication_status = 'draft') AS draft_count,
       SUM(e.publication_status = 'ready') AS ready_count,
       SUM(e.publication_status = 'archived') AS archived_count
FROM catalog_series AS s
JOIN catalog_episodes AS e ON e.series_id = s.id
GROUP BY s.id, s.title
ORDER BY draft_count DESC, s.id
LIMIT 20;

SELECT genre_id, episode_count, ROUND(total_duration_ms / 3600000, 2) AS total_hours
FROM v_genre_stats
WHERE episode_count > 0
ORDER BY episode_count DESC, genre_id
LIMIT 20;
