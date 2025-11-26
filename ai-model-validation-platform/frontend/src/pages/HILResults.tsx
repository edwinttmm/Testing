import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Container,
  Paper,
  AppBar,
  Toolbar,
  IconButton,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Alert,
  AlertTitle,
  Chip,
  Stack,
  Card,
  CardContent,
  Select,
  MenuItem,
  FormControl,
  Dialog,
  DialogTitle,
  DialogContent,
  Tooltip,
  Divider
} from '@mui/material';
import { ArrowBack as ArrowBackIcon, Close as CloseIcon, VideoLibrary as VideoLibraryIcon, Info as InfoIcon } from '@mui/icons-material';
import { apiService } from '../services/api';
import { EnhancedHILResults, VideoSequenceResults, EnhancedDetectionEvent, PerVideoResult } from '../types/enhanced-results';
import FrameCorrelationTimeline from '../components/FrameCorrelationTimeline';
import { TestStatusBanner } from '../components/TestStatusBanner';
import { MetricsSummaryCards } from '../components/MetricsSummaryCards';
import { DetectionTableRow } from '../components/DetectionTableRow';
import { GroundTruthComparisonCards } from '../components/GroundTruthComparisonCards';
import { ApprovalPanel } from '../components/ApprovalPanel';
import {
  collectDetectionCandidates,
  normalizeDetectionEvent,
  normalizeDetectionEvents,
  normalizeSequenceResults
} from '../utils/hilResultsNormalization';

type NumericLike = number | string | null | undefined;

const toNumber = (value: NumericLike, fallback = 0): number => {
  if (value == null) {
    return fallback;
  }
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const normalizeGroundTruthMetrics = (rawMetrics?: any | null) => {
  if (!rawMetrics) {
    return null;
  }

  const truePositives = toNumber(rawMetrics.true_positives ?? rawMetrics.truePositives);
  const falsePositives = toNumber(rawMetrics.false_positives ?? rawMetrics.falsePositives);
  const falseNegatives = toNumber(rawMetrics.false_negatives ?? rawMetrics.falseNegatives);
  // CRITICAL: ground_truth_events_available is the authoritative total from backend (e.g., 131)
  // total_ground_truth may sometimes be incorrectly set to matched count (e.g., 65)
  const totalGroundTruth = toNumber(
    rawMetrics.ground_truth_events_available ??
      rawMetrics.groundTruthEventsAvailable ??
      rawMetrics.total_ground_truth ??
      rawMetrics.totalGroundTruth ??
      rawMetrics.ground_truth_total ??
      rawMetrics.groundTruthTotal,
    0
  );

  const precision =
    rawMetrics.precision != null
      ? toNumber(rawMetrics.precision)
      : (truePositives + falsePositives) > 0
        ? (truePositives / (truePositives + falsePositives)) * 100
        : 0;

  const recall =
    rawMetrics.recall != null
      ? toNumber(rawMetrics.recall)
      : (truePositives + falseNegatives) > 0
        ? (truePositives / (truePositives + falseNegatives)) * 100
        : 0;

  const precisionDecimal = precision / 100;
  const recallDecimal = recall / 100;
  const f1Score =
    rawMetrics.f1_score != null || rawMetrics.f1Score != null
      ? toNumber(rawMetrics.f1_score ?? rawMetrics.f1Score)
      : (precisionDecimal + recallDecimal) > 0
        ? (2 * (precisionDecimal * recallDecimal)) / (precisionDecimal + recallDecimal) * 100
        : 0;

  return {
    true_positives: truePositives,
    false_positives: falsePositives,
    false_negatives: falseNegatives,
    total_ground_truth: totalGroundTruth,
    precision,
    recall,
    f1_score: f1Score,
  };
};


const mergeGroundTruthMetrics = (base: any, fallback: any) => {
  if (!fallback) {
    return base ?? null;
  }

  const merged = {
    true_positives:
      fallback.true_positives ?? fallback.truePositives ?? base?.true_positives ?? 0,
    false_positives:
      fallback.false_positives ?? fallback.falsePositives ?? base?.false_positives ?? 0,
    false_negatives:
      fallback.false_negatives ?? fallback.falseNegatives ?? base?.false_negatives ?? 0,
    total_ground_truth:
      fallback.total_ground_truth ??
      fallback.totalGroundTruth ??
      base?.total_ground_truth ??
      0,
    precision: fallback.precision ?? base?.precision ?? 0,
    recall: fallback.recall ?? base?.recall ?? 0,
    f1_score: fallback.f1_score ?? fallback.f1Score ?? base?.f1_score ?? 0,
  };

  return merged;
};

const normalizeResultStatus = (value?: string | null): string | null => {
  if (!value || typeof value !== 'string') {
    return null;
  }
  return value.toUpperCase();
};

const formatStatusLabel = (status?: string | null): string => {
  const normalized = normalizeResultStatus(status);
  switch (normalized) {
    case 'PASS':
      return 'Pass';
    case 'FAIL':
      return 'Fail';
    case 'CONDITIONAL_PASS':
      return 'Conditional Pass';
    case 'PENDING':
      return 'Pending';
    default:
      return 'Unknown';
  }
};

const statusToChipColor = (status?: string | null): 'success' | 'warning' | 'error' | 'default' => {
  const normalized = normalizeResultStatus(status);
  switch (normalized) {
    case 'PASS':
      return 'success';
    case 'CONDITIONAL_PASS':
      return 'warning';
    case 'FAIL':
      return 'error';
    default:
      return 'default';
  }
};

const formatPercentageDisplay = (value?: number | null, treatAsRatio = false): string | null => {
  if (value == null || Number.isNaN(value)) {
    return null;
  }
  const normalized = treatAsRatio && value <= 1 ? value * 100 : value;
  return `${normalized.toFixed(1)}%`;
};

/**
 * HIL Results Page - Clean, Modern Implementation
 *
 * This component displays Hardware-in-the-Loop (HIL) test results with:
 * - Clear pass/fail status
 * - Summary metrics cards
 * - Detection timeline visualization
 * - Single, clean detection events table
 * - Support for multi-video sequences
 */
const HILResults: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  // State management
  const [enhancedResults, setEnhancedResults] = useState<EnhancedHILResults | null>(null);
  const [sequenceResults, setSequenceResults] = useState<VideoSequenceResults | null>(null);
  const [isSequence, setIsSequence] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [groundTruthEvents, setGroundTruthEvents] = useState<any[]>([]);
  const [videoId, setVideoId] = useState<string | null>(null);
  const [baseDetections, setBaseDetections] = useState<EnhancedDetectionEvent[]>([]);
  const [perVideoSummaries, setPerVideoSummaries] = useState<PerVideoResult[]>([]);
  const [videoDetectionMap, setVideoDetectionMap] = useState<Record<string, EnhancedDetectionEvent[]>>({});
  const [videoGroundTruthMap, setVideoGroundTruthMap] = useState<Record<string, any[]>>({});
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);
  const [realtimeEnabled, setRealtimeEnabled] = useState(false);
  const [availableVideos, setAvailableVideos] = useState<Array<{ id: string; filename: string; url: string }>>([]);
  // BUG FIX: Track loading state per video to show spinner during async data loading
  const [videoLoadingState, setVideoLoadingState] = useState<Record<string, boolean>>({});

  const effectivePerVideoSummaries = useMemo(() => {
    // CRITICAL FIX: Backend may return either perVideoResults (camelCase) or per_video_results (snake_case)
    // Check both field names to ensure we capture the data
    const sourceList: any[] =
      (perVideoSummaries && perVideoSummaries.length > 0
        ? perVideoSummaries
        : (sequenceResults?.perVideoResults ?? sequenceResults?.per_video_results)) ?? [];

    console.log('[effectivePerVideoSummaries] Source data:', {
      hasPerVideoSummaries: perVideoSummaries && perVideoSummaries.length > 0,
      perVideoSummariesCount: perVideoSummaries?.length,
      sequenceResultsPerVideoResults: sequenceResults?.perVideoResults?.length,
      sequenceResultsPer_video_results: sequenceResults?.per_video_results?.length,
      sourceListLength: sourceList.length,
      firstVideo: sourceList[0] ? {
        videoId: sourceList[0].videoId ?? sourceList[0].video_id,
        videoName: sourceList[0].videoName ?? sourceList[0].video_name,
        hasGroundTruthComparison: !!(sourceList[0].ground_truth_comparison ?? sourceList[0].groundTruthComparison),
        hasDetectionEvents: !!(sourceList[0].detection_events ?? sourceList[0].detectionEvents)
      } : null
    });

    if (!sourceList.length) {
      return [];
    }

    return sourceList.map((video) => {
      const currentId = video.videoId ?? video.video_id ?? video.id;
      const detections = currentId ? (videoDetectionMap[currentId] ?? []) : [];
      const groundTruth = currentId ? (videoGroundTruthMap[currentId] ?? []) : [];

      // CRITICAL FIX: Prefer ground_truth_metrics which has correct total_ground_truth (e.g., 131)
      // ground_truth_comparison may have incorrect total_ground_truth (e.g., 65) in some cases
      // Backend provides accurate TP/FP/FN from proper ground truth matching
      const existingMetricsRaw =
        video.ground_truth_metrics ??
        video.groundTruthMetrics ??
        video.ground_truth_comparison ??
        video.groundTruthComparison ??
        null;

      const existingNormalized = normalizeGroundTruthMetrics(existingMetricsRaw);

      // Check if backend provided any ground truth data at all (even if zeros)
      const hasBackendGroundTruthData = !!existingNormalized && (
        existingNormalized.true_positives > 0 ||
        existingNormalized.false_positives > 0 ||
        existingNormalized.false_negatives > 0 ||
        existingNormalized.total_ground_truth > 0 ||
        existingNormalized.precision > 0 ||
        existingNormalized.recall > 0
      );

      console.log(`[effectivePerVideoSummaries] Video ${currentId}: Backend GT data=${hasBackendGroundTruthData}`, existingNormalized);

      // ONLY use backend ground truth data - deprecated frontend recalculation removed
      // This ensures we always use correct backend metrics and prevent incorrect calculations
      const selectedMetrics = hasBackendGroundTruthData
        ? existingNormalized
        : existingNormalized;

      if (!selectedMetrics) {
        return video;
      }

      const metrics = mergeGroundTruthMetrics(existingNormalized, selectedMetrics);
      if (!metrics) {
        return video;
      }

      const detectionCount =
        detections.length ||
        (video.total_detections ??
        video.totalDetections ??
        video.detection_count ??
        video.detectionCount ??
        0);

      const camelMetrics = {
        truePositives: metrics.true_positives,
        falsePositives: metrics.false_positives,
        falseNegatives: metrics.false_negatives,
        totalGroundTruth: metrics.total_ground_truth,
        precision: metrics.precision,
        recall: metrics.recall,
        f1Score: metrics.f1_score,
      };

      // Explicitly preserve video name fields to ensure they're available for getVideoName()
      const videoName = video.videoName ?? video.video_name ?? video.video_filename ?? video.videoFilename;

      // CRITICAL: Preserve detectionEvents from backend if they exist
      // Backend may include per-video detection_events or detectionEvents arrays
      const backendDetectionEvents = video.detection_events ?? video.detectionEvents;

      return {
        ...video,
        videoName,
        video_name: videoName,
        ground_truth_metrics: metrics,
        groundTruthMetrics: camelMetrics,
        // CRITICAL: Merge ground_truth_comparison to preserve any additional backend fields
        ground_truth_comparison: {
          ...(video.ground_truth_comparison ?? {}),
          ...metrics,
        },
        groundTruthComparison: {
          ...(video.groundTruthComparison ?? {}),
          ...camelMetrics,
        },
        total_detections: detectionCount,
        totalDetections: detectionCount,
        detection_count: detectionCount,
        detectionCount,
        // Explicitly preserve detectionEvents if backend provided them
        ...(backendDetectionEvents && {
          detection_events: backendDetectionEvents,
          detectionEvents: backendDetectionEvents
        }),
      };
    }).map((video, index) => {
      // Log final transformed video for debugging
      console.log(`[effectivePerVideoSummaries] Video ${index + 1}/${sourceList.length}:`, {
        videoId: video.videoId ?? video.video_id,
        videoName: video.videoName ?? video.video_name,
        hasGroundTruthComparison: !!(video.ground_truth_comparison),
        groundTruthMetrics: video.ground_truth_comparison ? {
          tp: video.ground_truth_comparison.true_positives,
          fp: video.ground_truth_comparison.false_positives,
          fn: video.ground_truth_comparison.false_negatives,
          f1: video.ground_truth_comparison.f1_score
        } : null,
        hasDetectionEvents: !!(video.detection_events ?? video.detectionEvents),
        detectionEventsCount: (video.detection_events ?? video.detectionEvents)?.length ?? 0
      });
      return video;
    });
  }, [perVideoSummaries, sequenceResults, videoDetectionMap, videoGroundTruthMap]);


  // Video popup state
  const [videoDialogOpen, setVideoDialogOpen] = useState(false);
  const [selectedDetection, setSelectedDetection] = useState<EnhancedDetectionEvent | null>(null);
  const [playbackVideoUrl, setPlaybackVideoUrl] = useState<string>('');
  /**
   * Load ground truth events for a specific video
   */
  const loadGroundTruthData = useCallback(async (videoId: string) => {
    try {
      console.log(`Loading ground truth data for video: ${videoId}`);
      setGroundTruthEvents([]);
      const response = await apiService.getGroundTruthEvents(videoId);

      if (response?.success && response?.data?.ground_truth_events) {
        const rawEvents = response.data.ground_truth_events;
        const dedupedEvents = (() => {
          const seen = new Set<string>();
          const result: any[] = [];
          rawEvents.forEach((evt: any) => {
            const frame = evt.video_frame ?? evt.frame_number;
            const ts = evt.timestamp ?? evt.video_timestamp ?? evt.video_relative_timestamp;
            const key =
              Number.isFinite(frame) && frame !== null
                ? `frame:${frame}`
                : `time:${ts ?? 'unknown'}:${evt.class_label ?? evt.label ?? ''}`;
            if (!seen.has(key)) {
              seen.add(key);
              result.push(evt);
            }
          });
          return result;
        })();

        console.log(`Loaded ${rawEvents.length} ground truth events (deduped to ${dedupedEvents.length})`);
        setGroundTruthEvents(dedupedEvents);
        setVideoGroundTruthMap(prev => ({ ...prev, [videoId]: dedupedEvents }));
        setPerVideoSummaries(prev =>
          prev.map(video => {
            const currentId = video.videoId ?? video.video_id ?? video.id;
            if (currentId === videoId) {
              return {
                ...video,
                ground_truth_events_available: dedupedEvents.length,
                groundTruthEventsAvailable: dedupedEvents.length,
                ground_truth_count: dedupedEvents.length
              } as any;
            }
            return video;
          })
        );
        return dedupedEvents;
      } else {
        console.log('No ground truth data available for this video');
        setGroundTruthEvents([]);
        setVideoGroundTruthMap(prev => ({ ...prev, [videoId]: [] }));
        return [];
      }
    } catch (error) {
      console.warn('Failed to load ground truth data:', error);
      setGroundTruthEvents([]);
      setVideoGroundTruthMap(prev => ({ ...prev, [videoId]: [] }));
      return [];
    }
  }, []);

  // Preload ground truth data for all videos in a sequence so counts stay accurate
  useEffect(() => {
    if (!isSequence || effectivePerVideoSummaries.length === 0) {
      return;
    }

    perVideoSummaries.forEach(video => {
      const currentId = video.videoId ?? video.video_id ?? video.id;
      if (!currentId) {
        return;
      }

      if (videoGroundTruthMap[currentId] === undefined) {
        loadGroundTruthData(currentId);
      }
    });
  }, [isSequence, perVideoSummaries, videoGroundTruthMap, loadGroundTruthData]);

  /**
   * Load detections for a specific video
   * @param videoId - Video ID to filter by, or null to load all detections (no filter)
   */
  const loadDetectionsForVideo = useCallback(async (videoId: string | null) => {
    // BUG FIX: Set loading state before async operation to show spinner
    const loadingKey = videoId || '__all__';
    setVideoLoadingState(prev => ({ ...prev, [loadingKey]: true }));
    try {
      console.log(`Loading detections${videoId ? ` for video: ${videoId}` : ' (all videos)'}`);

      // CRITICAL FIX: Only pass video_id filter if we have a specific video in multi-video mode
      // For single-video sessions, pass empty filters to get ALL detections (including those with NULL video_id)
      const filters = (videoId && isSequence) ? { video_id: videoId } : {};

      const videoDetections = await apiService.getTestSessionEvents(
        sessionId!,
        2000,
        filters  // ✅ Empty object for single-video, or with video_id for multi-video
      );

      const normalized = normalizeDetectionEvents(videoDetections);
      console.log(`Loaded ${normalized.length} detections${videoId ? ` for video ${videoId}` : ' (all)'}`);

     if (videoId && isSequence) {
       // Multi-video mode: store per-video detections but keep existing base/all array
       setVideoDetectionMap(prev => {
         const next = { ...prev, [videoId]: normalized };

          // Maintain a combined "__all__" entry for aggregate views
          const combined = Object.entries(next)
            .filter(([key]) => key !== '__all__')
            .flatMap(([, value]) => Array.isArray(value) ? value : []);

          // DEDUPLICATION FIX: Remove duplicates when building __all__ aggregate
          const seen = new Set<string>();
          const deduplicated = combined.filter((detection) => {
            const id = detection?.id ?? detection?.event_id ?? detection?.detection_id;
            if (!id || seen.has(id)) {
              return false;
            }
            seen.add(id);
            return true;
          });

          const prevAll = Array.isArray(prev['__all__']) ? prev['__all__'] : [];
          if (deduplicated.length > prevAll.length) {
            console.log(`🔍 [videoDetectionMap __all__] Deduplication: ${combined.length} → ${deduplicated.length} (removed ${combined.length - deduplicated.length} duplicates)`);
            next['__all__'] = deduplicated;
          } else if (prevAll.length > 0) {
            next['__all__'] = prevAll;
          }
          return next;
       });

        setPerVideoSummaries(prev =>
          prev.map(video => {
            const currentId = video.videoId ?? video.video_id ?? video.id;
            if (currentId === videoId) {
              return {
                ...video,
                detection_count: normalized.length,
                total_detections: normalized.length,
                detectionCount: normalized.length,
                totalDetections: normalized.length
              } as any;
            }
            return video;
          })
        );

        // Preserve the original full list for aggregated metrics
        setBaseDetections(prev => {
          const existing = Array.isArray(prev) ? prev : [];
          if (existing.length === 0) {
            return normalized;
          }
          const existingIds = new Set(existing.map(item => (item as any)?.id ?? (item as any)?.detection_id));
          const merged = existing.concat(
            normalized.filter(item => {
              const identifier = (item as any)?.id ?? (item as any)?.detection_id;
              return identifier ? !existingIds.has(identifier) : true;
            })
          );
          return merged;
        });
      } else {
        // Single-video or explicit "all videos" load: update base + map entry
        setBaseDetections(normalized);
        setVideoDetectionMap(prev => ({
          ...prev,
          [loadingKey]: normalized
        }));
      }
    } catch (error) {
      console.error(`Failed to load detections${videoId ? ` for video ${videoId}` : ''}:`, error);
      // Don't throw - just log the error and keep existing data
    } finally {
      // BUG FIX: Clear loading state after async operation completes
      setVideoLoadingState(prev => ({ ...prev, [loadingKey]: false }));
    }
  }, [sessionId, isSequence]);

  /**
   * Handle video selection change (for multi-video sequences)
   */
  const handleVideoTabChange = useCallback((_: React.SyntheticEvent, newVideoId: string) => {
    if (!newVideoId) return;
    console.log(`Switching to video: ${newVideoId}`);

    // FIX #1: Handle "All Videos" aggregated view
    if (newVideoId === '__all__') {
      setSelectedVideoId('__all__');
      setVideoId(null);
      // Load all detections for aggregated view
      loadDetectionsForVideo(null);
      return;
    }

    setSelectedVideoId(newVideoId);
    setVideoId(newVideoId);

    // Load ground truth and detections for the selected video
    loadGroundTruthData(newVideoId);
    loadDetectionsForVideo(newVideoId);
  }, [loadGroundTruthData, loadDetectionsForVideo]);

  /**
   * Load HIL test results with ground truth comparison
   */
  const loadHILResults = useCallback(async () => {
    if (!sessionId) return;

    try {
      setLoading(true);
      setError(null);
      setGroundTruthEvents([]);
      setIsSequence(false);
      setSequenceResults(null);
      setPerVideoSummaries([]);
      setVideoDetectionMap({});
      setSelectedVideoId(null);
      setVideoId(null);
      setBaseDetections([]);
      setAvailableVideos([]);

      console.log('Loading HIL results for session:', sessionId);

      let enhancedData: EnhancedHILResults;
      try {
        enhancedData = await apiService.getEnhancedHILResultsWithGroundTruth(sessionId);
        console.log('Enhanced HIL results loaded:', enhancedData);
      } catch (error) {
        console.warn('Ground truth endpoint failed, using basic results:', error);
        enhancedData = await apiService.getEnhancedHILResults(sessionId);
      }

      setEnhancedResults(enhancedData);

      const detectionCandidates: any[] = [];

      const addCandidateEvents = (value: unknown) => {
        if (Array.isArray(value) && value.length > 0) {
          detectionCandidates.push(...value);
        }
      };

      addCandidateEvents((enhancedData as any)?.detection_events);
      addCandidateEvents((enhancedData as any)?.detectionEvents);
      addCandidateEvents((enhancedData as any)?.combined_detection_events);
      addCandidateEvents((enhancedData as any)?.combinedDetectionEvents);
      addCandidateEvents((enhancedData as any)?.detection_statistics?.detection_events);
      addCandidateEvents((enhancedData as any)?.detection_statistics?.combined_detection_events);
      addCandidateEvents(collectDetectionCandidates(enhancedData));

      let normalizedDetections = normalizeDetectionEvents(detectionCandidates);
      let candidateEvents = detectionCandidates.slice();

      if (normalizedDetections.length === 0) {
        try {
          const events = await apiService.getTestSessionEvents(sessionId, 2000);
          normalizedDetections = normalizeDetectionEvents(events);
          if (Array.isArray(events)) {
            candidateEvents.push(...events);
          }
        } catch (eventsError) {
          console.warn('Session events endpoint unavailable:', eventsError);
        }
      }

      if (normalizedDetections.length === 0) {
        try {
          const fallbackDetections = await apiService.getTestSessionDetections(sessionId);
          normalizedDetections = normalizeDetectionEvents(fallbackDetections);
          if (Array.isArray(fallbackDetections)) {
            candidateEvents.push(...fallbackDetections);
          }
        } catch (fallbackError) {
          console.warn('Fallback detection fetch failed:', fallbackError);
        }
      }

      if (normalizedDetections.length > 1) {
        const deduped: EnhancedDetectionEvent[] = [];
        const seenKeys = new Set<string>();
        normalizedDetections.forEach(event => {
          const key = event.id || `${event.timestamp}-${event.voltage ?? ''}-${event.real_latency_ms ?? ''}`;
          if (!seenKeys.has(key)) {
            seenKeys.add(key);
            deduped.push(event);
          }
        });
        normalizedDetections = deduped;
      }

      let session: any = null;
      try {
        session = await apiService.getTestSession(sessionId);

        // Load available videos for the project if we have a project ID
        if (session?.projectId || session?.project_id) {
          const projectId = session.projectId || session.project_id;
          console.log('🎥 Loading available videos for project:', projectId);
          try {
            const projectVideos = await apiService.getVideos(projectId);
            console.log('🎥 Loaded project videos:', projectVideos);
            const videoList = projectVideos.map((v: any) => ({
              id: v.id,
              filename: v.filename || v.name || v.originalName,
              url: v.url || ''
            }));
            setAvailableVideos(videoList);
          } catch (videoError) {
            console.warn('Failed to load project videos:', videoError);
          }
        }
      } catch (sessionError) {
        console.warn('Failed to load session metadata:', sessionError);
      }

      const hasSequence = Boolean(session?.hasVideoSequence ?? session?.has_video_sequence);
      const detectedSequenceId: string | null = session?.sequenceId ?? session?.sequence_id ?? null;
      const sessionVideoId: string | null = session?.videoId ?? session?.video_id ?? null;

      let sequenceMetadata: Record<string, any> | null = null;
      let sequenceVideoIds: string[] = [];
      try {
        const rawMetadata = session?.sequence_metadata ?? session?.sequenceMetadata ?? null;
        if (rawMetadata) {
          sequenceMetadata = typeof rawMetadata === 'string' ? JSON.parse(rawMetadata) : rawMetadata;
          const ids = sequenceMetadata?.video_ids ?? sequenceMetadata?.videoIds ?? sequenceMetadata?.videos ?? null;
          if (Array.isArray(ids)) {
            sequenceVideoIds = ids.filter((id: unknown) => typeof id === 'string');
          }
        }
      } catch (metadataError) {
        console.warn('Failed to parse sequence metadata', metadataError);
        sequenceMetadata = null;
        sequenceVideoIds = [];
      }

      if (hasSequence && detectedSequenceId) {
        console.log('Multi-video sequence detected:', detectedSequenceId);
        setIsSequence(true);

        try {
          const seqResults = await apiService.getVideoSequenceResults(detectedSequenceId);
          const normalizedSeqResults = normalizeSequenceResults(seqResults);
          const effectiveSeqResults = normalizedSeqResults ?? seqResults;
          setSequenceResults(effectiveSeqResults);

          // CRITICAL FIX #3: Use ground_truth_comparison from backend API instead of recalculating
          // Backend already calculated correct TP/FP/FN metrics (59 TP, 6 FP, 455 FN)
          // Frontend was recalculating from wrong field (validation_result = "PASS"/"FAIL" not "TP"/"FP"/"FN")

          // Collect all detection sources and deduplicate before normalization
          const rawCombinedEvents = [
            ...(((effectiveSeqResults as any)?.combined_detection_events) ?? []),
            ...(((effectiveSeqResults as any)?.combinedDetectionEvents) ?? []),
            ...(((effectiveSeqResults as any)?.detection_events) ?? []),
            ...collectDetectionCandidates(effectiveSeqResults)
          ];

          // DEDUPLICATION FIX: Remove duplicates from raw events before normalization
          const seenRawIds = new Set<string>();
          const dedupedRawEvents = rawCombinedEvents.filter((event) => {
            const rawId = event?.id ?? event?.event_id ?? event?.detection_id ?? event?.uuid;
            if (!rawId) {
              return true; // Keep events without IDs (will get generated IDs during normalization)
            }
            if (seenRawIds.has(String(rawId))) {
              return false;
            }
            seenRawIds.add(String(rawId));
            return true;
          });

          console.log(`🔍 [sequenceCombinedEvents] Raw deduplication: ${rawCombinedEvents.length} → ${dedupedRawEvents.length} (removed ${rawCombinedEvents.length - dedupedRawEvents.length} duplicates)`);

          const sequenceCombinedEvents = normalizeDetectionEvents(dedupedRawEvents);

          if (sequenceCombinedEvents.length > 0) {
            const seenIds = new Set<string>(normalizedDetections.map(event => event.id));
            sequenceCombinedEvents.forEach(event => {
              if (!event.id || !seenIds.has(event.id)) {
                normalizedDetections.push(event);
                if (event.id) {
                  seenIds.add(event.id);
                }
              }
            });

            if (normalizedDetections.length > 1) {
              const dedupedSeq: EnhancedDetectionEvent[] = [];
              const seenKeysSeq = new Set<string>();
              normalizedDetections.forEach(event => {
                const key = event.id || `${event.timestamp}-${event.voltage ?? ''}-${event.real_latency_ms ?? ''}`;
                if (!seenKeysSeq.has(key)) {
                  seenKeysSeq.add(key);
                  dedupedSeq.push(event);
                }
              });
              normalizedDetections = dedupedSeq;
            }
          }

          const rawPerVideo = (
            effectiveSeqResults?.perVideoResults ??
            effectiveSeqResults?.per_video_results ??
            []
          ) as PerVideoResult[];

          // 🔧 DEFENSIVE FIX: Filter out detection objects that shouldn't be in per_video_results
          const validatedPerVideo = rawPerVideo.filter((item: any) => {
            const isVideo = !!(item.video_id || item.videoId) &&
                           (item.video_name || item.videoName || item.video_filename);
            const isDetection = !!(item.detection_time_ms || item.real_latency_ms || item.voltage);

            if (isDetection && !isVideo) {
              console.error('🚨 Detection object found in per_video_results, filtering out:', item);
              return false;
            }
            return isVideo;
          });

          let sortedPerVideo = [...validatedPerVideo].sort((a, b) => {
            const orderA = a.sequenceIndex ?? a.sequence_index ?? a.videoOrder ?? a.video_order ?? a.video_number ?? a.videoNumber ?? 0;
            const orderB = b.sequenceIndex ?? b.sequence_index ?? b.videoOrder ?? b.video_order ?? b.video_number ?? b.videoNumber ?? 0;
            return orderA - orderB;
          });

          if (sortedPerVideo.length === 0 && sequenceVideoIds.length > 0) {
            sortedPerVideo = sequenceVideoIds.map((id, index) => ({
              video_id: id,
              videoId: id,
              video_name: sequenceMetadata?.video_names?.[id] ?? sequenceMetadata?.videoNames?.[id] ?? sequenceMetadata?.video_metadata?.[id]?.name ?? `Video ${index + 1}`,
              videoNumber: index + 1,
              sequenceIndex: index,
              passFail: 'pending',
              detection_count: 0,
              total_detections: 0
            } as PerVideoResult));
          }

          setPerVideoSummaries(sortedPerVideo);

          // CRITICAL FIX: For multi-video sequences, preload ALL detections upfront
          // This ensures aggregatedMetrics can correctly calculate totals across all videos
          if (isSequence && sortedPerVideo.length > 1) {
            console.log(`🔄 Preloading detections for ${sortedPerVideo.length} videos in sequence`);

            const detectionMap: Record<string, EnhancedDetectionEvent[]> = {};
            const groundTruthMap: Record<string, any[]> = {};

            // Load all videos in parallel for faster aggregation
            const loadPromises = sortedPerVideo.map(async (video) => {
              const videoId = video.video_id ?? video.videoId;
              if (!videoId) return;

              try {
                // Load detections
                const detResponse = await apiService.getDetectionEvents(sessionId, videoId);
                const detections = normalizeDetectionEvents(detResponse?.data?.detection_events ?? []);
                detectionMap[videoId] = detections;

                // Load ground truth
                const gtResponse = await apiService.getGroundTruthEvents(videoId);
                if (gtResponse?.success && gtResponse?.data?.ground_truth_events) {
                  const rawEvents = gtResponse.data.ground_truth_events;
                  const dedupedEvents = (() => {
                    const seen = new Set<string>();
                    const result: any[] = [];
                    rawEvents.forEach((evt: any) => {
                      const frame = evt.video_frame ?? evt.frame_number;
                      const ts = evt.timestamp ?? evt.video_timestamp ?? evt.video_relative_timestamp;
                      const key =
                        Number.isFinite(frame) && frame !== null
                          ? `frame:${frame}`
                          : `time:${ts ?? 'unknown'}:${evt.class_label ?? evt.label ?? ''}`;
                      if (!seen.has(key)) {
                        seen.add(key);
                        result.push(evt);
                      }
                    });
                    return result;
                  })();
                  groundTruthMap[videoId] = dedupedEvents;
                }

                console.log(`✅ Loaded ${detections.length} detections for video ${videoId}`);
              } catch (error) {
                console.error(`Failed to load data for video ${videoId}:`, error);
                detectionMap[videoId] = [];
                groundTruthMap[videoId] = [];
              }
            });

            await Promise.all(loadPromises);

            setVideoDetectionMap(detectionMap);
            setVideoGroundTruthMap(groundTruthMap);

            const firstVideoId = sortedPerVideo[0].video_id ?? sortedPerVideo[0].videoId;
            setSelectedVideoId(firstVideoId);
            setVideoId(firstVideoId);
            if (firstVideoId && groundTruthMap[firstVideoId]) {
              setGroundTruthEvents(groundTruthMap[firstVideoId]);
            }
          } else {
            // Single video - use original lazy loading strategy
            const detectionMap: Record<string, EnhancedDetectionEvent[]> = {};
            setVideoDetectionMap(detectionMap);

            const firstVideoId = sortedPerVideo[0] ? (sortedPerVideo[0].videoId ?? sortedPerVideo[0].video_id ?? null) : null;
            if (firstVideoId) {
              setVideoId(firstVideoId);
              await loadGroundTruthData(firstVideoId);
              // CRITICAL FIX: Load detections and store under the actual video ID
              // Previously stored under '__all__' causing key mismatch with selectedVideoId
              const videoDetections = await apiService.getTestSessionEvents(sessionId!, 2000, {});
              const normalizedDetections = normalizeDetectionEvents(videoDetections);
              console.log(`Loaded ${normalizedDetections.length} detections for single-video session`);
              // Store under BOTH the video ID AND __all__ to support both lookup patterns
              setVideoDetectionMap({
                [firstVideoId]: normalizedDetections,
                '__all__': normalizedDetections
              });
              setSelectedVideoId(firstVideoId);
            }
          }
        } catch (sequenceError) {
          console.warn('Failed to load sequence results:', sequenceError);
          setSequenceResults(null);
          setPerVideoSummaries([]);
        }
      } else {
        setIsSequence(false);
        const fallbackVideoId = sessionVideoId;

        if (fallbackVideoId) {
          setVideoId(fallbackVideoId);
          setSelectedVideoId(fallbackVideoId);
          await loadGroundTruthData(fallbackVideoId);
        }

        if (fallbackVideoId && normalizedDetections.length > 0) {
          setVideoDetectionMap({ [fallbackVideoId]: normalizedDetections });
        } else {
          setVideoDetectionMap(normalizedDetections.length > 0 ? { __all__: normalizedDetections } : {});
        }
      }
      setBaseDetections([...normalizedDetections]);

      setLoading(false);
    } catch (err: any) {
      console.error('Error loading HIL results:', err);
      setError(err?.message || 'Failed to load HIL results');
      setLoading(false);
    }
  }, [sessionId, loadGroundTruthData]);

  // Load results on mount
  useEffect(() => {
    loadHILResults();
  }, [loadHILResults]);

  // Load detections when selectedVideoId changes (for multi-video sequences only)
  useEffect(() => {
    // Only auto-load for multi-video sequences where we filter by video_id
    const videoSequence = sequenceResults?.per_video_results || [];
    if (selectedVideoId && isSequence && videoSequence.length > 1 && !videoDetectionMap[selectedVideoId]) {
      console.log(`🔄 Auto-loading detections for selected video: ${selectedVideoId}`);
      loadDetectionsForVideo(selectedVideoId);
    }
  }, [selectedVideoId, isSequence, sequenceResults, videoDetectionMap, loadDetectionsForVideo]);

  // CRITICAL DEBUG: Log detection map and loading state changes
  useEffect(() => {
    console.log('🔍 DETECTION MAP STATE:', {
      selectedVideoId,
      isSequence,
      mapKeys: Object.keys(videoDetectionMap),
      loadingStates: videoLoadingState,
      selectedVideoDetections: selectedVideoId ? videoDetectionMap[selectedVideoId]?.length ?? 'undefined' : 'N/A',
      allDetectionCounts: Object.entries(videoDetectionMap).reduce((acc, [key, val]) => {
        acc[key] = val?.length ?? 0;
        return acc;
      }, {} as Record<string, number>)
    });
  }, [videoDetectionMap, selectedVideoId, videoLoadingState, isSequence]);

  // Subscribe to real-time detection updates via WebSocket
  useEffect(() => {
    if (!sessionId || !realtimeEnabled) return;

    console.log('🔌 HILResults: Subscribing to real-time detection updates for session:', sessionId);

    // Import websocketService and subscribe to detection events
    let unsubscribeDetections: (() => void) | null = null;

    import('../services/websocketService').then(({ default: websocketService }) => {
      // Subscribe to detection_event updates
      unsubscribeDetections = websocketService.subscribe('detection_event', (data: any) => {
        console.log('🎯 HILResults: Received detection event:', data);

        // Normalize incoming detection event
        const newDetection = normalizeDetectionEvent(data, baseDetections.length);

        // Add to base detections with deduplication by event_id
        // FIX #7: Prevent duplicates when WebSocket delivers events already in REST API response
        setBaseDetections(prev => {
          const eventId = newDetection.event_id || newDetection.eventId || newDetection.id;
          // Check if this detection already exists by event_id or frame_number+video_id
          const isDuplicate = prev.some(existing => {
            const existingId = existing.event_id || existing.eventId || existing.id;
            // Match by event_id if available
            if (eventId && existingId && eventId === existingId) {
              console.log(`🔄 Skipping duplicate detection by event_id: ${eventId}`);
              return true;
            }
            // Fallback: match by frame_number + video_id combination
            const existingVideoId = existing.video_id || existing.videoId;
            const newVideoId = newDetection.video_id || newDetection.videoId;
            if (existing.frame_number === newDetection.frame_number &&
                existingVideoId && newVideoId && existingVideoId === newVideoId) {
              console.log(`🔄 Skipping duplicate detection by frame+video: frame ${newDetection.frame_number}`);
              return true;
            }
            return false;
          });

          if (isDuplicate) {
            return prev; // Don't add duplicate
          }

          const updated = [...prev, newDetection];
          console.log('📊 Updated detection count:', updated.length);
          return updated;
        });

        // Update video detection map if video ID is available (with deduplication)
        const videoIdFromEvent = (data as any).video_id ?? (data as any).videoId ?? selectedVideoId;
        if (videoIdFromEvent) {
          setVideoDetectionMap(prev => {
            const existing = prev[videoIdFromEvent] || [];
            const eventId = newDetection.event_id || newDetection.eventId || newDetection.id;

            // Check for duplicates in the video-specific map
            const isDuplicate = existing.some(det => {
              const existingId = det.event_id || det.eventId || det.id;
              if (eventId && existingId && eventId === existingId) return true;
              if (det.frame_number === newDetection.frame_number) return true;
              return false;
            });

            if (isDuplicate) {
              return prev; // Don't add duplicate
            }

            return {
              ...prev,
              [videoIdFromEvent]: [...existing, newDetection]
            };
          });
        }

        // Refresh ground truth comparison if needed
        if (groundTruthEvents.length > 0) {
          console.log('🔄 New detection received, ground truth comparison may need update');
        }
      });

      // Subscribe to approval status updates
      websocketService.subscribe('session_approval_updated', (data: any) => {
        console.log('✅ HILResults: Received approval update:', data);
        if (data.session_id === sessionId) {
          setEnhancedResults(prev => prev ? ({
            ...prev,
            approvalStatus: data.approval_status,
            approvedBy: data.approved_by,
            approvedAt: data.approved_at
          }) : null);
        }
      });

      // Join session room for detection events
      websocketService.emit('join_session', { session_id: sessionId });
      console.log('📡 Joined session room for real-time detection updates');
    }).catch(err => {
      console.error('❌ Failed to set up WebSocket subscription:', err);
    });

    // Cleanup on unmount
    return () => {
      if (unsubscribeDetections) {
        unsubscribeDetections();
        console.log('🔕 Unsubscribed from detection events');
      }

      import('../services/websocketService').then(({ default: websocketService }) => {
        websocketService.emit('leave_session', { session_id: sessionId });
        console.log('🔕 Left session room');
      }).catch(err => {
        console.error('❌ Failed to leave session:', err);
      });
    };
  }, [sessionId, realtimeEnabled, selectedVideoId, baseDetections.length, groundTruthEvents.length]);

  // Calculate aggregated metrics across all videos for multi-video sequences
  const aggregatedMetrics = useMemo(() => {
    if (!isSequence) {
      return null;
    }

    const videos = effectivePerVideoSummaries;

    if (!videos.length) {
      console.warn('[aggregatedMetrics] No videos available for aggregation', {
        perVideoSummaries: effectivePerVideoSummaries?.length,
        sequenceResults: sequenceResults?.per_video_results?.length
      });
      return null;
    }

    // CRITICAL FIX: Use SESSION-LEVEL ground_truth_comparison from enhancedResults
    // This has the CORRECT values (e.g., 131 GT, 65 TP, 66 FN) calculated from the full session
    // The per_video_results.ground_truth_metrics has WRONG values because it queries per-video GT objects
    const sessionGtComp = enhancedResults?.ground_truth_comparison;

    let totalTP: number;
    let totalFP: number;
    let totalFN: number;
    let totalGroundTruthEvents: number;
    let aggregatedPrecision: number;
    let aggregatedRecall: number;
    let aggregatedF1: number;

    if (sessionGtComp && sessionGtComp.ground_truth_events_available > 0) {
      // USE SESSION-LEVEL METRICS (CORRECT SOURCE)
      totalTP = toNumber(sessionGtComp.true_positives ?? 0);
      totalFP = toNumber(sessionGtComp.false_positives ?? 0);
      totalFN = toNumber(sessionGtComp.false_negatives ?? 0);
      totalGroundTruthEvents = toNumber(sessionGtComp.ground_truth_events_available ?? 0);
      aggregatedPrecision = toNumber(sessionGtComp.precision ?? 0);
      aggregatedRecall = toNumber(sessionGtComp.recall ?? 0);
      aggregatedF1 = toNumber(sessionGtComp.f1_score ?? 0);

      console.log(`[aggregatedMetrics] ✅ USING SESSION-LEVEL ground_truth_comparison:`, {
        totalTP, totalFP, totalFN, totalGroundTruthEvents,
        precision: aggregatedPrecision, recall: aggregatedRecall, f1: aggregatedF1
      });
    } else {
      // FALLBACK: Aggregate from per-video metrics (may have incorrect values)
      console.warn('[aggregatedMetrics] ⚠️ Session-level ground_truth_comparison not available, falling back to per-video aggregation');

      totalTP = videos.reduce((sum, v) => {
        const gtComp = v.ground_truth_metrics ?? v.groundTruthMetrics ?? v.ground_truth_comparison ?? v.groundTruthComparison ?? {};
        const tp = gtComp.true_positives ?? gtComp.truePositives ?? 0;
        return sum + toNumber(tp);
      }, 0);
      totalFP = videos.reduce((sum, v) => {
        const gtComp = v.ground_truth_metrics ?? v.groundTruthMetrics ?? v.ground_truth_comparison ?? v.groundTruthComparison ?? {};
        const fp = gtComp.false_positives ?? gtComp.falsePositives ?? 0;
        return sum + toNumber(fp);
      }, 0);
      totalFN = videos.reduce((sum, v) => {
        const gtComp = v.ground_truth_metrics ?? v.groundTruthMetrics ?? v.ground_truth_comparison ?? v.groundTruthComparison ?? {};
        const fn = gtComp.false_negatives ?? gtComp.falseNegatives ?? 0;
        return sum + toNumber(fn);
      }, 0);
      totalGroundTruthEvents = videos.reduce((sum, v) => {
        const backendCount = v.ground_truth_metrics?.total_ground_truth ??
                             v.ground_truth_comparison?.ground_truth_events_available ??
                             v.ground_truth_comparison?.total_ground_truth ??
                             v.ground_truth_events_available ?? v.groundTruthEventsAvailable ??
                             v.ground_truth_count ?? v.groundTruthCount ?? 0;
        return sum + toNumber(backendCount);
      }, 0);

      // Calculate precision, recall, F1 from totals
      aggregatedPrecision = (totalTP + totalFP) > 0 ? (totalTP / (totalTP + totalFP)) * 100 : 0;
      aggregatedRecall = (totalTP + totalFN) > 0 ? (totalTP / (totalTP + totalFN)) * 100 : 0;
      const precisionDecimal = aggregatedPrecision / 100;
      const recallDecimal = aggregatedRecall / 100;
      aggregatedF1 = (precisionDecimal + recallDecimal) > 0
        ? (2 * (precisionDecimal * recallDecimal) / (precisionDecimal + recallDecimal)) * 100
        : 0;

      console.log(`[aggregatedMetrics] ⚠️ FALLBACK aggregation: TP=${totalTP}, FP=${totalFP}, FN=${totalFN}, GT=${totalGroundTruthEvents}`);
    }

    console.log(`[aggregatedMetrics] FINAL: TP=${totalTP}, FP=${totalFP}, FN=${totalFN}, GT=${totalGroundTruthEvents}`);
    console.log(`[aggregatedMetrics] FINAL: Precision=${aggregatedPrecision.toFixed(1)}%, Recall=${aggregatedRecall.toFixed(1)}%, F1=${aggregatedF1.toFixed(1)}%`);

    // Aggregate detection metrics - ALWAYS use backend data first (source of truth)
    const totalDetections = videos.reduce((sum, v) => {
      // Backend data is authoritative
      const backendCount = v.total_detections ?? v.totalDetections ?? v.detection_count ?? v.detectionCount ?? 0;

      if (backendCount > 0) {
        return sum + backendCount;
      }

      // Fallback to map only if backend data missing (shouldn't happen for sequences)
      const currentId = v.videoId ?? v.video_id ?? v.id;
      const mapCount = currentId ? (videoDetectionMap[currentId]?.length ?? 0) : 0;
      if (mapCount === 0 && backendCount === 0) {
        console.warn(`No detection count available for video ${currentId}`);
      }
      return sum + mapCount;
    }, 0);
    const totalPassed = videos.reduce((sum, v) => sum + (v.passed_detections ?? v.passedDetections ?? 0), 0);
    const totalFailed = videos.reduce((sum, v) => sum + (v.failed_detections ?? v.failedDetections ?? 0), 0);
    const overallPassRate = totalDetections > 0 ? (totalPassed / totalDetections) * 100 : 0;

    // Aggregate latency metrics (calculate average of averages, weighted by detection count)
    const totalLatencyWeighted = videos.reduce((sum, v) => {
      const detCount = v.total_detections ?? v.totalDetections ?? v.detection_count ?? v.detectionCount ?? 0;
      const avgLatency = v.average_latency_ms ?? v.averageLatencyMs ?? 0;
      return sum + (avgLatency * detCount);
    }, 0);
    const avgLatency = totalDetections > 0 ? totalLatencyWeighted / totalDetections : 0;
    const worstLatency = Math.max(...videos.map(v => v.max_latency_ms ?? v.maxLatencyMs ?? 0));
    const bestLatency = Math.min(...videos.map(v => v.min_latency_ms ?? v.minLatencyMs ?? Infinity).filter(x => x < Infinity));

    // Count videos by status
    const videosPassed = videos.filter(v => {
      const status = (v.status ?? v.pass_fail ?? v.passFail ?? v.validation_result ?? '').toString().toLowerCase();
      return status === 'pass' || status === 'completed';
    }).length;

    return {
      aggregatedF1Score: aggregatedF1,
      aggregatedPrecision,
      aggregatedRecall,
      totalTruePositives: totalTP,
      totalFalsePositives: totalFP,
      totalFalseNegatives: totalFN,
      overallDetectionCount: totalDetections,
      overallGroundTruthCount: totalGroundTruthEvents,
      overallPassedCount: totalPassed,
      overallFailedCount: totalFailed,
      overallPassRate,
      averageLatencyMs: avgLatency,
      worstLatencyMs: worstLatency,
      bestLatencyMs: bestLatency > 0 ? bestLatency : 0,
      videosPassed,
      totalVideos: videos.length
    };
  }, [isSequence, sequenceResults, perVideoSummaries, videoDetectionMap, videoGroundTruthMap, effectivePerVideoSummaries, enhancedResults]);

  // Destructure aggregated metrics for easy access
  const {
    aggregatedF1Score = 0,
    aggregatedPrecision = 0,
    aggregatedRecall = 0,
    totalTruePositives = 0,
    totalFalsePositives = 0,
    totalFalseNegatives = 0,
    overallDetectionCount: aggOverallDetectionCount = 0,
    overallPassedCount = 0,
    overallGroundTruthCount = 0,
    overallFailedCount = 0,
    overallPassRate: aggOverallPassRate = 0,
    averageLatencyMs: aggAverageLatencyMs = 0,
    worstLatencyMs: aggWorstLatencyMs = 0,
    bestLatencyMs: aggBestLatencyMs = 0,
    videosPassed = 0,
    totalVideos = 0
  } = aggregatedMetrics || {};

  // Calculate derived metrics
  const allDetections = useMemo(() => {
    const baseCount = baseDetections?.length ?? 0;
    const cachedAll = videoDetectionMap['__all__'];

    if (Array.isArray(cachedAll) && cachedAll.length > 0) {
      return cachedAll.length >= baseCount ? cachedAll : baseDetections;
    }

    if (isSequence) {
      const combined = Object.entries(videoDetectionMap)
        .filter(([key]) => key !== '__all__')
        .flatMap(([, value]) => (Array.isArray(value) ? value : []));

      // DEDUPLICATION FIX: Remove duplicates based on unique ID
      // Issue: Frame 1 shows two entries with "real 9ms" and "real 7ms"
      // Issue: Frame 5 shows two entries with "real 16ms" and "real 1ms"
      // Root cause: videoDetectionMap can contain same detection across multiple video keys
      if (combined.length > baseCount) {
        const seen = new Set<string>();
        const deduplicated = combined.filter((detection) => {
          const id = detection?.id ?? detection?.event_id ?? detection?.detection_id;
          if (!id || seen.has(id)) {
            return false;
          }
          seen.add(id);
          return true;
        });
        console.log(`🔍 [allDetections] Deduplication: ${combined.length} → ${deduplicated.length} (removed ${combined.length - deduplicated.length} duplicates)`);
        return deduplicated;
      }
    }

    return baseDetections;
  }, [videoDetectionMap, baseDetections, isSequence]);

  const activeDetections = useMemo(() => {
    // CRITICAL FIX: Check loading state first - if loading, return empty to show spinner
    const loadingKey = selectedVideoId || '__all__';
    if (videoLoadingState[loadingKey]) {
      console.log(`🔄 Video ${selectedVideoId} is loading, returning empty array for spinner`);
      return [];
    }

    // FIX #1: Handle "All Videos" aggregated view
    if (selectedVideoId === '__all__') {
      console.log(`✅ Returning all detections for aggregated view: ${allDetections.length}`);
      return allDetections;
    }

    if (selectedVideoId) {
      const mapped = videoDetectionMap[selectedVideoId];
      if (mapped && mapped.length > 0) {
        console.log(`✅ Returning ${mapped.length} detections for video: ${selectedVideoId}`);
        return mapped;
      }
      // CRITICAL FIX: If not in map but not loading, check if it's been loaded
      // Return empty only if we're confident there are no detections
      if (mapped !== undefined) {
        console.log(`⚠️ Video ${selectedVideoId} loaded but has 0 detections`);
        return [];
      }
      // Not loaded yet and not loading - shouldn't happen but fallback to empty
      console.log(`⚠️ Video ${selectedVideoId} not in map and not loading - returning empty`);
      return [];
    }

    if (!isSequence) {
      if (videoId && videoDetectionMap[videoId]) {
        return videoDetectionMap[videoId];
      }
      const allFallback = videoDetectionMap['__all__'];
      if (allFallback && allFallback.length > 0) {
        return allFallback;
      }
    }

    return allDetections;
  }, [allDetections, isSequence, selectedVideoId, videoDetectionMap, videoId, videoLoadingState]);

  const overallDetectionCount = allDetections.length;
  const activeDetectionCount = activeDetections.length;

  const activePassedDetections = activeDetections.filter(d => d?.passed || d?.result === 'pass').length;
  // Calculate detection latency from individual detection events (fallback)
  const activeAvgLatency = activeDetectionCount > 0
    ? activeDetections.reduce((sum, d) => {
        const rawLatency =
          (d as any)?.real_latency_ms ??
          (d as any)?.actualLatencyMs ??
          (d as any)?.detection_time_ms ??
          (d as any)?.corrected_latency?.real_latency_ms ??
          0;
        const numericLatency = typeof rawLatency === 'number' ? rawLatency : Number(rawLatency) || 0;
        return sum + numericLatency;
      }, 0) / activeDetectionCount
    : 0;

  // Extract real detection latency and video startup delay from enhanced results
  const detectionLatency = enhancedResults?.detection_statistics?.corrected_results?.average_real_latency_ms ?? activeAvgLatency;
  const videoStartupDelay = enhancedResults?.video_timing?.startup_delay_ms;

  const activeMatchedCount = activeDetections.filter(d => (d as any)?.ground_truth_match_id || (d as any)?.groundTruthMatchId).length;
  const activeGroundTruthCount = selectedVideoId
    ? (videoGroundTruthMap[selectedVideoId]?.length ?? groundTruthEvents.length)
    : groundTruthEvents.length;
  const activeExpectedCount = activeGroundTruthCount || activeDetectionCount;
  const activeMatchRate = activeExpectedCount > 0 ? (activeMatchedCount / activeExpectedCount) * 100 : 0;

  const overallCorrectedStats = enhancedResults?.detection_statistics?.corrected_results as any;
  // Latency-based pass/fail metrics for the banner
  // GT metrics (TP/FP/FN, F1, Precision, Recall) are shown in dual_evaluation section
  const overallPassedDetections = overallCorrectedStats?.passed_detections ?? allDetections.filter(d => d?.passed || d?.result === 'pass').length;
  const overallFailedDetections = overallCorrectedStats?.failed_detections ?? Math.max(0, overallDetectionCount - overallPassedDetections);
  const overallPassRate = sequenceResults?.overallPassRate
    ?? sequenceResults?.overall_pass_rate
    ?? overallCorrectedStats?.pass_rate
    ?? (overallDetectionCount > 0 ? (overallPassedDetections / overallDetectionCount) * 100 : 0);

  // GT comparison for accuracy metrics
  const gtComparisonForStats = enhancedResults?.ground_truth_comparison;
  const hasGtMetrics = Boolean(gtComparisonForStats && gtComparisonForStats.ground_truth_events_available > 0);

  // Extract Ground Truth Comparison Metrics
  // CRITICAL: This uses backend's pre-calculated ground_truth_comparison object
  // Backend calculates correct TP/FP/FN from ground truth matching
  const gtComparison = enhancedResults?.ground_truth_comparison;
  const hasGroundTruth = Boolean(gtComparison && gtComparison.ground_truth_events_available > 0);

  console.log('[HILResults] Single video ground truth comparison from backend:', gtComparison);

  const totalGroundTruthFromMap = useMemo(() => {
    if (isSequence) {
      return Object.values(videoGroundTruthMap).reduce(
        (sum, arr) => sum + (Array.isArray(arr) ? arr.length : 0),
        0
      );
    }

    if (selectedVideoId && videoGroundTruthMap[selectedVideoId]) {
      return videoGroundTruthMap[selectedVideoId]?.length ?? 0;
    }

    return groundTruthEvents.length;
  }, [isSequence, videoGroundTruthMap, groundTruthEvents, selectedVideoId]);

  // CRITICAL: Backend ground_truth_events_available is authoritative (total GT events, e.g., 131)
  // totalGroundTruthFromMap counts matched events from arrays (e.g., 65 TPs), NOT total GT
  // Always prefer backend value when available for correct recall denominator
  const totalGroundTruth = gtComparison?.ground_truth_events_available || totalGroundTruthFromMap || 0;

  const precision = gtComparison?.precision ?? 0;
  // FIXED: Read from accuracyRecall (decimal 0-1) and convert to percentage
  // Backend stores recall as decimal in accuracyRecall field
  // If gtComparison.recall exists (as percentage), use it directly
  // Otherwise, fallback to accuracyRecall * 100 to convert decimal to percentage
  const recall = gtComparison?.recall ?? ((enhancedResults as any)?.accuracyRecall ? (enhancedResults as any).accuracyRecall * 100 : 0);
  const f1Score = gtComparison?.f1_score ?? 0;
  const truePositives = gtComparison?.true_positives ?? 0;
  const falsePositives = gtComparison?.false_positives ?? 0;
  const falseNegatives = gtComparison?.false_negatives ?? 0;

  const overallExpectedCount = totalGroundTruth > 0 ? totalGroundTruth : overallDetectionCount;
  const overallMatchRate = gtComparison?.precision ?? (overallDetectionCount > 0 ? (overallPassedDetections / overallDetectionCount) * 100 : 0);

  const aggregateMetrics = (sequenceResults?.aggregateMetrics ?? sequenceResults?.aggregate_metrics ?? {}) as Record<string, any>;
  const latencyThresholdMs =
    aggregateMetrics.max_latency_threshold_ms ??
    aggregateMetrics.maxLatencyThresholdMs ??
    aggregateMetrics.maxLatencyMs ??
    (allDetections[0]?.threshold_ms ?? null);

  const dualEvaluation = enhancedResults?.dual_evaluation ?? enhancedResults?.dualEvaluation ?? null;
  const accuracyStatus = normalizeResultStatus(dualEvaluation?.accuracy?.result);
  const latencyStatus = normalizeResultStatus(dualEvaluation?.latency?.result);
  const overallStatus = normalizeResultStatus(dualEvaluation?.overall?.result);

  const testPassed = overallStatus ? overallStatus === 'PASS' : overallFailedDetections === 0;
  const criteriaBaseText = latencyThresholdMs
    ? `Pass if corrected latency ≤ ${latencyThresholdMs}ms`
    : 'Pass if all detections meet latency tolerance';
  const fallbackCriteriaText = overallFailedDetections > 0
    ? `${criteriaBaseText} • ${overallFailedDetections} detection(s) exceeded the limit`
    : criteriaBaseText;
  const criteriaText = dualEvaluation
    ? `Accuracy ${formatStatusLabel(accuracyStatus)} • Latency ${formatStatusLabel(latencyStatus)}`
    : fallbackCriteriaText;

  const accuracyF1Display = dualEvaluation?.accuracy?.f1Score != null
    ? formatPercentageDisplay(dualEvaluation.accuracy.f1Score, true)
    : null;
  const latencyMeanDisplay = dualEvaluation?.latency?.meanLatencyMs != null
    ? `${dualEvaluation.latency.meanLatencyMs.toFixed(1)} ms`
    : null;
  const latencyPercentDisplay = dualEvaluation?.latency
    ? formatPercentageDisplay(dualEvaluation.latency.withinTolerancePercent ?? null, false)
    : null;

  const selectedVideoSummary = useMemo(() => {
    if (!selectedVideoId) {
      return null;
    }
    return effectivePerVideoSummaries.find(
      (video) => (video.videoId ?? video.video_id) === selectedVideoId
    ) ?? null;
  }, [effectivePerVideoSummaries, selectedVideoId]);

  const videoTabs = useMemo(() => {
    if (!isSequence) return [];
    return effectivePerVideoSummaries
      .map((video, index) => {
        const id = video.videoId ?? video.video_id;
        if (!id) return null;

        const name =
          video.videoName ??
          video.video_name ??
          `Video ${(video.sequenceIndex ?? video.sequence_index ?? video.videoNumber ?? video.video_number ?? index) + 1}`;

        const detectionCount =
          video.detectionCount ??
          video.detection_count ??
          video.total_detections ??
          (videoDetectionMap[id]?.length ?? 0);

        const statusRaw = (video.passFail ?? video.pass_fail ?? video.status ?? '') as string;
        const normalizedStatus = typeof statusRaw === 'string' ? statusRaw.toLowerCase() : '';
        const status: 'pass' | 'fail' | 'pending' =
          normalizedStatus === 'pass' ? 'pass' : normalizedStatus === 'fail' ? 'fail' : 'pending';

        return { id, name, detectionCount, status };
      })
      .filter(Boolean) as Array<{ id: string; name: string; detectionCount: number; status: 'pass' | 'fail' | 'pending'; }>;
  }, [isSequence, effectivePerVideoSummaries, videoDetectionMap]);

  const selectedVideoStatus = selectedVideoSummary
    ? (() => {
        const raw = (selectedVideoSummary.passFail ?? selectedVideoSummary.pass_fail ?? selectedVideoSummary.status ?? '') as string;
        const normalized = raw.toLowerCase?.() ?? raw;
        if (normalized === 'pass' || normalized === 'fail') {
          return normalized as 'pass' | 'fail';
        }
        return 'pending';
      })()
    : null;

  const selectedVideoStatusColor = selectedVideoStatus === 'pass' ? 'success' : selectedVideoStatus === 'fail' ? 'error' : 'warning';

  const selectedVideoPassRate = activeDetectionCount > 0 ? (activePassedDetections / activeDetectionCount) * 100 : 0;
  const selectedVideoPassChipColor = selectedVideoPassRate >= 95 ? 'success' : selectedVideoPassRate >= 80 ? 'warning' : 'error';

  // Helper functions to extract video information for detection rows
  const getVideoName = useCallback((videoId: string | undefined): string => {
    if (!videoId) return 'N/A';

    const video = effectivePerVideoSummaries.find(v =>
      (v.video_id || v.videoId) === videoId
    );

    if (!video) {
      console.warn(`Video not found in effectivePerVideoSummaries: ${videoId}`);
      return `Video ${videoId.substring(0, 8)}`;
    }

    return video.videoName
      ?? video.video_name
      ?? video.video_filename
      ?? video.videoFilename
      ?? `Video ${videoId.substring(0, 8)}`;
  }, [effectivePerVideoSummaries]);

  const getVideoSequenceNumber = useCallback((videoId: string | undefined): number => {
    if (!videoId) return 0;
    const videoIndex = effectivePerVideoSummaries.findIndex(v =>
      (v.video_id || v.videoId) === videoId
    );
    if (videoIndex === -1) return 0;
    const video = effectivePerVideoSummaries[videoIndex];
    return (video?.sequence_order || video?.sequenceOrder || video?.sequence_index || video?.sequenceIndex || videoIndex) + 1;
  }, [effectivePerVideoSummaries]);

  // Handle detection row click to open video playback popup
  const handleDetectionClick = useCallback((detection: EnhancedDetectionEvent) => {
    // Find the video URL for the detection's video_id
    const detectionVideoId = (detection as any).video_id ?? (detection as any).videoId ?? selectedVideoId ?? videoId;
    const videoUrl = availableVideos.find(v => v.id === detectionVideoId)?.url || '';

    setSelectedDetection(detection);
    setPlaybackVideoUrl(videoUrl);
    setVideoDialogOpen(true);
  }, [availableVideos, selectedVideoId, videoId]);

  // Video metadata for timeline
  const videoMetadata = useMemo(() => {
    if (selectedVideoSummary) {
      const metrics = (selectedVideoSummary.metrics ?? {}) as Record<string, any>;
      const duration =
        selectedVideoSummary.durationSeconds ??
        selectedVideoSummary.duration_seconds ??
        selectedVideoSummary.duration ??
        metrics.actual_duration ??
        metrics.expected_duration ??
        undefined;
      const fps = selectedVideoSummary.fps ?? metrics.fps ?? enhancedResults?.video_timing?.fps ?? 24;
      const filename =
        selectedVideoSummary.videoName ??
        selectedVideoSummary.video_name ??
        metrics.video_filename ??
        metrics.videoFilePath ??
        enhancedResults?.video_timing?.filename ??
        'Unknown';
      // CRITICAL FIX: Include video_start_timestamp_epoch_sec for timestamp normalization
      const videoStartEpoch =
        selectedVideoSummary.video_start_timestamp_epoch_sec ??
        (selectedVideoSummary as any).videoStartTimestampEpochSec ??
        metrics.video_start_timestamp_epoch_sec ??
        enhancedResults?.video_timing?.video_start_timestamp_epoch_sec;

      return {
        fps,
        duration,
        filename,
        video_start_timestamp_epoch_sec: videoStartEpoch
      };
    }

    return {
      fps: enhancedResults?.video_timing?.fps || 24,
      duration: enhancedResults?.video_timing?.duration,
      filename: enhancedResults?.video_timing?.filename || 'No filename',
      // CRITICAL FIX: Include video_start_timestamp_epoch_sec for timestamp normalization
      video_start_timestamp_epoch_sec: enhancedResults?.video_timing?.video_start_timestamp_epoch_sec
    };
  }, [selectedVideoSummary, enhancedResults]);

  // Hardware status
  const hardwareStatus = {
    labJackConnected: enhancedResults?.hardware_status?.labjack_connected || false,
    labJackModel: enhancedResults?.hardware_status?.model || 'Unknown'
  };

  // Loading state
  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ py: 4, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <Box textAlign="center">
          <CircularProgress size={60} />
          <Typography variant="h6" sx={{ mt: 2 }}>
            Loading HIL Test Results...
          </Typography>
        </Box>
      </Container>
    );
  }

  // Error state
  if (error) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Alert severity="error" sx={{ mb: 3 }}>
          <Typography variant="h6">Error Loading Results</Typography>
          <Typography variant="body2">{error}</Typography>
        </Alert>
        <IconButton onClick={() => navigate(-1)}>
          <ArrowBackIcon />
          <Typography sx={{ ml: 1 }}>Go Back</Typography>
        </IconButton>
      </Container>
    );
  }

  // No results state
  if (!enhancedResults) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Alert severity="warning">
          <Typography variant="h6">No Results Available</Typography>
          <Typography variant="body2">No test results found for session: {sessionId}</Typography>
        </Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <AppBar position="static" color="transparent" elevation={0} sx={{ mb: 3 }}>
        <Toolbar sx={{ px: 0 }}>
          <IconButton onClick={() => navigate(-1)} edge="start">
            <ArrowBackIcon />
          </IconButton>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexGrow: 1, ml: 2 }}>
            <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
              HIL Test Results
            </Typography>
            {isSequence && effectivePerVideoSummaries.length > 0 && (
              <Chip
                label={`${effectivePerVideoSummaries.length} Videos in Sequence`}
                color="info"
                size="medium"
                icon={<VideoLibraryIcon />}
              />
            )}
          </Box>
          <Chip
            label={realtimeEnabled ? 'Live Updates: ON' : 'Live Updates: OFF'}
            color={realtimeEnabled ? 'success' : 'default'}
            onClick={() => setRealtimeEnabled(!realtimeEnabled)}
            sx={{ cursor: 'pointer' }}
          />
        </Toolbar>
      </AppBar>

      {/* Overall Test Status Banner */}
      {/* Shows actual detection count vs expected GT count */}
      {/* TP/FP/FN are accuracy metrics shown separately in dual_evaluation */}
      <TestStatusBanner
        passed={testPassed}
        detectionCount={overallDetectionCount}
        expectedCount={overallExpectedCount}
        matchRate={overallMatchRate}
        passRate={overallPassRate}
        failedCount={overallFailedDetections}
        latencyThresholdMs={latencyThresholdMs ?? undefined}
        criteriaText={criteriaText}
        videoCount={isSequence ? effectivePerVideoSummaries.length : undefined}
        videosPassedCount={isSequence ? effectivePerVideoSummaries.filter(v => {
          // BUG FIX: Backend returns status/pass_fail fields - accept both 'pass' and 'completed'
          const status = (v.status ?? v.pass_fail ?? v.passFail ?? v.validation_result ?? '').toString().toLowerCase();
          return status === 'pass' || status === 'completed';
        }).length : undefined}
      />

      {dualEvaluation && (
        <Paper elevation={1} sx={{ mb: 3, p: 2 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
            Accuracy vs Latency Evaluation
          </Typography>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
            <Chip
              label={`Accuracy: ${formatStatusLabel(accuracyStatus)}${accuracyF1Display ? ` • F1 ${accuracyF1Display}` : ''}`}
              color={statusToChipColor(accuracyStatus)}
              sx={{ fontWeight: 600 }}
            />
            <Chip
              label={`Latency: ${formatStatusLabel(latencyStatus)}${latencyMeanDisplay ? ` • μ ${latencyMeanDisplay}` : ''}${latencyPercentDisplay ? ` • ${latencyPercentDisplay} within` : ''}`}
              color={statusToChipColor(latencyStatus)}
              sx={{ fontWeight: 600 }}
            />
            <Chip
              label={`Overall: ${formatStatusLabel(overallStatus)}`}
              color={statusToChipColor(overallStatus)}
              sx={{ fontWeight: 600 }}
            />
          </Stack>
        </Paper>
      )}

      {/* Approval Panel - Shows after test completion */}
      {enhancedResults.status === 'completed' && (
        <ApprovalPanel
          sessionId={sessionId as string}
          approvalStatus={(enhancedResults.approvalStatus as 'pending' | 'approved' | 'rejected') || 'pending'}
          approvedBy={enhancedResults.approvedBy}
          approvedAt={enhancedResults.approvedAt}
          approvalComments={enhancedResults.approvalComments}
          rejectionReason={enhancedResults.rejectionReason}
          onApprovalChange={(status: string) => {
            setEnhancedResults(prev => ({
              ...prev,
              approvalStatus: status
            }));
          }}
        />
      )}

      {/* Aggregated Metrics for Multi-Video Sequences */}
      {isSequence && sequenceResults && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom sx={{ fontWeight: 'bold' }}>
            Aggregated Across All Videos
          </Typography>

          {aggOverallDetectionCount > 0 && (
            <Alert severity={aggOverallPassRate >= 90 ? 'success' : 'warning'} sx={{ mb: 2 }}>
              <AlertTitle>
                {aggOverallPassRate >= 90 ? '✓ TEST PASSED' : '⚠ TEST NEEDS REVIEW'}
              </AlertTitle>
              {videosPassed}/{totalVideos} videos passed • {aggOverallDetectionCount} detections •
              Pass rate: {aggOverallPassRate.toFixed(1)}% • Avg latency: {aggAverageLatencyMs.toFixed(1)}ms
            </Alert>
          )}

          {/* FIX #5: Add video comparison table showing all videos side-by-side */}
          {effectivePerVideoSummaries.length > 1 && (
            <TableContainer component={Paper} sx={{ mb: 2 }}>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ bgcolor: 'grey.100' }}>
                    <TableCell sx={{ fontWeight: 'bold' }}>Video</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }} align="center">Status</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }} align="center">Detections</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }} align="center">F1 Score</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }} align="center">Precision</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }} align="center">Recall</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }} align="center">Avg Latency</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {effectivePerVideoSummaries.map((video, index) => {
                    const videoName = video.video_name ?? video.videoName ?? `Video ${index + 1}`;
                    const statusRaw = (video.status ?? video.pass_fail ?? video.passFail ?? 'pending').toString().toLowerCase();
                    const status = statusRaw === 'pass' ? 'completed' : statusRaw === 'fail' ? 'failed' : statusRaw;
                    const detections = video.total_detections ?? video.totalDetections ?? 0;
                    const gtMetrics = video.ground_truth_comparison ?? video.groundTruthComparison ?? video.ground_truth_metrics ?? {};
                    const f1 = gtMetrics.f1_score ?? gtMetrics.f1Score ?? 0;
                    const precision = gtMetrics.precision ?? 0;
                    const recall = gtMetrics.recall ?? 0;
                    const avgLatency = video.average_latency_ms ?? video.averageLatencyMs ?? 0;

                    return (
                      <TableRow key={video.video_id ?? video.videoId ?? index} hover>
                        <TableCell>{videoName}</TableCell>
                        <TableCell align="center">
                          <Chip
                            label={status.toUpperCase()}
                            size="small"
                            color={status === 'completed' ? 'success' : status === 'failed' ? 'error' : 'warning'}
                          />
                        </TableCell>
                        <TableCell align="center">{detections}</TableCell>
                        <TableCell align="center" sx={{ fontWeight: 'bold', color: f1 >= 80 ? 'success.main' : f1 >= 60 ? 'warning.main' : 'error.main' }}>
                          {f1 > 0 ? `${f1.toFixed(1)}%` : 'N/A'}
                        </TableCell>
                        <TableCell align="center">{precision > 0 ? `${precision.toFixed(1)}%` : 'N/A'}</TableCell>
                        <TableCell align="center">{recall > 0 ? `${recall.toFixed(1)}%` : 'N/A'}</TableCell>
                        <TableCell align="center">{avgLatency > 0 ? `${avgLatency.toFixed(1)}ms` : 'N/A'}</TableCell>
                      </TableRow>
                    );
                  })}
                  {/* Aggregated totals row */}
                  <TableRow sx={{ bgcolor: 'info.light', fontWeight: 'bold' }}>
                    <TableCell sx={{ fontWeight: 'bold' }}>TOTAL (All Videos)</TableCell>
                    <TableCell align="center">
                      <Chip
                        label={`${videosPassed}/${totalVideos}`}
                        size="small"
                        color={videosPassed === totalVideos ? 'success' : 'warning'}
                      />
                    </TableCell>
                    <TableCell align="center" sx={{ fontWeight: 'bold' }}>{aggOverallDetectionCount}</TableCell>
                    <TableCell align="center" sx={{ fontWeight: 'bold', color: aggregatedF1Score >= 80 ? 'success.main' : 'warning.main' }}>
                      {aggregatedF1Score.toFixed(1)}%
                    </TableCell>
                    <TableCell align="center" sx={{ fontWeight: 'bold' }}>{aggregatedPrecision.toFixed(1)}%</TableCell>
                    <TableCell align="center" sx={{ fontWeight: 'bold' }}>{aggregatedRecall.toFixed(1)}%</TableCell>
                    <TableCell align="center" sx={{ fontWeight: 'bold' }}>{aggAverageLatencyMs.toFixed(1)}ms</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
          )}

          {/* Show GT cards if we have aggregated metrics OR if any GT data exists */}
          {(aggregatedMetrics || totalTruePositives > 0 || totalFalsePositives > 0 || totalFalseNegatives > 0) && (
            <GroundTruthComparisonCards
              f1Score={aggregatedF1Score}
              precision={aggregatedPrecision}
              recall={aggregatedRecall}
              truePositives={totalTruePositives}
              falsePositives={totalFalsePositives}
              falseNegatives={totalFalseNegatives}
              title="Aggregated Across All Videos"
            />
          )}
        </Box>
      )}

      {/* Sequence Timeline */}
      {isSequence && sequenceResults?.per_video_results && (
        <Card sx={{ mb: 3 }} elevation={2}>
          <CardContent>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 'bold' }}>
              📊 Multi-Video Sequence Overview
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2, gap: 0.5 }}>
              {sequenceResults.per_video_results.map((video, index) => {
                const duration = video.duration_seconds ?? video.durationSeconds ?? 1;
                const status = (video.status ?? video.pass_fail ?? video.passFail ?? 'pending').toString().toLowerCase();
                const videoName = video.video_name ?? video.videoName ?? `V${index + 1}`;

                return (
                  <Box
                    key={video.video_id ?? video.videoId ?? index}
                    sx={{
                      flex: duration,
                      minWidth: 60,
                      height: 50,
                      bgcolor: status === 'pass' ? 'success.light' : status === 'fail' ? 'error.light' : 'warning.light',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 1,
                      position: 'relative',
                      '&:hover': {
                        bgcolor: status === 'pass' ? 'success.main' : status === 'fail' ? 'error.main' : 'warning.main',
                        color: 'white',
                        cursor: 'pointer',
                        transform: 'scale(1.05)',
                        zIndex: 1,
                        transition: 'all 0.2s'
                      }
                    }}
                    title={`${videoName}\n${duration.toFixed(1)}s\nStatus: ${status}`}
                  >
                    <Typography variant="caption" fontWeight="bold">
                      V{index + 1}
                    </Typography>
                    <Typography variant="caption" sx={{ fontSize: '0.65rem' }}>
                      {duration.toFixed(1)}s
                    </Typography>
                  </Box>
                );
              })}
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Total Duration: {(sequenceResults.sequence_duration_seconds ?? sequenceResults.sequenceDurationSeconds ?? 0).toFixed(1)}s
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Avg Latency: {aggAverageLatencyMs.toFixed(1)}ms
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Worst: {aggWorstLatencyMs.toFixed(1)}ms
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Best: {aggBestLatencyMs > 0 ? aggBestLatencyMs.toFixed(1) : 'N/A'}ms
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* GROUND TRUTH COMPARISON - PRIMARY DISPLAY (Both single and multi-video) */}
      {hasGroundTruth && (
        <GroundTruthComparisonCards
          precision={isSequence ? aggregatedPrecision : precision}
          recall={isSequence ? aggregatedRecall : recall}
          f1Score={isSequence ? aggregatedF1Score : f1Score}
          truePositives={isSequence ? totalTruePositives : truePositives}
          falsePositives={isSequence ? totalFalsePositives : falsePositives}
          falseNegatives={isSequence ? totalFalseNegatives : falseNegatives}
          totalGroundTruth={isSequence ? overallGroundTruthCount : totalGroundTruth}
        />
      )}

      {/* Signal Quality Metrics - SECONDARY */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom sx={{ fontWeight: 'bold', color: 'text.secondary' }}>
          Signal Quality Metrics
        </Typography>
        <MetricsSummaryCards
          detections={activeDetectionCount}
          expected={activeExpectedCount}
          avgLatency={activeAvgLatency}
          matchRate={activeMatchRate}
          hardwareStatus={hardwareStatus}
          detectionLatency={detectionLatency}
          videoStartupDelay={videoStartupDelay}
        />
      </Box>

      {/* Video Selector Dropdown (for multi-video sequences) */}
      {isSequence && videoTabs.length > 0 && (
        <Paper sx={{ mb: 3, p: 2 }} elevation={2}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: '120px' }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                Select Video:
              </Typography>
              <Tooltip title={`Multi-video test sequence with ${effectivePerVideoSummaries.length} videos`}>
                <InfoIcon fontSize="small" color="action" sx={{ cursor: 'help' }} />
              </Tooltip>
            </Box>
            <FormControl fullWidth>
              <Select
                value={selectedVideoId ?? (videoTabs[0]?.id ?? '')}
                onChange={(e) => {
                  const newVideoId = e.target.value;
                  setSelectedVideoId(newVideoId);
                  handleVideoTabChange(null as any, newVideoId);
                }}
                displayEmpty
                sx={{ backgroundColor: 'background.paper' }}
              >
                {/* FIX #1: Add "All Videos (Aggregated)" option */}
                <MenuItem value="__all__">
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                    <Box>
                      <Typography variant="body2" fontWeight="bold">
                        All Videos (Aggregated)
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {aggOverallDetectionCount} total detections • {aggAverageLatencyMs.toFixed(1)}ms avg latency
                      </Typography>
                    </Box>
                    <Chip
                      label={`${videosPassed}/${totalVideos} PASSED`}
                      size="small"
                      color={videosPassed === totalVideos ? 'success' : 'warning'}
                      sx={{ height: 24, fontSize: '0.7rem' }}
                    />
                  </Box>
                </MenuItem>
                {effectivePerVideoSummaries?.map((video, index) => {
                  const videoId = video.video_id ?? video.videoId;
                  const videoName = video.video_name ?? video.videoName ?? `Video ${index + 1}`;
                  // FIX #7: Standardize status naming to 'playing', 'completed', 'failed'
                  const statusRaw = (video.status ?? video.pass_fail ?? video.passFail ?? 'pending').toString().toLowerCase();
                  const status = statusRaw === 'pass' ? 'completed' : statusRaw === 'fail' ? 'failed' : statusRaw === 'playing' ? 'playing' : 'pending';
                  const totalDet = video.actual_detection_count ?? video.total_detections ?? video.totalDetections ?? video.detection_count ?? video.detectionCount ?? 0;
                  const expectedDet = video.expected_detection_count ?? video.expectedDetectionCount ?? 0;
                  const avgLatency = video.average_latency_ms ?? video.avg_latency_ms ?? video.averageLatencyMs ?? 0;

                  return (
                    <MenuItem
                      key={videoId ?? index}
                      value={videoId ?? ''}
                    >
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                        <Box>
                          <Typography variant="body2" fontWeight="bold">
                            Video {index + 1}: {videoName}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {totalDet}/{expectedDet} detections • {avgLatency > 0 ? `${avgLatency.toFixed(1)}ms avg` : 'N/A'}
                          </Typography>
                        </Box>
                        <Chip
                          label={status.toUpperCase()}
                          size="small"
                          color={status === 'completed' ? 'success' : status === 'failed' ? 'error' : status === 'playing' ? 'info' : 'warning'}
                          sx={{ height: 24, fontSize: '0.7rem' }}
                        />
                      </Box>
                    </MenuItem>
                  );
                })}
              </Select>
            </FormControl>
          </Box>
        </Paper>
      )}

      {/* Video Selector for Non-Sequence Tests (Single/Available Videos) */}
      {!isSequence && availableVideos.length > 0 && (
        <Paper sx={{ mb: 3, p: 2 }} elevation={2}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 'bold', minWidth: '120px' }}>
              Select Video:
            </Typography>
            <FormControl fullWidth>
              <Select
                value={videoId || (availableVideos[0]?.id ?? '')}
                onChange={(e) => {
                  const newVideoId = e.target.value;
                  setVideoId(newVideoId);
                  setSelectedVideoId(newVideoId);
                  // Reload ground truth and detections for new video
                  loadGroundTruthData(newVideoId);
                  loadDetectionsForVideo(newVideoId);
                }}
                displayEmpty
                sx={{ backgroundColor: 'background.paper' }}
              >
                {availableVideos.map((video, index) => (
                  <MenuItem key={video.id} value={video.id}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body2">
                        {index + 1}. {video.filename}
                      </Typography>
                    </Box>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        </Paper>
      )}

      {(isSequence && selectedVideoId) && (
        <Box sx={{ mb: 3 }}>
          <Stack direction="row" spacing={1} flexWrap="wrap">
            <Chip label={`Detections: ${activeDetectionCount}`} variant="outlined" />
            <Chip
              label={`Pass rate: ${selectedVideoPassRate.toFixed(1)}%`}
              color={selectedVideoPassChipColor}
              variant="outlined"
            />
            {selectedVideoStatus && (
              <Chip
                label={`Status: ${selectedVideoStatus.toUpperCase()}`}
                color={selectedVideoStatusColor}
                variant="outlined"
              />
            )}
          </Stack>

          {/* Per-Video Ground Truth Metrics */}
          {/* CRITICAL FIX: For single-video sessions or when only 1 video exists, use session-level ground_truth_comparison
              which has correct metrics (131 GT, 66 FN). The per_video_results.ground_truth_metrics has wrong values
              because backend queries GT objects per video_id instead of session-level totals. */}
          {selectedVideoSummary?.ground_truth_metrics && (
            <Box sx={{ mt: 3 }}>
              {(() => {
                // Use session-level metrics when only 1 video (per-video metrics are incorrect for single-video sessions)
                const isSingleVideo = effectivePerVideoSummaries.length <= 1;
                const sessionGt = enhancedResults?.ground_truth_comparison;
                const useSessionMetrics = isSingleVideo && sessionGt && sessionGt.ground_truth_events_available > 0;

                const metrics = useSessionMetrics ? {
                  precision: sessionGt.precision ?? 0,
                  recall: sessionGt.recall ?? 0,
                  f1_score: sessionGt.f1_score ?? 0,
                  true_positives: sessionGt.true_positives ?? 0,
                  false_positives: sessionGt.false_positives ?? 0,
                  false_negatives: sessionGt.false_negatives ?? 0,
                  total_ground_truth: sessionGt.ground_truth_events_available ?? 0
                } : selectedVideoSummary.ground_truth_metrics;

                return (
                  <GroundTruthComparisonCards
                    precision={metrics.precision ?? 0}
                    recall={metrics.recall ?? 0}
                    f1Score={metrics.f1_score ?? metrics.f1Score ?? 0}
                    truePositives={metrics.true_positives ?? metrics.truePositives ?? 0}
                    falsePositives={metrics.false_positives ?? metrics.falsePositives ?? 0}
                    falseNegatives={metrics.false_negatives ?? metrics.falseNegatives ?? 0}
                    totalGroundTruth={metrics.total_ground_truth ?? metrics.totalGroundTruth}
                    title={`Ground Truth Metrics - ${selectedVideoSummary.videoName ?? selectedVideoSummary.video_name ?? 'Selected Video'}`}
                  />
                );
              })()}
            </Box>
          )}
        </Box>
      )}

      {/* Timeline Visualization */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom sx={{ fontWeight: 'bold' }}>
          Detection Timeline
        </Typography>
        <FrameCorrelationTimeline
          detectionEvents={activeDetections}
          groundTruthEvents={groundTruthEvents}
          videoMetadata={videoMetadata}
        />
      </Box>

      {/* Single Clean Detection Table */}
      <Paper sx={{ mb: 3 }} elevation={2}>
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', bgcolor: 'primary.50' }}>
          <Typography variant="h6" fontWeight="bold">
            Detection Events ({activeDetectionCount} total)
          </Typography>
          <Typography variant="body2" color="textSecondary">
            {isSequence && selectedVideoSummary
              ? `Showing detection events for ${selectedVideoSummary.videoName ?? selectedVideoSummary.video_name ?? 'selected video'}`
              : 'Showing all detection events captured during the test'}
          </Typography>
        </Box>
        <TableContainer sx={{ maxHeight: 600 }}>
          <Table stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 'bold' }}>#</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>Video</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>
                  <Tooltip title="Detection source: LabJack (hardware), AI model, or manual">
                    <span style={{ cursor: 'help', borderBottom: '1px dotted' }}>Source</span>
                  </Tooltip>
                </TableCell>
                {/* FIX #6: Add clear timestamp column headers */}
                <TableCell sx={{ fontWeight: 'bold' }}>
                  <Tooltip title={isSequence ? "Time relative to the start of this specific video" : "Time from video start"}>
                    <span style={{ cursor: 'help', borderBottom: '1px dotted' }}>Video Time (s)</span>
                  </Tooltip>
                </TableCell>
                {isSequence && (
                  <TableCell sx={{ fontWeight: 'bold' }}>
                    <Tooltip title="Time relative to the start of the entire multi-video sequence">
                      <span style={{ cursor: 'help', borderBottom: '1px dotted' }}>Sequence Time (s)</span>
                    </Tooltip>
                  </TableCell>
                )}
                <TableCell sx={{ fontWeight: 'bold' }}>Voltage (V)</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>
                  Latency (ms)
                  {/* FIX #3: Add tooltip explaining Frame 0 / artificial 10s latency */}
                  <Tooltip title="Real latency from detection to trigger. Values >5000ms indicate detections outside video window (Frame 0 - assigned artificial 10s latency).">
                    <span style={{ marginLeft: 4, cursor: 'help' }}>ⓘ</span>
                  </Tooltip>
                </TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>Matched GT</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>Result</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {/* BUG FIX: Show loading spinner while video data is being fetched */}
              {videoLoadingState[selectedVideoId ?? ''] ? (
                <TableRow>
                  <TableCell colSpan={isSequence ? 9 : 8} align="center">
                    <Box sx={{ py: 5, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                      <CircularProgress size={40} />
                      <Typography color="textSecondary">
                        Loading detections for {selectedVideoId ? `Video ${getVideoSequenceNumber(selectedVideoId)}` : 'selected video'}...
                      </Typography>
                    </Box>
                  </TableCell>
                </TableRow>
              ) : activeDetections.length > 0 ? (
                (() => {
                  // FIX #2: Group detections by video_id for visual separation
                  const groupedDetections = isSequence && selectedVideoId === '__all__'
                    ? activeDetections.reduce((acc, detection) => {
                        const videoId = (detection as any).video_id || (detection as any).videoId || '__unknown__';
                        if (!acc[videoId]) acc[videoId] = [];
                        acc[videoId].push(detection);
                        return acc;
                      }, {} as Record<string, typeof activeDetections>)
                    : { '__single__': activeDetections };

                  const rows: JSX.Element[] = [];
                  let globalIndex = 0;

                  Object.entries(groupedDetections).forEach(([videoId, detections], groupIndex) => {
                    // Add separator row between video groups
                    if (isSequence && selectedVideoId === '__all__' && groupIndex > 0) {
                      rows.push(
                        <TableRow key={`separator-${videoId}`}>
                          <TableCell colSpan={isSequence ? 8 : 7} sx={{ bgcolor: 'grey.100', py: 0.5 }}>
                            <Divider sx={{ borderStyle: 'dashed', borderWidth: 1 }} />
                          </TableCell>
                        </TableRow>
                      );
                    }

                    // Add video header row if showing all videos
                    if (isSequence && selectedVideoId === '__all__' && videoId !== '__unknown__') {
                      rows.push(
                        <TableRow key={`header-${videoId}`}>
                          <TableCell colSpan={isSequence ? 8 : 7} sx={{ bgcolor: 'info.light', fontWeight: 'bold', py: 1 }}>
                            {getVideoName(videoId)} ({detections.length} detections)
                          </TableCell>
                        </TableRow>
                      );
                    }

                    // Add detection rows
                    detections.forEach((detection, index) => {
                      const detectionVideoId = (detection as any).video_id || (detection as any).videoId;
                      rows.push(
                        <DetectionTableRow
                          key={detection.id || `detection-${globalIndex}`}
                          index={globalIndex}
                          detection={detection}
                          videoName={getVideoName(detectionVideoId)}
                          videoSequenceNumber={getVideoSequenceNumber(detectionVideoId)}
                          totalVideos={effectivePerVideoSummaries.length}
                          onClick={() => handleDetectionClick(detection)}
                        />
                      );
                      globalIndex++;
                    });
                  });

                  return <>{rows}</>;
                })()
              ) : (
                <TableRow>
                  <TableCell colSpan={isSequence ? 9 : 8} align="center">
                    <Typography color="textSecondary" sx={{ py: 3 }}>
                      No detection events found for this video
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* Session Information Footer */}
      <Paper sx={{ p: 2, bgcolor: 'grey.50' }} elevation={1}>
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
          <Typography variant="caption" color="textSecondary">
            Session ID: {sessionId}
            {enhancedResults?.session_info?.project_name && (
              <> • Project: {enhancedResults.session_info.project_name}</>
            )}
            {enhancedResults?.session_info?.name && (
              <> • Test: {enhancedResults.session_info.name}</>
            )}
          </Typography>
          {enhancedResults?.session_info?.configuration?.constantVoltageMode && (
            <Tooltip title="Debounce filter bypassed - 95%+ detection rate enabled. Press Ctrl+Shift+R if values don't update." arrow>
              <Chip
                icon={<InfoIcon />}
                label="🔬 Constant Voltage Mode Active"
                color="warning"
                size="small"
                variant="outlined"
              />
            </Tooltip>
          )}
        </Stack>
      </Paper>

      {/* Video Playback Dialog */}
      <Dialog
        open={videoDialogOpen}
        onClose={() => setVideoDialogOpen(false)}
        maxWidth="xl"
        fullWidth
        PaperProps={{
          sx: {
            minHeight: '80vh',
            maxHeight: '90vh'
          }
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant="h6">
              Video Playback - Detection at {selectedDetection?.timestamp?.toFixed(3) || '—'}s
            </Typography>
            {selectedDetection && (
              <Typography variant="caption" color="text.secondary">
                Latency: {(selectedDetection.real_latency_ms || selectedDetection.actualLatencyMs || 0).toFixed(1)}ms •
                Voltage: {(selectedDetection.voltage || selectedDetection.voltage_level || 0).toFixed(2)}V •
                Result: {selectedDetection.passed || selectedDetection.result === 'pass' ? 'PASS' : 'FAIL'}
              </Typography>
            )}
          </Box>
          <IconButton onClick={() => setVideoDialogOpen(false)} edge="end">
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ p: 3 }}>
          {playbackVideoUrl ? (
            <Box sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
              <video
                controls
                autoPlay
                src={playbackVideoUrl}
                style={{
                  width: '100%',
                  maxHeight: '70vh',
                  backgroundColor: '#000',
                  borderRadius: '8px'
                }}
                onLoadedMetadata={(e) => {
                  // Seek to the detection timestamp when video loads
                  if (selectedDetection?.timestamp && e.currentTarget) {
                    e.currentTarget.currentTime = selectedDetection.timestamp;
                  }
                }}
              />
              <Alert severity="info" sx={{ mt: 2 }}>
                <Typography variant="body2">
                  Video will start at the detection timestamp ({selectedDetection?.timestamp?.toFixed(3) || '—'}s).
                  Use the video controls to review the detection event.
                </Typography>
              </Alert>
            </Box>
          ) : (
            <Alert severity="warning">
              <AlertTitle>Video Not Available</AlertTitle>
              <Typography variant="body2">
                Unable to load video for this detection. The video file may not be accessible.
              </Typography>
            </Alert>
          )}
        </DialogContent>
      </Dialog>

    </Container>
  );
};

export default HILResults;
