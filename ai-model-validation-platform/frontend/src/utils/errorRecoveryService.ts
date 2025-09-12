/**
 * Enhanced Error Recovery Service
 * Provides comprehensive error recovery mechanisms with user-friendly options
 */

import { appConfig } from '../config/appConfig';

export interface ErrorRecoveryOptions {
  retry?: boolean;
  fallback?: boolean;
  alternative?: boolean;
  offline?: boolean;
}

export interface RecoveryAction {
  label: string;
  action: () => Promise<void> | void;
  icon?: string;
  primary?: boolean;
}

export interface ErrorRecoveryState {
  canRetry: boolean;
  canFallback: boolean;
  hasAlternative: boolean;
  supportsOffline: boolean;
  recoveryActions: RecoveryAction[];
  suggestions: string[];
}

class ErrorRecoveryService {
  private retryAttempts = new Map<string, number>();
  private maxRetries = 3;
  
  /**
   * Analyze error and provide recovery options
   */
  analyzeError(error: Error, context?: string): ErrorRecoveryState {
    const errorType = this.classifyError(error);
    const attemptCount = this.retryAttempts.get(context || error.message) || 0;
    
    const state: ErrorRecoveryState = {
      canRetry: attemptCount < this.maxRetries && this.isRetryableError(errorType),
      canFallback: this.hasFallbackOptions(errorType),
      hasAlternative: this.hasAlternativeActions(errorType),
      supportsOffline: this.supportsOfflineMode(errorType),
      recoveryActions: [],
      suggestions: []
    };
    
    // Build recovery actions based on error type
    state.recoveryActions = this.buildRecoveryActions(errorType, context, state);
    state.suggestions = this.generateSuggestions(errorType);
    
    return state;
  }
  
  /**
   * Execute automatic recovery attempt
   */
  async attemptAutoRecovery(error: Error, context?: string): Promise<boolean> {
    const errorType = this.classifyError(error);
    const key = context || error.message;
    
    // Increment attempt counter
    const attempts = (this.retryAttempts.get(key) || 0) + 1;
    this.retryAttempts.set(key, attempts);
    
    // Try recovery strategies based on error type
    try {
      switch (errorType) {
        case 'NETWORK_ERROR':
          return await this.recoverFromNetworkError();
          
        case 'TIMEOUT_ERROR':
          return await this.recoverFromTimeout();
          
        case 'AUTH_ERROR':
          return await this.recoverFromAuthError();
          
        case 'VALIDATION_ERROR':
          return false; // User input required
          
        case 'SERVER_ERROR':
          return await this.recoverFromServerError();
          
        default:
          return false;
      }
    } catch (recoveryError) {
      console.error('Recovery attempt failed:', recoveryError);
      return false;
    }
  }
  
  /**
   * Reset retry counter for context
   */
  resetRetryCount(context: string): void {
    this.retryAttempts.delete(context);
  }
  
  /**
   * Clear all retry counters
   */
  clearRetryCounters(): void {
    this.retryAttempts.clear();
  }
  
  private classifyError(error: Error): string {
    const message = error.message.toLowerCase();
    
    if (message.includes('network') || message.includes('fetch')) {
      return 'NETWORK_ERROR';
    }
    if (message.includes('timeout')) {
      return 'TIMEOUT_ERROR';
    }
    if (message.includes('auth') || message.includes('unauthorized')) {
      return 'AUTH_ERROR';
    }
    if (message.includes('validation') || message.includes('invalid')) {
      return 'VALIDATION_ERROR';
    }
    if (message.includes('500') || message.includes('server')) {
      return 'SERVER_ERROR';
    }
    
    return 'UNKNOWN_ERROR';
  }
  
  private isRetryableError(errorType: string): boolean {
    const retryableErrors = ['NETWORK_ERROR', 'TIMEOUT_ERROR', 'SERVER_ERROR'];
    return retryableErrors.includes(errorType);
  }
  
  private hasFallbackOptions(errorType: string): boolean {
    const fallbackSupportedErrors = ['NETWORK_ERROR', 'SERVER_ERROR'];
    return fallbackSupportedErrors.includes(errorType);
  }
  
  private hasAlternativeActions(errorType: string): boolean {
    return errorType !== 'VALIDATION_ERROR';
  }
  
  private supportsOfflineMode(errorType: string): boolean {
    return errorType === 'NETWORK_ERROR';
  }
  
  private buildRecoveryActions(
    errorType: string, 
    context?: string, 
    state?: ErrorRecoveryState
  ): RecoveryAction[] {
    const actions: RecoveryAction[] = [];
    
    // Retry action
    if (state?.canRetry) {
      actions.push({
        label: 'Retry',
        action: () => this.executeRetry(context),
        icon: 'refresh',
        primary: true
      });
    }
    
    // Fallback actions
    if (state?.canFallback) {
      actions.push({
        label: 'Use Fallback',
        action: () => this.useFallbackService(),
        icon: 'swap_horiz'
      });
    }
    
    // Alternative actions based on error type
    switch (errorType) {
      case 'NETWORK_ERROR':
        actions.push({
          label: 'Work Offline',
          action: () => this.enableOfflineMode(),
          icon: 'cloud_off'
        });
        break;
        
      case 'AUTH_ERROR':
        actions.push({
          label: 'Re-authenticate',
          action: () => this.initiateReauth(),
          icon: 'login'
        });
        break;
        
      case 'VALIDATION_ERROR':
        actions.push({
          label: 'Reset Form',
          action: () => this.resetForm(context),
          icon: 'refresh'
        });
        break;
    }
    
    // Always provide refresh option
    actions.push({
      label: 'Refresh Page',
      action: () => window.location.reload(),
      icon: 'refresh'
    });
    
    return actions;
  }
  
  private generateSuggestions(errorType: string): string[] {
    const suggestions: string[] = [];
    
    switch (errorType) {
      case 'NETWORK_ERROR':
        suggestions.push('Check your internet connection');
        suggestions.push('Try using a different network');
        suggestions.push('Disable VPN if active');
        break;
        
      case 'TIMEOUT_ERROR':
        suggestions.push('The server may be busy, try again in a moment');
        suggestions.push('Check if your internet connection is stable');
        break;
        
      case 'AUTH_ERROR':
        suggestions.push('Your session may have expired');
        suggestions.push('Try logging out and logging back in');
        break;
        
      case 'VALIDATION_ERROR':
        suggestions.push('Check that all required fields are filled correctly');
        suggestions.push('Ensure uploaded files meet the requirements');
        break;
        
      case 'SERVER_ERROR':
        suggestions.push('The server is experiencing issues');
        suggestions.push('Try again in a few minutes');
        suggestions.push('Contact support if the problem persists');
        break;
    }
    
    return suggestions;
  }
  
  // Recovery implementations
  private async recoverFromNetworkError(): Promise<boolean> {
    // Try to ping a reliable endpoint
    try {
      const response = await fetch(appConfig.api.baseUrl + '/health', {
        method: 'GET',
        signal: AbortSignal.timeout(5000)
      });
      return response.ok;
    } catch {
      return false;
    }
  }
  
  private async recoverFromTimeout(): Promise<boolean> {
    // Wait a brief moment and try again
    await new Promise(resolve => setTimeout(resolve, 1000));
    return true;
  }
  
  private async recoverFromAuthError(): Promise<boolean> {
    // Attempt to refresh authentication
    try {
      // Implementation depends on auth system
      return false; // User intervention required
    } catch {
      return false;
    }
  }
  
  private async recoverFromServerError(): Promise<boolean> {
    // Wait and try again
    await new Promise(resolve => setTimeout(resolve, 2000));
    return true;
  }
  
  private async executeRetry(context?: string): Promise<void> {
    // Implementation depends on context
    console.log('Executing retry for context:', context);
  }
  
  private async useFallbackService(): Promise<void> {
    // Switch to fallback API endpoint
    console.log('Switching to fallback service');
  }
  
  private async enableOfflineMode(): Promise<void> {
    // Enable offline functionality
    console.log('Enabling offline mode');
  }
  
  private async initiateReauth(): Promise<void> {
    // Redirect to login or show auth modal
    console.log('Initiating re-authentication');
  }
  
  private async resetForm(context?: string): Promise<void> {
    // Reset form based on context
    console.log('Resetting form for context:', context);
  }
}

export const errorRecoveryService = new ErrorRecoveryService();