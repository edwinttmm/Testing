import type { Config } from '@jest/types';

const config: Config.InitialOptions = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  roots: ['<rootDir>'],
  testMatch: [
    '**/__tests__/**/*.ts',
    '**/?(*.)+(spec|test).ts'
  ],
  transform: {
    '^.+\\.ts$': 'ts-jest'
  },
  collectCoverageFrom: [
    '**/*.ts',
    '!**/*.d.ts',
    '!**/mocks/**/*.ts',
    '!jest.config.ts',
    '!setup.ts'
  ],
  coverageDirectory: 'coverage',
  coverageReporters: [
    'text',
    'html',
    'lcov',
    'clover'
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  },
  testTimeout: 30000,
  maxWorkers: 4,
  verbose: true,
  testPathIgnorePatterns: [
    '/node_modules/',
    '/dist/'
  ],
  moduleNameMapping: {
    '^@/(.*)$': '<rootDir>/../ai-model-validation-platform/frontend/src/$1'
  },
  setupFilesAfterEnv: ['<rootDir>/setup.ts'],
  globals: {
    'ts-jest': {
      useESM: true,
      isolatedModules: true
    }
  }
};

export default config;