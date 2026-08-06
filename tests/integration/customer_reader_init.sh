#!/bin/sh
set -eu

if [ -z "${CUSTOMER_READER_USER:-}" ] || [ -z "${CUSTOMER_READER_PASSWORD:-}" ]; then
    echo "Customer reader credentials are required" >&2
    exit 1
fi

psql --set=ON_ERROR_STOP=1 \
    --set=database_name="$POSTGRES_DB" \
    --set=reader_user="$CUSTOMER_READER_USER" \
    --set=reader_password="$CUSTOMER_READER_PASSWORD" \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" <<'SQL'
REVOKE CREATE ON DATABASE :"database_name" FROM PUBLIC;
REVOKE TEMPORARY ON DATABASE :"database_name" FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE ROLE :"reader_user"
    LOGIN
    PASSWORD :'reader_password'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT;

REVOKE ALL ON DATABASE :"database_name" FROM :"reader_user";
GRANT CONNECT ON DATABASE :"database_name" TO :"reader_user";
GRANT USAGE ON SCHEMA business TO :"reader_user";
GRANT SELECT ON ALL TABLES IN SCHEMA business TO :"reader_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA business
    GRANT SELECT ON TABLES TO :"reader_user";
SQL
