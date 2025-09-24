// Lightweight T3 YOLO detection service helpers for frontend
// Provides functions to start/stop T3 sessions, fetch stats/alerts, and open WebSocket

export interface T3StartResponse {
  session_id: string;
  status: string;
  websocket_url?: string;
  started_at: string;
}

export interface T3StatsResponse {
  session_id: string;
  t3_pipeline_stats: any;
  video_monitoring_stats?: any;
  database_stats?: any;
  alerts?: {
    t3_pipeline: any[];
    video_monitor: any[];
    database: any[];
  };
  timestamp: string;
}

export interface T3AlertsResponse {
  session_id: string;
  alerts: {
    t3_pipeline: any[];
    video_monitor: any[];
    database: any[];
  };
  timestamp: string;
}

export async function startT3Session(sessionId: string, videoPath: string, videoId?: string) {
  const url = new URL(`/api/t3/${encodeURIComponent(sessionId)}/start`, window.location.origin);
  url.searchParams.set('video_path', videoPath);
  if (videoId) url.searchParams.set('video_id', videoId);
  url.searchParams.set('enable_coordination', 'true');
  const res = await fetch(url.toString(), { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to start T3: ${res.status}`);
  return (await res.json()) as T3StartResponse;
}

export async function stopT3Session(sessionId: string) {
  const res = await fetch(`/api/t3/${encodeURIComponent(sessionId)}/stop`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to stop T3: ${res.status}`);
  return await res.json();
}

export async function getT3Stats(sessionId: string): Promise<T3StatsResponse> {
  const url = `/api/t3/${encodeURIComponent(sessionId)}/stats`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch T3 stats: ${res.status}`);
  return await res.json();
}

export async function getT3Alerts(sessionId: string): Promise<T3AlertsResponse> {
  const url = `/api/t3/${encodeURIComponent(sessionId)}/alerts`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch T3 alerts: ${res.status}`);
  return await res.json();
}

export function openT3WebSocket(sessionId: string): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${protocol}://${window.location.host}/api/t3/${encodeURIComponent(sessionId)}/stream`;
  return new WebSocket(wsUrl);
}

export async function getT3Pipeline(sessionId: string, limit = 50) {
  const url = new URL(`/api/t3/${encodeURIComponent(sessionId)}/pipeline`, window.location.origin);
  url.searchParams.set('limit', String(limit));
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Failed to fetch T3 pipeline: ${res.status}`);
  return await res.json();
}
