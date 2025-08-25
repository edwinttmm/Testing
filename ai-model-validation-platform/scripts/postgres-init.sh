#!/bin/bash
set -e

echo "🔧 PostgreSQL Initialization Script Starting..."

# Wait for PostgreSQL to be fully ready
echo "⏳ Waiting for PostgreSQL to be fully operational..."
until pg_isready -h localhost -p 5432 -U "${POSTGRES_USER:-postgres}"; do
    echo "PostgreSQL is unavailable - sleeping"
    sleep 2
done

echo "✅ PostgreSQL is ready!"

# Test database connection
echo "🔍 Testing database connection..."
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname "${POSTGRES_DB:-vru_validation}" <<-EOSQL
    SELECT version();
    SELECT current_database();
    \l
EOSQL

echo "✅ PostgreSQL initialization completed successfully!"