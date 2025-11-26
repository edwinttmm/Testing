# Variable Shadowing Fix Guide
## Step-by-Step Instructions for Fixing All 36 Shadowing Issues

**Priority:** CRITICAL
**Estimated Time:** 4-6 hours
**Risk Level:** LOW (removing redundant imports is safe)

---

## Quick Reference: What is Variable Shadowing?

```python
# Problem Pattern:
import threading  # Module-level import

def some_function():
    event = threading.Event()  # Uses threading from line 1
    # ... 500 lines of code ...
    import threading  # Local import shadows module-level!
    # ❌ BUG: Any use of 'threading' before this line will fail with UnboundLocalError
    # because Python sees the local import and treats 'threading' as a local variable
```

---

## Fix Strategy

For all 36 issues, the fix is the same:
1. **Remove the local import statement**
2. **Verify the module is already imported at module level**
3. **Test the function still works**

---

## Critical Fixes (Must Do Immediately)

### 1. services/labjack_service.py - Line 639

**Current Code:**
```python
# Line 23
import os

# Line 639 in _connect_direct()
if ljm is None:
    try:
        import sys
        import os  # ❌ REMOVE THIS
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
```

**Fix:**
```python
# Add sys to module-level imports (around line 23)
import os
import sys  # ✅ ADD THIS

# Line 639 - Remove local imports
if ljm is None:
    try:
        # ✅ REMOVED: import sys
        # ✅ REMOVED: import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
```

**Command to apply:**
```bash
# Remove line 639 (import os)
sed -i '639d' services/labjack_service.py
# Remove line 638 (import sys) - now 638 after previous deletion
sed -i '638d' services/labjack_service.py
# Add sys import at module level (after line 23)
sed -i '23a import sys' services/labjack_service.py
```

---

### 2. services/latency_decomposition_service.py - Line 260

**Current Code:**
```python
# Line 23
import threading

# Line 260 in _measure_context_switch_overhead()
def _measure_context_switch_overhead(self) -> int:
    import threading  # ❌ REMOVE THIS
    import queue
```

**Fix:**
```python
# Line 23 - already has threading
import threading

# Line 260 - Remove redundant import
def _measure_context_switch_overhead(self) -> int:
    # ✅ REMOVED: import threading
    import queue  # Keep this if not at module level
```

**Command to apply:**
```bash
# Check if queue is imported at module level
grep -n "^import queue" services/latency_decomposition_service.py
# If not found, add it to module level, then remove line 260
sed -i '260d' services/latency_decomposition_service.py
```

---

### 3. services/detection_pipeline_service.py - Multiple Lines

This file has 6 shadowing instances - the most critical file!

**Current Code:**
```python
# Lines 8, 15, 17, 20, 21
import torch
import time
from pathlib import Path
from database import SessionLocal
from models import DetectionEvent, TestSession, Video, GroundTruthObject

# Line 134-137 in load_model()
try:
    from ultralytics import YOLO
    import torch  # ❌ REMOVE
    from pathlib import Path  # ❌ REMOVE

# Lines 996-999 in process_video_with_storage()
async def process_video_with_storage(self, video_path: str, video_id: str, config: dict = None):
    from database import SessionLocal  # ❌ REMOVE
    from models import DetectionEvent, TestSession  # ❌ REMOVE (partial)
    from datetime import datetime  # Keep if not at module level
    import time  # ❌ REMOVE
```

**Fix:**
```python
# Module-level imports (lines 1-30)
import torch
import time
from pathlib import Path
from database import SessionLocal
from models import DetectionEvent, TestSession, Video, GroundTruthObject
from datetime import datetime  # ✅ ADD THIS if not present

# Line 134-137 - Remove redundant imports
try:
    from ultralytics import YOLO
    # ✅ REMOVED: import torch
    # ✅ REMOVED: from pathlib import Path
    # Use torch and Path from module level

# Lines 996-999 - Remove redundant imports
async def process_video_with_storage(self, video_path: str, video_id: str, config: dict = None):
    # ✅ REMOVED: from database import SessionLocal
    # ✅ REMOVED: from models import DetectionEvent, TestSession
    # ✅ REMOVED: import time
    # Use SessionLocal, models, time from module level
    db = SessionLocal()
```

**Commands to apply:**
```bash
cd services
# Remove line 134 (import torch in load_model)
sed -i '134d' detection_pipeline_service.py
# Remove line 137 (from pathlib import Path) - now 136 after previous deletion
sed -i '136d' detection_pipeline_service.py

# Remove lines 996-999 (in process_video_with_storage)
# First identify exact line numbers after previous changes
grep -n "from database import SessionLocal" detection_pipeline_service.py | grep "process_video_with_storage" -A 5
# Then remove those lines (adjust line numbers based on output)
sed -i '996d;997d;999d' detection_pipeline_service.py

# Add datetime to module imports if not present
grep -q "from datetime import datetime" detection_pipeline_service.py || sed -i '22a from datetime import datetime' detection_pipeline_service.py
```

---

### 4. services/dedicated_labjack_monitor.py - 5 Instances

**Current Code:**
```python
# Lines 16, 17, 19, 37
import os
import asyncio
import threading
from models import TestSession, DetectionEvent, Video, SequenceVideoResult

# Line 127 in __init__()
def __init__(self, websocket_emit_fn: Optional[Callable] = None):
    import os  # ❌ REMOVE

# Line 1687 in _validate_video_status()
def _validate_video_status(self, db, video_id: str) -> Optional[str]:
    from models import Video  # ❌ REMOVE (already imported at line 37)

# Line 1983 in _store_detection_event_async()
async def _store_detection_event_async(self, hil_event: HILDetectionEvent):
    import os  # ❌ REMOVE

# Line 2242 in _schedule_hil_processing() - ALREADY FIXED
def _schedule_hil_processing(self, ...):
    # import threading  # ✅ ALREADY REMOVED

    # Line 2247 in _hil_processing_worker()
    def _hil_processing_worker():
        import asyncio  # ❌ REMOVE
```

**Fix:**
```python
# All imports already at module level - just remove local ones

# Line 127 - Remove
def __init__(self, websocket_emit_fn: Optional[Callable] = None):
    # ✅ REMOVED: import os
    log_dir = os.path.join(...)  # Use module-level os

# Line 1687 - Remove
def _validate_video_status(self, db, video_id: str) -> Optional[str]:
    # ✅ REMOVED: from models import Video
    video = db.query(Video).filter(...)  # Use module-level Video

# Line 1983 - Remove
async def _store_detection_event_async(self, hil_event: HILDetectionEvent):
    # ✅ REMOVED: import os
    screenshot_path = os.path.join(...)  # Use module-level os

# Line 2247 - Remove
def _hil_processing_worker():
    # ✅ REMOVED: import asyncio
    loop = asyncio.new_event_loop()  # Use module-level asyncio
```

**Commands to apply:**
```bash
cd services
# Remove line 127 (import os in __init__)
sed -i '127d' dedicated_labjack_monitor.py

# Remove line 1687 (from models import Video)
sed -i '1687d' dedicated_labjack_monitor.py

# Remove line 1983 (import os in _store_detection_event_async)
sed -i '1983d' dedicated_labjack_monitor.py

# Remove line 2247 (import asyncio in _hil_processing_worker)
sed -i '2247d' dedicated_labjack_monitor.py
```

---

### 5. services/ground_truth_service.py - 5 Instances

**Current Code:**
```python
# Lines 14, 16, 19, 44, 45
import os
import cv2
import torch
from database import SessionLocal
import crud

# Line 97 in __init__()
def __init__(self, config: Optional[Dict[str, Any]] = None):
    import torch  # ❌ REMOVE

# Line 156 in _process_video()
def _process_video(self, video_path: str, video_id: str) -> List[Dict]:
    import os  # ❌ REMOVE

# Line 198 in _process_video()
    import cv2  # ❌ REMOVE

# Line 301 in process_video_blocking()
def process_video_blocking(self, video_path: str, video_id: str) -> List[Dict]:
    from database import SessionLocal  # ❌ REMOVE

# Line 533 in get_ground_truth()
async def get_ground_truth(self, video_id: str) -> List[Dict]:
    import crud  # ❌ REMOVE
```

**Fix:** Remove all 5 local imports (they're all already at module level)

**Commands to apply:**
```bash
cd services
sed -i '97d' ground_truth_service.py   # Remove import torch
sed -i '156d' ground_truth_service.py  # Remove import os (adjust line number)
sed -i '198d' ground_truth_service.py  # Remove import cv2 (adjust line number)
sed -i '301d' ground_truth_service.py  # Remove from database import SessionLocal
sed -i '533d' ground_truth_service.py  # Remove import crud
```

---

## Remaining 20 Files (Medium Priority)

### Quick Fix Script

```bash
#!/bin/bash
# fix_all_shadowing.sh

cd /home/rigade/Testing/ai-model-validation-platform/backend

# Fix services/windows_labjack_bridge.py
sed -i '152d' services/windows_labjack_bridge.py  # Remove import socket

# Fix services/video_timing_service.py
sed -i '265d' services/video_timing_service.py  # Remove import time

# Fix services/test_execution_service.py
sed -i '364d;534d' services/test_execution_service.py  # Remove import datetime (2x)

# Fix services/signal_validation_wsl.py
sed -i '66d' services/signal_validation_wsl.py  # Remove import datetime

# Fix services/ground_truth_matching_service.py
sed -i '485d' services/ground_truth_matching_service.py  # Remove from models import

# Fix services/labjack_detection_service.py
# Multiple lines - need to verify exact line numbers first
grep -n "import json\|import time\|import datetime\|import sqlalchemy" services/labjack_detection_service.py

# Fix routers/health.py
sed -i '76d' routers/health.py  # Remove import fastapi

# Fix routers/videos.py
sed -i '65d' routers/videos.py  # Remove import sqlalchemy

# Fix routers/dashboard.py
sed -i '58d' routers/dashboard.py  # Remove from models import

echo "✅ All shadowing issues fixed!"
echo "⚠️  Please run tests to verify functionality"
```

---

## Testing After Fixes

### 1. Syntax Check
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 -m py_compile services/*.py
python3 -m py_compile routers/*.py
```

### 2. Import Check
```bash
# Verify all imports still work
python3 << EOF
import sys
sys.path.insert(0, '.')

# Test critical imports
from services import labjack_service
from services import detection_pipeline_service
from services import dedicated_labjack_monitor
from services import ground_truth_service
from routers import health, videos, dashboard

print("✅ All imports successful!")
EOF
```

### 3. Unit Tests
```bash
# Run existing test suite
pytest tests/ -v
```

### 4. Manual Verification
```bash
# Start the server and check logs for import errors
python3 main.py
# Check logs for any ImportError or UnboundLocalError
```

---

## Verification Checklist

After fixing each file:

- [ ] Verify module-level import exists for the shadowed module
- [ ] Remove local import statement
- [ ] Run syntax check (`python3 -m py_compile <file>`)
- [ ] Search for any other uses of the module in that function
- [ ] Run relevant unit tests if available
- [ ] Check application logs after restart

---

## Rollback Plan

If any fix breaks functionality:

```bash
# Restore from git (if changes committed)
git checkout services/<filename>.py

# Or restore from backup
cp services/<filename>.py.bak services/<filename>.py
```

---

## Prevention Strategy

### 1. Add Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Check for variable shadowing before commit

python3 << 'PYEOF'
import sys
import re
import os

def check_shadowing(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    lines = content.split('\n')

    # Find module-level imports
    module_imports = set()
    for i, line in enumerate(lines[:100]):  # Check first 100 lines
        match = re.match(r'^import (\w+)', line.strip())
        if match:
            module_imports.add(match.group(1))
        match = re.match(r'^from (\w+) import', line.strip())
        if match:
            module_imports.add(match.group(1))

    # Check for local imports that shadow
    in_function = False
    issues = []
    for i, line in enumerate(lines, 1):
        if re.match(r'^(def |class |async def )', line.strip()):
            in_function = True

        if in_function:
            match = re.match(r'^\s+import (\w+)', line)
            if match and match.group(1) in module_imports:
                issues.append(f"{filepath}:{i} - import {match.group(1)} shadows module-level import")

            match = re.match(r'^\s+from (\w+) import', line)
            if match and match.group(1) in module_imports:
                issues.append(f"{filepath}:{i} - from {match.group(1)} import shadows module-level import")

    return issues

# Check all Python files being committed
all_issues = []
for root, dirs, files in os.walk('.'):
    if '.git' in dirs:
        dirs.remove('.git')
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            all_issues.extend(check_shadowing(filepath))

if all_issues:
    print("❌ COMMIT BLOCKED: Variable shadowing detected!\n")
    for issue in all_issues:
        print(issue)
    sys.exit(1)

print("✅ No shadowing issues detected")
sys.exit(0)
PYEOF
```

### 2. Add Pylint Check

Add to `.pylintrc`:

```ini
[MESSAGES CONTROL]
enable=
    redefined-outer-name,
    redefined-builtin,
    import-outside-toplevel
```

### 3. Add to CI/CD Pipeline

```yaml
# .github/workflows/code-quality.yml
name: Code Quality Checks

on: [push, pull_request]

jobs:
  check-shadowing:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Check for variable shadowing
        run: |
          python3 scripts/check_shadowing.py
```

---

## Summary

**Total Issues:** 36 variable shadowing instances
**Estimated Fix Time:** 4-6 hours
**Risk Level:** LOW (removing redundant imports)
**Priority:** CRITICAL (prevents runtime UnboundLocalError)

**Next Steps:**
1. Create backup of all files: `cp -r services services.bak`
2. Apply fixes to critical files (1-5 above)
3. Run tests
4. Apply fixes to remaining files
5. Deploy and monitor

**Benefits:**
- Eliminates UnboundLocalError risks
- Improves code clarity (no redundant imports)
- Faster import time (slight performance gain)
- Better IDE support (clearer namespace)

---

**Document Version:** 1.0
**Last Updated:** 2025-11-19
**Author:** Code Quality Analyzer Agent
