/**
 * Real-time drift visualization component
 * Shows synchronization status and timing drift for each video
 */

import React, { useEffect, useState } from 'react';
import type { DriftStatus } from '../types/timing.types';
import type { TimingService } from '../services/timingService';

interface DriftMonitorProps {
  timingService: TimingService;
  videoIds: string[];
}

interface ClockSyncStatus {
  offset: number;
  isHealthy: boolean;
  lastSyncAgo: number;
  rtt: number;
  accuracy: number;
}

export const DriftMonitor: React.FC<DriftMonitorProps> = ({ timingService, videoIds }) => {
  const [driftStatuses, setDriftStatuses] = useState<Map<string, DriftStatus>>(new Map());
  const [clockSync, setClockSync] = useState<ClockSyncStatus | null>(null);
  const [wsLatency, setWsLatency] = useState<number>(0);

  useEffect(() => {
    // Update drift statuses every 100ms
    const intervalId = setInterval(() => {
      updateStatuses();
    }, 100);

    return () => clearInterval(intervalId);
  }, [timingService, videoIds]);

  const updateStatuses = () => {
    // Update clock sync status
    const syncStatus = timingService.getClockSyncStatus();
    if (syncStatus.latestSync) {
      const now = performance.now() + performance.timeOrigin;
      setClockSync({
        offset: syncStatus.offset,
        isHealthy: syncStatus.isHealthy,
        lastSyncAgo: now - syncStatus.latestSync.calculatedAt,
        rtt: syncStatus.latestSync.rtt,
        accuracy: syncStatus.latestSync.accuracy,
      });
    }

    // Update WebSocket latency
    setWsLatency(timingService.getWebSocketLatency());

    // Update video drift statuses
    const newStatuses = new Map<string, DriftStatus>();
    videoIds.forEach(videoId => {
      // In real implementation, this would come from backend comparison
      // For now, we show clock offset as proxy for drift
      const offset = syncStatus.offset;
      const severity = getSeverity(Math.abs(offset));

      newStatuses.set(videoId, {
        videoId,
        drift: offset,
        severity,
        clockOffset: offset,
        compensated: syncStatus.isHealthy,
        lastUpdate: Date.now(),
      });
    });

    setDriftStatuses(newStatuses);
  };

  const getSeverity = (drift: number): 'good' | 'warning' | 'critical' => {
    if (drift < 50) return 'good';
    if (drift < 200) return 'warning';
    return 'critical';
  };

  const getSeverityColor = (severity: 'good' | 'warning' | 'critical'): string => {
    switch (severity) {
      case 'good': return '#10b981'; // green
      case 'warning': return '#f59e0b'; // yellow
      case 'critical': return '#ef4444'; // red
    }
  };

  const getSeverityBackground = (severity: 'good' | 'warning' | 'critical'): string => {
    switch (severity) {
      case 'good': return '#d1fae5';
      case 'warning': return '#fef3c7';
      case 'critical': return '#fee2e2';
    }
  };

  return (
    <div style={styles.container}>
      <h3 style={styles.title}>⏱️ Timing & Drift Monitor</h3>

      {/* Clock Sync Status */}
      <div style={styles.section}>
        <h4 style={styles.sectionTitle}>Clock Synchronization</h4>
        {clockSync ? (
          <div style={styles.syncGrid}>
            <div style={styles.syncItem}>
              <span style={styles.label}>Status:</span>
              <span style={{
                ...styles.value,
                color: clockSync.isHealthy ? '#10b981' : '#ef4444'
              }}>
                {clockSync.isHealthy ? '✓ Healthy' : '✗ Unhealthy'}
              </span>
            </div>
            <div style={styles.syncItem}>
              <span style={styles.label}>Offset:</span>
              <span style={styles.value}>{clockSync.offset.toFixed(3)} ms</span>
            </div>
            <div style={styles.syncItem}>
              <span style={styles.label}>RTT:</span>
              <span style={styles.value}>{clockSync.rtt.toFixed(3)} ms</span>
            </div>
            <div style={styles.syncItem}>
              <span style={styles.label}>Accuracy:</span>
              <span style={styles.value}>±{clockSync.accuracy.toFixed(3)} ms</span>
            </div>
            <div style={styles.syncItem}>
              <span style={styles.label}>Last Sync:</span>
              <span style={styles.value}>{(clockSync.lastSyncAgo / 1000).toFixed(1)}s ago</span>
            </div>
            <div style={styles.syncItem}>
              <span style={styles.label}>WS Latency:</span>
              <span style={styles.value}>{wsLatency.toFixed(3)} ms</span>
            </div>
          </div>
        ) : (
          <div style={styles.loading}>Initializing clock sync...</div>
        )}
      </div>

      {/* Video Drift Status */}
      <div style={styles.section}>
        <h4 style={styles.sectionTitle}>Video Synchronization Status</h4>
        {videoIds.length === 0 ? (
          <div style={styles.noVideos}>No videos registered</div>
        ) : (
          <div style={styles.videoGrid}>
            {Array.from(driftStatuses.values()).map(status => (
              <div
                key={status.videoId}
                style={{
                  ...styles.videoCard,
                  backgroundColor: getSeverityBackground(status.severity),
                  borderColor: getSeverityColor(status.severity),
                }}
              >
                <div style={styles.videoHeader}>
                  <span style={styles.videoId}>{status.videoId}</span>
                  <span
                    style={{
                      ...styles.severityBadge,
                      backgroundColor: getSeverityColor(status.severity),
                    }}
                  >
                    {status.severity.toUpperCase()}
                  </span>
                </div>
                <div style={styles.videoStats}>
                  <div style={styles.stat}>
                    <span style={styles.statLabel}>Drift:</span>
                    <span style={styles.statValue}>
                      {status.drift >= 0 ? '+' : ''}{status.drift.toFixed(3)} ms
                    </span>
                  </div>
                  <div style={styles.stat}>
                    <span style={styles.statLabel}>Compensation:</span>
                    <span style={styles.statValue}>
                      {status.compensated ? '✓ Active' : '✗ Inactive'}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Legend */}
      <div style={styles.legend}>
        <div style={styles.legendTitle}>Severity Levels:</div>
        <div style={styles.legendItems}>
          <div style={styles.legendItem}>
            <div style={{ ...styles.legendColor, backgroundColor: '#10b981' }} />
            <span style={styles.legendText}>Good (&lt;50ms)</span>
          </div>
          <div style={styles.legendItem}>
            <div style={{ ...styles.legendColor, backgroundColor: '#f59e0b' }} />
            <span style={styles.legendText}>Warning (50-200ms)</span>
          </div>
          <div style={styles.legendItem}>
            <div style={{ ...styles.legendColor, backgroundColor: '#ef4444' }} />
            <span style={styles.legendText}>Critical (&gt;200ms)</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    padding: '20px',
    backgroundColor: '#f9fafb',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
    fontFamily: 'system-ui, -apple-system, sans-serif',
  },
  title: {
    margin: '0 0 20px 0',
    fontSize: '20px',
    fontWeight: '600',
    color: '#111827',
  },
  section: {
    marginBottom: '24px',
    padding: '16px',
    backgroundColor: '#ffffff',
    borderRadius: '6px',
    border: '1px solid #e5e7eb',
  },
  sectionTitle: {
    margin: '0 0 12px 0',
    fontSize: '16px',
    fontWeight: '600',
    color: '#374151',
  },
  syncGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '12px',
  },
  syncItem: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '8px 12px',
    backgroundColor: '#f9fafb',
    borderRadius: '4px',
  },
  label: {
    fontSize: '14px',
    color: '#6b7280',
    fontWeight: '500',
  },
  value: {
    fontSize: '14px',
    color: '#111827',
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  loading: {
    padding: '12px',
    textAlign: 'center',
    color: '#6b7280',
    fontSize: '14px',
  },
  noVideos: {
    padding: '12px',
    textAlign: 'center',
    color: '#6b7280',
    fontSize: '14px',
  },
  videoGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
    gap: '12px',
  },
  videoCard: {
    padding: '12px',
    borderRadius: '6px',
    border: '2px solid',
    transition: 'all 0.2s ease',
  },
  videoHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '8px',
  },
  videoId: {
    fontSize: '14px',
    fontWeight: '600',
    color: '#111827',
    fontFamily: 'monospace',
  },
  severityBadge: {
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: '700',
    color: '#ffffff',
    letterSpacing: '0.5px',
  },
  videoStats: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  stat: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '13px',
  },
  statLabel: {
    color: '#6b7280',
    fontWeight: '500',
  },
  statValue: {
    color: '#111827',
    fontWeight: '600',
    fontFamily: 'monospace',
  },
  legend: {
    marginTop: '20px',
    padding: '12px',
    backgroundColor: '#ffffff',
    borderRadius: '6px',
    border: '1px solid #e5e7eb',
  },
  legendTitle: {
    fontSize: '14px',
    fontWeight: '600',
    color: '#374151',
    marginBottom: '8px',
  },
  legendItems: {
    display: 'flex',
    gap: '16px',
    flexWrap: 'wrap',
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  legendColor: {
    width: '16px',
    height: '16px',
    borderRadius: '3px',
  },
  legendText: {
    fontSize: '13px',
    color: '#6b7280',
  },
};
