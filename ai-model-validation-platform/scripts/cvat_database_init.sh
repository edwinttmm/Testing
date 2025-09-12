#!/bin/bash

# CVAT Database Initialization Script
# Resolves PostgreSQL "auth_user" relation does not exist error

set -e

echo "🔧 CVAT Database Initialization Starting..."

# Configuration
CVAT_CONTAINER="ai_validation_cvat"
CVAT_DB_CONTAINER="ai_validation_cvat_db"
DB_NAME="cvat"
DB_USER="root"
DB_PASSWORD="cvat_password"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

echo_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to wait for database to be ready
wait_for_database() {
    echo_info "Waiting for CVAT database to be ready..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker exec $CVAT_DB_CONTAINER pg_isready -U $DB_USER -d $DB_NAME &> /dev/null; then
            echo_success "Database is ready"
            return 0
        fi
        
        echo_info "Attempt $attempt/$max_attempts - waiting for database..."
        sleep 2
        ((attempt++))
    done
    
    echo_error "Database did not become ready within expected time"
    return 1
}

# Function to check if Django tables exist
check_django_tables() {
    echo_info "Checking if Django tables exist..."
    
    local tables_exist=$(docker exec $CVAT_DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'auth_user';" 2>/dev/null | tr -d ' ' || echo "0")
    
    if [ "$tables_exist" = "1" ]; then
        echo_success "Django auth_user table exists"
        return 0
    else
        echo_warning "Django auth_user table does not exist"
        return 1
    fi
}

# Function to run Django migrations
run_django_migrations() {
    echo_info "Running Django migrations in CVAT container..."
    
    # Check if CVAT container is running
    if ! docker ps | grep -q $CVAT_CONTAINER; then
        echo_error "CVAT container is not running"
        return 1
    fi
    
    # Run Django migrations
    echo_info "Executing Django makemigrations..."
    docker exec $CVAT_CONTAINER bash -c "cd /home/django && python manage.py makemigrations" || {
        echo_warning "makemigrations completed with warnings - this is often normal"
    }
    
    echo_info "Executing Django migrate..."
    docker exec $CVAT_CONTAINER bash -c "cd /home/django && python manage.py migrate" || {
        echo_error "Django migrate failed"
        return 1
    }
    
    echo_success "Django migrations completed"
    return 0
}

# Function to create Django superuser
create_superuser() {
    echo_info "Creating Django superuser..."
    
    # Check if superuser already exists
    local superuser_exists=$(docker exec $CVAT_CONTAINER bash -c "cd /home/django && python manage.py shell -c \"from django.contrib.auth.models import User; print(User.objects.filter(is_superuser=True).exists())\"" 2>/dev/null || echo "False")
    
    if [ "$superuser_exists" = "True" ]; then
        echo_success "Django superuser already exists"
        return 0
    fi
    
    # Create superuser
    docker exec $CVAT_CONTAINER bash -c "cd /home/django && python manage.py shell -c \"
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@cvat.local', 'admin123')
    print('Superuser created')
else:
    print('Superuser already exists')
\"" || {
        echo_warning "Superuser creation completed with warnings"
    }
    
    echo_success "Django superuser setup completed"
    return 0
}

# Function to verify database schema
verify_schema() {
    echo_info "Verifying database schema..."
    
    # Check critical Django tables
    local critical_tables=("auth_user" "auth_permission" "django_content_type" "django_migrations")
    local missing_tables=()
    
    for table in "${critical_tables[@]}"; do
        local table_exists=$(docker exec $CVAT_DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '$table';" 2>/dev/null | tr -d ' ' || echo "0")
        
        if [ "$table_exists" = "0" ]; then
            missing_tables+=("$table")
        fi
    done
    
    if [ ${#missing_tables[@]} -eq 0 ]; then
        echo_success "All critical Django tables exist"
        return 0
    else
        echo_error "Missing tables: ${missing_tables[*]}"
        return 1
    fi
}

# Function to show database status
show_database_status() {
    echo_info "Database Status:"
    
    # Show table count
    local table_count=$(docker exec $CVAT_DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ' || echo "0")
    echo "  - Tables: $table_count"
    
    # Show user count
    local user_count=$(docker exec $CVAT_DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM auth_user;" 2>/dev/null | tr -d ' ' || echo "0")
    echo "  - Users: $user_count"
    
    # Show migration status
    echo_info "Checking Django migration status..."
    docker exec $CVAT_CONTAINER bash -c "cd /home/django && python manage.py showmigrations --plan" 2>/dev/null | head -10 || echo "  - Unable to check migrations"
}

# Main execution
main() {
    echo_info "Starting CVAT Database Initialization..."
    
    # Step 1: Wait for database
    if ! wait_for_database; then
        echo_error "Database initialization failed - database not ready"
        exit 1
    fi
    
    # Step 2: Check current state
    if check_django_tables; then
        echo_info "Django tables already exist - checking integrity..."
        if verify_schema; then
            echo_success "Database schema is complete"
            show_database_status
            exit 0
        else
            echo_warning "Schema incomplete - attempting repair..."
        fi
    fi
    
    # Step 3: Run migrations
    if ! run_django_migrations; then
        echo_error "Failed to run Django migrations"
        exit 1
    fi
    
    # Step 4: Create superuser
    if ! create_superuser; then
        echo_warning "Superuser creation failed - continuing anyway"
    fi
    
    # Step 5: Final verification
    if verify_schema; then
        echo_success "✅ CVAT Database initialization completed successfully!"
        show_database_status
    else
        echo_error "❌ Database initialization completed but schema verification failed"
        exit 1
    fi
}

# Handle script arguments
case "${1:-}" in
    --check)
        echo_info "Checking database status only..."
        check_django_tables && verify_schema && show_database_status
        ;;
    --migrate-only)
        echo_info "Running migrations only..."
        wait_for_database && run_django_migrations
        ;;
    --verify)
        echo_info "Verifying schema only..."
        verify_schema && show_database_status
        ;;
    *)
        main
        ;;
esac