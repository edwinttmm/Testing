// API Response Cache with TTL and Request Deduplication
interface CacheEntry<T> {
  data: T;
  timestamp: number;
  expiresAt: number;
}

interface PendingRequest {
  promise: Promise<any>;
  timestamp: number;
}

class ApiCache {
  private cache = new Map<string, CacheEntry<any>>();
  private pendingRequests = new Map<string, PendingRequest>();
  private defaultTTL = 5 * 60 * 1000; // 5 minutes default
  private maxCacheSize = 100;

  // Cache configurations per endpoint
  private cacheConfigs = new Map([
    ['/api/dashboard/stats', { ttl: 30 * 1000 }], // 30 seconds for dashboard
    ['/api/projects', { ttl: 2 * 60 * 1000 }], // 2 minutes for projects
    ['/api/dashboard/charts', { ttl: 60 * 1000 }], // 1 minute for charts
    ['health', { ttl: 60 * 1000 }], // 1 minute for health check
  ]);

  private getCacheKey(method: string, url: string, params?: any): string {
    const paramStr = params ? JSON.stringify(params) : '';
    return `${method}:${url}:${paramStr}`;
  }

  private isExpired(entry: CacheEntry<any>): boolean {
    return Date.now() > entry.expiresAt;
  }

  private getTTL(url: string): number {
    // Use Array.from to make it ES5 compatible
    const configs = Array.from(this.cacheConfigs.entries());
    for (let i = 0; i < configs.length; i++) {
      const [pattern, config] = configs[i];
      if (url.includes(pattern)) {
        return config.ttl;
      }
    }
    return this.defaultTTL;
  }

  private cleanup(): void {
    if (this.cache.size <= this.maxCacheSize) return;

    // Remove expired entries first
    const entries = Array.from(this.cache.entries());
    for (let i = 0; i < entries.length; i++) {
      const [key, entry] = entries[i];
      if (this.isExpired(entry)) {
        this.cache.delete(key);
      }
    }

    // If still over limit, remove oldest entries
    if (this.cache.size > this.maxCacheSize) {
      const entries = Array.from(this.cache.entries())
        .sort(([, a], [, b]) => a.timestamp - b.timestamp);
      
      const toRemove = entries.slice(0, entries.length - this.maxCacheSize);
      toRemove.forEach(([key]) => this.cache.delete(key));
    }

    // Clean up old pending requests (older than 30 seconds)
    const now = Date.now();
    const pendingEntries = Array.from(this.pendingRequests.entries());
    for (let i = 0; i < pendingEntries.length; i++) {
      const [key, request] = pendingEntries[i];
      if (now - request.timestamp > 30000) {
        this.pendingRequests.delete(key);
      }
    }
  }

  get<T>(method: string, url: string, params?: any): T | null {
    const key = this.getCacheKey(method, url, params);
    const entry = this.cache.get(key);

    if (!entry || this.isExpired(entry)) {
      return null;
    }

    return entry.data;
  }

  set<T>(method: string, url: string, data: T, params?: any): void {
    const key = this.getCacheKey(method, url, params);
    const ttl = this.getTTL(url);
    const now = Date.now();

    this.cache.set(key, {
      data,
      timestamp: now,
      expiresAt: now + ttl,
    });

    this.cleanup();
  }

  // Request deduplication - returns existing promise if request is already pending
  getPendingRequest(method: string, url: string, params?: any): Promise<any> | null {
    const key = this.getCacheKey(method, url, params);
    const pending = this.pendingRequests.get(key);

    if (pending) {
      return pending.promise;
    }

    return null;
  }

  setPendingRequest(method: string, url: string, promise: Promise<any>, params?: any): void {
    const key = this.getCacheKey(method, url, params);
    this.pendingRequests.set(key, {
      promise,
      timestamp: Date.now(),
    });

    // Clean up when promise completes
    promise.finally(() => {
      this.pendingRequests.delete(key);
    });
  }

  invalidate(method: string, url: string, params?: any): void {
    const key = this.getCacheKey(method, url, params);
    this.cache.delete(key);
    this.pendingRequests.delete(key);
  }

  invalidatePattern(pattern: string): void {
    const cacheKeys = Array.from(this.cache.keys());
    for (let i = 0; i < cacheKeys.length; i++) {
      const key = cacheKeys[i];
      if (key.includes(pattern)) {
        this.cache.delete(key);
      }
    }
    const pendingKeys = Array.from(this.pendingRequests.keys());
    for (let i = 0; i < pendingKeys.length; i++) {
      const key = pendingKeys[i];
      if (key.includes(pattern)) {
        this.pendingRequests.delete(key);
      }
    }
  }

  clear(): void {
    this.cache.clear();
    this.pendingRequests.clear();
  }

  // Get cache statistics
  getStats() {
    const entries = Array.from(this.cache.values());
    const expired = entries.filter(entry => this.isExpired(entry)).length;
    const valid = entries.length - expired;

    return {
      totalEntries: this.cache.size,
      validEntries: valid,
      expiredEntries: expired,
      pendingRequests: this.pendingRequests.size,
      hitRate: valid / (valid + expired) || 0,
    };
  }
}

export const apiCache = new ApiCache();
export default apiCache;