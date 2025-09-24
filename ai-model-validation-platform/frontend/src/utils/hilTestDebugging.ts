/**
 * HIL Test Ground Truth Debugging Utilities
 * Comprehensive debugging tools for investigating ground truth loading issues
 */

import { apiService } from '../services/api';
import { VideoFile } from '../services/types';

export interface HILDebugInfo {
  timestamp: string;
  step: string;
  status: 'success' | 'warning' | 'error' | 'info';
  data: any;
  message: string;
}

export class HILTestDebugger {
  private debugLog: HILDebugInfo[] = [];
  private isDebugging: boolean = true;

  constructor() {
    this.log('info', 'HIL Test Debugger initialized', {});
  }

  private log(status: HILDebugInfo['status'], message: string, data: any, step?: string) {
    const entry: HILDebugInfo = {
      timestamp: new Date().toISOString(),
      step: step || 'general',
      status,
      message,
      data
    };
    
    this.debugLog.push(entry);
    
    if (this.isDebugging) {
      const emoji = {
        success: '✅',
        warning: '⚠️',
        error: '❌',
        info: 'ℹ️'
      }[status];
      
      console.log(`${emoji} [HIL DEBUG] ${step || 'GENERAL'}: ${message}`, data);
    }
  }

  /**
   * Comprehensive video and annotation investigation
   */
  async investigateGroundTruthLoading(videoPlaylist: VideoFile[], validatedVideos: VideoFile[]) {
    this.log('info', 'Starting comprehensive ground truth investigation', {
      videoPlaylistCount: videoPlaylist.length,
      validatedVideosCount: validatedVideos.length
    }, 'INVESTIGATION_START');

    // Step 1: Analyze video playlist
    await this.analyzeVideoPlaylist(videoPlaylist);
    
    // Step 2: Analyze validated videos
    await this.analyzeValidatedVideos(validatedVideos);
    
    // Step 3: Test API connectivity
    await this.testApiConnectivity();
    
    // Step 4: Try loading annotations for each video
    await this.testAnnotationEndpoints(videoPlaylist);
    
    // Step 5: Search for Child.mp4 specifically
    await this.findChildVideo(videoPlaylist);
    
    // Return summary
    return this.generateSummaryReport();
  }

  private async analyzeVideoPlaylist(videoPlaylist: VideoFile[]) {
    this.log('info', 'Analyzing video playlist', { count: videoPlaylist.length }, 'PLAYLIST_ANALYSIS');
    
    videoPlaylist.forEach((video, index) => {
      this.log('info', `Video ${index + 1}`, {
        id: video.id,
        filename: video.filename,
        status: video.status,
        processing_status: (video as any).processing_status,
        url: video.url,
        file_path: (video as any).file_path,
        originalName: (video as any).originalName,
        project_id: (video as any).project_id
      }, 'VIDEO_DETAILS');

      // Check for Child.mp4 specifically
      if (video.filename && video.filename.toLowerCase().includes('child')) {
        this.log('success', 'Found Child.mp4 variant!', {
          filename: video.filename,
          id: video.id,
          status: video.status
        }, 'CHILD_VIDEO_FOUND');
      }
    });
  }

  private async analyzeValidatedVideos(validatedVideos: VideoFile[]) {
    this.log('info', 'Analyzing validated videos', { count: validatedVideos.length }, 'VALIDATED_ANALYSIS');
    
    if (validatedVideos.length === 0) {
      this.log('warning', 'No validated videos found - this is the primary issue!', {
        possibleReasons: [
          'Videos have incorrect status field',
          'Validation process not completed',
          'Status filtering logic is too strict',
          'Backend returning different status format'
        ]
      }, 'NO_VALIDATED_VIDEOS');
    }

    validatedVideos.forEach((video, index) => {
      this.log('info', `Validated video ${index + 1}`, {
        id: video.id,
        filename: video.filename,
        status: video.status,
        validation_details: 'passed validation filter'
      }, 'VALIDATED_VIDEO');
    });
  }

  private async testApiConnectivity() {
    this.log('info', 'Testing API connectivity', {}, 'API_CONNECTIVITY');
    
    try {
      const health = await apiService.healthCheck();
      this.log('success', 'API health check passed', health, 'API_HEALTH');
    } catch (error) {
      this.log('error', 'API health check failed', { error: (error as Error).message }, 'API_HEALTH');
    }

    try {
      const projects = await apiService.getProjects();
      this.log('success', 'Projects endpoint working', { count: projects.length }, 'API_PROJECTS');
    } catch (error) {
      this.log('error', 'Projects endpoint failed', { error: (error as Error).message }, 'API_PROJECTS');
    }
  }

  private async testAnnotationEndpoints(videoPlaylist: VideoFile[]) {
    this.log('info', 'Testing annotation endpoints for all videos', {}, 'ANNOTATION_ENDPOINTS');
    
    for (const video of videoPlaylist) {
      if (!video.id) {
        this.log('warning', 'Video has no ID, skipping annotation test', { filename: video.filename }, 'ANNOTATION_TEST');
        continue;
      }

      try {
        // Test main annotations endpoint
        const annotations = await apiService.getAnnotations(video.id);
        this.log('success', `Annotations loaded for ${video.filename}`, {
          videoId: video.id,
          annotationCount: Array.isArray(annotations) ? annotations.length : 'not an array',
          annotationStructure: Array.isArray(annotations) && annotations.length > 0 ? annotations[0] : 'empty or invalid',
          fullResponse: annotations
        }, 'ANNOTATION_SUCCESS');

        if (Array.isArray(annotations) && annotations.length > 0) {
          this.log('success', 'FOUND ANNOTATIONS! This video has ground truth data', {
            videoFilename: video.filename,
            videoId: video.id,
            annotationCount: annotations.length,
            sampleAnnotation: annotations[0]
          }, 'GROUND_TRUTH_FOUND');
        }

      } catch (error) {
        this.log('error', `Annotations failed for ${video.filename}`, {
          videoId: video.id,
          error: (error as Error).message,
          errorDetails: error
        }, 'ANNOTATION_FAILURE');

        // Try alternative endpoints
        await this.tryAlternativeEndpoints(video);
      }
    }
  }

  private async tryAlternativeEndpoints(video: VideoFile) {
    this.log('info', `Trying alternative endpoints for ${video.filename}`, {}, 'ALTERNATIVE_ENDPOINTS');
    
    // Try ground truth endpoint
    try {
      const groundTruth = await apiService.getGroundTruth(video.id);
      this.log('success', `Ground truth endpoint worked for ${video.filename}`, {
        groundTruthData: groundTruth
      }, 'GROUND_TRUTH_ENDPOINT');
    } catch (error) {
      this.log('warning', `Ground truth endpoint failed for ${video.filename}`, {
        error: (error as Error).message
      }, 'GROUND_TRUTH_ENDPOINT');
    }

    // Try detections endpoint
    try {
      const detections = await apiService.getVideoDetections(video.id);
      this.log('success', `Detections endpoint worked for ${video.filename}`, {
        detectionsData: detections
      }, 'DETECTIONS_ENDPOINT');
    } catch (error) {
      this.log('warning', `Detections endpoint failed for ${video.filename}`, {
        error: (error as Error).message
      }, 'DETECTIONS_ENDPOINT');
    }
  }

  private async findChildVideo(videoPlaylist: VideoFile[]) {
    this.log('info', 'Searching specifically for Child.mp4 variants', {}, 'CHILD_SEARCH');
    
    const childVariants = videoPlaylist.filter(video => 
      video.filename && (
        video.filename.toLowerCase().includes('child') ||
        video.filename.toLowerCase().includes('AI Detection Session - Child'.toLowerCase()) ||
        (video as any).originalName?.toLowerCase().includes('child')
      )
    );

    if (childVariants.length === 0) {
      this.log('error', 'No Child.mp4 variants found in video playlist!', {
        availableFilenames: videoPlaylist.map(v => v.filename),
        searchTerms: ['child', 'AI Detection Session - Child']
      }, 'CHILD_NOT_FOUND');
    } else {
      this.log('success', `Found ${childVariants.length} Child.mp4 variant(s)`, {
        variants: childVariants.map(v => ({
          id: v.id,
          filename: v.filename,
          status: v.status,
          processing_status: (v as any).processing_status
        }))
      }, 'CHILD_VARIANTS_FOUND');

      // Test each variant for annotations
      for (const variant of childVariants) {
        await this.testChildVideoAnnotations(variant);
      }
    }
  }

  private async testChildVideoAnnotations(video: VideoFile) {
    this.log('info', `Testing Child.mp4 variant: ${video.filename}`, {}, 'CHILD_ANNOTATION_TEST');
    
    try {
      const annotations = await apiService.getAnnotations(video.id);
      
      if (Array.isArray(annotations) && annotations.length > 0) {
        this.log('success', 'CHILD.MP4 HAS ANNOTATIONS!', {
          videoId: video.id,
          filename: video.filename,
          annotationCount: annotations.length,
          annotations: annotations,
          processed: annotations.map(ann => ({
            id: ann.id,
            timestamp: ann.timestamp,
            frame_number: ann.frame_number,
            timestampInSeconds: ann.timestamp ? ann.timestamp / 1000 : 'no timestamp'
          }))
        }, 'CHILD_ANNOTATIONS_SUCCESS');
      } else {
        this.log('warning', 'Child.mp4 found but no annotations', {
          videoId: video.id,
          filename: video.filename,
          response: annotations
        }, 'CHILD_NO_ANNOTATIONS');
      }
    } catch (error) {
      this.log('error', 'Child.mp4 annotation loading failed', {
        videoId: video.id,
        filename: video.filename,
        error: (error as Error).message
      }, 'CHILD_ANNOTATION_ERROR');
    }
  }

  private generateSummaryReport() {
    const errors = this.debugLog.filter(log => log.status === 'error');
    const warnings = this.debugLog.filter(log => log.status === 'warning');
    const successes = this.debugLog.filter(log => log.status === 'success');
    
    const summary = {
      timestamp: new Date().toISOString(),
      totalLogs: this.debugLog.length,
      errorCount: errors.length,
      warningCount: warnings.length,
      successCount: successes.length,
      criticalIssues: errors.map(e => e.message),
      warnings: warnings.map(w => w.message),
      successes: successes.map(s => s.message),
      fullDebugLog: this.debugLog,
      recommendations: this.generateRecommendations()
    };

    this.log('info', 'Investigation complete', summary, 'SUMMARY');
    return summary;
  }

  private generateRecommendations() {
    const issues = this.debugLog.filter(log => log.status === 'error' || log.status === 'warning');
    const recommendations = [];

    if (issues.some(i => i.step === 'NO_VALIDATED_VIDEOS')) {
      recommendations.push({
        issue: 'No validated videos found',
        recommendation: 'Check video validation logic in validatedVideos filter. Videos may need status "validated" and processing_status "completed".',
        priority: 'HIGH'
      });
    }

    if (issues.some(i => i.step === 'CHILD_NOT_FOUND')) {
      recommendations.push({
        issue: 'Child.mp4 not found in playlist',
        recommendation: 'Check video upload and project assignment. Ensure Child.mp4 is uploaded and assigned to the correct project.',
        priority: 'HIGH'
      });
    }

    if (issues.some(i => i.step === 'ANNOTATION_FAILURE')) {
      recommendations.push({
        issue: 'Annotation endpoints failing',
        recommendation: 'Check backend annotation service. Verify database contains annotation data for test videos.',
        priority: 'MEDIUM'
      });
    }

    return recommendations;
  }

  getDebugLog() {
    return this.debugLog;
  }

  clearLog() {
    this.debugLog = [];
  }
}

export const createHILDebugger = () => new HILTestDebugger();