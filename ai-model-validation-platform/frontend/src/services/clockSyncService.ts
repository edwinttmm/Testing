/**
 * Clock Synchronization Service
 *
 * Implements NTP-style clock synchronization between client and server
 * to prevent timestamp mismatches in video playback and LabJack correlation.
 *
 * Algorithm:
 * 1. Client records t0 (time before request)
 * 2. Server responds with server_time_ms
 * 3. Client records t1 (time after response)
 * 4. RTT = t1 - t0
 * 5. offset_ms = server_time_ms - (client_time + RTT/2)
 *
 * Critical for:
 * - Video playback timing accuracy
 * - LabJack event correlation
 * - Ground truth matching within tolerance windows
 *
 * Maximum acceptable drift: 5000ms (5 seconds)
 */

interface ClockSyncResponse {
  server_time_ms: number;
  server_time_ns: number;
  timestamp: string;
}

interface SyncMetrics {
  offset_ms: number;
  rtt_ms: number;
  server_time_ms: number;
  client_time_ms: number;
  synced_at: number;
}

class ClockSyncService {
  private offset_ms: number = 0;
  private last_sync_time: number = 0;
  private sync_interval_ms: number = 60000; // Re-sync every 60 seconds
  private max_drift_ms: number = 5000; // 5 second maximum drift
  private metrics: SyncMetrics | null = null;

  /**
   * Synchronize client clock with server.
   *
   * @returns Calculated time offset in milliseconds
   * @throws Error if synchronization fails
   */
  async synchronize(): Promise<number> {
    try {
      // Record client time before request
      const t0 = performance.now();
      const client_time_before = Date.now();

      // Request server time
      const response = await fetch('/api/clock-sync');

      if (!response.ok) {
        throw new Error(`Clock sync failed: HTTP ${response.status}`);
      }

      // Record client time after response
      const t1 = performance.now();
      const client_time_after = Date.now();

      const data: ClockSyncResponse = await response.json();
      const server_time_ms = data.server_time_ms;

      // Calculate round-trip time
      const rtt_ms = t1 - t0;

      // Calculate client time at midpoint of request
      const client_time_ms = client_time_before + (rtt_ms / 2);

      // Calculate offset: server_time - client_time
      this.offset_ms = server_time_ms - client_time_ms;
      this.last_sync_time = Date.now();

      // Store metrics for diagnostics
      this.metrics = {
        offset_ms: this.offset_ms,
        rtt_ms,
        server_time_ms,
        client_time_ms,
        synced_at: this.last_sync_time
      };

      console.log(`Clock synchronized. Offset: ${this.offset_ms.toFixed(2)}ms, RTT: ${rtt_ms.toFixed(2)}ms`);

      // Warn if drift is significant
      if (Math.abs(this.offset_ms) > this.max_drift_ms) {
        console.warn(
          `WARNING: Clock drift (${this.offset_ms.toFixed(2)}ms) exceeds maximum (${this.max_drift_ms}ms). ` +
          `This may cause timestamp correlation failures.`
        );
      }

      return this.offset_ms;
    } catch (error) {
      console.error('Clock synchronization failed:', error);
      throw error;
    }
  }

  /**
   * Get synchronized time in milliseconds since epoch.
   *
   * @returns Server-synchronized timestamp
   */
  getSynchronizedTime(): number {
    return Date.now() + this.offset_ms;
  }

  /**
   * Check if clock needs re-synchronization.
   *
   * @returns true if sync is stale
   */
  needsResync(): boolean {
    return (Date.now() - this.last_sync_time) > this.sync_interval_ms;
  }

  /**
   * Get current synchronization metrics.
   *
   * @returns Sync metrics or null if not synchronized
   */
  getMetrics(): SyncMetrics | null {
    return this.metrics;
  }

  /**
   * Get current time offset.
   *
   * @returns Offset in milliseconds
   */
  getOffset(): number {
    return this.offset_ms;
  }

  /**
   * Check if clock drift is within acceptable tolerance.
   *
   * @returns true if drift is acceptable
   */
  isDriftAcceptable(): boolean {
    return Math.abs(this.offset_ms) <= this.max_drift_ms;
  }

  /**
   * Auto-sync if needed (non-blocking).
   * Use before critical operations like video playback start.
   */
  async autoSyncIfNeeded(): Promise<void> {
    if (this.needsResync()) {
      try {
        await this.synchronize();
      } catch (error) {
        console.error('Auto-sync failed:', error);
        // Don't throw - use existing offset
      }
    }
  }
}

// Export singleton instance
export const clockSyncService = new ClockSyncService();
