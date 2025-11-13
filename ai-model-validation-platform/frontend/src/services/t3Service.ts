// Lightweight T3 YOLO detection service helpers for frontend
// Provides functions to start/stop T3 sessions, fetch stats/alerts, and open WebSocket

import { getServiceConfig } from '../utils/envConfig';

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

const FALLBACK_API_BASE = 'http://localhost:8000';

const getApiBaseUrl = (): string => {
  try {
    const apiConfig = getServiceConfig('api');
    if (apiConfig && typeof apiConfig.url === 'string' && apiConfig.url.length > 0) {
      return apiConfig.url;
    }
  } catch (error) {
    console.warn('t3Service: failed to resolve API base from envConfig, falling back to runtime config.', error);
  }

  if (typeof window !== 'undefined') {
    const runtimeConfig = (window as any)?.RUNTIME_CONFIG;
    if (runtimeConfig && typeof runtimeConfig.REACT_APP_API_URL === 'string' && runtimeConfig.REACT_APP_API_URL.length > 0) {
      return runtimeConfig.REACT_APP_API_URL;
    }
    return window.location.origin;
  }

  return FALLBACK_API_BASE;
};

const buildT3Url = (path: string): string => {
  const baseUrl = getApiBaseUrl();
  return new URL(path, baseUrl).toString();
};

const buildAuthHeaders = (): HeadersInit => {
  const headers: Record<string, string> = {};

  try {
    if (typeof window !== 'undefined') {
      const runtimeToken = (window as any)?.RUNTIME_CONFIG?.REACT_APP_API_TOKEN;
      const envToken = process.env.REACT_APP_API_TOKEN;
      const storedToken = window.localStorage?.getItem('api_token') || window.localStorage?.getItem('access_token');

      const token = runtimeToken || envToken || storedToken;
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
    } else if (process.env.REACT_APP_API_TOKEN) {
      headers.Authorization = `Bearer ${process.env.REACT_APP_API_TOKEN}`;
    }
  } catch (error) {
    console.warn('t3Service: unable to resolve auth token', error);
  }

  return headers;
};

const fetchWithAuth = async (input: RequestInfo | URL, init: RequestInit = {}) => {
  const headers = {
    ...buildAuthHeaders(),
    ...(init.headers as Record<string, string> | undefined)
  };

  return fetch(input, {
    ...init,
    headers,
    credentials: init.credentials ?? 'include'
  });
};

export async function startT3Session(sessionId: string, videoPath: string, videoId?: string) {
  const url = new URL(`/api/t3/${encodeURIComponent(sessionId)}/start`, getApiBaseUrl());
  url.searchParams.set('video_path', videoPath);
  if (videoId) url.searchParams.set('video_id', videoId);
  url.searchParams.set('enable_coordination', 'true');
  const res = await fetchWithAuth(url.toString(), { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to start T3: ${res.status}`);
  return (await res.json()) as T3StartResponse;
}

export async function stopT3Session(sessionId: string) {
  const res = await fetchWithAuth(buildT3Url(`/api/t3/${encodeURIComponent(sessionId)}/stop`), { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to stop T3: ${res.status}`);
  return await res.json();
}

export async function getT3Stats(sessionId: string): Promise<T3StatsResponse> {
  const url = buildT3Url(`/api/t3/${encodeURIComponent(sessionId)}/stats`);
  const res = await fetchWithAuth(url);
  if (!res.ok) throw new Error(`Failed to fetch T3 stats: ${res.status}`);
  return await res.json();
}

export async function getT3Alerts(sessionId: string): Promise<T3AlertsResponse> {
  const url = buildT3Url(`/api/t3/${encodeURIComponent(sessionId)}/alerts`);
  const res = await fetchWithAuth(url);
  if (!res.ok) throw new Error(`Failed to fetch T3 alerts: ${res.status}`);
  return await res.json();
}

export function openT3WebSocket(sessionId: string): WebSocket {
  const streamUrl = new URL(`/api/t3/${encodeURIComponent(sessionId)}/stream`, getApiBaseUrl());
  streamUrl.protocol = streamUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  return new WebSocket(streamUrl.toString());
}

export async function getT3Pipeline(sessionId: string, limit = 2000) {
  const url = new URL(`/api/t3/${encodeURIComponent(sessionId)}/pipeline`, getApiBaseUrl());
  url.searchParams.set('limit', String(limit));
  const res = await fetchWithAuth(url.toString());
  if (!res.ok) throw new Error(`Failed to fetch T3 pipeline: ${res.status}`);
  return await res.json();
}
