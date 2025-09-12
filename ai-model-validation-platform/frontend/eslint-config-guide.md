# ESLint Configuration Guide

## Overview

This project uses a sophisticated ESLint configuration that automatically adapts rules based on the environment (development vs production) to provide an optimal developer experience while maintaining strict production code quality.

## Configuration Files

### Main Configuration (`.eslintrc.js`)
- **Auto-detects environment** based on `NODE_ENV`
- **Development**: Relaxed rules, console warnings allowed
- **Production**: Strict rules, console statements are errors

### Environment-Specific Configs
- `.eslintrc.development.js` - Development-friendly rules
- `.eslintrc.production.js` - Production-strict rules

### Ignore Patterns (`.eslintignore`)
- Build outputs, node_modules, generated files
- Legacy and vendor code exceptions

## Console vs Logger Rules

### Development Environment
```javascript
// ✅ ALLOWED - Warnings only
console.log('Debug info');
console.info('Information');
console.debug('Debug details');

// ✅ ALWAYS ALLOWED
console.error('Error message');
console.warn('Warning message');
```

### Production Environment
```javascript
// ❌ ERROR - Not allowed in production
console.log('Debug info');

// ✅ ALLOWED - Critical error handling only
console.error('Critical error');
console.warn('Important warning');

// ✅ RECOMMENDED - Use logger instead
logger.info('Information');
logger.debug('Debug details');
```

## Available Scripts

### Linting Scripts
```bash
# Development linting (relaxed, max 50 warnings)
npm run lint:dev

# Production linting (strict, max 0 warnings)
npm run lint:prod

# General linting with current environment
npm run lint

# Auto-fix issues
npm run lint:fix

# Analyze logger usage
npm run logger-analysis

# Combined analysis
npm run lint:analyze
```

### Build Scripts
```bash
# Development build (uses dev linting)
npm run build:dev

# Production build (uses production linting)
npm run build
```

## Pre-commit Hooks

The project uses Husky and lint-staged to ensure production-quality code:

```json
"lint-staged": {
  "src/**/*.{ts,tsx}": [
    "npm run lint:prod",
    "git add"
  ]
}
```

This means every commit is checked against **production ESLint rules**.

## Exception Handling

### Critical Error Handling Files
Files that handle critical errors can use `console.error` and `console.warn`:

- `src/**/errorHandling.ts`
- `src/**/errorBoundary.tsx` 
- `src/**/crashReporter.ts`
- `src/utils/logger.ts`

### Test Files
Test files have relaxed rules:
- Development: No console restrictions
- Production: Console warnings only
- `@typescript-eslint/no-explicit-any` is relaxed

### Inline Overrides
For exceptional cases, use inline ESLint disables:

```typescript
// Emergency logging that must stay
// eslint-disable-next-line no-console
console.error('CRITICAL: System failure', error);
```

## Logger Usage Analysis

Run the custom analyzer to see console vs logger usage:

```bash
npm run logger-analysis
```

**Sample Output:**
```
=== ESLint Logger Usage Report ===
Files scanned: 181
Console statements found: 316
Logger statements found: 50
Logger adoption score: 13.7%

--- Console statements to replace ---
src/component/Example.tsx:42
  Current: console.log('Debug info')
  Suggest: logger.info('Debug info')
```

## Configuration Switching

The main `.eslintrc.js` automatically switches based on `NODE_ENV`:

```javascript
const isDevelopment = process.env.NODE_ENV === 'development' || 
                     process.env.NODE_ENV === 'test' || 
                     !process.env.NODE_ENV;
```

## Best Practices

### 1. Development Phase
- Use console statements freely for debugging
- Focus on functionality over linting perfection
- Address warnings gradually

### 2. Pre-Production
- Run `npm run lint:prod` regularly
- Replace console statements with logger calls
- Fix all TypeScript strict mode issues

### 3. Production Deployment
- Pre-commit hooks enforce production rules
- Zero console statements allowed (except error/warn)
- All TypeScript warnings must be resolved

### 4. Logger Migration
```typescript
// Before
console.log('User action:', action);
console.debug('State change:', newState);

// After
logger.info('User action:', action);
logger.debug('State change:', newState);
```

## Troubleshooting

### Common Issues

**Build failing on console statements:**
```bash
# Check what's failing
npm run lint:prod

# Fix automatically where possible
npm run lint:fix

# Manual fixes required for console -> logger migration
```

**Pre-commit hook blocking commits:**
```bash
# The hook runs production linting
# Fix all issues or commit will be blocked
npm run lint:prod
npm run lint:fix
```

**Too many warnings in development:**
```bash
# Development allows up to 50 warnings
# If exceeded, prioritize fixing critical issues
npm run lint:dev --max-warnings 100
```

## Migration Strategy

1. **Phase 1**: Set up configuration (✅ Complete)
2. **Phase 2**: Create logger utility if not exists
3. **Phase 3**: Gradually replace console statements
4. **Phase 4**: Enable strict production rules
5. **Phase 5**: Monitor and maintain

## Environment Detection

The configuration detects environment automatically:
- `NODE_ENV=development` → Development rules
- `NODE_ENV=production` → Production rules  
- `NODE_ENV=test` → Development rules
- No NODE_ENV → Development rules (safe default)

This ensures developers get helpful warnings without breaking their workflow, while production deployments maintain strict quality standards.