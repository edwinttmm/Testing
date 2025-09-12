#!/usr/bin/env python3
"""
Database configuration validator and fixer.
Validates all database connections and fixes common issues.
"""

import os
import sys
import logging
from pathlib import Path
from sqlalchemy import create_engine, text
from contextlib import contextmanager

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseValidator:
    """Validate and fix database configuration issues"""
    
    def __init__(self):
        self.issues = []
        self.fixes_applied = []
        self.config_summary = {}
    
    def analyze_current_config(self):
        """Analyze current configuration state"""
        # Environment variables analysis
        env_vars = {
            'DATABASE_URL': os.getenv('DATABASE_URL'),
            'AIVALIDATION_DATABASE_URL': os.getenv('AIVALIDATION_DATABASE_URL'),
            'VRU_DATABASE_URL': os.getenv('VRU_DATABASE_URL'),
            'POSTGRES_USER': os.getenv('POSTGRES_USER'),
            'POSTGRES_PASSWORD': os.getenv('POSTGRES_PASSWORD'),
            'POSTGRES_DB': os.getenv('POSTGRES_DB'),
            'VRU_DATABASE_USER': os.getenv('VRU_DATABASE_USER'),
            'VRU_DATABASE_PASSWORD': os.getenv('VRU_DATABASE_PASSWORD'),
            'VRU_DATABASE_NAME': os.getenv('VRU_DATABASE_NAME'),
        }
        
        self.config_summary = {
            'environment_variables': {k: v for k, v in env_vars.items() if v is not None},
            'missing_variables': [k for k, v in env_vars.items() if v is None],
        }
        
        # Try to import and analyze backend config
        try:
            from config import settings
            self.config_summary['backend_config'] = {
                'database_url': settings.database_url,
                'environment': getattr(settings, 'app_environment', 'unknown'),
                'pool_size': getattr(settings, 'database_pool_size', 'unknown'),
                'max_overflow': getattr(settings, 'database_max_overflow', 'unknown')
            }
        except Exception as e:
            self.config_summary['backend_config'] = {'error': str(e)}
    
    def validate_environment_variables(self):
        """Validate all database environment variables"""
        critical_vars = ['DATABASE_URL', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB']
        missing_vars = []
        
        for var in critical_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            self.issues.append(f"Missing critical environment variables: {', '.join(missing_vars)}")
            return False
        return True
    
    def validate_database_connection(self):
        """Test database connection with current settings"""
        database_urls = [
            os.getenv('AIVALIDATION_DATABASE_URL'),
            os.getenv('DATABASE_URL'),
            os.getenv('VRU_DATABASE_URL'),
        ]
        
        for i, db_url in enumerate(database_urls):
            if not db_url:
                continue
                
            try:
                logger.info(f"Testing connection {i+1}: {self._mask_url(db_url)}")
                engine = create_engine(db_url, connect_args={'connect_timeout': 10})
                
                with engine.connect() as conn:
                    # Test basic connection
                    result = conn.execute(text("SELECT 1")).fetchone()
                    if result and result[0] == 1:
                        # Test database info
                        try:
                            info_result = conn.execute(text("SELECT current_database(), current_user"))
                            db_name, username = info_result.fetchone()
                            logger.info(f"✅ Connection successful: database='{db_name}', user='{username}'")
                            return True
                        except Exception as e:
                            logger.warning(f"Basic connection OK, but metadata query failed: {e}")
                            return True  # Basic connection works
                            
            except Exception as e:
                error_msg = str(e).lower()
                if 'could not connect' in error_msg:
                    self.issues.append(f"Cannot connect to database server: {self._mask_url(db_url)}")
                elif 'authentication failed' in error_msg or 'password authentication failed' in error_msg:
                    self.issues.append(f"Authentication failed for: {self._mask_url(db_url)}")
                elif 'does not exist' in error_msg:
                    self.issues.append(f"Database does not exist: {self._mask_url(db_url)}")
                else:
                    self.issues.append(f"Database connection error: {str(e)}")
        
        return False
    
    def validate_credentials_match(self):
        """Validate that Docker and backend credentials match"""
        # Get database URL from backend config
        try:
            from config import settings
            db_url = settings.database_url
        except:
            db_url = os.getenv('DATABASE_URL')
        
        if not db_url:
            return True  # Can't validate if no URL
        
        # Extract credentials from URL
        if '@' in db_url and '://' in db_url:
            try:
                auth_part = db_url.split('@')[0].split('//')[-1]
                if ':' in auth_part:
                    url_user, url_pass = auth_part.split(':', 1)
                    
                    env_user = os.getenv('POSTGRES_USER')
                    env_pass = os.getenv('POSTGRES_PASSWORD')
                    
                    if env_user and url_user != env_user:
                        self.issues.append(f"Username mismatch: URL uses '{url_user}' but POSTGRES_USER is '{env_user}'")
                        return False
                        
                    if env_pass and url_pass != env_pass:
                        self.issues.append(f"Password mismatch: URL and POSTGRES_PASSWORD don't match")
                        return False
            except Exception as e:
                logger.warning(f"Could not parse database URL for credential validation: {e}")
        
        return True
    
    def analyze_docker_config(self):
        """Analyze Docker compose configuration"""
        docker_compose_path = backend_dir.parent / 'docker-compose.yml'
        if docker_compose_path.exists():
            try:
                with open(docker_compose_path, 'r') as f:
                    content = f.read()
                    
                # Look for database configuration patterns
                if 'vru_prod_user' in content:
                    self.issues.append("Docker compose contains production credentials (vru_prod_user)")
                if 'VRU_Prod_2024_SecureDB_Password_9876' in content:
                    self.issues.append("Docker compose contains hardcoded production password")
                    
            except Exception as e:
                logger.warning(f"Could not analyze docker-compose.yml: {e}")
    
    def generate_fix_commands(self):
        """Generate commands to fix identified issues"""
        fixes = []
        
        if self.issues:
            fixes.append("# Database Configuration Fix Commands")
            fixes.append("# =====================================")
            fixes.append("")
            fixes.append("# 1. Stop all services")
            fixes.append("docker-compose down")
            fixes.append("")
            fixes.append("# 2. Set unified development environment variables")
            fixes.append("export ENVIRONMENT=development")
            fixes.append("export DATABASE_URL=postgresql://postgres:password@postgres:5432/vru_validation")
            fixes.append("export AIVALIDATION_DATABASE_URL=$DATABASE_URL")
            fixes.append("export VRU_DATABASE_URL=$DATABASE_URL")
            fixes.append("export POSTGRES_USER=postgres")
            fixes.append("export POSTGRES_PASSWORD=password")
            fixes.append("export POSTGRES_DB=vru_validation")
            fixes.append("export VRU_DATABASE_USER=postgres")
            fixes.append("export VRU_DATABASE_PASSWORD=password") 
            fixes.append("export VRU_DATABASE_NAME=vru_validation")
            fixes.append("")
            fixes.append("# 3. Create unified .env file")
            fixes.append("cat > .env << 'EOF'")
            fixes.append("ENVIRONMENT=development")
            fixes.append("DATABASE_URL=postgresql://postgres:password@postgres:5432/vru_validation")
            fixes.append("AIVALIDATION_DATABASE_URL=postgresql://postgres:password@postgres:5432/vru_validation")
            fixes.append("VRU_DATABASE_URL=postgresql://postgres:password@postgres:5432/vru_validation")
            fixes.append("POSTGRES_USER=postgres")
            fixes.append("POSTGRES_PASSWORD=password")
            fixes.append("POSTGRES_DB=vru_validation")
            fixes.append("VRU_DATABASE_USER=postgres")
            fixes.append("VRU_DATABASE_PASSWORD=password")
            fixes.append("VRU_DATABASE_NAME=vru_validation")
            fixes.append("EOF")
            fixes.append("")
            fixes.append("# 4. Start services in correct order")
            fixes.append("docker-compose up -d postgres")
            fixes.append("sleep 15  # Wait for PostgreSQL to be ready")
            fixes.append("docker-compose up -d backend")
            fixes.append("")
            fixes.append("# 5. Verify the fix")
            fixes.append("python3 backend/scripts/validate_database_config.py")
        
        return fixes
    
    def _mask_url(self, url):
        """Mask password in database URL for safe logging"""
        if not url:
            return "None"
        if '://' in url and '@' in url:
            try:
                scheme = url.split('://')[0]
                rest = url.split('://')[1]
                if '@' in rest:
                    auth, host_db = rest.split('@', 1)
                    if ':' in auth:
                        user, password = auth.split(':', 1)
                        return f"{scheme}://{user}:***@{host_db}"
            except:
                pass
        return url
    
    def print_summary(self):
        """Print configuration analysis summary"""
        print("\n📊 Configuration Analysis Summary")
        print("=" * 50)
        
        print("\n🔍 Current Environment Variables:")
        for var, value in self.config_summary.get('environment_variables', {}).items():
            if 'PASSWORD' in var.upper():
                print(f"   {var}: ***")
            elif 'URL' in var.upper():
                print(f"   {var}: {self._mask_url(value)}")
            else:
                print(f"   {var}: {value}")
        
        if self.config_summary.get('missing_variables'):
            print(f"\n⚠️  Missing Variables: {', '.join(self.config_summary['missing_variables'])}")
        
        if 'backend_config' in self.config_summary:
            print(f"\n🔧 Backend Configuration:")
            backend_config = self.config_summary['backend_config']
            for key, value in backend_config.items():
                if key == 'database_url':
                    print(f"   {key}: {self._mask_url(value)}")
                else:
                    print(f"   {key}: {value}")

def main():
    """Run database configuration validation"""
    print("🔍 AI Model Validation Platform - Database Configuration Validator")
    print("=" * 70)
    
    validator = DatabaseValidator()
    
    print("\n📋 Step 1: Analyzing current configuration...")
    validator.analyze_current_config()
    validator.print_summary()
    
    print("\n📋 Step 2: Validating environment variables...")
    env_ok = validator.validate_environment_variables()
    if env_ok:
        print("   ✅ Environment variables are properly set")
    
    print("\n📋 Step 3: Testing database connectivity...")
    conn_ok = validator.validate_database_connection()
    if conn_ok:
        print("   ✅ Database connection successful")
    
    print("\n📋 Step 4: Validating credential consistency...")
    creds_ok = validator.validate_credentials_match()
    if creds_ok:
        print("   ✅ Credentials are consistent")
    
    print("\n📋 Step 5: Analyzing Docker configuration...")
    validator.analyze_docker_config()
    
    # Report results
    print("\n" + "=" * 70)
    if validator.issues:
        print("❌ ISSUES DETECTED:")
        for i, issue in enumerate(validator.issues, 1):
            print(f"   {i}. {issue}")
        
        print(f"\n🔧 AUTOMATED FIX AVAILABLE:")
        print("   Run the following commands to fix all issues:")
        print()
        fixes = validator.generate_fix_commands()
        for fix in fixes:
            print(fix)
            
        print(f"\n💾 Fix script saved to: /tmp/database_fix.sh")
        try:
            with open('/tmp/database_fix.sh', 'w') as f:
                f.write('#!/bin/bash\n')
                f.write('# Auto-generated database configuration fix\n\n')
                for fix in fixes:
                    f.write(fix + '\n')
            os.chmod('/tmp/database_fix.sh', 0o755)
            print("   Execute with: bash /tmp/database_fix.sh")
        except Exception as e:
            print(f"   Could not save fix script: {e}")
    else:
        print("✅ ALL DATABASE CONFIGURATION CHECKS PASSED!")
        print("   Your database configuration is correct and working.")
    
    print("=" * 70)
    return len(validator.issues) == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)