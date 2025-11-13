from backend.routers.video_sequence_testing import VideoResultSummary, DetectionEventSummary


def test_video_result_summary_exposes_extended_fields():
    event = DetectionEventSummary(
        id="event-1",
        timestamp=123.456,
        video_relative_timestamp=2.5,
        signal_type="GPIO",
        channel="AIN0",
        signal_value=3.3,
        video_id="vid-123",
        sequence_video_result_id="seq-result-1"
    )

    summary = VideoResultSummary(
        video_id="vid-123",
        video_name="Test Video",
        sequence_index=0,
        video_url="http://localhost:8000/uploads/test.mp4",
        start_time=0.0,
        end_time=5.0,
        duration=5.0,
        started_at_iso="2025-01-01T00:00:00Z",
        ended_at_iso="2025-01-01T00:00:05Z",
        video_status="pass",
        expected_detection_count=10,
        actual_detection_count=8,
        passed_detections=7,
        failed_detections=1,
        pass_rate_percent=87.5,
        avg_latency_ms=45.0,
        max_latency_ms=90.0,
        min_latency_ms=30.0,
        latency_threshold_ms=120.0,
        detection_count=8,
        detection_events=[event],
        pass_fail="pass",
        metrics={}
    )

    data = summary.dict()

    assert data["video_status"] == "pass"
    assert data["expected_detection_count"] == 10
    assert data["actual_detection_count"] == 8
    assert data["passed_detections"] == 7
    assert data["failed_detections"] == 1
    assert data["latency_threshold_ms"] == 120.0
    assert len(data["detection_events"]) == 1
    assert data["detection_events"][0]["video_id"] == "vid-123"
    assert data["detection_events"][0]["sequence_video_result_id"] == "seq-result-1"
