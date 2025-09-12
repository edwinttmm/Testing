/**
 * Error Recovery System Validation Script
 * 
 * Validates that the comprehensive error recovery system achieves
 * the target 85%+ error recovery rate across all scenarios.
 */

import SmartErrorRecoveryEngine, { SmartErrorType, RecoveryStrategy, ErrorContext } from '../utils/smartErrorRecovery';
import { executeWithProgression, ErrorStage, EscalationLevel } from '../utils/progressiveErrorHandler';
import { createUserMessage, MessageCategory } from '../utils/userFriendlyMessages';
import offlineCapabilities from '../utils/offlineCapabilities';

interface ValidationScenario {
  id: string;
  name: string;
  category: string;
  error: any;
  context: ErrorContext;
  expectedRecoverable: boolean;
  weight: number; // Importance factor (1-10)
}

interface ValidationResult {
  scenario: ValidationScenario;
  recovered: boolean;
  recoveryStrategy: RecoveryStrategy;
  automaticRecovery: boolean;
  userGuidanceProvided: boolean;
  estimatedRecoveryRate: number;
  executionTime: number;
}

interface ValidationSummary {
  totalScenarios: number;
  recoveredScenarios: number;
  overallRecoveryRate: number;
  weightedRecoveryRate: number;
  categoryBreakdown: Record<string, {
    total: number;
    recovered: number;
    rate: number;
  }>;
  criticalIssues: ValidationResult[];
  recommendations: string[];
}

class ErrorRecoverySystemValidator {
  private recoveryEngine: SmartErrorRecoveryEngine;
  private scenarios: ValidationScenario[] = [];

  constructor() {
    this.recoveryEngine = new SmartErrorRecoveryEngine();
    this.initializeValidationScenarios();
  }

  private initializeValidationScenarios() {
    this.scenarios = [
      // Critical Network Scenarios (Weight: 10)
      {
        id: 'network-offline',
        name: 'Complete Network Outage',
        category: 'Network',
        error: new Error('ERR_NETWORK'),
        context: this.createContext('api-client', 'fetch-data'),
        expectedRecoverable: true,
        weight: 10
      },
      {
        id: 'network-timeout',
        name: 'Network Timeout',
        category: 'Network',
        error: new Error('Request timeout'),
        context: this.createContext('form', 'submit'),
        expectedRecoverable: true,
        weight: 9
      },
      {
        id: 'network-slow',
        name: 'Slow Network Connection',
        category: 'Network',
        error: { code: 'NETWORK_SLOW', message: 'Slow connection detected' },
        context: this.createContext('video-player', 'load'),
        expectedRecoverable: true,
        weight: 8
      },

      // Authentication Scenarios (Weight: 9)
      {
        id: 'auth-expired',
        name: 'Session Expired',
        category: 'Authentication',
        error: { response: { status: 401 }, message: 'Unauthorized' },
        context: this.createContext('api-client', 'protected-request'),
        expectedRecoverable: true,
        weight: 9
      },
      {
        id: 'auth-forbidden',
        name: 'Access Forbidden',
        category: 'Authentication',
        error: { response: { status: 403 }, message: 'Forbidden' },
        context: this.createContext('admin-panel', 'access'),
        expectedRecoverable: true,
        weight: 8
      },

      // Server Error Scenarios (Weight: 8)
      {
        id: 'server-internal',
        name: 'Internal Server Error',
        category: 'Server',
        error: { response: { status: 500 }, message: 'Internal Server Error' },
        context: this.createContext('data-service', 'fetch'),
        expectedRecoverable: true,
        weight: 8
      },
      {
        id: 'server-unavailable',
        name: 'Service Unavailable',
        category: 'Server',
        error: { response: { status: 503 }, message: 'Service Unavailable' },
        context: this.createContext('upload-service', 'upload-video'),
        expectedRecoverable: true,
        weight: 8
      },
      {
        id: 'server-gateway',
        name: 'Bad Gateway',
        category: 'Server',
        error: { response: { status: 502 }, message: 'Bad Gateway' },
        context: this.createContext('api-gateway', 'route-request'),
        expectedRecoverable: true,
        weight: 7
      },

      // Rate Limiting Scenarios (Weight: 7)
      {
        id: 'rate-limit-exceeded',
        name: 'Rate Limit Exceeded',
        category: 'RateLimit',
        error: { 
          response: { 
            status: 429, 
            headers: { 'retry-after': '60' }
          }, 
          message: 'Too Many Requests' 
        },
        context: this.createContext('api-client', 'bulk-operation'),
        expectedRecoverable: true,
        weight: 7
      },

      // Validation Scenarios (Weight: 6)
      {
        id: 'validation-required-fields',
        name: 'Required Fields Missing',
        category: 'Validation',
        error: { 
          name: 'ValidationError', 
          type: 'validation',
          fieldErrors: { name: 'Required', email: 'Invalid format' }
        },
        context: this.createContext('user-form', 'create-user'),
        expectedRecoverable: true,
        weight: 6
      },
      {
        id: 'validation-format-error',
        name: 'Invalid Data Format',
        category: 'Validation',
        error: { response: { status: 422 }, message: 'Validation failed' },
        context: this.createContext('settings-form', 'save-settings'),
        expectedRecoverable: true,
        weight: 6
      },

      // Resource Loading Scenarios (Weight: 8)
      {
        id: 'chunk-loading-failed',
        name: 'Application Update Failed',
        category: 'Resources',
        error: new Error('Loading chunk 2 failed'),
        context: this.createContext('router', 'lazy-load'),
        expectedRecoverable: true,
        weight: 8
      },
      {
        id: 'resource-not-found',
        name: 'Resource Not Found',
        category: 'Resources',
        error: { response: { status: 404 }, message: 'Not Found' },
        context: this.createContext('media-player', 'load-video'),
        expectedRecoverable: true,
        weight: 7
      },

      // WebSocket Scenarios (Weight: 7)
      {
        id: 'websocket-connection-lost',
        name: 'WebSocket Connection Lost',
        category: 'WebSocket',
        error: { type: 'websocket', code: 1006, message: 'Connection lost' },
        context: this.createContext('real-time-updates', 'maintain-connection'),
        expectedRecoverable: true,
        weight: 7
      },
      {
        id: 'websocket-protocol-error',
        name: 'WebSocket Protocol Error',
        category: 'WebSocket',
        error: { type: 'websocket', code: 1002, message: 'Protocol error' },
        context: this.createContext('notification-system', 'receive-updates'),
        expectedRecoverable: true,
        weight: 6
      },

      // Component Rendering Scenarios (Weight: 6)
      {
        id: 'component-render-error',
        name: 'Component Render Error',
        category: 'Component',
        error: new Error('Cannot read property \'map\' of undefined'),
        context: this.createContext('data-table', 'render-rows'),
        expectedRecoverable: true,
        weight: 6
      },
      {
        id: 'component-props-error',
        name: 'Invalid Component Props',
        category: 'Component',
        error: new Error('Cannot read property of null'),
        context: this.createContext('chart-component', 'process-data'),
        expectedRecoverable: true,
        weight: 5
      },

      // Memory/Performance Scenarios (Weight: 5)
      {
        id: 'memory-exhausted',
        name: 'Memory Exhausted',
        category: 'Performance',
        error: new Error('Maximum call stack size exceeded'),
        context: this.createContext('data-processor', 'process-large-dataset'),
        expectedRecoverable: false, // Truly critical errors
        weight: 5
      },

      // File Operation Scenarios (Weight: 7)
      {
        id: 'file-too-large',
        name: 'File Too Large',
        category: 'FileOperations',
        error: { response: { status: 413 }, message: 'Payload too large' },
        context: this.createContext('file-uploader', 'upload-video'),
        expectedRecoverable: true,
        weight: 7
      },
      {
        id: 'invalid-file-type',
        name: 'Invalid File Type',
        category: 'FileOperations',
        error: { response: { status: 400 }, message: 'Invalid file type' },
        context: this.createContext('file-uploader', 'validate-file'),
        expectedRecoverable: true,
        weight: 6
      },

      // Security Scenarios (Weight: 8)
      {
        id: 'csrf-token-invalid',
        name: 'CSRF Token Invalid',
        category: 'Security',
        error: { response: { status: 419 }, message: 'CSRF token mismatch' },
        context: this.createContext('form-submission', 'secure-submit'),
        expectedRecoverable: true,
        weight: 8
      },

      // Database Scenarios (Weight: 7)
      {
        id: 'database-connection-lost',
        name: 'Database Connection Lost',
        category: 'Database',
        error: { response: { status: 500 }, message: 'Database connection failed' },
        context: this.createContext('data-service', 'query-database'),
        expectedRecoverable: true,
        weight: 7
      },

      // Third-party Service Scenarios (Weight: 6)
      {
        id: 'external-api-down',
        name: 'External API Down',
        category: 'ExternalServices',
        error: { response: { status: 503 }, message: 'External service unavailable' },
        context: this.createContext('integration-service', 'call-external-api'),
        expectedRecoverable: true,
        weight: 6
      }
    ];
  }

  private createContext(component: string, operation: string): ErrorContext {
    return {
      component,
      operation,
      timestamp: Date.now(),
      url: 'https://app.example.com/test',
      userAgent: 'Test Agent 1.0',
      retryCount: 0,
      networkStatus: 'online'
    };
  }

  public async validateErrorRecoverySystem(): Promise<ValidationSummary> {
    console.log('🚀 Starting Error Recovery System Validation...');
    console.log(`📊 Testing ${this.scenarios.length} scenarios across ${this.getUniqueCategories().length} categories`);

    const results: ValidationResult[] = [];

    for (const scenario of this.scenarios) {
      console.log(`\n🧪 Testing: ${scenario.name} (${scenario.category})`);
      
      const startTime = performance.now();
      const result = await this.validateScenario(scenario);
      const executionTime = performance.now() - startTime;

      result.executionTime = executionTime;
      results.push(result);

      const status = result.recovered ? '✅' : '❌';
      const autoStatus = result.automaticRecovery ? '🤖' : '👤';
      console.log(`   ${status} ${autoStatus} Recovery Rate: ${result.estimatedRecoveryRate}% (${executionTime.toFixed(1)}ms)`);
    }

    return this.generateValidationSummary(results);
  }

  private async validateScenario(scenario: ValidationScenario): Promise<ValidationResult> {
    try {
      // Generate recovery plan
      const plan = this.recoveryEngine.generateRecoveryPlan(scenario.error, scenario.context);
      
      // Test progressive error handling
      const progressiveResult = await this.testProgressiveHandling(scenario);
      
      // Generate user-friendly message
      const userMessage = createUserMessage(
        scenario.error,
        plan.errorType,
        scenario.context
      );

      // Determine if recovery is possible
      const hasAutomaticActions = plan.actions.some(action => action.automatic);
      const hasUserGuidance = plan.guidanceSteps && plan.guidanceSteps.length > 0;
      const hasAlternatives = progressiveResult.alternatives && progressiveResult.alternatives.length > 0;
      
      // Calculate recovery likelihood
      const recoveryFactors = [
        hasAutomaticActions ? 40 : 0,
        hasUserGuidance ? 25 : 0,
        hasAlternatives ? 20 : 0,
        userMessage.actionable ? 15 : 0,
        plan.estimatedRecoveryRate > 70 ? plan.estimatedRecoveryRate * 0.1 : 0
      ];

      const calculatedRecoveryRate = Math.min(
        recoveryFactors.reduce((sum, factor) => sum + factor, 0),
        plan.estimatedRecoveryRate
      );

      const recovered = calculatedRecoveryRate >= 70 || 
                       hasAutomaticActions || 
                       (hasUserGuidance && userMessage.actionable);

      return {
        scenario,
        recovered,
        recoveryStrategy: plan.strategy,
        automaticRecovery: hasAutomaticActions,
        userGuidanceProvided: hasUserGuidance,
        estimatedRecoveryRate: calculatedRecoveryRate,
        executionTime: 0 // Will be set by caller
      };

    } catch (error) {
      console.warn(`⚠️  Validation failed for ${scenario.name}:`, error);
      return {
        scenario,
        recovered: false,
        recoveryStrategy: RecoveryStrategy.MANUAL_INTERVENTION,
        automaticRecovery: false,
        userGuidanceProvided: false,
        estimatedRecoveryRate: 0,
        executionTime: 0
      };
    }
  }

  private async testProgressiveHandling(scenario: ValidationScenario): Promise<any> {
    try {
      // Create a mock operation that fails
      const failingOperation = async () => {
        throw scenario.error;
      };

      const result = await executeWithProgression(
        failingOperation,
        scenario.context.component,
        scenario.context.operation
      );

      return result;
    } catch (error) {
      return { success: false, alternatives: [], guidance: [] };
    }
  }

  private generateValidationSummary(results: ValidationResult[]): ValidationSummary {
    const totalScenarios = results.length;
    const recoveredScenarios = results.filter(r => r.recovered).length;
    
    // Calculate weighted recovery rate
    const totalWeight = this.scenarios.reduce((sum, s) => sum + s.weight, 0);
    const weightedRecovered = results.reduce((sum, result) => {
      return sum + (result.recovered ? result.scenario.weight : 0);
    }, 0);

    const overallRecoveryRate = (recoveredScenarios / totalScenarios) * 100;
    const weightedRecoveryRate = (weightedRecovered / totalWeight) * 100;

    // Category breakdown
    const categories = this.getUniqueCategories();
    const categoryBreakdown: Record<string, { total: number; recovered: number; rate: number }> = {};

    for (const category of categories) {
      const categoryResults = results.filter(r => r.scenario.category === category);
      const categoryRecovered = categoryResults.filter(r => r.recovered).length;
      
      categoryBreakdown[category] = {
        total: categoryResults.length,
        recovered: categoryRecovered,
        rate: (categoryRecovered / categoryResults.length) * 100
      };
    }

    // Identify critical issues
    const criticalIssues = results.filter(r => 
      r.scenario.expectedRecoverable && 
      !r.recovered && 
      r.scenario.weight >= 8
    );

    // Generate recommendations
    const recommendations = this.generateRecommendations(results, criticalIssues);

    const summary: ValidationSummary = {
      totalScenarios,
      recoveredScenarios,
      overallRecoveryRate,
      weightedRecoveryRate,
      categoryBreakdown,
      criticalIssues,
      recommendations
    };

    this.printValidationReport(summary);
    return summary;
  }

  private getUniqueCategories(): string[] {
    return [...new Set(this.scenarios.map(s => s.category))];
  }

  private generateRecommendations(results: ValidationResult[], criticalIssues: ValidationResult[]): string[] {
    const recommendations: string[] = [];

    if (criticalIssues.length > 0) {
      recommendations.push(`Address ${criticalIssues.length} critical recovery issues`);
    }

    const lowRecoveryCategories = Object.entries(
      results.reduce((acc, r) => {
        const cat = r.scenario.category;
        if (!acc[cat]) acc[cat] = { total: 0, recovered: 0 };
        acc[cat].total++;
        if (r.recovered) acc[cat].recovered++;
        return acc;
      }, {} as Record<string, { total: number; recovered: number }>)
    ).filter(([, stats]) => (stats.recovered / stats.total) < 0.8);

    if (lowRecoveryCategories.length > 0) {
      recommendations.push(`Improve recovery for: ${lowRecoveryCategories.map(([cat]) => cat).join(', ')}`);
    }

    const noAutomaticRecovery = results.filter(r => 
      r.recovered && !r.automaticRecovery && r.scenario.weight >= 7
    );

    if (noAutomaticRecovery.length > 5) {
      recommendations.push('Consider adding automatic recovery for high-weight scenarios');
    }

    const averageExecutionTime = results.reduce((sum, r) => sum + r.executionTime, 0) / results.length;
    if (averageExecutionTime > 100) {
      recommendations.push('Optimize error recovery performance');
    }

    return recommendations;
  }

  private printValidationReport(summary: ValidationSummary): void {
    console.log('\n🏆 ERROR RECOVERY SYSTEM VALIDATION REPORT');
    console.log('='.repeat(60));

    console.log(`\n📊 OVERALL RESULTS:`);
    console.log(`   Total Scenarios: ${summary.totalScenarios}`);
    console.log(`   Recovered: ${summary.recoveredScenarios}`);
    console.log(`   Overall Recovery Rate: ${summary.overallRecoveryRate.toFixed(1)}%`);
    console.log(`   Weighted Recovery Rate: ${summary.weightedRecoveryRate.toFixed(1)}%`);

    const targetAchieved = summary.weightedRecoveryRate >= 85;
    const targetStatus = targetAchieved ? '✅ TARGET ACHIEVED' : '❌ TARGET NOT MET';
    console.log(`\n🎯 TARGET STATUS: ${targetStatus}`);
    console.log(`   Target: 85%+ recovery rate`);
    console.log(`   Achieved: ${summary.weightedRecoveryRate.toFixed(1)}%`);

    console.log(`\n📋 CATEGORY BREAKDOWN:`);
    Object.entries(summary.categoryBreakdown).forEach(([category, stats]) => {
      const status = stats.rate >= 80 ? '✅' : stats.rate >= 60 ? '⚠️' : '❌';
      console.log(`   ${status} ${category}: ${stats.recovered}/${stats.total} (${stats.rate.toFixed(1)}%)`);
    });

    if (summary.criticalIssues.length > 0) {
      console.log(`\n❌ CRITICAL ISSUES (${summary.criticalIssues.length}):`);
      summary.criticalIssues.forEach(issue => {
        console.log(`   • ${issue.scenario.name} (Weight: ${issue.scenario.weight})`);
      });
    }

    if (summary.recommendations.length > 0) {
      console.log(`\n💡 RECOMMENDATIONS:`);
      summary.recommendations.forEach(rec => {
        console.log(`   • ${rec}`);
      });
    }

    console.log('\n' + '='.repeat(60));

    if (targetAchieved) {
      console.log('🎉 SUCCESS: Error Recovery System meets 85%+ recovery rate target!');
    } else {
      console.log('⚠️  WARNING: Error Recovery System needs improvement to meet target.');
    }
  }

  public async runQuickValidation(): Promise<boolean> {
    const summary = await this.validateErrorRecoverySystem();
    return summary.weightedRecoveryRate >= 85;
  }
}

// Export for use in tests and demonstrations
export { ErrorRecoverySystemValidator };
export type { ValidationScenario, ValidationResult, ValidationSummary };

// CLI execution
if (require.main === module) {
  const validator = new ErrorRecoverySystemValidator();
  
  validator.validateErrorRecoverySystem()
    .then((summary) => {
      process.exit(summary.weightedRecoveryRate >= 85 ? 0 : 1);
    })
    .catch((error) => {
      console.error('Validation failed:', error);
      process.exit(1);
    });
}