#!/usr/bin/env python3
"""
Database Migration Script: Fix Enum Validation Errors

This script addresses the enum validation errors in the projects table by:
1. Updating "Mixed" camera_view values to "Multi-angle" 
2. Updating "Mixed" signal_type values to "Network Packet"
3. Verifying all values match the valid enum definitions
4. Providing rollback capability and detailed logging

Usage:
    python scripts/fix_enum_validation.py --fix           # Apply the fixes
    python scripts/fix_enum_validation.py --check         # Check for issues only
    python scripts/fix_enum_validation.py --rollback     # Rollback to backup (if exists)
"""

import sys
import os
import argparse
import logging
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from config import settings
from database import engine
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EnumValidationFixer:
    """Database migration tool to fix enum validation errors"""
    
    def __init__(self, dry_run: bool = False, db_path: Optional[str] = None):
        self.dry_run = dry_run
        self.db_path = db_path or "dev_database.db"  # Use the database that has the data
        self.backup_created = False
        self.backup_path = None
        
        # Valid enum values from schemas.py
        self.valid_camera_views = {
            "Front-facing VRU",
            "Rear-facing VRU", 
            "In-Cab Driver Behavior",
            "Multi-angle"
        }
        
        self.valid_signal_types = {
            "GPIO",
            "Network Packet", 
            "Serial",
            "CAN Bus"
        }
        
        # Migration mappings
        self.camera_view_migrations = {
            "Mixed": "Multi-angle",
            # Add other problematic values if found
        }
        
        self.signal_type_migrations = {
            "Mixed": "Network Packet",
            # Add other problematic values if found
        }
        
        logger.info(f"EnumValidationFixer initialized (dry_run={dry_run})")
    
    def get_database_path(self) -> str:
        """Get database file path"""
        return self.db_path
    
    def create_backup(self) -> bool:
        """Create a backup of the database before making changes"""
        try:
            db_path = self.get_database_path()
            if not os.path.exists(db_path):
                logger.error(f"Database file not found: {db_path}")
                return False
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.backup_path = f"{db_path}.backup_{timestamp}"
            
            if self.dry_run:
                logger.info(f"[DRY RUN] Would create backup: {self.backup_path}")
                return True
            
            shutil.copy2(db_path, self.backup_path)
            self.backup_created = True
            logger.info(f"✅ Backup created: {self.backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create backup: {e}")
            return False
    
    def check_enum_issues(self) -> Dict[str, List[Tuple[str, str, str]]]:
        """Check for enum validation issues in the database"""
        logger.info("🔍 Checking for enum validation issues...")
        
        issues = {
            'camera_view_issues': [],
            'signal_type_issues': []
        }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check camera_view issues
            valid_views_str = "','".join(self.valid_camera_views)
            cursor.execute(f"""
                SELECT id, name, camera_view 
                FROM projects 
                WHERE camera_view NOT IN ('{valid_views_str}')
            """)
            
            for row in cursor.fetchall():
                issues['camera_view_issues'].append((row[0], row[1], row[2]))
                logger.warning(f"Invalid camera_view: '{row[2]}' in project '{row[1]}' (ID: {row[0]})")
            
            # Check signal_type issues  
            valid_types_str = "','".join(self.valid_signal_types)
            cursor.execute(f"""
                SELECT id, name, signal_type 
                FROM projects 
                WHERE signal_type NOT IN ('{valid_types_str}')
            """)
            
            for row in cursor.fetchall():
                issues['signal_type_issues'].append((row[0], row[1], row[2]))
                logger.warning(f"Invalid signal_type: '{row[2]}' in project '{row[1]}' (ID: {row[0]})")
                
            conn.close()
        
        except Exception as e:
            logger.error(f"❌ Failed to check enum issues: {e}")
            return {}
        
        total_issues = len(issues['camera_view_issues']) + len(issues['signal_type_issues'])
        if total_issues == 0:
            logger.info("✅ No enum validation issues found!")
        else:
            logger.info(f"Found {total_issues} enum validation issues")
            
        return issues
    
    def fix_camera_view_issues(self, issues: List[Tuple[str, str, str]]) -> int:
        """Fix camera_view enum issues"""
        if not issues:
            logger.info("No camera_view issues to fix")
            return 0
            
        fixed_count = 0
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for project_id, project_name, invalid_value in issues:
                if invalid_value in self.camera_view_migrations:
                    new_value = self.camera_view_migrations[invalid_value]
                    
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would update project '{project_name}': camera_view '{invalid_value}' → '{new_value}'")
                    else:
                        cursor.execute("""
                            UPDATE projects 
                            SET camera_view = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (new_value, project_id))
                        
                        logger.info(f"✅ Updated project '{project_name}': camera_view '{invalid_value}' → '{new_value}'")
                    
                    fixed_count += 1
                else:
                    logger.warning(f"⚠️  No migration mapping for camera_view '{invalid_value}' in project '{project_name}'")
            
            if not self.dry_run:
                conn.commit()
            conn.close()
                        
        except Exception as e:
            logger.error(f"❌ Failed to fix camera_view issues: {e}")
            return 0
            
        return fixed_count
    
    def fix_signal_type_issues(self, issues: List[Tuple[str, str, str]]) -> int:
        """Fix signal_type enum issues"""
        if not issues:
            logger.info("No signal_type issues to fix")
            return 0
            
        fixed_count = 0
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for project_id, project_name, invalid_value in issues:
                if invalid_value in self.signal_type_migrations:
                    new_value = self.signal_type_migrations[invalid_value]
                    
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would update project '{project_name}': signal_type '{invalid_value}' → '{new_value}'")
                    else:
                        cursor.execute("""
                            UPDATE projects 
                            SET signal_type = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (new_value, project_id))
                        
                        logger.info(f"✅ Updated project '{project_name}': signal_type '{invalid_value}' → '{new_value}'")
                    
                    fixed_count += 1
                else:
                    logger.warning(f"⚠️  No migration mapping for signal_type '{invalid_value}' in project '{project_name}'")
            
            if not self.dry_run:
                conn.commit()
            conn.close()
                        
        except Exception as e:
            logger.error(f"❌ Failed to fix signal_type issues: {e}")
            return 0
            
        return fixed_count
    
    def verify_fixes(self) -> bool:
        """Verify that all enum issues have been resolved"""
        logger.info("🔍 Verifying fixes...")
        
        remaining_issues = self.check_enum_issues()
        
        if not remaining_issues:
            logger.error("❌ Failed to check remaining issues")
            return False
            
        total_remaining = len(remaining_issues['camera_view_issues']) + len(remaining_issues['signal_type_issues'])
        
        if total_remaining == 0:
            logger.info("✅ All enum validation issues have been resolved!")
            return True
        else:
            logger.error(f"❌ {total_remaining} enum validation issues still remain")
            return False
    
    def run_migration(self) -> bool:
        """Run the complete migration process"""
        logger.info("🚀 Starting enum validation migration...")
        
        # Step 1: Create backup
        if not self.create_backup():
            logger.error("❌ Failed to create backup, aborting migration")
            return False
        
        # Step 2: Check current issues
        issues = self.check_enum_issues()
        if not issues:
            logger.error("❌ Failed to check enum issues")
            return False
        
        total_issues = len(issues['camera_view_issues']) + len(issues['signal_type_issues'])
        if total_issues == 0:
            logger.info("✅ No enum validation issues found, migration not needed")
            return True
        
        logger.info(f"Found {total_issues} enum validation issues to fix")
        
        # Step 3: Fix camera_view issues
        camera_view_fixes = self.fix_camera_view_issues(issues['camera_view_issues'])
        
        # Step 4: Fix signal_type issues  
        signal_type_fixes = self.fix_signal_type_issues(issues['signal_type_issues'])
        
        total_fixes = camera_view_fixes + signal_type_fixes
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would have fixed {total_fixes}/{total_issues} issues")
            return True
        
        # Step 5: Verify fixes
        if not self.verify_fixes():
            logger.error("❌ Migration verification failed")
            return False
        
        logger.info(f"✅ Migration completed successfully! Fixed {total_fixes} issues")
        return True
    
    def rollback_migration(self) -> bool:
        """Rollback to the backup if it exists"""
        if not self.backup_path or not os.path.exists(self.backup_path):
            logger.error("❌ No backup found to rollback to")
            return False
        
        try:
            db_path = self.get_database_path()
            
            if self.dry_run:
                logger.info(f"[DRY RUN] Would rollback database from backup: {self.backup_path}")
                return True
            
            shutil.copy2(self.backup_path, db_path)
            logger.info(f"✅ Database rolled back from backup: {self.backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to rollback database: {e}")
            return False

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="Fix enum validation errors in the database",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--fix', action='store_true',
                       help='Apply the enum validation fixes')
    parser.add_argument('--check', action='store_true', 
                       help='Check for enum validation issues without fixing')
    parser.add_argument('--rollback', action='store_true',
                       help='Rollback to backup (if exists)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--db', type=str, default='dev_database.db',
                       help='Database file to work with (default: dev_database.db)')
    
    args = parser.parse_args()
    
    if not any([args.fix, args.check, args.rollback]):
        parser.print_help()
        return
    
    fixer = EnumValidationFixer(dry_run=args.dry_run, db_path=args.db)
    
    try:
        if args.check:
            logger.info("🔍 Checking for enum validation issues...")
            issues = fixer.check_enum_issues()
            if issues:
                total = len(issues['camera_view_issues']) + len(issues['signal_type_issues'])
                print(f"\nFound {total} enum validation issues:")
                for issue_type, issue_list in issues.items():
                    if issue_list:
                        print(f"\n{issue_type.replace('_', ' ').title()}:")
                        for project_id, project_name, invalid_value in issue_list:
                            print(f"  - Project '{project_name}' (ID: {project_id}): '{invalid_value}'")
                            
        elif args.rollback:
            logger.info("🔄 Rolling back database...")
            success = fixer.rollback_migration()
            sys.exit(0 if success else 1)
            
        elif args.fix:
            logger.info("🔧 Applying enum validation fixes...")
            success = fixer.run_migration()
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        logger.info("\n⏹️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()