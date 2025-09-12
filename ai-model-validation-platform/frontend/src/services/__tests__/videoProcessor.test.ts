/**
 * Test suite for Enhanced Video Processor Service
 * Tests Frame 80 extraction functionality and video processing features
 */

import { 
  VideoProcessorService, 
  videoProcessor,
  SUPPORTED_VIDEO_FORMATS,
  VideoProcessingError,
  VideoMetadata,
  Frame80Result,
  ProcessedFrame
} from '../videoProcessor';

// Mock HTML video element for testing
class MockVideoElement {
  public duration = 10;
  public videoWidth = 1920;
  public videoHeight = 1080;
  public currentTime = 0;
  public readyState = HTMLMediaElement.HAVE_METADATA;
  public src = '';
  public crossOrigin = '';
  public preload = '';
  public muted = true;

  private eventListeners: { [key: string]: Function[] } = {};

  addEventListener(event: string, handler: Function) {
    if (!this.eventListeners[event]) {
      this.eventListeners[event] = [];
    }
    this.eventListeners[event].push(handler);
  }

  removeEventListener(event: string, handler: Function) {
    if (this.eventListeners[event]) {
      const index = this.eventListeners[event].indexOf(handler);
      if (index > -1) {
        this.eventListeners[event].splice(index, 1);
      }
    }
  }

  load() {
    setTimeout(() => {
      this.triggerEvent('loadedmetadata');
    }, 10);
  }

  private triggerEvent(eventName: string) {
    if (this.eventListeners[eventName]) {
      this.eventListeners[eventName].forEach(handler => handler());
    }
  }

  set currentTime(time: number) {
    this.currentTime = time;
    setTimeout(() => {
      this.triggerEvent('seeked');
    }, 5);
  }
}

// Mock Canvas and Context
class MockCanvasRenderingContext2D {
  public imageSmoothingEnabled = true;
  public imageSmoothingQuality = 'high';
  public fillStyle = '';

  drawImage() {}
  clearRect() {}
  fillRect() {}
}

class MockCanvas {
  public width = 0;
  public height = 0;
  private context = new MockCanvasRenderingContext2D();

  getContext(contextType?: string, options?: any) {
    return this.context;
  }

  toDataURL(type: string, quality?: number): string {
    return `data:${type};base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==`;
  }
}

// Mock File for testing
class MockFile {
  public name: string;
  public size: number;
  public type: string;

  constructor(name: string, size: number, type: string) {
    this.name = name;
    this.size = size;
    this.type = type;
  }
}

// Mock global objects
const mockCreateElement = jest.fn();
const mockCreateObjectURL = jest.fn();
const mockRevokeObjectURL = jest.fn();

beforeAll(() => {
  // Mock document.createElement
  (global as any).document = {
    createElement: mockCreateElement.mockImplementation((tagName: string) => {
      if (tagName === 'video') {
        return new MockVideoElement();
      } else if (tagName === 'canvas') {
        return new MockCanvas();
      }
      return {};
    })
  };

  // Mock URL methods
  (global as any).URL = {
    createObjectURL: mockCreateObjectURL.mockReturnValue('blob:mock-url'),
    revokeObjectURL: mockRevokeObjectURL
  };

  // Mock performance
  (global as any).performance = {
    now: jest.fn().mockReturnValue(1000)
  };

  // Mock console methods to avoid noise in tests
  global.console.warn = jest.fn();
  global.console.error = jest.fn();
});

describe('VideoProcessorService', () => {
  let processor: VideoProcessorService;

  beforeEach(() => {
    jest.clearAllMocks();
    try {
      processor = new VideoProcessorService();
    } catch (error) {
      // Ignore canvas context errors in test environment
    }
  });

  afterEach(() => {
    if (processor && processor.cleanup) {
      processor.cleanup();
    }
  });

  describe('Video File Validation', () => {
    test('should validate supported video formats', () => {
      if (!processor) {
        console.log('Skipping test: VideoProcessor not initialized');
        return;
      }
      
      const validFile = new MockFile('test.mp4', 10 * 1024 * 1024, 'video/mp4');
      const result = processor.validateVideoFile(validFile as any);
      
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });

    test('should reject unsupported video formats', () => {
      const invalidFile = new MockFile('test.txt', 1024, 'text/plain');
      const result = processor.validateVideoFile(invalidFile as any);
      
      expect(result.valid).toBe(false);
      expect(result.error).toBe(VideoProcessingError.UNSUPPORTED_FORMAT);
      expect(result.message).toContain('Unsupported video format');
    });

    test('should reject files that are too large', () => {
      const largeFile = new MockFile('large.mp4', 600 * 1024 * 1024, 'video/mp4');
      const result = processor.validateVideoFile(largeFile as any);
      
      expect(result.valid).toBe(false);
      expect(result.error).toBe(VideoProcessingError.FILE_TOO_LARGE);
      expect(result.message).toContain('Video file too large');
    });

    test('should reject empty files', () => {
      const emptyFile = new MockFile('empty.mp4', 0, 'video/mp4');
      const result = processor.validateVideoFile(emptyFile as any);
      
      expect(result.valid).toBe(false);
      expect(result.error).toBe(VideoProcessingError.INVALID_VIDEO);
    });

    test('should reject files with invalid extensions', () => {
      const invalidExtFile = new MockFile('video.xyz', 1024 * 1024, 'video/mp4');
      const result = processor.validateVideoFile(invalidExtFile as any);
      
      expect(result.valid).toBe(false);
      expect(result.error).toBe(VideoProcessingError.UNSUPPORTED_FORMAT);
    });
  });

  describe('Video Loading', () => {
    test('should load video and extract metadata', async () => {
      const validFile = new MockFile('test.mp4', 10 * 1024 * 1024, 'video/mp4');
      
      const metadata = await processor.loadVideo(validFile as any);
      
      expect(metadata).toMatchObject({
        duration: 10,
        width: 1920,
        height: 1080,
        format: 'video/mp4',
        size: 10 * 1024 * 1024,
        aspectRatio: 1920 / 1080,
        isValid: true,
        fileType: 'mp4'
      });
      expect(metadata.frameRate).toBeGreaterThan(0);
      expect(metadata.totalFrames).toBeGreaterThan(0);
    });

    test('should reject invalid video files during load', async () => {
      const invalidFile = new MockFile('invalid.txt', 1024, 'text/plain');
      
      await expect(processor.loadVideo(invalidFile as any))
        .rejects
        .toThrow('Video validation failed');
    });
  });

  describe('Frame Extraction', () => {
    beforeEach(async () => {
      const validFile = new MockFile('test.mp4', 10 * 1024 * 1024, 'video/mp4');
      await processor.loadVideo(validFile as any);
    });

    test('should extract specific frame', async () => {
      const frame = await processor.extractFrame({ frameNumber: 30 });
      
      expect(frame).toMatchObject({
        frameNumber: 30,
        width: expect.any(Number),
        height: expect.any(Number),
        imageData: expect.stringMatching(/^data:image\/jpeg;base64,/),
        quality: 0.8,
        format: 'jpeg',
        extractionTime: expect.any(Number)
      });
    });

    test('should extract frame with custom options', async () => {
      const frame = await processor.extractFrame({
        frameNumber: 60,
        quality: 0.9,
        format: 'png',
        maxWidth: 800,
        maxHeight: 600
      });
      
      expect(frame.quality).toBe(0.9);
      expect(frame.format).toBe('png');
      expect(frame.imageData).toMatch(/^data:image\/png;base64,/);
    });
  });

  describe('Frame 80 Extraction', () => {
    beforeEach(async () => {
      const validFile = new MockFile('test.mp4', 10 * 1024 * 1024, 'video/mp4');
      await processor.loadVideo(validFile as any);
    });

    test('should extract Frame 80 with optimized settings', async () => {
      const frame80 = await processor.extractFrame80();
      
      expect(frame80).toMatchObject({
        frameNumber: 80,
        isFrame80: true,
        optimized: true,
        quality: 0.95,
        format: 'jpeg'
      });
      expect(frame80.analysisReady).toBe(true);
    });

    test('Frame 80 should have high quality settings', async () => {
      const frame80 = await processor.extractFrame80();
      
      expect(frame80.quality).toBe(0.95);
      expect(frame80.width).toBeGreaterThanOrEqual(640);
      expect(frame80.height).toBeGreaterThanOrEqual(480);
    });
  });

  describe('Batch Frame Extraction', () => {
    beforeEach(async () => {
      const validFile = new MockFile('test.mp4', 10 * 1024 * 1024, 'video/mp4');
      await processor.loadVideo(validFile as any);
    });

    test('should extract multiple frames', async () => {
      const frameNumbers = [10, 20, 30, 40, 50];
      const frames = await processor.extractFrames(frameNumbers);
      
      expect(frames).toHaveLength(frameNumbers.length);
      frames.forEach((frame, index) => {
        expect(frame.frameNumber).toBe(frameNumbers[index]);
      });
    });

    test('should extract frame range with progress', async () => {
      const frames: ProcessedFrame[] = [];
      const progressUpdates: number[] = [];
      
      for await (const frame of processor.extractFrameRange(
        1, 5, 
        { quality: 0.7 },
        (progress) => progressUpdates.push(progress)
      )) {
        frames.push(frame);
      }
      
      expect(frames).toHaveLength(5);
      expect(progressUpdates).toHaveLength(5);
      expect(progressUpdates[progressUpdates.length - 1]).toBe(1); // Final progress should be 100%
    });
  });

  describe('Memory Management', () => {
    test('should track memory usage', () => {
      const usage = processor.getMemoryUsage();
      
      expect(usage).toMatchObject({
        current: expect.any(Number),
        max: expect.any(Number),
        percentage: expect.any(Number)
      });
      expect(usage.current).toBeGreaterThanOrEqual(0);
      expect(usage.max).toBeGreaterThan(0);
      expect(usage.percentage).toBeGreaterThanOrEqual(0);
    });

    test('should cleanup resources properly', () => {
      processor.cleanup();
      
      expect(mockRevokeObjectURL).toHaveBeenCalled();
      expect(processor.isVideoLoaded()).toBe(false);
    });
  });

  describe('Utility Functions', () => {
    test('should calculate frame to timestamp conversion', () => {
      const timestamp = processor.frameToTimestamp(80, 30);
      expect(timestamp).toBeCloseTo(80 / 30, 5);
    });

    test('should calculate timestamp to frame conversion', () => {
      const frame = processor.timestampToFrame(2.666, 30);
      expect(frame).toBe(79); // floor(2.666 * 30)
    });

    test('should provide capability information', () => {
      const capabilities = processor.getCapabilities();
      
      expect(capabilities).toMatchObject({
        supportedFormats: SUPPORTED_VIDEO_FORMATS,
        maxFileSize: 500 * 1024 * 1024,
        maxResolution: { width: 3840, height: 2160 },
        features: expect.arrayContaining(['Frame 80 extraction'])
      });
    });
  });

  describe('Error Handling', () => {
    test('should handle frame extraction without loaded video', async () => {
      const freshProcessor = new VideoProcessorService();
      
      await expect(freshProcessor.extractFrame({ frameNumber: 10 }))
        .rejects
        .toThrow('No video loaded');
      
      freshProcessor.cleanup();
    });

    test('should handle seeking to invalid video', async () => {
      const freshProcessor = new VideoProcessorService();
      
      await expect(freshProcessor.seekToTimestamp(5))
        .rejects
        .toThrow('No video loaded');
      
      freshProcessor.cleanup();
    });
  });
});

describe('VideoProcessor Singleton', () => {
  test('should export singleton instance', () => {
    expect(videoProcessor).toBeInstanceOf(VideoProcessorService);
  });

  test('should export supported formats', () => {
    expect(SUPPORTED_VIDEO_FORMATS).toContain('video/mp4');
    expect(SUPPORTED_VIDEO_FORMATS).toContain('video/webm');
    expect(SUPPORTED_VIDEO_FORMATS).toContain('video/avi');
  });
});