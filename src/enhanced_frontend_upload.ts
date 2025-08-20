/**
 * Enhanced Frontend Upload Service with Chunked Upload Support
 * Provides robust file upload handling with progress tracking, error recovery,
 * and support for large files through chunked uploads.
 */

import axios, { AxiosProgressEvent, CancelToken } from 'axios';

export interface UploadConfig {
  chunkSize: number;
  maxConcurrentChunks: number;
  maxRetries: number;
  retryDelay: number;
  enableCompression: boolean;
  enableHashValidation: boolean;
  hashAlgorithm: 'md5' | 'sha256';
}

export interface UploadSession {
  uploadId: string;
  filename: string;
  totalSize: number;
  chunkSize: number;
  totalChunks: number;
  uploadedChunks: Set<number>;
  failedChunks: Map<number, number>; // chunk number -> retry count
  status: 'initiated' | 'uploading' | 'completed' | 'failed' | 'cancelled';
  progressPercentage: number;
  uploadSpeed: number;
  estimatedTimeRemaining: number;
  startTime: number;
  cancelToken?: CancelToken;
}

export interface UploadProgress {
  uploadId: string;
  progressPercentage: number;
  uploadedSize: number;
  totalSize: number;
  uploadSpeed: number;
  estimatedTimeRemaining: number;
  completedChunks: number;
  totalChunks: number;
  status: string;
}

export interface ChunkUploadResult {
  success: boolean;
  chunkNumber: number;
  uploadedSize: number;
  totalSize: number;
  progressPercentage: number;
  uploadComplete: boolean;
  error?: string;
}

export class EnhancedUploadClient {
  private baseUrl: string;
  private activeSessions = new Map<string, UploadSession>();
  private progressCallbacks = new Map<string, Array<(progress: UploadProgress) => void>>();
  private config: UploadConfig;
  private webSocket?: WebSocket;

  constructor(baseUrl: string = '/api/uploads', config?: Partial<UploadConfig>) {
    this.baseUrl = baseUrl;
    this.config = {
      chunkSize: 5 * 1024 * 1024, // 5MB
      maxConcurrentChunks: 3,
      maxRetries: 3,
      retryDelay: 1000,
      enableCompression: false,
      enableHashValidation: true,
      hashAlgorithm: 'md5',
      ...config
    };
  }

  /**
   * Upload a file with automatic chunking for large files
   */
  async uploadFile(
    file: File,
    projectId?: string,
    onProgress?: (progress: UploadProgress) => void
  ): Promise<string> {
    // For small files, use direct upload
    if (file.size <= this.config.chunkSize) {
      return this.uploadSmallFile(file, projectId, onProgress);
    }

    // For large files, use chunked upload
    return this.uploadLargeFile(file, projectId, onProgress);
  }

  /**
   * Upload small file directly
   */
  private async uploadSmallFile(
    file: File,
    projectId?: string,
    onProgress?: (progress: UploadProgress) => void
  ): Promise<string> {
    const formData = new FormData();
    formData.append('file', file);
    if (projectId) formData.append('project_id', projectId);

    try {
      const response = await axios.post(`${this.baseUrl}/legacy/video`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent: AxiosProgressEvent) => {
          if (onProgress && progressEvent.total) {
            const progress: UploadProgress = {
              uploadId: 'direct-upload',
              progressPercentage: (progressEvent.loaded / progressEvent.total) * 100,
              uploadedSize: progressEvent.loaded,
              totalSize: progressEvent.total,
              uploadSpeed: this.calculateSpeed(progressEvent.loaded, Date.now()),
              estimatedTimeRemaining: 0,
              completedChunks: 1,
              totalChunks: 1,
              status: 'uploading'
            };
            onProgress(progress);
          }
        },
      });

      return response.data.id;
    } catch (error) {
      console.error('Small file upload failed:', error);
      throw this.handleUploadError(error);
    }
  }

  /**
   * Upload large file using chunked upload
   */
  private async uploadLargeFile(
    file: File,
    projectId?: string,
    onProgress?: (progress: UploadProgress) => void
  ): Promise<string> {
    try {
      // Step 1: Initiate chunked upload
      const session = await this.initiateChunkedUpload(file);
      
      // Step 2: Register progress callback
      if (onProgress) {
        this.addProgressCallback(session.uploadId, onProgress);
      }

      // Step 3: Upload chunks concurrently
      await this.uploadChunks(file, session);

      // Step 4: Wait for completion
      await this.waitForCompletion(session.uploadId);

      return session.uploadId;

    } catch (error) {
      console.error('Large file upload failed:', error);
      throw this.handleUploadError(error);
    }
  }

  /**
   * Initiate chunked upload session
   */
  private async initiateChunkedUpload(file: File): Promise<UploadSession> {
    const response = await axios.post(`${this.baseUrl}/initiate`, {
      filename: file.name,
      file_size: file.size,
      content_type: file.type,
      metadata: {
        lastModified: file.lastModified,
        originalSize: file.size
      }
    });

    const { upload_id, chunk_size, total_chunks } = response.data.data;
    
    const session: UploadSession = {
      uploadId: upload_id,
      filename: file.name,
      totalSize: file.size,
      chunkSize: chunk_size,
      totalChunks: total_chunks,
      uploadedChunks: new Set(),
      failedChunks: new Map(),
      status: 'initiated',
      progressPercentage: 0,
      uploadSpeed: 0,
      estimatedTimeRemaining: 0,
      startTime: Date.now(),
      cancelToken: axios.CancelToken.source().token
    };

    this.activeSessions.set(upload_id, session);
    return session;
  }

  /**
   * Upload file chunks concurrently
   */
  private async uploadChunks(file: File, session: UploadSession): Promise<void> {
    session.status = 'uploading';
    
    const semaphore = new Semaphore(this.config.maxConcurrentChunks);
    const uploadPromises: Promise<void>[] = [];

    for (let chunkNumber = 0; chunkNumber < session.totalChunks; chunkNumber++) {
      const uploadPromise = semaphore.acquire().then(async () => {
        try {
          await this.uploadSingleChunk(file, session, chunkNumber);
        } finally {
          semaphore.release();
        }
      });

      uploadPromises.push(uploadPromise);
    }

    await Promise.all(uploadPromises);
  }

  /**
   * Upload a single chunk with retry logic
   */
  private async uploadSingleChunk(
    file: File, 
    session: UploadSession, 
    chunkNumber: number
  ): Promise<void> {
    const maxRetries = this.config.maxRetries;
    let retryCount = 0;

    while (retryCount <= maxRetries) {
      try {
        const chunkData = await this.extractChunk(file, chunkNumber, session.chunkSize);
        const chunkHash = this.config.enableHashValidation 
          ? await this.calculateHash(chunkData, this.config.hashAlgorithm)
          : undefined;

        const formData = new FormData();
        formData.append('upload_id', session.uploadId);
        formData.append('chunk_number', chunkNumber.toString());
        formData.append('chunk_file', new Blob([chunkData]), `chunk_${chunkNumber}`);
        if (chunkHash) {
          formData.append('chunk_hash', chunkHash);
          formData.append('hash_algorithm', this.config.hashAlgorithm);
        }

        const response = await axios.post(`${this.baseUrl}/chunk`, formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          cancelToken: session.cancelToken,
          timeout: 60000 // 1 minute timeout per chunk
        });

        // Mark chunk as uploaded
        session.uploadedChunks.add(chunkNumber);
        session.failedChunks.delete(chunkNumber);
        
        // Update progress
        this.updateProgress(session);

        console.debug(`Chunk ${chunkNumber} uploaded successfully for ${session.uploadId}`);
        return;

      } catch (error) {
        retryCount++;
        console.warn(`Chunk ${chunkNumber} upload attempt ${retryCount} failed:`, error);

        if (retryCount <= maxRetries) {
          // Exponential backoff
          const delay = this.config.retryDelay * Math.pow(2, retryCount - 1);
          await this.sleep(delay);
        } else {
          // Mark chunk as failed
          session.failedChunks.set(chunkNumber, retryCount);
          throw new Error(`Chunk ${chunkNumber} failed after ${maxRetries} retries`);
        }
      }
    }
  }

  /**
   * Extract chunk data from file
   */
  private async extractChunk(file: File, chunkNumber: number, chunkSize: number): Promise<ArrayBuffer> {
    const start = chunkNumber * chunkSize;
    const end = Math.min(start + chunkSize, file.size);
    const chunk = file.slice(start, end);
    return chunk.arrayBuffer();
  }

  /**
   * Calculate hash of chunk data
   */
  private async calculateHash(data: ArrayBuffer, algorithm: 'md5' | 'sha256'): Promise<string> {
    const hashBuffer = await crypto.subtle.digest(
      algorithm === 'md5' ? 'SHA-1' : 'SHA-256', // Note: Web Crypto API doesn't support MD5
      data
    );
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  }

  /**
   * Update upload progress and notify callbacks
   */
  private updateProgress(session: UploadSession): void {
    const uploadedSize = session.uploadedChunks.size * session.chunkSize;
    const progressPercentage = (uploadedSize / session.totalSize) * 100;
    
    // Calculate upload speed
    const elapsedTime = (Date.now() - session.startTime) / 1000; // seconds
    const uploadSpeed = elapsedTime > 0 ? uploadedSize / elapsedTime : 0;
    
    // Estimate time remaining
    const remainingSize = session.totalSize - uploadedSize;
    const estimatedTimeRemaining = uploadSpeed > 0 ? remainingSize / uploadSpeed : 0;

    session.progressPercentage = progressPercentage;
    session.uploadSpeed = uploadSpeed;
    session.estimatedTimeRemaining = estimatedTimeRemaining;

    // Notify progress callbacks
    const callbacks = this.progressCallbacks.get(session.uploadId);
    if (callbacks) {
      const progress: UploadProgress = {
        uploadId: session.uploadId,
        progressPercentage,
        uploadedSize,
        totalSize: session.totalSize,
        uploadSpeed,
        estimatedTimeRemaining,
        completedChunks: session.uploadedChunks.size,
        totalChunks: session.totalChunks,
        status: session.status
      };

      callbacks.forEach(callback => {
        try {
          callback(progress);
        } catch (error) {
          console.error('Progress callback error:', error);
        }
      });
    }
  }

  /**
   * Wait for upload completion
   */
  private async waitForCompletion(uploadId: string, maxWaitTime = 300000): Promise<void> {
    const startTime = Date.now();
    
    while (Date.now() - startTime < maxWaitTime) {
      try {
        const response = await axios.get(`${this.baseUrl}/status/${uploadId}`);
        const status = response.data.status;

        if (status === 'completed') {
          const session = this.activeSessions.get(uploadId);
          if (session) {
            session.status = 'completed';
            this.updateProgress(session);
          }
          return;
        } else if (status === 'failed') {
          throw new Error('Upload failed on server');
        }

        await this.sleep(1000); // Check every second
      } catch (error) {
        console.error('Error checking upload status:', error);
        await this.sleep(2000); // Wait longer on error
      }
    }

    throw new Error('Upload completion timeout');
  }

  /**
   * Cancel an active upload
   */
  async cancelUpload(uploadId: string): Promise<boolean> {
    try {
      const session = this.activeSessions.get(uploadId);
      if (session?.cancelToken) {
        // Cancel ongoing requests
        axios.cancel('Upload cancelled by user');
      }

      // Cancel on server
      await axios.delete(`${this.baseUrl}/cancel/${uploadId}`);

      // Update local state
      if (session) {
        session.status = 'cancelled';
        this.updateProgress(session);
      }

      this.cleanupSession(uploadId);
      return true;

    } catch (error) {
      console.error('Error cancelling upload:', error);
      return false;
    }
  }

  /**
   * Retry failed chunks
   */
  async retryFailedChunks(uploadId: string): Promise<boolean> {
    try {
      const session = this.activeSessions.get(uploadId);
      if (!session) {
        throw new Error('Upload session not found');
      }

      // Reset failed chunks on server
      await axios.post(`${this.baseUrl}/retry/${uploadId}`);

      // Retry locally
      const file = await this.getFileFromSession(session);
      for (const [chunkNumber] of session.failedChunks) {
        session.failedChunks.delete(chunkNumber);
        await this.uploadSingleChunk(file, session, chunkNumber);
      }

      return true;

    } catch (error) {
      console.error('Error retrying failed chunks:', error);
      return false;
    }
  }

  /**
   * Get upload progress for a session
   */
  async getUploadProgress(uploadId: string): Promise<UploadProgress | null> {
    try {
      const response = await axios.get(`${this.baseUrl}/progress/${uploadId}`);
      return response.data;
    } catch (error) {
      console.error('Error getting upload progress:', error);
      return null;
    }
  }

  /**
   * Add progress callback
   */
  addProgressCallback(uploadId: string, callback: (progress: UploadProgress) => void): void {
    if (!this.progressCallbacks.has(uploadId)) {
      this.progressCallbacks.set(uploadId, []);
    }
    this.progressCallbacks.get(uploadId)!.push(callback);
  }

  /**
   * Remove progress callback
   */
  removeProgressCallback(uploadId: string, callback: (progress: UploadProgress) => void): void {
    const callbacks = this.progressCallbacks.get(uploadId);
    if (callbacks) {
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
      if (callbacks.length === 0) {
        this.progressCallbacks.delete(uploadId);
      }
    }
  }

  /**
   * Connect to WebSocket for real-time progress updates
   */
  connectWebSocket(uploadId: string): WebSocket {
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/upload/${uploadId}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'status_update' || message.type === 'initial_status') {
          const session = this.activeSessions.get(uploadId);
          if (session) {
            this.updateProgressFromServer(session, message.data);
          }
        }
      } catch (error) {
        console.error('WebSocket message parsing error:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.info(`WebSocket connection closed for upload ${uploadId}`);
    };

    return ws;
  }

  /**
   * Update progress from server data
   */
  private updateProgressFromServer(session: UploadSession, serverData: any): void {
    session.progressPercentage = serverData.progress_percentage;
    session.uploadSpeed = serverData.upload_speed_bps || 0;
    session.status = serverData.status;

    this.updateProgress(session);
  }

  /**
   * Cleanup session data
   */
  private cleanupSession(uploadId: string): void {
    this.activeSessions.delete(uploadId);
    this.progressCallbacks.delete(uploadId);
  }

  /**
   * Handle upload errors with user-friendly messages
   */
  private handleUploadError(error: any): Error {
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data;
      
      switch (status) {
        case 413:
          return new Error('File too large. Please select a smaller file.');
        case 400:
          return new Error(data.detail || 'Invalid file format or request.');
        case 500:
          return new Error('Server error. Please try again later.');
        case 408:
          return new Error('Upload timeout. Please check your connection and try again.');
        default:
          return new Error(`Upload failed: ${data.detail || error.message}`);
      }
    } else if (error.request) {
      return new Error('Network error. Please check your internet connection.');
    } else {
      return new Error(`Upload error: ${error.message}`);
    }
  }

  /**
   * Utility method to calculate upload speed
   */
  private calculateSpeed(loaded: number, timestamp: number): number {
    const elapsed = (timestamp - Date.now()) / 1000;
    return elapsed > 0 ? loaded / elapsed : 0;
  }

  /**
   * Utility method for sleep
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Get file object from session (placeholder for actual implementation)
   */
  private async getFileFromSession(session: UploadSession): Promise<File> {
    // In a real implementation, you might need to store file references
    // or reconstruct the file from chunks
    throw new Error('File retrieval from session not implemented');
  }
}

/**
 * Semaphore for controlling concurrent operations
 */
class Semaphore {
  private permits: number;
  private waiting: Array<() => void> = [];

  constructor(permits: number) {
    this.permits = permits;
  }

  async acquire(): Promise<void> {
    if (this.permits > 0) {
      this.permits--;
      return Promise.resolve();
    } else {
      return new Promise<void>((resolve) => {
        this.waiting.push(resolve);
      });
    }
  }

  release(): void {
    this.permits++;
    if (this.waiting.length > 0) {
      const next = this.waiting.shift()!;
      this.permits--;
      next();
    }
  }
}

/**
 * React Hook for enhanced uploads
 */
export function useEnhancedUpload(baseUrl?: string, config?: Partial<UploadConfig>) {
  const client = new EnhancedUploadClient(baseUrl, config);

  return {
    uploadFile: client.uploadFile.bind(client),
    cancelUpload: client.cancelUpload.bind(client),
    retryFailedChunks: client.retryFailedChunks.bind(client),
    getUploadProgress: client.getUploadProgress.bind(client),
    addProgressCallback: client.addProgressCallback.bind(client),
    removeProgressCallback: client.removeProgressCallback.bind(client),
    connectWebSocket: client.connectWebSocket.bind(client)
  };
}

export default EnhancedUploadClient;