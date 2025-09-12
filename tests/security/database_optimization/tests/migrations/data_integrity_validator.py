#!/usr/bin/env python3
"""
Data Integrity Validator for Project-Video Migration
Validates data integrity before and after migration
"""

import sqlite3
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple
from pathlib import Path
import hashlib

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataIntegrityValidator:
    """Comprehensive data integrity validation for migrations"""
    
    def __init__(self, db_path: str = "./dev_database.db"):
        self.db_path = db_path
        self.validation_results = {}
        
    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive data integrity validation"""
        logger.info("Starting comprehensive data integrity validation...")
        
        validation_results = {
            'timestamp': datetime.now().isoformat(),
            'database_path': self.db_path,
            'validations': {}
        }
        
        try:
            # Check database accessibility
            validation_results['validations']['database_accessible'] = self._check_database_accessibility()
            
            # Validate table structures
            validation_results['validations']['table_structures'] = self._validate_table_structures()
            
            # Validate data counts
            validation_results['validations']['data_counts'] = self._validate_data_counts()
            
            # Validate relationships
            validation_results['validations']['relationships'] = self._validate_relationships()
            
            # Validate data quality
            validation_results['validations']['data_quality'] = self._validate_data_quality()
            
            # Validate indexes
            validation_results['validations']['indexes'] = self._validate_indexes()
            
            # Validate foreign key constraints
            validation_results['validations']['foreign_keys'] = self._validate_foreign_keys()
            
            # Calculate overall integrity score
            validation_results['overall_score'] = self._calculate_integrity_score(validation_results['validations'])
            
            logger.info(f"Validation completed with overall score: {validation_results['overall_score']}")
            return validation_results
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            validation_results['error'] = str(e)
            validation_results['overall_score'] = 0.0
            return validation_results
    
    def _check_database_accessibility(self) -> Dict[str, Any]:
        """Check if database is accessible and responsive"""
        logger.info("Checking database accessibility...")
        
        result = {
            'status': 'unknown',
            'details': {},
            'score': 0.0
        }
        
        try:
            if not os.path.exists(self.db_path):
                result['status'] = 'failed'
                result['details']['error'] = 'Database file does not exist'
                return result
            
            # Check file permissions
            result['details']['file_size'] = os.path.getsize(self.db_path)
            result['details']['readable'] = os.access(self.db_path, os.R_OK)
            result['details']['writable'] = os.access(self.db_path, os.W_OK)
            
            # Test database connection
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            conn.close()
            
            result['details']['table_count'] = len(tables)
            result['details']['tables'] = [t[0] for t in tables]
            
            result['status'] = 'passed'
            result['score'] = 1.0
            
        except Exception as e:
            result['status'] = 'failed'
            result['details']['error'] = str(e)
            result['score'] = 0.0
        
        return result
    
    def _validate_table_structures(self) -> Dict[str, Any]:
        """Validate expected table structures after migration"""
        logger.info("Validating table structures...")
        
        result = {
            'status': 'unknown',
            'details': {},
            'score': 0.0
        }
        
        expected_tables = {
            'projects': {
                'required_columns': ['id', 'name', 'description', 'status', 'created_at'],
                'optional_columns': ['project_metadata', 'max_videos', 'tolerance_ms']
            },
            'videos': {
                'required_columns': ['id', 'filename', 'file_path', 'created_at'],
                'optional_columns': ['camera_model', 'camera_view', 'lens_type', 'video_resolution', 'frame_rate', 'signal_type']
            },
            'project_videos': {
                'required_columns': ['id', 'project_id', 'video_id', 'created_at'],
                'optional_columns': []
            }
        }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            table_validations = {}
            
            for table_name, table_spec in expected_tables.items():
                table_validation = {
                    'exists': False,
                    'columns': {},
                    'missing_columns': [],
                    'extra_columns': [],
                    'score': 0.0
                }
                
                # Check if table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                if cursor.fetchone():
                    table_validation['exists'] = True
                    
                    # Get table columns
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns_info = cursor.fetchall()
                    actual_columns = [col[1] for col in columns_info]
                    
                    table_validation['columns'] = {col[1]: col for col in columns_info}
                    
                    # Check required columns
                    for req_col in table_spec['required_columns']:
                        if req_col not in actual_columns:
                            table_validation['missing_columns'].append(req_col)
                    
                    # Check for unexpected columns (informational)
                    expected_all = table_spec['required_columns'] + table_spec['optional_columns']
                    for actual_col in actual_columns:
                        if actual_col not in expected_all:
                            table_validation['extra_columns'].append(actual_col)
                    
                    # Calculate table score
                    if len(table_validation['missing_columns']) == 0:
                        table_validation['score'] = 1.0
                    else:
                        missing_ratio = len(table_validation['missing_columns']) / len(table_spec['required_columns'])
                        table_validation['score'] = max(0.0, 1.0 - missing_ratio)
                
                table_validations[table_name] = table_validation
            
            conn.close()
            
            result['details'] = table_validations
            result['score'] = sum(tv['score'] for tv in table_validations.values()) / len(table_validations)
            result['status'] = 'passed' if result['score'] >= 0.8 else 'failed'
            
        except Exception as e:
            result['status'] = 'failed'
            result['details']['error'] = str(e)
            result['score'] = 0.0
        
        return result
    
    def _validate_data_counts(self) -> Dict[str, Any]:
        """Validate data counts and detect data loss"""
        logger.info("Validating data counts...")
        
        result = {
            'status': 'unknown',
            'details': {},
            'score': 0.0
        }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            counts = {}
            
            # Count projects
            cursor.execute("SELECT COUNT(*) FROM projects")
            counts['projects'] = cursor.fetchone()[0]
            
            # Count videos
            cursor.execute("SELECT COUNT(*) FROM videos")
            counts['videos'] = cursor.fetchone()[0]
            
            # Count project-video relationships
            cursor.execute("SELECT COUNT(*) FROM project_videos")
            counts['project_videos'] = cursor.fetchone()[0]
            
            # Validate relationship consistency
            cursor.execute("SELECT COUNT(DISTINCT project_id) FROM project_videos")
            counts['projects_with_videos'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT video_id) FROM project_videos")
            counts['videos_with_projects'] = cursor.fetchone()[0]
            
            conn.close()
            
            result['details'] = counts
            
            # Check for reasonable data distribution
            checks = []
            checks.append(counts['projects'] > 0)  # At least some projects
            checks.append(counts['videos'] > 0)    # At least some videos
            checks.append(counts['project_videos'] > 0)  # At least some relationships
            checks.append(counts['projects_with_videos'] <= counts['projects'])  # Logical constraint
            checks.append(counts['videos_with_projects'] <= counts['videos'])    # Logical constraint
            
            result['score'] = sum(checks) / len(checks)
            result['status'] = 'passed' if result['score'] >= 0.8 else 'failed'
            
        except Exception as e:
            result['status'] = 'failed'
            result['details']['error'] = str(e)
            result['score'] = 0.0
        
        return result
    
    def _validate_relationships(self) -> Dict[str, Any]:
        """Validate relationship integrity"""
        logger.info("Validating relationships...")
        
        result = {
            'status': 'unknown',
            'details': {},
            'score': 0.0
        }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            relationship_checks = {}
            
            # Check for orphaned project_videos records (invalid project_id)
            cursor.execute("""
                SELECT COUNT(*) FROM project_videos pv
                LEFT JOIN projects p ON pv.project_id = p.id
                WHERE p.id IS NULL
            """)
            relationship_checks['orphaned_project_relationships'] = cursor.fetchone()[0]
            
            # Check for orphaned project_videos records (invalid video_id)
            cursor.execute("""
                SELECT COUNT(*) FROM project_videos pv
                LEFT JOIN videos v ON pv.video_id = v.id
                WHERE v.id IS NULL
            """)
            relationship_checks['orphaned_video_relationships'] = cursor.fetchone()[0]
            
            # Check for duplicate relationships
            cursor.execute("""
                SELECT project_id, video_id, COUNT(*) as count
                FROM project_videos
                GROUP BY project_id, video_id
                HAVING count > 1
            """)
            duplicate_relationships = cursor.fetchall()
            relationship_checks['duplicate_relationships'] = len(duplicate_relationships)
            
            # Check referential integrity with complex join
            cursor.execute("""
                SELECT COUNT(*) FROM project_videos pv
                INNER JOIN projects p ON pv.project_id = p.id
                INNER JOIN videos v ON pv.video_id = v.id
            """)
            relationship_checks['valid_relationships'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM project_videos")
            total_relationships = cursor.fetchone()[0]
            relationship_checks['total_relationships'] = total_relationships
            
            conn.close()
            
            result['details'] = relationship_checks
            
            # Calculate integrity score
            integrity_checks = []
            integrity_checks.append(relationship_checks['orphaned_project_relationships'] == 0)
            integrity_checks.append(relationship_checks['orphaned_video_relationships'] == 0)
            integrity_checks.append(relationship_checks['duplicate_relationships'] == 0)
            if total_relationships > 0:
                integrity_checks.append(
                    relationship_checks['valid_relationships'] == total_relationships
                )
            
            result['score'] = sum(integrity_checks) / len(integrity_checks) if integrity_checks else 0.0
            result['status'] = 'passed' if result['score'] >= 0.9 else 'failed'
            
        except Exception as e:
            result['status'] = 'failed'
            result['details']['error'] = str(e)
            result['score'] = 0.0
        
        return result
    
    def _validate_data_quality(self) -> Dict[str, Any]:
        """Validate data quality and consistency"""
        logger.info("Validating data quality...")
        
        result = {
            'status': 'unknown',
            'details': {},
            'score': 0.0
        }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            quality_checks = {}
            
            # Check for null required fields in projects
            cursor.execute("SELECT COUNT(*) FROM projects WHERE id IS NULL OR name IS NULL")
            quality_checks['projects_null_required_fields'] = cursor.fetchone()[0]
            
            # Check for null required fields in videos
            cursor.execute("SELECT COUNT(*) FROM videos WHERE id IS NULL OR filename IS NULL OR file_path IS NULL")
            quality_checks['videos_null_required_fields'] = cursor.fetchone()[0]
            
            # Check for null required fields in project_videos
            cursor.execute("SELECT COUNT(*) FROM project_videos WHERE id IS NULL OR project_id IS NULL OR video_id IS NULL")
            quality_checks['project_videos_null_required_fields'] = cursor.fetchone()[0]
            
            # Check for empty or whitespace-only names
            cursor.execute("SELECT COUNT(*) FROM projects WHERE trim(name) = ''")
            quality_checks['projects_empty_names'] = cursor.fetchone()[0]
            
            # Check for empty or whitespace-only filenames
            cursor.execute("SELECT COUNT(*) FROM videos WHERE trim(filename) = ''")
            quality_checks['videos_empty_filenames'] = cursor.fetchone()[0]
            
            # Check for reasonable file paths
            cursor.execute("SELECT COUNT(*) FROM videos WHERE file_path IS NOT NULL AND trim(file_path) != ''")
            quality_checks['videos_with_valid_paths'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM videos")
            total_videos = cursor.fetchone()[0]
            
            # Check data type consistency for numeric fields
            cursor.execute("SELECT COUNT(*) FROM videos WHERE duration IS NOT NULL AND duration > 0")
            quality_checks['videos_with_positive_duration'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM videos WHERE duration IS NOT NULL")
            videos_with_duration = cursor.fetchone()[0]
            
            conn.close()
            
            result['details'] = quality_checks
            
            # Calculate quality score
            quality_score_checks = []
            quality_score_checks.append(quality_checks['projects_null_required_fields'] == 0)
            quality_score_checks.append(quality_checks['videos_null_required_fields'] == 0)
            quality_score_checks.append(quality_checks['project_videos_null_required_fields'] == 0)
            quality_score_checks.append(quality_checks['projects_empty_names'] == 0)
            quality_score_checks.append(quality_checks['videos_empty_filenames'] == 0)
            
            if total_videos > 0:
                path_validity_ratio = quality_checks['videos_with_valid_paths'] / total_videos
                quality_score_checks.append(path_validity_ratio >= 0.9)
            
            if videos_with_duration > 0:
                duration_validity_ratio = quality_checks['videos_with_positive_duration'] / videos_with_duration
                quality_score_checks.append(duration_validity_ratio >= 0.8)
            
            result['score'] = sum(quality_score_checks) / len(quality_score_checks) if quality_score_checks else 0.0
            result['status'] = 'passed' if result['score'] >= 0.8 else 'failed'
            
        except Exception as e:
            result['status'] = 'failed'
            result['details']['error'] = str(e)
            result['score'] = 0.0
        
        return result
    
    def _validate_indexes(self) -> Dict[str, Any]:
        """Validate that expected indexes exist"""
        logger.info("Validating indexes...")
        
        result = {
            'status': 'unknown',
            'details': {},
            'score': 0.0
        }
        
        expected_indexes = [
            'idx_project_videos_project_id',
            'idx_project_videos_video_id', 
            'idx_project_videos_project_video',
            'idx_videos_filename',
            'idx_videos_status',
            'idx_videos_camera_model',
            'idx_projects_name',
            'idx_projects_status'
        ]
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all indexes
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            actual_indexes = [row[0] for row in cursor.fetchall()]
            
            index_status = {}
            
            for expected_index in expected_indexes:
                index_status[expected_index] = expected_index in actual_indexes
            
            conn.close()
            
            result['details'] = {
                'expected_indexes': expected_indexes,
                'actual_indexes': actual_indexes,
                'index_status': index_status
            }
            
            # Calculate score based on how many expected indexes exist
            existing_count = sum(index_status.values())
            result['score'] = existing_count / len(expected_indexes) if expected_indexes else 1.0
            result['status'] = 'passed' if result['score'] >= 0.8 else 'failed'
            
        except Exception as e:
            result['status'] = 'failed'
            result['details']['error'] = str(e)
            result['score'] = 0.0
        
        return result
    
    def _validate_foreign_keys(self) -> Dict[str, Any]:
        """Validate foreign key constraints"""
        logger.info("Validating foreign key constraints...")
        
        result = {
            'status': 'unknown',
            'details': {},
            'score': 0.0
        }
        
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Enable foreign key checking
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Check foreign key violations
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_key_check")
            violations = cursor.fetchall()
            
            result['details'] = {
                'violations': violations,
                'violation_count': len(violations)
            }
            
            result['score'] = 1.0 if len(violations) == 0 else 0.0
            result['status'] = 'passed' if len(violations) == 0 else 'failed'
            
            conn.close()
            
        except Exception as e:
            result['status'] = 'failed'
            result['details']['error'] = str(e)
            result['score'] = 0.0
        
        return result
    
    def _calculate_integrity_score(self, validations: Dict[str, Any]) -> float:
        """Calculate overall integrity score"""
        scores = []
        for validation_name, validation_result in validations.items():
            if isinstance(validation_result, dict) and 'score' in validation_result:
                scores.append(validation_result['score'])
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def generate_validation_report(self, validation_results: Dict[str, Any]) -> str:
        """Generate comprehensive validation report"""
        report = f"""
# Database Integrity Validation Report

**Generated:** {validation_results['timestamp']}
**Database:** {validation_results['database_path']}
**Overall Integrity Score:** {validation_results['overall_score']:.2%}

## Summary
"""
        
        for validation_name, validation_result in validation_results['validations'].items():
            if isinstance(validation_result, dict):
                status_icon = '✅' if validation_result['status'] == 'passed' else '❌'
                score = validation_result.get('score', 0.0)
                report += f"- **{validation_name.replace('_', ' ').title()}:** {status_icon} {score:.2%}\n"
        
        report += "\n## Detailed Results\n"
        
        for validation_name, validation_result in validation_results['validations'].items():
            if isinstance(validation_result, dict):
                report += f"\n### {validation_name.replace('_', ' ').title()}\n"
                report += f"**Status:** {validation_result['status']}\n"
                report += f"**Score:** {validation_result.get('score', 0.0):.2%}\n"
                
                if 'details' in validation_result:
                    report += "**Details:**\n"
                    details = validation_result['details']
                    if isinstance(details, dict):
                        for key, value in details.items():
                            if isinstance(value, (list, dict)):
                                report += f"- {key}: {len(value) if isinstance(value, list) else 'complex'}\n"
                            else:
                                report += f"- {key}: {value}\n"
                
        return report
    
    def save_validation_results(self, validation_results: Dict[str, Any], filepath: str = None) -> str:
        """Save validation results to file"""
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"data_integrity_validation_{timestamp}.json"
        
        with open(filepath, 'w') as f:
            json.dump(validation_results, f, indent=2, default=str)
        
        logger.info(f"Validation results saved to: {filepath}")
        return filepath

def main():
    """Main validation execution function"""
    validator = DataIntegrityValidator()
    
    print("🔍 Starting comprehensive data integrity validation...")
    
    # Run validation
    validation_results = validator.run_comprehensive_validation()
    
    # Generate report
    report = validator.generate_validation_report(validation_results)
    print(report)
    
    # Save results
    results_file = validator.save_validation_results(validation_results)
    print(f"\n📊 Detailed results saved to: {results_file}")
    
    # Determine success
    overall_score = validation_results.get('overall_score', 0.0)
    if overall_score >= 0.8:
        print(f"🎉 Validation PASSED! (Score: {overall_score:.2%})")
        return 0
    else:
        print(f"❌ Validation FAILED! (Score: {overall_score:.2%})")
        return 1

if __name__ == "__main__":
    exit(main())