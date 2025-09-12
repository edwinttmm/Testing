#!/usr/bin/env python3
"""
Docker Compose Configuration Fixer
Fixes the docker-compose.yml to use consistent development credentials.
"""

import os
import sys
import yaml
from pathlib import Path

def fix_docker_compose():
    """Fix docker-compose.yml for consistent database configuration"""
    
    # Path to docker-compose.yml
    compose_path = Path(__file__).parent.parent.parent / 'docker-compose.yml'
    
    if not compose_path.exists():
        print(f"❌ docker-compose.yml not found at {compose_path}")
        return False
    
    print(f"🔧 Fixing docker-compose.yml at {compose_path}")
    
    # Backup original file
    backup_path = compose_path.with_suffix('.yml.backup')
    print(f"📄 Creating backup at {backup_path}")
    
    try:
        with open(compose_path, 'r') as f:
            original_content = f.read()
        
        with open(backup_path, 'w') as f:
            f.write(original_content)
        
        # Load and modify the compose configuration
        with open(compose_path, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        # Fix PostgreSQL service
        if 'services' in compose_data and 'postgres' in compose_data['services']:
            postgres_service = compose_data['services']['postgres']
            
            # Update environment variables to use development defaults
            postgres_env = {
                'POSTGRES_DB': '${POSTGRES_DB:-vru_validation}',
                'POSTGRES_USER': '${POSTGRES_USER:-postgres}', 
                'POSTGRES_PASSWORD': '${POSTGRES_PASSWORD:-password}',
                'POSTGRES_INITDB_ARGS': '--encoding=UTF-8'
            }
            
            postgres_service['environment'] = postgres_env
            
            # Update health check
            healthcheck_test = [
                "CMD-SHELL", 
                "pg_isready -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-vru_validation}"
            ]
            
            if 'healthcheck' in postgres_service:
                postgres_service['healthcheck']['test'] = healthcheck_test
            
            print("✅ Fixed PostgreSQL service configuration")
        
        # Fix backend service environment
        if 'services' in compose_data and 'backend' in compose_data['services']:
            backend_service = compose_data['services']['backend']
            
            if 'environment' in backend_service:
                # Update backend environment to use consistent variables
                for i, env_var in enumerate(backend_service['environment']):
                    if isinstance(env_var, str):
                        # Fix database URL references
                        if env_var.startswith('- AIVALIDATION_DATABASE_URL='):
                            backend_service['environment'][i] = '- AIVALIDATION_DATABASE_URL=${DATABASE_URL:-postgresql://postgres:password@postgres:5432/vru_validation}'
                        elif env_var.startswith('- DATABASE_URL='):
                            backend_service['environment'][i] = '- DATABASE_URL=${DATABASE_URL:-postgresql://postgres:password@postgres:5432/vru_validation}'
                        elif env_var.startswith('- REDIS_URL='):
                            backend_service['environment'][i] = '- REDIS_URL=${REDIS_URL:-redis://redis:6379}'
                        elif env_var.startswith('- AIVALIDATION_REDIS_URL='):
                            backend_service['environment'][i] = '- AIVALIDATION_REDIS_URL=${REDIS_URL:-redis://redis:6379}'
            
            print("✅ Fixed backend service configuration")
        
        # Fix Redis service if it uses authentication
        if 'services' in compose_data and 'redis' in compose_data['services']:
            redis_service = compose_data['services']['redis']
            
            # Update Redis command to not require password in development
            if 'command' in redis_service:
                # Simple Redis without password for development
                redis_service['command'] = 'redis-server --appendonly yes'
                print("✅ Fixed Redis service configuration")
        
        # Write the updated configuration
        with open(compose_path, 'w') as f:
            yaml.dump(compose_data, f, default_flow_style=False, indent=2, sort_keys=False)
        
        print("✅ docker-compose.yml updated successfully")
        print(f"📄 Original backed up to {backup_path}")
        
        # Create a fixed environment file
        env_path = compose_path.parent / '.env.development.fixed'
        with open(env_path, 'w') as f:
            f.write("""# Fixed Development Environment Configuration
# This file contains the correct database credentials for development

# Environment
ENVIRONMENT=development
APP_ENV=development

# Database Configuration - Development
DATABASE_URL=postgresql://postgres:password@postgres:5432/vru_validation
AIVALIDATION_DATABASE_URL=postgresql://postgres:password@postgres:5432/vru_validation
VRU_DATABASE_URL=postgresql://postgres:password@postgres:5432/vru_validation

# PostgreSQL Container Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=vru_validation

# VRU-specific Database Variables
VRU_DATABASE_USER=postgres
VRU_DATABASE_PASSWORD=password
VRU_DATABASE_NAME=vru_validation

# Redis Configuration - Development
REDIS_URL=redis://redis:6379
AIVALIDATION_REDIS_URL=redis://redis:6379
VRU_REDIS_URL=redis://redis:6379

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
AIVALIDATION_API_HOST=0.0.0.0
AIVALIDATION_API_PORT=8000

# Security Keys - Development Only
SECRET_KEY=development-secret-key-change-for-production
AIVALIDATION_SECRET_KEY=development-secret-key-change-for-production
VRU_SECRET_KEY=development-secret-key-change-for-production
JWT_SECRET_KEY=development-jwt-secret-key-change-for-production

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:8001
AIVALIDATION_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:8001

# Docker Mode
DOCKER_MODE=true
AIVALIDATION_DOCKER_MODE=true

# Logging
LOG_LEVEL=DEBUG
AIVALIDATION_LOG_LEVEL=DEBUG
""")
        
        print(f"✅ Created fixed environment file: {env_path}")
        print(f"   Copy to .env with: cp {env_path} .env")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing docker-compose.yml: {str(e)}")
        # Restore backup if something went wrong
        if backup_path.exists():
            with open(backup_path, 'r') as f:
                backup_content = f.read()
            with open(compose_path, 'w') as f:
                f.write(backup_content)
            print(f"🔄 Restored original file from backup")
        return False

def main():
    """Main function to fix Docker Compose configuration"""
    print("🐳 Docker Compose Configuration Fixer")
    print("=====================================")
    
    success = fix_docker_compose()
    
    if success:
        print("\n✅ All fixes applied successfully!")
        print("\nNext steps:")
        print("1. Copy the fixed environment: cp .env.development.fixed .env")
        print("2. Restart services: docker-compose down && docker-compose up -d")
        print("3. Validate fix: python3 backend/scripts/validate_database_config.py")
    else:
        print("\n❌ Fix failed. Please check the errors above.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)