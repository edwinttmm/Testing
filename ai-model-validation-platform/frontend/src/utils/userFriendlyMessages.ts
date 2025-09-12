/**
 * User-Friendly Error Messages System
 * 
 * Transforms technical errors into clear, actionable user messages
 * with context-aware guidance and recovery suggestions.
 */

import { SmartErrorType } from './smartErrorRecovery';

export interface UserMessage {
  title: string;
  message: string;
  severity: 'error' | 'warning' | 'info' | 'success';
  actionable: boolean;
  category: MessageCategory;
  context?: string;
  suggestions?: string[];
  nextSteps?: string[];
  learnMoreUrl?: string;
  estimatedFixTime?: string;
}

export enum MessageCategory {
  CONNECTION = 'connection',
  AUTHENTICATION = 'authentication',
  PERMISSIONS = 'permissions',
  DATA = 'data',
  SYSTEM = 'system',
  USER_INPUT = 'user_input',
  RESOURCES = 'resources',
  TEMPORARY = 'temporary'
}

class UserFriendlyMessenger {
  private contextTemplates: Map<string, MessageTemplate> = new Map();
  private fallbackMessages: Map<SmartErrorType, UserMessage> = new Map();

  constructor() {
    this.initializeMessageTemplates();
    this.initializeFallbackMessages();
  }

  /**
   * Convert technical error to user-friendly message
   */
  public createUserMessage(
    error: any,
    errorType: SmartErrorType,
    context?: {
      component: string;
      operation: string;
      userAction?: string;
      retryCount?: number;
    }
  ): UserMessage {
    // Try context-specific message first
    if (context) {
      const contextKey = `${context.component}-${context.operation}`;
      const template = this.contextTemplates.get(contextKey);
      if (template) {
        return this.applyTemplate(template, error, context);
      }
    }

    // Use error type specific message
    const typeMessage = this.getMessageByErrorType(errorType, error, context);
    if (typeMessage) {
      return typeMessage;
    }

    // Fallback to generic message
    return this.getFallbackMessage(error);
  }

  private initializeMessageTemplates() {
    // API Connection Messages
    this.contextTemplates.set('api-client-fetch', {
      title: 'Connection Issue',
      message: 'We\'re having trouble connecting to our servers.',
      severity: 'warning',
      category: MessageCategory.CONNECTION,
      suggestions: [
        'Check your internet connection',
        'Try refreshing the page',
        'Switch to a different network if available'
      ],
      nextSteps: [
        'We\'ll automatically retry the connection',
        'You can continue working offline if needed',
        'Your data will sync when connection is restored'
      ],
      estimatedFixTime: '1-2 minutes'
    });

    // Form Submission Messages
    this.contextTemplates.set('form-submit', {
      title: 'Submission Failed',
      message: 'There was a problem submitting your form.',
      severity: 'error',
      category: MessageCategory.DATA,
      suggestions: [
        'Please review the highlighted fields',
        'Make sure all required information is provided',
        'Check that your data is in the correct format'
      ],
      nextSteps: [
        'Fix any validation errors shown',
        'Click submit again when ready',
        'Your progress has been automatically saved'
      ]
    });

    // File Upload Messages
    this.contextTemplates.set('upload-file', {
      title: 'Upload Problem',
      message: 'We couldn\'t upload your file.',
      severity: 'warning',
      category: MessageCategory.DATA,
      suggestions: [
        'Check that the file isn\'t too large (max 50MB)',
        'Make sure the file type is supported',
        'Try uploading a different file to test'
      ],
      nextSteps: [
        'You can try uploading again',
        'Consider compressing large files',
        'Contact support if the problem persists'
      ],
      estimatedFixTime: 'Usually resolves immediately'
    });

    // Authentication Messages
    this.contextTemplates.set('auth-login', {
      title: 'Sign In Required',
      message: 'Please sign in to continue.',
      severity: 'info',
      category: MessageCategory.AUTHENTICATION,
      suggestions: [
        'Your session may have expired for security',
        'Click "Sign In" to authenticate again',
        'Enable "Keep me signed in" for longer sessions'
      ],
      nextSteps: [
        'Sign in with your credentials',
        'You\'ll return to where you left off',
        'Your work will be automatically saved'
      ]
    });

    // Video Player Messages
    this.contextTemplates.set('video-player-load', {
      title: 'Video Loading Issue',
      message: 'The video couldn\'t be loaded.',
      severity: 'warning',
      category: MessageCategory.RESOURCES,
      suggestions: [
        'The video file might be corrupted or missing',
        'Your internet connection might be too slow',
        'Try refreshing the page'
      ],
      nextSteps: [
        'We\'ll try to load a different quality version',
        'Check if other videos work normally',
        'Report this video if the problem persists'
      ],
      estimatedFixTime: '30 seconds'
    });

    // Data Loading Messages
    this.contextTemplates.set('data-fetch', {
      title: 'Loading Problem',
      message: 'We\'re having trouble loading your data.',
      severity: 'warning',
      category: MessageCategory.DATA,
      suggestions: [
        'This might be due to a slow connection',
        'The server might be experiencing high load',
        'Try refreshing to reload the data'
      ],
      nextSteps: [
        'We\'ll keep trying to load your data',
        'You can use cached data in the meantime',
        'Contact support if this continues'
      ]
    });
  }

  private initializeFallbackMessages() {
    this.fallbackMessages.set(SmartErrorType.NETWORK_CONNECTION, {
      title: 'No Internet Connection',
      message: 'It looks like you\'re offline. Some features may not work until you reconnect.',
      severity: 'warning',
      actionable: true,
      category: MessageCategory.CONNECTION,
      suggestions: [
        'Check your WiFi or cellular connection',
        'Try moving to an area with better signal',
        'Some features will work offline'
      ],
      nextSteps: [
        'We\'ll automatically reconnect when possible',
        'Your changes will be saved locally',
        'Everything will sync when you\'re back online'
      ],
      estimatedFixTime: 'When connection is restored'
    });

    this.fallbackMessages.set(SmartErrorType.NETWORK_TIMEOUT, {
      title: 'Slow Connection',
      message: 'The request is taking longer than usual due to a slow connection.',
      severity: 'info',
      actionable: true,
      category: MessageCategory.CONNECTION,
      suggestions: [
        'Your internet connection might be slow',
        'The service might be busy right now',
        'We\'ll keep trying automatically'
      ],
      nextSteps: [
        'Wait a moment for the request to complete',
        'You can try again if it doesn\'t work',
        'Consider using a faster connection'
      ],
      estimatedFixTime: '1-2 minutes'
    });

    this.fallbackMessages.set(SmartErrorType.API_UNAUTHORIZED, {
      title: 'Sign In Again',
      message: 'Your session has expired. Please sign in again to continue.',
      severity: 'info',
      actionable: true,
      category: MessageCategory.AUTHENTICATION,
      suggestions: [
        'This happens automatically for security',
        'Your work has been saved',
        'Sign in to pick up where you left off'
      ],
      nextSteps: [
        'Click the sign in button',
        'Enter your credentials',
        'You\'ll return to your previous page'
      ]
    });

    this.fallbackMessages.set(SmartErrorType.API_FORBIDDEN, {
      title: 'Access Denied',
      message: 'You don\'t have permission to perform this action.',
      severity: 'warning',
      actionable: false,
      category: MessageCategory.PERMISSIONS,
      suggestions: [
        'This action requires special permissions',
        'Contact your administrator for access',
        'Try a different approach to achieve your goal'
      ],
      nextSteps: [
        'Request the necessary permissions',
        'Use alternative features that you have access to',
        'Contact support if you think this is a mistake'
      ]
    });

    this.fallbackMessages.set(SmartErrorType.API_NOT_FOUND, {
      title: 'Content Not Found',
      message: 'The item you\'re looking for couldn\'t be found.',
      severity: 'warning',
      actionable: true,
      category: MessageCategory.DATA,
      suggestions: [
        'The item might have been moved or deleted',
        'Check that you have the correct link',
        'Try searching for similar content'
      ],
      nextSteps: [
        'Go back and try again',
        'Use the search feature to find what you need',
        'Contact support if this content should exist'
      ]
    });

    this.fallbackMessages.set(SmartErrorType.API_SERVER_ERROR, {
      title: 'Service Temporarily Down',
      message: 'Our servers are experiencing issues. We\'re working to fix this quickly.',
      severity: 'error',
      actionable: true,
      category: MessageCategory.SYSTEM,
      suggestions: [
        'This is usually temporary',
        'Our team has been automatically notified',
        'Try again in a few minutes'
      ],
      nextSteps: [
        'We\'ll keep trying automatically',
        'You can use offline features in the meantime',
        'Check our status page for updates'
      ],
      estimatedFixTime: '5-15 minutes',
      learnMoreUrl: '/status'
    });

    this.fallbackMessages.set(SmartErrorType.API_RATE_LIMITED, {
      title: 'Slow Down a Bit',
      message: 'You\'re working too fast! Please wait a moment before trying again.',
      severity: 'info',
      actionable: true,
      category: MessageCategory.TEMPORARY,
      suggestions: [
        'This prevents system overload',
        'Wait a moment and try again',
        'Consider batching similar operations'
      ],
      nextSteps: [
        'We\'ll automatically retry in a moment',
        'Take a short break',
        'Your request will be processed soon'
      ],
      estimatedFixTime: '30-60 seconds'
    });

    this.fallbackMessages.set(SmartErrorType.WEBSOCKET_CONNECTION, {
      title: 'Real-time Updates Paused',
      message: 'Live updates have been temporarily paused. We\'re reconnecting now.',
      severity: 'info',
      actionable: false,
      category: MessageCategory.CONNECTION,
      suggestions: [
        'Real-time features will be restored shortly',
        'You can still use the app normally',
        'Refresh the page if this continues'
      ],
      nextSteps: [
        'We\'re automatically reconnecting',
        'Live updates will resume soon',
        'You can continue working normally'
      ],
      estimatedFixTime: '10-30 seconds'
    });

    this.fallbackMessages.set(SmartErrorType.COMPONENT_RENDER, {
      title: 'Display Issue',
      message: 'Some content isn\'t displaying properly. Other features still work normally.',
      severity: 'warning',
      actionable: true,
      category: MessageCategory.SYSTEM,
      suggestions: [
        'This affects only this section',
        'Try refreshing the page',
        'Other features continue to work'
      ],
      nextSteps: [
        'Refresh the page to fix display issues',
        'Use other parts of the app normally',
        'Report this if it keeps happening'
      ]
    });

    this.fallbackMessages.set(SmartErrorType.CHUNK_LOADING, {
      title: 'Update Required',
      message: 'The app was updated while you were using it. Please refresh to get the latest version.',
      severity: 'info',
      actionable: true,
      category: MessageCategory.SYSTEM,
      suggestions: [
        'The app has new features and improvements',
        'Refreshing will get you the latest version',
        'Your work will be automatically saved'
      ],
      nextSteps: [
        'Click refresh to update',
        'Your data will be preserved',
        'You\'ll get the newest features'
      ]
    });

    this.fallbackMessages.set(SmartErrorType.VALIDATION_ERROR, {
      title: 'Please Check Your Input',
      message: 'Some information needs to be corrected before we can continue.',
      severity: 'warning',
      actionable: true,
      category: MessageCategory.USER_INPUT,
      suggestions: [
        'Look for highlighted fields with issues',
        'Follow the hints next to each field',
        'Make sure required fields are filled in'
      ],
      nextSteps: [
        'Fix the highlighted issues',
        'Use the examples provided as guides',
        'Submit again when everything looks good'
      ]
    });
  }

  private getMessageByErrorType(
    errorType: SmartErrorType,
    error: any,
    context?: any
  ): UserMessage | null {
    const baseMessage = this.fallbackMessages.get(errorType);
    if (!baseMessage) return null;

    // Enhance message with context
    return {
      ...baseMessage,
      context: context ? `${context.component} - ${context.operation}` : (baseMessage.context || ''),
    };
  }

  private applyTemplate(
    template: MessageTemplate,
    error: any,
    context: any
  ): UserMessage {
    // Apply dynamic content based on error and context
    let message = template.message;
    let title = template.title;

    // Context-specific customizations
    if (context.retryCount && context.retryCount > 0) {
      message += ` (Attempt ${context.retryCount + 1})`;
    }

    if (context.userAction) {
      title = `${title} - ${context.userAction}`;
    }

    return {
      title,
      message,
      severity: template.severity,
      actionable: true,
      category: template.category,
      context: `${context.component} - ${context.operation}`,
      ...(template.suggestions && { suggestions: template.suggestions }),
      ...(template.nextSteps && { nextSteps: template.nextSteps }),
      ...(template.learnMoreUrl && { learnMoreUrl: template.learnMoreUrl }),
      ...(template.estimatedFixTime && { estimatedFixTime: template.estimatedFixTime }),
    };
  }

  private getFallbackMessage(error: any): UserMessage {
    return {
      title: 'Something Went Wrong',
      message: 'We encountered an unexpected issue, but we\'re working to resolve it.',
      severity: 'error',
      actionable: true,
      category: MessageCategory.SYSTEM,
      suggestions: [
        'This is an uncommon error',
        'Try refreshing the page',
        'The issue has been automatically reported'
      ],
      nextSteps: [
        'Wait a moment and try again',
        'Refresh the page if needed',
        'Contact support if this continues'
      ]
    };
  }

  /**
   * Get message variations based on user experience level
   */
  public getMessageForAudience(
    baseMessage: UserMessage,
    audience: 'beginner' | 'intermediate' | 'advanced'
  ): UserMessage {
    switch (audience) {
      case 'beginner':
        return {
          ...baseMessage,
          message: this.simplifyLanguage(baseMessage.message),
          ...(baseMessage.suggestions && { suggestions: baseMessage.suggestions.map(s => this.simplifyLanguage(s)) }),
          ...(baseMessage.nextSteps && { nextSteps: baseMessage.nextSteps.map(s => this.addMoreDetail(s)) }),
        };
      
      case 'advanced':
        return {
          ...baseMessage,
          suggestions: [
            ...(baseMessage.suggestions || []),
            'Check browser console for technical details',
            'Verify network requests in developer tools'
          ]
        };
      
      default:
        return baseMessage;
    }
  }

  private simplifyLanguage(text: string): string {
    return text
      .replace(/server/gi, 'system')
      .replace(/connection/gi, 'internet')
      .replace(/authentication/gi, 'sign in')
      .replace(/validation/gi, 'checking');
  }

  private addMoreDetail(text: string): string {
    if (text.includes('try again')) {
      return `${text} - this usually works on the second attempt`;
    }
    if (text.includes('refresh')) {
      return `${text} - use Ctrl+R (Windows) or Cmd+R (Mac)`;
    }
    return text;
  }

  /**
   * Generate contextual help text
   */
  public generateHelpText(message: UserMessage): string[] {
    const helpTexts: string[] = [];

    switch (message.category) {
      case MessageCategory.CONNECTION:
        helpTexts.push(
          'Internet connection issues are usually temporary.',
          'The app will automatically reconnect when your internet is back.',
          'Some features work offline - look for the offline indicator.'
        );
        break;

      case MessageCategory.AUTHENTICATION:
        helpTexts.push(
          'Sessions expire for security reasons.',
          'Signing in again is quick and keeps your data safe.',
          'Enable "Remember me" for longer sessions.'
        );
        break;

      case MessageCategory.PERMISSIONS:
        helpTexts.push(
          'Different users have different access levels.',
          'Contact your administrator to request additional permissions.',
          'Some features may be restricted based on your role.'
        );
        break;

      case MessageCategory.USER_INPUT:
        helpTexts.push(
          'Input validation helps ensure data quality.',
          'Look for red highlights to see what needs fixing.',
          'Hover over field labels for formatting hints.'
        );
        break;

      default:
        helpTexts.push(
          'Most errors are temporary and resolve quickly.',
          'The system automatically reports issues for investigation.',
          'Your data is safe even when errors occur.'
        );
    }

    return helpTexts;
  }
}

interface MessageTemplate {
  title: string;
  message: string;
  severity: 'error' | 'warning' | 'info' | 'success';
  category: MessageCategory;
  suggestions?: string[];
  nextSteps?: string[];
  learnMoreUrl?: string;
  estimatedFixTime?: string;
}

// Singleton instance
const userFriendlyMessenger = new UserFriendlyMessenger();

// Export functions for easy use
export const createUserMessage = (
  error: any,
  errorType: SmartErrorType,
  context?: {
    component: string;
    operation: string;
    userAction?: string;
    retryCount?: number;
  }
): UserMessage => {
  return userFriendlyMessenger.createUserMessage(error, errorType, context);
};

export const getMessageForAudience = (
  baseMessage: UserMessage,
  audience: 'beginner' | 'intermediate' | 'advanced'
): UserMessage => {
  return userFriendlyMessenger.getMessageForAudience(baseMessage, audience);
};

export const generateHelpText = (message: UserMessage): string[] => {
  return userFriendlyMessenger.generateHelpText(message);
};

export default userFriendlyMessenger;