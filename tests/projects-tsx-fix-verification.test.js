// Test to verify the TypeScript fixes in Projects.tsx
// This file verifies the specific errors mentioned were resolved:
// 1. useCallback import was added
// 2. loadAllProjectVideos function was moved before its usage

const fs = require('fs');
const path = require('path');

describe('Projects.tsx TypeScript Fixes', () => {
  let fileContent;

  beforeAll(() => {
    const filePath = path.join(__dirname, '../ai-model-validation-platform/frontend/src/pages/Projects.tsx');
    fileContent = fs.readFileSync(filePath, 'utf8');
  });

  test('should import useCallback from React', () => {
    // Check that useCallback is imported
    const importLine = fileContent.split('\n')[0];
    expect(importLine).toContain('useCallback');
    expect(importLine).toMatch(/import React, \{ useState, useEffect, useCallback \} from 'react'/);
  });

  test('should define loadAllProjectVideos before useEffect', () => {
    const lines = fileContent.split('\n');
    
    // Find the line where loadAllProjectVideos is defined
    const functionDefIndex = lines.findIndex(line => 
      line.trim().startsWith('const loadAllProjectVideos = useCallback')
    );
    
    // Find the line where useEffect uses loadAllProjectVideos in dependency array
    const useEffectIndex = lines.findIndex(line => 
      line.includes('}, [projects, loadAllProjectVideos]);')
    );
    
    expect(functionDefIndex).toBeGreaterThan(-1);
    expect(useEffectIndex).toBeGreaterThan(-1);
    expect(functionDefIndex).toBeLessThan(useEffectIndex);
  });

  test('should not have eslint disable comment for use-before-define', () => {
    // Should not contain the eslint-disable comment since function is now properly ordered
    expect(fileContent).not.toContain('eslint-disable-line @typescript-eslint/no-use-before-define');
  });

  test('should maintain useCallback dependency on projects', () => {
    // Verify that loadAllProjectVideos still has proper dependencies
    const functionMatch = fileContent.match(/const loadAllProjectVideos = useCallback\([\s\S]*?\}, \[projects\]\);/);
    expect(functionMatch).toBeTruthy();
  });
});