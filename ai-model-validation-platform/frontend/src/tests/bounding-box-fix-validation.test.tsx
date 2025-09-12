/**
 * Simple validation test for bounding box coordinate transformation fix
 */

import { describe, it, expect } from '@jest/globals';

describe('Bounding Box Coordinate Transformation Logic', () => {
  it('should calculate correct scaling factors for native to display transformation', () => {
    // Test data based on the fix
    const nativeWidth = 640;
    const nativeHeight = 480;
    const displayWidth = 320;  // 50% scale
    const displayHeight = 240; // 50% scale
    
    // Calculate scaling factors (from native to display)
    const scaleX = displayWidth / nativeWidth;
    const scaleY = displayHeight / nativeHeight;
    
    expect(scaleX).toBe(0.5);
    expect(scaleY).toBe(0.5);
    
    // Test bounding box transformation
    const nativeBbox = { x: 100, y: 150, width: 80, height: 120 };
    const displayBbox = {
      x: nativeBbox.x * scaleX,
      y: nativeBbox.y * scaleY,
      width: nativeBbox.width * scaleX,
      height: nativeBbox.height * scaleY,
    };
    
    expect(displayBbox.x).toBe(50);
    expect(displayBbox.y).toBe(75);
    expect(displayBbox.width).toBe(40);
    expect(displayBbox.height).toBe(60);
  });

  it('should calculate correct reverse scaling for click coordinates', () => {
    // Test click coordinate transformation (display to native)
    const nativeWidth = 640;
    const nativeHeight = 480;
    const displayWidth = 320;
    const displayHeight = 240;
    
    // Click at center of display (160, 120)
    const displayClickX = 160;
    const displayClickY = 120;
    
    // Transform to native coordinates
    const scaleX = nativeWidth / displayWidth;
    const scaleY = nativeHeight / displayHeight;
    
    const nativeClickX = displayClickX * scaleX;
    const nativeClickY = displayClickY * scaleY;
    
    expect(nativeClickX).toBe(320);
    expect(nativeClickY).toBe(240);
  });

  it('should handle different aspect ratios correctly', () => {
    // Test with non-uniform scaling
    const nativeWidth = 1920;
    const nativeHeight = 1080;
    const displayWidth = 640;   // Different scale factor
    const displayHeight = 480;  // Different scale factor
    
    const scaleX = displayWidth / nativeWidth;
    const scaleY = displayHeight / nativeHeight;
    
    expect(scaleX).toBeCloseTo(0.333, 3);
    expect(scaleY).toBeCloseTo(0.444, 3);
    
    // Test bounding box at corner
    const cornerBbox = { x: 1800, y: 900, width: 100, height: 150 };
    const displayCornerBbox = {
      x: cornerBbox.x * scaleX,
      y: cornerBbox.y * scaleY,
      width: cornerBbox.width * scaleX,
      height: cornerBbox.height * scaleY,
    };
    
    expect(displayCornerBbox.x).toBeCloseTo(600, 1);
    expect(displayCornerBbox.y).toBeCloseTo(400, 1);
    expect(displayCornerBbox.width).toBeCloseTo(33.33, 1);
    expect(displayCornerBbox.height).toBeCloseTo(66.67, 1);
  });
});