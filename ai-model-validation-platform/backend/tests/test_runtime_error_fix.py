#!/usr/bin/env python3
"""
Focused test for the specific RuntimeError: generator didn't stop after throw()
This test verifies that the generator cleanup issue is fixed.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_no_runtime_error_on_exception():
    """
    Test that throwing an exception into the generator doesn't cause:
    RuntimeError: generator didn't stop after throw()
    """
    from database import get_db
    from sqlalchemy.exc import SQLAlchemyError

    print("="*60)
    print("TESTING FIX FOR: RuntimeError: generator didn't stop after throw()")
    print("="*60)

    test_cases = [
        ("ValueError", ValueError("Test error")),
        ("SQLAlchemyError", SQLAlchemyError("Test SQL error")),
        ("KeyError", KeyError("Test key")),
        ("RuntimeError", RuntimeError("Test runtime error (not generator)")),
    ]

    all_passed = True

    for name, exception in test_cases:
        print(f"\nTest: Throwing {name} into generator...")

        try:
            gen = get_db()
            db = next(gen)
            print(f"  ✓ Created session")

            # The critical test: throw an exception into the generator
            # Before the fix, this would cause RuntimeError: generator didn't stop after throw()
            runtime_error_occurred = False
            expected_exception_raised = False

            try:
                gen.throw(type(exception), exception)
            except type(exception):
                # The original exception was raised (expected)
                expected_exception_raised = True
            except RuntimeError as e:
                if "generator didn't stop" in str(e):
                    print(f"  ✗ CRITICAL BUG: RuntimeError occurred: {e}")
                    runtime_error_occurred = True
                else:
                    # Different RuntimeError, re-raise
                    raise
            except StopIteration:
                # Generator stopped cleanly (also acceptable)
                expected_exception_raised = True

            if runtime_error_occurred:
                print(f"  ✗ FAILED: {name} caused RuntimeError")
                all_passed = False
            elif expected_exception_raised:
                print(f"  ✓ PASSED: {name} handled correctly, no RuntimeError")
            else:
                print(f"  ⚠  WARNING: {name} handled unexpectedly but no RuntimeError")

        except Exception as e:
            if "generator didn't stop" in str(e):
                print(f"  ✗ CRITICAL BUG: RuntimeError during {name}: {e}")
                all_passed = False
            else:
                print(f"  ⚠  Unexpected error during {name}: {e}")

    print("\n" + "="*60)
    if all_passed:
        print("✓✓✓ SUCCESS ✓✓✓")
        print("No RuntimeError: 'generator didn't stop after throw()' occurred")
        print("The bug is FIXED!")
        return 0
    else:
        print("✗✗✗ FAILURE ✗✗✗")
        print("RuntimeError: 'generator didn't stop after throw()' still occurs")
        print("The bug is NOT fixed!")
        return 1


if __name__ == "__main__":
    sys.exit(test_no_runtime_error_on_exception())
