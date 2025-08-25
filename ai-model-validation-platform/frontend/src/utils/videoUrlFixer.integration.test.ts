/**
 * Integration Test for Video URL Fixer
 * Verifies that localhost URLs are properly converted to the correct backend URL
 */

import { fixVideoUrl, fixVideoObjectUrl } from './videoUrlFixer';

// Mock environment config to simulate production scenario
jest.mock('./envConfig', () => ({
  getServiceConfig: jest.fn((service: string) => {
    if (service === 'video') {
      return {
        baseUrl: 'http://155.138.239.131:8000',
        maxSizeMB: 100,
        supportedFormats: ['mp4', 'avi', 'mov']
      };
    }
    return {};
  })
}));

describe('Video URL Fixer Integration Tests', () => {
  describe('Localhost URL Conversion', () => {
    it('should convert localhost video URLs to production URLs', () => {
      const testCases = [
        {
          input: 'http://localhost:8000/uploads/30adaef3-8430-476d-a126-6606a6ae2a6f.mp4',
          expected: 'http://155.138.239.131:8000/uploads/30adaef3-8430-476d-a126-6606a6ae2a6f.mp4',
          description: 'Basic localhost to production URL conversion'
        },
        {
          input: 'http://localhost:8000/uploads/test-video.mp4',
          expected: 'http://155.138.239.131:8000/uploads/test-video.mp4',
          description: 'Test video localhost conversion'
        },
        {
          input: '/uploads/relative-video.mp4',
          expected: 'http://155.138.239.131:8000/uploads/relative-video.mp4',
          description: 'Relative URL conversion'
        }
      ];

      testCases.forEach(({ input, expected, description }) => {
        const result = fixVideoUrl(input);
        expect(result).toBe(expected);
        console.log(`✅ ${description}: ${input} → ${result}`);
      });
    });

    it('should handle video objects correctly', () => {
      const testVideos = [
        {
          id: 'video-1',
          filename: 'test-video.mp4',
          url: 'http://localhost:8000/uploads/test-video.mp4'
        },
        {
          id: 'video-2',
          filename: 'another-video.mp4',
          url: '/uploads/another-video.mp4'
        },
        {
          id: 'video-3',
          filename: 'no-url-video.mp4',
          url: ''
        }
      ];

      testVideos.forEach(video => {
        const originalUrl = video.url;
        fixVideoObjectUrl(video);
        
        console.log(`📹 Video ${video.id}: ${originalUrl} → ${video.url}`);
        expect(video.url).toMatch(/^http:\/\/155\.138\.239\.131:8000/);
      });
    });

    it('should not modify already correct URLs', () => {
      const correctUrls = [
        'http://155.138.239.131:8000/uploads/correct-video.mp4',
        'https://155.138.239.131:8000/uploads/secure-video.mp4',
        'https://external-cdn.com/video.mp4'
      ];

      correctUrls.forEach(url => {
        const result = fixVideoUrl(url);
        expect(result).toBe(url);
        console.log(`✅ Correct URL unchanged: ${url}`);
      });
    });
  });

  describe('Error Prevention', () => {
    it('should handle edge cases gracefully', () => {
      const edgeCases = [
        { input: '', expected: '', description: 'Empty string' },
        { input: undefined, expected: '', description: 'Undefined URL' },
        { input: null as any, expected: '', description: 'Null URL' }
      ];

      edgeCases.forEach(({ input, expected, description }) => {
        const result = fixVideoUrl(input);
        expect(result).toBe(expected);
        console.log(`🛡️ ${description} handled: "${input}" → "${result}"`);
      });
    });
  });

  describe('Ground Truth Interface Simulation', () => {
    it('should fix the specific Ground Truth ERR_CONNECTION_REFUSED issue', () => {
      // Simulate the exact scenario from the bug report
      const problematicVideo = {
        id: '30adaef3-8430-476d-a126-6606a6ae2a6f',
        filename: '30adaef3-8430-476d-a126-6606a6ae2a6f.mp4',
        url: 'http://localhost:8000/uploads/30adaef3-8430-476d-a126-6606a6ae2a6f.mp4'
      };

      const originalUrl = problematicVideo.url;
      fixVideoObjectUrl(problematicVideo);

      console.log('🔧 Ground Truth Video Fix:');
      console.log(`  Before: ${originalUrl}`);
      console.log(`  After:  ${problematicVideo.url}`);

      expect(problematicVideo.url).toBe('http://155.138.239.131:8000/uploads/30adaef3-8430-476d-a126-6606a6ae2a6f.mp4');
      expect(problematicVideo.url).not.toContain('localhost');
    });
  });

  describe('Multiple Video Batch Processing', () => {
    it('should handle arrays of videos correctly', () => {
      const videos = [
        { id: '1', url: 'http://localhost:8000/uploads/video1.mp4', filename: 'video1.mp4' },
        { id: '2', url: '/uploads/video2.mp4', filename: 'video2.mp4' },
        { id: '3', url: '', filename: 'video3.mp4' },
        { id: '4', url: 'http://155.138.239.131:8000/uploads/video4.mp4', filename: 'video4.mp4' }
      ];

      videos.forEach(fixVideoObjectUrl);

      videos.forEach((video, index) => {
        console.log(`📹 Video ${index + 1}: ${video.url}`);
        expect(video.url).toMatch(/^http:\/\/155\.138\.239\.131:8000/);
        expect(video.url).not.toContain('localhost');
      });
    });
  });
});

export {};