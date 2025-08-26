/**
 * Test suite for Video URL Fixer utility
 */

import { fixVideoUrl, fixVideoObjectUrl, isVideoUrlValid, getVideoBaseUrl } from './videoUrlFixer';
import { getServiceConfig } from './envConfig';

// Mock the environment config
jest.mock('./envConfig', () => ({
  getServiceConfig: jest.fn((service) => {
    if (service === 'video') {
      return {
        baseUrl: 'http://155.138.239.131:8000',
        maxSizeMB: 100,
        supportedFormats: ['mp4', 'avi', 'mov', 'mkv']
      };
    }
    return {};
  })
}));

describe('Video URL Fixer', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('fixVideoUrl', () => {
    it('should fix localhost URLs', () => {
      const localhostUrl = 'http://localhost:8000/uploads/test-video.mp4';
      const result = fixVideoUrl(localhostUrl);
      expect(result).toBe('http://155.138.239.131:8000/uploads/test-video.mp4');
    });

    it('should convert relative URLs to absolute', () => {
      const relativeUrl = '/uploads/test-video.mp4';
      const result = fixVideoUrl(relativeUrl);
      expect(result).toBe('http://155.138.239.131:8000/uploads/test-video.mp4');
    });

    it('should construct URL from filename when no URL is provided', () => {
      const result = fixVideoUrl('', 'test-video.mp4');
      expect(result).toBe('http://155.138.239.131:8000/uploads/test-video.mp4');
    });

    it('should construct URL from id when no URL or filename is provided', () => {
      const result = fixVideoUrl('', '', 'video-123.mp4');
      expect(result).toBe('http://155.138.239.131:8000/uploads/video-123.mp4');
    });

    it('should return empty string when no URL, filename, or id is provided', () => {
      const result = fixVideoUrl('', '', '');
      expect(result).toBe('');
    });

    it('should return valid absolute URLs unchanged', () => {
      const validUrl = 'http://155.138.239.131:8000/uploads/test-video.mp4';
      const result = fixVideoUrl(validUrl);
      expect(result).toBe(validUrl);
    });

    it('should force absolute URLs when requested', () => {
      const result = fixVideoUrl('uploads/test.mp4', '', '', { forceAbsolute: true });
      expect(result).toBe('http://155.138.239.131:8000/uploads/test.mp4');
    });

    it('should prevent recursive :8000 appending', () => {
      // Test the exact problem scenario
      const originalUrl = 'http://localhost:8000/uploads/video.mp4';
      const firstFix = fixVideoUrl(originalUrl);
      expect(firstFix).toBe('http://155.138.239.131:8000/uploads/video.mp4');
      
      // This should NOT append another :8000
      const secondFix = fixVideoUrl(firstFix);
      expect(secondFix).toBe('http://155.138.239.131:8000/uploads/video.mp4');
      
      // Third fix should still be stable
      const thirdFix = fixVideoUrl(secondFix);
      expect(thirdFix).toBe('http://155.138.239.131:8000/uploads/video.mp4');
    });

    it('should handle malformed localhost URLs without corruption', () => {
      const malformedUrl = 'http://localhost:8000:8000/uploads/video.mp4';
      const result = fixVideoUrl(malformedUrl);
      // Should not create more port corruption
      expect(result).not.toContain(':8000:8000:8000');
      expect(result).not.toContain(':8000:8000');
      expect(result).toBe('http://155.138.239.131:8000/uploads/video.mp4');
    });

    it('should preserve path and query parameters when fixing URLs', () => {
      const urlWithQuery = 'http://localhost:8000/uploads/video.mp4?v=1&t=30';
      const result = fixVideoUrl(urlWithQuery);
      expect(result).toBe('http://155.138.239.131:8000/uploads/video.mp4?v=1&t=30');
    });

    it('should handle localhost without port correctly', () => {
      const localhostNoPort = 'http://localhost/uploads/video.mp4';
      const result = fixVideoUrl(localhostNoPort);
      expect(result).toBe('http://155.138.239.131:8000/uploads/video.mp4');
    });

    it('should handle 127.0.0.1 URLs correctly', () => {
      const loopbackUrl = 'http://127.0.0.1:8000/uploads/video.mp4';
      const result = fixVideoUrl(loopbackUrl);
      expect(result).toBe('http://155.138.239.131:8000/uploads/video.mp4');
      
      // Should not corrupt on second fix
      const secondFix = fixVideoUrl(result);
      expect(secondFix).toBe('http://155.138.239.131:8000/uploads/video.mp4');
    });
  });

  describe('fixVideoObjectUrl', () => {
    it('should fix video object URL in place', () => {
      const video = {
        id: 'test-id',
        url: 'http://localhost:8000/uploads/test.mp4',
        filename: 'test.mp4'
      };

      fixVideoObjectUrl(video);
      expect(video.url).toBe('http://155.138.239.131:8000/uploads/test.mp4');
    });
  });

  describe('isVideoUrlValid', () => {
    it('should validate HTTP URLs', () => {
      expect(isVideoUrlValid('http://example.com/video.mp4')).toBe(true);
    });

    it('should validate HTTPS URLs', () => {
      expect(isVideoUrlValid('https://example.com/video.mp4')).toBe(true);
    });

    it('should reject invalid URLs', () => {
      expect(isVideoUrlValid('not-a-url')).toBe(false);
      expect(isVideoUrlValid('')).toBe(false);
      expect(isVideoUrlValid('ftp://example.com/video.mp4')).toBe(false);
    });
  });

  describe('getVideoBaseUrl', () => {
    it('should return the configured video base URL', () => {
      const result = getVideoBaseUrl();
      expect(result).toBe('http://155.138.239.131:8000');
      expect(getServiceConfig).toHaveBeenCalledWith('video');
    });
  });
});