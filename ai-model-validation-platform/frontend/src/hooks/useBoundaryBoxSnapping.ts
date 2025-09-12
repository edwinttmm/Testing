import { useState, useCallback, useMemo } from 'react';

export interface SnapPoint {
  x: number;
  y: number;
  type: 'grid' | 'detection' | 'edge' | 'center';
  priority: number;
}

export interface SnapResult {
  x: number;
  y: number;
  snapped: boolean;
  snapPoint?: SnapPoint;
  distance?: number;
}

export interface BoundaryBoxSnappingOptions {
  enabled: boolean;
  gridSize: number;
  width: number;
  height: number;
  snapDistance?: number;
  snapToGrid?: boolean;
  snapToDetections?: boolean;
  snapToEdges?: boolean;
  snapToCenters?: boolean;
}

export interface UseBoundaryBoxSnappingReturn {
  snapPosition: (position: { x: number; y: number }) => SnapResult;
  isNearSnapPoint: (position: { x: number; y: number }) => boolean;
  getSnapPoint: (position: { x: number; y: number }) => SnapPoint | null;
  snapPoints: SnapPoint[];
  setDetections: (detections: Array<{ id: string; boundingBox: { x: number; y: number; width: number; height: number } }>) => void;
  updateOptions: (options: Partial<BoundaryBoxSnappingOptions>) => void;
}

export const useBoundaryBoxSnapping = (
  options: BoundaryBoxSnappingOptions
): UseBoundaryBoxSnappingReturn => {
  const {
    enabled,
    gridSize,
    width,
    height,
    snapDistance = 15,
    snapToGrid = true,
    snapToDetections = true,
    snapToEdges = true,
    snapToCenters = true
  } = options;

  const [detections, setDetections] = useState<Array<{
    id: string;
    boundingBox: { x: number; y: number; width: number; height: number };
  }>>([]);

  const [currentOptions, setCurrentOptions] = useState<BoundaryBoxSnappingOptions>(options);

  // Generate grid snap points
  const gridSnapPoints = useMemo((): SnapPoint[] => {
    if (!enabled || !snapToGrid) return [];

    const points: SnapPoint[] = [];
    
    // Grid intersection points
    for (let x = 0; x <= width; x += gridSize) {
      for (let y = 0; y <= height; y += gridSize) {
        points.push({
          x,
          y,
          type: 'grid',
          priority: 1
        });
      }
    }

    return points;
  }, [enabled, snapToGrid, width, height, gridSize]);

  // Generate detection-based snap points
  const detectionSnapPoints = useMemo((): SnapPoint[] => {
    if (!enabled || !snapToDetections) return [];

    const points: SnapPoint[] = [];

    detections.forEach(detection => {
      const { x, y, width: w, height: h } = detection.boundingBox;

      // Corner points
      points.push(
        { x, y, type: 'detection', priority: 3 }, // Top-left
        { x: x + w, y, type: 'detection', priority: 3 }, // Top-right
        { x, y: y + h, type: 'detection', priority: 3 }, // Bottom-left
        { x: x + w, y: y + h, type: 'detection', priority: 3 } // Bottom-right
      );

      // Edge midpoints
      if (snapToEdges) {
        points.push(
          { x: x + w / 2, y, type: 'edge', priority: 2 }, // Top edge
          { x: x + w / 2, y: y + h, type: 'edge', priority: 2 }, // Bottom edge
          { x, y: y + h / 2, type: 'edge', priority: 2 }, // Left edge
          { x: x + w, y: y + h / 2, type: 'edge', priority: 2 } // Right edge
        );
      }

      // Center point
      if (snapToCenters) {
        points.push({
          x: x + w / 2,
          y: y + h / 2,
          type: 'center',
          priority: 4
        });
      }
    });

    return points;
  }, [enabled, snapToDetections, snapToEdges, snapToCenters, detections]);

  // Combine all snap points
  const allSnapPoints = useMemo((): SnapPoint[] => {
    return [...gridSnapPoints, ...detectionSnapPoints];
  }, [gridSnapPoints, detectionSnapPoints]);

  // Calculate distance between two points
  const calculateDistance = useCallback((
    point1: { x: number; y: number },
    point2: { x: number; y: number }
  ): number => {
    const dx = point1.x - point2.x;
    const dy = point1.y - point2.y;
    return Math.sqrt(dx * dx + dy * dy);
  }, []);

  // Find the nearest snap point
  const findNearestSnapPoint = useCallback((
    position: { x: number; y: number }
  ): { snapPoint: SnapPoint; distance: number } | null => {
    if (!enabled || allSnapPoints.length === 0) return null;

    let nearestPoint: SnapPoint | null = null;
    let minDistance = Infinity;

    allSnapPoints.forEach(snapPoint => {
      const distance = calculateDistance(position, snapPoint);
      
      if (distance < minDistance && distance <= snapDistance) {
        // Prioritize higher priority points if distances are close
        if (!nearestPoint || distance < minDistance || 
            (Math.abs(distance - minDistance) < 2 && snapPoint.priority > nearestPoint.priority)) {
          nearestPoint = snapPoint;
          minDistance = distance;
        }
      }
    });

    return nearestPoint ? { snapPoint: nearestPoint, distance: minDistance } : null;
  }, [enabled, allSnapPoints, calculateDistance, snapDistance]);

  // Snap position to nearest snap point
  const snapPosition = useCallback((position: { x: number; y: number }): SnapResult => {
    if (!enabled) {
      return {
        x: position.x,
        y: position.y,
        snapped: false
      };
    }

    const nearest = findNearestSnapPoint(position);
    
    if (nearest) {
      return {
        x: nearest.snapPoint.x,
        y: nearest.snapPoint.y,
        snapped: true,
        snapPoint: nearest.snapPoint,
        distance: nearest.distance
      };
    }

    return {
      x: position.x,
      y: position.y,
      snapped: false
    };
  }, [enabled, findNearestSnapPoint]);

  // Check if position is near a snap point
  const isNearSnapPoint = useCallback((position: { x: number; y: number }): boolean => {
    if (!enabled) return false;
    const nearest = findNearestSnapPoint(position);
    return nearest !== null;
  }, [enabled, findNearestSnapPoint]);

  // Get the nearest snap point
  const getSnapPoint = useCallback((position: { x: number; y: number }): SnapPoint | null => {
    if (!enabled) return null;
    const nearest = findNearestSnapPoint(position);
    return nearest?.snapPoint || null;
  }, [enabled, findNearestSnapPoint]);

  // Update options
  const updateOptions = useCallback((newOptions: Partial<BoundaryBoxSnappingOptions>) => {
    setCurrentOptions(prev => ({ ...prev, ...newOptions }));
  }, []);

  return {
    snapPosition,
    isNearSnapPoint,
    getSnapPoint,
    snapPoints: allSnapPoints,
    setDetections,
    updateOptions
  };
};

export default useBoundaryBoxSnapping;