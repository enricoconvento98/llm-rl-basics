#!/bin/bash
# Runs once, on the first start of an empty data volume.
# POSTGRES_DB (rltrading) is created by the image; this adds a separate database for MLflow.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    CREATE DATABASE mlflow OWNER "$POSTGRES_USER";
SQL
