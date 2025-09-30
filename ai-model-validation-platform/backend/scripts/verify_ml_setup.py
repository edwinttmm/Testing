"""
Verify ML (YOLO) setup inside the backend venv.
Loads the YOLO model and runs a single dummy inference.
"""

import sys
import os

def main() -> int:
    try:
        import numpy as np  # noqa: F401
        import cv2  # noqa: F401
        from ultralytics import YOLO
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return 1

    # Try local model files first
    candidate_paths = [
        os.path.join(os.getcwd(), 'yolov8n.pt'),
        os.path.join(os.path.dirname(__file__), '..', 'yolov8n.pt'),
        'yolov8n.pt',
    ]

    model = None
    last_err = None
    for p in candidate_paths:
        try:
            if os.path.exists(p):
                print(f"🔎 Loading local model: {p}")
                model = YOLO(p)
                break
        except Exception as e:  # keep trying
            last_err = e
            continue

    if model is None:
        try:
            print("🌐 Loading default model by name: yolov8n.pt (may download)")
            model = YOLO('yolov8n.pt')
        except Exception as e:
            print(f"❌ Failed to load YOLO model: {e} | last local error: {last_err}")
            return 2

    # Dummy inference
    try:
        import numpy as np
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        _ = model(dummy, verbose=False)
        print("✅ YOLO loaded and dummy inference completed")
    except Exception as e:
        print(f"❌ Inference failed: {e}")
        return 3

    return 0

if __name__ == '__main__':
    sys.exit(main())

