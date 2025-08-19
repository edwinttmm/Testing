/**
 * Jest Configuration for TypeScript Error Fix Tests
 * London School TDD Testing Environment
 */

module.exports = {
  // Test Environment
  testEnvironment: 'jsdom',
  
  // Setup Files
  setupFilesAfterEnv: [
    '<rootDir>/tests/setup/test-setup.ts',
    '<rootDir>/tests/setup/mock-setup.ts'
  ],
  
  // Module Path Mapping
  moduleNameMapping: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '^@tests/(.*)$': '<rootDir>/tests/$1',
    '^@mocks/(.*)$': '<rootDir>/tests/mocks/$1',
    '^@contracts/(.*)$': '<rootDir>/tests/contracts/$1',
    '^@fixtures/(.*)$': '<rootDir>/tests/fixtures/$1'
  },
  
  // File Extensions
  moduleFileExtensions: [
    'ts',
    'tsx',
    'js',
    'jsx',
    'json'
  ],
  
  // Transform Configuration
  transform: {
    '^.+\\.(ts|tsx)$': 'ts-jest',
    '^.+\\.(js|jsx)$': 'babel-jest'
  },
  
  // Test Match Patterns
  testMatch: [
    '<rootDir>/tests/unit/**/*.test.(ts|tsx)',
    '<rootDir>/tests/integration/**/*.test.(ts|tsx)',
    '<rootDir>/tests/**/*.spec.(ts|tsx)'
  ],
  
  // Coverage Configuration
  collectCoverage: true,
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    'tests/mocks/**/*.{ts,tsx}',
    'tests/contracts/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/*.test.{ts,tsx}',
    '!src/**/*.spec.{ts,tsx}'
  ],
  
  coverageDirectory: 'coverage/typescript-error-fixes',
  
  coverageReporters: [
    'text',
    'text-summary',
    'html',
    'lcov',
    'json-summary'
  ],
  
  coverageThreshold: {
    global: {
      branches: 90,
      functions: 90,
      lines: 90,
      statements: 90
    },
    './tests/mocks/': {
      branches: 95,
      functions: 95,
      lines: 95,
      statements: 95
    },
    './tests/contracts/': {
      branches: 100,
      functions: 100,
      lines: 100,
      statements: 100
    }
  },
  
  // Mock Configuration
  clearMocks: true,
  resetMocks: false,
  restoreMocks: true,
  
  // Test Timeout
  testTimeout: 10000,
  
  // Globals
  globals: {
    'ts-jest': {
      tsconfig: {
        jsx: 'react-jsx',
        esModuleInterop: true,
        allowSyntheticDefaultImports: true
      }
    }
  },
  
  // Module Directories
  moduleDirectories: [
    'node_modules',
    '<rootDir>/src',
    '<rootDir>/tests'
  ],
  
  // Ignore Patterns
  testPathIgnorePatterns: [
    '<rootDir>/node_modules/',
    '<rootDir>/dist/',
    '<rootDir>/build/'
  ],
  
  // Watch Plugins
  watchPlugins: [
    'jest-watch-typeahead/filename',
    'jest-watch-typeahead/testname'
  ],
  
  // Reporters
  reporters: [
    'default',
    [
      'jest-junit',
      {
        outputDirectory: 'coverage/typescript-error-fixes',
        outputName: 'junit.xml',
        classNameTemplate: '{classname}',
        titleTemplate: '{title}',
        ancestorSeparator: ' › '
      }
    ],
    [
      'jest-html-reporters',
      {
        publicPath: 'coverage/typescript-error-fixes',
        filename: 'report.html',
        expand: true,
        hideIcon: false
      }
    ]
  ],
  
  // Mock Patterns
  moduleNameMapping: {
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
    '\\.(jpg|jpeg|png|gif|eot|otf|webp|svg|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga)$': 
      '<rootDir>/tests/mocks/file-mock.js'
  },
  
  // London School TDD Specific Configuration
  testEnvironmentOptions: {
    url: 'http://localhost:3000'
  },
  
  // Custom Matchers
  setupFiles: [
    '<rootDir>/tests/setup/custom-matchers.ts'
  ],
  
  // Verbose Output for Contract Validation
  verbose: true,
  
  // Error on Deprecated
  errorOnDeprecated: true,
  
  // Detect Open Handles (for cleanup verification)
  detectOpenHandles: true,
  
  // Force Exit (ensures clean shutdown)
  forceExit: false,
  
  // Max Workers for Parallel Execution
  maxWorkers: '50%',
  
  // Snapshot Serializers
  snapshotSerializers: [
    '@emotion/jest/serializer',
    'enzyme-to-json/serializer'
  ]
};