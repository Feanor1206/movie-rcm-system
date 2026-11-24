#!/bin/bash
(
    set -euo pipefail
    encode_password() {
        printf '%s' "$1" | od -An -v -t x1 | tr -d ' \n'
    }

    app_password=$(encode_password "${DIPPIE_DB_APP_PASSWORD:?DIPPIE_DB_APP_PASSWORD required}")
    readonly_password=$(encode_password "${DIPPIE_DB_READONLY_PASSWORD:?DIPPIE_DB_READONLY_PASSWORD required}")
    admin_password=$(encode_password "${DIPPIE_DB_ADMIN_PASSWORD:?DIPPIE_DB_ADMIN_PASSWORD required}")
    {
        printf 'SET @dippie_db_app_password = CONVERT(0x%s USING utf8mb4);\n' "$app_password"
        printf 'SET @dippie_db_readonly_password = CONVERT(0x%s USING utf8mb4);\n' "$readonly_password"
        printf 'SET @dippie_db_admin_password = CONVERT(0x%s USING utf8mb4);\n' "$admin_password"
        for name in views functions procedures triggers security; do
            cat "/opt/dippie/database-objects/$name.sql" || exit 1
            printf '\n'
        done
    } | MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=socket --user=root --batch \
        --default-character-set=utf8mb4 --database="$MYSQL_DATABASE"
)
