"""
HIL Detection Pipeline Test Suite

Comprehensive validation tests for the Hardware-in-the-Loop (HIL) detection pipeline
including LabJack connection, WebSocket events, detection queue, and end-to-end integration.

Test Coverage:
- LabJack connection stability and reconnection
- Signal capture and voltage threshold detection
- WebSocket event emission and fallback polling
- Detection queue for race condition prevention
- Video timing synchronization
- Ground truth matching integration
- Performance benchmarks and scalability

Created: 2025-11-14
Agent: Test Engineering Specialist (Queen Seraphina's Swarm)
"""

__version__ = "1.0.0"
__author__ = "Test Engineering Specialist"
__all__ = ["test_labjack_connection", "test_websocket_events", "test_detection_queue", "test_integration"]
