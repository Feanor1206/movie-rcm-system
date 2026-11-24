DROP TRIGGER IF EXISTS trg_episode_audit_update;
DROP TRIGGER IF EXISTS trg_episode_audit_delete;
DROP TRIGGER IF EXISTS trg_watch_progress_duration_insert;
DROP TRIGGER IF EXISTS trg_watch_progress_duration_update;

DELIMITER $$

CREATE TRIGGER trg_episode_audit_update
AFTER UPDATE ON catalog_episodes
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, record_id, operation, old_values, new_values, mysql_user)
    VALUES (
        'catalog_episodes', OLD.id, 'UPDATE',
        JSON_OBJECT(
            'id', OLD.id, 'series_id', OLD.series_id,
            'season_id', OLD.season_id, 'number', OLD.number,
            'title', OLD.title, 'aliases_json', OLD.aliases_json,
            'synopsis', OLD.synopsis, 'translations_json', OLD.translations_json,
            'kind', OLD.kind, 'release_date', OLD.release_date,
            'duration_ms', OLD.duration_ms, 'genre_ids_json', OLD.genre_ids_json,
            'primary_language', OLD.primary_language, 'orders_json', OLD.orders_json,
            'links_json', OLD.links_json, 'character_ids_json', OLD.character_ids_json,
            'plot_facts_json', OLD.plot_facts_json, 'keywords_json', OLD.keywords_json,
            'themes_json', OLD.themes_json, 'attributes_json', OLD.attributes_json,
            'ratings_json', OLD.ratings_json, 'artworks_json', OLD.artworks_json,
            'credits_json', OLD.credits_json, 'record_json', OLD.record_json,
            'publication_status', OLD.publication_status, 'raw_json', OLD.raw_json,
            'revision', OLD.revision, 'opt_lock_version', OLD.opt_lock_version,
            'updated_at', OLD.updated_at
        ),
        JSON_OBJECT(
            'id', NEW.id, 'series_id', NEW.series_id,
            'season_id', NEW.season_id, 'number', NEW.number,
            'title', NEW.title, 'aliases_json', NEW.aliases_json,
            'synopsis', NEW.synopsis, 'translations_json', NEW.translations_json,
            'kind', NEW.kind, 'release_date', NEW.release_date,
            'duration_ms', NEW.duration_ms, 'genre_ids_json', NEW.genre_ids_json,
            'primary_language', NEW.primary_language, 'orders_json', NEW.orders_json,
            'links_json', NEW.links_json, 'character_ids_json', NEW.character_ids_json,
            'plot_facts_json', NEW.plot_facts_json, 'keywords_json', NEW.keywords_json,
            'themes_json', NEW.themes_json, 'attributes_json', NEW.attributes_json,
            'ratings_json', NEW.ratings_json, 'artworks_json', NEW.artworks_json,
            'credits_json', NEW.credits_json, 'record_json', NEW.record_json,
            'publication_status', NEW.publication_status, 'raw_json', NEW.raw_json,
            'revision', NEW.revision, 'opt_lock_version', NEW.opt_lock_version,
            'updated_at', NEW.updated_at
        ),
        USER()
    );
END$$

CREATE TRIGGER trg_episode_audit_delete
AFTER DELETE ON catalog_episodes
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, record_id, operation, old_values, new_values, mysql_user)
    VALUES (
        'catalog_episodes', OLD.id, 'DELETE',
        JSON_OBJECT(
            'id', OLD.id, 'series_id', OLD.series_id,
            'season_id', OLD.season_id, 'number', OLD.number,
            'title', OLD.title, 'aliases_json', OLD.aliases_json,
            'synopsis', OLD.synopsis, 'translations_json', OLD.translations_json,
            'kind', OLD.kind, 'release_date', OLD.release_date,
            'duration_ms', OLD.duration_ms, 'genre_ids_json', OLD.genre_ids_json,
            'primary_language', OLD.primary_language, 'orders_json', OLD.orders_json,
            'links_json', OLD.links_json, 'character_ids_json', OLD.character_ids_json,
            'plot_facts_json', OLD.plot_facts_json, 'keywords_json', OLD.keywords_json,
            'themes_json', OLD.themes_json, 'attributes_json', OLD.attributes_json,
            'ratings_json', OLD.ratings_json, 'artworks_json', OLD.artworks_json,
            'credits_json', OLD.credits_json, 'record_json', OLD.record_json,
            'publication_status', OLD.publication_status, 'raw_json', OLD.raw_json,
            'revision', OLD.revision, 'opt_lock_version', OLD.opt_lock_version,
            'updated_at', OLD.updated_at
        ),
        NULL,
        USER()
    );
END$$

CREATE TRIGGER trg_watch_progress_duration_insert
BEFORE INSERT ON watch_progress
FOR EACH ROW
BEGIN
    DECLARE episode_duration_ms BIGINT;
    SELECT duration_ms INTO episode_duration_ms FROM catalog_episodes WHERE id = NEW.episode_id FOR SHARE;
    IF NEW.position_ms > episode_duration_ms THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Watch position exceeds episode duration_ms.';
    END IF;
END$$

CREATE TRIGGER trg_watch_progress_duration_update
BEFORE UPDATE ON watch_progress
FOR EACH ROW
BEGIN
    DECLARE episode_duration_ms BIGINT;
    SELECT duration_ms INTO episode_duration_ms FROM catalog_episodes WHERE id = NEW.episode_id FOR SHARE;
    IF NEW.position_ms > episode_duration_ms THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Watch position exceeds episode duration_ms.';
    END IF;
END$$

DELIMITER ;
