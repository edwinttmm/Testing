/**
 * Global Type Definitions for AI Model Validation Platform
 * Provides TypeScript definitions for global objects and environment variables
 */

// Global Window Extensions
declare global {
  interface Window {
    RUNTIME_CONFIG?: Record<string, any>;
  }

  // Process Environment Extensions (for browser environments)
  namespace NodeJS {
    interface ProcessEnv {
      // Environment Configuration
      NODE_ENV?: 'development' | 'staging' | 'production';
      APP_ENV?: 'development' | 'staging' | 'production';
      AIVALIDATION_APP_ENVIRONMENT?: 'development' | 'staging' | 'production';
      ENVIRONMENT?: string;
      ENV?: string;

      // API Configuration
      REACT_APP_API_URL?: string;
      API_URL?: string;
      REACT_APP_WS_URL?: string;
      WS_URL?: string;
      REACT_APP_SOCKETIO_URL?: string;
      SOCKETIO_URL?: string;

      // CORS Configuration
      CORS_ORIGINS?: string;
      ALLOWED_ORIGINS?: string;

      // Feature Flags
      REACT_APP_DEBUG?: 'true' | 'false';
      REACT_APP_ANALYTICS?: 'true' | 'false';
      REACT_APP_MONITORING?: 'true' | 'false';
      DEBUG?: 'true' | 'false';
      AIVALIDATION_API_DEBUG?: 'true' | 'false';

      // Security Configuration
      SSL_ENABLED?: 'true' | 'false';
      AIVALIDATION_SSL_ENABLED?: 'true' | 'false';
      HTTPS?: 'true' | 'false';

      // Logging Configuration
      LOG_LEVEL?: 'debug' | 'info' | 'warn' | 'error';
      LOG_FILE?: string;

      // Network Configuration
      EXTERNAL_IP?: string;
      PUBLIC_IP?: string;
      SERVER_IP?: string;
      AIVALIDATION_EXTERNAL_IP?: string;
      HOSTNAME?: string;
      COMPUTERNAME?: string;

      // Port Configuration
      FRONTEND_PORT?: string;
      PORT?: string;
      BACKEND_PORT?: string;
      API_PORT?: string;
      WEBSOCKET_PORT?: string;
      WS_PORT?: string;
      SOCKETIO_PORT?: string;

      // Docker Configuration
      DOCKER?: 'true' | 'false';
      CONTAINER_NAME?: string;
      DOCKER_NETWORK?: string;
      COMPOSE_PROJECT_NAME?: string;

      // Cloud Configuration
      KUBERNETES_SERVICE_HOST?: string;
      K8S_NAMESPACE?: string;
      AWS_REGION?: string;
      AWS_LAMBDA_FUNCTION_NAME?: string;
      GOOGLE_CLOUD_PROJECT?: string;
      GCP_PROJECT?: string;
      GOOGLE_CLOUD_REGION?: string;
      AZURE_RESOURCE_GROUP?: string;
      AZURE_CLIENT_ID?: string;
      AZURE_REGION?: string;
      CLOUD_PROVIDER?: string;
      DEPLOYMENT_ENV?: string;

      // Additional Environment Variables
      STAGING?: 'true' | 'false';
      DEPLOYMENT_STAGE?: string;
      API_HOST?: string;
      MONITORING_ENABLED?: 'true' | 'false';
    }
  }

  // Extended Process Interface (for browser compatibility)
  interface Process {
    env: NodeJS.ProcessEnv;
  }

  var process: Process;
}

// Fetch API Extensions (for timeout support)
declare interface RequestInit {
  timeout?: number;
  signal?: AbortSignal;
}

// AbortSignal Extensions
declare interface AbortSignalStatic {
  timeout(delay: number): AbortSignal;
}

// Export empty object to make this a module
export {};