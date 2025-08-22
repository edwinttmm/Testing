# Video Workflow Code Changes Specification

## Overview
This document provides specific code changes needed to fix the video upload and linking workflow issues identified in the analysis report.

## Database Schema Changes

### 1. Make Video.project_id Nullable
```sql
-- Migration SQL:
ALTER TABLE videos 
MODIFY COLUMN project_id VARCHAR(36) NULL;

-- Update the model in models.py:
class Video(Base):
    __tablename__ = "videos"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False, index=True)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    duration = Column(Float)
    fps = Column(Float)
    resolution = Column(String)
    status = Column(String, default="uploaded", index=True)
    ground_truth_generated = Column(Boolean, default=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)  # Changed to nullable=True
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

## Backend Changes

### 1. Include Annotation Routes in main.py
```python
# Add to imports at top of main.py:
from annotation_routes import router as annotation_router

# Add after app creation (around line 50):
app.include_router(annotation_router, prefix="/api")
```

### 2. Add Central Video Upload Endpoint
```python
# Add to main.py after existing video endpoints:

@app.post("/api/videos", response_model=VideoUploadResponse)
async def upload_video_to_central_store(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload video to central store without project association"""
    temp_file_path = None
    try:
        # Generate secure filename and validate extension
        secure_filename, file_extension = generate_secure_filename(file.filename)
        
        # Setup paths for chunked upload with temp file
        upload_dir = settings.upload_directory
        os.makedirs(upload_dir, exist_ok=True)
        final_file_path = secure_join_path(upload_dir, secure_filename)
        
        # Use a temporary file during upload to prevent partial files in upload directory
        import tempfile
        temp_fd, temp_file_path = tempfile.mkstemp(suffix=file_extension, dir=upload_dir)
        
        # MEMORY OPTIMIZED: Chunked upload with size validation
        chunk_size = 64 * 1024  # 64KB chunks
        max_file_size = 100 * 1024 * 1024  # 100MB limit
        bytes_written = 0
        
        try:
            with os.fdopen(temp_fd, 'wb') as temp_file:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    
                    bytes_written += len(chunk)
                    if bytes_written > max_file_size:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File too large. Maximum size: {max_file_size / 1024 / 1024:.1f}MB"
                        )
                    
                    temp_file.write(chunk)
            
            # Move temp file to final location atomically
            os.rename(temp_file_path, final_file_path)
            temp_file_path = None  # Prevent cleanup since file was moved successfully
            
            # Create video record WITHOUT project association
            db_video = Video(
                filename=secure_filename,
                file_path=final_file_path,
                file_size=bytes_written,
                status="uploaded",
                project_id=None  # No project association
            )
            
            db.add(db_video)
            db.commit()
            db.refresh(db_video)
            
            logger.info(f"Video uploaded to central store: {db_video.id} ({secure_filename})")
            
            return VideoUploadResponse(
                id=db_video.id,
                filename=db_video.filename,
                file_size=db_video.file_size,
                status=db_video.status,
                created_at=db_video.created_at
            )
            
        except Exception as e:
            # Cleanup temp file on any error
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            if os.path.exists(final_file_path):
                os.unlink(final_file_path)
            raise e
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video upload error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )
    finally:
        # Final cleanup for any remaining temp files
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass

@app.get("/api/videos", response_model=List[VideoFile])
async def get_all_videos(db: Session = Depends(get_db)):
    """Get all videos in central store"""
    videos = db.query(Video).order_by(Video.created_at.desc()).all()
    return videos

@app.get("/api/videos/unlinked", response_model=List[VideoFile]) 
async def get_unlinked_videos(db: Session = Depends(get_db)):
    """Get videos not linked to any project"""
    # Get videos that have no project_id AND are not in video_project_links
    from models_annotation import VideoProjectLink
    
    linked_video_ids = db.query(VideoProjectLink.video_id).distinct().all()
    linked_video_ids = [vid[0] for vid in linked_video_ids]
    
    unlinked_videos = db.query(Video).filter(
        Video.project_id.is_(None),
        ~Video.id.in_(linked_video_ids) if linked_video_ids else True
    ).order_by(Video.created_at.desc()).all()
    
    return unlinked_videos
```

## Frontend Changes

### 1. Update API Service (api.ts)
```typescript
// Add new methods to ApiService class:

async uploadVideoToCentral(file: File, onProgress?: (progress: number) => void): Promise<VideoFile> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await this.api.post<VideoFile>('/api/videos', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100);
        onProgress(progress);
      }
    },
  });

  return response.data;
}

async getAllVideos(): Promise<VideoFile[]> {
  return this.cachedRequest<VideoFile[]>('GET', '/api/videos');
}

async getUnlinkedVideos(): Promise<VideoFile[]> {
  return this.cachedRequest<VideoFile[]>('GET', '/api/videos/unlinked');
}

// Add to exports at bottom:
export const uploadVideoToCentral = apiServiceInstance.uploadVideoToCentral.bind(apiServiceInstance);
export const getAllVideos = apiServiceInstance.getAllVideos.bind(apiServiceInstance);
export const getUnlinkedVideos = apiServiceInstance.getUnlinkedVideos.bind(apiServiceInstance);
```

### 2. Fix GroundTruth.tsx Upload Logic
```typescript
// Replace the uploadFiles function in GroundTruth.tsx:

const uploadFiles = useCallback(async (files: File[]) => {
  const newUploadingVideos: UploadingVideo[] = files.map(file => ({
    id: Math.random().toString(36).substr(2, 9),
    file,
    name: file.name,
    size: formatFileSize(file.size),
    progress: 0,
    status: 'uploading'
  }));
  
  setUploadingVideos(prev => [...prev, ...newUploadingVideos]);
  setUploadDialog(false);
  
  // Upload files concurrently to central store
  const uploadPromises = newUploadingVideos.map(async (uploadingVideo) => {
    try {
      const uploadedVideo = await apiService.uploadVideoToCentral( // Changed from uploadVideo
        uploadingVideo.file,
        (progress) => {
          setUploadingVideos(prev => 
            prev.map(v => 
              v.id === uploadingVideo.id 
                ? { ...v, progress }
                : v
            )
          );
        }
      );
      
      // Update status to processing
      setUploadingVideos(prev => 
        prev.map(v => 
          v.id === uploadingVideo.id 
            ? { ...v, status: 'processing', progress: 100 }
            : v
        )
      );
      
      // Add to main videos list and remove from uploading
      setTimeout(() => {
        setVideos(prev => [uploadedVideo, ...prev]);
        setUploadingVideos(prev => prev.filter(v => v.id !== uploadingVideo.id));
        setSuccessMessage(`Successfully uploaded ${uploadingVideo.name} to central store`);
      }, 1000);
      
    } catch (err) {
      const apiError = err as ApiError;
      const errorMessage = typeof apiError === 'string' 
        ? apiError 
        : apiError?.message || apiError?.detail || 'Upload failed';
      
      setUploadingVideos(prev => 
        prev.map(v => 
          v.id === uploadingVideo.id 
            ? { ...v, status: 'failed', error: errorMessage }
            : v
        )
      );
      
      setUploadErrors(prev => [...prev, {
        message: errorMessage,
        fileName: uploadingVideo.name
      }]);
    }
  });
  
  await Promise.allSettled(uploadPromises);
}, []);

// Update the loadVideos function to get all videos instead of project-specific:
const loadVideos = useCallback(async () => {
  if (loading) return;
  
  setLoading(true);
  
  try {
    setError(null);
    const videoList = await apiService.getAllVideos(); // Changed from getVideos(projectId)
    setVideos(videoList);
  } catch (err) {
    const apiError = err as ApiError;
    const errorMessage = typeof apiError === 'string' 
      ? apiError 
      : apiError?.message || apiError?.detail || 'Failed to load videos';
    setError(errorMessage);
    console.error('Failed to load videos:', err);
  } finally {
    setLoading(false);
  }
}, [loading]);
```

### 3. Fix React Error Handling in ProjectDetail.tsx
```typescript
// Update error handling in ProjectDetail.tsx:

// In catch blocks, ensure error is always a string:
} catch (err: any) {
  console.error('Failed to load project data:', err);
  const errorMessage = typeof err === 'string' 
    ? err 
    : err?.message || err?.detail || 'Failed to load project data';
  setError(errorMessage);
}

// In linkVideosToProject error handling:
} catch (err: any) {
  console.error('Failed to link videos:', err);
  const errorMessage = typeof err === 'string' 
    ? err 
    : err?.message || err?.detail || 'Failed to link videos to project';
  setError(errorMessage);
}

// In unlinkVideo error handling:  
} catch (err: any) {
  console.error('Video unlink error:', err);
  const errorMessage = typeof err === 'string' 
    ? err 
    : err?.message || err?.detail || 'Failed to unlink video';
  setError(errorMessage);
}

// In JSX, add fallback for error display:
{error && (
  <Alert severity="error" sx={{ mb: 2 }}>
    {error || 'An error occurred'}
  </Alert>
)}
```

### 4. Add Video Selection Dialog Component
```typescript
// Create new component: VideoSelectionDialog.tsx (already exists, may need updates)

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Checkbox,
  Typography,
  Box,
  CircularProgress
} from '@mui/material';
import { VideoFile, ApiError } from '../services/types';
import { apiService } from '../services/api';

interface VideoSelectionDialogProps {
  open: boolean;
  onClose: () => void;
  onSelect: (videos: VideoFile[]) => void;
}

export default function VideoSelectionDialog({ open, onClose, onSelect }: VideoSelectionDialogProps) {
  const [videos, setVideos] = useState<VideoFile[]>([]);
  const [selectedVideos, setSelectedVideos] = useState<VideoFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      loadUnlinkedVideos();
    }
  }, [open]);

  const loadUnlinkedVideos = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const unlinkedVideos = await apiService.getUnlinkedVideos();
      setVideos(unlinkedVideos);
    } catch (err: any) {
      const errorMessage = typeof err === 'string' 
        ? err 
        : err?.message || err?.detail || 'Failed to load available videos';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleVideo = (video: VideoFile) => {
    setSelectedVideos(prev => {
      const isSelected = prev.some(v => v.id === video.id);
      if (isSelected) {
        return prev.filter(v => v.id !== video.id);
      } else {
        return [...prev, video];
      }
    });
  };

  const handleConfirm = () => {
    onSelect(selectedVideos);
    setSelectedVideos([]);
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Select Videos to Link</DialogTitle>
      <DialogContent>
        {loading && (
          <Box display="flex" justifyContent="center" p={2}>
            <CircularProgress />
          </Box>
        )}
        
        {error && (
          <Typography color="error" paragraph>
            {error}
          </Typography>
        )}
        
        {!loading && !error && videos.length === 0 && (
          <Typography color="textSecondary" paragraph>
            No unlinked videos available. Upload videos to the Ground Truth store first.
          </Typography>
        )}
        
        {!loading && !error && videos.length > 0 && (
          <List>
            {videos.map((video) => (
              <ListItem key={video.id} button onClick={() => handleToggleVideo(video)}>
                <ListItemText
                  primary={video.filename}
                  secondary={`${video.file_size ? Math.round(video.file_size / 1024 / 1024) : 0}MB • ${video.created_at ? new Date(video.created_at).toLocaleDateString() : 'Unknown date'}`}
                />
                <ListItemSecondaryAction>
                  <Checkbox
                    checked={selectedVideos.some(v => v.id === video.id)}
                    onChange={() => handleToggleVideo(video)}
                  />
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button 
          onClick={handleConfirm} 
          variant="contained" 
          disabled={selectedVideos.length === 0}
        >
          Link {selectedVideos.length} Video{selectedVideos.length !== 1 ? 's' : ''}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
```

## Implementation Steps

### Phase 1: Critical Fixes
1. **Update models.py** - Make Video.project_id nullable
2. **Include annotation routes** - Add router to main.py
3. **Fix error handling** - Update ProjectDetail.tsx error handling

### Phase 2: Architecture Changes  
1. **Add central video endpoints** - Implement new API endpoints
2. **Update frontend API service** - Add new methods
3. **Fix GroundTruth component** - Remove project ID requirement

### Phase 3: Enhanced UI
1. **Update VideoSelectionDialog** - Support selecting from unlinked videos
2. **Test workflow end-to-end** - Upload → Browse → Link → Unlink
3. **Add bulk operations** - Multi-select, bulk linking

## Testing Checklist

- [ ] Videos can be uploaded without project ID
- [ ] Uploaded videos appear in central store
- [ ] Videos can be linked to projects
- [ ] Linked videos appear in project view
- [ ] Videos can be unlinked from projects
- [ ] Unlinked videos return to available pool
- [ ] Error messages display as strings (no React object errors)
- [ ] Loading states work correctly
- [ ] File upload progress tracking works

## Backward Compatibility

These changes maintain backward compatibility:
- Existing project-specific uploads continue working
- Existing video records with project_id remain valid
- Frontend components gracefully handle both workflows
- No breaking changes to existing API contracts