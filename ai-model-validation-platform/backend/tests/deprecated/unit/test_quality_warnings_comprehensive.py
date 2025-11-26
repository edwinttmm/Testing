"""
DEPRECATED TEST FILE
===================

This test file has been deprecated on 2025-11-20 because it imports services
that no longer exist or have been removed from the codebase.

Deprecated services used:
- Services that were removed during architecture refactoring
- Services that were consolidated into other modules
- Services that were replaced with newer implementations

This file is preserved for historical reference but is not actively maintained.
If you need similar functionality, please check the current service implementations
in src/services/ or consult the documentation.

Original location: tests/unit/test_quality_warnings_comprehensive.py
"""

"""
Comprehensive Unit Tests for Quality Warning System

Tests the quality_warnings.py service to ensure:
1. Correct warning generation for different quality scenarios
2. Accurate quality statistics calculation
3. Proper severity levels
4. Correct recommendations
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

# Import the quality warning system
import sys
sys.path.insert(0, '/home/rigade/Testing/ai-model-validation-platform/backend')

from services.quality_warnings import QualityWarning, check_quality, get_quality_stats


class TestQualityWarningGeneration:
    """Test quality warning generation logic"""

    def test_no_detections_generates_error(self):
        """Test that no detections generates ERROR severity warning"""
        # Mock database session
        mock_db = Mock(spec=Session)

        # Mock query to return 0 detections
        mock_query = MagicMock()
        mock_query.filter.return_value.count.return_value = 0
        mock_db.query.return_value = mock_query

        # Also mock session query
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Call quality check
        warnings = QualityWarning.check_session_quality("test-session-id", mock_db)

        # Verify WARNING generated
        assert len(warnings) >= 1
        assert any(w['severity'] == 'ERROR' for w in warnings)
        assert any(w['code'] == 'NO_DETECTIONS' for w in warnings)
        assert any('No detections captured' in w['message'] for w in warnings)

    def test_all_degraded_generates_error(self):
        """Test that all degraded detections generates ERROR severity warning"""
        mock_db = Mock(spec=Session)

        # Mock total detections = 100
        total_query = MagicMock()
        total_query.filter.return_value.count.return_value = 100

        # Mock validated detections = 0
        validated_query = MagicMock()
        validated_query.filter.return_value.filter.return_value.count.return_value = 0

        # Setup query mock to return different values on different calls
        mock_db.query.side_effect = [total_query, validated_query, MagicMock()]

        warnings = QualityWarning.check_session_quality("test-session-id", mock_db)

        # Verify ERROR warning generated
        assert len(warnings) >= 1
        assert any(w['severity'] == 'ERROR' for w in warnings)
        assert any(w['code'] == 'ALL_DEGRADED' for w in warnings)
        assert any('All 100 detections have degraded timing' in w['message'] for w in warnings)

    def test_low_quality_rate_generates_warning(self):
        """Test that < 50% validation rate generates WARNING"""
        mock_db = Mock(spec=Session)

        # Mock total = 100, validated = 40 (40% < 50%)
        total_query = MagicMock()
        total_query.filter.return_value.count.return_value = 100

        validated_query = MagicMock()
        validated_query.filter.return_value.filter.return_value.count.return_value = 40

        mock_db.query.side_effect = [total_query, validated_query, MagicMock()]

        warnings = QualityWarning.check_session_quality("test-session-id", mock_db)

        # Verify WARNING generated
        assert len(warnings) >= 1
        assert any(w['severity'] == 'WARNING' for w in warnings)
        assert any(w['code'] == 'LOW_QUALITY_RATE' for w in warnings)

    def test_some_degraded_generates_info(self):
        """Test that 50-90% validation rate generates INFO"""
        mock_db = Mock(spec=Session)

        # Mock total = 100, validated = 85 (85% between 50-90%)
        total_query = MagicMock()
        total_query.filter.return_value.count.return_value = 100

        validated_query = MagicMock()
        validated_query.filter.return_value.filter.return_value.count.return_value = 85

        mock_db.query.side_effect = [total_query, validated_query, MagicMock()]

        warnings = QualityWarning.check_session_quality("test-session-id", mock_db)

        # Verify INFO warning generated
        assert len(warnings) >= 1
        assert any(w['severity'] == 'INFO' for w in warnings)
        assert any(w['code'] == 'SOME_DEGRADED' for w in warnings)

    def test_session_timing_degraded_flag_generates_warning(self):
        """Test that session.timing_degraded=True generates warning"""
        mock_db = Mock(spec=Session)

        # Mock good detection quality (95%)
        total_query = MagicMock()
        total_query.filter.return_value.count.return_value = 100

        validated_query = MagicMock()
        validated_query.filter.return_value.filter.return_value.count.return_value = 95

        # Mock session with timing_degraded=True
        mock_session = Mock()
        mock_session.timing_degraded = True
        session_query = MagicMock()
        session_query.filter.return_value.first.return_value = mock_session

        mock_db.query.side_effect = [total_query, validated_query, session_query]

        warnings = QualityWarning.check_session_quality("test-session-id", mock_db)

        # Verify WARNING about session timing degradation
        assert any(w['code'] == 'SESSION_TIMING_DEGRADED' for w in warnings)


class TestQualityStatistics:
    """Test quality statistics calculation"""

    def test_statistics_calculation_accurate(self):
        """Test that quality statistics are calculated correctly"""
        mock_db = Mock(spec=Session)

        # Mock statistics query result
        mock_result = Mock()
        mock_result.total = 100
        mock_result.validated = 80
        mock_result.degraded = 20

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_result
        mock_db.query.return_value = mock_query

        stats = QualityWarning.get_quality_statistics("test-session-id", mock_db)

        # Verify calculations
        assert stats['total_detections'] == 100
        assert stats['validated_detections'] == 80
        assert stats['degraded_detections'] == 20
        assert stats['non_validated_detections'] == 20
        assert stats['validation_rate'] == 80.0
        assert stats['degradation_rate'] == 20.0

    def test_quality_level_excellent(self):
        """Test EXCELLENT quality level for >= 95% validation"""
        mock_db = Mock(spec=Session)

        mock_result = Mock()
        mock_result.total = 100
        mock_result.validated = 96
        mock_result.degraded = 4

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_result
        mock_db.query.return_value = mock_query

        stats = QualityWarning.get_quality_statistics("test-session-id", mock_db)

        assert stats['quality_level'] == 'EXCELLENT'

    def test_quality_level_good(self):
        """Test GOOD quality level for 80-95% validation"""
        mock_db = Mock(spec=Session)

        mock_result = Mock()
        mock_result.total = 100
        mock_result.validated = 85
        mock_result.degraded = 15

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_result
        mock_db.query.return_value = mock_query

        stats = QualityWarning.get_quality_statistics("test-session-id", mock_db)

        assert stats['quality_level'] == 'GOOD'

    def test_quality_level_fair(self):
        """Test FAIR quality level for 50-80% validation"""
        mock_db = Mock(spec=Session)

        mock_result = Mock()
        mock_result.total = 100
        mock_result.validated = 60
        mock_result.degraded = 40

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_result
        mock_db.query.return_value = mock_query

        stats = QualityWarning.get_quality_statistics("test-session-id", mock_db)

        assert stats['quality_level'] == 'FAIR'

    def test_quality_level_poor(self):
        """Test POOR quality level for < 50% validation"""
        mock_db = Mock(spec=Session)

        mock_result = Mock()
        mock_result.total = 100
        mock_result.validated = 30
        mock_result.degraded = 70

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_result
        mock_db.query.return_value = mock_query

        stats = QualityWarning.get_quality_statistics("test-session-id", mock_db)

        assert stats['quality_level'] == 'POOR'


class TestWarningRecommendations:
    """Test that warnings include actionable recommendations"""

    def test_no_detections_has_recommendation(self):
        """Test NO_DETECTIONS warning includes actionable recommendation"""
        mock_db = Mock(spec=Session)
        mock_query = MagicMock()
        mock_query.filter.return_value.count.return_value = 0
        mock_db.query.return_value = mock_query
        mock_db.query.return_value.filter.return_value.first.return_value = None

        warnings = QualityWarning.check_session_quality("test-session-id", mock_db)

        no_detection_warning = next(w for w in warnings if w['code'] == 'NO_DETECTIONS')
        assert 'recommendation' in no_detection_warning
        assert len(no_detection_warning['recommendation']) > 0

    def test_all_warnings_have_required_fields(self):
        """Test all warnings include required fields"""
        mock_db = Mock(spec=Session)
        total_query = MagicMock()
        total_query.filter.return_value.count.return_value = 100
        validated_query = MagicMock()
        validated_query.filter.return_value.filter.return_value.count.return_value = 40
        mock_db.query.side_effect = [total_query, validated_query, MagicMock()]

        warnings = QualityWarning.check_session_quality("test-session-id", mock_db)

        for warning in warnings:
            assert 'severity' in warning
            assert 'code' in warning
            assert 'message' in warning
            assert 'impact' in warning
            assert 'recommendation' in warning


class TestConvenienceFunctions:
    """Test convenience wrapper functions"""

    def test_check_quality_wrapper_works(self):
        """Test check_quality() convenience function"""
        with patch.object(QualityWarning, 'check_session_quality') as mock_check:
            mock_check.return_value = [{'severity': 'INFO'}]

            result = check_quality("test-session-id")

            mock_check.assert_called_once()
            assert len(result) == 1

    def test_get_quality_stats_wrapper_works(self):
        """Test get_quality_stats() convenience function"""
        with patch.object(QualityWarning, 'get_quality_statistics') as mock_stats:
            mock_stats.return_value = {'total_detections': 100}

            result = get_quality_stats("test-session-id")

            mock_stats.assert_called_once()
            assert result['total_detections'] == 100


class TestErrorHandling:
    """Test error handling in quality checks"""

    def test_database_error_returns_error_warning(self):
        """Test that database errors are handled gracefully"""
        mock_db = Mock(spec=Session)
        mock_db.query.side_effect = Exception("Database connection failed")

        warnings = QualityWarning.check_session_quality("test-session-id", mock_db)

        # Should return error warning, not crash
        assert len(warnings) >= 1
        assert any(w['code'] == 'QUALITY_CHECK_FAILED' for w in warnings)

    def test_missing_session_handled_gracefully(self):
        """Test that missing session doesn't crash quality check"""
        mock_db = Mock(spec=Session)

        total_query = MagicMock()
        total_query.filter.return_value.count.return_value = 100
        validated_query = MagicMock()
        validated_query.filter.return_value.filter.return_value.count.return_value = 80

        # Session query returns None
        session_query = MagicMock()
        session_query.filter.return_value.first.return_value = None

        mock_db.query.side_effect = [total_query, validated_query, session_query]

        # Should not crash
        warnings = QualityWarning.check_session_quality("test-session-id", mock_db)
        assert isinstance(warnings, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
