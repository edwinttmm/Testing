#!/usr/bin/env python3
"""
Database Schema Diagnostic Tool for detection_events table
Checks current table structure and identifies missing columns
"""
import sys
import os
from pathlib import Path
from sqlalchemy import text, inspect, MetaData, Table
from sqlalchemy.exc import OperationalError, ProgrammingError
import logging

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from database import engine, get_db
from models import Base, DetectionEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseDiagnostics:
    def __init__(self):
        self.engine = engine
        self.inspector = inspect(engine)
        
    def test_connection(self):
        """Test database connection"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.info("✅ Database connection successful")
                return True
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False
    
    def check_table_exists(self, table_name):
        """Check if a table exists"""
        try:
            tables = self.inspector.get_table_names()
            exists = table_name in tables
            logger.info(f"📋 Available tables: {', '.join(sorted(tables))}")
            return exists
        except Exception as e:
            logger.error(f"❌ Error checking tables: {e}")
            return False
    
    def get_table_schema(self, table_name):
        """Get detailed schema information for a table"""
        if not self.check_table_exists(table_name):
            logger.error(f"❌ Table '{table_name}' does not exist!")
            return None
            
        try:
            columns = self.inspector.get_columns(table_name)
            indexes = self.inspector.get_indexes(table_name)
            foreign_keys = self.inspector.get_foreign_keys(table_name)
            
            logger.info(f"📊 Schema for table '{table_name}':")
            logger.info("=" * 60)
            
            logger.info("COLUMNS:")
            for col in columns:
                nullable = "NULL" if col.get('nullable', True) else "NOT NULL"
                default = f"DEFAULT {col.get('default', 'None')}" if col.get('default') else ""
                logger.info(f"  - {col['name']} ({col['type']}) {nullable} {default}")
            
            logger.info(f"\nINDEXES ({len(indexes)}):")
            for idx in indexes:
                unique = "UNIQUE" if idx.get('unique', False) else ""
                logger.info(f"  - {idx['name']} ({', '.join(idx['column_names'])}) {unique}")
            
            logger.info(f"\nFOREIGN KEYS ({len(foreign_keys)}):")
            for fk in foreign_keys:
                logger.info(f"  - {fk['name']}: {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
            
            return {
                'columns': columns,
                'indexes': indexes,
                'foreign_keys': foreign_keys
            }
        except Exception as e:
            logger.error(f"❌ Error getting schema for {table_name}: {e}")
            return None
    
    def compare_with_model(self, table_name, model_class):
        """Compare actual table with SQLAlchemy model"""
        logger.info(f"🔍 Comparing '{table_name}' table with {model_class.__name__} model")
        logger.info("=" * 60)
        
        # Get actual table schema
        actual_schema = self.get_table_schema(table_name)
        if not actual_schema:
            return False
        
        actual_columns = {col['name']: col for col in actual_schema['columns']}
        
        # Get model columns from SQLAlchemy
        model_table = model_class.__table__
        model_columns = {col.name: col for col in model_table.columns}
        
        logger.info("MODEL vs DATABASE COMPARISON:")
        logger.info("=" * 40)
        
        all_match = True
        
        # Check for missing columns in database
        missing_in_db = set(model_columns.keys()) - set(actual_columns.keys())
        if missing_in_db:
            logger.error(f"❌ Columns missing in database: {', '.join(missing_in_db)}")
            all_match = False
            
            for col_name in missing_in_db:
                model_col = model_columns[col_name]
                logger.info(f"   {col_name}: {model_col.type} {'NOT NULL' if not model_col.nullable else 'NULL'}")
        
        # Check for extra columns in database
        extra_in_db = set(actual_columns.keys()) - set(model_columns.keys())
        if extra_in_db:
            logger.warning(f"⚠️  Extra columns in database: {', '.join(extra_in_db)}")
        
        # Check matching columns
        matching_columns = set(model_columns.keys()) & set(actual_columns.keys())
        logger.info(f"✅ Matching columns: {len(matching_columns)}")
        
        if all_match:
            logger.info("🎉 Database schema matches model perfectly!")
        else:
            logger.error("💥 Database schema does NOT match model!")
        
        return all_match
    
    def generate_migration_sql(self, table_name, model_class):
        """Generate SQL to fix missing columns"""
        logger.info(f"🔧 Generating migration SQL for '{table_name}'")
        
        # Get actual table schema
        actual_schema = self.get_table_schema(table_name)
        if not actual_schema:
            return None
            
        actual_columns = {col['name'] for col in actual_schema['columns']}
        
        # Get model columns
        model_table = model_class.__table__
        model_columns = {col.name: col for col in model_table.columns}
        
        # Find missing columns
        missing_columns = set(model_columns.keys()) - actual_columns
        
        if not missing_columns:
            logger.info("✅ No missing columns to add")
            return []
        
        sql_statements = []
        
        logger.info("📝 Generated SQL statements:")
        logger.info("=" * 40)
        
        for col_name in missing_columns:
            model_col = model_columns[col_name]
            
            # Map SQLAlchemy types to database types
            col_type = str(model_col.type)
            if 'VARCHAR' in col_type.upper():
                db_type = col_type
            elif 'INTEGER' in col_type.upper():
                db_type = 'INTEGER'
            elif 'FLOAT' in col_type.upper():
                db_type = 'FLOAT'
            elif 'BOOLEAN' in col_type.upper():
                db_type = 'BOOLEAN'
            elif 'TEXT' in col_type.upper():
                db_type = 'TEXT'
            elif 'JSON' in col_type.upper():
                db_type = 'JSON'
            elif 'DATETIME' in col_type.upper():
                db_type = 'DATETIME'
            else:
                db_type = 'TEXT'  # Default fallback
            
            # Add nullable/default constraints
            constraints = []
            if not model_col.nullable:
                if model_col.default is not None:
                    default_val = model_col.default.arg if hasattr(model_col.default, 'arg') else 'NULL'
                    constraints.append(f"DEFAULT {default_val}")
                else:
                    constraints.append("DEFAULT NULL")  # For existing rows
            
            constraint_str = " ".join(constraints)
            sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {db_type} {constraint_str};"
            
            sql_statements.append(sql)
            logger.info(f"  {sql}")
        
        return sql_statements
    
    def check_detection_events_issue(self):
        """Specifically diagnose the detection_events table issue"""
        logger.info("🔍 DETECTION EVENTS DIAGNOSIS")
        logger.info("=" * 50)
        
        # Test connection first
        if not self.test_connection():
            return False
        
        # Check if detection_events table exists
        table_exists = self.check_table_exists("detection_events")
        
        if not table_exists:
            logger.error("❌ detection_events table does not exist!")
            logger.info("💡 Solution: Run database initialization or create table manually")
            return False
        
        # Get schema and compare with model
        schema_match = self.compare_with_model("detection_events", DetectionEvent)
        
        if not schema_match:
            logger.info("🔧 RECOMMENDED ACTIONS:")
            logger.info("-" * 30)
            
            # Generate migration SQL
            sql_statements = self.generate_migration_sql("detection_events", DetectionEvent)
            
            if sql_statements:
                logger.info("1. Execute the following SQL statements:")
                for sql in sql_statements:
                    logger.info(f"   {sql}")
                
                # Save to file
                migration_file = Path(__file__).parent / "fix_detection_events_columns.sql"
                with open(migration_file, 'w') as f:
                    f.write("-- Fix detection_events table missing columns\n")
                    f.write("-- Generated by diagnose_detection_events_schema.py\n\n")
                    for sql in sql_statements:
                        f.write(sql + "\n")
                
                logger.info(f"📁 SQL saved to: {migration_file}")
                logger.info("2. OR run the migration script: python migrate_detection_events.py")
        
        return schema_match

def main():
    """Run diagnostics"""
    print("🔬 Database Schema Diagnostics Tool")
    print("=" * 50)
    
    diagnostics = DatabaseDiagnostics()
    
    try:
        # Run specific diagnosis for detection_events
        success = diagnostics.check_detection_events_issue()
        
        if success:
            print("\n🎉 Database schema is correct!")
        else:
            print("\n❌ Database schema issues found - see recommendations above")
            
        return success
        
    except Exception as e:
        logger.error(f"💥 Diagnostic failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)