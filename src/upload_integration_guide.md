# Video Upload Integration Guide

## Overview
This guide explains how to integrate the enhanced video upload system with chunked upload support, progress tracking, and robust error handling into the AI Model Validation Platform.

## Architecture Components

### 1. Backend Components
- **EnhancedUploadService** (`enhanced_upload_service.py`): Core chunked upload service
- **Upload Middleware** (`upload_middleware.py`): FastAPI integration with endpoints
- **Legacy Compatibility**: Maintains backward compatibility with existing upload endpoints

### 2. Frontend Components
- **EnhancedUploadClient** (`enhanced_frontend_upload.ts`): TypeScript client for chunked uploads
- **React Hook**: `useEnhancedUpload` for easy React integration
- **WebSocket Support**: Real-time progress updates

## Integration Steps

### Step 1: Backend Integration

1. **Install Dependencies**
```bash
pip install aiofiles uvloop websockets
```

2. **Update main.py**
```python
from src.upload_middleware import create_upload_router, create_websocket_router
from src.enhanced_upload_service import EnhancedUploadService, UploadConfiguration

# Configure upload service
upload_config = UploadConfiguration(
    max_file_size=500 * 1024 * 1024,  # 500MB
    chunk_size=5 * 1024 * 1024,      # 5MB chunks
    max_concurrent_chunks=3,
    upload_timeout=3600,              # 1 hour
    enable_integrity_check=True,
    temp_directory="temp_uploads",
    final_directory="uploads"
)

# Add routers
app.include_router(create_upload_router())
app.include_router(create_websocket_router())
```

3. **Update existing upload endpoints to support both legacy and chunked uploads**
```python
@app.post("/api/videos", response_model=VideoUploadResponse)
async def upload_video_enhanced(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(default=None),
    service: EnhancedUploadService = Depends(get_upload_service)
):
    """Enhanced upload endpoint with automatic chunking"""
    # Use enhanced upload service for large files
    if file.size > service.config.chunk_size:
        return await handle_chunked_upload(file, project_id, service)
    else:
        return await handle_direct_upload(file, project_id)
```

### Step 2: Frontend Integration

1. **Install Frontend Dependencies**
```bash
npm install axios
```

2. **Update API Service**
```typescript
import EnhancedUploadClient, { useEnhancedUpload } from './enhanced_frontend_upload';

export class ApiService {
  private uploadClient: EnhancedUploadClient;

  constructor() {
    this.uploadClient = new EnhancedUploadClient('/api/uploads', {
      chunkSize: 5 * 1024 * 1024,  // 5MB chunks
      maxConcurrentChunks: 3,
      maxRetries: 3,
      enableHashValidation: true
    });
  }

  async uploadVideo(
    projectId: string, 
    file: File, 
    onProgress?: (progress: UploadProgress) => void
  ): Promise<VideoFile> {
    try {
      const uploadId = await this.uploadClient.uploadFile(file, projectId, onProgress);
      
      // Convert to existing VideoFile format
      return {
        id: uploadId,
        projectId,
        filename: file.name,
        originalName: file.name,
        size: file.size,
        status: 'uploaded',
        createdAt: new Date().toISOString(),
        // ... other properties
      };
    } catch (error) {
      throw this.handleError(error);
    }
  }
}
```

3. **Update Upload Components**
```tsx
import React, { useState, useCallback } from 'react';
import { useEnhancedUpload, UploadProgress } from '../services/enhanced_frontend_upload';

export const VideoUploadComponent: React.FC = () => {
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [uploading, setUploading] = useState(false);
  const { uploadFile, cancelUpload } = useEnhancedUpload();

  const handleFileUpload = useCallback(async (file: File) => {
    setUploading(true);
    
    try {
      const uploadId = await uploadFile(file, undefined, (progress) => {
        setUploadProgress(progress);
      });
      
      console.log('Upload completed:', uploadId);
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setUploading(false);
    }
  }, [uploadFile]);

  return (
    <div>
      <input
        type="file"
        accept=".mp4,.avi,.mov,.mkv,.webm"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFileUpload(file);
        }}
        disabled={uploading}
      />
      
      {uploadProgress && (
        <div>
          <progress value={uploadProgress.progressPercentage} max={100} />
          <p>
            {uploadProgress.progressPercentage.toFixed(1)}% - 
            {(uploadProgress.uploadSpeed / 1024 / 1024).toFixed(2)} MB/s - 
            {Math.round(uploadProgress.estimatedTimeRemaining)}s remaining
          </p>
          <p>
            {uploadProgress.completedChunks} of {uploadProgress.totalChunks} chunks completed
          </p>
        </div>
      )}
    </div>
  );
};
```

### Step 3: Database Schema Updates

Update your database schema to support chunked uploads:

```sql
-- Add upload sessions table
CREATE TABLE upload_sessions (
    id VARCHAR(36) PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    total_size BIGINT NOT NULL,
    uploaded_size BIGINT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'initiated',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    project_id VARCHAR(36) NULL,
    temp_file_path VARCHAR(500) NULL,
    final_file_path VARCHAR(500) NULL,
    file_hash VARCHAR(64) NULL,
    metadata JSON NULL
);

-- Add upload chunks table
CREATE TABLE upload_chunks (
    id VARCHAR(36) PRIMARY KEY,
    upload_session_id VARCHAR(36) NOT NULL,
    chunk_number INTEGER NOT NULL,
    size INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    hash VARCHAR(64) NULL,
    uploaded_at TIMESTAMP NULL,
    retry_count INTEGER DEFAULT 0,
    FOREIGN KEY (upload_session_id) REFERENCES upload_sessions(id),
    UNIQUE KEY unique_chunk (upload_session_id, chunk_number)
);

-- Update videos table to reference upload sessions
ALTER TABLE videos ADD COLUMN upload_session_id VARCHAR(36) NULL;
ALTER TABLE videos ADD FOREIGN KEY (upload_session_id) REFERENCES upload_sessions(id);
```

### Step 4: Configuration Updates

1. **Backend Configuration** (`config.py`):
```python
class Settings(BaseSettings):
    # Enhanced upload settings
    enhanced_upload_enabled: bool = True
    max_file_size: int = 500 * 1024 * 1024  # 500MB
    chunk_size: int = 5 * 1024 * 1024      # 5MB
    max_concurrent_chunks: int = 3
    upload_timeout: int = 3600              # 1 hour
    temp_upload_directory: str = "temp_uploads"
    
    # Existing settings...
```

2. **Frontend Configuration** (`.env`):
```env
REACT_APP_ENHANCED_UPLOAD_ENABLED=true
REACT_APP_MAX_FILE_SIZE=524288000
REACT_APP_CHUNK_SIZE=5242880
REACT_APP_UPLOAD_TIMEOUT=3600000
```

## Usage Examples

### Basic Upload with Progress
```typescript
const uploadClient = new EnhancedUploadClient();

const uploadId = await uploadClient.uploadFile(file, projectId, (progress) => {
  console.log(`Upload ${progress.progressPercentage}% complete`);
  console.log(`Speed: ${progress.uploadSpeed / 1024 / 1024} MB/s`);
  console.log(`ETA: ${progress.estimatedTimeRemaining}s`);
});
```

### Upload with Error Handling
```typescript
try {
  const uploadId = await uploadClient.uploadFile(file, projectId);
  console.log('Upload successful:', uploadId);
} catch (error) {
  if (error.message.includes('File too large')) {
    alert('Please select a smaller file (max 500MB)');
  } else if (error.message.includes('Network error')) {
    alert('Check your internet connection and try again');
  } else {
    alert(`Upload failed: ${error.message}`);
  }
}
```

### Real-time Progress with WebSocket
```typescript
const ws = uploadClient.connectWebSocket(uploadId);
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'status_update') {
    updateProgressUI(data.data);
  }
};
```

### Cancel Upload
```typescript
const success = await uploadClient.cancelUpload(uploadId);
if (success) {
  console.log('Upload cancelled successfully');
}
```

### Retry Failed Chunks
```typescript
const success = await uploadClient.retryFailedChunks(uploadId);
if (success) {
  console.log('Failed chunks retried successfully');
}
```

## Error Handling

### Common Error Scenarios
1. **File too large**: Handled with clear user message
2. **Network interruption**: Automatic retry with exponential backoff
3. **Server errors**: Graceful degradation with retry options
4. **Chunk corruption**: Hash validation and re-upload
5. **Upload timeout**: Session cleanup and user notification

### Error Recovery Features
- **Automatic retry**: Failed chunks are automatically retried
- **Resume capability**: Interrupted uploads can be resumed
- **Progress persistence**: Upload state is maintained across page refreshes
- **Cleanup**: Temporary files are automatically cleaned up on failure

## Performance Optimizations

### Backend
- **Async I/O**: Uses `aiofiles` and `asyncio` for non-blocking operations
- **Concurrent chunks**: Limits concurrent chunk uploads to prevent overload
- **Memory efficiency**: Streams large files without loading into memory
- **Background cleanup**: Automatic cleanup of expired upload sessions

### Frontend
- **Chunk streaming**: Processes file chunks without loading entire file
- **Concurrent uploads**: Multiple chunks uploaded simultaneously
- **Progress batching**: Reduces UI update frequency for better performance
- **Memory management**: Proper cleanup of file references and event listeners

## Monitoring and Logging

### Backend Logging
```python
logger.info(f"Upload session {upload_id} initiated: {filename} ({file_size / 1024 / 1024:.1f}MB)")
logger.debug(f"Chunk {chunk_number} uploaded for session {upload_id}")
logger.error(f"Upload session {upload_id} failed: {error_message}")
```

### Frontend Logging
```typescript
console.info(`Upload ${uploadId} started: ${file.name}`);
console.debug(`Chunk ${chunkNumber} uploaded successfully`);
console.error(`Upload failed: ${error.message}`);
```

### Metrics Collection
- Upload success/failure rates
- Average upload speeds
- Chunk retry rates
- Session timeout rates
- File size distributions

## Security Considerations

### File Validation
- **Extension checking**: Only allowed video formats
- **Size limits**: Configurable maximum file sizes
- **Hash validation**: Optional integrity checking
- **Virus scanning**: Integration ready (configurable)

### Access Control
- **Project-based permissions**: Files associated with specific projects
- **Session tokens**: Upload sessions tied to user authentication
- **Rate limiting**: Prevent abuse with configurable limits
- **Cleanup policies**: Automatic removal of abandoned uploads

## Testing

### Backend Tests
```python
# Test chunked upload workflow
async def test_complete_chunked_upload():
    service = EnhancedUploadService()
    session = await service.initiate_upload("test.mp4", 50*1024*1024)
    
    # Upload chunks
    for chunk_num in range(session.total_chunks):
        await service.upload_chunk(session.upload_id, chunk_num, chunk_data)
    
    assert session.status == UploadStatus.COMPLETED
```

### Frontend Tests
```typescript
// Test upload progress tracking
describe('EnhancedUploadClient', () => {
  it('should track upload progress correctly', async () => {
    const client = new EnhancedUploadClient();
    const progressUpdates = [];
    
    await client.uploadFile(mockFile, undefined, (progress) => {
      progressUpdates.push(progress);
    });
    
    expect(progressUpdates.length).toBeGreaterThan(0);
    expect(progressUpdates[progressUpdates.length - 1].progressPercentage).toBe(100);
  });
});
```

## Migration from Legacy System

### Gradual Migration Strategy
1. **Phase 1**: Deploy enhanced system alongside existing system
2. **Phase 2**: Route large files (>5MB) to enhanced system
3. **Phase 3**: Migrate all uploads to enhanced system
4. **Phase 4**: Remove legacy upload endpoints

### Backward Compatibility
- Legacy endpoints continue to work
- Existing upload format maintained
- Database schema additions only (no breaking changes)
- Frontend gracefully degrades if enhanced features unavailable

## Troubleshooting

### Common Issues
1. **Uploads fail immediately**: Check file size limits and permissions
2. **Chunks timeout**: Increase chunk timeout or reduce chunk size
3. **High memory usage**: Reduce concurrent chunks or chunk size
4. **Slow uploads**: Check network conditions and server resources

### Debug Mode
Enable debug logging for detailed troubleshooting:
```python
logging.getLogger('enhanced_upload_service').setLevel(logging.DEBUG)
```

### Health Check Endpoint
```bash
curl http://localhost:8000/api/uploads/statistics
```

This comprehensive guide provides everything needed to integrate the enhanced upload system while maintaining backward compatibility and providing a smooth migration path.