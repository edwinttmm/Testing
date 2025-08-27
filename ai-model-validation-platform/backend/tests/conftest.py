"""
VRU Platform Test Configuration
===============================

Pytest configuration and fixtures for VRU platform testing suite.
"""

import pytest
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure asyncio for pytest
pytest_plugins = ['pytest_asyncio']

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for session-scoped async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_config():
    """Test configuration fixture"""
    return {
        "test_timeout": 300,
        "production_server": "155.138.239.131",
        "production_port": 8000
    }

def pytest_configure(config):
    """Configure pytest settings"""
    config.addinivalue_line("markers", "integration: Integration test marker")
    config.addinivalue_line("markers", "performance: Performance test marker") 
    config.addinivalue_line("markers", "production: Production test marker")

def pytest_collection_modifyitems(config, items):
    """Modify collected test items"""
    # Add markers based on test names
    for item in items:
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        if "performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        if "production" in item.nodeid:
            item.add_marker(pytest.mark.production)