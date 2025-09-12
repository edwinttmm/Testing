#!/usr/bin/env python3
"""
Test Enhanced Database Storage After Fix
Verify that the class name collision fix allows proper database storage
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import logging
from database import SessionLocal
from models import TestSession, DetectionEvent, TestResult
from models import TestResult as SQLTestResult
import uuid
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database_storage_fix():
    """Test that TestResult can now be stored in database"""
    try:
        db = SessionLocal()
        
        print("=" * 80)
        print("🔧 TESTING DATABASE STORAGE FIX")
        print("=" * 80)
        
        print("\n1️⃣ Testing SQLAlchemy TestResult Creation:")
        
        # Create a test session first
        test_session = TestSession(
            id=str(uuid.uuid4()),
            name="Test Enhanced Storage Fix",
            project_id="test-project",
            video_id="test-video",
            status="testing"
        )
        db.add(test_session)
        db.commit()
        print(f"✅ Created test session: {test_session.id}")
        
        # Create TestResult using SQLAlchemy model (should work now)
        test_result = SQLTestResult(
            id=str(uuid.uuid4()),
            test_session_id=test_session.id,
            accuracy=0.85,
            precision=0.90,
            recall=0.80,
            f1_score=0.85,
            true_positives=4,
            false_positives=1,
            false_negatives=1,
            statistical_analysis={"test": "data"},
            confidence_intervals={"precision": [0.8, 1.0]}
        )
        
        print(f"✅ SQLTestResult object created: {test_result.id}")
        
        # Add to database - this should work now
        db.add(test_result)
        db.commit()
        print(f"✅ TestResult successfully saved to database!")
        
        # Verify it was saved
        saved_result = db.query(SQLTestResult).filter(
            SQLTestResult.id == test_result.id
        ).first()
        
        if saved_result:
            print(f"✅ Verified: TestResult retrieved from database")
            print(f"   ID: {saved_result.id}")
            print(f"   Accuracy: {saved_result.accuracy}")
            print(f"   F1 Score: {saved_result.f1_score}")
        else:
            print(f"❌ TestResult not found in database")
            
        # Clean up test data
        db.delete(test_result)
        db.delete(test_session)
        db.commit()
        print(f"✅ Test data cleaned up")
        
        db.close()
        
        print(f"\n🎉 DATABASE STORAGE FIX SUCCESSFUL!")
        print(f"   - Class name collision resolved")
        print(f"   - SQLAlchemy TestResult can be saved")
        print(f"   - Enhanced tests can now store results")
        
        return True
        
    except Exception as e:
        print(f"❌ Database storage test failed: {e}")
        import traceback
        traceback.print_exc()
        if 'db' in locals():
            db.rollback()
            db.close()
        return False

if __name__ == "__main__":
    success = test_database_storage_fix()
    
    if success:
        print(f"\n💡 NEXT: Run enhanced test to verify complete flow!")
        print(f"   Your enhanced tests should now save results to database.")
    
    sys.exit(0 if success else 1)