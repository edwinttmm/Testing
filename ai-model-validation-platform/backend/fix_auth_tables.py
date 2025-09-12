#!/usr/bin/env python3
"""
SPARC REFINEMENT PHASE: Direct fix for missing auth tables.
This script creates the missing auth_users and user_sessions tables in the SQLite database.
"""

import sys
import logging
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_missing_auth_tables():
    """Create missing authentication tables using the correct SQLite engine."""
    try:
        logger.info("🔍 Checking for missing auth tables...")
        
        # Bypass unified database - use direct SQLite connection
        from sqlalchemy import create_engine, inspect
        from database import Base
        
        # Create direct SQLite engine
        sqlite_url = "sqlite:///./dev_database.db"
        engine = create_engine(sqlite_url, echo=True)
        
        # Check current tables
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        logger.info(f"Current tables ({len(existing_tables)}): {existing_tables}")
        
        # Check for auth tables
        auth_tables = ['auth_users', 'user_sessions']
        missing_auth = [t for t in auth_tables if t not in existing_tables]
        
        if missing_auth:
            logger.info(f"❌ Missing auth tables: {missing_auth}")
            
            # Import models to register them with Base
            logger.info("📥 Importing auth models...")
            from models import AuthUser, UserSession
            logger.info("✅ Auth models imported successfully")
            
            # Create only the missing tables
            logger.info("🔧 Creating missing auth tables...")
            Base.metadata.create_all(bind=engine, checkfirst=True)
            
            # Verify creation
            inspector = inspect(engine)
            new_tables = inspector.get_table_names()
            new_auth_tables = [t for t in auth_tables if t in new_tables]
            
            if len(new_auth_tables) == len(auth_tables):
                logger.info(f"✅ Auth tables created successfully: {new_auth_tables}")
                logger.info(f"📊 Total tables now: {len(new_tables)}")
                return True
            else:
                logger.error(f"❌ Failed to create all auth tables. Created: {new_auth_tables}")
                return False
        else:
            logger.info("✅ All auth tables already exist")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to create auth tables: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def verify_auth_system():
    """Verify the auth system works after table creation."""
    try:
        logger.info("🔍 Verifying auth system...")
        
        # Use direct SQLite session
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from models import AuthUser
        
        sqlite_url = "sqlite:///./dev_database.db"
        engine = create_engine(sqlite_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        with SessionLocal() as session:
            # Try to query auth_users table
            user_count = session.query(AuthUser).count()
            logger.info(f"✅ Auth system working - found {user_count} users")
            
            # Create test user if none exist
            if user_count == 0:
                logger.info("👤 Creating default admin user...")
                admin_user = AuthUser(
                    email="admin@aivalidation.local",
                    username="admin",
                    full_name="System Administrator",
                    is_active=True,
                    is_superuser=True,
                    is_verified=True
                )
                admin_user.set_password("admin123")
                session.add(admin_user)
                session.commit()
                logger.info("✅ Default admin user created")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Auth system verification failed: {e}")
        return False

def main():
    """Main execution function."""
    logger.info("🚀 SPARC REFINEMENT: Fixing missing auth tables...")
    
    # Step 1: Create missing auth tables
    if not create_missing_auth_tables():
        logger.error("❌ Failed to create auth tables")
        return False
    
    # Step 2: Verify auth system works
    if not verify_auth_system():
        logger.error("❌ Auth system verification failed")
        return False
    
    logger.info("🎉 SPARC REFINEMENT COMPLETED: Auth tables fixed successfully!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)