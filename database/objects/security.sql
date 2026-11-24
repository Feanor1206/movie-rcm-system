DROP TEMPORARY TABLE IF EXISTS dippie_account_password_guard;
CREATE TEMPORARY TABLE dippie_account_password_guard (all_account_passwords_required INT PRIMARY KEY);
INSERT INTO dippie_account_password_guard VALUES (1);
INSERT INTO dippie_account_password_guard
SELECT 1 WHERE COALESCE(CHAR_LENGTH(@dippie_db_app_password), 0) = 0
            OR COALESCE(CHAR_LENGTH(@dippie_db_readonly_password), 0) = 0
            OR COALESCE(CHAR_LENGTH(@dippie_db_admin_password), 0) = 0;
DROP TEMPORARY TABLE dippie_account_password_guard;

SET @dippie_saved_sql_mode = @@SESSION.sql_mode;
SET SESSION sql_mode = TRIM(BOTH ',' FROM REPLACE(CONCAT(',', @@SESSION.sql_mode, ','), ',NO_BACKSLASH_ESCAPES,', ','));
SET @dippie_accounts = CONCAT(
    '''dippie_app''@''%'' IDENTIFIED BY ', QUOTE(@dippie_db_app_password),
    ', ''dippie_readonly''@''%'' IDENTIFIED BY ', QUOTE(@dippie_db_readonly_password),
    ', ''dippie_admin''@''%'' IDENTIFIED BY ', QUOTE(@dippie_db_admin_password)
);

SET @dippie_ddl = CONCAT('CREATE USER IF NOT EXISTS ', @dippie_accounts);
PREPARE dippie_permissions FROM @dippie_ddl;
EXECUTE dippie_permissions;
DEALLOCATE PREPARE dippie_permissions;

SET @dippie_ddl = CONCAT('ALTER USER ', @dippie_accounts);
PREPARE dippie_permissions FROM @dippie_ddl;
EXECUTE dippie_permissions;
DEALLOCATE PREPARE dippie_permissions;
SET @dippie_accounts = NULL, @dippie_ddl = NULL,
    @dippie_db_app_password = NULL, @dippie_db_readonly_password = NULL, @dippie_db_admin_password = NULL;
SET SESSION sql_mode = @dippie_saved_sql_mode;

REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'dippie_app'@'%', 'dippie_readonly'@'%', 'dippie_admin'@'%';

SET @dippie_schema = CONCAT('`', REPLACE(DATABASE(), '`', '``'), '`');
SET @dippie_grant_schema = IF(@@GLOBAL.partial_revokes, @dippie_schema,
    REPLACE(REPLACE(@dippie_schema, '_', CONCAT(CHAR(92), '_')), '%', CONCAT(CHAR(92), '%')));

SET @dippie_ddl = CONCAT('GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE ON ', @dippie_grant_schema, '.* TO ''dippie_app''@''%''');
PREPARE dippie_permissions FROM @dippie_ddl;
EXECUTE dippie_permissions;
DEALLOCATE PREPARE dippie_permissions;

SET @dippie_ddl = CONCAT('GRANT ALL PRIVILEGES ON ', @dippie_grant_schema, '.* TO ''dippie_admin''@''%''');
PREPARE dippie_permissions FROM @dippie_ddl;
EXECUTE dippie_permissions;
DEALLOCATE PREPARE dippie_permissions;

SET @dippie_ddl = CONCAT('GRANT SELECT ON ', @dippie_schema, '.v_published_episodes TO ''dippie_readonly''@''%''');
PREPARE dippie_permissions FROM @dippie_ddl;
EXECUTE dippie_permissions;
DEALLOCATE PREPARE dippie_permissions;

SET @dippie_ddl = CONCAT('GRANT SELECT ON ', @dippie_schema, '.v_genre_stats TO ''dippie_readonly''@''%''');
PREPARE dippie_permissions FROM @dippie_ddl;
EXECUTE dippie_permissions;
DEALLOCATE PREPARE dippie_permissions;

SET @dippie_ddl = CONCAT('GRANT SELECT ON ', @dippie_schema, '.v_user_watch_history TO ''dippie_readonly''@''%''');
PREPARE dippie_permissions FROM @dippie_ddl;
EXECUTE dippie_permissions;
DEALLOCATE PREPARE dippie_permissions;

SET @dippie_ddl = CONCAT('GRANT SELECT ON ', @dippie_schema, '.v_movie_rating_summary TO ''dippie_readonly''@''%''');
PREPARE dippie_permissions FROM @dippie_ddl;
EXECUTE dippie_permissions;
DEALLOCATE PREPARE dippie_permissions;
