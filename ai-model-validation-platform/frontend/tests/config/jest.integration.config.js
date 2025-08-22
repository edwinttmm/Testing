/**
 * Jest Configuration for Integration Tests
 * 
 * Optimized configuration for full-stack integration testing
 * of the AI Model Validation Platform
 */

const path = require('path');

module.exports = {
  // Test environment
  testEnvironment: 'jsdom',
  
  // Root directory
  rootDir: path.resolve(__dirname, '../..'),
  
  // Test patterns
  testMatch: [
    '<rootDir>/tests/integration/**/*.test.{js,ts,tsx}',
    '<rootDir>/tests/e2e/**/*.test.{js,ts,tsx}',
    '<rootDir>/tests/performance/**/*.test.{js,ts,tsx}'
  ],
  
  // Setup files
  setupFilesAfterEnv: [
    '<rootDir>/tests/config/setup-integration.ts',
    '<rootDir>/src/setupTests.ts'
  ],
  
  // Module resolution
  moduleNameMapping: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '^@tests/(.*)$': '<rootDir>/tests/$1',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
    '\\.(jpg|jpeg|png|gif|eot|otf|webp|svg|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga)$': '<rootDir>/tests/mocks/fileMock.js'
  },
  
  // Transform configuration
  transform: {
    '^.+\\.(ts|tsx)$': ['ts-jest', {
      tsconfig: {
        jsx: 'react-jsx',
        esModuleInterop: true,
        allowSyntheticDefaultImports: true
      }
    }],
    '^.+\\.(js|jsx)$': ['babel-jest', {
      presets: [
        ['@babel/preset-env', { targets: { node: 'current' } }],
        ['@babel/preset-react', { runtime: 'automatic' }]
      ]
    }]
  },
  
  // File extensions
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  
  // Coverage configuration
  collectCoverage: true,
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/index.tsx',
    '!src/reportWebVitals.ts',
    '!src/setupTests.ts',
    '!src/**/*.stories.{ts,tsx}',
    '!src/**/*.test.{ts,tsx}'
  ],
  
  coverageDirectory: '<rootDir>/coverage/integration',
  
  coverageReporters: [
    'text',
    'lcov',
    'html',
    'json-summary'
  ],
  
  // Coverage thresholds for integration tests
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 75,
      lines: 80,
      statements: 80
    },
    './src/components/': {
      branches: 75,
      functions: 80,
      lines: 85,
      statements: 85
    },
    './src/pages/': {
      branches: 70,
      functions: 75,
      lines: 80,
      statements: 80
    },
    './src/services/': {
      branches: 80,
      functions: 85,
      lines: 90,
      statements: 90
    }
  },
  
  // Test timeout
  testTimeout: 30000,
  
  // Retry configuration
  retry: {
    times: 2,
    condition: (err, testPath) => {
      // Retry flaky network-dependent tests
      return testPath.includes('integration') || testPath.includes('e2e');
    }
  },
  
  // Global variables
  globals: {
    'ts-jest': {
      useESM: true
    },
    '__INTEGRATION_TEST__': true,
    '__TEST_TIMEOUT__': 30000
  },
  
  // Test environment options
  testEnvironmentOptions: {
    url: 'http://localhost:3000',
    userAgent: 'jest-integration-tests'
  },
  
  // Reporters
  reporters: [
    'default',
    ['jest-html-reporters', {
      publicPath: '<rootDir>/coverage/integration/html-report',
      filename: 'integration-report.html',
      expand: true,
      hideIcon: false,
      pageTitle: 'Integration Test Report'
    }],
    ['jest-junit', {
      outputDirectory: '<rootDir>/coverage/integration',
      outputName: 'junit.xml',
      suiteName: 'Integration Tests'
    }]
  ],
  
  // Verbose output
  verbose: true,
  
  // Detect memory leaks
  detectLeaks: true,
  
  // Force exit after tests complete
  forceExit: true,
  
  // Clear mocks between tests
  clearMocks: true,
  
  // Restore mocks after each test
  restoreMocks: true,
  
  // Maximum worker processes
  maxWorkers: process.env.CI ? 2 : '50%',
  
  // Cache configuration
  cache: true,
  cacheDirectory: '<rootDir>/node_modules/.cache/jest-integration',
  
  // Ignore patterns
  testPathIgnorePatterns: [
    '<rootDir>/node_modules/',
    '<rootDir>/build/',
    '<rootDir>/coverage/'
  ],
  
  // Watch plugins
  watchPlugins: [
    'jest-watch-typeahead/filename',
    'jest-watch-typeahead/testname'
  ],
  
  // Custom matcher paths
  setupFilesAfterEnv: [
    '<rootDir>/tests/config/setup-integration.ts'
  ]
};
