module.exports = {
  extends: [
    'react-app',
    'react-app/jest'
  ],
  env: {
    browser: true,
    es2021: true,
    node: true,
    development: true
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
  ],
  rules: {
    // DEVELOPMENT FRIENDLY RULES
    // Console statements are warnings in development
    'no-console': ['warn', {
      allow: ['error', 'warn', 'info', 'debug']
    }],
    'no-debugger': 'warn', // Allow debugger in development
    'no-alert': 'warn',
    
    // TypeScript relaxed rules for development
    '@typescript-eslint/no-unused-vars': ['warn', { 
      argsIgnorePattern: '^_',
      varsIgnorePattern: '^_',
      ignoreRestSiblings: true
    }],
    '@typescript-eslint/no-explicit-any': 'warn',
    '@typescript-eslint/prefer-nullish-coalescing': 'warn',
    '@typescript-eslint/prefer-optional-chain': 'warn',
    
    // Code quality - relaxed for development
    'prefer-const': 'warn',
    'no-var': 'warn',
    'no-undef': 'error', // Still error for safety
    'no-unreachable': 'warn',
    'no-unused-expressions': 'warn',
    
    // Security - still important in development
    'no-eval': 'error',
    'no-implied-eval': 'error',
    'no-script-url': 'error',
    
    // Performance - relaxed
    'no-loop-func': 'warn',
    'no-await-in-loop': 'off' // Allow for development/testing
  },
  overrides: [
    {
      // Development utilities have no console restrictions
      files: [
        'src/utils/logger.ts',
        'src/utils/debugger.ts',
        'src/utils/devTools.ts'
      ],
      rules: {
        'no-console': 'off',
        'no-debugger': 'off'
      }
    },
    {
      // Test files are very relaxed
      files: [
        '**/*.test.ts',
        '**/*.test.tsx',
        '**/*.spec.ts',
        '**/*.spec.tsx'
      ],
      rules: {
        'no-console': 'off',
        'no-debugger': 'off',
        '@typescript-eslint/no-explicit-any': 'off'
      }
    }
  ]
};