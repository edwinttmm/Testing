/**
 * Annotation Display Debugging Utility
 * 
 * This utility helps debug annotation display issues by providing
 * comprehensive validation and debugging functions.
 */

import { GroundTruthAnnotation, BoundingBox } from '../services/types';

export interface DebugAnnotationInfo {
  id: string;
  frameNumber: number;
  timestamp: number;
  vruType: string;
  boundingBox: BoundingBox;
  isValid: boolean;
  issues: string[];
  coordinateType: 'normalized' | 'absolute' | 'unknown';
}

export interface VideoDisplayInfo {
  videoNaturalSize: { width: number; height: number };
  videoDisplaySize: { width: number; height: number };
  canvasSize: { width: number; height: number };
  scaleFactors: { scaleX: number; scaleY: number };
  aspectRatio: number;
}

export class AnnotationDebugger {
  
  /**
   * Validate and debug annotation data
   */
  static debugAnnotations(annotations: GroundTruthAnnotation[]): DebugAnnotationInfo[] {
    return annotations.map((annotation) => {
      const issues: string[] = [];
      let isValid = true;
      
      // Check required fields
      if (!annotation.id) {
        issues.push('Missing annotation ID');
        isValid = false;
      }
      
      if (typeof annotation.frameNumber !== 'number' || annotation.frameNumber < 0) {
        issues.push('Invalid frame number');
        isValid = false;
      }
      
      if (typeof annotation.timestamp !== 'number' || annotation.timestamp < 0) {
        issues.push('Invalid timestamp');
        isValid = false;
      }
      
      if (!annotation.vruType) {
        issues.push('Missing VRU type');
        isValid = false;
      }
      
      // Check bounding box
      const bbox = annotation.boundingBox;
      if (!bbox) {
        issues.push('Missing bounding box');
        isValid = false;
      } else {
        if (typeof bbox.x !== 'number' || typeof bbox.y !== 'number' ||
            typeof bbox.width !== 'number' || typeof bbox.height !== 'number') {
          issues.push('Invalid bounding box coordinates');
          isValid = false;
        }
        
        if (bbox.width <= 0 || bbox.height <= 0) {
          issues.push('Invalid bounding box dimensions');
          isValid = false;
        }
      }
      
      // Determine coordinate type
      let coordinateType: 'normalized' | 'absolute' | 'unknown' = 'unknown';
      if (bbox && isValid) {
        const maxCoord = Math.max(bbox.x + bbox.width, bbox.y + bbox.height);
        if (maxCoord <= 1) {
          coordinateType = 'normalized';
        } else if (maxCoord > 1) {
          coordinateType = 'absolute';
        }
      }
      
      return {
        id: annotation.id,
        frameNumber: annotation.frameNumber,
        timestamp: annotation.timestamp,
        vruType: annotation.vruType,
        boundingBox: annotation.boundingBox,
        isValid,
        issues,
        coordinateType
      };
    });
  }
  
  /**
   * Debug video display information
   */
  static debugVideoDisplay(
    videoElement: HTMLVideoElement, 
    canvasElement: HTMLCanvasElement
  ): VideoDisplayInfo {
    const rect = videoElement.getBoundingClientRect();
    const videoNaturalWidth = videoElement.videoWidth;
    const videoNaturalHeight = videoElement.videoHeight;
    
    return {
      videoNaturalSize: { 
        width: videoNaturalWidth, 
        height: videoNaturalHeight 
      },
      videoDisplaySize: { 
        width: rect.width, 
        height: rect.height 
      },
      canvasSize: { 
        width: canvasElement.width, 
        height: canvasElement.height 
      },
      scaleFactors: {
        scaleX: rect.width / videoNaturalWidth,
        scaleY: rect.height / videoNaturalHeight
      },
      aspectRatio: videoNaturalWidth / videoNaturalHeight
    };
  }
  
  /**
   * Test coordinate transformation
   */
  static testCoordinateTransformation(
    bbox: BoundingBox,
    videoInfo: VideoDisplayInfo
  ): {
    normalized: BoundingBox;
    absolute: BoundingBox;
    display: BoundingBox;
  } {
    const isNormalized = bbox.x <= 1 && bbox.y <= 1 && bbox.width <= 1 && bbox.height <= 1;
    
    let normalized: BoundingBox;
    let absolute: BoundingBox;
    
    if (isNormalized) {
      normalized = { ...bbox };
      absolute = {
        x: bbox.x * videoInfo.videoNaturalSize.width,
        y: bbox.y * videoInfo.videoNaturalSize.height,
        width: bbox.width * videoInfo.videoNaturalSize.width,
        height: bbox.height * videoInfo.videoNaturalSize.height,
        confidence: bbox.confidence
      };
    } else {
      absolute = { ...bbox };
      normalized = {
        x: bbox.x / videoInfo.videoNaturalSize.width,
        y: bbox.y / videoInfo.videoNaturalSize.height,
        width: bbox.width / videoInfo.videoNaturalSize.width,
        height: bbox.height / videoInfo.videoNaturalSize.height,
        confidence: bbox.confidence
      };
    }
    
    const display: BoundingBox = {
      x: normalized.x * videoInfo.videoDisplaySize.width,
      y: normalized.y * videoInfo.videoDisplaySize.height,
      width: normalized.width * videoInfo.videoDisplaySize.width,
      height: normalized.height * videoInfo.videoDisplaySize.height,
      confidence: bbox.confidence
    };
    
    return { normalized, absolute, display };
  }
  
  /**
   * Generate debug report
   */
  static generateReport(
    annotations: GroundTruthAnnotation[],
    videoInfo?: VideoDisplayInfo,
    currentFrame?: number
  ): string {
    const debugInfo = this.debugAnnotations(annotations);
    const validAnnotations = debugInfo.filter(a => a.isValid);
    const invalidAnnotations = debugInfo.filter(a => !a.isValid);
    
    let report = '=== ANNOTATION DEBUG REPORT ===\n\n';
    
    report += `Total Annotations: ${annotations.length}\n`;
    report += `Valid Annotations: ${validAnnotations.length}\n`;
    report += `Invalid Annotations: ${invalidAnnotations.length}\n\n`;
    
    if (currentFrame !== undefined) {
      const frameAnnotations = validAnnotations.filter(a => 
        Math.abs(a.frameNumber - currentFrame) <= 3
      );
      report += `Annotations near frame ${currentFrame}: ${frameAnnotations.length}\n\n`;
    }
    
    // VRU type distribution
    const vruTypes: { [key: string]: number } = {};
    validAnnotations.forEach(a => {
      vruTypes[a.vruType] = (vruTypes[a.vruType] || 0) + 1;
    });
    
    report += 'VRU Type Distribution:\n';
    Object.entries(vruTypes).forEach(([type, count]) => {
      report += `  ${type}: ${count}\n`;
    });
    
    // Coordinate type analysis
    const coordTypes: { [key: string]: number } = {};
    validAnnotations.forEach(a => {
      coordTypes[a.coordinateType] = (coordTypes[a.coordinateType] || 0) + 1;
    });
    
    report += '\nCoordinate Type Distribution:\n';
    Object.entries(coordTypes).forEach(([type, count]) => {
      report += `  ${type}: ${count}\n`;
    });
    
    // Video display info
    if (videoInfo) {
      report += '\nVideo Display Info:\n';
      report += `  Natural Size: ${videoInfo.videoNaturalSize.width}x${videoInfo.videoNaturalSize.height}\n`;
      report += `  Display Size: ${videoInfo.videoDisplaySize.width}x${videoInfo.videoDisplaySize.height}\n`;
      report += `  Canvas Size: ${videoInfo.canvasSize.width}x${videoInfo.canvasSize.height}\n`;
      report += `  Scale Factors: X=${videoInfo.scaleFactors.scaleX.toFixed(3)}, Y=${videoInfo.scaleFactors.scaleY.toFixed(3)}\n`;
      report += `  Aspect Ratio: ${videoInfo.aspectRatio.toFixed(3)}\n`;
    }
    
    // Issues summary
    if (invalidAnnotations.length > 0) {
      report += '\nISSUES FOUND:\n';
      invalidAnnotations.forEach(a => {
        report += `  Annotation ${a.id}: ${a.issues.join(', ')}\n`;
      });
    }
    
    return report;
  }
  
  /**
   * Log comprehensive debug information to console
   */
  static logDebugInfo(
    annotations: GroundTruthAnnotation[],
    videoElement?: HTMLVideoElement,
    canvasElement?: HTMLCanvasElement,
    currentFrame?: number
  ): void {
    console.group('📊 ANNOTATION DEBUG INFORMATION');
    
    let videoInfo: VideoDisplayInfo | undefined;
    if (videoElement && canvasElement) {
      videoInfo = this.debugVideoDisplay(videoElement, canvasElement);
    }
    
    const report = this.generateReport(annotations, videoInfo, currentFrame);
    console.log(report);
    
    // Log sample annotations with coordinate transformations
    if (annotations.length > 0 && videoInfo) {
      console.group('📊 Sample Coordinate Transformations');
      annotations.slice(0, 3).forEach((annotation, index) => {
        const transforms = this.testCoordinateTransformation(annotation.boundingBox, videoInfo!);
        console.log(`Annotation ${index + 1}:`, {
          original: annotation.boundingBox,
          normalized: transforms.normalized,
          absolute: transforms.absolute,
          display: transforms.display
        });
      });
      console.groupEnd();
    }
    
    console.groupEnd();
  }
}

// Global debug function for easy access in browser console
(window as any).debugAnnotations = AnnotationDebugger.logDebugInfo;