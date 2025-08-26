/**
 * Video Enhancement Cache
 * 
 * Provides intelligent caching for video URL enhancements with:
 * - LRU eviction policy
 * - Memory-based storage with TTL
 * - Performance metrics
 * - Duplicate prevention
 */

import { VideoFile } from '../services/types';

interface CacheEntry {
  value: VideoFile;
  timestamp: number;
  accessCount: number;
  lastAccessed: number;
}

interface CacheStats {
  size: number;
  maxSize: number;
  hits: number;
  misses: number;
  hitRate: number;
  totalRequests: number;
  evictions: number;
  averageAccessTime: number;
  oldestEntry: number;
}

export class VideoEnhancementCache {
  private cache = new Map<string, CacheEntry>();
  private maxSize: number;
  private ttl: number; // Time to live in milliseconds
  private stats = {
    hits: 0,
    misses: 0,
    evictions: 0,
    totalAccessTime: 0,
    totalRequests: 0
  };

  constructor(maxSize = 1000, ttl = 5 * 60 * 1000) { // 5 minutes default TTL
    this.maxSize = maxSize;
    this.ttl = ttl;
  }

  /**
   * Get a cached video enhancement
   */
  get(videoId: string): VideoFile | null {
    const start = performance.now();
    this.stats.totalRequests++;

    const entry = this.cache.get(videoId);
    if (!entry) {
      this.stats.misses++;
      this.stats.totalAccessTime += performance.now() - start;
      return null;
    }

    // Check if entry has expired
    if (Date.now() - entry.timestamp > this.ttl) {
      this.cache.delete(videoId);
      this.stats.misses++;
      this.stats.totalAccessTime += performance.now() - start;
      return null;
    }

    // Update access statistics
    entry.accessCount++;
    entry.lastAccessed = Date.now();
    this.stats.hits++;
    this.stats.totalAccessTime += performance.now() - start;

    // Move to end (most recently used) - for Map this happens automatically
    this.cache.delete(videoId);
    this.cache.set(videoId, entry);

    return { ...entry.value }; // Return a copy to prevent mutation
  }

  /**
   * Cache a video enhancement
   */
  set(videoId: string, video: VideoFile): void {
    // Remove old entry if it exists
    this.cache.delete(videoId);

    // If cache is at capacity, remove least recently used entry
    if (this.cache.size >= this.maxSize) {
      this.evictLRU();
    }

    // Add new entry
    const entry: CacheEntry = {
      value: { ...video }, // Store a copy to prevent mutation
      timestamp: Date.now(),
      accessCount: 1,
      lastAccessed: Date.now()
    };

    this.cache.set(videoId, entry);
  }

  /**
   * Remove a specific video from cache
   */
  delete(videoId: string): boolean {
    return this.cache.delete(videoId);
  }

  /**
   * Clear all cached entries
   */
  clear(): void {
    this.cache.clear();
    this.resetStats();
  }

  /**
   * Check if video is cached
   */
  has(videoId: string): boolean {
    const entry = this.cache.get(videoId);
    if (!entry) return false;

    // Check if expired
    if (Date.now() - entry.timestamp > this.ttl) {
      this.cache.delete(videoId);
      return false;
    }

    return true;
  }

  /**
   * Get cache statistics
   */
  getStats(): CacheStats {
    const oldestEntry = Math.min(
      ...[...this.cache.values()].map(entry => entry.timestamp)
    );

    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      hits: this.stats.hits,
      misses: this.stats.misses,
      hitRate: this.stats.totalRequests > 0 ? 
        (this.stats.hits / this.stats.totalRequests) * 100 : 0,
      totalRequests: this.stats.totalRequests,
      evictions: this.stats.evictions,
      averageAccessTime: this.stats.totalRequests > 0 ? 
        this.stats.totalAccessTime / this.stats.totalRequests : 0,
      oldestEntry: this.cache.size > 0 ? Date.now() - oldestEntry : 0
    };
  }

  /**
   * Clean up expired entries
   */
  cleanup(): number {
    const now = Date.now();
    let removed = 0;

    for (const [videoId, entry] of this.cache) {
      if (now - entry.timestamp > this.ttl) {
        this.cache.delete(videoId);
        removed++;
      }
    }

    return removed;
  }

  /**
   * Update cache configuration
   */
  configure(options: { maxSize?: number; ttl?: number }): void {
    if (options.maxSize !== undefined) {
      this.maxSize = options.maxSize;
      // If new max size is smaller, evict entries
      while (this.cache.size > this.maxSize) {
        this.evictLRU();
      }
    }
    if (options.ttl !== undefined) {
      this.ttl = options.ttl;
      this.cleanup(); // Remove entries that are now expired
    }
  }

  /**
   * Get all cached video IDs
   */
  getKeys(): string[] {
    this.cleanup(); // Remove expired entries first
    return [...this.cache.keys()];
  }

  /**
   * Evict least recently used entry
   */
  private evictLRU(): void {
    const firstKey = this.cache.keys().next().value;
    if (firstKey !== undefined) {
      this.cache.delete(firstKey);
      this.stats.evictions++;
    }
  }

  /**
   * Reset statistics
   */
  private resetStats(): void {
    this.stats = {
      hits: 0,
      misses: 0,
      evictions: 0,
      totalAccessTime: 0,
      totalRequests: 0
    };
  }
}

// Export singleton instance for global use
export const videoEnhancementCache = new VideoEnhancementCache();

export default VideoEnhancementCache;