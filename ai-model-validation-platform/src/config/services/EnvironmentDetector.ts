/**
 * Environment Detection Service
 * Automatically detects deployment environment, platform, and network configuration
 * Part of the Unified Configuration Architecture
 */

export interface Environment {
  type: 'development' | 'staging' | 'production';
  platform: 'local' | 'docker' | 'cloud';
  network: {
    internalIP: string;
    externalIP?: string;
    hostname: string;
    dockerNetwork?: string;
    ports: {
      frontend: number;
      backend: number;
      websocket: number;
      socketio: number;
    };
  };
  features: {
    ssl: boolean;
    cors: string[];
    debugging: boolean;
    analytics: boolean;
    monitoring: boolean;
  };
  deployment: {
    containerized: boolean;
    orchestrator?: 'docker-compose' | 'kubernetes';
    region?: string;
  };
}

export class EnvironmentDetector {
  private static instance: EnvironmentDetector;
  private detectedEnvironment: Environment | null = null;
  private detectionTime: number = 0;
  private readonly CACHE_DURATION = 60000; // 1 minute cache

  static getInstance(): EnvironmentDetector {
    if (!this.instance) {
      this.instance = new EnvironmentDetector();
    }
    return this.instance;
  }

  /**
   * Detect complete environment configuration
   */
  async detectEnvironment(force = false): Promise<Environment> {
    // Return cached result if recent and not forced
    if (!force && this.detectedEnvironment && 
        (Date.now() - this.detectionTime) < this.CACHE_DURATION) {
      return this.detectedEnvironment;
    }

    console.log('🔍 Starting environment detection...');

    const platform = await this.detectPlatform();
    const environmentType = this.detectEnvironmentType();
    const network = await this.detectNetwork();
    const features = this.detectFeatures(environmentType, platform);
    const deployment = await this.detectDeployment();

    this.detectedEnvironment = {
      type: environmentType,
      platform,
      network,
      features,
      deployment
    };

    this.detectionTime = Date.now();

    console.log('✅ Environment detection complete:', {
      type: this.detectedEnvironment.type,
      platform: this.detectedEnvironment.platform,
      containerized: this.detectedEnvironment.deployment.containerized,
      externalIP: this.detectedEnvironment.network.externalIP
    });

    return this.detectedEnvironment;
  }

  /**
   * Detect deployment platform (local, docker, cloud)
   */
  private async detectPlatform(): Promise<Environment['platform']> {
    // Check for Docker environment indicators
    if (await this.isDockerEnvironment()) {
      return 'docker';
    }

    // Check for cloud environment indicators
    if (await this.isCloudEnvironment()) {
      return 'cloud';
    }

    return 'local';
  }

  /**
   * Check if running in Docker environment
   */
  private async isDockerEnvironment(): Promise<boolean> {
    const dockerIndicators = [
      // Environment variables
      () => process.env.DOCKER === 'true',
      () => process.env.CONTAINER_NAME !== undefined,
      () => process.env.HOSTNAME?.startsWith('docker'),
      
      // Filesystem indicators (Node.js only)
      () => {
        if (typeof window !== 'undefined') return false;
        try {
          const fs = require('fs');
          return fs.existsSync('/.dockerenv') || 
                 fs.existsSync('/proc/1/cgroup') && 
                 fs.readFileSync('/proc/1/cgroup', 'utf8').includes('docker');
        } catch {
          return false;
        }
      },
      
      // Network indicators
      () => process.env.DOCKER_NETWORK !== undefined
    ];

    return dockerIndicators.some(check => check());
  }

  /**
   * Check if running in cloud environment
   */
  private async isCloudEnvironment(): Promise<boolean> {
    const cloudIndicators = [
      // Kubernetes
      () => process.env.KUBERNETES_SERVICE_HOST !== undefined,
      () => process.env.K8S_NAMESPACE !== undefined,
      
      // AWS
      () => process.env.AWS_REGION !== undefined,
      () => process.env.AWS_LAMBDA_FUNCTION_NAME !== undefined,
      
      // Google Cloud
      () => process.env.GOOGLE_CLOUD_PROJECT !== undefined,
      () => process.env.GCP_PROJECT !== undefined,
      
      // Azure
      () => process.env.AZURE_RESOURCE_GROUP !== undefined,
      () => process.env.AZURE_CLIENT_ID !== undefined,
      
      // Generic cloud indicators
      () => process.env.CLOUD_PROVIDER !== undefined,
      () => process.env.DEPLOYMENT_ENV === 'cloud'
    ];

    return cloudIndicators.some(check => check());
  }

  /**
   * Detect environment type (development, staging, production)
   */
  private detectEnvironmentType(): Environment['type'] {
    const envVars = [
      process.env.AIVALIDATION_APP_ENVIRONMENT,
      process.env.APP_ENV,
      process.env.NODE_ENV,
      process.env.ENVIRONMENT,
      process.env.ENV
    ];

    for (const env of envVars) {
      if (env) {
        const envLower = env.toLowerCase();
        if (['production', 'prod'].includes(envLower)) return 'production';
        if (['staging', 'stage', 'test'].includes(envLower)) return 'staging';
        if (['development', 'dev', 'local'].includes(envLower)) return 'development';
      }
    }

    // Auto-detect based on other indicators
    if (this.isProductionIndicators()) return 'production';
    if (this.isStagingIndicators()) return 'staging';

    return 'development';
  }

  /**
   * Check for production environment indicators
   */
  private isProductionIndicators(): boolean {
    return [
      process.env.DEBUG === 'false',
      process.env.AIVALIDATION_API_DEBUG === 'false',
      process.env.SSL_ENABLED === 'true',
      process.env.MONITORING_ENABLED === 'true',
      typeof window === 'undefined' && process.env.NODE_ENV === 'production'
    ].some(indicator => indicator);
  }

  /**
   * Check for staging environment indicators
   */
  private isStagingIndicators(): boolean {
    return [
      process.env.STAGING === 'true',
      process.env.DEPLOYMENT_STAGE === 'staging',
      process.env.API_HOST?.includes('staging'),
      process.env.HOSTNAME?.includes('staging')
    ].some(indicator => indicator);
  }

  /**
   * Detect network configuration
   */
  private async detectNetwork(): Promise<Environment['network']> {
    const internalIP = await this.detectInternalIP();
    const externalIP = await this.detectExternalIP();
    const hostname = this.detectHostname();
    const dockerNetwork = await this.detectDockerNetwork();
    const ports = this.detectPorts();

    return {
      internalIP,
      externalIP,
      hostname,
      dockerNetwork,
      ports
    };
  }

  /**
   * Detect internal IP address
   */
  private async detectInternalIP(): Promise<string> {
    // Browser environment
    if (typeof window !== 'undefined') {
      return window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname;
    }

    // Node.js environment
    try {
      const os = await import('os');
      const interfaces = os.networkInterfaces();
      
      // Find first non-internal IPv4 address
      for (const [name, addresses] of Object.entries(interfaces)) {
        if (!addresses) continue;
        
        for (const addr of addresses) {
          if (addr.family === 'IPv4' && !addr.internal) {
            return addr.address;
          }
        }
      }
    } catch (error) {
      console.warn('Could not detect internal IP:', error);
    }

    return '127.0.0.1';
  }

  /**
   * Detect external IP address
   */
  private async detectExternalIP(): Promise<string | undefined> {
    // Check configured external IP first
    const configuredIPs = [
      process.env.EXTERNAL_IP,
      process.env.PUBLIC_IP,
      process.env.SERVER_IP,
      process.env.AIVALIDATION_EXTERNAL_IP
    ];

    for (const ip of configuredIPs) {
      if (ip && this.isValidIP(ip)) {
        console.log(`📍 Using configured external IP: ${ip}`);
        return ip;
      }
    }

    // Browser environment - use current hostname if it's an IP
    if (typeof window !== 'undefined') {
      const hostname = window.location.hostname;
      if (this.isValidIP(hostname)) {
        return hostname;
      }
    }

    // Auto-detect external IP (Node.js only)
    if (typeof window === 'undefined') {
      try {
        console.log('🌐 Auto-detecting external IP...');
        
        // Try multiple IP detection services for reliability
        const ipServices = [
          'https://api.ipify.org?format=json',
          'https://httpbin.org/ip',
          'https://ipinfo.io/ip'
        ];

        for (const service of ipServices) {
          try {
            const response = await fetch(service, { 
              timeout: 5000,
              signal: AbortSignal.timeout(5000)
            });
            
            if (response.ok) {
              const data = await response.json();
              const ip = data.ip || data.origin?.split(' ')[0] || data;
              
              if (typeof ip === 'string' && this.isValidIP(ip)) {
                console.log(`📍 Auto-detected external IP: ${ip}`);
                return ip;
              }
            }
          } catch (error) {
            console.warn(`Failed to get IP from ${service}:`, error.message);
            continue;
          }
        }
      } catch (error) {
        console.warn('Could not auto-detect external IP:', error.message);
      }
    }

    return undefined;
  }

  /**
   * Validate IP address format
   */
  private isValidIP(ip: string): boolean {
    const ipv4Regex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    return ipv4Regex.test(ip);
  }

  /**
   * Detect hostname
   */
  private detectHostname(): string {
    if (typeof window !== 'undefined') {
      return window.location.hostname;
    }

    return process.env.HOSTNAME || 
           process.env.COMPUTERNAME || 
           'localhost';
  }

  /**
   * Detect Docker network name
   */
  private async detectDockerNetwork(): Promise<string | undefined> {
    const dockerNetworks = [
      process.env.DOCKER_NETWORK,
      process.env.COMPOSE_PROJECT_NAME,
      'vru_validation_network',
      'ai_validation_network'
    ];

    for (const network of dockerNetworks) {
      if (network) return network;
    }

    return undefined;
  }

  /**
   * Detect service ports
   */
  private detectPorts(): Environment['network']['ports'] {
    return {
      frontend: parseInt(process.env.FRONTEND_PORT || process.env.PORT || '3000'),
      backend: parseInt(process.env.BACKEND_PORT || process.env.API_PORT || '8000'),
      websocket: parseInt(process.env.WEBSOCKET_PORT || process.env.WS_PORT || '8000'),
      socketio: parseInt(process.env.SOCKETIO_PORT || '8001')
    };
  }

  /**
   * Detect environment features
   */
  private detectFeatures(
    environmentType: Environment['type'], 
    platform: Environment['platform']
  ): Environment['features'] {
    const isProduction = environmentType === 'production';
    
    return {
      ssl: this.detectSSLEnabled(isProduction),
      cors: [], // Will be populated by CORS configuration
      debugging: !isProduction,
      analytics: isProduction,
      monitoring: isProduction || environmentType === 'staging'
    };
  }

  /**
   * Detect SSL/TLS configuration
   */
  private detectSSLEnabled(isProduction: boolean): boolean {
    // Check explicit SSL configuration
    const sslEnvVars = [
      process.env.SSL_ENABLED,
      process.env.AIVALIDATION_SSL_ENABLED,
      process.env.HTTPS
    ];

    for (const sslVar of sslEnvVars) {
      if (sslVar === 'true') return true;
      if (sslVar === 'false') return false;
    }

    // Auto-detect SSL based on environment
    if (typeof window !== 'undefined') {
      return window.location.protocol === 'https:';
    }

    // Default to SSL in production
    return isProduction;
  }

  /**
   * Detect deployment configuration
   */
  private async detectDeployment(): Promise<Environment['deployment']> {
    const containerized = await this.isDockerEnvironment() || await this.isCloudEnvironment();
    
    let orchestrator: 'docker-compose' | 'kubernetes' | undefined;
    if (process.env.KUBERNETES_SERVICE_HOST) {
      orchestrator = 'kubernetes';
    } else if (process.env.COMPOSE_PROJECT_NAME || containerized) {
      orchestrator = 'docker-compose';
    }

    const region = process.env.AWS_REGION || 
                  process.env.GOOGLE_CLOUD_REGION || 
                  process.env.AZURE_REGION;

    return {
      containerized,
      orchestrator,
      region
    };
  }

  /**
   * Get environment summary for logging
   */
  getEnvironmentSummary(): Record<string, any> {
    if (!this.detectedEnvironment) {
      return { status: 'not_detected' };
    }

    return {
      type: this.detectedEnvironment.type,
      platform: this.detectedEnvironment.platform,
      containerized: this.detectedEnvironment.deployment.containerized,
      ssl: this.detectedEnvironment.features.ssl,
      network: {
        internal: this.detectedEnvironment.network.internalIP,
        external: this.detectedEnvironment.network.externalIP,
        hostname: this.detectedEnvironment.network.hostname
      },
      ports: this.detectedEnvironment.network.ports,
      detectedAt: new Date(this.detectionTime).toISOString()
    };
  }
}

// Export singleton instance
export const environmentDetector = EnvironmentDetector.getInstance();