/**
 * Video URL Fixer Utility - Production-Ready Optimized Version
 * 
 * Provides centralized video URL fixing functionality to ensure all video URLs
 * use the correct backend server URL instead of localhost references.
 * 
 * Advanced Optimizations:
 * - Multi-level intelligent caching system
 * - Batch processing with chunking and throttling
 * - Performance monitoring and metrics
 * - Migration-aware processing
 * - Duplicate detection and deduplication
 * - Background processing queue
 * - Production fallback strategies
 * - Comprehensive error recovery
 */

import { getServiceConfig } from './envConfig';

// Multi-level cache system
interface CacheEntry {
  value: string;
  timestamp: number;
  hits: number;
  lastAccess: number;
}

interface ProcessingMetrics {
  totalProcessed: number;
  totalSkipped: number;
  cacheHits: number;
  cacheMisses: number;
  batchesProcessed: number;
  averageProcessingTime: number;
  errorsEncountered: number;
  migrationAwareSkips: number;
}

// Advanced caching configuration
const CACHE_CONFIG = {
  BASE_URL_TTL: 300000, // 5 minutes for base URL
  URL_MAPPING_TTL: 600000, // 10 minutes for URL mappings
  DEDUP_TTL: 60000, // 1 minute for deduplication
  MAX_CACHE_SIZE: 1000,
  CLEANUP_INTERVAL: 300000 // 5 minutes
};

// Multi-level cache stores
let cachedVideoBaseUrl: string | null = null;
let baseUrlCacheTimestamp = 0;
const urlMappingCache = new Map<string, CacheEntry>();
const deduplicationCache = new Set<string>();
const processingQueue: Array<() => Promise<void>> = [];
let isProcessingQueue = false;

// Performance metrics
const metrics: ProcessingMetrics = {
  totalProcessed: 0,
  totalSkipped: 0,
  cacheHits: 0,
  cacheMisses: 0,
  batchesProcessed: 0,
  averageProcessingTime: 0,
  errorsEncountered: 0,
  migrationAwareSkips: 0
};

// Migration state detection
interface MigrationState {
  isActive: boolean;
  lastChecked: number;
  checkInterval: number;
}

const migrationState: MigrationState = {
  isActive: false,
  lastChecked: 0,
  checkInterval: 30000 // Check every 30 seconds
};

export interface VideoUrlFixOptions {
  forceAbsolute?: boolean | undefined;
  debug?: boolean | undefined;
  skipValidation?: boolean | undefined;
  skipCache?: boolean | undefined;
  skipDeduplication?: boolean | undefined;
  forceDuringMigration?: boolean | undefined;
}

// Performance optimization: Pre-compiled regex patterns
const LOCALHOST_PATTERN = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?/;
const RELATIVE_PATH_PATTERN = /^\//;
const PROTOCOL_PATTERN = /^https?:\/\//;
const CORRUPTED_PORT_PATTERN = /:8000:8000/;
const TARGET_HOST_PATTERN = /155\.138\.239\.131/;

/**
 * Detect if database migration is currently active
 */
function checkMigrationState(): boolean {
  const now = Date.now();
  if (now - migrationState.lastChecked < migrationState.checkInterval) {
    return migrationState.isActive;
  }
  
  try {
    // Check for migration indicators
    const config = getServiceConfig('database');
    migrationState.isActive = config?.migrating === true || 
                              process.env.MIGRATION_ACTIVE === 'true' ||
                              document.cookie.includes('migration-active=true');
    migrationState.lastChecked = now;
  } catch (error) {
    // Assume no migration if check fails
    migrationState.isActive = false;
  }
  
  return migrationState.isActive;
}

/**
 * Get cached video base URL with advanced TTL and fallback strategies
 */
function getCachedVideoBaseUrl(): string {
  const now = Date.now();
  
  // Return cached value if still valid
  if (cachedVideoBaseUrl && (now - baseUrlCacheTimestamp) < CACHE_CONFIG.BASE_URL_TTL) {
    return cachedVideoBaseUrl;
  }
  
  try {
    // Try to get from service config
    const videoConfig = getServiceConfig('video');
    cachedVideoBaseUrl = videoConfig?.baseUrl ?? null;
    
    // Fallback strategies
    if (!cachedVideoBaseUrl) {
      // Production fallback
      cachedVideoBaseUrl = 'http://155.138.239.131:8000';
      
      // Environment-based fallback
      if (typeof window !== 'undefined') {
        const hostname = window.location.hostname;
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
          cachedVideoBaseUrl = 'http://localhost:8000';
        }
      }
    }
    
    baseUrlCacheTimestamp = now;
    return cachedVideoBaseUrl;
  } catch (error) {
    // Ultimate fallback
    cachedVideoBaseUrl = 'http://155.138.239.131:8000';
    baseUrlCacheTimestamp = now;
    return cachedVideoBaseUrl;
  }
}

/**
 * Intelligent cache lookup with hit tracking
 */
function getCachedMapping(originalUrl: string): string | null {
  const entry = urlMappingCache.get(originalUrl);
  const now = Date.now();
  
  if (entry && (now - entry.timestamp) < CACHE_CONFIG.URL_MAPPING_TTL) {
    entry.hits++;
    entry.lastAccess = now;
    metrics.cacheHits++;
    return entry.value;
  }
  
  if (entry) {
    // Remove expired entry
    urlMappingCache.delete(originalUrl);
  }
  
  metrics.cacheMisses++;
  return null;
}

/**
 * Store URL mapping in cache with intelligent eviction
 */
function setCachedMapping(originalUrl: string, fixedUrl: string): void {
  const now = Date.now();
  
  // Clean up cache if it's getting too large
  if (urlMappingCache.size >= CACHE_CONFIG.MAX_CACHE_SIZE) {
    cleanupCache();
  }
  
  urlMappingCache.set(originalUrl, {
    value: fixedUrl,
    timestamp: now,
    hits: 0,
    lastAccess: now
  });
}

/**
 * Clean up expired and least-used cache entries
 */
function cleanupCache(): void {
  const now = Date.now();
  const entries = Array.from(urlMappingCache.entries());
  
  // Remove expired entries
  for (const [key, entry] of entries) {
    if (now - entry.timestamp > CACHE_CONFIG.URL_MAPPING_TTL) {
      urlMappingCache.delete(key);
    }
  }
  
  // If still too large, remove least recently used
  if (urlMappingCache.size >= CACHE_CONFIG.MAX_CACHE_SIZE) {
    const sortedEntries = Array.from(urlMappingCache.entries())
      .sort(([,a], [,b]) => a.lastAccess - b.lastAccess);
    
    const toRemove = Math.floor(CACHE_CONFIG.MAX_CACHE_SIZE * 0.2); // Remove 20%
    for (let i = 0; i < toRemove; i++) {
      if (sortedEntries[i]) {
        urlMappingCache.delete(sortedEntries[i][0]);
      }
    }
  }
}

/**
 * Check if URL has been processed recently to avoid duplicates
 */
function isDuplicateProcessing(url: string): boolean {
  const key = `${url}-${Date.now() - (Date.now() % CACHE_CONFIG.DEDUP_TTL)}`;
  if (deduplicationCache.has(key)) {
    return true;
  }
  
  deduplicationCache.add(key);
  
  // Clean up old dedup entries periodically
  if (deduplicationCache.size > 500) {
    deduplicationCache.clear();
  }
  
  return false;
}

/**
 * Fix video URL to use the correct backend base URL - Production-Ready Optimized Version
 * 
 * Advanced features:
 * - Multi-level intelligent caching
 * - Migration-aware processing
 * - Duplicate detection
 * - Performance metrics tracking
 * - Background queue processing
 * - Comprehensive error recovery
 * 
 * Performance optimizations:
 * - Cached URL mapping lookups
 * - Pre-compiled regex patterns
 * - Early returns for common cases
 * - Reduced string operations
 * - Batch processing optimizations
 */
export function fixVideoUrl(
  url: string | undefined, 
  filename?: string, 
  id?: string,
  options: VideoUrlFixOptions = {}
): string {
  const startTime = performance.now();
  const { forceAbsolute = false, debug = false, skipValidation = false } = options;
  
  try {
    // Check for duplicate processing to avoid unnecessary work
    if (!options.skipDeduplication && url && isDuplicateProcessing(url)) {
      metrics.totalSkipped++;
      if (debug) {
        console.log('🔧 fixVideoUrl skipped duplicate processing:', url);
      }
      return url;
    }
    
    // Migration-aware processing - reduce load during migrations
    const isMigrationActive = checkMigrationState();
    if (isMigrationActive && !options.forceDuringMigration) {
      metrics.migrationAwareSkips++;
      
      // During migration, only do essential fixes
      if (!url || url.includes('localhost')) {
        // Quick essential fix without full processing
        const baseUrl = getCachedVideoBaseUrl();
        const quickFix = url ? url.replace(LOCALHOST_PATTERN, baseUrl) : 
                               (filename ? `${baseUrl}/uploads/${filename}` : '');
        if (debug) {
          console.log('🔧 fixVideoUrl migration-aware quick fix:', url, '->', quickFix);
        }
        return quickFix;
      }
      return url || '';
    }
    
    if (debug) {
      console.log('🔧 fixVideoUrl called with:', { url, filename, id, isMigrationActive });
    }
    
    // Check cache first for known URL mappings
    if (url && !options.skipCache) {
      const cachedResult = getCachedMapping(url);
      if (cachedResult) {
        metrics.totalProcessed++;
        if (debug) {
          console.log('🔧 fixVideoUrl cache hit:', url, '->', cachedResult);
        }
        return cachedResult;
      }
    }
    
    const baseUrl = getCachedVideoBaseUrl();
    let fixedUrl = '';
    
    // Early return for empty URLs - construct from filename or id
    if (!url || url.trim() === '') {
      const fallbackName = (filename && filename.trim()) || (id && id.trim());
      if (fallbackName) {
        fixedUrl = `${baseUrl}/uploads/${fallbackName}`;
        if (debug) {
          console.log('🔧 fixVideoUrl constructed from fallback:', fixedUrl);
        }
      } else {
        if (debug) {
          console.warn('🔧 fixVideoUrl no URL, filename, or id provided');
        }
        return '';
      }
    }
    
    // Process non-empty URLs
    if (!fixedUrl && url) {
      const originalUrl = url;
      
      // Early return if URL already looks correct and skip validation is enabled
      if (skipValidation && url.includes('155.138.239.131')) {
        fixedUrl = url;
      }
      // Fix localhost URLs - optimized with regex patterns
      else if (LOCALHOST_PATTERN.test(url)) {
        try {
          const urlObj = new URL(url);
          const targetUrlObj = new URL(baseUrl);
          
          // Only replace if it's actually localhost/127.0.0.1
          if (urlObj.hostname === 'localhost' || urlObj.hostname === '127.0.0.1') {
            fixedUrl = `${targetUrlObj.protocol}//${targetUrlObj.host}${urlObj.pathname}${urlObj.search}${urlObj.hash}`;
            if (debug) {
              console.log('🔧 fixVideoUrl fixed localhost with URL parsing:', url, '->', fixedUrl);
            }
          } else {
            fixedUrl = url;
          }
        } catch (urlError) {
          // Fast fallback for malformed URLs
          if (CORRUPTED_PORT_PATTERN.test(url)) {
            const pathPart = url.split('/').slice(3).join('/');
            fixedUrl = `${baseUrl}/${pathPart}`;
            if (debug) {
              console.log('🔧 fixVideoUrl fixed corrupted URL:', url, '->', fixedUrl);
            }
          }
          // Only fix if target host not already present
          else if (!TARGET_HOST_PATTERN.test(url)) {
            fixedUrl = url.replace(LOCALHOST_PATTERN, baseUrl);
            if (debug) {
              console.log('🔧 fixVideoUrl fixed localhost with regex:', url, '->', fixedUrl);
            }
          } else {
            fixedUrl = url;
          }
        }
      }
      // Convert relative URLs to absolute - fast path check
      else if (RELATIVE_PATH_PATTERN.test(url)) {
        fixedUrl = `${baseUrl}${url}`;
        if (debug) {
          console.log('🔧 fixVideoUrl converted relative URL:', url, '->', fixedUrl);
        }
      }
      // Force absolute URLs - optimized protocol check
      else if (forceAbsolute && !PROTOCOL_PATTERN.test(url)) {
        fixedUrl = `${baseUrl}/${url}`;
        if (debug) {
          console.log('🔧 fixVideoUrl forced absolute:', url, '->', fixedUrl);
        }
      }
      // URL is already correct, return as-is
      else {
        fixedUrl = url;
        if (debug) {
          console.log('🔧 fixVideoUrl URL already correct:', url);
        }
      }
      
      // Cache the result if it was processed
      if (originalUrl && fixedUrl !== originalUrl && !options.skipCache) {
        setCachedMapping(originalUrl, fixedUrl);
      }
    }
    
    // Update metrics
    metrics.totalProcessed++;
    const processingTime = performance.now() - startTime;
    metrics.averageProcessingTime = (
      (metrics.averageProcessingTime * (metrics.totalProcessed - 1) + processingTime) / 
      metrics.totalProcessed
    );
    
    return fixedUrl;
    
  } catch (error) {
    metrics.errorsEncountered++;
    if (debug) {
      console.error('🔧 fixVideoUrl error:', error, 'for URL:', url);
    }
    
    // Fallback error handling
    if (url && url.includes('localhost')) {
      const baseUrl = getCachedVideoBaseUrl();
      return url.replace(LOCALHOST_PATTERN, baseUrl);
    }
    
    return url || '';
  }
}

/**
 * Fix video object's URL property in-place
 */
export function fixVideoObjectUrl(
  video: { url?: string; filename?: string; id?: string },
  options: VideoUrlFixOptions = {}
): void {
  if (!video) return;
  
  const originalUrl = video.url;
  video.url = fixVideoUrl(video.url, video.filename, video.id, options);
  
  if (options.debug && originalUrl !== video.url) {
    console.log('🔧 fixVideoObjectUrl updated:', originalUrl, '->', video.url);
  }
}

/**
 * Advanced batch processing with chunking, throttling, and intelligent scheduling
 */
export async function fixMultipleVideoUrls(
  videos: Array<{ url?: string; filename?: string; id?: string }>,
  options: VideoUrlFixOptions & {
    chunkSize?: number;
    throttleMs?: number;
    priority?: 'low' | 'medium' | 'high';
    useBackgroundQueue?: boolean;
  } = {}
): Promise<void> {
  if (!videos || videos.length === 0) return;
  
  const {
    chunkSize = 50,
    throttleMs = 10,
    priority = 'medium',
    useBackgroundQueue = false,
    ...fixOptions
  } = options;
  
  const startTime = performance.now();
  let processed = 0;
  let skipped = 0;
  let errorsCount = 0;
  
  // Check migration state for adaptive processing
  const isMigrationActive = checkMigrationState();
  const adaptiveChunkSize = isMigrationActive ? Math.max(10, Math.floor(chunkSize / 3)) : chunkSize;
  const adaptiveThrottle = isMigrationActive ? throttleMs * 3 : throttleMs;
  
  if (options.debug) {
    console.log(`🔧 fixMultipleVideoUrls starting batch processing:`, {
      totalVideos: videos.length,
      chunkSize: adaptiveChunkSize,
      throttle: adaptiveThrottle,
      migrationActive: isMigrationActive,
      useBackgroundQueue
    });
  }
  
  // Pre-filter videos for efficiency
  const videosToProcess = videos.filter((video, index) => {
    if (!video) {
      skipped++;
      return false;
    }
    
    // Early skip for videos that look correct
    if (video.url && video.url.includes('155.138.239.131') && !video.url.includes('localhost')) {
      skipped++;
      return false;
    }
    
    return true;
  });
  
  if (videosToProcess.length === 0) {
    if (options.debug) {
      console.log(`🔧 fixMultipleVideoUrls no videos to process, skipped ${skipped}`);
    }
    return;
  }
  
  // Background queue processing for non-urgent tasks
  if (useBackgroundQueue && priority === 'low') {
    queueBackgroundProcessing(() => 
      processBatchChunks(videosToProcess, adaptiveChunkSize, adaptiveThrottle, fixOptions)
        .then(() => {
          metrics.batchesProcessed++;
          if (options.debug) {
            console.log(`🔧 Background batch processing completed for ${videosToProcess.length} videos`);
          }
        })
        .catch(error => {
          console.error('🔧 Background batch processing error:', error);
        })
    );
    return;
  }
  
  // Immediate processing
  try {
    const results = await processBatchChunks(videosToProcess, adaptiveChunkSize, adaptiveThrottle, fixOptions);
    processed = results.processed;
    errorsCount = results.errors;
    
    const endTime = performance.now();
    const totalTime = endTime - startTime;
    
    // Update global metrics
    metrics.batchesProcessed++;
    metrics.totalProcessed += processed;
    metrics.totalSkipped += skipped;
    metrics.errorsEncountered += errorsCount;
    
    if (options.debug) {
      console.log(`🔧 fixMultipleVideoUrls completed:`, {
        processed,
        skipped,
        errors: errorsCount,
        totalTime: `${totalTime.toFixed(2)}ms`,
        avgPerVideo: `${(totalTime / (processed + skipped)).toFixed(2)}ms`,
        throughput: `${((processed + skipped) / totalTime * 1000).toFixed(0)} videos/sec`
      });
    }
    
  } catch (error) {
    metrics.errorsEncountered++;
    if (options.debug) {
      console.error('🔧 fixMultipleVideoUrls batch processing error:', error);
    }
    throw error;
  }
}

/**
 * Process videos in chunks with throttling
 */
async function processBatchChunks(
  videos: Array<{ url?: string; filename?: string; id?: string }>,
  chunkSize: number,
  throttleMs: number,
  fixOptions: VideoUrlFixOptions
): Promise<{ processed: number; errors: number }> {
  let processed = 0;
  let errors = 0;
  
  const optimizedOptions = {
    ...fixOptions,
    skipValidation: true,
    skipDeduplication: false, // Keep dedup for batch processing
    debug: false
  };
  
  // Process in chunks
  for (let i = 0; i < videos.length; i += chunkSize) {
    const chunk = videos.slice(i, i + chunkSize);
    
    // Process chunk in parallel
    const chunkPromises = chunk.map(async (video, index) => {
      try {
        const debug = fixOptions.debug === true && i + index < 3; // Only debug first 3
        fixVideoObjectUrl(video, { ...optimizedOptions, debug });
        return { success: true, error: null };
      } catch (error) {
        return { success: false, error };
      }
    });
    
    const chunkResults = await Promise.all(chunkPromises);
    
    // Count results
    for (const result of chunkResults) {
      if (result.success) {
        processed++;
      } else {
        errors++;
        if (fixOptions.debug) {
          console.error('🔧 Chunk processing error:', result.error);
        }
      }
    }
    
    // Throttle between chunks (except for last chunk)
    if (i + chunkSize < videos.length && throttleMs > 0) {
      await new Promise(resolve => setTimeout(resolve, throttleMs));
    }
  }
  
  return { processed, errors };
}

/**
 * Queue function for background processing
 */
function queueBackgroundProcessing(task: () => Promise<void>): void {
  processingQueue.push(task);
  
  if (!isProcessingQueue) {
    processQueue();
  }
}

/**
 * Process background queue with rate limiting
 */
async function processQueue(): Promise<void> {
  if (isProcessingQueue || processingQueue.length === 0) {
    return;
  }
  
  isProcessingQueue = true;
  
  try {
    while (processingQueue.length > 0) {
      const task = processingQueue.shift();
      if (task) {
        try {
          await task();
        } catch (error) {
          console.error('🔧 Background queue task error:', error);
        }
        
        // Rate limiting for background tasks
        if (processingQueue.length > 0) {
          await new Promise(resolve => setTimeout(resolve, 100));
        }
      }
    }
  } finally {
    isProcessingQueue = false;
  }
}

/**
 * Validate if a video URL is accessible (basic check) - Optimized
 */
export function isVideoUrlValid(url: string): boolean {
  if (!url || url.trim() === '') return false;
  
  // Fast regex check before expensive URL parsing
  if (!PROTOCOL_PATTERN.test(url)) return false;
  
  try {
    const urlObj = new URL(url);
    return urlObj.protocol === 'http:' || urlObj.protocol === 'https:';
  } catch {
    return false;
  }
}

/**
 * Get the proper video base URL for the current environment - Cached
 */
export function getVideoBaseUrl(): string {
  return getCachedVideoBaseUrl();
}

/**
 * Clear the base URL cache (useful for testing or config changes)
 */
export function clearBaseUrlCache(): void {
  cachedVideoBaseUrl = null;
  baseUrlCacheTimestamp = 0;
}

/**
 * Clear all caches (comprehensive reset)
 */
export function clearAllCaches(): void {
  clearBaseUrlCache();
  urlMappingCache.clear();
  deduplicationCache.clear();
  resetMetrics();
}

/**
 * Comprehensive performance monitoring and metrics collection
 */
export function getPerformanceMetrics(): ProcessingMetrics & {
  cacheStats: {
    urlMappingCacheSize: number;
    baseUrlCacheAge: number;
    deduplicationCacheSize: number;
    cacheHitRate: number;
  };
  systemStats: {
    migrationActive: boolean;
    queueLength: number;
    isProcessingQueue: boolean;
    uptime: number;
  };
} {
  const now = Date.now();
  const totalCacheRequests = metrics.cacheHits + metrics.cacheMisses;
  
  return {
    ...metrics,
    cacheStats: {
      urlMappingCacheSize: urlMappingCache.size,
      baseUrlCacheAge: cachedVideoBaseUrl ? now - baseUrlCacheTimestamp : 0,
      deduplicationCacheSize: deduplicationCache.size,
      cacheHitRate: totalCacheRequests > 0 ? metrics.cacheHits / totalCacheRequests : 0
    },
    systemStats: {
      migrationActive: migrationState.isActive,
      queueLength: processingQueue.length,
      isProcessingQueue,
      uptime: now - (baseUrlCacheTimestamp || now)
    }
  };
}

/**
 * Generate performance report with insights
 */
export function generatePerformanceReport(): {
  summary: string;
  metrics: ReturnType<typeof getPerformanceMetrics>;
  insights: string[];
  recommendations: string[];
} {
  const metrics = getPerformanceMetrics();
  const insights: string[] = [];
  const recommendations: string[] = [];
  
  // Generate insights
  if (metrics.cacheStats.cacheHitRate > 0.8) {
    insights.push(`Excellent cache performance: ${(metrics.cacheStats.cacheHitRate * 100).toFixed(1)}% hit rate`);
  } else if (metrics.cacheStats.cacheHitRate < 0.5) {
    insights.push(`Low cache hit rate: ${(metrics.cacheStats.cacheHitRate * 100).toFixed(1)}%`);
    recommendations.push('Consider increasing cache TTL or reviewing URL patterns');
  }
  
  if (metrics.averageProcessingTime > 5) {
    insights.push(`High processing time: ${metrics.averageProcessingTime.toFixed(2)}ms average`);
    recommendations.push('Consider optimizing URL processing logic');
  }
  
  if (metrics.errorsEncountered > metrics.totalProcessed * 0.1) {
    insights.push(`High error rate: ${((metrics.errorsEncountered / metrics.totalProcessed) * 100).toFixed(1)}%`);
    recommendations.push('Review error handling and input validation');
  }
  
  if (metrics.migrationAwareSkips > 0) {
    insights.push(`Migration-aware optimization: ${metrics.migrationAwareSkips} operations skipped during migration`);
  }
  
  if (metrics.systemStats.queueLength > 100) {
    insights.push(`Large background queue: ${metrics.systemStats.queueLength} pending tasks`);
    recommendations.push('Consider increasing background processing capacity');
  }
  
  const efficiency = metrics.totalProcessed / (metrics.totalProcessed + metrics.totalSkipped);
  if (efficiency < 0.7) {
    insights.push(`Processing efficiency: ${(efficiency * 100).toFixed(1)}%`);
    recommendations.push('Review filtering logic to reduce unnecessary processing');
  }
  
  const summary = `Processed ${metrics.totalProcessed} URLs, skipped ${metrics.totalSkipped}, ` +
                 `${metrics.errorsEncountered} errors. Cache hit rate: ${(metrics.cacheStats.cacheHitRate * 100).toFixed(1)}%`;
  
  return {
    summary,
    metrics,
    insights,
    recommendations
  };
}

/**
 * Reset metrics (useful for testing or periodic resets)
 */
export function resetMetrics(): void {
  metrics.totalProcessed = 0;
  metrics.totalSkipped = 0;
  metrics.cacheHits = 0;
  metrics.cacheMisses = 0;
  metrics.batchesProcessed = 0;
  metrics.averageProcessingTime = 0;
  metrics.errorsEncountered = 0;
  metrics.migrationAwareSkips = 0;
}

/**
 * Periodic cleanup and maintenance
 */
export function performMaintenance(): void {
  cleanupCache();
  
  // Clean up deduplication cache
  if (deduplicationCache.size > 1000) {
    deduplicationCache.clear();
  }
  
  // Log performance summary if debug is enabled
  if (process.env.NODE_ENV === 'development') {
    const report = generatePerformanceReport();
    console.log('🔧 VideoUrlFixer Performance Summary:', report.summary);
    if (report.insights.length > 0) {
      console.log('🔧 Insights:', report.insights);
    }
    if (report.recommendations.length > 0) {
      console.log('🔧 Recommendations:', report.recommendations);
    }
  }
}

/**
 * Start automatic maintenance (call once at app startup)
 */
let maintenanceInterval: NodeJS.Timeout | null = null;

export function startAutoMaintenance(intervalMs: number = CACHE_CONFIG.CLEANUP_INTERVAL): void {
  if (maintenanceInterval) {
    clearInterval(maintenanceInterval);
  }
  
  maintenanceInterval = setInterval(performMaintenance, intervalMs);
}

/**
 * Stop automatic maintenance
 */
export function stopAutoMaintenance(): void {
  if (maintenanceInterval) {
    clearInterval(maintenanceInterval);
    maintenanceInterval = null;
  }
}

/**
 * Legacy cache stats function for backward compatibility
 */
export function getCacheStats() {
  const metrics = getPerformanceMetrics();
  return {
    hasCachedUrl: !!cachedVideoBaseUrl,
    cacheAge: metrics.cacheStats.baseUrlCacheAge,
    cacheTtl: CACHE_CONFIG.BASE_URL_TTL,
    // Legacy fields
    cacheSize: metrics.cacheStats.urlMappingCacheSize,
    hitRate: metrics.cacheStats.cacheHitRate
  };
}

/**
 * Hooks integration for swarm coordination
 */
export async function initializeWithHooks(): Promise<void> {
  try {
    // Initialize hooks if available
    if (typeof window !== 'undefined' && (window as any).claudeFlow) {
      const hooks = (window as any).claudeFlow.hooks;
      if (hooks) {
        await hooks.notify({
          component: 'videoUrlFixer',
          action: 'initialized',
          message: 'VideoUrlFixer optimization system initialized'
        });
      }
    }
    
    // Start auto-maintenance
    startAutoMaintenance();
    
    // Pre-warm cache
    getCachedVideoBaseUrl();
    
    console.log('🔧 VideoUrlFixer optimization system initialized');
  } catch (error) {
    console.warn('🔧 VideoUrlFixer hooks integration failed:', error);
  }
}

/**
 * Notify hooks about performance events
 */
async function notifyHooks(event: string, data: any): Promise<void> {
  try {
    if (typeof window !== 'undefined' && (window as any).claudeFlow?.hooks) {
      const hooks = (window as any).claudeFlow.hooks;
      await hooks.notify({
        component: 'videoUrlFixer',
        action: event,
        data,
        timestamp: new Date().toISOString()
      });
    }
  } catch (error) {
    // Silently fail - hooks are optional
  }
}

/**
 * Enhanced export with all optimization features
 */
export default {
  // Core functions
  fixVideoUrl,
  fixVideoObjectUrl,
  fixMultipleVideoUrls,
  isVideoUrlValid,
  getVideoBaseUrl,
  
  // Cache management
  getCacheStats,
  clearBaseUrlCache,
  clearAllCaches,
  
  // Performance monitoring
  getPerformanceMetrics,
  generatePerformanceReport,
  resetMetrics,
  
  // Maintenance
  performMaintenance,
  startAutoMaintenance,
  stopAutoMaintenance,
  
  // Initialization
  initializeWithHooks
};

// Auto-initialize if in browser environment
if (typeof window !== 'undefined') {
  // Delay initialization to allow other systems to load
  setTimeout(() => {
    initializeWithHooks().catch(error => {
      console.warn('🔧 Auto-initialization failed:', error);
    });
  }, 1000);
}