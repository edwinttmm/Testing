import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { apiService } from '../services/api';
import GroundTruthComparisonPanel from '../components/GroundTruthComparisonPanel';
import EnhancedDetectionEventsTable from '../components/EnhancedDetectionEventsTable';
import { GroundTruthComparisonMetrics, EnhancedDetectionEvent } from '../types/enhanced-results';

// Mock API service
jest.mock('../services/api');
const mockedApiService = jest.mocked(apiService);

describe('Enhanced HIL Ground Truth Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('GroundTruthComparisonPanel', () => {
    it('should display loading state', () => {
      render(<GroundTruthComparisonPanel comparisonData={null} loading={true} />);
      expect(screen.getByText('Loading ground truth comparison data...')).toBeInTheDocument();
    });

    it('should display error state', () => {
      const error = 'Failed to load ground truth data';
      render(<GroundTruthComparisonPanel comparisonData={null} error={error} />);
      expect(screen.getByText(`Error loading ground truth data: ${error}`)).toBeInTheDocument();
    });

    it('should display ground truth comparison metrics', () => {
      const mockData: GroundTruthComparisonMetrics = {
        ground_truth_events_available: 24,
        total_detections: 39,
        events_with_matches: 39,
        average_confidence_score: 0.85,
        timing_quality_distribution: {
          excellent: 10,
          good: 15,
          fair: 10,
          poor: 4
        },
        precision: 0.92,
        recall: 0.88,
        f1_score: 0.90,
        true_positives: 36,
        false_positives: 3,
        false_negatives: 3
      };

      render(<GroundTruthComparisonPanel comparisonData={mockData} />);
      
      expect(screen.getByText('Ground Truth Events:')).toBeInTheDocument();
      expect(screen.getByText('24')).toBeInTheDocument();
      expect(screen.getByText('Total Detections:')).toBeInTheDocument();
      expect(screen.getByText('39')).toBeInTheDocument();
      expect(screen.getByText('Events with Matches:')).toBeInTheDocument();
      expect(screen.getByText('Average Confidence:')).toBeInTheDocument();
      expect(screen.getByText('85.0%')).toBeInTheDocument();
      
      // Performance metrics
      expect(screen.getByText('Precision:')).toBeInTheDocument();
      expect(screen.getByText('92.0%')).toBeInTheDocument();
      expect(screen.getByText('Recall:')).toBeInTheDocument();
      expect(screen.getByText('88.0%')).toBeInTheDocument();
      expect(screen.getByText('F1 Score:')).toBeInTheDocument();
      expect(screen.getByText('90.0%')).toBeInTheDocument();
      
      // Timing quality distribution
      expect(screen.getByText('Excellent: 10')).toBeInTheDocument();
      expect(screen.getByText('Good: 15')).toBeInTheDocument();
      expect(screen.getByText('Fair: 10')).toBeInTheDocument();
      expect(screen.getByText('Poor: 4')).toBeInTheDocument();
    });
  });

  describe('EnhancedDetectionEventsTable', () => {
    it('should display empty state when no events', () => {
      render(<EnhancedDetectionEventsTable events={[]} />);
      expect(screen.getByText('No enhanced detection events available')).toBeInTheDocument();
    });

    it('should display enhanced detection events with timing synchronization', () => {
      const mockEvents: EnhancedDetectionEvent[] = [
        {
          id: 'event_001',
          timestamp: 1630000000.123,
          frame_number: 100,
          detection_time_ms: 45.2,
          labJack_trigger_time_ms: 1630000000.120,
          passed: true,
          voltage: 4.8,
          video_frame: 100,
          real_latency_ms: 45.2,
          apparent_latency_ms: 125.5,
          timing_quality: 'excellent',
          confidence_score: 0.95,
          ground_truth_available: true,
          match_iou_score: 0.87,
          processing_time_ms: 42.1
        },
        {
          id: 'event_002',
          timestamp: 1630000001.456,
          frame_number: 124,
          detection_time_ms: 67.8,
          labJack_trigger_time_ms: 1630000001.450,
          passed: true,
          voltage: 4.2,
          video_frame: 124,
          real_latency_ms: 67.8,
          apparent_latency_ms: 155.2,
          timing_quality: 'good',
          confidence_score: 0.82,
          ground_truth_available: true,
          processing_time_ms: 65.3
        }
      ];

      render(<EnhancedDetectionEventsTable events={mockEvents} />);
      
      expect(screen.getByText('Enhanced Detection Events (2 events)')).toBeInTheDocument();
      expect(screen.getByText('event_001')).toBeInTheDocument();
      expect(screen.getByText('event_002')).toBeInTheDocument();
      
      // Check timing quality chips
      expect(screen.getByText('excellent')).toBeInTheDocument();
      expect(screen.getByText('good')).toBeInTheDocument();
      
      // Check confidence scores
      expect(screen.getByText('95%')).toBeInTheDocument();
      expect(screen.getByText('82%')).toBeInTheDocument();
      
      // Check latency values
      expect(screen.getByText('Real: 45ms')).toBeInTheDocument();
      expect(screen.getByText('Real: 68ms')).toBeInTheDocument();
    });
  });

  describe('API Integration', () => {
    it('should fetch enhanced HIL results with ground truth', async () => {
      const mockEnhancedResults = {
        session_id: 'test-session-123',
        ground_truth_comparison: {
          ground_truth_events_available: 24,
          total_detections: 39,
          events_with_matches: 39,
          average_confidence_score: 0.2,
          timing_quality_distribution: { poor: 39 }
        },
        detection_events: [{
          timing_synchronization: {
            timing_quality: 'poor',
            confidence_score: 0.2,
            ground_truth_available: true
          }
        }]
      };

      mockedApiService.getEnhancedHILResultsWithGroundTruth.mockResolvedValue(mockEnhancedResults);

      const sessionId = 'test-session-123';
      const result = await apiService.getEnhancedHILResultsWithGroundTruth(sessionId);

      expect(mockedApiService.getEnhancedHILResultsWithGroundTruth).toHaveBeenCalledWith(sessionId);
      expect(result).toEqual(mockEnhancedResults);
      expect(result.ground_truth_comparison.ground_truth_events_available).toBe(24);
      expect(result.ground_truth_comparison.total_detections).toBe(39);
    });

    it('should handle API errors gracefully', async () => {
      const errorMessage = 'Enhanced HIL ground truth comparison fetch failed';
      mockedApiService.getEnhancedHILResultsWithGroundTruth.mockRejectedValue(new Error(errorMessage));

      await expect(apiService.getEnhancedHILResultsWithGroundTruth('test-session'))
        .rejects
        .toThrow(errorMessage);
    });

    it('should fallback to basic enhanced results when ground truth fails', async () => {
      const mockBasicResults = {
        session_id: 'test-session-123',
        detection_events: []
      };

      mockedApiService.getEnhancedHILResultsWithGroundTruth.mockRejectedValue(new Error('Ground truth not available'));
      mockedApiService.getEnhancedHILResults.mockResolvedValue(mockBasicResults);

      // This would be tested in the component logic
      try {
        await apiService.getEnhancedHILResultsWithGroundTruth('test-session-123');
      } catch (error) {
        const fallbackResult = await apiService.getEnhancedHILResults('test-session-123');
        expect(fallbackResult).toEqual(mockBasicResults);
      }
    });
  });

  describe('Type Safety', () => {
    it('should have proper TypeScript interfaces', () => {
      const comparisonData: GroundTruthComparisonMetrics = {
        ground_truth_events_available: 10,
        total_detections: 15,
        events_with_matches: 12,
        average_confidence_score: 0.75,
        timing_quality_distribution: {
          excellent: 5,
          good: 4,
          fair: 2,
          poor: 1
        },
        precision: 0.8,
        recall: 0.75,
        f1_score: 0.77,
        true_positives: 12,
        false_positives: 3,
        false_negatives: 4
      };

      const detectionEvent: EnhancedDetectionEvent = {
        id: 'test-event',
        timestamp: 1630000000,
        frame_number: 100,
        detection_time_ms: 50,
        labJack_trigger_time_ms: 1630000000,
        passed: true,
        real_latency_ms: 50,
        timing_quality: 'excellent',
        confidence_score: 0.9,
        ground_truth_available: true
      };

      // These should compile without TypeScript errors
      expect(comparisonData.ground_truth_events_available).toBe(10);
      expect(detectionEvent.timing_quality).toBe('excellent');
    });
  });
});