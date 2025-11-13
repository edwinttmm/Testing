import { normalizeSequenceResults } from '../hilResultsNormalization';

describe('hilResultsNormalization', () => {
  it('normalizes backend sequence results payload', () => {
    const raw = {
      sequence_id: 'seq-123',
      total_videos: 2,
      overall_pass_rate: 50,
      total_detections: 4,
      per_video_results: [
        {
          video_id: 'vid-1',
          video_name: 'Video 1',
          sequence_index: 0,
          video_url: '/uploads/video1.mp4',
          start_time: 0,
          end_time: 5,
          duration: 5,
          detection_count: 2,
          detection_events: [
            { id: 'det-1', timestamp: 1, result: 'pass', voltage: 2.1, active_video_id: 'vid-1' },
            { id: 'det-2', timestamp: 1.5, result: 'fail', voltage: 1.8, active_video_id: 'vid-1' }
          ],
          pass_fail: 'pass',
          metrics: {
            pass_rate_percent: 50,
            avg_latency_ms: 45,
            max_latency_ms: 80,
            min_latency_ms: 20,
            latency_threshold_ms: 120,
            expected_detection_count: 2
          }
        },
        {
          video_id: 'vid-2',
          video_name: 'Video 2',
          sequence_index: 1,
          start_time: 5,
          end_time: 10,
          duration: 5,
          detection_count: 2,
          detection_events: [],
          pass_fail: 'fail',
          metrics: {
            pass_rate_percent: 0,
            avg_latency_ms: 60,
            max_latency_ms: 130,
            min_latency_ms: 35
          }
        }
      ],
      aggregate_metrics: {
        max_latency_threshold_ms: 120
      }
    };

    const normalized = normalizeSequenceResults(raw);
    expect(normalized).not.toBeNull();
    expect(normalized?.sequence_id).toBe('seq-123');

    const videos = normalized?.per_video_results ?? [];
    expect(videos).toHaveLength(2);

    const firstVideo = videos[0];
    expect(firstVideo.video_id).toBe('vid-1');
    expect(firstVideo.duration_seconds).toBeCloseTo(5);
    expect(firstVideo.pass_rate_percent).toBeCloseTo(50);
    expect(firstVideo.latency_threshold_ms).toBeCloseTo(120);
    expect(firstVideo.detection_events).toHaveLength(2);
    expect(firstVideo.detection_events[0].result).toBe('pass');
    expect(firstVideo.detection_events[0].video_id).toBe('vid-1');
    expect(firstVideo.detection_events[0].videoId).toBe('vid-1');

    const sequenceSummary = normalized?.sequence_summary;
    expect(sequenceSummary).toBeDefined();
    expect(sequenceSummary?.total_videos).toBe(2);
    expect(sequenceSummary?.total_detections).toBe(4);
    expect(sequenceSummary?.overall_status).toBe('partial');
    expect(sequenceSummary?.sequence_duration_seconds).toBeCloseTo(10);
  });
});
