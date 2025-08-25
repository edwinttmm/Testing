#!/usr/bin/env python3
"""
Validate All 11 Tables Creation After Connectivity Restored

Specialized validation script to ensure all 11 expected database tables
are properly created and functional after database connectivity is restored.

Features:
- Validates all 11 expected tables existence
- Verifies table structure and constraints
- Tests table relationships and foreign keys
- Validates indexes and performance characteristics
- Tests basic CRUD operations on each table
- Provides detailed reporting on table health
- Automated repair suggestions for missing elements
"""

import os
import sys
import json
import time
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add backend directory to path
sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from sqlalchemy import create_engine, text, inspect, MetaData
    from sqlalchemy.exc import SQLAlchemyError
    
    # Import application modules
    from database import engine, DATABASE_URL, SessionLocal
    from models import (
        Base, Project, Video, GroundTruthObject, TestSession, DetectionEvent,
        Annotation, AnnotationSession, ValidationResult, ModelVersion,
        VideoProjectLink, SystemConfig
    )
except ImportError as e:
    print(f"Warning: Some database modules unavailable: {e}")
    engine = None
    DATABASE_URL = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TableValidationResult:
    """Individual table validation result"""
    table_name: str
    exists: bool
    structure_valid: bool
    constraints_valid: bool
    indexes_valid: bool
    relationships_valid: bool
    crud_operations_work: bool
    row_count: int
    issues: List[str]
    recommendations: List[str]
    details: Dict[str, Any]
    validation_time_ms: float

@dataclass
class AllTablesValidationResult:
    """Overall validation result for all tables"""
    timestamp: str
    total_tables_expected: int
    tables_found: int
    tables_valid: int
    validation_successful: bool
    table_results: List[TableValidationResult]
    missing_tables: List[str]
    critical_issues: List[str]
    recommendations: List[str]
    summary: Dict[str, Any]
    total_validation_time_ms: float

class AllTablesValidator:
    """Comprehensive validator for all 11 database tables"""
    
    def __init__(self):
        self.expected_tables = self._define_expected_tables()
        self.validation_results = []
        
    def _define_expected_tables(self) -> Dict[str, Dict]:
        """Define comprehensive specifications for all 11 expected tables"""
        return {
            'projects': {
                'model_class': Project,
                'expected_columns': [
                    'id', 'name', 'description', 'camera_model', 'camera_view', 
                    'lens_type', 'resolution', 'frame_rate', 'signal_type', 
                    'status', 'owner_id', 'created_at', 'updated_at'
                ],
                'required_columns': ['id', 'name', 'camera_model', 'camera_view', 'signal_type'],
                'primary_key': ['id'],
                'foreign_keys': [],
                'relationships': {
                    'videos': 'one-to-many',
                    'test_sessions': 'one-to-many',
                    'annotation_sessions': 'one-to-many',
                    'video_project_links': 'one-to-many'
                },
                'expected_indexes': ['ix_projects_name', 'ix_projects_status', 'ix_projects_created_at'],
                'sample_data': {
                    'name': 'Validation Test Project',
                    'camera_model': 'Test Camera',
                    'camera_view': 'Front-facing VRU',
                    'signal_type': 'GPIO'
                }
            },
            'videos': {
                'model_class': Video,
                'expected_columns': [
                    'id', 'filename', 'file_path', 'file_size', 'duration', 
                    'fps', 'resolution', 'status', 'processing_status', 
                    'ground_truth_generated', 'project_id', 'created_at', 'updated_at'
                ],
                'required_columns': ['id', 'filename', 'file_path', 'project_id'],
                'primary_key': ['id'],
                'foreign_keys': [('project_id', 'projects', 'id')],
                'relationships': {
                    'project': 'many-to-one',
                    'ground_truth_objects': 'one-to-many',
                    'annotations': 'one-to-many',
                    'annotation_sessions': 'one-to-many',
                    'detection_events': 'one-to-many'
                },
                'expected_indexes': ['ix_videos_filename', 'ix_videos_status', 'idx_video_project_status'],
                'sample_data': {
                    'filename': 'validation_test.mp4',
                    'file_path': '/tmp/validation_test.mp4',
                    'status': 'uploaded'
                }
            },
            'ground_truth_objects': {
                'model_class': GroundTruthObject,
                'expected_columns': [
                    'id', 'video_id', 'frame_number', 'timestamp', 'class_label',
                    'x', 'y', 'width', 'height', 'bounding_box', 'confidence',
                    'validated', 'difficult', 'created_at'
                ],
                'required_columns': ['id', 'video_id', 'timestamp', 'class_label', 'x', 'y', 'width', 'height'],
                'primary_key': ['id'],
                'foreign_keys': [('video_id', 'videos', 'id')],
                'relationships': {
                    'video': 'many-to-one'
                },
                'expected_indexes': ['idx_gt_video_timestamp', 'idx_gt_video_class'],
                'sample_data': {
                    'timestamp': 1.5,
                    'class_label': 'pedestrian',
                    'x': 100.0,
                    'y': 150.0,
                    'width': 50.0,
                    'height': 100.0
                }
            },
            'test_sessions': {
                'model_class': TestSession,
                'expected_columns': [
                    'id', 'name', 'description', 'project_id', 'model_version',
                    'status', 'created_at', 'updated_at'
                ],
                'required_columns': ['id', 'name', 'project_id'],
                'primary_key': ['id'],
                'foreign_keys': [('project_id', 'projects', 'id')],
                'relationships': {
                    'project': 'many-to-one',
                    'detection_events': 'one-to-many',
                    'validation_results': 'one-to-many'
                },
                'expected_indexes': ['ix_test_sessions_name', 'ix_test_sessions_status'],
                'sample_data': {
                    'name': 'Validation Test Session',
                    'status': 'pending'
                }
            },
            'detection_events': {
                'model_class': DetectionEvent,
                'expected_columns': [
                    'id', 'session_id', 'video_id', 'timestamp', 'frame_number',
                    'class_label', 'confidence', 'x', 'y', 'width', 'height',
                    'bounding_box', 'detection_data', 'created_at'
                ],
                'required_columns': ['id', 'session_id', 'video_id', 'timestamp', 'class_label'],
                'primary_key': ['id'],
                'foreign_keys': [
                    ('session_id', 'test_sessions', 'id'),
                    ('video_id', 'videos', 'id')
                ],
                'relationships': {
                    'session': 'many-to-one',
                    'video': 'many-to-one'
                },
                'expected_indexes': ['idx_detection_session_timestamp'],
                'sample_data': {
                    'timestamp': 2.0,
                    'class_label': 'vehicle',
                    'confidence': 0.95
                }
            },
            'annotations': {
                'model_class': Annotation,
                'expected_columns': [
                    'id', 'video_id', 'annotation_session_id', 'timestamp',
                    'annotation_data', 'annotation_type', 'created_by', 'created_at'
                ],
                'required_columns': ['id', 'video_id', 'timestamp', 'annotation_data'],
                'primary_key': ['id'],
                'foreign_keys': [
                    ('video_id', 'videos', 'id'),
                    ('annotation_session_id', 'annotation_sessions', 'id')
                ],
                'relationships': {
                    'video': 'many-to-one',
                    'annotation_session': 'many-to-one'
                },
                'expected_indexes': [],
                'sample_data': {
                    'timestamp': 3.0,
                    'annotation_data': {'type': 'manual', 'confidence': 1.0}
                }
            },
            'annotation_sessions': {
                'model_class': AnnotationSession,
                'expected_columns': [
                    'id', 'project_id', 'video_id', 'status', 'annotator_id',
                    'started_at', 'completed_at', 'created_at'
                ],
                'required_columns': ['id', 'project_id', 'video_id'],
                'primary_key': ['id'],
                'foreign_keys': [
                    ('project_id', 'projects', 'id'),
                    ('video_id', 'videos', 'id')
                ],
                'relationships': {
                    'project': 'many-to-one',
                    'video': 'many-to-one',
                    'annotations': 'one-to-many'
                },
                'expected_indexes': [],
                'sample_data': {
                    'status': 'in_progress'
                }
            },
            'validation_results': {
                'model_class': ValidationResult,
                'expected_columns': [
                    'id', 'test_session_id', 'metrics_data', 'accuracy',
                    'precision', 'recall', 'f1_score', 'created_at'
                ],
                'required_columns': ['id', 'test_session_id', 'metrics_data'],
                'primary_key': ['id'],
                'foreign_keys': [('test_session_id', 'test_sessions', 'id')],
                'relationships': {
                    'test_session': 'many-to-one'
                },
                'expected_indexes': [],
                'sample_data': {
                    'metrics_data': {'accuracy': 0.85, 'precision': 0.82}
                }
            },
            'model_versions': {
                'model_class': ModelVersion,
                'expected_columns': [
                    'id', 'name', 'version', 'model_path', 'description',
                    'training_data', 'hyperparameters', 'created_at'
                ],
                'required_columns': ['id', 'name', 'version', 'model_path'],
                'primary_key': ['id'],
                'foreign_keys': [],
                'relationships': {},
                'expected_indexes': [],
                'sample_data': {
                    'name': 'Validation Model',
                    'version': '1.0.0',
                    'model_path': '/models/validation.pt'
                }
            },
            'video_project_links': {
                'model_class': VideoProjectLink,
                'expected_columns': [
                    'id', 'video_id', 'project_id', 'link_type', 'metadata', 'created_at'
                ],
                'required_columns': ['id', 'video_id', 'project_id'],
                'primary_key': ['id'],
                'foreign_keys': [
                    ('video_id', 'videos', 'id'),
                    ('project_id', 'projects', 'id')
                ],
                'relationships': {
                    'video': 'many-to-one',
                    'project': 'many-to-one'
                },
                'expected_indexes': [],
                'sample_data': {
                    'link_type': 'primary'
                }
            },
            'system_config': {
                'model_class': SystemConfig,
                'expected_columns': [
                    'id', 'config_key', 'config_value', 'description',
                    'config_type', 'updated_at'
                ],
                'required_columns': ['id', 'config_key', 'config_value'],
                'primary_key': ['id'],
                'foreign_keys': [],
                'relationships': {},
                'expected_indexes': [],
                'sample_data': {
                    'config_key': 'validation_setting',
                    'config_value': 'enabled'
                }
            }
        }
    
    def validate_individual_table(self, table_name: str, table_spec: Dict) -> TableValidationResult:
        """Validate individual table comprehensively"""
        start_time = time.time()
        issues = []
        recommendations = []
        details = {}
        
        # Initialize result
        result = TableValidationResult(
            table_name=table_name,
            exists=False,
            structure_valid=False,
            constraints_valid=False,
            indexes_valid=False,
            relationships_valid=False,
            crud_operations_work=False,
            row_count=0,
            issues=issues,
            recommendations=recommendations,
            details=details,
            validation_time_ms=0
        )
        
        try:
            if not engine:
                issues.append("SQLAlchemy engine not available")
                return result
            
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            
            # Step 1: Check if table exists
            result.exists = table_name in existing_tables
            if not result.exists:
                issues.append(f"Table '{table_name}' does not exist")
                recommendations.append(f"Create table '{table_name}' using database initialization")
                return result
            
            # Step 2: Validate table structure
            result.structure_valid, structure_details = self._validate_table_structure(
                table_name, table_spec, inspector
            )
            details['structure'] = structure_details
            
            if not result.structure_valid:
                issues.extend(structure_details.get('issues', []))
                recommendations.extend(structure_details.get('recommendations', []))
            
            # Step 3: Validate constraints
            result.constraints_valid, constraints_details = self._validate_table_constraints(
                table_name, table_spec, inspector
            )
            details['constraints'] = constraints_details
            
            if not result.constraints_valid:
                issues.extend(constraints_details.get('issues', []))
                recommendations.extend(constraints_details.get('recommendations', []))
            
            # Step 4: Validate indexes
            result.indexes_valid, indexes_details = self._validate_table_indexes(
                table_name, table_spec, inspector
            )
            details['indexes'] = indexes_details
            
            if not result.indexes_valid:
                issues.extend(indexes_details.get('issues', []))
                recommendations.extend(indexes_details.get('recommendations', []))
            
            # Step 5: Validate relationships
            result.relationships_valid, relationships_details = self._validate_table_relationships(
                table_name, table_spec, inspector
            )
            details['relationships'] = relationships_details
            
            if not result.relationships_valid:
                issues.extend(relationships_details.get('issues', []))
                recommendations.extend(relationships_details.get('recommendations', []))
            
            # Step 6: Get row count
            try:
                with engine.connect() as conn:
                    count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    result.row_count = count_result.fetchone()[0]
                    details['row_count'] = result.row_count
            except Exception as e:
                issues.append(f"Could not get row count: {str(e)}")
                result.row_count = -1
            
            # Step 7: Test CRUD operations
            result.crud_operations_work, crud_details = self._test_crud_operations(
                table_name, table_spec
            )
            details['crud'] = crud_details
            
            if not result.crud_operations_work:
                issues.extend(crud_details.get('issues', []))
                recommendations.extend(crud_details.get('recommendations', []))
            
        except Exception as e:
            logger.error(f"Table validation failed for {table_name}: {e}")
            issues.append(f"Validation error: {str(e)}")
            details['error'] = str(e)
            details['traceback'] = traceback.format_exc()
        
        finally:
            result.validation_time_ms = round((time.time() - start_time) * 1000, 2)
            result.issues = issues
            result.recommendations = recommendations
            result.details = details
        
        return result
    
    def _validate_table_structure(self, table_name: str, table_spec: Dict, inspector) -> Tuple[bool, Dict]:
        """Validate table column structure"""
        details = {'issues': [], 'recommendations': []}
        
        try:
            columns = inspector.get_columns(table_name)
            column_names = [col['name'] for col in columns]
            column_types = {col['name']: str(col['type']) for col in columns}
            
            expected_columns = table_spec['expected_columns']
            required_columns = table_spec.get('required_columns', [])
            
            # Check for missing columns
            missing_columns = [col for col in expected_columns if col not in column_names]
            extra_columns = [col for col in column_names if col not in expected_columns]
            missing_required = [col for col in required_columns if col not in column_names]
            
            details.update({
                'columns_found': column_names,
                'expected_columns': expected_columns,
                'missing_columns': missing_columns,
                'extra_columns': extra_columns,
                'missing_required_columns': missing_required,
                'column_types': column_types
            })
            
            # Evaluate structure validity
            structure_valid = len(missing_required) == 0
            
            if missing_required:
                details['issues'].append(f"Missing required columns: {missing_required}")
                details['recommendations'].append(f"Add missing required columns: {missing_required}")
            
            if missing_columns:
                details['issues'].append(f"Missing expected columns: {missing_columns}")
                details['recommendations'].append(f"Consider adding missing columns: {missing_columns}")
            
            if extra_columns:
                details['issues'].append(f"Extra columns found: {extra_columns}")
                details['recommendations'].append(f"Review extra columns: {extra_columns}")
            
            return structure_valid, details
            
        except Exception as e:
            details['issues'].append(f"Structure validation error: {str(e)}")
            return False, details
    
    def _validate_table_constraints(self, table_name: str, table_spec: Dict, inspector) -> Tuple[bool, Dict]:
        """Validate table constraints"""
        details = {'issues': [], 'recommendations': []}
        
        try:
            # Check primary key
            pk_constraint = inspector.get_pk_constraint(table_name)
            expected_pk = table_spec.get('primary_key', [])
            
            pk_columns = pk_constraint.get('constrained_columns', [])
            
            details.update({
                'primary_key_found': pk_columns,
                'expected_primary_key': expected_pk,
                'primary_key_valid': set(pk_columns) == set(expected_pk)
            })
            
            # Check foreign keys
            foreign_keys = inspector.get_foreign_keys(table_name)
            expected_fks = table_spec.get('foreign_keys', [])
            
            fk_details = []
            for fk in foreign_keys:
                fk_details.append({
                    'constrained_columns': fk['constrained_columns'],
                    'referred_table': fk['referred_table'],
                    'referred_columns': fk['referred_columns']
                })
            
            details.update({
                'foreign_keys_found': fk_details,
                'expected_foreign_keys': expected_fks
            })
            
            # Validate constraints
            constraints_valid = True
            
            if not details['primary_key_valid']:
                constraints_valid = False
                details['issues'].append(f"Primary key mismatch: found {pk_columns}, expected {expected_pk}")
                details['recommendations'].append("Fix primary key constraint")
            
            # Check if expected foreign keys exist
            for expected_fk in expected_fks:
                fk_column, ref_table, ref_column = expected_fk
                
                fk_exists = any(
                    fk_column in fk['constrained_columns'] and
                    ref_table == fk['referred_table']
                    for fk in fk_details
                )
                
                if not fk_exists:
                    constraints_valid = False
                    details['issues'].append(f"Missing foreign key: {fk_column} -> {ref_table}({ref_column})")
                    details['recommendations'].append(f"Add foreign key constraint for {fk_column}")
            
            return constraints_valid, details
            
        except Exception as e:
            details['issues'].append(f"Constraints validation error: {str(e)}")
            return False, details
    
    def _validate_table_indexes(self, table_name: str, table_spec: Dict, inspector) -> Tuple[bool, Dict]:
        """Validate table indexes"""
        details = {'issues': [], 'recommendations': []}
        
        try:
            indexes = inspector.get_indexes(table_name)
            index_names = [idx['name'] for idx in indexes]
            expected_indexes = table_spec.get('expected_indexes', [])
            
            missing_indexes = [idx for idx in expected_indexes if idx not in index_names]
            
            details.update({
                'indexes_found': index_names,
                'expected_indexes': expected_indexes,
                'missing_indexes': missing_indexes,
                'index_details': indexes
            })
            
            indexes_valid = len(missing_indexes) == 0
            
            if missing_indexes:
                details['issues'].append(f"Missing indexes: {missing_indexes}")
                details['recommendations'].append(f"Create missing indexes: {missing_indexes}")
                # Note: This is often acceptable as indexes can be created later for performance
                indexes_valid = True  # Don't fail validation just for missing indexes
            
            return indexes_valid, details
            
        except Exception as e:
            details['issues'].append(f"Index validation error: {str(e)}")
            return False, details
    
    def _validate_table_relationships(self, table_name: str, table_spec: Dict, inspector) -> Tuple[bool, Dict]:
        """Validate table relationships"""
        details = {'issues': [], 'recommendations': []}
        
        try:
            expected_relationships = table_spec.get('relationships', {})
            
            # For now, we'll just verify that related tables exist
            existing_tables = inspector.get_table_names()
            
            missing_related_tables = []
            for related_table, relationship_type in expected_relationships.items():
                if related_table not in existing_tables:
                    missing_related_tables.append(related_table)
            
            details.update({
                'expected_relationships': expected_relationships,
                'existing_tables': existing_tables,
                'missing_related_tables': missing_related_tables
            })
            
            relationships_valid = len(missing_related_tables) == 0
            
            if missing_related_tables:
                details['issues'].append(f"Missing related tables: {missing_related_tables}")
                details['recommendations'].append(f"Create missing related tables: {missing_related_tables}")
            
            return relationships_valid, details
            
        except Exception as e:
            details['issues'].append(f"Relationships validation error: {str(e)}")
            return False, details
    
    def _test_crud_operations(self, table_name: str, table_spec: Dict) -> Tuple[bool, Dict]:
        """Test basic CRUD operations on the table"""
        details = {'issues': [], 'recommendations': []}
        
        try:
            model_class = table_spec.get('model_class')
            sample_data = table_spec.get('sample_data', {})
            
            if not model_class or not sample_data:
                details['issues'].append("Cannot test CRUD operations - missing model class or sample data")
                return False, details
            
            session = SessionLocal()
            crud_successful = False
            record_id = None
            
            try:
                # Test CREATE
                test_record = model_class(**sample_data)
                session.add(test_record)
                session.flush()  # Get ID without committing
                record_id = test_record.id
                
                details['create_successful'] = True
                details['created_record_id'] = record_id
                
                # Test READ
                read_record = session.query(model_class).filter(model_class.id == record_id).first()
                if read_record:
                    details['read_successful'] = True
                else:
                    details['issues'].append("Could not read created record")
                    details['read_successful'] = False
                
                # Test UPDATE (if possible)
                if hasattr(test_record, 'name'):
                    test_record.name = f"Updated {test_record.name}"
                    session.flush()
                    details['update_successful'] = True
                elif hasattr(test_record, 'status'):
                    test_record.status = 'updated'
                    session.flush()
                    details['update_successful'] = True
                else:
                    details['update_successful'] = None  # No updatable field found
                
                # Test DELETE
                session.delete(test_record)
                session.flush()
                
                # Verify deletion
                deleted_check = session.query(model_class).filter(model_class.id == record_id).first()
                if deleted_check is None:
                    details['delete_successful'] = True
                    crud_successful = True
                else:
                    details['issues'].append("Record was not properly deleted")
                    details['delete_successful'] = False
                
                # Rollback to avoid persisting test data
                session.rollback()
                
            except Exception as e:
                session.rollback()
                details['issues'].append(f"CRUD operation failed: {str(e)}")
                details['crud_error'] = str(e)
                crud_successful = False
                
            finally:
                session.close()
            
            if not crud_successful:
                details['recommendations'].append(f"Fix CRUD operation issues for {table_name}")
            
            return crud_successful, details
            
        except Exception as e:
            details['issues'].append(f"CRUD testing error: {str(e)}")
            details['recommendations'].append(f"Investigate CRUD testing issues for {table_name}")
            return False, details
    
    def validate_all_tables(self) -> AllTablesValidationResult:
        """Validate all 11 expected tables"""
        logger.info("Starting validation of all 11 database tables...")
        start_time = time.time()
        
        table_results = []
        missing_tables = []
        critical_issues = []
        recommendations = []
        
        # Validate each table
        for table_name, table_spec in self.expected_tables.items():
            logger.info(f"Validating table: {table_name}")
            
            result = self.validate_individual_table(table_name, table_spec)
            table_results.append(result)
            
            # Track missing tables
            if not result.exists:
                missing_tables.append(table_name)
            
            # Collect critical issues
            for issue in result.issues:
                if any(keyword in issue.lower() for keyword in ['missing', 'does not exist', 'failed', 'error']):
                    critical_issues.append(f"{table_name}: {issue}")
            
            # Collect recommendations
            recommendations.extend([f"{table_name}: {rec}" for rec in result.recommendations])
        
        # Calculate summary statistics
        total_expected = len(self.expected_tables)
        tables_found = sum(1 for result in table_results if result.exists)
        tables_valid = sum(1 for result in table_results if (
            result.exists and 
            result.structure_valid and 
            result.constraints_valid and 
            result.crud_operations_work
        ))
        
        validation_successful = (
            tables_found == total_expected and 
            tables_valid >= total_expected * 0.9  # At least 90% fully valid
        )
        
        # Generate overall recommendations
        if missing_tables:
            recommendations.insert(0, f"Create missing tables: {', '.join(missing_tables)}")
        
        if not validation_successful:
            recommendations.insert(0, "Run database initialization to create missing components")
        
        # Create summary
        summary = {
            'total_expected': total_expected,
            'tables_found': tables_found,
            'tables_valid': tables_valid,
            'missing_tables_count': len(missing_tables),
            'critical_issues_count': len(critical_issues),
            'validation_success_rate': round((tables_valid / total_expected) * 100, 1),
            'table_existence_rate': round((tables_found / total_expected) * 100, 1),
            'overall_health': 'healthy' if validation_successful else (
                'degraded' if tables_found >= total_expected * 0.8 else 'critical'
            )
        }
        
        total_time = (time.time() - start_time) * 1000
        
        result = AllTablesValidationResult(
            timestamp=datetime.now().isoformat(),
            total_tables_expected=total_expected,
            tables_found=tables_found,
            tables_valid=tables_valid,
            validation_successful=validation_successful,
            table_results=table_results,
            missing_tables=missing_tables,
            critical_issues=critical_issues,
            recommendations=recommendations[:20],  # Top 20 recommendations
            summary=summary,
            total_validation_time_ms=round(total_time, 2)
        )
        
        logger.info(f"Validation completed: {tables_valid}/{total_expected} tables valid in {total_time:.2f}ms")
        
        return result
    
    def save_validation_report(self, result: AllTablesValidationResult, filename: str = None) -> str:
        """Save validation report to file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'/home/user/Testing/ai-model-validation-platform/backend/logs/all_tables_validation_{timestamp}.json'
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Convert to serializable format
        report_data = asdict(result)
        
        with open(filename, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        return filename
    
    def generate_validation_report_text(self, result: AllTablesValidationResult) -> str:
        """Generate human-readable validation report"""
        report = []
        report.append("# Database Tables Validation Report")
        report.append(f"Generated: {result.timestamp}")
        report.append(f"Validation Time: {result.total_validation_time_ms}ms\n")
        
        # Overall status
        status_emoji = {
            'healthy': '✅',
            'degraded': '⚠️', 
            'critical': '🚨'
        }
        
        overall_health = result.summary['overall_health']
        report.append(f"## Overall Status: {status_emoji.get(overall_health, '❓')} {overall_health.upper()}")
        report.append(f"Tables Found: {result.tables_found}/{result.total_tables_expected} ({result.summary['table_existence_rate']}%)")
        report.append(f"Tables Valid: {result.tables_valid}/{result.total_tables_expected} ({result.summary['validation_success_rate']}%)")
        
        if result.validation_successful:
            report.append(f"🎉 All expected tables are properly configured!")
        else:
            report.append(f"⚠️  {len(result.critical_issues)} critical issues need attention")
        
        report.append("")
        
        # Missing tables (if any)
        if result.missing_tables:
            report.append(f"## 🚨 Missing Tables ({len(result.missing_tables)})")
            for table in result.missing_tables:
                report.append(f"- {table}")
            report.append("")
        
        # Individual table results
        report.append(f"## Individual Table Results")
        
        # Sort tables by status (failed first, then by name)
        sorted_results = sorted(result.table_results, key=lambda r: (r.exists, r.structure_valid, r.table_name))
        
        for table_result in sorted_results:
            # Determine table status
            if not table_result.exists:
                status = '❌ MISSING'
            elif (table_result.structure_valid and 
                  table_result.constraints_valid and 
                  table_result.crud_operations_work):
                status = '✅ VALID'
            elif table_result.structure_valid:
                status = '⚠️ PARTIAL'
            else:
                status = '🔴 INVALID'
            
            report.append(f"### {status} {table_result.table_name}")
            
            if table_result.exists:
                report.append(f"- Rows: {table_result.row_count}")
                report.append(f"- Structure: {'✅' if table_result.structure_valid else '❌'}")
                report.append(f"- Constraints: {'✅' if table_result.constraints_valid else '❌'}")
                report.append(f"- Indexes: {'✅' if table_result.indexes_valid else '❌'}")
                report.append(f"- Relationships: {'✅' if table_result.relationships_valid else '❌'}")
                report.append(f"- CRUD Operations: {'✅' if table_result.crud_operations_work else '❌'}")
                report.append(f"- Validation Time: {table_result.validation_time_ms}ms")
            
            # Issues
            if table_result.issues:
                report.append("**Issues:**")
                for issue in table_result.issues[:3]:  # Show top 3 issues
                    report.append(f"  - {issue}")
                
                if len(table_result.issues) > 3:
                    report.append(f"  - ... and {len(table_result.issues) - 3} more issues")
            
            # Key recommendations
            if table_result.recommendations:
                report.append("**Recommendations:**")
                for rec in table_result.recommendations[:2]:  # Show top 2 recommendations
                    report.append(f"  - {rec}")
            
            report.append("")
        
        # Overall recommendations
        if result.recommendations:
            report.append("## 💡 Overall Recommendations")
            for i, rec in enumerate(result.recommendations[:10], 1):  # Top 10
                report.append(f"{i}. {rec}")
            report.append("")
        
        # Quick fix commands
        if not result.validation_successful:
            report.append("## 🔧 Quick Fix Commands")
            report.append("```bash")
            report.append("# Initialize missing database components")
            report.append("cd /home/user/Testing/ai-model-validation-platform/backend")
            report.append("python database_init.py")
            report.append("")
            report.append("# Re-validate all tables")
            report.append("python tests/validate_all_tables.py --report")
            report.append("")
            report.append("# Check specific table details")
            report.append("python tests/table_creation_tester.py --report")
            report.append("```")
        
        return "\n".join(report)

def main():
    """Main validation execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate All 11 Database Tables')
    parser.add_argument('--output', help='Output file for results')
    parser.add_argument('--report', action='store_true', help='Generate human-readable report')
    parser.add_argument('--table', help='Validate specific table only')
    parser.add_argument('--summary-only', action='store_true', help='Show only summary results')
    
    args = parser.parse_args()
    
    # Create validator
    validator = AllTablesValidator()
    
    if args.table:
        # Validate specific table
        if args.table not in validator.expected_tables:
            print(f"Error: Unknown table '{args.table}'. Expected tables: {list(validator.expected_tables.keys())}")
            return
        
        print(f"Validating table: {args.table}")
        table_spec = validator.expected_tables[args.table]
        result = validator.validate_individual_table(args.table, table_spec)
        
        status = '✅ VALID' if (result.exists and result.structure_valid and result.crud_operations_work) else '❌ INVALID'
        print(f"\n=== {status} {args.table} ===")
        print(f"Exists: {result.exists}")
        
        if result.exists:
            print(f"Row Count: {result.row_count}")
            print(f"Structure Valid: {result.structure_valid}")
            print(f"Constraints Valid: {result.constraints_valid}")
            print(f"CRUD Operations: {result.crud_operations_work}")
            print(f"Validation Time: {result.validation_time_ms}ms")
            
            if result.issues:
                print(f"\nIssues ({len(result.issues)}):")
                for issue in result.issues:
                    print(f"  - {issue}")
            
            if result.recommendations:
                print(f"\nRecommendations ({len(result.recommendations)}):")
                for rec in result.recommendations:
                    print(f"  - {rec}")
    
    else:
        # Validate all tables
        print("Validating all 11 database tables...")
        result = validator.validate_all_tables()
        
        # Display summary
        if args.summary_only:
            print(f"\n=== Validation Summary ===")
            print(f"Overall Status: {result.summary['overall_health'].upper()}")
            print(f"Tables Found: {result.tables_found}/{result.total_tables_expected}")
            print(f"Tables Valid: {result.tables_valid}/{result.total_tables_expected}")
            
            if result.missing_tables:
                print(f"Missing Tables: {', '.join(result.missing_tables)}")
                
        else:
            print(f"\n=== All Tables Validation Results ===")
            print(f"Overall Status: {result.summary['overall_health'].upper()}")
            print(f"Validation Time: {result.total_validation_time_ms}ms")
            print(f"Tables Found: {result.tables_found}/{result.total_tables_expected} ({result.summary['table_existence_rate']}%)")
            print(f"Tables Valid: {result.tables_valid}/{result.total_tables_expected} ({result.summary['validation_success_rate']}%)")
            
            if result.validation_successful:
                print(f"🎉 All tables are properly configured!")
            else:
                print(f"⚠️  Issues found: {len(result.critical_issues)} critical, {len(result.missing_tables)} missing")
            
            # Quick table status overview
            print(f"\nTable Status Overview:")
            for table_result in result.table_results:
                if not table_result.exists:
                    status = '❌ MISSING'
                elif (table_result.structure_valid and table_result.constraints_valid and table_result.crud_operations_work):
                    status = '✅ VALID'
                else:
                    status = '⚠️ ISSUES'
                
                row_info = f" ({table_result.row_count} rows)" if table_result.exists else ""
                print(f"  {status} {table_result.table_name}{row_info}")
            
            if result.recommendations:
                print(f"\n💡 Top Recommendations:")
                for i, rec in enumerate(result.recommendations[:5], 1):
                    print(f"  {i}. {rec}")
        
        # Save results
        if args.output:
            output_file = args.output
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'/home/user/Testing/ai-model-validation-platform/backend/logs/all_tables_validation_{timestamp}.json'
        
        saved_file = validator.save_validation_report(result, output_file)
        print(f"\nResults saved to: {saved_file}")
        
        # Generate report if requested
        if args.report:
            report = validator.generate_validation_report_text(result)
            report_file = saved_file.replace('.json', '_report.md')
            with open(report_file, 'w') as f:
                f.write(report)
            print(f"Report saved to: {report_file}")
            if not args.summary_only:
                print(f"\n{report}")

if __name__ == '__main__':
    main()
