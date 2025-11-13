import { TestSession } from '../services/types';

export type DualResultStatus = 'PASS' | 'CONDITIONAL_PASS' | 'FAIL' | 'PENDING' | 'UNKNOWN';

const toPercent = (value?: number | null): number | null => {
  if (value === null || value === undefined) {
    return null;
  }
  if (!Number.isFinite(value)) {
    return null;
  }
  return value <= 1 ? value * 100 : value;
};

const extractNumberFromDetails = (
  details: Record<string, unknown> | undefined,
  key: string
): number | null => {
  if (!details || typeof details !== 'object') {
    return null;
  }
  const raw = details[key];
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : null;
};

export const normalizeResultStatus = (value?: string | null): DualResultStatus => {
  if (!value || typeof value !== 'string') {
    return 'UNKNOWN';
  }
  const normalized = value.toUpperCase();
  if (normalized === 'PASS' || normalized === 'CONDITIONAL_PASS' || normalized === 'FAIL' || normalized === 'PENDING') {
    return normalized as DualResultStatus;
  }
  return 'UNKNOWN';
};

export const formatResultLabel = (status: DualResultStatus): string => {
  switch (status) {
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

export const getResultChipColor = (
  status: DualResultStatus
): 'success' | 'warning' | 'error' | 'default' => {
  switch (status) {
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

export const getAccuracyPercent = (session: TestSession): number | null => {
  if (typeof session.overallScore === 'number') {
    return session.overallScore;
  }
  const f1Score = toPercent(session.accuracyF1Score);
  if (f1Score !== null) {
    return f1Score;
  }
  return toPercent(session.metrics?.accuracy);
};

export const getPrecisionPercent = (session: TestSession): number | null => {
  return toPercent(session.accuracyPrecision ?? session.metrics?.precision);
};

export const getRecallPercent = (session: TestSession): number | null => {
  return toPercent(session.accuracyRecall ?? session.metrics?.recall);
};

export const getF1Percent = (session: TestSession): number | null => {
  const overallScore = typeof session.overallScore === 'number' ? session.overallScore : null;
  if (overallScore !== null) {
    return overallScore;
  }
  return toPercent(session.accuracyF1Score ?? session.metrics?.f1Score);
};

export const getAccuracyStatus = (session: TestSession): DualResultStatus => {
  return normalizeResultStatus(session.accuracyResult ?? session.passFailResult ?? session.overallTestResult);
};

export const getLatencyStatus = (session: TestSession): DualResultStatus => {
  return normalizeResultStatus(session.latencyResult);
};

export const getOverallStatus = (session: TestSession): DualResultStatus => {
  return normalizeResultStatus(session.overallTestResult ?? session.passFailResult ?? session.accuracyResult);
};

export const getLatencyMeanMs = (session: TestSession): number | null => {
  if (typeof session.latencyMeanMs === 'number') {
    return session.latencyMeanMs;
  }
  return extractNumberFromDetails(session.latencyDetails as Record<string, unknown> | undefined, 'meanLatencyMs');
};

export const getLatencyWithinPercent = (session: TestSession): number | null => {
  if (typeof session.latencyPercentWithinThreshold === 'number') {
    return session.latencyPercentWithinThreshold;
  }
  return extractNumberFromDetails(
    session.latencyDetails as Record<string, unknown> | undefined,
    'withinTolerancePercent'
  );
};

export const getTruePositives = (session: TestSession): number => {
  return session.truePositives ?? session.metrics?.truePositives ?? 0;
};

export const getFalsePositives = (session: TestSession): number => {
  return session.falsePositives ?? session.metrics?.falsePositives ?? 0;
};

export const getFalseNegatives = (session: TestSession): number => {
  return session.falseNegatives ?? session.metrics?.falseNegatives ?? 0;
};
