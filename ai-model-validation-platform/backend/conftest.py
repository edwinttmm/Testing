"""
Root conftest.py to configure pytest path resolution for the entire project.
This ensures all imports work correctly from any test location.
"""
import sys
import os
from pathlib import Path

# Add backend root to Python path FIRST (for imports like 'from services...' and 'from models...')
# This is the HIGHEST priority since tests import from here
backend_root = Path(__file__).parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

# Add src directory to Python path (for imports like 'from src.services...')
src_dir = backend_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Add tests directory to Python path
tests_dir = backend_root / "tests"
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))

# Verify critical directories exist
assert backend_root.exists(), f"Backend root not found: {backend_root}"
assert src_dir.exists(), f"Src directory not found: {src_dir}"
assert tests_dir.exists(), f"Tests directory not found: {tests_dir}"

# Verify services directories exist
services_dir = backend_root / "services"
src_services_dir = src_dir / "services"
assert services_dir.exists() or src_services_dir.exists(), \
    f"Services directory not found in {services_dir} or {src_services_dir}"

print(f"✓ Python path configured successfully:")
print(f"  Backend root: {backend_root}")
print(f"  Services: {services_dir.exists() and str(services_dir) or 'Not found'}")
print(f"  Src dir: {src_dir}")
print(f"  Src services: {src_services_dir.exists() and str(src_services_dir) or 'Not found'}")
print(f"  Tests dir: {tests_dir}")
