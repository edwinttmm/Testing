/**
 * URL Fix Validation Test - Demonstrating the recursive :8000 fix
 * 
 * This test file demonstrates the exact issue that was occurring:
 * - Original: http://localhost:8000/uploads/video.mp4
 * - After 1 fix: http://localhost:8000:8000/uploads/video.mp4 (BROKEN!)
 * - After 2 fixes: http://localhost:8000:8000:8000/uploads/video.mp4 (WORSE!)
 * 
 * With the new fix using proper URL parsing, this no longer happens.
 */

import { fixVideoUrl } from '../utils/videoUrlFixer';

describe('URL Fix Validation - Preventing Recursive :8000 Appending', () => {
  // Mock the environment config for these tests
  beforeAll(() => {
    jest.doMock('../utils/envConfig', () => ({
      getServiceConfig: jest.fn(() => ({
        baseUrl: 'http://155.138.239.131:8000'
      }))
    }));
  });

  it('should demonstrate the problem that WAS occurring', () => {
    // This is what WOULD have happened with the old broken logic
    const originalUrl = 'http://localhost:8000/uploads/video.mp4';
    const expectedFixed = 'http://155.138.239.131:8000/uploads/video.mp4';
    
    // First fix - should work correctly
    const firstFix = fixVideoUrl(originalUrl);
    expect(firstFix).toBe(expectedFixed);
    console.log('First fix:', originalUrl, '->', firstFix);
    
    // Second fix - this is where the OLD code would break
    const secondFix = fixVideoUrl(firstFix);
    expect(secondFix).toBe(expectedFixed); // Should NOT become :8000:8000
    expect(secondFix).not.toContain(':8000:8000');
    console.log('Second fix (stable):', firstFix, '->', secondFix);
    
    // Third fix - should still be stable
    const thirdFix = fixVideoUrl(secondFix);
    expect(thirdFix).toBe(expectedFixed);
    expect(thirdFix).not.toContain(':8000:8000:8000');
    console.log('Third fix (stable):', secondFix, '->', thirdFix);
  });

  it('should handle already-corrupted URLs and fix them', () => {
    // If we have URLs that are already corrupted, we should be able to fix them
    const corruptedUrl = 'http://localhost:8000:8000/uploads/video.mp4';
    const result = fixVideoUrl(corruptedUrl);
    
    expect(result).toBe('http://155.138.239.131:8000/uploads/video.mp4');
    expect(result).not.toContain(':8000:8000');
    expect(result).not.toContain(':8000:8000:8000');
  });

  it('should preserve query parameters and anchors during URL fixing', () => {
    const urlWithParams = 'http://localhost:8000/uploads/video.mp4?v=1&t=30#start';
    const result = fixVideoUrl(urlWithParams);
    
    expect(result).toBe('http://155.138.239.131:8000/uploads/video.mp4?v=1&t=30#start');
    expect(result).toContain('?v=1&t=30#start');
  });

  it('should handle localhost variations correctly', () => {
    const testCases = [
      {
        input: 'http://localhost:8000/video.mp4',
        expected: 'http://155.138.239.131:8000/video.mp4'
      },
      {
        input: 'http://localhost/video.mp4',
        expected: 'http://155.138.239.131:8000/video.mp4'
      },
      {
        input: 'http://127.0.0.1:8000/video.mp4',
        expected: 'http://155.138.239.131:8000/video.mp4'
      },
      {
        input: 'http://127.0.0.1/video.mp4',
        expected: 'http://155.138.239.131:8000/video.mp4'
      }
    ];

    testCases.forEach(({ input, expected }) => {
      const result = fixVideoUrl(input);
      expect(result).toBe(expected);
      
      // Test stability - second fix should yield same result
      const secondFix = fixVideoUrl(result);
      expect(secondFix).toBe(expected);
    });
  });
});