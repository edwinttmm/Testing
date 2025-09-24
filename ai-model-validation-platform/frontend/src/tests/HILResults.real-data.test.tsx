/**
 * HIL Results Real Data Testing Suite
 * 
 * This test suite validates the HIL Results page with real backend data,
 * focusing on:
 * - Real ground truth data loading and display
 * - Accurate latency calculations with actual detection events
 * - Timeline functionality with real timestamps
 * - Detection matching logic validation
 * - Error handling and edge cases
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import HILResults from '../pages/HILResults';
import { apiService } from '../services/api';

// Mock dependencies
jest.mock('../services/api');
const mockApiService = apiService as jest.Mocked<typeof apiService>;

// Mock router params
const mockParams = { sessionId: '2c378820-887d-41b7-8b6f-c3a529e1d7ac' };
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useParams: () => mockParams,
  useNavigate: () => jest.fn()
}));

// Real test data based on actual database content
const REAL_TEST_SESSION_ID = '2c378820-887d-41b7-8b6f-c3a529e1d7ac';

const REAL_DETECTION_EVENTS = [
  {
    id: "31756c67-4ecb-4af6-8fdc-4f0c5349f080",
    timestamp: 1758205264.710978,
    voltage: 3.5319924354553223,
    channel: "AIN0",
    video_frame: 36,
    video_timestamp: 1.511228084564209,
    detection_type: "voltage",
    validation_result: "PENDING",
    timing_quality: "high",
    frame_number: 36,
    latency_ms: 1511.228084564209,
    raw_timestamp: 1758205264.710978
  },
  {
    id: "94e7de10-d7d2-44d3-88c7-9da6fa75e391",
    timestamp: 1758205264.76517,
    voltage: 4.239562034606934,
    channel: "AIN0",
    video_frame: 37,
    video_timestamp: 1.565420150756836,
    detection_type: "voltage",
    validation_result: "PENDING",
    timing_quality: "high",
    frame_number: 37,
    latency_ms: 1565.420150756836,
    raw_timestamp: 1758205264.76517
  },
  {
    id: "c5395b2e-ab1a-40f3-b158-d33ccff36d39",
    timestamp: 1758205264.881278,
    voltage: 4.200449466705322,
    channel: "AIN0",
    video_frame: 40,
    video_timestamp: 1.681528091430664,
    detection_type: "voltage",
    validation_result: "PENDING",
    timing_quality: "high",
    frame_number: 40,
    latency_ms: 1681.528091430664,
    raw_timestamp: 1758205264.881278
  }
];

const REAL_HIL_RESULTS = {
  session_id: REAL_TEST_SESSION_ID,
  test_session_id: REAL_TEST_SESSION_ID,
  validation_type: "latency_based",
  total_detections: 107,
  passed_detections: 107,
  failed_detections: 0,
  pass_rate: 100.0,
  status: "completed",
  session_info: {
    project_name: "HIL Test Project",
    operator: "System",
    start_time: "2025-09-18T14:21:03Z",
    end_time: "2025-09-18T14:21:09Z",
    duration_seconds: 6.17
  },
  latency_stats: {
    average_ms: 0.0,
    min_ms: 0.0,
    max_ms: 0.0,
    median_ms: 0.0,
    std_dev_ms: 0.0,
    threshold_ms: 100
  },
  latency_distribution: [],
  hardware_status: {
    labjack_connected: true,
    model: "T7",
    serial_number: "TEST123",
    firmware_version: "1.0285",
    sampling_rate_hz: 1000,
    active_channels: ["AIN0", "AIN1"]
  },
  detection_events: REAL_DETECTION_EVENTS.map(event => ({
    event_id: event.id,
    frame_number: event.frame_number,
    timestamp: new Date(event.timestamp * 1000).toISOString(),
    detection_time: new Date(event.timestamp * 1000).toISOString(),
    labjack_trigger_time: new Date(event.timestamp * 1000).toISOString(),
    latency_ms: event.latency_ms,
    latency_ns: event.latency_ms * 1000000,
    voltage_level: event.voltage,
    channel: event.channel,
    result: event.voltage >= 2.5 ? "pass" : "fail",
    error_message: event.voltage >= 2.5 ? null : "Voltage below threshold",
    session_id: REAL_TEST_SESSION_ID
  }))
};

// Ground truth events for Child.mp4 (based on actual annotations)
const GROUND_TRUTH_EVENTS = [
  { time: 0.21, frame: 5, label: 'Child/Pedestrian' },
  { time: 0.42, frame: 10, label: 'Child/Pedestrian' },
  { time: 0.62, frame: 15, label: 'Child/Pedestrian' },
  { time: 0.83, frame: 20, label: 'Child/Pedestrian' },
  { time: 1.04, frame: 25, label: 'Child/Pedestrian' },
  { time: 1.25, frame: 30, label: 'Child/Pedestrian' },
  { time: 1.46, frame: 35, label: 'Child/Pedestrian' },
  { time: 1.67, frame: 40, label: 'Child/Pedestrian' },
  { time: 1.88, frame: 45, label: 'Child/Pedestrian' },
  { time: 2.08, frame: 50, label: 'Child/Pedestrian' },
  { time: 2.29, frame: 55, label: 'Child/Pedestrian' },
  { time: 2.50, frame: 60, label: 'Child/Pedestrian' },
  { time: 2.71, frame: 65, label: 'Child/Pedestrian' },
  { time: 2.92, frame: 70, label: 'Child/Pedestrian' },
  { time: 3.13, frame: 75, label: 'Child/Pedestrian' },
  { time: 3.33, frame: 80, label: 'Child/Pedestrian' },
  { time: 3.54, frame: 85, label: 'Child/Pedestrian' },
  { time: 3.75, frame: 90, label: 'Child/Pedestrian' },
  { time: 3.96, frame: 95, label: 'Child/Pedestrian' },
  { time: 4.17, frame: 100, label: 'Child/Pedestrian' },
  { time: 4.38, frame: 105, label: 'Child/Pedestrian' },
  { time: 4.58, frame: 110, label: 'Child/Pedestrian' },
  { time: 4.79, frame: 115, label: 'Child/Pedestrian' },
  { time: 5.00, frame: 120, label: 'Child/Pedestrian' }
];

describe('HIL Results - Real Data Integration Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock successful test session fetch
    mockApiService.getTestSession.mockResolvedValue({
      id: REAL_TEST_SESSION_ID,
      name: 'HIL Test 18/09/2025, 15:21:03',
      createdAt: '2025-09-18T14:21:03Z',
      projectName: 'HIL Test Project'
    });
  });

  const renderHILResults = () => {
    return render(
      <BrowserRouter>
        <HILResults />
      </BrowserRouter>
    );
  };

  describe('Real Ground Truth Data Loading', () => {
    test('should load and display real HIL results with detection events', async () => {
      // Mock HIL results API response
      mockApiService.get.mockImplementation((url: string) => {
        if (url.includes('/results')) {
          return Promise.resolve(REAL_HIL_RESULTS);
        }
        if (url.includes('/events')) {
          return Promise.resolve(REAL_DETECTION_EVENTS);
        }
        return Promise.resolve({});
      });

      renderHILResults();

      // Wait for data to load
      await waitFor(() => {
        expect(screen.getByText('HIL Test Results')).toBeInTheDocument();
      });

      // Verify session information is displayed
      expect(screen.getByText(/HIL Test 18\/09\/2025, 15:21:03/)).toBeInTheDocument();
      expect(screen.getByText(/HIL Test Project/)).toBeInTheDocument();

      // Verify detection count
      await waitFor(() => {
        expect(screen.getByText('107')).toBeInTheDocument(); // Total detections
      });

      // Verify hardware status
      expect(screen.getByText(/LabJack: T7/)).toBeInTheDocument();
      expect(screen.getByText(/Connected: Yes/)).toBeInTheDocument();
    });

    test('should handle real voltage detection events correctly', async () => {
      mockApiService.get.mockImplementation((url: string) => {
        if (url.includes('/results')) {
          return Promise.resolve(REAL_HIL_RESULTS);
        }
        if (url.includes('/events')) {
          return Promise.resolve(REAL_DETECTION_EVENTS);
        }
        return Promise.resolve({});
      });

      renderHILResults();

      await waitFor(() => {
        expect(screen.getByText('HIL Test Results')).toBeInTheDocument();
      });

      // Check voltage values are displayed
      await waitFor(() => {
        expect(screen.getByText(/3\.53V/)).toBeInTheDocument(); // First event voltage
        expect(screen.getByText(/4\.24V/)).toBeInTheDocument(); // Second event voltage
      });

      // Verify channel information
      expect(screen.getByText(/AIN0/)).toBeInTheDocument();
    });

    test('should calculate latency correctly with real timestamps', async () => {
      mockApiService.get.mockImplementation((url: string) => {
        if (url.includes('/results')) {
          return Promise.resolve(REAL_HIL_RESULTS);
        }
        if (url.includes('/events')) {
          return Promise.resolve(REAL_DETECTION_EVENTS);
        }
        return Promise.resolve({});
      });

      renderHILResults();

      await waitFor(() => {
        expect(screen.getByText('HIL Test Results')).toBeInTheDocument();
      });

      // Verify timing calculations are shown
      await waitFor(() => {
        // Check for latency values in the timeline
        expect(screen.getByText(/System Delay:/)).toBeInTheDocument();
        expect(screen.getByText(/ms/)).toBeInTheDocument();
      });
    });
  });

  describe('Timeline Display with Real Events', () => {
    test('should display ground truth events in timeline', async () => {
      mockApiService.get.mockResolvedValue(REAL_HIL_RESULTS);

      renderHILResults();

      await waitFor(() => {
        expect(screen.getByText('HIL Test Results')).toBeInTheDocument();
      });

      // Verify ground truth events are shown
      await waitFor(() => {
        expect(screen.getByText(/Expected Ground Truth Events/)).toBeInTheDocument();
        expect(screen.getByText(/24 Child Detections/)).toBeInTheDocument();
      });

      // Check for specific ground truth timestamps
      expect(screen.getByText(/GT: 0.21s/)).toBeInTheDocument();
      expect(screen.getByText(/GT: 0.42s/)).toBeInTheDocument();
    });

    test('should show combined timeline with ground truth and detections', async () => {
      mockApiService.get.mockResolvedValue(REAL_HIL_RESULTS);

      renderHILResults();

      await waitFor(() => {
        expect(screen.getByText('HIL Test Results')).toBeInTheDocument();
      });

      // Verify combined timeline is displayed
      await waitFor(() => {
        expect(screen.getByText(/Combined Timeline: Ground Truth vs LabJack Detections/)).toBeInTheDocument();
      });

      // Check timeline shows both event types
      expect(screen.getByText('GROUND TRUTH')).toBeInTheDocument();
      expect(screen.getByText('LABJACK')).toBeInTheDocument();
    });

    test('should calculate detection timing relative to ground truth', async () => {
      mockApiService.get.mockResolvedValue(REAL_HIL_RESULTS);

      renderHILResults();

      await waitFor(() => {
        expect(screen.getByText('HIL Test Results')).toBeInTheDocument();
      });

      // Check timing analysis metrics
      await waitFor(() => {
        expect(screen.getByText(/First GT Event:/)).toBeInTheDocument();
        expect(screen.getByText(/First LabJack Detection:/)).toBeInTheDocument();
        expect(screen.getByText(/Detection Latency:/)).toBeInTheDocument();
      });
    });
  });

  describe('Detection Matching Logic', () => {
    test('should correctly match detection events to ground truth', async () => {
      mockApiService.get.mockResolvedValue(REAL_HIL_RESULTS);

      renderHILResults();

      await waitFor(() => {
        expect(screen.getByText('HIL Test Results')).toBeInTheDocument();
      });

      // Verify matching logic results
      await waitFor(() => {
        expect(screen.getByText(/TIMING MISMATCH/)).toBeInTheDocument();
        expect(screen.getByText(/None of these 24 ground truth events match/)).toBeInTheDocument();
      });

      // Check that false positives and negatives are calculated
      expect(screen.getByText(/False Positives:/)).toBeInTheDocument();
      expect(screen.getByText(/False Negatives:/)).toBeInTheDocument();
    });

    test('should handle voltage threshold validation', async () => {
      const eventsWithLowVoltage = [
        ...REAL_DETECTION_EVENTS,
        {
          ...REAL_DETECTION_EVENTS[0],
          id: "low-voltage-event",
          voltage: 2.0, // Below 2.5V threshold
          validation_result: "FAIL"
        }
      ];

      const resultsWithFailures = {
        ...REAL_HIL_RESULTS,
        detection_events: [
          ...REAL_HIL_RESULTS.detection_events,
          {
            event_id: "low-voltage-event",
            frame_number: 50,
            timestamp: new Date().toISOString(),
            voltage_level: 2.0,
            channel: "AIN0",
            result: "fail",
            error_message: "Voltage below threshold"
          }
        ]
      };

      mockApiService.get.mockResolvedValue(resultsWithFailures);

      renderHILResults();

      await waitFor(() => {
        expect(screen.getByText('HIL Test Results')).toBeInTheDocument();
      });

      // Check voltage validation is applied
      await waitFor(() => {
        expect(screen.getByText(/2\.00V/)).toBeInTheDocument();
        expect(screen.getByText(/Voltage below threshold/)).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling and Edge Cases', () => {
    test('should handle API failure gracefully', async () => {
      mockApiService.get.mockRejectedValue(new Error('API Error'));
      mockApiService.getTestSession.mockRejectedValue(new Error('Session not found'));

      renderHILResults();

      await waitFor(() => {
        expect(screen.getByText(/Failed to Load HIL Results/)).toBeInTheDocument();
      });

      // Should show retry button
      expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
    });

    test('should handle empty detection events', async () => {
      const emptyResults = {
        ...REAL_HIL_RESULTS,
        total_detections: 0,
        detection_events: []
      };

      mockApiService.get.mockResolvedValue(emptyResults);

      renderHILResults();

      await waitFor(() => {
        expect(screen.getByText('HIL Test Results')).toBeInTheDocument();
      });

      // Should show zero detections
      await waitFor(() => {
        expect(screen.getByText('0')).toBeInTheDocument(); // Zero detections
      });

      // Should show appropriate message for no events
      expect(screen.getByText(/No detection events available/)).toBeInTheDocument();
    });

    test('should handle malformed detection event data', async () => {
      const malformedResults = {
        ...REAL_HIL_RESULTS,
        detection_events: [
          {
            event_id: "malformed",
            // Missing required fields
            timestamp: null,
            voltage_level: null,
            frame_number: null
          }
        ]
      };

      mockApiService.get.mockResolvedValue(malformedResults);

      renderHILResults();

      await waitFor(() => {
        expect(screen.getByText('HIL Test Results')).toBeInTheDocument();
      });

      // Should handle missing data gracefully
      expect(screen.queryByText(/Error:/)).not.toBeInTheDocument();
    });
  });

  describe('Performance and Large Datasets', () => {
    test('should handle large number of detection events efficiently', async () => {
      // Create a large dataset
      const largeEventSet = Array.from({ length: 1000 }, (_, index) => ({
        ...REAL_DETECTION_EVENTS[0],
        id: `event-${index}`,
        timestamp: 1758205264.710978 + (index * 0.1),
        frame_number: index,
        voltage: 3.5 + (Math.random() * 1.5) // 3.5-5.0V range
      }));

      const largeResults = {
        ...REAL_HIL_RESULTS,
        total_detections: 1000,
        detection_events: largeEventSet.map((event, index) => ({
          event_id: event.id,
          frame_number: event.frame_number,
          timestamp: new Date(event.timestamp * 1000).toISOString(),
          voltage_level: event.voltage,
          channel: "AIN0",
          result: "pass"
        }))
      };

      mockApiService.get.mockResolvedValue(largeResults);

      const startTime = performance.now();
      renderHILResults();

      await waitFor(() => {
        expect(screen.getByText('HIL Test Results')).toBeInTheDocument();
      });

      const renderTime = performance.now() - startTime;

      // Should render within reasonable time (less than 2 seconds)
      expect(renderTime).toBeLessThan(2000);

      // Should show correct total
      await waitFor(() => {
        expect(screen.getByText('1000')).toBeInTheDocument();
      });
    });
  });

  describe('User Interactions', () => {
    test('should allow refreshing HIL results', async () => {
      mockApiService.get.mockResolvedValue(REAL_HIL_RESULTS);

      renderHILResults();

      await waitFor(() => {
        expect(screen.getByText('HIL Test Results')).toBeInTheDocument();
      });

      const refreshButton = screen.getByRole('button', { name: /Refresh/i });
      
      // Clear mocks to verify refresh calls API again
      jest.clearAllMocks();
      mockApiService.get.mockResolvedValue(REAL_HIL_RESULTS);

      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(mockApiService.get).toHaveBeenCalled();
      });
    });

    test('should allow computing results', async () => {
      mockApiService.get.mockResolvedValue(REAL_HIL_RESULTS);

      // Mock fetch for compute endpoint
      global.fetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: {
            results: {
              total_detections: 107,
              true_positives: 24,
              false_positives: 83,
              mean_latency_ms: 45.2
            }
          }
        }),
        headers: {
          get: () => 'application/json'
        }
      }) as jest.Mock;

      renderHILResults();

      await waitFor(() => {
        expect(screen.getByText('HIL Test Results')).toBeInTheDocument();
      });

      const computeButton = screen.getByRole('button', { name: /Compute Results/i });
      fireEvent.click(computeButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/compute-and-fetch'),
          expect.objectContaining({
            method: 'POST'
          })
        );
      });
    });
  });
});

export {};