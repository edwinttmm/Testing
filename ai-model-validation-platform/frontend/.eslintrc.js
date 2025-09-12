// Main ESLint configuration - automatically switches based on NODE_ENV
const isDevelopment = process.env.NODE_ENV === 'development' || 
                     process.env.NODE_ENV === 'test' || 
                     !process.env.NODE_ENV;

const baseConfig = {
  extends: [
    'react-app',
    'react-app/jest'
  ],
  env: {
    browser: true,
    es2021: true,
    node: true
  },
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaFeatures: {
      jsx: true
    },
    ecmaVersion: 12,
    sourceType: 'module'
  },
  plugins: [
    '@typescript-eslint'
  ]
};

// Development configuration
const developmentRules = {
  'no-console': ['warn', {
    allow: ['error', 'warn', 'info', 'debug']
  }],
  'no-debugger': 'warn',
  '@typescript-eslint/no-unused-vars': ['warn', { 
    argsIgnorePattern: '^_',
    varsIgnorePattern: '^_',
    ignoreRestSiblings: true
  }],
  '@typescript-eslint/no-explicit-any': 'error', // Upgraded to error to prevent regression
  'prefer-const': 'warn',
  'no-var': 'warn',
  'react-hooks/exhaustive-deps': 'warn' // Ensure proper hook dependencies
};

// Production configuration
const productionRules = {
  'no-console': 'error', // Strict no console in production
  'no-debugger': 'error',
  '@typescript-eslint/no-unused-vars': ['error', { 
    argsIgnorePattern: '^_',
    varsIgnorePattern: '^_'
  }],
  '@typescript-eslint/no-explicit-any': 'error',
  'prefer-const': 'error',
  'no-var': 'error',
  'no-eval': 'error',
  'no-implied-eval': 'error'
};

module.exports = {
  ...baseConfig,
  rules: isDevelopment ? developmentRules : productionRules,
  overrides: [
    {
      // Exception for critical error handling - always allow console.error/warn
      files: [
        'src/**/errorHandling.ts',
        'src/**/errorBoundary.tsx',
        'src/**/crashReporter.ts',
        'src/utils/logger.ts'
      ],
      rules: {
        'no-console': ['warn', {
          allow: ['error', 'warn']
        }]
      }
    },
    {
      // Test files are more relaxed
      files: [
        '**/*.test.ts',
        '**/*.test.tsx',
        '**/*.spec.ts',
        '**/*.spec.tsx'
      ],
      rules: {
        'no-console': isDevelopment ? 'off' : 'warn',
        '@typescript-eslint/no-explicit-any': 'warn'
      }
    }
  ]
};