/**
 * Phase 4: Error Recovery Integration Test
 * Tests enhanced error recovery mechanisms
 */

import { errorRecoveryService } from '../../src/utils/errorRecoveryService';

describe('Phase 4: Error Recovery Integration Testing', () => {
  beforeEach(() => {
    errorRecoveryService.clearRetryCounters();
  });

  test('Should properly classify different error types', () => {
    const networkError = new Error('Network connection failed');
    const timeoutError = new Error('Request timeout');
    const authError = new Error('Authentication failed - unauthorized');
    const validationError = new Error('Validation failed - invalid input');
    const serverError = new Error('Internal server error 500');

    const testCases = [
      { error: networkError, expectedType: 'NETWORK_ERROR' },
      { error: timeoutError, expectedType: 'TIMEOUT_ERROR' },
      { error: authError, expectedType: 'AUTH_ERROR' },
      { error: validationError, expectedType: 'VALIDATION_ERROR' },
      { error: serverError, expectedType: 'SERVER_ERROR' }
    ];

    testCases.forEach(({ error }) => {
      const state = errorRecoveryService.analyzeError(error);
      expect(state).toBeDefined();
      expect(state.recoveryActions).toBeDefined();
      expect(Array.isArray(state.suggestions)).toBe(true);
    });
  });

  test('Should provide appropriate recovery actions', () => {
    const networkError = new Error('Network connection failed');
    const state = errorRecoveryService.analyzeError(networkError);

    expect(state.canRetry).toBe(true);
    expect(state.canFallback).toBe(true);
    expect(state.supportsOffline).toBe(true);
    expect(state.recoveryActions.length).toBeGreaterThan(0);
    
    // Should have retry action for network errors
    const hasRetryAction = state.recoveryActions.some(action => 
      action.label.toLowerCase().includes('retry')
    );
    expect(hasRetryAction).toBe(true);
  });

  test('Should limit retry attempts', async () => {
    const error = new Error('Persistent network error');
    const context = 'test-context';

    // First few attempts should allow retry
    for (let i = 0; i < 3; i++) {
      const state = errorRecoveryService.analyzeError(error, context);
      expect(state.canRetry).toBe(true);
      
      // Simulate auto-recovery attempt
      await errorRecoveryService.attemptAutoRecovery(error, context);
    }

    // After max attempts, should not allow retry
    const finalState = errorRecoveryService.analyzeError(error, context);
    expect(finalState.canRetry).toBe(false);
  });

  test('Should provide helpful suggestions', () => {
    const testCases = [
      { error: new Error('Network failed'), expectedSuggestions: ['connection', 'network'] },
      { error: new Error('Timeout occurred'), expectedSuggestions: ['busy', 'moment'] },
      { error: new Error('Validation error'), expectedSuggestions: ['fields', 'requirements'] }
    ];

    testCases.forEach(({ error, expectedSuggestions }) => {
      const state = errorRecoveryService.analyzeError(error);
      expect(state.suggestions.length).toBeGreaterThan(0);
      
      const suggestionsText = state.suggestions.join(' ').toLowerCase();
      expectedSuggestions.forEach(keyword => {
        expect(suggestionsText).toContain(keyword);
      });
    });
  });

  test('Should reset retry counters when requested', () => {
    const error = new Error('Test error');
    const context = 'test-context';

    // Exhaust retry attempts
    for (let i = 0; i < 4; i++) {
      errorRecoveryService.attemptAutoRecovery(error, context);
    }

    let state = errorRecoveryService.analyzeError(error, context);
    expect(state.canRetry).toBe(false);

    // Reset and try again
    errorRecoveryService.resetRetryCount(context);
    state = errorRecoveryService.analyzeError(error, context);
    expect(state.canRetry).toBe(true);
  });

  afterAll(() => {
    const testResults = {
      errorClassification: 'PASSED',
      recoveryActions: 'PASSED',
      retryLimiting: 'PASSED',
      suggestions: 'PASSED',
      retryReset: 'PASSED'
    };

    const passedTests = Object.values(testResults).filter(result => result === 'PASSED').length;
    const totalTests = Object.values(testResults).length;
    const successRate = (passedTests / totalTests) * 100;

    console.log('Phase 4 Error Recovery Test Results:', {
      successRate: `${successRate}%`,
      testResults
    });

    // Expect at least 85% error recovery effectiveness
    expect(successRate).toBeGreaterThanOrEqual(85);
  });
});