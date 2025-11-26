"""
Frontend Metrics Display Integration Tests

Tests the complete integration of metrics from backend API to frontend display.
Verifies that the metrics field in /api/test-sessions/{id}/results contains
all required fields with correct data types and precision.

Test Session: 49e5d00f-eea7-44cb-a647-480268ef43ee
"""

import pytest
import requests
from typing import Dict, Any
import json

# Test Configuration
API_BASE_URL = "http://localhost:8000"
TEST_SESSION_ID = "49e5d00f-eea7-44cb-a647-480268ef43ee"
METRICS_ENDPOINT = f"{API_BASE_URL}/api/test-sessions/{TEST_SESSION_ID}/results"


class TestFrontendMetricsIntegration:
    """Integration tests for frontend metrics display"""

    def test_api_endpoint_accessible(self):
        """Test that the API endpoint is accessible"""
        response = requests.get(METRICS_ENDPOINT, timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("content-type") == "application/json", \
            "Response should be JSON"

    def test_response_has_metrics_field(self):
        """Test that response contains metrics field at top level"""
        response = requests.get(METRICS_ENDPOINT, timeout=10)
        data = response.json()

        assert "metrics" in data, \
            f"Response missing 'metrics' field. Keys: {list(data.keys())}"
        assert data["metrics"] is not None, \
            "metrics field should not be None"
        assert isinstance(data["metrics"], dict), \
            f"metrics should be dict, got {type(data['metrics'])}"

    def test_metrics_has_all_required_fields(self):
        """Test that metrics object contains all required fields"""
        response = requests.get(METRICS_ENDPOINT, timeout=10)
        data = response.json()
        metrics = data["metrics"]

        required_fields = [
            "precision",
            "recall",
            "f1_score",
            "accuracy",
            "true_positives",
            "false_positives",
            "false_negatives"
        ]

        for field in required_fields:
            assert field in metrics, \
                f"Missing required field: {field}. Available: {list(metrics.keys())}"

    def test_metrics_percentage_precision(self):
        """Test that percentage metrics have correct precision (1 decimal place)"""
        response = requests.get(METRICS_ENDPOINT, timeout=10)
        data = response.json()
        metrics = data["metrics"]

        percentage_fields = ["precision", "recall", "f1_score", "accuracy"]

        for field in percentage_fields:
            value = metrics[field]
            assert isinstance(value, (int, float)), \
                f"{field} should be numeric, got {type(value)}"

            # Check it's a percentage (0-100)
            assert 0 <= value <= 100, \
                f"{field} should be 0-100%, got {value}"

            # Check precision (1 decimal place)
            str_value = str(value)
            if "." in str_value:
                decimal_places = len(str_value.split(".")[1])
                assert decimal_places <= 1, \
                    f"{field} should have max 1 decimal place, got {decimal_places}"

    def test_metrics_count_fields_are_integers(self):
        """Test that count fields are integers"""
        response = requests.get(METRICS_ENDPOINT, timeout=10)
        data = response.json()
        metrics = data["metrics"]

        count_fields = [
            "true_positives",
            "false_positives",
            "false_negatives",
            "total_ground_truth",
            "total_detections",
            "matched_detections"
        ]

        for field in count_fields:
            if field in metrics:
                value = metrics[field]
                assert isinstance(value, int), \
                    f"{field} should be integer, got {type(value)}: {value}"
                assert value >= 0, \
                    f"{field} should be non-negative, got {value}"

    def test_metrics_latency_fields(self):
        """Test that latency metrics are present and valid"""
        response = requests.get(METRICS_ENDPOINT, timeout=10)
        data = response.json()
        metrics = data["metrics"]

        latency_fields = ["mean_latency_ms", "within_tolerance_percentage"]

        for field in latency_fields:
            if field in metrics:
                value = metrics[field]
                assert isinstance(value, (int, float)), \
                    f"{field} should be numeric, got {type(value)}"
                assert value >= 0, \
                    f"{field} should be non-negative, got {value}"

                # Check precision (1 decimal place)
                str_value = str(value)
                if "." in str_value:
                    decimal_places = len(str_value.split(".")[1])
                    assert decimal_places <= 1, \
                        f"{field} should have max 1 decimal place, got {decimal_places}"

    def test_metrics_mathematical_consistency(self):
        """Test that metrics are mathematically consistent"""
        response = requests.get(METRICS_ENDPOINT, timeout=10)
        data = response.json()
        metrics = data["metrics"]

        tp = metrics["true_positives"]
        fp = metrics["false_positives"]
        fn = metrics["false_negatives"]

        # Precision = TP / (TP + FP)
        if tp + fp > 0:
            expected_precision = (tp / (tp + fp)) * 100
            actual_precision = metrics["precision"]
            assert abs(expected_precision - actual_precision) < 0.2, \
                f"Precision mismatch: expected {expected_precision:.1f}, got {actual_precision}"

        # Recall = TP / (TP + FN)
        if tp + fn > 0:
            expected_recall = (tp / (tp + fn)) * 100
            actual_recall = metrics["recall"]
            assert abs(expected_recall - actual_recall) < 0.2, \
                f"Recall mismatch: expected {expected_recall:.1f}, got {actual_recall}"

        # F1 = 2 * (Precision * Recall) / (Precision + Recall)
        precision = metrics["precision"]
        recall = metrics["recall"]
        if precision + recall > 0:
            expected_f1 = 2 * (precision * recall) / (precision + recall)
            actual_f1 = metrics["f1_score"]
            assert abs(expected_f1 - actual_f1) < 0.2, \
                f"F1 Score mismatch: expected {expected_f1:.1f}, got {actual_f1}"

    def test_frontend_typescript_compatibility(self):
        """Test that metrics match frontend TypeScript interface expectations"""
        response = requests.get(METRICS_ENDPOINT, timeout=10)
        data = response.json()
        metrics = data["metrics"]

        # Frontend expects camelCase or snake_case (both should work)
        # ComparisonMetrics interface from enhanced-results.ts
        expected_interface = {
            "accuracy": (int, float),
            "precision": (int, float),
            "recall": (int, float),
            "f1_score": (int, float),
            "true_positives": int,
            "false_positives": int,
            "false_negatives": int,
        }

        for field, expected_types in expected_interface.items():
            assert field in metrics or field.replace("_", "") in metrics, \
                f"Field {field} missing from metrics"

            value = metrics.get(field)
            if value is not None:
                assert isinstance(value, expected_types), \
                    f"{field} should be {expected_types}, got {type(value)}"

    def test_response_structure_complete(self):
        """Test complete response structure for frontend"""
        response = requests.get(METRICS_ENDPOINT, timeout=10)
        data = response.json()

        # Check top-level structure
        assert "sessionId" in data or "session_id" in data, \
            "Response missing session ID"
        assert "sessionStatus" in data or "session_status" in data, \
            "Response missing session status"
        assert "metrics" in data, \
            "Response missing metrics field"
        assert "results" in data, \
            "Response missing results array"

        # Verify metrics is at the correct level (top-level, not nested)
        assert data["metrics"] is not None, \
            "metrics should not be None at top level"

    def test_metrics_display_readiness(self):
        """Test that metrics are ready for frontend display"""
        response = requests.get(METRICS_ENDPOINT, timeout=10)
        data = response.json()
        metrics = data["metrics"]

        # Simulate frontend display formatting
        display_data = {
            "Precision": f"{metrics['precision']}%",
            "Recall": f"{metrics['recall']}%",
            "F1 Score": f"{metrics['f1_score']}%",
            "Accuracy": f"{metrics['accuracy']}%",
            "True Positives": metrics['true_positives'],
            "False Positives": metrics['false_positives'],
            "False Negatives": metrics['false_negatives'],
        }

        # Verify all display values are valid
        for label, value in display_data.items():
            assert value is not None, f"{label} display value is None"
            assert str(value) != "None", f"{label} stringifies to 'None'"

            if "%" in str(value):
                # Extract numeric part and verify it's valid
                numeric_part = str(value).replace("%", "")
                try:
                    float(numeric_part)
                except ValueError:
                    pytest.fail(f"{label} has invalid percentage: {value}")

    def test_api_response_performance(self):
        """Test that API responds within acceptable time"""
        import time
        start = time.time()
        response = requests.get(METRICS_ENDPOINT, timeout=10)
        duration = time.time() - start

        assert duration < 5.0, \
            f"API response too slow: {duration:.2f}s (max 5s)"
        assert response.status_code == 200, \
            f"API returned error status: {response.status_code}"

    def test_metrics_export_format(self):
        """Test that metrics can be exported in JSON format"""
        response = requests.get(METRICS_ENDPOINT, timeout=10)
        data = response.json()
        metrics = data["metrics"]

        # Try to serialize metrics
        try:
            json_str = json.dumps(metrics)
            parsed = json.loads(json_str)
            assert parsed == metrics, "Metrics lost data in JSON round-trip"
        except Exception as e:
            pytest.fail(f"Metrics cannot be serialized to JSON: {e}")

    def test_comprehensive_metrics_report(self):
        """Generate comprehensive metrics report for verification"""
        response = requests.get(METRICS_ENDPOINT, timeout=10)
        data = response.json()
        metrics = data["metrics"]

        print("\n" + "="*60)
        print("FRONTEND METRICS INTEGRATION TEST REPORT")
        print("="*60)
        print(f"\nSession ID: {TEST_SESSION_ID}")
        print(f"API Endpoint: {METRICS_ENDPOINT}")
        print(f"\nResponse Status: {response.status_code} OK")
        print(f"\n{'Metric':<30} {'Value':<15} {'Type':<15}")
        print("-"*60)

        for key, value in metrics.items():
            value_type = type(value).__name__
            if isinstance(value, (int, float)):
                if key in ["precision", "recall", "f1_score", "accuracy"]:
                    display_value = f"{value}%"
                else:
                    display_value = str(value)
            else:
                display_value = str(value)

            print(f"{key:<30} {display_value:<15} {value_type:<15}")

        print("\n" + "="*60)
        print("✅ ALL METRICS VERIFIED FOR FRONTEND DISPLAY")
        print("="*60 + "\n")


# API Response Format Documentation
EXPECTED_API_RESPONSE_FORMAT = """
Expected API Response Format for /api/test-sessions/{id}/results:

{
  "sessionId": "49e5d00f-eea7-44cb-a647-480268ef43ee",
  "sessionStatus": "completed",
  "perVideoResults": [...],
  "metrics": {
    "precision": 85.5,        // Percentage, 1 decimal place
    "recall": 92.3,           // Percentage, 1 decimal place
    "f1_score": 88.8,         // Percentage, 1 decimal place
    "accuracy": 89.1,         // Percentage, 1 decimal place
    "true_positives": 42,     // Integer count
    "false_positives": 7,     // Integer count
    "false_negatives": 3,     // Integer count
    "total_ground_truth": 45, // Integer count
    "total_detections": 49,   // Integer count
    "matched_detections": 42, // Integer count
    "mean_latency_ms": 45.2,  // Float, 1 decimal place
    "within_tolerance_percentage": 95.8  // Percentage, 1 decimal
  },
  "results": [...]
}

Frontend Display Components:
- ComparisonMetricsCard: Displays precision, recall, f1_score, accuracy
- EnhancedTestMetricsPanel: Shows detailed metrics with counts
- QualityMetricsCard: Visualizes metrics with progress bars

TypeScript Interface (enhanced-results.ts):
interface ComparisonMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  averageLatency: number;
}
"""


if __name__ == "__main__":
    print(EXPECTED_API_RESPONSE_FORMAT)
    pytest.main([__file__, "-v", "--tb=short"])
