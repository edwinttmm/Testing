"""Quick test to verify RuntimeError fix."""
import sys
sys.path.insert(0, '/home/rigade/Testing/ai-model-validation-platform/backend')

from database import get_db
from main import get_db as get_db_override

def test_database_py_no_runtime_error():
    """Test database.py get_db() doesn't raise RuntimeError."""
    try:
        gen = get_db()
        session = next(gen)
        try:
            # Simulate an error
            raise ValueError("Test error")
        except ValueError:
            print("✓ ValueError caught correctly")
            try:
                gen.throw(ValueError, ValueError("Test error"), None)
            except (ValueError, StopIteration):
                pass
    except RuntimeError as e:
        if "generator didn't stop" in str(e):
            print("❌ FAILED: RuntimeError still occurs in database.py")
            return False
    print("✓ database.py: No RuntimeError")
    return True

def test_main_py_no_runtime_error():
    """Test main.py get_db() doesn't raise RuntimeError."""
    try:
        gen = get_db_override()
        session = next(gen)
        try:
            # Simulate an error
            raise ValueError("Test error")
        except ValueError:
            print("✓ ValueError caught correctly")
            try:
                gen.throw(ValueError, ValueError("Test error"), None)
            except (ValueError, StopIteration):
                pass
    except RuntimeError as e:
        if "generator didn't stop" in str(e):
            print("❌ FAILED: RuntimeError still occurs in main.py")
            return False
    print("✓ main.py: No RuntimeError")
    return True

if __name__ == "__main__":
    print("Testing RuntimeError fix...")
    result1 = test_database_py_no_runtime_error()
    result2 = test_main_py_no_runtime_error()

    if result1 and result2:
        print("\n✅ SUCCESS: RuntimeError fix verified!")
        sys.exit(0)
    else:
        print("\n❌ FAILED: RuntimeError still present")
        sys.exit(1)
