#!/bin/bash
echo "🚨 EMERGENCY DATABASE RESET"
echo "=============================="
echo ""
echo "⚠️  WARNING: This will completely destroy and recreate your database!"
echo "All data will be permanently lost!"
echo ""
read -p "Type 'YES' to proceed with database reset: " response

if [ "$response" != "YES" ]; then
    echo "❌ Operation cancelled"
    exit 1
fi

echo ""
echo "🔌 Stopping backend to close database connections..."
docker-compose stop backend

echo ""
echo "🗑️ Dropping and recreating database..."
docker-compose exec postgres psql -U postgres -c "DROP DATABASE IF EXISTS vru_validation;"
docker-compose exec postgres psql -U postgres -c "CREATE DATABASE vru_validation;"

echo ""
echo "🚀 Starting backend with fresh database..."
docker-compose start backend

echo ""
echo "✅ Database reset completed!"
echo ""
echo "Monitor the backend logs to see clean initialization:"
echo "docker logs -f ai-model-validation-platform_backend_1"