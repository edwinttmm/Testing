/**
 * Offline Capabilities Manager
 * 
 * Provides offline functionality to ensure users can continue working
 * even when network connectivity is unavailable, supporting the
 * goal of achieving 85%+ error recovery rates.
 */

export interface OfflineData {
  id: string;
  type: string;
  data: unknown;
  timestamp: number;
  synced: boolean;
  priority: 'low' | 'medium' | 'high' | 'critical';
  retryCount: number;
  maxRetries: number;
}

export interface SyncStatus {
  isOnline: boolean;
  lastSync: Date | null;
  pendingItems: number;
  failedItems: number;
  syncInProgress: boolean;
}

export enum OfflineCapability {
  VIEW_DATA = 'view_data',
  CREATE_DRAFT = 'create_draft',
  EDIT_EXISTING = 'edit_existing',
  CACHE_RESOURCES = 'cache_resources',
  QUEUE_ACTIONS = 'queue_actions',
  BASIC_NAVIGATION = 'basic_navigation'
}

class OfflineCapabilitiesManager {
  private readonly STORAGE_PREFIX = 'offline_';
  private readonly SYNC_QUEUE_KEY = 'sync_queue';
  private readonly CACHE_KEY = 'cached_data';
  private readonly SETTINGS_KEY = 'offline_settings';
  
  private isOnline: boolean = navigator.onLine;
  private syncInProgress: boolean = false;
  private syncQueue: OfflineData[] = [];
  private cachedData: Map<string, unknown> = new Map();
  private listeners: Array<(status: SyncStatus) => void> = [];
  
  constructor() {
    this.initializeOfflineCapabilities();
    this.setupNetworkListeners();
    this.loadPersistedData();
  }

  private initializeOfflineCapabilities() {
    // Register service worker for offline caching
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js')
        .then(registration => {
          console.log('ServiceWorker registered:', registration);
        })
        .catch(error => {
          console.warn('ServiceWorker registration failed:', error);
        });
    }

    // Enable offline storage
    this.enableOfflineStorage();
  }

  private setupNetworkListeners() {
    window.addEventListener('online', () => {
      this.isOnline = true;
      this.notifyListeners();
      this.processSyncQueue();
    });

    window.addEventListener('offline', () => {
      this.isOnline = false;
      this.notifyListeners();
    });

    // Periodic connectivity check
    setInterval(() => {
      this.checkConnectivity();
    }, 30000); // Check every 30 seconds
  }

  private async checkConnectivity() {
    try {
      const response = await fetch('/api/ping', {
        method: 'HEAD',
        cache: 'no-cache',
        signal: AbortSignal.timeout(5000)
      });
      
      const wasOnline = this.isOnline;
      this.isOnline = response.ok;
      
      if (!wasOnline && this.isOnline) {
        this.notifyListeners();
        this.processSyncQueue();
      } else if (wasOnline && !this.isOnline) {
        this.notifyListeners();
      }
    } catch {
      if (this.isOnline) {
        this.isOnline = false;
        this.notifyListeners();
      }
    }
  }

  private loadPersistedData() {
    try {
      // Load sync queue
      const queueData = localStorage.getItem(this.STORAGE_PREFIX + this.SYNC_QUEUE_KEY);
      if (queueData) {
        this.syncQueue = JSON.parse(queueData);
      }

      // Load cached data
      const cacheData = localStorage.getItem(this.STORAGE_PREFIX + this.CACHE_KEY);
      if (cacheData) {
        const parsed = JSON.parse(cacheData);
        this.cachedData = new Map(Object.entries(parsed));
      }
    } catch (error) {
      console.warn('Failed to load persisted offline data:', error);
    }
  }

  private persistData() {
    try {
      // Persist sync queue
      localStorage.setItem(
        this.STORAGE_PREFIX + this.SYNC_QUEUE_KEY,
        JSON.stringify(this.syncQueue)
      );

      // Persist cached data
      const cacheObject = Object.fromEntries(this.cachedData.entries());
      localStorage.setItem(
        this.STORAGE_PREFIX + this.CACHE_KEY,
        JSON.stringify(cacheObject)
      );
    } catch (error) {
      console.warn('Failed to persist offline data:', error);
    }
  }

  /**
   * Check if the application is currently online
   */
  public isApplicationOnline(): boolean {
    return this.isOnline;
  }

  /**
   * Get current sync status
   */
  public getSyncStatus(): SyncStatus {
    const pendingItems = this.syncQueue.filter(item => !item.synced).length;
    const failedItems = this.syncQueue.filter(item => item.retryCount >= item.maxRetries).length;

    return {
      isOnline: this.isOnline,
      lastSync: this.getLastSyncTime(),
      pendingItems,
      failedItems,
      syncInProgress: this.syncInProgress,
    };
  }

  /**
   * Add data to offline cache
   */
  public cacheData(key: string, data: unknown, expiry?: number): void {
    const cacheEntry = {
      data,
      timestamp: Date.now(),
      expiry: expiry ? Date.now() + expiry : null,
    };

    this.cachedData.set(key, cacheEntry);
    this.persistData();
  }

  /**
   * Retrieve data from offline cache
   */
  public getCachedData<T>(key: string): T | null {
    const entry = this.cachedData.get(key);
    if (!entry) return null;

    // Check expiry with proper type checking
    if (entry && typeof entry === 'object' && 'expiry' in entry && entry.expiry && Date.now() > entry.expiry) {
      this.cachedData.delete(key);
      this.persistData();
      return null;
    }

    return entry && typeof entry === 'object' && 'data' in entry ? (entry as any).data : null;
  }

  /**
   * Queue an action for synchronization when online
   */
  public queueForSync(
    type: string,
    data: any,
    priority: 'low' | 'medium' | 'high' | 'critical' = 'medium'
  ): string {
    const id = `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const offlineData: OfflineData = {
      id,
      type,
      data,
      timestamp: Date.now(),
      synced: false,
      priority,
      retryCount: 0,
      maxRetries: priority === 'critical' ? 5 : priority === 'high' ? 3 : 2,
    };

    this.syncQueue.push(offlineData);
    this.persistData();
    this.notifyListeners();

    // If online, try to sync immediately
    if (this.isOnline && !this.syncInProgress) {
      this.processSyncQueue();
    }

    return id;
  }

  /**
   * Process the sync queue when online
   */
  public async processSyncQueue(): Promise<void> {
    if (!this.isOnline || this.syncInProgress) {
      return;
    }

    this.syncInProgress = true;
    this.notifyListeners();

    try {
      // Sort by priority and timestamp
      const itemsToSync = this.syncQueue
        .filter(item => !item.synced && item.retryCount < item.maxRetries)
        .sort((a, b) => {
          const priorityOrder = { critical: 4, high: 3, medium: 2, low: 1 };
          const aPriority = priorityOrder[a.priority];
          const bPriority = priorityOrder[b.priority];
          
          if (aPriority !== bPriority) {
            return bPriority - aPriority;
          }
          
          return a.timestamp - b.timestamp;
        });

      for (const item of itemsToSync) {
        try {
          await this.syncItem(item);
          item.synced = true;
        } catch (error) {
          item.retryCount++;
          console.warn(`Sync failed for ${item.id} (attempt ${item.retryCount}):`, error);
          
          // If max retries reached, mark as failed
          if (item.retryCount >= item.maxRetries) {
            console.error(`Max retries reached for ${item.id}, giving up`);
          }
        }
      }

      // Clean up synced items older than 24 hours
      const cutoffTime = Date.now() - (24 * 60 * 60 * 1000);
      this.syncQueue = this.syncQueue.filter(
        item => !item.synced || item.timestamp > cutoffTime
      );

      this.persistData();
    } finally {
      this.syncInProgress = false;
      this.notifyListeners();
    }
  }

  private async syncItem(item: OfflineData): Promise<void> {
    switch (item.type) {
      case 'create_project':
        await this.syncCreateProject(item.data);
        break;
      case 'update_project':
        await this.syncUpdateProject(item.data);
        break;
      case 'delete_project':
        await this.syncDeleteProject(item.data);
        break;
      case 'create_dataset':
        await this.syncCreateDataset(item.data);
        break;
      case 'upload_video':
        await this.syncUploadVideo(item.data);
        break;
      case 'save_annotation':
        await this.syncSaveAnnotation(item.data);
        break;
      case 'run_detection':
        await this.syncRunDetection(item.data);
        break;
      default:
        throw new Error(`Unknown sync type: ${item.type}`);
    }
  }

  // Sync implementations for different data types
  private async syncCreateProject(data: any): Promise<void> {
    const response = await fetch('/api/projects', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error(`Failed to create project: ${response.statusText}`);
    }

    // Update cached data with server response
    const result = await response.json();
    this.cacheData(`project_${result.id}`, result);
  }

  private async syncUpdateProject(data: any): Promise<void> {
    const response = await fetch(`/api/projects/${data.id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error(`Failed to update project: ${response.statusText}`);
    }

    const result = await response.json();
    this.cacheData(`project_${result.id}`, result);
  }

  private async syncDeleteProject(data: any): Promise<void> {
    const response = await fetch(`/api/projects/${data.id}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error(`Failed to delete project: ${response.statusText}`);
    }

    // Remove from cache
    this.cachedData.delete(`project_${data.id}`);
    this.persistData();
  }

  private async syncCreateDataset(data: any): Promise<void> {
    // Note: /api/datasets endpoint not implemented in backend
    // Using projects API instead for dataset functionality
    console.log('syncCreateDataset called but /api/datasets not available - using projects API');
    throw new Error('Dataset creation not implemented - use projects API instead');
  }

  private async syncUploadVideo(data: any): Promise<void> {
    const formData = new FormData();
    formData.append('file', data.file);
    formData.append('datasetId', data.datasetId);

    const response = await fetch('/api/videos/upload', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Failed to upload video: ${response.statusText}`);
    }

    const result = await response.json();
    this.cacheData(`video_${result.id}`, result);
  }

  private async syncSaveAnnotation(data: any): Promise<void> {
    const response = await fetch('/api/annotations', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error(`Failed to save annotation: ${response.statusText}`);
    }

    const result = await response.json();
    this.cacheData(`annotation_${result.id}`, result);
  }

  private async syncRunDetection(data: any): Promise<void> {
    const response = await fetch('/api/detections/run', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error(`Failed to run detection: ${response.statusText}`);
    }

    const result = await response.json();
    this.cacheData(`detection_${result.id}`, result);
  }

  /**
   * Enable offline functionality for a specific capability
   */
  public enableOfflineCapability(capability: OfflineCapability): void {
    const settings = this.getOfflineSettings();
    settings.enabledCapabilities = settings.enabledCapabilities || [];
    
    if (!settings.enabledCapabilities.includes(capability)) {
      settings.enabledCapabilities.push(capability);
      this.saveOfflineSettings(settings);
    }
  }

  /**
   * Check if a specific offline capability is enabled
   */
  public isOfflineCapabilityEnabled(capability: OfflineCapability): boolean {
    const settings = this.getOfflineSettings();
    return settings.enabledCapabilities?.includes(capability) || false;
  }

  /**
   * Get offline-capable operations for current state
   */
  public getAvailableOfflineOperations(): string[] {
    const operations = [];

    if (this.isOfflineCapabilityEnabled(OfflineCapability.VIEW_DATA)) {
      operations.push('View cached projects and datasets');
    }

    if (this.isOfflineCapabilityEnabled(OfflineCapability.CREATE_DRAFT)) {
      operations.push('Create draft projects and annotations');
    }

    if (this.isOfflineCapabilityEnabled(OfflineCapability.EDIT_EXISTING)) {
      operations.push('Edit cached data (syncs when online)');
    }

    if (this.isOfflineCapabilityEnabled(OfflineCapability.BASIC_NAVIGATION)) {
      operations.push('Navigate between cached pages');
    }

    return operations;
  }

  /**
   * Prepare for offline mode by preloading essential data
   */
  public async prepareForOffline(): Promise<void> {
    if (!this.isOnline) return;

    try {
      // Cache essential data
      await this.cacheEssentialData();
      
      // Enable all offline capabilities
      Object.values(OfflineCapability).forEach(capability => {
        this.enableOfflineCapability(capability);
      });

      console.log('Offline mode preparation completed');
    } catch (error) {
      console.warn('Failed to prepare for offline mode:', error);
    }
  }

  private async cacheEssentialData(): Promise<void> {
    // Cache projects
    try {
      const projectsResponse = await fetch('/api/projects');
      if (projectsResponse.ok) {
        const projects = await projectsResponse.json();
        projects.forEach((project: any) => {
          this.cacheData(`project_${project.id}`, project, 7 * 24 * 60 * 60 * 1000); // 7 days
        });
      }
    } catch (error) {
      console.warn('Failed to cache projects:', error);
    }

    // Cache datasets - skip for now since backend doesn't have /api/datasets endpoint
    try {
      // Note: /api/datasets endpoint not implemented in backend
      // Using projects and test sessions instead
      console.log('Dataset caching skipped - using projects and test sessions');
    } catch (error) {
      console.warn('Failed to cache datasets:', error);
    }
  }

  /**
   * Register a listener for sync status changes
   */
  public onSyncStatusChange(listener: (status: SyncStatus) => void): void {
    this.listeners.push(listener);
  }

  /**
   * Remove a sync status listener
   */
  public offSyncStatusChange(listener: (status: SyncStatus) => void): void {
    const index = this.listeners.indexOf(listener);
    if (index > -1) {
      this.listeners.splice(index, 1);
    }
  }

  private notifyListeners(): void {
    const status = this.getSyncStatus();
    this.listeners.forEach(listener => {
      try {
        listener(status);
      } catch (error) {
        console.warn('Sync status listener error:', error);
      }
    });
  }

  private getLastSyncTime(): Date | null {
    const lastSyncedItem = this.syncQueue
      .filter(item => item.synced)
      .sort((a, b) => b.timestamp - a.timestamp)[0];
    
    return lastSyncedItem ? new Date(lastSyncedItem.timestamp) : null;
  }

  private enableOfflineStorage(): void {
    // Request persistent storage
    if ('storage' in navigator && 'persist' in navigator.storage) {
      navigator.storage.persist().then(persistent => {
        console.log(`Persistent storage: ${persistent}`);
      });
    }
  }

  private getOfflineSettings(): any {
    try {
      const settings = localStorage.getItem(this.STORAGE_PREFIX + this.SETTINGS_KEY);
      return settings ? JSON.parse(settings) : {};
    } catch {
      return {};
    }
  }

  private saveOfflineSettings(settings: any): void {
    try {
      localStorage.setItem(
        this.STORAGE_PREFIX + this.SETTINGS_KEY,
        JSON.stringify(settings)
      );
    } catch (error) {
      console.warn('Failed to save offline settings:', error);
    }
  }

  /**
   * Clear all offline data
   */
  public clearOfflineData(): void {
    this.syncQueue = [];
    this.cachedData.clear();
    
    // Clear from localStorage
    Object.keys(localStorage).forEach(key => {
      if (key.startsWith(this.STORAGE_PREFIX)) {
        localStorage.removeItem(key);
      }
    });

    this.notifyListeners();
  }

  /**
   * Get storage usage statistics
   */
  public getStorageStats(): {
    totalSize: number;
    cacheSize: number;
    queueSize: number;
    itemCount: number;
  } {
    const cacheData = JSON.stringify(Object.fromEntries(this.cachedData.entries()));
    const queueData = JSON.stringify(this.syncQueue);
    
    return {
      totalSize: cacheData.length + queueData.length,
      cacheSize: cacheData.length,
      queueSize: queueData.length,
      itemCount: this.cachedData.size + this.syncQueue.length,
    };
  }
}

// Singleton instance
const offlineCapabilities = new OfflineCapabilitiesManager();

export default offlineCapabilities;