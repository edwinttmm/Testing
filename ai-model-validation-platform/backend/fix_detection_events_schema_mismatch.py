#!/usr/bin/env python3
"""
Fix DetectionEvent Schema Mismatch Issues
Corrects code that uses incorrect field names when creating DetectionEvent records
"""
import sys
from pathlib import Path
import logging

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_detection_event_usage():
    """Analyze and fix DetectionEvent field name mismatches"""
    
    logger.info("🔍 DETECTION EVENT SCHEMA MISMATCH ANALYSIS")
    logger.info("=" * 60)
    
    issues_found = []
    
    # Issue 1: test_execution_service.py uses incorrect field names
    test_execution_file = backend_dir / "services" / "test_execution_service.py"
    
    logger.info("📁 Analyzing test_execution_service.py...")
    
    if test_execution_file.exists():
        with open(test_execution_file, 'r') as f:
            content = f.read()
        
        # Check for video_id usage (should not exist)
        if "video_id=video.id" in content and "# REMOVED:" not in content:
            issues_found.append({
                'file': str(test_execution_file),
                'line_approx': 313,
                'issue': 'video_id field does not exist in DetectionEvent model',
                'fix': 'Remove video_id parameter - DetectionEvent links to TestSession, not Video'
            })
            logger.error("❌ Found video_id field usage (does not exist in model)")
        elif "# REMOVED: video_id=video.id" in content:
            logger.info("✅ video_id usage correctly removed/commented")
        
        # Check for incorrect bounding box field names
        if "x=detection.bounding_box.x" in content and "bounding_box_x=detection.bounding_box.x" not in content:
            issues_found.append({
                'file': str(test_execution_file),
                'line_approx': 318,
                'issue': 'Using "x" instead of "bounding_box_x"',
                'fix': 'Change x -> bounding_box_x, y -> bounding_box_y, etc.'
            })
            logger.error("❌ Found incorrect bounding box field names")
        elif "bounding_box_x=detection.bounding_box.x" in content:
            logger.info("✅ Bounding box field names correctly fixed")
    
    # Issue 2: Check other service files
    detection_pipeline_file = backend_dir / "services" / "detection_pipeline_service.py"
    
    if detection_pipeline_file.exists():
        logger.info("📁 Analyzing detection_pipeline_service.py...")
        with open(detection_pipeline_file, 'r') as f:
            content = f.read()
            
        if "DetectionEvent(" in content:
            logger.info("✅ DetectionEvent usage found - checking for issues...")
            
            # Check for potential field name issues
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'DetectionEvent(' in line:
                    # Check next 20 lines for field assignments
                    for j in range(i, min(i+20, len(lines))):
                        check_line = lines[j].strip()
                        if any(field in check_line for field in ['video_id=', 'x=', 'y=', 'width=', 'height=']):
                            if not any(correct in check_line for correct in ['bounding_box_x', 'bounding_box_y', 'bounding_box_width', 'bounding_box_height']):
                                logger.warning(f"⚠️  Potential issue at line {j+1}: {check_line}")
    
    logger.info("\n📊 ANALYSIS SUMMARY")
    logger.info("-" * 40)
    
    if issues_found:
        logger.error(f"❌ Found {len(issues_found)} schema mismatch issues:")
        for i, issue in enumerate(issues_found, 1):
            logger.error(f"\n{i}. File: {issue['file']}")
            logger.error(f"   Line ~{issue['line_approx']}: {issue['issue']}")
            logger.error(f"   Fix: {issue['fix']}")
    else:
        logger.info("✅ No obvious schema mismatches found")
    
    return issues_found

def generate_fix_for_test_execution_service():
    """Generate the corrected code for test_execution_service.py"""
    
    logger.info("\n🔧 GENERATING CORRECTED CODE")
    logger.info("=" * 40)
    
    corrected_code = '''
                        for detection in validated_detections:
                            detection_event = DetectionEvent(
                                id=detection.detection_id,
                                test_session_id=session_id,
                                # REMOVED: video_id=video.id,  # ❌ This field does not exist!
                                frame_number=frame_count,
                                timestamp=frame_count / fps,
                                confidence=detection.confidence,
                                class_label=detection.class_label,
                                # FIXED: Use correct column names
                                bounding_box_x=detection.bounding_box.x,
                                bounding_box_y=detection.bounding_box.y,
                                bounding_box_width=detection.bounding_box.width,
                                bounding_box_height=detection.bounding_box.height,
                                validation_result="VALIDATED",
                                # Optional: Add additional fields
                                detection_id=detection.detection_id,
                                vru_type=detection.class_label  # Map class_label to vru_type
                            )
                            db.add(detection_event)
    '''
    
    logger.info("✅ Corrected DetectionEvent creation code:")
    logger.info(corrected_code)
    
    return corrected_code.strip()

def check_database_schema():
    """Verify the actual database schema matches expectations"""
    
    logger.info("\n🗄️ DATABASE SCHEMA VERIFICATION")
    logger.info("=" * 40)
    
    try:
        from sqlalchemy import inspect
        from database import engine
        
        inspector = inspect(engine)
        
        if 'detection_events' not in inspector.get_table_names():
            logger.error("❌ detection_events table does not exist!")
            return False
        
        columns = inspector.get_columns('detection_events')
        column_names = {col['name'] for col in columns}
        
        required_columns = {
            'id', 'test_session_id', 'timestamp', 'confidence', 'class_label',
            'detection_id', 'frame_number', 'bounding_box_x', 'bounding_box_y',
            'bounding_box_width', 'bounding_box_height'
        }
        
        missing = required_columns - column_names
        extra = column_names - required_columns
        
        logger.info(f"📋 Total columns in database: {len(column_names)}")
        logger.info(f"✅ Required columns present: {len(required_columns - missing)}")
        
        if missing:
            logger.error(f"❌ Missing required columns: {', '.join(missing)}")
        
        if extra:
            logger.info(f"ℹ️  Additional columns: {', '.join(extra)}")
        
        # Check for problematic columns that don't exist
        problematic = {'video_id', 'x', 'y', 'width', 'height'}
        found_problematic = problematic & column_names
        
        if found_problematic:
            logger.warning(f"⚠️  Found potentially confusing columns: {', '.join(found_problematic)}")
            logger.warning("   These might be causing confusion with field names")
        
        return len(missing) == 0
        
    except Exception as e:
        logger.error(f"❌ Database schema check failed: {e}")
        return False

def main():
    """Main analysis and fix generation function"""
    
    print("🔧 DetectionEvent Schema Mismatch Fix Tool")
    print("=" * 50)
    
    try:
        # Analyze current code issues
        issues = analyze_detection_event_usage()
        
        # Check database schema
        schema_ok = check_database_schema()
        
        # Generate fixes
        if issues:
            fix_code = generate_fix_for_test_execution_service()
            
            # Save fix to file
            fix_file = backend_dir / "fixed_detection_event_creation.py"
            with open(fix_file, 'w') as f:
                f.write(f"""# Corrected DetectionEvent creation code
# Generated by fix_detection_events_schema_mismatch.py

# Replace the DetectionEvent creation in test_execution_service.py with:
{fix_code}
""")
            
            logger.info(f"\n📁 Fix saved to: {fix_file}")
        
        print(f"\n📊 FINAL SUMMARY")
        print("=" * 30)
        print(f"Code issues found: {len(issues)}")
        print(f"Database schema: {'✅ OK' if schema_ok else '❌ Issues'}")
        
        if issues or not schema_ok:
            print("\n🔧 NEXT STEPS:")
            print("1. Fix the field name mismatches in the code")
            print("2. Update test_execution_service.py with correct field names")
            print("3. Remove video_id parameter from DetectionEvent creation")
            print("4. Use bounding_box_x/y/width/height instead of x/y/width/height")
            
            return False
        else:
            print("\n🎉 All checks passed!")
            return True
        
    except Exception as e:
        logger.error(f"💥 Analysis failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)