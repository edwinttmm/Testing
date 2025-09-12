/**
 * Progressive Error Handler
 * 
 * Implements a 3-stage error handling approach:
 * 1. TRY - Initial attempt with basic error handling
 * 2. RETRY - Smart retry with escalating strategies
 * 3. ESCALATE - Advanced recovery with user guidance
 */

import SmartErrorRecoveryEngine, { 
  SmartErrorType, 
  RecoveryStrategy, 
  RecoveryPriority,
  ErrorContext 
} from './smartErrorRecovery';

export enum ErrorStage {
  TRY = 'try',
  RETRY = 'retry',
  ESCALATE = 'escalate'
}

export enum EscalationLevel {
  AUTO_RETRY = 'auto_retry',
  GUIDED_RETRY = 'guided_retry',
  ALTERNATIVE_APPROACH = 'alternative_approach',
  USER_INTERVENTION = 'user_intervention',
  SUPPORT_CONTACT = 'support_contact'
}

export interface ProgressiveConfig {
  maxRetries: number;
  retryDelayMs: number;
  exponentialBackoff: boolean;
  enableUserGuidance: boolean;
  enableAlternatives: boolean;
  enableSupportEscalation: boolean;
  component: string;
}

export interface AttemptResult<T> {
  success: boolean;
  data?: T;
  error?: Error;
  stage: ErrorStage;
  escalationLevel?: EscalationLevel;
  guidance?: string[];
  alternatives?: Array<{
    label: string;
    description: string;
    action: () => Promise<T>;
  }>;
}

export interface ProgressiveErrorState {
  currentStage: ErrorStage;
  attemptCount: number;
  totalAttempts: number;
  errors: Error[];
  lastAttempt: Date;
  escalationHistory: EscalationLevel[];
  userInteractionRequired: boolean;
  alternativesAvailable: boolean;
}

class ProgressiveErrorHandler<T> {
  private config: ProgressiveConfig;
  private recoveryEngine: SmartErrorRecoveryEngine;
  private state: ProgressiveErrorState;
  private operation: () => Promise<T>;
  private context: ErrorContext;

  constructor(
    operation: () => Promise<T>,
    context: ErrorContext,
    config: Partial<ProgressiveConfig> = {}
  ) {
    this.operation = operation;
    this.context = context;
    this.recoveryEngine = new SmartErrorRecoveryEngine();
    
    this.config = {
      maxRetries: 3,
      retryDelayMs: 1000,
      exponentialBackoff: true,
      enableUserGuidance: true,
      enableAlternatives: true,
      enableSupportEscalation: true,
      component: 'unknown',
      ...config
    };

    this.state = {
      currentStage: ErrorStage.TRY,
      attemptCount: 0,
      totalAttempts: 0,
      errors: [],
      lastAttempt: new Date(),
      escalationHistory: [],
      userInteractionRequired: false,
      alternativesAvailable: false,
    };
  }

  /**
   * Execute the operation with progressive error handling
   */
  async execute(): Promise<AttemptResult<T>> {
    this.state.totalAttempts++;
    
    try {
      // Stage 1: TRY - Initial attempt
      if (this.state.currentStage === ErrorStage.TRY) {
        return await this.tryStage();
      }
      
      // Stage 2: RETRY - Smart retry with recovery
      if (this.state.currentStage === ErrorStage.RETRY) {
        return await this.retryStage();
      }
      
      // Stage 3: ESCALATE - Advanced recovery
      return await this.escalateStage();
      
    } catch (error) {
      return this.createFailureResult(error as Error);
    }
  }

  /**
   * Stage 1: TRY - Initial attempt with basic error handling
   */
  private async tryStage(): Promise<AttemptResult<T>> {
    try {
      const data = await this.operation();
      return this.createSuccessResult(data, ErrorStage.TRY);
    } catch (error) {
      const err = error as Error;
      this.state.errors.push(err);
      this.state.attemptCount++;
      
      // Classify error and determine if retry is worthwhile
      const errorType = this.recoveryEngine.classifyError(err, this.context);
      const shouldRetry = this.shouldRetryError(errorType);
      
      if (shouldRetry && this.state.attemptCount < this.config.maxRetries) {
        this.state.currentStage = ErrorStage.RETRY;
        return this.createRetryResult(err, EscalationLevel.AUTO_RETRY);
      } else {
        this.state.currentStage = ErrorStage.ESCALATE;
        return this.createEscalationResult(err);
      }
    }
  }

  /**
   * Stage 2: RETRY - Smart retry with recovery strategies
   */
  private async retryStage(): Promise<AttemptResult<T>> {
    const lastError = this.state.errors[this.state.errors.length - 1];
    const errorType = this.recoveryEngine.classifyError(lastError, this.context);
    
    // Apply retry-specific recovery strategies
    await this.applyRetryStrategy(errorType);
    
    try {
      const data = await this.operation();
      return this.createSuccessResult(data, ErrorStage.RETRY);
    } catch (error) {
      const err = error as Error;
      this.state.errors.push(err);
      this.state.attemptCount++;
      
      // Check if we should continue retrying or escalate
      if (this.state.attemptCount < this.config.maxRetries) {
        // Try a different retry strategy
        const escalationLevel = this.determineNextRetryLevel();
        return this.createRetryResult(err, escalationLevel);
      } else {
        this.state.currentStage = ErrorStage.ESCALATE;
        return this.createEscalationResult(err);
      }
    }
  }

  /**
   * Stage 3: ESCALATE - Advanced recovery with user guidance
   */
  private async escalateStage(): Promise<AttemptResult<T>> {
    const lastError = this.state.errors[this.state.errors.length - 1];
    const recoveryPlan = this.recoveryEngine.generateRecoveryPlan(lastError, this.context);
    
    // Determine escalation approach
    const escalationLevel = this.determineEscalationLevel(recoveryPlan);
    this.state.escalationHistory.push(escalationLevel);
    
    switch (escalationLevel) {
      case EscalationLevel.GUIDED_RETRY:
        return await this.guidedRetryEscalation(lastError);
      
      case EscalationLevel.ALTERNATIVE_APPROACH:
        return await this.alternativeApproachEscalation(lastError);
      
      case EscalationLevel.USER_INTERVENTION:
        return await this.userInterventionEscalation(lastError);
      
      case EscalationLevel.SUPPORT_CONTACT:
        return await this.supportContactEscalation(lastError);
      
      default:
        return this.createFailureResult(lastError);
    }
  }

  /**
   * Apply retry-specific strategies based on error type
   */
  private async applyRetryStrategy(errorType: SmartErrorType): Promise<void> {
    const delay = this.calculateRetryDelay();
    
    switch (errorType) {
      case SmartErrorType.NETWORK_CONNECTION:
        // Wait for network recovery
        await this.waitForNetworkRecovery();
        break;
        
      case SmartErrorType.API_RATE_LIMITED:
        // Wait longer for rate limit reset
        await this.delay(delay * 2);
        break;
        
      case SmartErrorType.API_SERVER_ERROR:
        // Progressive delay for server issues
        await this.delay(delay);
        break;
        
      case SmartErrorType.API_UNAUTHORIZED:
        // Attempt to refresh auth token
        await this.attemptAuthRefresh();
        break;
        
      default:
        await this.delay(delay);
        break;
    }
  }

  /**
   * Guided retry with user feedback
   */
  private async guidedRetryEscalation(error: Error): Promise<AttemptResult<T>> {
    const guidance = this.generateRetryGuidance(error);
    
    return {
      success: false,
      error,
      stage: ErrorStage.ESCALATE,
      escalationLevel: EscalationLevel.GUIDED_RETRY,
      guidance,
    };
  }

  /**
   * Offer alternative approaches to achieve the same goal
   */
  private async alternativeApproachEscalation(error: Error): Promise<AttemptResult<T>> {
    const alternatives = await this.generateAlternatives(error);
    
    this.state.alternativesAvailable = alternatives.length > 0;
    
    return {
      success: false,
      error,
      stage: ErrorStage.ESCALATE,
      escalationLevel: EscalationLevel.ALTERNATIVE_APPROACH,
      guidance: [
        "The standard approach failed. Here are some alternatives:",
        ...alternatives.map(alt => `• ${alt.description}`)
      ],
      alternatives,
    };
  }

  /**
   * Require user intervention with clear instructions
   */
  private async userInterventionEscalation(error: Error): Promise<AttemptResult<T>> {
    this.state.userInteractionRequired = true;
    
    const guidance = this.generateUserInterventionGuidance(error);
    
    return {
      success: false,
      error,
      stage: ErrorStage.ESCALATE,
      escalationLevel: EscalationLevel.USER_INTERVENTION,
      guidance,
    };
  }

  /**
   * Escalate to support with detailed context
   */
  private async supportContactEscalation(error: Error): Promise<AttemptResult<T>> {
    const errorReport = this.generateErrorReport();
    
    return {
      success: false,
      error,
      stage: ErrorStage.ESCALATE,
      escalationLevel: EscalationLevel.SUPPORT_CONTACT,
      guidance: [
        "This issue requires technical support assistance.",
        "All error details have been collected automatically.",
        "Please contact support with the error reference provided.",
        `Error Reference: ${errorReport.referenceId}`,
      ],
    };
  }

  /**
   * Helper methods
   */
  private shouldRetryError(errorType: SmartErrorType): boolean {
    const retryableErrors = [
      SmartErrorType.NETWORK_CONNECTION,
      SmartErrorType.NETWORK_TIMEOUT,
      SmartErrorType.API_SERVER_ERROR,
      SmartErrorType.API_RATE_LIMITED,
      SmartErrorType.WEBSOCKET_CONNECTION,
    ];
    
    return retryableErrors.includes(errorType);
  }

  private calculateRetryDelay(): number {
    const baseDelay = this.config.retryDelayMs;
    
    if (this.config.exponentialBackoff) {
      return Math.min(
        baseDelay * Math.pow(2, this.state.attemptCount - 1),
        30000 // Cap at 30 seconds
      );
    }
    
    return baseDelay;
  }

  private determineNextRetryLevel(): EscalationLevel {
    const attempt = this.state.attemptCount;
    
    if (attempt === 1) return EscalationLevel.AUTO_RETRY;
    if (attempt === 2) return EscalationLevel.GUIDED_RETRY;
    return EscalationLevel.ALTERNATIVE_APPROACH;
  }

  private determineEscalationLevel(recoveryPlan: any): EscalationLevel {
    if (recoveryPlan.priority === RecoveryPriority.CRITICAL) {
      return EscalationLevel.SUPPORT_CONTACT;
    }
    
    if (this.config.enableAlternatives && this.hasAlternatives()) {
      return EscalationLevel.ALTERNATIVE_APPROACH;
    }
    
    if (this.config.enableUserGuidance) {
      return EscalationLevel.USER_INTERVENTION;
    }
    
    return EscalationLevel.SUPPORT_CONTACT;
  }

  private generateRetryGuidance(error: Error): string[] {
    const errorType = this.recoveryEngine.classifyError(error, this.context);
    
    switch (errorType) {
      case SmartErrorType.NETWORK_CONNECTION:
        return [
          "Network connection issue detected",
          "Please check your internet connection",
          "Try switching between WiFi and mobile data",
          "Click retry when your connection is stable"
        ];
        
      case SmartErrorType.API_UNAUTHORIZED:
        return [
          "Your session may have expired",
          "Please sign in again to continue",
          "Any unsaved work will be preserved",
          "Click retry after signing in"
        ];
        
      case SmartErrorType.API_SERVER_ERROR:
        return [
          "The server is experiencing issues",
          "This is usually temporary",
          "Wait a moment before retrying",
          "If the problem persists, try the alternative options below"
        ];
        
      default:
        return [
          "An unexpected error occurred",
          "This might be a temporary issue",
          "Try the operation again",
          "If the problem continues, contact support"
        ];
    }
  }

  private async generateAlternatives(error: Error): Promise<Array<{
    label: string;
    description: string;
    action: () => Promise<T>;
  }>> {
    const alternatives: Array<{
      label: string;
      description: string;
      action: () => Promise<T>;
    }> = [];

    // Context-specific alternatives based on component and operation
    if (this.context.component === 'api-client') {
      alternatives.push({
        label: 'Use Cached Data',
        description: 'Continue with previously cached data',
        action: async () => {
          return await this.useCachedData();
        }
      });

      if (this.context.operation?.includes('upload')) {
        alternatives.push({
          label: 'Save for Later',
          description: 'Save the data locally and sync when available',
          action: async () => {
            return await this.saveForLaterSync();
          }
        });
      }
    }

    if (this.context.component === 'form') {
      alternatives.push({
        label: 'Save Draft',
        description: 'Save your work as a draft to continue later',
        action: async () => {
          return await this.saveDraft();
        }
      });
    }

    return alternatives;
  }

  private generateUserInterventionGuidance(error: Error): string[] {
    return [
      "Manual action is required to resolve this issue",
      "Please follow the steps below carefully:",
      "1. Review the error details",
      "2. Check the suggested solutions",
      "3. Try the recommended actions",
      "4. Contact support if the issue persists"
    ];
  }

  private generateErrorReport(): { referenceId: string; details: any } {
    const referenceId = `ERR-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    return {
      referenceId,
      details: {
        component: this.config.component,
        context: this.context,
        errors: this.state.errors.map(e => ({
          message: e.message,
          stack: e.stack,
          timestamp: new Date().toISOString()
        })),
        attempts: this.state.totalAttempts,
        escalationHistory: this.state.escalationHistory,
        userAgent: navigator.userAgent,
        url: window.location.href,
      }
    };
  }

  private hasAlternatives(): boolean {
    // Determine if alternatives are available based on context
    return this.context.component === 'api-client' || 
           this.context.component === 'form' ||
           this.context.operation?.includes('upload');
  }

  // Result factory methods
  private createSuccessResult(data: T, stage: ErrorStage): AttemptResult<T> {
    return {
      success: true,
      data,
      stage,
    };
  }

  private createRetryResult(error: Error, escalationLevel: EscalationLevel): AttemptResult<T> {
    return {
      success: false,
      error,
      stage: ErrorStage.RETRY,
      escalationLevel,
      guidance: this.generateRetryGuidance(error),
    };
  }

  private createEscalationResult(error: Error): AttemptResult<T> {
    return {
      success: false,
      error,
      stage: ErrorStage.ESCALATE,
    };
  }

  private createFailureResult(error: Error): AttemptResult<T> {
    return {
      success: false,
      error,
      stage: this.state.currentStage,
      guidance: ["All recovery attempts have been exhausted"],
    };
  }

  // Utility methods
  private async delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private async waitForNetworkRecovery(): Promise<void> {
    return new Promise((resolve) => {
      if (navigator.onLine) {
        resolve();
        return;
      }

      const handleOnline = () => {
        window.removeEventListener('online', handleOnline);
        resolve();
      };

      window.addEventListener('online', handleOnline);
    });
  }

  private async attemptAuthRefresh(): Promise<void> {
    // Implementation would attempt to refresh authentication
    try {
      // Placeholder for auth refresh logic
      await fetch('/auth/refresh', { method: 'POST' });
    } catch {
      // Ignore refresh failures - will be handled by retry logic
    }
  }

  private async useCachedData(): Promise<T> {
    // Implementation would return cached data
    throw new Error('No cached data available');
  }

  private async saveForLaterSync(): Promise<T> {
    // Implementation would save data for later synchronization
    throw new Error('Save for later not implemented');
  }

  private async saveDraft(): Promise<T> {
    // Implementation would save form data as draft
    throw new Error('Draft saving not implemented');
  }

  /**
   * Get current error state
   */
  getState(): ProgressiveErrorState {
    return { ...this.state };
  }

  /**
   * Reset error state for new operation
   */
  reset(): void {
    this.state = {
      currentStage: ErrorStage.TRY,
      attemptCount: 0,
      totalAttempts: 0,
      errors: [],
      lastAttempt: new Date(),
      escalationHistory: [],
      userInteractionRequired: false,
      alternativesAvailable: false,
    };
  }
}

/**
 * Factory function for creating progressive error handlers
 */
export function createProgressiveHandler<T>(
  operation: () => Promise<T>,
  context: ErrorContext,
  config?: Partial<ProgressiveConfig>
): ProgressiveErrorHandler<T> {
  return new ProgressiveErrorHandler(operation, context, config);
}

/**
 * Utility function for simple progressive execution
 */
export async function executeWithProgression<T>(
  operation: () => Promise<T>,
  component: string,
  operationName?: string
): Promise<AttemptResult<T>> {
  const context: ErrorContext = {
    component,
    operation: operationName || 'unknown',
    timestamp: Date.now(),
    url: window.location.href,
    userAgent: navigator.userAgent,
    retryCount: 0,
    networkStatus: navigator.onLine ? 'online' : 'offline',
  };

  const handler = createProgressiveHandler(operation, context);
  return await handler.execute();
}

export { ProgressiveErrorHandler };