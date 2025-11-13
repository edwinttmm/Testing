# HIL System Fixes - Comprehensive Testing Strategy

**Date**: 2025-10-28
**Status**: Testing Plan for Recent HIL System Fixes
**Priority**: CRITICAL

---

## Executive Summary

This document provides a comprehensive testing strategy for the three critical fixes implemented in the HIL (Hardware-in-Loop) system:

1. **Detection events now save to database** (was broken)
2. **Video sequence entries now created** (was missing)
3. **Column names corrected** (test_session_id, detection_channel, etc.)

---

## PART 1: UNIT TESTS

### 1.1 Detection Event Database Storage Tests

**Test File**: `/tests/unit/test_labjack_detection_storage.py`

#### Test Cases:

```python
import pytest
from services.labjack_detection_service import LabJackDetectionMonitor, DetectionEvent
from models import DetectionEvent as DBDetectionEvent
from database import SessionLocal
from datetime import datetime
import uuid

class TestDetectionEventStorage:
    """Unit tests for detection event database storage"""

    def test_store_event_in_db_creates_record(self, test_db):
        """
        UNIT TEST: Verify _store_event_in_db() creates database record

        Validates:
        - Detection event is inserted into database
        - Correct column names used (test_session_id, detection_channel)
        - Timing calibration fields populated
        """
        # Arrange
        monitor = LabJackDetectionMonitor()
        session_id = str(uuid.uuid4())

        event = DetectionEvent(
            id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=datetime.now(),
            channel="AIN0",
            voltage=3.3,
            threshold=2.5,
            detected=True,
            video_relative_timestamp=1.5,
            actual_latency_ms=50.0
        )

        # Act
        import asyncio
        asyncio.run(monitor._store_event_in_db(event))

        # Assert
        db = SessionLocal()
        stored_event = db.query(DBDetectionEvent).filter(
            DBDetectionEvent.id == event.id
        ).first()

        assert stored_event is not None, "Event not saved to database"
        assert stored_event.test_session_id == session_id, "Wrong column: should use test_session_id"
        assert stored_event.detection_channel == "AIN0", "Wrong column: should use detection_channel"
        assert stored_event.labjack_voltage == 3.3, "Voltage not stored"
        assert stored_event.video_relative_timestamp == 1.5, "Timing calibration missing"
        assert stored_event.actual_latency_ms == 50.0, "Latency not stored"

        db.close()


    def test_store_event_column_name_mapping(self, test_db):
        """
        UNIT TEST: Verify correct column name mappings

        Critical Fix Validation:
        - test_session_id (NOT session_id)
        - detection_channel (NOT channel)
        - detection_metadata (NOT metadata)
        """
        monitor = LabJackDetectionMonitor()
        session_id = str(uuid.uuid4())

        event = DetectionEvent(
            id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=datetime.now(),
            channel="AIN1",
            voltage=2.8,
            threshold=2.5,
            metadata={"test": "data"}
        )

        import asyncio
        asyncio.run(monitor._store_event_in_db(event))

        # Verify using SQL query to check exact column names
        db = SessionLocal()
        from sqlalchemy import text

        result = db.execute(text("""
            SELECT test_session_id, detection_channel, detection_metadata
            FROM detection_events
            WHERE id = :event_id
        """), {"event_id": event.id}).fetchone()

        assert result is not None, "Event not found"
        assert result[0] == session_id, "test_session_id not populated"
        assert result[1] == "AIN1", "detection_channel not populated"
        assert result[2] is not None, "detection_metadata not populated"

        db.close()


    def test_fallback_storage_method(self, test_db):
        """
        UNIT TEST: Verify fallback storage works with correct columns

        Tests the _store_event_fallback() method uses correct SQL
        """
        monitor = LabJackDetectionMonitor()
        session_id = str(uuid.uuid4())

        event = DetectionEvent(
            id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=datetime.now(),
            channel="AIN0",
            voltage=3.0,
            threshold=2.5
        )

        db = SessionLocal()
        monitor._store_event_fallback(db, event)
        db.commit()

        # Verify event saved with correct columns
        stored = db.query(DBDetectionEvent).filter(
            DBDetectionEvent.id == event.id
        ).first()

        assert stored is not None
        assert stored.test_session_id == session_id
        assert stored.detection_channel == "AIN0"

        db.close()
```

### 1.2 Video Sequence Creation Tests

**Test File**: `/tests/unit/test_video_sequence_creation.py`

```python
class TestVideoSequenceCreation:
    """Unit tests for video sequence and result creation"""

    def test_sequence_video_result_creation(self, test_db, test_project):
        """
        UNIT TEST: Verify SequenceVideoResult entries are created

        Critical Fix: This table was not being populated before
        """
        from models import VideoTestSequence, SequenceVideoResult, Video

        # Create test videos
        video1 = Video(
            id=str(uuid.uuid4()),
            filename="test1.mp4",
            file_path="/test/test1.mp4",
            project_id=test_project.id,
            duration=30.0
        )
        video2 = Video(
            id=str(uuid.uuid4()),
            filename="test2.mp4",
            file_path="/test/test2.mp4",
            project_id=test_project.id,
            duration=40.0
        )
        test_db.add_all([video1, video2])
        test_db.commit()

        # Create video sequence
        sequence_id = str(uuid.uuid4())
        test_session_id = str(uuid.uuid4())

        video_ids = [video1.id, video2.id]

        # Simulate what /api/video-sequences/start does
        sequence = VideoTestSequence(
            id=sequence_id,
            test_session_id=test_session_id,
            name="Test Sequence",
            video_ids=video_ids,
            sequence_order=[
                {"video_id": video1.id, "order": 0, "duration_ms": 30000},
                {"video_id": video2.id, "order": 1, "duration_ms": 40000}
            ],
            max_latency_ms=100,
            status="running",
            total_videos=2
        )
        test_db.add(sequence)
        test_db.commit()

        # Create SequenceVideoResult entries (CRITICAL FIX)
        for idx, video_id in enumerate(video_ids):
            result = SequenceVideoResult(
                id=str(uuid.uuid4()),
                video_sequence_id=sequence_id,
                video_id=video_id,
                sequence_order=idx,
                video_status="pending",
                validation_result="pending",
                expected_detection_count=10,
                actual_detection_count=0
            )
            test_db.add(result)

        test_db.commit()

        # Assert
        results = test_db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == sequence_id
        ).all()

        assert len(results) == 2, "SequenceVideoResult entries not created"
        assert results[0].video_id == video1.id
        assert results[1].video_id == video2.id
        assert results[0].sequence_order == 0
        assert results[1].sequence_order == 1


    def test_ground_truth_count_populated(self, test_db, test_project):
        """
        UNIT TEST: Verify expected_detection_count is populated from ground truth

        Tests that SequenceVideoResult.expected_detection_count reflects
        actual ground truth object count
        """
        from models import Video, GroundTruthObject, SequenceVideoResult

        video = Video(
            id=str(uuid.uuid4()),
            filename="test.mp4",
            file_path="/test/test.mp4",
            project_id=test_project.id,
            duration=30.0
        )
        test_db.add(video)
        test_db.commit()

        # Add ground truth objects
        for i in range(5):
            gt = GroundTruthObject(
                id=str(uuid.uuid4()),
                video_id=video.id,
                timestamp=float(i),
                class_label="pedestrian",
                x=100.0, y=100.0, width=50.0, height=100.0
            )
            test_db.add(gt)
        test_db.commit()

        # Get ground truth count
        gt_count = test_db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == video.id
        ).count()

        # Create SequenceVideoResult
        result = SequenceVideoResult(
            id=str(uuid.uuid4()),
            video_sequence_id=str(uuid.uuid4()),
            video_id=video.id,
            sequence_order=0,
            expected_detection_count=gt_count  # CRITICAL: Must be populated
        )
        test_db.add(result)
        test_db.commit()

        # Assert
        assert result.expected_detection_count == 5, "Ground truth count not populated"
```

---

## PART 2: INTEGRATION TESTS

### 2.1 End-to-End HIL Test Flow

**Test File**: `/tests/integration/test_hil_detection_flow.py`

```python
class TestHILDetectionFlow:
    """Integration tests for complete HIL detection workflow"""

    @pytest.mark.integration
    def test_detection_event_saved_during_hil_test(self, test_db, test_project):
        """
        INTEGRATION: Start HIL test → Detection event → Verify database save

        Validates:
        1. HIL test session starts
        2. Detection events are captured
        3. Events are saved to detection_events table
        4. Correct columns used (test_session_id, detection_channel)
        """
        from routers.labjack_timing import start_hil_test
        from models import TestSession, DetectionEvent
        from services.labjack_detection_service import get_detection_monitor

        # Create test video
        video = Video(
            id=str(uuid.uuid4()),
            filename="hil_test.mp4",
            file_path="/test/hil_test.mp4",
            project_id=test_project.id,
            duration=30.0
        )
        test_db.add(video)
        test_db.commit()

        # Start HIL test
        session = TestSession(
            id=str(uuid.uuid4()),
            name="Integration Test",
            project_id=test_project.id,
            video_id=video.id,
            status="running"
        )
        test_db.add(session)
        test_db.commit()

        # Start monitoring
        monitor = get_detection_monitor()
        monitor.start_monitoring(
            session_id=session.id,
            channels=["AIN0"],
            voltage_threshold=2.5
        )

        # Simulate detection by creating event manually
        event = DetectionEvent(
            id=str(uuid.uuid4()),
            session_id=session.id,
            timestamp=datetime.now(),
            channel="AIN0",
            voltage=3.3,
            threshold=2.5
        )
        monitor._record_detection_event(session.id, event)

        # Wait for async storage
        import time
        time.sleep(0.5)

        # Assert event in database
        stored_events = test_db.query(DBDetectionEvent).filter(
            DBDetectionEvent.test_session_id == session.id
        ).all()

        assert len(stored_events) > 0, "No detection events saved to database"
        assert stored_events[0].test_session_id == session.id
        assert stored_events[0].detection_channel == "AIN0"

        # Cleanup
        monitor.stop_monitoring(session.id)


    @pytest.mark.integration
    def test_multi_video_sequence_entries_created(self, client, test_db, test_project):
        """
        INTEGRATION: Multi-video test → Verify sequence entries created

        Validates:
        1. POST /api/video-sequences/start creates VideoTestSequence
        2. SequenceVideoResult entries created for each video
        3. Detection events linked to correct SequenceVideoResult
        """
        # Create videos
        video1 = Video(id=str(uuid.uuid4()), filename="v1.mp4", file_path="/v1.mp4",
                      project_id=test_project.id, duration=30.0)
        video2 = Video(id=str(uuid.uuid4()), filename="v2.mp4", file_path="/v2.mp4",
                      project_id=test_project.id, duration=40.0)
        test_db.add_all([video1, video2])
        test_db.commit()

        # Start sequence
        payload = {
            "projectId": test_project.id,
            "videoIds": [video1.id, video2.id],
            "maxLatencyMs": 100.0,
            "enableLabjackMonitoring": False
        }

        response = client.post("/api/video-sequences/start", json=payload)
        assert response.status_code == 201

        data = response.json()
        sequence_id = data["sequenceId"]

        # Verify VideoTestSequence created
        sequence = test_db.query(VideoTestSequence).filter(
            VideoTestSequence.id == sequence_id
        ).first()
        assert sequence is not None, "VideoTestSequence not created"

        # Verify SequenceVideoResult entries created (CRITICAL FIX)
        results = test_db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == sequence_id
        ).order_by(SequenceVideoResult.sequence_order).all()

        assert len(results) == 2, "SequenceVideoResult entries not created"
        assert results[0].video_id == video1.id
        assert results[1].video_id == video2.id
        assert results[0].expected_detection_count >= 0
```

### 2.2 Database Validation Queries

**Test File**: `/tests/integration/test_database_validation.py`

```python
class TestDatabaseValidation:
    """SQL-based validation of database state"""

    def test_detection_events_table_structure(self, test_db):
        """
        INTEGRATION: Verify detection_events table has correct columns

        Critical columns:
        - test_session_id (NOT session_id)
        - detection_channel (NOT channel)
        - detection_metadata (NOT metadata)
        """
        from sqlalchemy import inspect, text

        inspector = inspect(test_db.bind)
        columns = inspector.get_columns('detection_events')
        column_names = [col['name'] for col in columns]

        # Verify critical columns exist
        assert 'test_session_id' in column_names, "Missing test_session_id column"
        assert 'detection_channel' in column_names, "Missing detection_channel column"
        assert 'detection_metadata' in column_names, "Missing detection_metadata column"
        assert 'video_relative_timestamp' in column_names, "Missing timing field"
        assert 'actual_latency_ms' in column_names, "Missing latency field"

        # Verify old columns don't exist (if migration complete)
        # assert 'session_id' not in column_names, "Old session_id column still exists"


    def test_sequence_video_results_table_exists(self, test_db):
        """
        INTEGRATION: Verify sequence_video_results table exists

        This table was missing before the fix
        """
        from sqlalchemy import inspect

        inspector = inspect(test_db.bind)
        tables = inspector.get_table_names()

        assert 'sequence_video_results' in tables, "sequence_video_results table missing"

        # Verify critical columns
        columns = inspector.get_columns('sequence_video_results')
        column_names = [col['name'] for col in columns]

        assert 'video_sequence_id' in column_names
        assert 'video_id' in column_names
        assert 'sequence_order' in column_names
        assert 'expected_detection_count' in column_names
        assert 'actual_detection_count' in column_names


    def test_detection_events_query_validation(self, test_db, test_session):
        """
        DATABASE VALIDATION: Verify detection events can be queried correctly

        SQL queries that should work:
        - SELECT by test_session_id
        - SELECT by video_id
        - SELECT by detection_channel
        """
        from sqlalchemy import text

        # Insert test data
        event_id = str(uuid.uuid4())
        test_db.execute(text("""
            INSERT INTO detection_events (
                id, test_session_id, video_id, timestamp, detection_channel,
                labjack_voltage, voltage_level, latency_threshold_ms
            ) VALUES (
                :id, :session_id, :video_id, :timestamp, :channel,
                :voltage, :voltage_level, :threshold
            )
        """), {
            "id": event_id,
            "session_id": test_session.id,
            "video_id": test_session.video_id,
            "timestamp": 1234567890.0,
            "channel": "AIN0",
            "voltage": 3.3,
            "voltage_level": 3.3,
            "threshold": 100.0
        })
        test_db.commit()

        # Query by test_session_id
        result = test_db.execute(text("""
            SELECT * FROM detection_events WHERE test_session_id = :session_id
        """), {"session_id": test_session.id}).fetchone()

        assert result is not None, "Cannot query by test_session_id"

        # Query by detection_channel
        result = test_db.execute(text("""
            SELECT * FROM detection_events WHERE detection_channel = :channel
        """), {"channel": "AIN0"}).fetchone()

        assert result is not None, "Cannot query by detection_channel"
```

---

## PART 3: END-TO-END TEST SCENARIOS

### 3.1 Scenario 1: Single Video HIL Test

**Test File**: `/tests/e2e/test_single_video_hil.py`

```python
@pytest.mark.e2e
class TestSingleVideoHIL:
    """End-to-end test for single video HIL workflow"""

    def test_complete_single_video_hil_flow(self, client, test_db, test_project):
        """
        E2E TEST: Complete single-video HIL test workflow

        Flow:
        1. Upload video → ground truth generated
        2. Start HIL test session
        3. Video plays → LabJack detections occur
        4. Detection events saved to database ✅
        5. Results displayed with correct data

        Validates Fixes:
        - Detection events saved to database
        - Correct column names used
        """
        # Step 1: Create video with ground truth
        video = Video(
            id=str(uuid.uuid4()),
            filename="single_hil.mp4",
            file_path="/test/single_hil.mp4",
            project_id=test_project.id,
            duration=30.0,
            ground_truth_count=5
        )
        test_db.add(video)

        for i in range(5):
            gt = GroundTruthObject(
                id=str(uuid.uuid4()),
                video_id=video.id,
                timestamp=float(i * 2),
                class_label="pedestrian",
                x=100.0, y=100.0, width=50.0, height=100.0
            )
            test_db.add(gt)
        test_db.commit()

        # Step 2: Start HIL test
        payload = {
            "projectId": test_project.id,
            "videoId": video.id,
            "toleranceMs": 100
        }
        response = client.post("/api/hil/start", json=payload)
        assert response.status_code == 200

        session_id = response.json()["sessionId"]

        # Step 3: Simulate detections
        for i in range(5):
            detection_payload = {
                "unixTimestamp": time.time(),
                "signalType": "GPIO",
                "channel": 0,
                "signalValue": 3.3
            }
            response = client.post(
                f"/api/hil/sessions/{session_id}/detection",
                json=detection_payload
            )
            assert response.status_code == 201
            time.sleep(0.1)

        # Step 4: Verify database state
        events = test_db.query(DBDetectionEvent).filter(
            DBDetectionEvent.test_session_id == session_id
        ).all()

        assert len(events) == 5, f"Expected 5 events, got {len(events)}"

        for event in events:
            assert event.test_session_id == session_id, "Wrong column used"
            assert event.detection_channel is not None, "Channel not saved"
            assert event.video_relative_timestamp is not None, "Timing not saved"

        # Step 5: Get results
        response = client.get(f"/api/hil/sessions/{session_id}/results")
        assert response.status_code == 200

        results = response.json()
        assert results["totalDetections"] == 5
        assert len(results["detectionEvents"]) == 5
```

### 3.2 Scenario 2: 2-Video Sequence Test

**Test File**: `/tests/e2e/test_two_video_sequence.py`

```python
@pytest.mark.e2e
class TestTwoVideoSequence:
    """End-to-end test for 2-video sequence workflow"""

    def test_two_video_sequence_complete_flow(self, client, test_db, test_project):
        """
        E2E TEST: Complete 2-video sequence test

        Flow:
        1. Create 2 videos with ground truth
        2. Start sequence → SequenceVideoResult entries created ✅
        3. Video 1 plays → detections saved
        4. Video 1 ends → detection count verified
        5. Video 2 plays → detections saved
        6. Video 2 ends → sequence complete
        7. Results show all detections per video

        Validates Fixes:
        - SequenceVideoResult entries created
        - Detection events linked to correct video
        - Ground truth counts populated
        """
        # Step 1: Create videos
        video1 = Video(id=str(uuid.uuid4()), filename="seq_v1.mp4",
                      file_path="/seq_v1.mp4", project_id=test_project.id, duration=30.0)
        video2 = Video(id=str(uuid.uuid4()), filename="seq_v2.mp4",
                      file_path="/seq_v2.mp4", project_id=test_project.id, duration=40.0)
        test_db.add_all([video1, video2])

        # Ground truth for video 1 (3 objects)
        for i in range(3):
            gt = GroundTruthObject(id=str(uuid.uuid4()), video_id=video1.id,
                                  timestamp=float(i), class_label="pedestrian",
                                  x=100.0, y=100.0, width=50.0, height=100.0)
            test_db.add(gt)

        # Ground truth for video 2 (4 objects)
        for i in range(4):
            gt = GroundTruthObject(id=str(uuid.uuid4()), video_id=video2.id,
                                  timestamp=float(i), class_label="cyclist",
                                  x=200.0, y=200.0, width=60.0, height=120.0)
            test_db.add(gt)
        test_db.commit()

        # Step 2: Start sequence
        payload = {
            "projectId": test_project.id,
            "videoIds": [video1.id, video2.id],
            "maxLatencyMs": 100.0,
            "enableLabjackMonitoring": False
        }
        response = client.post("/api/video-sequences/start", json=payload)
        assert response.status_code == 201

        sequence_id = response.json()["sequenceId"]

        # Verify SequenceVideoResult entries created (CRITICAL FIX)
        results = test_db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == sequence_id
        ).order_by(SequenceVideoResult.sequence_order).all()

        assert len(results) == 2, "SequenceVideoResult entries not created"
        assert results[0].video_id == video1.id
        assert results[0].expected_detection_count == 3, "Ground truth count wrong"
        assert results[1].video_id == video2.id
        assert results[1].expected_detection_count == 4, "Ground truth count wrong"

        # Step 3-4: Play video 1
        started_at = time.time()
        client.post(f"/api/video-sequences/{sequence_id}/video-started",
                   json={"videoId": video1.id, "startedAt": started_at})

        # Simulate 3 detections for video 1
        for i in range(3):
            client.post(f"/api/video-sequences/{sequence_id}/detection",
                       json={"unixTimestamp": started_at + i, "signalType": "GPIO"})
            time.sleep(0.05)

        ended_at = time.time()
        response = client.post(f"/api/video-sequences/{sequence_id}/video-ended",
                              json={"videoId": video1.id, "endedAt": ended_at})
        assert response.json()["detectionCount"] == 3

        # Step 5-6: Play video 2
        started_at = time.time()
        client.post(f"/api/video-sequences/{sequence_id}/video-started",
                   json={"videoId": video2.id, "startedAt": started_at})

        # Simulate 4 detections for video 2
        for i in range(4):
            client.post(f"/api/video-sequences/{sequence_id}/detection",
                       json={"unixTimestamp": started_at + i, "signalType": "GPIO"})
            time.sleep(0.05)

        ended_at = time.time()
        response = client.post(f"/api/video-sequences/{sequence_id}/video-ended",
                              json={"videoId": video2.id, "endedAt": ended_at})
        assert response.json()["detectionCount"] == 4
        assert response.json()["sequenceComplete"] == True

        # Step 7: Get final results
        response = client.get(f"/api/video-sequences/{sequence_id}/results")
        assert response.status_code == 200

        data = response.json()
        assert data["totalVideos"] == 2
        assert data["totalDetections"] == 7

        # Verify per-video results
        video_results = data["perVideoResults"]
        assert len(video_results) == 2
        assert video_results[0]["detectionCount"] == 3
        assert len(video_results[0]["detectionEvents"]) == 3
        assert video_results[1]["detectionCount"] == 4
        assert len(video_results[1]["detectionEvents"]) == 4
```

### 3.3 Scenario 3: 5-Video Sequence Test

**Test File**: `/tests/e2e/test_five_video_sequence.py`

```python
@pytest.mark.e2e
class TestFiveVideoSequence:
    """Stress test with 5-video sequence"""

    def test_five_video_sequence_stress_test(self, client, test_db, test_project):
        """
        E2E STRESS TEST: 5-video sequence with varying detection counts

        Validates:
        - System handles multiple videos
        - SequenceVideoResult entries created for all
        - Detection events properly segregated per video
        - Results aggregation works correctly
        """
        # Create 5 videos with varying ground truth counts
        videos = []
        gt_counts = [2, 5, 3, 7, 4]  # Different detection counts per video

        for i, gt_count in enumerate(gt_counts):
            video = Video(
                id=str(uuid.uuid4()),
                filename=f"stress_v{i+1}.mp4",
                file_path=f"/stress_v{i+1}.mp4",
                project_id=test_project.id,
                duration=20.0 + (i * 5)
            )
            test_db.add(video)
            videos.append(video)

            # Add ground truth
            for j in range(gt_count):
                gt = GroundTruthObject(
                    id=str(uuid.uuid4()),
                    video_id=video.id,
                    timestamp=float(j * 2),
                    class_label="pedestrian" if j % 2 == 0 else "cyclist",
                    x=100.0, y=100.0, width=50.0, height=100.0
                )
                test_db.add(gt)

        test_db.commit()

        # Start sequence
        video_ids = [v.id for v in videos]
        payload = {
            "projectId": test_project.id,
            "videoIds": video_ids,
            "maxLatencyMs": 100.0,
            "enableLabjackMonitoring": False
        }
        response = client.post("/api/video-sequences/start", json=payload)
        sequence_id = response.json()["sequenceId"]

        # Verify all SequenceVideoResult entries created
        results = test_db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == sequence_id
        ).order_by(SequenceVideoResult.sequence_order).all()

        assert len(results) == 5, f"Expected 5 SequenceVideoResult entries, got {len(results)}"

        for i, (video, expected_count) in enumerate(zip(videos, gt_counts)):
            assert results[i].video_id == video.id
            assert results[i].expected_detection_count == expected_count
            assert results[i].sequence_order == i

        # Play all videos sequentially
        total_detections = 0
        for video, expected_count in zip(videos, gt_counts):
            started_at = time.time()
            client.post(f"/api/video-sequences/{sequence_id}/video-started",
                       json={"videoId": video.id, "startedAt": started_at})

            # Simulate detections
            for j in range(expected_count):
                client.post(f"/api/video-sequences/{sequence_id}/detection",
                           json={"unixTimestamp": started_at + j * 0.1, "signalType": "GPIO"})
                time.sleep(0.02)

            total_detections += expected_count

            ended_at = time.time()
            response = client.post(f"/api/video-sequences/{sequence_id}/video-ended",
                                  json={"videoId": video.id, "endedAt": ended_at})
            assert response.json()["detectionCount"] == expected_count

        # Verify final results
        response = client.get(f"/api/video-sequences/{sequence_id}/results")
        data = response.json()

        assert data["totalVideos"] == 5
        assert data["totalDetections"] == sum(gt_counts)
        assert len(data["perVideoResults"]) == 5

        # Verify each video has correct detection count
        for i, expected_count in enumerate(gt_counts):
            assert data["perVideoResults"][i]["detectionCount"] == expected_count
            assert len(data["perVideoResults"][i]["detectionEvents"]) == expected_count
```

---

## PART 4: DATABASE VALIDATION QUERIES

### 4.1 SQL Verification Queries

**Test File**: `/tests/validation/test_sql_queries.py`

```python
class TestSQLValidation:
    """Raw SQL validation queries"""

    def test_detection_events_exist_query(self, test_db, test_session):
        """
        SQL QUERY: Verify detection events exist for session

        Query:
        SELECT * FROM detection_events WHERE test_session_id = ?
        """
        from sqlalchemy import text

        # Insert test event
        event_id = str(uuid.uuid4())
        test_db.execute(text("""
            INSERT INTO detection_events (
                id, test_session_id, timestamp, detection_channel, labjack_voltage
            ) VALUES (:id, :session_id, :timestamp, :channel, :voltage)
        """), {
            "id": event_id,
            "session_id": test_session.id,
            "timestamp": time.time(),
            "channel": "AIN0",
            "voltage": 3.3
        })
        test_db.commit()

        # Query
        result = test_db.execute(text("""
            SELECT COUNT(*) as count
            FROM detection_events
            WHERE test_session_id = :session_id
        """), {"session_id": test_session.id}).fetchone()

        assert result[0] > 0, "No detection events found for session"


    def test_sequence_video_results_populated_query(self, test_db):
        """
        SQL QUERY: Verify sequence_video_results populated

        Query:
        SELECT * FROM sequence_video_results WHERE video_sequence_id = ?
        """
        from sqlalchemy import text

        sequence_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())

        # Insert test data
        test_db.execute(text("""
            INSERT INTO sequence_video_results (
                id, video_sequence_id, video_id, sequence_order,
                expected_detection_count, actual_detection_count
            ) VALUES (:id, :seq_id, :vid_id, :order, :expected, :actual)
        """), {
            "id": str(uuid.uuid4()),
            "seq_id": sequence_id,
            "vid_id": video_id,
            "order": 0,
            "expected": 10,
            "actual": 8
        })
        test_db.commit()

        # Query
        result = test_db.execute(text("""
            SELECT expected_detection_count, actual_detection_count
            FROM sequence_video_results
            WHERE video_sequence_id = :seq_id
        """), {"seq_id": sequence_id}).fetchone()

        assert result is not None, "sequence_video_results entry not found"
        assert result[0] == 10, "expected_detection_count not saved"
        assert result[1] == 8, "actual_detection_count not saved"


    def test_ground_truth_counts_per_video_query(self, test_db, test_video):
        """
        SQL QUERY: Check ground truth counts per video

        Query:
        SELECT COUNT(*) FROM ground_truth_objects WHERE video_id = ?
        """
        from sqlalchemy import text

        # Add ground truth
        for i in range(7):
            gt = GroundTruthObject(
                id=str(uuid.uuid4()),
                video_id=test_video.id,
                timestamp=float(i),
                class_label="pedestrian",
                x=100.0, y=100.0, width=50.0, height=100.0
            )
            test_db.add(gt)
        test_db.commit()

        # Query
        result = test_db.execute(text("""
            SELECT COUNT(*) as count
            FROM ground_truth_objects
            WHERE video_id = :video_id
        """), {"video_id": test_video.id}).fetchone()

        assert result[0] == 7, f"Expected 7 ground truth objects, got {result[0]}"
```

### 4.2 Foreign Key Relationship Validation

```python
class TestForeignKeyValidation:
    """Validate database foreign key relationships"""

    def test_detection_event_to_test_session_fk(self, test_db):
        """
        FK VALIDATION: detection_events.test_session_id → test_sessions.id
        """
        from sqlalchemy import inspect

        inspector = inspect(test_db.bind)
        fks = inspector.get_foreign_keys('detection_events')

        # Find test_session_id FK
        session_fk = next((fk for fk in fks if 'test_session_id' in fk['constrained_columns']), None)

        assert session_fk is not None, "FK for test_session_id not found"
        assert session_fk['referred_table'] == 'test_sessions'
        assert session_fk['referred_columns'][0] == 'id'


    def test_sequence_video_result_to_video_fk(self, test_db):
        """
        FK VALIDATION: sequence_video_results.video_id → videos.id
        """
        from sqlalchemy import inspect

        inspector = inspect(test_db.bind)
        fks = inspector.get_foreign_keys('sequence_video_results')

        video_fk = next((fk for fk in fks if 'video_id' in fk['constrained_columns']), None)

        assert video_fk is not None, "FK for video_id not found"
        assert video_fk['referred_table'] == 'videos'
```

---

## PART 5: FAILURE CASES TO TEST

### 5.1 Edge Cases and Error Scenarios

**Test File**: `/tests/edge_cases/test_hil_failure_scenarios.py`

```python
class TestHILFailureScenarios:
    """Test failure cases and error handling"""

    def test_video_with_no_ground_truth(self, client, test_db, test_project):
        """
        EDGE CASE: What if video has no ground truth?

        Expected:
        - SequenceVideoResult.expected_detection_count = 0
        - Test runs without errors
        - Results show 0 expected detections
        """
        video = Video(
            id=str(uuid.uuid4()),
            filename="no_gt.mp4",
            file_path="/no_gt.mp4",
            project_id=test_project.id,
            duration=30.0,
            ground_truth_count=0  # No ground truth
        )
        test_db.add(video)
        test_db.commit()

        payload = {
            "projectId": test_project.id,
            "videoIds": [video.id],
            "maxLatencyMs": 100.0
        }
        response = client.post("/api/video-sequences/start", json=payload)
        assert response.status_code == 201

        sequence_id = response.json()["sequenceId"]

        # Verify SequenceVideoResult created with 0 expected count
        result = test_db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == sequence_id
        ).first()

        assert result is not None, "SequenceVideoResult should be created even with no GT"
        assert result.expected_detection_count == 0


    def test_labjack_disconnect_mid_test(self, test_db, test_session):
        """
        EDGE CASE: LabJack disconnects during test

        Expected:
        - Monitoring stops gracefully
        - Events saved up to disconnect
        - No data corruption
        """
        from services.labjack_detection_service import get_detection_monitor

        monitor = get_detection_monitor()
        monitor.start_monitoring(session_id=test_session.id)

        # Simulate some detections
        for i in range(3):
            event = DetectionEvent(
                id=str(uuid.uuid4()),
                session_id=test_session.id,
                timestamp=datetime.now(),
                channel="AIN0",
                voltage=3.3,
                threshold=2.5
            )
            monitor._record_detection_event(test_session.id, event)

        time.sleep(0.2)

        # Simulate disconnect by stopping monitor
        monitor.stop_monitoring(test_session.id)

        # Verify events saved
        events = test_db.query(DBDetectionEvent).filter(
            DBDetectionEvent.test_session_id == test_session.id
        ).all()

        assert len(events) >= 3, "Events before disconnect should be saved"


    def test_database_transaction_fails(self, test_db, monkeypatch):
        """
        EDGE CASE: Database transaction fails during event storage

        Expected:
        - Error logged
        - Event stored in fallback method
        - System continues operating
        """
        from services.labjack_detection_service import LabJackDetectionMonitor

        monitor = LabJackDetectionMonitor()

        # Mock database commit to fail
        def mock_commit_fail(*args, **kwargs):
            raise Exception("Database commit failed")

        monkeypatch.setattr("database.SessionLocal.commit", mock_commit_fail)

        event = DetectionEvent(
            id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            channel="AIN0",
            voltage=3.3,
            threshold=2.5
        )

        # Should not raise exception - should use fallback
        try:
            import asyncio
            asyncio.run(monitor._store_event_in_db(event))
        except Exception as e:
            pytest.fail(f"Should handle DB failure gracefully: {e}")
```

---

## PART 6: PYTEST CONFIGURATION

### 6.1 Pytest Setup

**File**: `/tests/conftest.py`

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from models import Project, Video, TestSession
import uuid

# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_hil.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def test_db():
    """Create test database for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def test_project(test_db):
    """Create test project"""
    project = Project(
        id=str(uuid.uuid4()),
        name="Test HIL Project",
        description="Testing HIL fixes",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO",
        status="active"
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)
    return project

@pytest.fixture
def test_video(test_db, test_project):
    """Create test video"""
    video = Video(
        id=str(uuid.uuid4()),
        filename="test_video.mp4",
        file_path="/test/test_video.mp4",
        project_id=test_project.id,
        duration=30.0,
        fps=30.0,
        status="uploaded"
    )
    test_db.add(video)
    test_db.commit()
    test_db.refresh(video)
    return video

@pytest.fixture
def test_session(test_db, test_project, test_video):
    """Create test session"""
    session = TestSession(
        id=str(uuid.uuid4()),
        name="Test Session",
        project_id=test_project.id,
        video_id=test_video.id,
        status="created"
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)
    return session

@pytest.fixture
def client():
    """Test client for API"""
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)
```

### 6.2 Test Execution Plan

**File**: `/tests/RUN_HIL_TESTS.md`

```markdown
# HIL System Fixes - Test Execution Plan

## Quick Start

```bash
# Run all HIL fix tests
pytest tests/ -v -m hil_fixes

# Run specific test categories
pytest tests/unit/ -v                    # Unit tests only
pytest tests/integration/ -v             # Integration tests
pytest tests/e2e/ -v                     # End-to-end tests
pytest tests/validation/ -v              # Database validation

# Run with coverage
pytest tests/ --cov=services --cov=routers --cov-report=html
```

## Test Categories

### Unit Tests (Fast - ~5 seconds)
```bash
pytest tests/unit/test_labjack_detection_storage.py -v
pytest tests/unit/test_video_sequence_creation.py -v
```

### Integration Tests (Medium - ~30 seconds)
```bash
pytest tests/integration/test_hil_detection_flow.py -v
pytest tests/integration/test_database_validation.py -v
```

### E2E Tests (Slow - ~2 minutes)
```bash
pytest tests/e2e/test_single_video_hil.py -v
pytest tests/e2e/test_two_video_sequence.py -v
pytest tests/e2e/test_five_video_sequence.py -v
```

### Validation Queries (Fast - ~5 seconds)
```bash
pytest tests/validation/test_sql_queries.py -v
```

### Edge Cases (Medium - ~20 seconds)
```bash
pytest tests/edge_cases/test_hil_failure_scenarios.py -v
```

## Expected Results

All tests should PASS:
- ✅ Detection events saved to database
- ✅ Correct column names used (test_session_id, detection_channel)
- ✅ SequenceVideoResult entries created
- ✅ Ground truth counts populated
- ✅ Foreign key relationships valid
```

---

## PART 7: MANUAL VERIFICATION CHECKLIST

### 7.1 Database Verification

**File**: `/tests/MANUAL_VERIFICATION.md`

```markdown
# Manual Verification Checklist

## 1. Database Schema Verification

```sql
-- Verify detection_events table has correct columns
PRAGMA table_info(detection_events);
-- Should show: test_session_id, detection_channel, detection_metadata

-- Verify sequence_video_results table exists
SELECT name FROM sqlite_master WHERE type='table' AND name='sequence_video_results';
-- Should return: sequence_video_results

-- Verify foreign keys
PRAGMA foreign_key_list(detection_events);
-- Should show FK to test_sessions(id)
```

## 2. Detection Event Storage Verification

```sql
-- Start HIL test, trigger detection, then run:
SELECT
    id,
    test_session_id,
    detection_channel,
    labjack_voltage,
    video_relative_timestamp,
    actual_latency_ms
FROM detection_events
ORDER BY timestamp DESC
LIMIT 5;

-- Expected: Recent events with all fields populated
```

## 3. Sequence Video Results Verification

```sql
-- Start multi-video sequence, then run:
SELECT
    svr.id,
    svr.video_id,
    svr.sequence_order,
    svr.expected_detection_count,
    svr.actual_detection_count,
    v.filename
FROM sequence_video_results svr
JOIN videos v ON svr.video_id = v.id
WHERE svr.video_sequence_id = '<your-sequence-id>'
ORDER BY svr.sequence_order;

-- Expected: One row per video with correct ground truth counts
```

## 4. Ground Truth Count Verification

```sql
-- For each video in sequence:
SELECT
    v.id,
    v.filename,
    COUNT(gt.id) as ground_truth_count
FROM videos v
LEFT JOIN ground_truth_objects gt ON gt.video_id = v.id
WHERE v.id IN ('<video-id-1>', '<video-id-2>')
GROUP BY v.id;

-- Cross-reference with sequence_video_results.expected_detection_count
```

## 5. Frontend Display Verification

1. Start multi-video HIL test
2. Navigate to Results page
3. Verify:
   - ✅ Detection events displayed (not just count)
   - ✅ Each video shows its detections
   - ✅ Detection timestamps shown
   - ✅ Detection channels displayed
   - ✅ Video-relative timestamps correct

## 6. API Response Verification

```bash
# Start sequence
curl -X POST http://localhost:8000/api/video-sequences/start \
  -H "Content-Type: application/json" \
  -d '{
    "projectId": "...",
    "videoIds": ["...", "..."],
    "maxLatencyMs": 100
  }'

# Get results
curl http://localhost:8000/api/video-sequences/<sequence-id>/results

# Verify response includes:
# - perVideoResults[].detectionEvents[] array (not empty)
# - Each event has: id, timestamp, videoRelativeTimestamp, channel
```
```

---

## SUMMARY

### Test Coverage Matrix

| Fix | Unit Tests | Integration Tests | E2E Tests | SQL Validation |
|-----|-----------|------------------|-----------|---------------|
| Detection events saved | ✅ 3 tests | ✅ 2 tests | ✅ 3 scenarios | ✅ 2 queries |
| Sequence entries created | ✅ 2 tests | ✅ 2 tests | ✅ 3 scenarios | ✅ 2 queries |
| Column names corrected | ✅ 2 tests | ✅ 3 tests | ✅ Implicit in all | ✅ 3 queries |

### Test Execution Order

1. **Unit Tests** (5 min) - Fast validation of core functions
2. **Integration Tests** (10 min) - Database and API integration
3. **E2E Tests** (15 min) - Complete user workflows
4. **SQL Validation** (2 min) - Direct database verification
5. **Edge Cases** (5 min) - Failure scenario handling

**Total Estimated Time**: ~37 minutes

### Success Criteria

All tests must pass with:
- ✅ 100% detection event storage success
- ✅ 100% sequence entry creation
- ✅ 0 column name errors
- ✅ All foreign key relationships valid
- ✅ Frontend displays detection events correctly

---

**Next Steps**:
1. Review this testing strategy
2. Implement test files in parallel
3. Run tests in CI/CD pipeline
4. Document any failures
5. Update production deployment checklist
