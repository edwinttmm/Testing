import { EnhancedDetectionEvent, PerVideoResult, VideoSequenceResults } from '../types/enhanced-results';

type DetectionLike = Record<string, unknown>;

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

export const toNumber = (value: unknown): number | undefined => {
  if (isFiniteNumber(value)) {
    return value;
  }

  if (value instanceof Date) {
    return value.getTime() / 1000;
  }

  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) {
      return undefined;
    }

    const numeric = Number(trimmed);
    if (!Number.isNaN(numeric) && Number.isFinite(numeric)) {
      return numeric;
    }

    const dateParsed = Date.parse(trimmed);
    if (!Number.isNaN(dateParsed)) {
      return dateParsed / 1000;
    }
  }

  return undefined;
};

const toInt = (value: unknown): number | undefined => {
  const numeric = toNumber(value);
  if (numeric === undefined) {
    return undefined;
  }
  if (!Number.isFinite(numeric)) {
    return undefined;
  }
  return Math.trunc(numeric);
};

const ensureNonNegative = (value: number | undefined): number | undefined => {
  if (value === undefined) {
    return undefined;
  }
  return value < 0 ? 0 : value;
};

const coerceStatus = (value: unknown): string | undefined => {
  if (typeof value === 'string') {
    return value.toLowerCase();
  }
  return undefined;
};

const normalizeResultStatus = (
  rawStatus: string | undefined,
  passRatePercent: number | undefined,
  totalDetections: number
): 'pass' | 'fail' | 'partial' | 'pending' => {
  if (rawStatus) {
    if (rawStatus === 'pass' || rawStatus === 'fail' || rawStatus === 'pending' || rawStatus === 'partial') {
      return rawStatus;
    }
    if (rawStatus === 'completed' && passRatePercent !== undefined && totalDetections >= 0) {
      return passRatePercent >= 99.9 ? 'pass' : passRatePercent <= 0 && totalDetections > 0 ? 'fail' : 'partial';
    }
    if (rawStatus === 'failed' || rawStatus === 'error') {
      return 'fail';
    }
  }

  if (passRatePercent !== undefined && totalDetections > 0) {
    if (passRatePercent >= 99.9) {
      return 'pass';
    }
    if (passRatePercent <= 0) {
      return 'fail';
    }
    return 'partial';
  }

  return 'pending';
};

export const formatSeconds = (value?: number): string => {
  if (!isFiniteNumber(value) || value < 0) {
    return '00:00:00';
  }

  const wholeSeconds = Math.floor(value);
  const hours = Math.floor(wholeSeconds / 3600);
  const minutes = Math.floor((wholeSeconds % 3600) / 60);
  const seconds = wholeSeconds % 60;

  const components = [hours, minutes, seconds].map((component) => component.toString().padStart(2, '0'));
  return components.join(':');
};

export const normalizeDetectionEvent = (event: any, index: number): EnhancedDetectionEvent => {
  const source: DetectionLike = event ?? {};

  const confidenceScore =
    source.confidence ??
    source.confidence_score ??
    source.detection_confidence ??
    source.match_confidence ??
    undefined;

  const timestampCandidate =
    source.timestamp ??
    source.time ??
    source.unix_timestamp ??
    source.video_relative_timestamp ??
    source.detection_timestamp ??
    undefined;

  let timestamp = toNumber(timestampCandidate);

  if (timestamp === undefined && typeof source.timestamp_iso === 'string') {
    const parsed = Date.parse(source.timestamp_iso);
    if (!Number.isNaN(parsed)) {
      timestamp = parsed / 1000;
    }
  }

  if (timestamp === undefined && typeof source.frame_number === 'number' && source.frame_number >= 0) {
    const fps = toNumber(source.fps ?? source.frame_rate ?? 24) ?? 24;
    if (fps > 0) {
      timestamp = source.frame_number / fps;
    }
  }

  if (timestamp === undefined) {
    timestamp = index;
  }

  // UNIFIED LATENCY FIELD RESOLUTION
  // actual_latency_ms is the canonical field - always prefer it
  // Legacy fields are fallbacks for backward compatibility only
  const realLatency = toNumber(
    source.actual_latency_ms ??       // PRIMARY: Canonical field
      source.actualLatencyMs ??        // Camel case variant
      // LEGACY FALLBACKS (for old data compatibility only)
      source.latency_ms ??
      source.real_latency_ms ??
      source.detection_latency_ms
  );

  const detectionTimeMs = toNumber(source.detection_time_ms);

  const voltageLevel = toNumber(
    source.voltage_level ?? source.voltage ?? source.signal_value ?? source.signalValue ?? source.labjack_voltage
  );

  const rawResult = coerceStatus(
    source.result ?? source.validation_result ?? source.pass_fail ?? source.status ?? source.outcome
  );

  const videoIdValue = (
    source.video_id ??
    source.videoId ??
    source.active_video_id ??
    source.activeVideoId ??
    source.sequence_video_id ??
    source.sequenceVideoId
  ) as
    | string
    | undefined;
  const sequenceVideoResultIdValue = (
    source.sequence_video_result_id ??
    source.sequenceVideoResultId ??
    source.active_sequence_video_result_id ??
    source.activeSequenceVideoResultId
  ) as
    | string
    | undefined;

  const passed =
    typeof source.passed === 'boolean'
      ? source.passed
      : rawResult === 'pass'
        ? true
        : rawResult === 'fail'
          ? false
          : undefined;

  const normalizedResult: 'pass' | 'fail' | 'pending' =
    rawResult === 'pass' || rawResult === 'fail'
      ? rawResult
      : passed === undefined
        ? 'pending'
        : passed
          ? 'pass'
          : 'fail';

  const id =
    source.id ??
    source.event_id ??
    source.detection_id ??
    source.detectionId ??
    source.uuid ??
    source.identifier ??
    `detection-${index}`;

  // UNIFIED LATENCY FIELD - actual_latency_ms is the single source of truth
  const latencyMs = toNumber(
    source.actual_latency_ms ??       // PRIMARY: Always use this
    source.actualLatencyMs ??          // Camel case variant
    // LEGACY FALLBACKS (for backward compatibility only)
    source.latency_ms ??
    source.real_latency_ms
  );

  // NEW BACKEND FIELDS (Issue #2 - Agent 1)
  const sequenceId = source.sequence_id ?? source.sequenceId ?? undefined;
  const sequenceVideoResultId = source.sequence_video_result_id ?? source.sequenceVideoResultId ?? undefined;

  const videoRelativeTimestamp = toNumber(
    source.video_relative_timestamp ??
    source.videoRelativeTimestamp ??
    source.relative_timestamp ??
    source.relativeTimestamp
  );

  const frameNumber = toInt(
    source.frame_number ??
    source.frameNumber ??
    source.video_frame ??
    source.videoFrame ??
    source.video_frame_number
  );

  return {
    ...(source as object),
    id,
    timestamp,
    latency_ms: latencyMs ?? realLatency ?? detectionTimeMs,
    detection_time_ms: detectionTimeMs ?? realLatency ?? toNumber(source.processing_time_ms),
    real_latency_ms: realLatency,
    actualLatencyMs: source.actualLatencyMs ?? source.actual_latency_ms ?? realLatency ?? undefined,
    actual_latency_ms: source.actual_latency_ms ?? source.actualLatencyMs ?? realLatency ?? undefined, // NEW: Explicit mapping
    video_relative_timestamp: videoRelativeTimestamp,
    videoRelativeTimestamp: videoRelativeTimestamp,
    frame_number: frameNumber,
    frameNumber: frameNumber,
    voltage: voltageLevel,
    voltage_level: voltageLevel,
    passed,
    result: normalizedResult,
    ground_truth_match_id:
      source.ground_truth_match_id ?? source.groundTruthMatchId ?? source.match_id ?? source.matchId ?? null,
    validation_result: source.validation_result ?? source.validationResult ?? undefined,
    confidence: confidenceScore,
    video_id: videoIdValue,
    videoId: videoIdValue,
    sequence_video_result_id: sequenceVideoResultIdValue,
    sequenceVideoResultId: sequenceVideoResultIdValue,
    // NEW BACKEND FIELDS (Issue #2 - Agent 1)
    sequence_id: sequenceId,      // NEW: Video sequence identifier
    sequenceId: sequenceId        // Camel case variant
  } as EnhancedDetectionEvent;
};

export const normalizeDetectionEvents = (events: any[] | undefined | null): EnhancedDetectionEvent[] => {
  if (!Array.isArray(events) || events.length === 0) {
    return [];
  }
  return events.map((event, index) => normalizeDetectionEvent(event, index));
};

export const isDetectionLikeObject = (value: any): boolean => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false;
  }

  const keys = Object.keys(value).map((key) => key.toLowerCase());
  const indicatorKeys = [
    'real_latency',
    'latency',
    'voltage',
    'labjack',
    'threshold',
    'channel',
    'detection_time',
    'result',
    'passed',
    'sequence_video_id'
  ];

  return indicatorKeys.some((indicator) => keys.some((key) => key.includes(indicator)));
};

export const collectDetectionCandidates = (root: any, maxDepth = 4): any[] => {
  if (!root || typeof root !== 'object' || maxDepth < 0) {
    return [];
  }

  const seen = new WeakSet<object>();
  const collected: any[] = [];

  const traverse = (value: any, depth: number) => {
    if (!value || typeof value !== 'object' || depth > maxDepth) {
      return;
    }

    if (seen.has(value)) {
      return;
    }
    seen.add(value);

    if (Array.isArray(value)) {
      if (value.length === 0) {
        return;
      }

      const detectionItems = value.filter((item) => isDetectionLikeObject(item));
      if (detectionItems.length > 0) {
        collected.push(...detectionItems);
        return;
      }

      value.forEach((child) => traverse(child, depth + 1));
      return;
    }

    Object.values(value).forEach((child) => traverse(child, depth + 1));
  };

  traverse(root, 0);
  return collected;
};

const normalizePerVideoResult = (
  video: any,
  index: number,
  aggregateLatencyThreshold?: number
): PerVideoResult => {
  const metrics = (video?.metrics ?? video?.video_metrics ?? {}) as Record<string, unknown>;

  const videoId =
    video?.video_id ??
    video?.videoId ??
    metrics.video_id ??
    metrics.videoId ??
    metrics.id ??
    video?.id ??
    null;

  const detectionEvents = normalizeDetectionEvents(video?.detection_events ?? video?.detectionEvents ?? []);

  const detectionCount =
    ensureNonNegative(
      toInt(
        video?.detection_count ??
          video?.detectionCount ??
          metrics.actual_detection_count ??
          metrics.metadata_detection_count
      )
    ) ?? detectionEvents.length;

  const expectedDetectionCount = ensureNonNegative(
    toInt(video?.expected_detection_count ?? video?.expectedDetectionCount ?? metrics.expected_detection_count)
  );

  const passRatePercent = ensureNonNegative(
    toNumber(
      video?.pass_rate_percent ??
        video?.passRatePercent ??
        video?.pass_rate ??
        video?.passRate ??
        metrics.pass_rate_percent
    )
  );

  let passedDetections = ensureNonNegative(
    toInt(video?.passed_detections ?? video?.passedDetections ?? metrics.passed_detections)
  );

  let failedDetections = ensureNonNegative(
    toInt(video?.failed_detections ?? video?.failedDetections ?? metrics.failed_detections)
  );

  if (passedDetections === undefined && detectionEvents.length > 0) {
    const passEvents = detectionEvents.filter(
      (event) => event?.passed === true || event?.result === 'pass'
    ).length;
    const failEvents = detectionEvents.filter(
      (event) => event?.passed === false || event?.result === 'fail'
    ).length;
    if (passEvents || failEvents) {
      passedDetections = passEvents;
      failedDetections = failEvents || (detectionCount !== undefined ? Math.max(detectionCount - passEvents, 0) : 0);
    }
  }

  if (passedDetections === undefined && passRatePercent !== undefined && detectionCount !== undefined) {
    passedDetections = Math.round(detectionCount * (passRatePercent / 100));
  }

  if (failedDetections === undefined && passedDetections !== undefined && detectionCount !== undefined) {
    failedDetections = Math.max(detectionCount - passedDetections, 0);
  }

  let resolvedPassRatePercent = passRatePercent;
  if (resolvedPassRatePercent === undefined && detectionCount && passedDetections !== undefined) {
    resolvedPassRatePercent = (passedDetections / detectionCount) * 100;
  }

  // NEW BACKEND FIELDS (Issue #2 - Agent 1) - Priority order updated
  const videoStartTime =
    toNumber(
      video?.video_start_time ??        // NEW: Highest priority (from SequenceVideoResult)
        video?.videoStartTime ??         // Camel case
        video?.start_time ??             // Legacy field
        video?.startTime ??              // Legacy camel case
        metrics.video_start_time ??      // Metrics object variant
        metrics.started_at ??            // ISO timestamp fallback
        metrics.start_time
    ) ?? undefined;

  const videoEndTime =
    toNumber(
      video?.video_end_time ??          // NEW: Highest priority (from SequenceVideoResult)
        video?.videoEndTime ??           // Camel case
        video?.end_time ??               // Legacy field
        video?.endTime ??                // Legacy camel case
        metrics.video_end_time ??        // Metrics object variant
        metrics.ended_at ??              // ISO timestamp fallback
        metrics.end_time
    ) ?? undefined;

  // Keep legacy aliases for backward compatibility
  const startTime = videoStartTime;
  const endTime = videoEndTime;

  const durationSeconds =
    ensureNonNegative(
      toNumber(
        video?.duration ??
          video?.duration_seconds ??
          video?.durationSeconds ??
          metrics.actual_duration ??
          metrics.expected_duration ??
          video?.expected_duration
      )
    ) ?? (startTime !== undefined && endTime !== undefined ? Math.max(endTime - startTime, 0) : undefined);

  const startedAtIso =
    (video?.started_at_iso ??
      video?.startedAtIso ??
      metrics.started_at_iso ??
      metrics.start_time_iso ??
      metrics.video_started_at_iso) ??
    undefined;

  const endedAtIso =
    (video?.ended_at_iso ??
      video?.endedAtIso ??
      metrics.ended_at_iso ??
      metrics.end_time_iso ??
      metrics.video_ended_at_iso) ??
    undefined;

  const fps =
    toNumber(video?.fps ?? metrics.fps ?? video?.frame_rate ?? metrics.frame_rate ?? metrics.video_fps) ?? undefined;

  const latencyThreshold =
    toNumber(video?.latency_threshold_ms ?? video?.latencyThresholdMs ?? metrics.latency_threshold_ms) ??
    aggregateLatencyThreshold ??
    undefined;

  const avgLatency =
    toNumber(video?.avg_latency_ms ?? video?.avgLatencyMs ?? metrics.avg_latency_ms ?? metrics.average_latency_ms) ??
    undefined;
  const maxLatency =
    toNumber(video?.max_latency_ms ?? video?.maxLatencyMs ?? metrics.max_latency_ms ?? metrics.maximum_latency_ms) ??
    undefined;
  const minLatency =
    toNumber(video?.min_latency_ms ?? video?.minLatencyMs ?? metrics.min_latency_ms ?? metrics.minimum_latency_ms) ??
    undefined;

  const statusRaw = coerceStatus(
    video?.status ??
      video?.video_status ??
      video?.videoStatus ??
      video?.pass_fail ??
      video?.passFail ??
      metrics.video_status ??
      metrics.validation_result
  );

  const normalizedStatus = normalizeResultStatus(statusRaw, resolvedPassRatePercent, detectionCount ?? 0);

  const sequenceIndex =
    toInt(video?.sequence_index ?? video?.sequenceIndex ?? metrics.sequence_index ?? metrics.sequence_order) ?? index;
  const videoNumber =
    toInt(video?.video_number ?? video?.videoNumber ?? metrics.video_number ?? metrics.sequence_order) ??
    sequenceIndex;

  const videoUrl =
    video?.video_url ?? video?.videoUrl ?? metrics.video_url ?? metrics.url ?? metrics.final_url ?? undefined;

  const durationFormatted =
    video?.duration_formatted ?? video?.durationFormatted ?? formatSeconds(durationSeconds ?? 0);

  const normalized: PerVideoResult = {
    ...(video ?? {}),
    metrics: {
      ...(typeof video?.metrics === 'object' ? (video.metrics as Record<string, unknown>) : {}),
      started_at_iso: startedAtIso ?? metrics.started_at_iso ?? undefined,
      ended_at_iso: endedAtIso ?? metrics.ended_at_iso ?? undefined,
      latency_threshold_ms: latencyThreshold ?? metrics.latency_threshold_ms ?? undefined,
      expected_detection_count: expectedDetectionCount ?? metrics.expected_detection_count ?? undefined,
      actual_detection_count: detectionCount ?? metrics.actual_detection_count ?? undefined,
      pass_rate_percent: resolvedPassRatePercent ?? metrics.pass_rate_percent ?? undefined,
      avg_latency_ms: avgLatency ?? metrics.avg_latency_ms ?? undefined,
      max_latency_ms: maxLatency ?? metrics.max_latency_ms ?? undefined,
      min_latency_ms: minLatency ?? metrics.min_latency_ms ?? undefined,
      passed_detections: passedDetections ?? metrics.passed_detections ?? undefined,
      failed_detections: failedDetections ?? metrics.failed_detections ?? undefined,
      video_status: normalizedStatus
    },
    video_id: videoId ?? undefined,
    videoId: videoId ?? undefined,
    video_name: video?.video_name ?? video?.videoName ?? metrics.video_filename ?? metrics.name ?? undefined,
    videoName: video?.videoName ?? video?.video_name ?? metrics.video_filename ?? metrics.name ?? undefined,
    video_url: videoUrl,
    videoUrl: videoUrl,
    start_time: startTime,
    startTime: startTime,
    end_time: endTime,
    endTime: endTime,
    // NEW BACKEND FIELDS (Issue #2 - Agent 1) - Explicit video timing
    video_start_time: videoStartTime,  // NEW: Epoch timestamp (from SequenceVideoResult)
    videoStartTime: videoStartTime,    // Camel case variant
    video_end_time: videoEndTime,      // NEW: Epoch timestamp (from SequenceVideoResult)
    videoEndTime: videoEndTime,        // Camel case variant
    started_at_iso: startedAtIso,
    startedAtIso: startedAtIso,
    ended_at_iso: endedAtIso,
    endedAtIso: endedAtIso,
    sequence_index: sequenceIndex,
    sequenceIndex: sequenceIndex,
    video_number: videoNumber !== undefined ? videoNumber + 1 : sequenceIndex + 1,
    videoNumber: videoNumber !== undefined ? videoNumber + 1 : sequenceIndex + 1,
    duration: durationSeconds,
    duration_seconds: durationSeconds,
    durationSeconds: durationSeconds,
    duration_formatted: durationFormatted,
    durationFormatted: durationFormatted,
    fps,
    total_detections: detectionCount ?? 0,
    totalDetections: detectionCount ?? 0,
    detection_count: detectionCount ?? 0,
    detectionCount: detectionCount ?? 0,
    expected_detection_count: expectedDetectionCount,
    expectedDetectionCount: expectedDetectionCount,
    actual_detection_count: detectionCount ?? undefined,
    actualDetectionCount: detectionCount ?? undefined,
    passed_detections: passedDetections ?? 0,
    passedDetections: passedDetections ?? 0,
    failed_detections: failedDetections ?? (detectionCount !== undefined && passedDetections !== undefined
      ? Math.max(detectionCount - passedDetections, 0)
      : 0),
    failedDetections: failedDetections ?? (detectionCount !== undefined && passedDetections !== undefined
      ? Math.max(detectionCount - passedDetections, 0)
      : 0),
    pass_rate: resolvedPassRatePercent,
    passRate: resolvedPassRatePercent,
    pass_rate_percent: resolvedPassRatePercent,
    passRatePercent: resolvedPassRatePercent,
    average_latency_ms: avgLatency ?? undefined,
    averageLatencyMs: avgLatency ?? undefined,
    max_latency_ms: maxLatency ?? undefined,
    maxLatencyMs: maxLatency ?? undefined,
    min_latency_ms: minLatency ?? undefined,
    minLatencyMs: minLatency ?? undefined,
    latency_threshold_ms: latencyThreshold ?? undefined,
    latencyThresholdMs: latencyThreshold ?? undefined,
    video_status: normalizedStatus,
    videoStatus: normalizedStatus,
    pass_fail: normalizedStatus,
    passFail: normalizedStatus,
    status: normalizedStatus === 'pass' || normalizedStatus === 'fail' ? normalizedStatus : undefined,
    detection_events: detectionEvents,
    detectionEvents: detectionEvents,
    // Ground truth metrics normalization - support both field name variants
    ground_truth_metrics: video?.ground_truth_metrics ?? video?.groundTruthMetrics ?? video?.ground_truth_comparison ?? {},
    groundTruthMetrics: video?.groundTruthMetrics ?? video?.ground_truth_metrics ?? video?.groundTruthComparison ?? {},
    ground_truth_comparison: video?.ground_truth_comparison ?? video?.ground_truth_metrics ?? video?.groundTruthComparison ?? {},
    groundTruthComparison: video?.groundTruthComparison ?? video?.ground_truth_comparison ?? video?.ground_truth_metrics ?? {}
  };

  return normalized;
};

export const normalizeSequenceResults = (raw: any): VideoSequenceResults | null => {
  if (!raw || typeof raw !== 'object') {
    return raw ?? null;
  }

  const aggregateMetrics =
    raw?.aggregate_metrics ??
    raw?.aggregateMetrics ??
    {};

  const fallbackLatencyThreshold = toNumber(
    aggregateMetrics.max_latency_threshold_ms ?? aggregateMetrics.maxLatencyThresholdMs
  );

  const perVideoRaw: any[] = Array.isArray(raw?.per_video_results)
    ? raw.per_video_results
    : Array.isArray(raw?.perVideoResults)
      ? raw.perVideoResults
      : [];

  const normalizedVideos = perVideoRaw.map((video, index) =>
    normalizePerVideoResult(video, index, fallbackLatencyThreshold ?? undefined)
  );

  const normalizedSequenceGroundTruth = (() => {
    const rawGT = raw?.ground_truth_comparison ?? raw?.groundTruthComparison;
    if (!rawGT || typeof rawGT !== 'object') {
      return null;
    }
    // Extract metrics directly from rawGT
    const metrics = {
      true_positives: rawGT.true_positives ?? rawGT.truePositives ?? 0,
      false_positives: rawGT.false_positives ?? rawGT.falsePositives ?? 0,
      false_negatives: rawGT.false_negatives ?? rawGT.falseNegatives ?? 0,
      total_ground_truth: rawGT.total_ground_truth ?? rawGT.totalGroundTruth ?? rawGT.ground_truth_events_available ?? 0,
      precision: rawGT.precision ?? 0,
      recall: rawGT.recall ?? 0,
      f1_score: rawGT.f1_score ?? rawGT.f1Score ?? 0
    };
    return {
      ...rawGT,
      ...metrics,
      ground_truth_events_available:
        rawGT.ground_truth_events_available ??
        rawGT.groundTruthEventsAvailable ??
        metrics.total_ground_truth
    };
  })();

  const totalVideos = raw?.total_videos ?? raw?.totalVideos ?? normalizedVideos.length;

  const videosPassed =
    raw?.videos_passed ??
    raw?.videosPassed ??
    normalizedVideos.filter((video) => (video.status ?? video.pass_fail ?? '').toString().toLowerCase() === 'pass').length;

  const videosFailed =
    raw?.videos_failed ??
    raw?.videosFailed ??
    normalizedVideos.filter((video) => (video.status ?? video.pass_fail ?? '').toString().toLowerCase() === 'fail').length;

  // CRITICAL FIX: Always calculate from per-video results first to avoid using stale/incorrect top-level values
  // Backend may return total_detections: 0 even when per-video results have actual counts
  const detectionSumFromVideos = normalizedVideos.reduce(
    (sum, video) => sum + (video.total_detections ?? video.totalDetections ?? video.detection_count ?? video.detectionCount ?? 0),
    0
  );

  const totalDetections = detectionSumFromVideos > 0
    ? detectionSumFromVideos
    : (raw?.total_detections ?? raw?.totalDetections ?? 0);

  // CRITICAL FIX: Calculate from per-video results first
  const passedSumFromVideos = normalizedVideos.reduce(
    (sum, video) => sum + (video.passed_detections ?? video.passedDetections ?? 0),
    0
  );

  const totalPassedDetections = passedSumFromVideos > 0 || normalizedVideos.length > 0
    ? passedSumFromVideos
    : (raw?.total_passed_detections ?? raw?.totalPassedDetections ?? 0);

  // CRITICAL FIX: Calculate from per-video results first
  const failedSumFromVideos = normalizedVideos.reduce(
    (sum, video) => sum + (video.failed_detections ?? video.failedDetections ?? 0),
    0
  );

  const totalFailedDetections = failedSumFromVideos > 0 || normalizedVideos.length > 0
    ? failedSumFromVideos
    : (raw?.total_failed_detections ?? raw?.totalFailedDetections ?? 0);

  const totalLatencyWeighted = normalizedVideos.reduce((sum, video) => {
    const avg = video.average_latency_ms ?? video.averageLatencyMs;
    const count = video.total_detections ?? video.totalDetections ?? 0;
    if (isFiniteNumber(avg) && count > 0) {
      return sum + avg * count;
    }
    return sum;
  }, 0);

  const averageLatency =
    totalDetections && totalDetections > 0 ? totalLatencyWeighted / totalDetections : raw?.average_latency_ms ?? raw?.averageLatencyMs;

  const worstLatencyCandidates = normalizedVideos
    .map((video) => video.max_latency_ms ?? video.maxLatencyMs)
    .filter(isFiniteNumber);
  const worstLatency =
    worstLatencyCandidates.length > 0
      ? Math.max(...worstLatencyCandidates)
      : raw?.worst_latency_ms ?? raw?.worstLatencyMs ?? undefined;

  const bestLatencyCandidates = normalizedVideos
    .map((video) => video.min_latency_ms ?? video.minLatencyMs)
    .filter(isFiniteNumber);
  const bestLatency =
    bestLatencyCandidates.length > 0
      ? Math.min(...bestLatencyCandidates)
      : raw?.best_latency_ms ?? raw?.bestLatencyMs ?? undefined;

  const totalDurationFromVideos = normalizedVideos.reduce(
    (sum, video) => sum + (video.duration_seconds ?? video.duration ?? 0),
    0
  );

  const sequenceDurationSeconds =
    toNumber(
      raw?.sequence_duration_seconds ??
        raw?.sequenceDurationSeconds ??
        raw?.total_duration ??
        raw?.totalDuration
    ) ?? totalDurationFromVideos;

  const sequenceDurationFormatted =
    raw?.sequence_duration_formatted ??
    raw?.sequenceDurationFormatted ??
    formatSeconds(sequenceDurationSeconds);

  const overallPassRate =
    totalDetections > 0
      ? (totalPassedDetections / totalDetections) * 100
      : raw?.overall_pass_rate ?? raw?.overallPassRate ?? 0;

  const normalizedOverallStatus: 'pass' | 'fail' | 'partial' = (() => {
    if (totalVideos > 0 && videosPassed === totalVideos && videosFailed === 0) {
      return 'pass';
    }
    if (videosFailed > 0 && videosPassed === 0) {
      return 'fail';
    }
    if (videosPassed > 0 && videosFailed > 0) {
      return 'partial';
    }
    const rawStatus = coerceStatus(raw?.sequence_status ?? raw?.sequenceStatus);
    if (rawStatus === 'pass' || rawStatus === 'fail') {
      return rawStatus;
    }
    return 'partial';
  })();

  const sequenceSummary = {
    overall_status: normalizedOverallStatus,
    total_videos: totalVideos,
    videos_passed: videosPassed,
    videos_failed: videosFailed,
    sequence_duration_seconds: sequenceDurationSeconds,
    sequence_duration_formatted: sequenceDurationFormatted,
    average_latency_ms: averageLatency ?? 0,
    worst_latency_ms: worstLatency ?? 0,
    best_latency_ms: bestLatency ?? 0,
    total_detections: totalDetections,
    total_passed_detections: totalPassedDetections,
    total_failed_detections: totalFailedDetections,
    overall_pass_rate: overallPassRate
  };

  const normalizedResults: VideoSequenceResults = {
    ...(raw as Record<string, unknown>),
    sequence_id: raw?.sequence_id ?? raw?.sequenceId,
    sequenceId: raw?.sequenceId ?? raw?.sequence_id,
    test_session_id: raw?.test_session_id ?? raw?.testSessionId,
    testSessionId: raw?.testSessionId ?? raw?.test_session_id,
    project_id: raw?.project_id ?? raw?.projectId,
    projectId: raw?.projectId ?? raw?.project_id,
    sequence_status: raw?.sequence_status ?? raw?.sequenceStatus ?? normalizedOverallStatus,
    sequenceStatus: raw?.sequenceStatus ?? raw?.sequence_status ?? normalizedOverallStatus,
    total_videos: totalVideos,
    totalVideos: totalVideos,
    videos_completed: raw?.videos_completed ?? raw?.videosCompleted ?? normalizedVideos.filter((video) =>
      ['pass', 'fail'].includes((video.status ?? video.pass_fail ?? '').toString().toLowerCase())
    ).length,
    videosCompleted:
      raw?.videosCompleted ??
      raw?.videos_completed ??
      normalizedVideos.filter((video) =>
        ['pass', 'fail'].includes((video.status ?? video.pass_fail ?? '').toString().toLowerCase())
      ).length,
    videos_passed: videosPassed,
    videosPassed: videosPassed,
    videos_failed: videosFailed,
    videosFailed: videosFailed,
    overall_pass_rate: overallPassRate,
    overallPassRate: overallPassRate,
    sequence_started_at: raw?.sequence_started_at ?? raw?.sequenceStartedAt ?? undefined,
    sequenceStartedAt: raw?.sequenceStartedAt ?? raw?.sequence_started_at ?? undefined,
    sequence_completed_at: raw?.sequence_completed_at ?? raw?.sequenceCompletedAt ?? undefined,
    sequenceCompletedAt: raw?.sequenceCompletedAt ?? raw?.sequence_completed_at ?? undefined,
    total_duration: sequenceDurationSeconds,
    totalDuration: sequenceDurationSeconds,
    sequence_duration_seconds: sequenceDurationSeconds,
    sequenceDurationSeconds: sequenceDurationSeconds,
    sequence_duration_formatted: sequenceDurationFormatted,
    sequenceDurationFormatted: sequenceDurationFormatted,
    total_detections: totalDetections,
    totalDetections: totalDetections,
    total_passed_detections: totalPassedDetections,
    totalPassedDetections: totalPassedDetections,
    total_failed_detections: totalFailedDetections,
    totalFailedDetections: totalFailedDetections,
    average_latency_ms: averageLatency ?? undefined,
    averageLatencyMs: averageLatency ?? undefined,
    worst_latency_ms: worstLatency ?? undefined,
    worstLatencyMs: worstLatency ?? undefined,
    best_latency_ms: bestLatency ?? undefined,
    bestLatencyMs: bestLatency ?? undefined,
    aggregate_metrics: aggregateMetrics,
    aggregateMetrics: aggregateMetrics,
    per_video_results: normalizedVideos,
    perVideoResults: normalizedVideos,
    ground_truth_comparison: normalizedSequenceGroundTruth ?? undefined,
    groundTruthComparison: normalizedSequenceGroundTruth ?? undefined,
    sequence_summary: sequenceSummary,
    sequenceSummary: {
      overallStatus: sequenceSummary.overall_status,
      totalVideos: sequenceSummary.total_videos,
      videosPassed: sequenceSummary.videos_passed,
      videosFailed: sequenceSummary.videos_failed,
      sequenceDurationSeconds: sequenceSummary.sequence_duration_seconds,
      sequenceDurationFormatted: sequenceSummary.sequence_duration_formatted,
      averageLatencyMs: sequenceSummary.average_latency_ms,
      worstLatencyMs: sequenceSummary.worst_latency_ms,
      bestLatencyMs: sequenceSummary.best_latency_ms,
      totalDetections: sequenceSummary.total_detections,
      totalPassedDetections: sequenceSummary.total_passed_detections,
      totalFailedDetections: sequenceSummary.total_failed_detections,
      overallPassRate: sequenceSummary.overall_pass_rate
    }
  };

  return normalizedResults;
};
