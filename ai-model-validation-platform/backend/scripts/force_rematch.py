"""
This script directly invokes the ground truth matching service to force a
re-calculation of metrics for a given session, ignoring any cached results.
"""
import sys
import os
import argparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the backend directory to the Python path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from services.ground_truth_matching_service import get_ground_truth_matching_service
    from database import SessionLocal, engine # Import the configured engine
except ImportError as e:
    print(f"❌ Error importing modules: {e}")
    sys.exit(1)

def force_rematch(session_id: str):
    """
    Forces a re-match for the given session ID.
    """
    print(f"--- Forcing re-match for Session ID: {session_id} ---")
    
    try:
        matching_service = get_ground_truth_matching_service()
        print("✅ Successfully got matching service instance.")
        
        print("⏳ Calling match_detections_to_ground_truth with force_rematch=True...")
        # This will now delete old comparisons and re-run the logic,
        # which should trigger the 'INVESTIGATION' logs I added.
        matching_results = matching_service.match_detections_to_ground_truth(
            session_id=session_id,
            force_rematch=True,
            auto_commit=True # Ensure changes are saved
        )
        
        if matching_results:
            print("\n--- Re-match Complete ---")
            print(f"✅ Metrics recalculated successfully.")
            print(f"   - True Positives:  {matching_results.true_positives}")
            print(f"   - False Positives: {matching_results.false_positives}")
            print(f"   - False Negatives: {matching_results.false_negatives}")
            print(f"   - Recall:          {matching_results.recall:.2%}")
            print(f"   - Precision:       {matching_results.precision:.2%}")
        else:
            print("❌ Re-match process returned no results.")

    except Exception as e:
        print(f"\nAn exception occurred during the re-match process: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Force a re-match of ground truth data for a test session.")
    parser.add_argument("--session-id", default="e52146ff-3d1a-4f84-99d4-a8705a9b93f3", help="The ID of the test session to re-match.")
    
    args = parser.parse_args()

    force_rematch(args.session_id)
