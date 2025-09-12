module.exports = {
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
    sourceType: 'module',
    project: './tsconfig.json'
  },
  plugins: [
    '@typescript-eslint'
  ],
  rules: {
    // PRODUCTION STRICT RULES
    // Console statements are errors in production
    'no-console': 'error', // No console statements allowed in production
    'no-debugger': 'error',
    'no-alert': 'error',
    
    // TypeScript strict rules
    '@typescript-eslint/no-unused-vars': ['error', { 
      argsIgnorePattern: '^_',
      varsIgnorePattern: '^_'
    }],
    '@typescript-eslint/no-explicit-any': 'error',
    // Remove rules that require project config for now
    // '@typescript-eslint/prefer-nullish-coalescing': 'error',
    // '@typescript-eslint/prefer-optional-chain': 'error',
    
    // Code quality
    'prefer-const': 'error',
    'no-var': 'error',
    'no-undef': 'error',
    'no-unreachable': 'error',
    'no-unused-expressions': 'error',
    
    // Security
    'no-eval': 'error',
    'no-implied-eval': 'error',
    'no-script-url': 'error',
    
    // Performance
    'no-loop-func': 'error',
    'no-await-in-loop': 'warn'
  },
  overrides: [
    {
      // Exception for error handling files
      files: [
        'src/**/errorHandling.ts',
        'src/**/errorBoundary.tsx',
        'src/**/crashReporter.ts'
      ],
      rules: {
        'no-console': ['warn', {
          allow: ['error', 'warn']
        }]
      }
    },
    {
      // Exception for development utilities
      files: [
        'src/utils/logger.ts',
        'src/utils/debugger.ts'
      ],
      rules: {
        'no-console': 'off' // Logger utility can use console
      }
    },
    {
      // Test files can use console for debugging and exclude from project parsing
      files: [
        '**/*.test.ts',
        '**/*.test.tsx',
        '**/*.spec.ts',
        '**/*.spec.tsx'
      ],
      parser: '@typescript-eslint/parser',
      parserOptions: {
        ecmaFeatures: {
          jsx: true
        },
        ecmaVersion: 12,
        sourceType: 'module'
        // Remove project config for test files
      },
      rules: {
        'no-console': 'warn',
        '@typescript-eslint/no-explicit-any': 'warn'
      }
    }
  ]
};