#!/usr/bin/env python3
"""
Complete Migration Suite Runner
Orchestrates the entire Project-Video many-to-many migration process
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import subprocess
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'migration_suite_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MigrationSuiteRunner:
    """Complete migration suite orchestrator"""
    
    def __init__(self, db_path: str = "./dev_database.db", dry_run: bool = False):
        self.db_path = db_path
        self.dry_run = dry_run
        self.results = {
            'start_time': datetime.now().isoformat(),
            'phases': {},
            'overall_success': False
        }
        
    def run_complete_migration_suite(self) -> Dict[str, Any]:
        """Run the complete migration suite"""
        logger.info("🚀 Starting Complete Project-Video Many-to-Many Migration Suite")
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Dry Run: {self.dry_run}")
        
        try:
            # Phase 1: Pre-Migration Validation
            self.results['phases']['pre_validation'] = self._run_pre_migration_validation()
            
            if not self.results['phases']['pre_validation']['success']:
                logger.error("❌ Pre-migration validation failed, aborting migration")
                return self.results
            
            # Phase 2: Backup Creation
            self.results['phases']['backup'] = self._run_backup_creation()
            
            if not self.results['phases']['backup']['success']:
                logger.error("❌ Backup creation failed, aborting migration")
                return self.results
            
            # Phase 3: Migration Testing (if not dry run)
            if not self.dry_run:
                self.results['phases']['migration_test'] = self._run_migration_test()
                
                if not self.results['phases']['migration_test']['success']:
                    logger.error("❌ Migration test failed, aborting migration")
                    return self.results
                
                # Phase 4: Actual Migration
                self.results['phases']['migration'] = self._run_actual_migration()
                
                if not self.results['phases']['migration']['success']:
                    logger.error("❌ Migration failed, attempting rollback")
                    self.results['phases']['rollback'] = self._run_rollback()
                    return self.results
                
                # Phase 5: Post-Migration Validation
                self.results['phases']['post_validation'] = self._run_post_migration_validation()
            
            else:
                logger.info("🧪 Dry run mode - skipping actual migration")
                self.results['phases']['dry_run'] = {'success': True, 'message': 'Dry run completed successfully'}
            
            # Determine overall success
            failed_phases = [name for name, phase in self.results['phases'].items() 
                           if not phase.get('success', False)]
            
            self.results['overall_success'] = len(failed_phases) == 0
            self.results['end_time'] = datetime.now().isoformat()
            
            if self.results['overall_success']:
                logger.info("🎉 Migration suite completed successfully!")
            else:
                logger.error(f"❌ Migration suite failed. Failed phases: {failed_phases}")
            
            return self.results
            
        except Exception as e:
            logger.error(f"❌ Migration suite crashed: {e}")
            self.results['error'] = str(e)
            self.results['overall_success'] = False
            return self.results
    
    def _run_pre_migration_validation(self) -> Dict[str, Any]:
        """Run pre-migration validation"""
        logger.info("📋 Phase 1: Pre-Migration Validation")
        
        try:
            # Import and run data integrity validator
            from data_integrity_validator import DataIntegrityValidator
            
            validator = DataIntegrityValidator(self.db_path)
            validation_results = validator.run_comprehensive_validation()
            
            overall_score = validation_results.get('overall_score', 0.0)
            success = overall_score >= 0.7  # 70% threshold for pre-migration
            
            result = {
                'success': success,
                'score': overall_score,
                'details': validation_results,
                'message': f'Pre-migration validation {"passed" if success else "failed"} with score: {overall_score:.2%}'
            }
            
            if success:
                logger.info(f"✅ Pre-migration validation passed: {overall_score:.2%}")
            else:
                logger.error(f"❌ Pre-migration validation failed: {overall_score:.2%}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Pre-migration validation crashed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _run_backup_creation(self) -> Dict[str, Any]:
        """Run backup creation"""
        logger.info("💾 Phase 2: Backup Creation")
        
        try:
            from data_backup_script import DatabaseBackupManager
            
            backup_manager = DatabaseBackupManager(self.db_path)
            backup_files = backup_manager.create_comprehensive_backup()
            
            # Verify backup integrity
            integrity_check = backup_manager.verify_backup_integrity(backup_files)
            
            result = {
                'success': integrity_check,
                'backup_files': backup_files,
                'message': f'Backup {"created successfully" if integrity_check else "failed integrity check"}'
            }
            
            if integrity_check:
                logger.info(f"✅ Backup created successfully: {len(backup_files)} files")
                for backup_type, file_path in backup_files.items():
                    logger.info(f"   📁 {backup_type}: {file_path}")
            else:
                logger.error("❌ Backup integrity check failed")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Backup creation crashed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _run_migration_test(self) -> Dict[str, Any]:
        """Run migration test on test database"""
        logger.info("🧪 Phase 3: Migration Testing")
        
        try:
            from migration_test_runner import MigrationTestRunner
            
            # Create test runner with separate test database
            test_db_path = self.db_path.replace('.db', '_migration_test.db')
            test_runner = MigrationTestRunner(test_db_path)
            
            # Run comprehensive migration test
            test_results = test_runner.run_migration_test()
            
            success = (
                test_results.get('setup_success', False) and
                test_results.get('migration_success', False) and
                test_results.get('data_integrity_check', False)
            )
            
            result = {
                'success': success,
                'test_results': test_results,
                'test_database': test_db_path,
                'message': f'Migration test {"passed" if success else "failed"}'
            }
            
            if success:
                logger.info("✅ Migration test passed")
            else:
                logger.error("❌ Migration test failed")
                logger.error(f"   Setup: {'✅' if test_results.get('setup_success') else '❌'}")
                logger.error(f"   Migration: {'✅' if test_results.get('migration_success') else '❌'}")
                logger.error(f"   Integrity: {'✅' if test_results.get('data_integrity_check') else '❌'}")
            
            # Cleanup test database
            try:
                if os.path.exists(test_db_path):
                    os.remove(test_db_path)
            except:
                pass
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Migration test crashed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _run_actual_migration(self) -> Dict[str, Any]:
        """Run the actual migration"""
        logger.info("🔄 Phase 4: Actual Migration")
        
        try:
            # Import migration module and run upgrade
            from migration_0004_project_video_many_to_many import upgrade
            
            # Set up Alembic-like context
            import sqlalchemy as sa
            from alembic.operations import Operations
            from alembic.migration import MigrationContext
            
            engine = sa.create_engine(f"sqlite:///{self.db_path}")
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                op = Operations(context)
                
                # Set up operations context globally
                import migration_0004_project_video_many_to_many as migration_module
                migration_module.op = op
                
                # Run the upgrade
                logger.info("🔄 Running migration upgrade...")
                upgrade()
                
            result = {
                'success': True,
                'message': 'Migration completed successfully'
            }
            
            logger.info("✅ Migration completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _run_post_migration_validation(self) -> Dict[str, Any]:
        """Run post-migration validation"""
        logger.info("🔍 Phase 5: Post-Migration Validation")
        
        try:
            from data_integrity_validator import DataIntegrityValidator
            
            validator = DataIntegrityValidator(self.db_path)
            validation_results = validator.run_comprehensive_validation()
            
            overall_score = validation_results.get('overall_score', 0.0)
            success = overall_score >= 0.9  # 90% threshold for post-migration
            
            result = {
                'success': success,
                'score': overall_score,
                'details': validation_results,
                'message': f'Post-migration validation {"passed" if success else "failed"} with score: {overall_score:.2%}'
            }
            
            if success:
                logger.info(f"✅ Post-migration validation passed: {overall_score:.2%}")
            else:
                logger.error(f"❌ Post-migration validation failed: {overall_score:.2%}")
                
                # Log specific validation failures
                for validation_name, validation_result in validation_results.get('validations', {}).items():
                    if isinstance(validation_result, dict) and validation_result.get('status') != 'passed':
                        score = validation_result.get('score', 0.0)
                        logger.error(f"   ❌ {validation_name}: {score:.2%}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Post-migration validation crashed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _run_rollback(self) -> Dict[str, Any]:
        """Run migration rollback"""
        logger.info("🔄 Phase R: Migration Rollback")
        
        try:
            # Try to restore from backup first
            from data_backup_script import DatabaseBackupManager
            
            backup_manager = DatabaseBackupManager(self.db_path)
            
            # Find the most recent backup
            backup_dir = Path("./migration_backups")
            if backup_dir.exists():
                backup_files = list(backup_dir.glob("database_backup_*.db"))
                if backup_files:
                    latest_backup = max(backup_files, key=lambda f: f.stat().st_mtime)
                    
                    # Restore from backup
                    import shutil
                    shutil.copy2(latest_backup, self.db_path)
                    
                    logger.info(f"✅ Restored database from backup: {latest_backup}")
                    return {'success': True, 'method': 'backup_restore', 'backup_file': str(latest_backup)}
            
            # If backup restore fails, try migration downgrade
            from migration_0004_project_video_many_to_many import downgrade
            
            import sqlalchemy as sa
            from alembic.operations import Operations
            from alembic.migration import MigrationContext
            
            engine = sa.create_engine(f"sqlite:///{self.db_path}")
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                op = Operations(context)
                
                # Set up operations context globally
                import migration_0004_project_video_many_to_many as migration_module
                migration_module.op = op
                
                # Run the downgrade
                downgrade()
            
            logger.info("✅ Rollback completed using migration downgrade")
            return {'success': True, 'method': 'migration_downgrade'}
            
        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def generate_final_report(self) -> str:
        """Generate final migration report"""
        report = f"""
# Project-Video Many-to-Many Migration Report

**Migration Date:** {self.results['start_time']}
**Database:** {self.db_path}
**Dry Run:** {self.dry_run}
**Overall Success:** {'✅ PASSED' if self.results['overall_success'] else '❌ FAILED'}

## Phase Results

"""
        
        phase_icons = {
            'pre_validation': '📋',
            'backup': '💾', 
            'migration_test': '🧪',
            'migration': '🔄',
            'post_validation': '🔍',
            'rollback': '↩️',
            'dry_run': '🧪'
        }
        
        for phase_name, phase_result in self.results['phases'].items():
            icon = phase_icons.get(phase_name, '📝')
            status = '✅ PASSED' if phase_result.get('success') else '❌ FAILED'
            message = phase_result.get('message', 'No details')
            
            report += f"### {icon} {phase_name.replace('_', ' ').title()}\n"
            report += f"**Status:** {status}\n"
            report += f"**Details:** {message}\n\n"
            
            # Add score information for validation phases
            if 'score' in phase_result:
                report += f"**Score:** {phase_result['score']:.2%}\n\n"
        
        if not self.results['overall_success']:
            report += "\n## Troubleshooting\n\n"
            report += "The migration failed. Please:\n\n"
            report += "1. Review the detailed logs above\n"
            report += "2. Check the backup files in `./migration_backups/`\n"
            report += "3. Verify database integrity\n"
            report += "4. Contact the development team with this report\n\n"
        else:
            report += "\n## Next Steps\n\n"
            if self.dry_run:
                report += "Dry run completed successfully. You can now run the actual migration:\n"
                report += "```bash\npython run_migration_suite.py --no-dry-run\n```\n\n"
            else:
                report += "Migration completed successfully. Please:\n\n"
                report += "1. Update your application code to use the new many-to-many relationships\n"
                report += "2. Test all application functionality\n"
                report += "3. Monitor performance and error logs\n"
                report += "4. Update API documentation\n\n"
        
        return report
    
    def save_results(self, filepath: Optional[str] = None) -> str:
        """Save migration results to file"""
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"migration_suite_results_{timestamp}.json"
        
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        logger.info(f"Migration results saved to: {filepath}")
        return filepath

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Project-Video Many-to-Many Migration Suite')
    parser.add_argument('--database', '-d', default='./dev_database.db', 
                       help='Database file path')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run in dry-run mode (no actual migration)')
    parser.add_argument('--no-dry-run', action='store_true', 
                       help='Force actual migration (override safety)')
    
    args = parser.parse_args()
    
    # Determine dry run mode
    dry_run = args.dry_run or not args.no_dry_run
    
    # Create and run migration suite
    suite = MigrationSuiteRunner(args.database, dry_run)
    results = suite.run_complete_migration_suite()
    
    # Generate and display report
    report = suite.generate_final_report()
    print(report)
    
    # Save detailed results
    results_file = suite.save_results()
    print(f"\n📊 Detailed results saved to: {results_file}")
    
    # Save report to markdown file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"migration_report_{timestamp}.md"
    with open(report_file, 'w') as f:
        f.write(report)
    print(f"📄 Report saved to: {report_file}")
    
    # Return appropriate exit code
    return 0 if results['overall_success'] else 1

if __name__ == "__main__":
    exit(main())