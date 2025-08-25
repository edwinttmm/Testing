/**
 * Test suite for Video URL Fixer utility
 */

import { fixVideoUrl, fixVideoObjectUrl, isVideoUrlValid, getVideoBaseUrl } from './videoUrlFixer';
import { getServiceConfig } from './envConfig';

// Mock the environment config
jest.mock('./envConfig', () => ({
  getServiceConfig: jest.fn(() => ({
    baseUrl: 'http://155.138.239.131:8000'
  }))
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