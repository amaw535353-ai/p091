#!/bin/sh
set -eu
# Values are generated as hexadecimal by bootstrap_live.py; refuse arbitrary SQL.
for secret in "$APP_DATABASE_PASSWORD" "$FGA_DATABASE_PASSWORD" "$KEYCLOAK_DATABASE_PASSWORD" "$NEXTCLOUD_DATABASE_PASSWORD"; do
  case "$secret" in *[!a-f0-9]*|'') echo 'Invalid generated database password format' >&2; exit 1;; esac
  [ "${#secret}" -eq 48 ] || { echo 'Invalid generated database password length' >&2; exit 1; }
done
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<SQL
CREATE ROLE p091 LOGIN PASSWORD '$APP_DATABASE_PASSWORD';
CREATE DATABASE p091 OWNER p091;
CREATE ROLE openfga LOGIN PASSWORD '$FGA_DATABASE_PASSWORD';
CREATE DATABASE openfga OWNER openfga;
CREATE ROLE keycloak LOGIN PASSWORD '$KEYCLOAK_DATABASE_PASSWORD';
CREATE DATABASE keycloak OWNER keycloak;
CREATE ROLE nextcloud LOGIN PASSWORD '$NEXTCLOUD_DATABASE_PASSWORD';
CREATE DATABASE nextcloud OWNER nextcloud;
SQL
