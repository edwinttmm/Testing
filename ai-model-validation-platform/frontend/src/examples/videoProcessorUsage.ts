/**
 * Video Processor Service Usage Examples
 * Demonstrates Frame 80 extraction functionality and video processing features
 */

import { 
  videoProcessor, 
  VideoMetadata, 
  Frame80Result, 
  ProcessedFrame,
  VideoValidationResult,
  SUPPORTED_VIDEO_FORMATS 
} from '../services/videoProcessor';

// Example 1: Basic Video Validation
export async function validateVideoFile(file: File): Promise<VideoValidationResult> {
  console.log('🔍 Validating video file:', file.name);
  
  const validation = videoProcessor.validateVideoFile(file);
  
  if (validation.valid) {
    console.log('✅ Video file is valid');
  } else {
    console.error('❌ Video validation failed:', validation.message);
    console.log('📋 Supported formats:', SUPPORTED_VIDEO_FORMATS);
  }
  
  return validation;
}

// Example 2: Load Video and Extract Metadata
export async function loadVideoWithMetadata(file: File): Promise<VideoMetadata | null> {
  try {
    console.log('📹 Loading video file:', file.name);
    
    const metadata = await videoProcessor.loadVideo(file);
    
    console.log('📊 Video Metadata:');
    console.log(`   Duration: ${metadata.duration.toFixed(2)}s`);
    console.log(`   Resolution: ${metadata.width}x${metadata.height}`);
    console.log(`   Frame Rate: ${metadata.frameRate}fps`);
    console.log(`   Total Frames: ${metadata.totalFrames}`);
    console.log(`   Aspect Ratio: ${metadata.aspectRatio.toFixed(2)}`);
    console.log(`   File Size: ${(metadata.size / 1024 / 1024).toFixed(2)}MB`);
    console.log(`   Has Audio: ${metadata.hasAudio ? '🔊' : '🔇'}`);
    
    return metadata;
  } catch (error) {
    console.error('❌ Failed to load video:', error);
    return null;
  }
}

// Example 3: Extract Frame 80 (Primary Use Case)
export async function extractFrame80(file: File): Promise<Frame80Result | null> {
  try {
    console.log('🎯 Extracting Frame 80 for analysis...');
    
    // First load the video
    await videoProcessor.loadVideo(file);
    
    // Extract Frame 80 with optimized settings
    const frame80 = await videoProcessor.extractFrame80();
    
    console.log('🖼️ Frame 80 Extracted:');
    console.log(`   Frame Number: ${frame80.frameNumber}`);
    console.log(`   Resolution: ${frame80.width}x${frame80.height}`);
    console.log(`   Quality: ${frame80.quality}`);
    console.log(`   Format: ${frame80.format}`);
    console.log(`   Extraction Time: ${frame80.extractionTime.toFixed(2)}ms`);
    console.log(`   Analysis Ready: ${frame80.analysisReady ? '✅' : '⚠️'}`);
    console.log(`   Optimized: ${frame80.optimized ? '🚀' : '📈'}`);
    console.log(`   File Size: ${(frame80.fileSize / 1024).toFixed(2)}KB`);
    
    return frame80;
  } catch (error) {
    console.error('❌ Frame 80 extraction failed:', error);
    return null;
  }
}

// Example 4: Extract Custom Frame
export async function extractCustomFrame(
  file: File, 
  frameNumber: number, 
  options?: {
    quality?: number;
    format?: 'jpeg' | 'png' | 'webp';
    maxWidth?: number;
    maxHeight?: number;
  }
): Promise<ProcessedFrame | null> {
  try {
    console.log(`🎬 Extracting frame ${frameNumber}...`);
    
    // Load video if not already loaded
    if (!videoProcessor.isVideoLoaded()) {
      await videoProcessor.loadVideo(file);
    }
    
    const frame = await videoProcessor.extractFrame({
      frameNumber,
      quality: options?.quality || 0.8,
      format: options?.format || 'jpeg',
      maxWidth: options?.maxWidth,
      maxHeight: options?.maxHeight
    });
    
    console.log(`✅ Frame ${frameNumber} extracted successfully`);
    console.log(`   Timestamp: ${frame.videoTimestamp.toFixed(3)}s`);
    console.log(`   Size: ${frame.width}x${frame.height}`);
    console.log(`   Format: ${frame.format}`);
    
    return frame;
  } catch (error) {
    console.error(`❌ Failed to extract frame ${frameNumber}:`, error);
    return null;
  }
}

// Example 5: Batch Frame Extraction
export async function extractMultipleFrames(
  file: File, 
  frameNumbers: number[]
): Promise<ProcessedFrame[]> {
  try {
    console.log(`📹 Extracting ${frameNumbers.length} frames:`, frameNumbers);
    
    await videoProcessor.loadVideo(file);
    
    const frames = await videoProcessor.extractFrames(frameNumbers, {
      quality: 0.75,
      format: 'jpeg',
      maxWidth: 1280,
      maxHeight: 720
    });
    
    console.log(`✅ Successfully extracted ${frames.length} frames`);
    
    frames.forEach((frame, index) => {
      console.log(`   Frame ${frame.frameNumber}: ${frame.width}x${frame.height}, ${frame.extractionTime.toFixed(1)}ms`);
    });
    
    return frames;
  } catch (error) {
    console.error('❌ Batch frame extraction failed:', error);
    return [];
  }
}

// Example 6: Frame Range Extraction with Progress
export async function extractFrameRange(
  file: File,
  startFrame: number,
  endFrame: number,
  onProgress?: (progress: number) => void
): Promise<ProcessedFrame[]> {
  try {
    console.log(`🎞️ Extracting frame range ${startFrame}-${endFrame}...`);
    
    await videoProcessor.loadVideo(file);
    
    const frames: ProcessedFrame[] = [];
    
    for await (const frame of videoProcessor.extractFrameRange(
      startFrame, 
      endFrame, 
      { quality: 0.7 },
      onProgress
    )) {
      frames.push(frame);
      console.log(`   📸 Extracted frame ${frame.frameNumber}`);
    }
    
    console.log(`✅ Range extraction complete: ${frames.length} frames`);
    return frames;
  } catch (error) {
    console.error('❌ Frame range extraction failed:', error);
    return [];
  }
}

// Example 7: Create Video Thumbnail
export async function createVideoThumbnail(
  file: File, 
  frameNumber: number = 0,
  size: number = 200
): Promise<string | null> {
  try {
    console.log(`🖼️ Creating thumbnail from frame ${frameNumber}...`);
    
    await videoProcessor.loadVideo(file);
    
    const thumbnail = await videoProcessor.createThumbnail(frameNumber, size);
    
    console.log(`✅ Thumbnail created: ${size}x${size}px`);
    
    return thumbnail;
  } catch (error) {
    console.error('❌ Thumbnail creation failed:', error);
    return null;
  }
}

// Example 8: Monitor Memory Usage
export function monitorMemoryUsage(): void {
  const usage = videoProcessor.getMemoryUsage();
  
  console.log('💾 Memory Usage:');
  console.log(`   Current: ${(usage.current / 1024 / 1024).toFixed(2)}MB`);
  console.log(`   Maximum: ${(usage.max / 1024 / 1024).toFixed(2)}MB`);
  console.log(`   Percentage: ${usage.percentage.toFixed(1)}%`);
  
  if (usage.percentage > 80) {
    console.warn('⚠️ Memory usage is high, consider cleanup');
  }
}

// Example 9: Video Processing Capabilities
export function displayCapabilities(): void {
  const capabilities = videoProcessor.getCapabilities();
  
  console.log('🛠️ Video Processor Capabilities:');
  console.log('   Supported Formats:');
  capabilities.supportedFormats.forEach(format => {
    console.log(`     • ${format}`);
  });
  console.log(`   Max File Size: ${(capabilities.maxFileSize / 1024 / 1024).toFixed(0)}MB`);
  console.log(`   Max Resolution: ${capabilities.maxResolution.width}x${capabilities.maxResolution.height}`);
  console.log('   Features:');
  capabilities.features.forEach(feature => {
    console.log(`     ✓ ${feature}`);
  });
}

// Example 10: Complete Workflow for Frame 80 Analysis
export async function completeFrame80Workflow(file: File): Promise<{
  validation: VideoValidationResult;
  metadata: VideoMetadata | null;
  frame80: Frame80Result | null;
  thumbnail: string | null;
}> {
  console.log('🚀 Starting complete Frame 80 analysis workflow...');
  
  // Step 1: Validate file
  const validation = await validateVideoFile(file);
  if (!validation.valid) {
    return { validation, metadata: null, frame80: null, thumbnail: null };
  }
  
  // Step 2: Load and extract metadata
  const metadata = await loadVideoWithMetadata(file);
  if (!metadata) {
    return { validation, metadata: null, frame80: null, thumbnail: null };
  }
  
  // Step 3: Extract Frame 80
  const frame80 = await extractFrame80(file);
  
  // Step 4: Create thumbnail
  const thumbnail = await createVideoThumbnail(file, 0, 150);
  
  // Step 5: Monitor memory
  monitorMemoryUsage();
  
  // Step 6: Cleanup
  videoProcessor.cleanup();
  
  console.log('✅ Frame 80 analysis workflow completed');
  
  return {
    validation,
    metadata,
    frame80,
    thumbnail
  };
}

// Example Usage Instructions
export const usageInstructions = `
Video Processor Service - Frame 80 Extraction

BASIC USAGE:
1. Import the service: import { videoProcessor } from './services/videoProcessor';
2. Validate file: videoProcessor.validateVideoFile(file)
3. Load video: await videoProcessor.loadVideo(file)
4. Extract Frame 80: await videoProcessor.extractFrame80()

SUPPORTED FORMATS:
• MP4 (.mp4)
• WebM (.webm)
• AVI (.avi)
• MOV (.mov)
• OGG (.ogg)
• 3GP (.3gp)

FRAME 80 OPTIMIZATIONS:
• High quality (0.95)
• JPEG format for analysis
• Max resolution 1920x1080
• Maintains aspect ratio
• Analysis-ready validation
• Performance monitoring

MEMORY MANAGEMENT:
• 500MB limit
• Automatic cleanup
• Memory usage tracking
• Resource optimization

ERROR HANDLING:
• File validation
• Format checking
• Size limits
• Timeout protection
• Memory management
`;

export default {
  validateVideoFile,
  loadVideoWithMetadata,
  extractFrame80,
  extractCustomFrame,
  extractMultipleFrames,
  extractFrameRange,
  createVideoThumbnail,
  monitorMemoryUsage,
  displayCapabilities,
  completeFrame80Workflow,
  usageInstructions
};