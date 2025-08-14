/**
 * Comprehensive Environment Compatibility Test Suite
 * Tests Windows MINGW64 environment with React 19.1.1 frontend
 */

import { describe, test, expect, beforeAll, afterAll } from '@jest/globals';
import { execSync } from 'child_process';
import { readFileSync, existsSync } from 'fs';
import * as path from 'path';

interface TestEnvironment {
  projectRoot: string;
  frontendRoot: string;
  nodeVersion: string;
  npmVersion: string;
  platform: string;
}

interface DependencyCheck {
  name: string;
  expected: string;
  actual: string;
  compatible: boolean;
}

describe('Windows MINGW64 Environment Compatibility', () => {
  let testEnv: TestEnvironment;

  beforeAll(async () => {
    testEnv = {
      projectRoot: process.cwd(),
      frontendRoot: path.join(process.cwd(), 'ai-model-validation-platform', 'frontend'),
      nodeVersion: process.version,
      npmVersion: execSync('npm --version', { encoding: 'utf8' }).trim(),
      platform: process.platform,
    };

    console.log('Test Environment:', testEnv);
  });

  describe('System Prerequisites', () => {
    test('Node.js version compatibility', () => {
      const nodeVersion = testEnv.nodeVersion;
      const majorVersion = parseInt(nodeVersion.slice(1).split('.')[0]);
      
      expect(majorVersion).toBeGreaterThanOrEqual(18);
      expect(majorVersion).toBeLessThanOrEqual(24); // Future-proofing
    });

    test('NPM version compatibility', () => {
      const npmVersion = testEnv.npmVersion;
      const majorVersion = parseInt(npmVersion.split('.')[0]);
      
      expect(majorVersion).toBeGreaterThanOrEqual(8);
    });

    test('Project structure exists', () => {
      expect(existsSync(testEnv.frontendRoot)).toBe(true);
      expect(existsSync(path.join(testEnv.frontendRoot, 'package.json'))).toBe(true);
      expect(existsSync(path.join(testEnv.frontendRoot, 'tsconfig.json'))).toBe(true);
    });
  });

  describe('Dependency Compatibility', () => {
    let packageJson: any;
    let packageLock: any;

    beforeAll(() => {
      packageJson = JSON.parse(readFileSync(path.join(testEnv.frontendRoot, 'package.json'), 'utf8'));
      
      if (existsSync(path.join(testEnv.frontendRoot, 'package-lock.json'))) {
        packageLock = JSON.parse(readFileSync(path.join(testEnv.frontendRoot, 'package-lock.json'), 'utf8'));
      }
    });

    test('React 19.1.1 compatibility', () => {
      const reactVersion = packageJson.dependencies?.react;
      expect(reactVersion).toBeDefined();
      expect(reactVersion).toMatch(/^19\./);
    });

    test('TypeScript version consistency', () => {
      const tsInPackage = packageJson.dependencies?.typescript || packageJson.devDependencies?.typescript;
      
      if (packageLock && tsInPackage) {
        const tsInLock = packageLock.packages?.['']?.dependencies?.typescript || 
                        packageLock.packages?.['']?.devDependencies?.typescript;
        
        if (tsInLock) {
          const packageMajor = tsInPackage.replace(/[^\d.]/g, '').split('.')[0];
          const lockMajor = tsInLock.replace(/[^\d.]/g, '').split('.')[0];
          
          expect(packageMajor).toBe(lockMajor);
        }
      }
    });

    test('@types/node compatibility', () => {
      const typesNode = packageJson.dependencies?.['@types/node'] || packageJson.devDependencies?.['@types/node'];
      
      if (typesNode) {
        const majorVersion = parseInt(typesNode.replace(/[^\d]/g, '').slice(0, 2));
        expect(majorVersion).toBeGreaterThanOrEqual(18);
      }
    });

    test('Testing library compatibility', () => {
      const testingReact = packageJson.devDependencies?.['@testing-library/react'];
      const userEvent = packageJson.devDependencies?.['@testing-library/user-event'];
      
      if (testingReact) {
        expect(parseInt(testingReact.split('.')[0])).toBeGreaterThanOrEqual(15);
      }
      
      if (userEvent) {
        expect(parseInt(userEvent.split('.')[0])).toBeGreaterThanOrEqual(14);
      }
    });
  });

  describe('TypeScript Configuration', () => {
    let tsConfig: any;

    beforeAll(() => {
      tsConfig = JSON.parse(readFileSync(path.join(testEnv.frontendRoot, 'tsconfig.json'), 'utf8'));
    });

    test('Target ES version for React 19', () => {
      expect(tsConfig.compilerOptions.target).toMatch(/ES2020|ES2021|ES2022/i);
    });

    test('JSX configuration for React 19', () => {
      expect(tsConfig.compilerOptions.jsx).toBe('react-jsx');
    });

    test('Module resolution configuration', () => {
      expect(tsConfig.compilerOptions.moduleResolution).toBe('node');
      expect(tsConfig.compilerOptions.module).toBe('esnext');
    });

    test('Required compiler options', () => {
      const required = [
        'strict',
        'esModuleInterop',
        'allowSyntheticDefaultImports',
        'forceConsistentCasingInFileNames',
        'skipLibCheck',
      ];

      required.forEach(option => {
        expect(tsConfig.compilerOptions[option]).toBe(true);
      });
    });
  });

  describe('Build System Compatibility', () => {
    test('CRACO configuration exists', () => {
      expect(existsSync(path.join(testEnv.frontendRoot, 'craco.config.js'))).toBe(true);
    });

    test('TypeScript compilation', () => {
      expect(() => {
        execSync('npx tsc --noEmit', { 
          cwd: testEnv.frontendRoot,
          stdio: 'pipe',
          timeout: 60000,
        });
      }).not.toThrow();
    });

    test('Build process', () => {
      expect(() => {
        execSync('npm run build', { 
          cwd: testEnv.frontendRoot,
          stdio: 'pipe',
          timeout: 300000, // 5 minutes
        });
      }).not.toThrow();
    }, 300000);

    test('Test execution', () => {
      expect(() => {
        execSync('npm test -- --coverage --watchAll=false', { 
          cwd: testEnv.frontendRoot,
          stdio: 'pipe',
          timeout: 120000, // 2 minutes
        });
      }).not.toThrow();
    }, 120000);
  });

  describe('Cross-Platform Features', () => {
    test('Package.json scripts for Windows/Unix', () => {
      const scripts = packageJson.scripts;
      
      // Should have cross-platform scripts
      expect(scripts.start).toBeDefined();
      expect(scripts.build).toBeDefined();
      
      // Ideally should have platform-specific scripts
      if (scripts['start:windows'] && scripts['start:unix']) {
        expect(scripts['start:windows']).toContain('set PORT');
        expect(scripts['start:unix']).toContain('PORT=');
      }
    });

    test('Engine constraints', () => {
      if (packageJson.engines) {
        expect(packageJson.engines.node).toMatch(/>=18/);
        expect(packageJson.engines.npm).toMatch(/>=8/);
      }
    });
  });

  describe('Performance Optimizations', () => {
    test('Bundle analysis capability', () => {
      const scripts = packageJson.scripts;
      expect(scripts['build:analyze'] || scripts.analyze).toBeDefined();
    });

    test('Browserslist configuration', () => {
      expect(packageJson.browserslist).toBeDefined();
      
      if (packageJson.browserslist.production) {
        expect(packageJson.browserslist.production).toContain('>0.2%');
        expect(packageJson.browserslist.production).toContain('not dead');
      }
    });
  });

  describe('GPU Detection and Fallbacks', () => {
    test('Environment detector utility exists', () => {
      const utilPath = path.join(testEnv.frontendRoot, 'src', 'utils', 'environmentDetector.ts');
      expect(existsSync(utilPath) || existsSync(utilPath.replace('.ts', '.js'))).toBe(true);
    });

    test('GPU detector utility exists', () => {
      const utilPath = path.join(testEnv.frontendRoot, 'src', 'utils', 'gpuDetector.ts');
      expect(existsSync(utilPath) || existsSync(utilPath.replace('.ts', '.js'))).toBe(true);
    });
  });

  afterAll(() => {
    console.log('Environment compatibility tests completed');
    console.log('Results summary:');
    console.log(`- Node.js: ${testEnv.nodeVersion}`);
    console.log(`- NPM: ${testEnv.npmVersion}`);
    console.log(`- Platform: ${testEnv.platform}`);
    console.log(`- Frontend: ${existsSync(testEnv.frontendRoot) ? 'Found' : 'Missing'}`);
  });
});

describe('Automated Fix Validation', () => {
  test('All critical dependencies resolved', async () => {
    const packageJson = JSON.parse(readFileSync(path.join(process.cwd(), 'ai-model-validation-platform', 'frontend', 'package.json'), 'utf8'));
    
    const criticalDeps = [
      'react',
      'react-dom',
      'typescript',
      '@types/node',
      '@types/react',
    ];

    criticalDeps.forEach(dep => {
      const version = packageJson.dependencies?.[dep] || packageJson.devDependencies?.[dep];
      expect(version).toBeDefined();
    });
  });

  test('Configuration files updated', () => {
    const frontendRoot = path.join(process.cwd(), 'ai-model-validation-platform', 'frontend');
    
    // Check if tsconfig.json has been updated
    const tsConfig = JSON.parse(readFileSync(path.join(frontendRoot, 'tsconfig.json'), 'utf8'));
    expect(tsConfig.compilerOptions.target).not.toBe('es5');
    expect(tsConfig.compilerOptions.jsx).toBe('react-jsx');
  });

  test('Utility files created', () => {
    const utilsDir = path.join(process.cwd(), 'ai-model-validation-platform', 'frontend', 'src', 'utils');
    
    if (existsSync(utilsDir)) {
      const files = ['environmentDetector', 'gpuDetector'];
      files.forEach(file => {
        const tsPath = path.join(utilsDir, `${file}.ts`);
        const jsPath = path.join(utilsDir, `${file}.js`);
        expect(existsSync(tsPath) || existsSync(jsPath)).toBe(true);
      });
    }
  });
});

export { TestEnvironment, DependencyCheck };