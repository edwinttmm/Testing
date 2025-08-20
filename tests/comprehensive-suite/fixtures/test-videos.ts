// Test video fixtures for comprehensive testing
export interface TestVideoFile {
  filename: string;
  size: number;
  duration: number;
  fps: number;
  resolution: string;
  format: string;
  path?: string;
  blob?: Blob;
}

export const TEST_VIDEOS: Record<string, TestVideoFile> = {
  small: {
    filename: 'test-small-video.mp4',
    size: 5 * 1024 * 1024, // 5MB
    duration: 10,
    fps: 30,
    resolution: '720p',
    format: 'video/mp4'
  },
  large: {
    filename: 'test-large-video.mp4',
    size: 100 * 1024 * 1024, // 100MB
    duration: 120,
    fps: 30,
    resolution: '1080p',
    format: 'video/mp4'
  },
  corrupted: {
    filename: 'test-corrupted-video.mp4',
    size: 1024,
    duration: 0,
    fps: 0,
    resolution: 'unknown',
    format: 'video/mp4'
  },
  unsupportedFormat: {
    filename: 'test-unsupported.avi',
    size: 2 * 1024 * 1024,
    duration: 5,
    fps: 25,
    resolution: '480p',
    format: 'video/avi'
  }
};

export const TEST_ANNOTATIONS = {
  pedestrian: {
    id: 'test-annotation-1',
    detectionId: 'det-001',
    frameNumber: 150,
    timestamp: 5.0,
    vruType: 'pedestrian',
    boundingBox: { x: 100, y: 50, width: 60, height: 120 },
    occluded: false,
    truncated: false,
    difficult: false,
    validated: true,
    annotator: 'test-user'
  },
  cyclist: {
    id: 'test-annotation-2',
    detectionId: 'det-002',
    frameNumber: 300,
    timestamp: 10.0,
    vruType: 'cyclist',
    boundingBox: { x: 200, y: 100, width: 80, height: 100 },
    occluded: false,
    truncated: true,
    difficult: false,
    validated: false,
    annotator: 'test-user'
  }
};

export const TEST_PROJECTS = {
  basic: {
    name: 'Test Project Basic',
    description: 'Basic test project for unit testing',
    camera_model: 'TestCam v1.0',
    camera_view: 'Front-facing VRU',
    lens_type: 'Wide-angle',
    resolution: '1920x1080',
    frame_rate: 30,
    signal_type: 'GPIO'
  },
  advanced: {
    name: 'Test Project Advanced',
    description: 'Advanced test project with complex configurations',
    camera_model: 'TestCam Pro v2.0',
    camera_view: 'Rear-facing VRU',
    lens_type: 'Fish-eye',
    resolution: '2560x1440',
    frame_rate: 60,
    signal_type: 'Network Packet'
  }
};

// Helper function to create mock video blob
export function createMockVideoBlob(video: TestVideoFile): Blob {
  // Create a minimal MP4-like blob for testing
  const header = new Uint8Array([
    0x00, 0x00, 0x00, 0x20, // Box size
    0x66, 0x74, 0x79, 0x70, // 'ftyp'
    0x69, 0x73, 0x6f, 0x6d, // 'isom'
    0x00, 0x00, 0x02, 0x00, // Minor version
    0x69, 0x73, 0x6f, 0x6d, // Compatible brands
    0x69, 0x73, 0x6f, 0x32,
    0x61, 0x76, 0x63, 0x31,
    0x6d, 0x70, 0x34, 0x31
  ]);
  
  // Fill remaining size with dummy data
  const remaining = Math.max(0, video.size - header.length);
  const paddingData = new Uint8Array(remaining).fill(0);
  
  const combinedData = new Uint8Array(header.length + paddingData.length);
  combinedData.set(header);
  combinedData.set(paddingData, header.length);
  
  return new Blob([combinedData], { type: video.format });
}

// Helper function to create corrupted video blob
export function createCorruptedVideoBlob(): Blob {
  const corruptedData = new Uint8Array(1024);
  // Fill with random data to simulate corruption
  crypto.getRandomValues(corruptedData);
  return new Blob([corruptedData], { type: 'video/mp4' });
}

export default {
  TEST_VIDEOS,
  TEST_ANNOTATIONS,
  TEST_PROJECTS,
  createMockVideoBlob,
  createCorruptedVideoBlob
};