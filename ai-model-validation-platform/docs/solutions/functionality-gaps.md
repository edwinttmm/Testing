# Functionality Gaps - Phase 2 Implementation Guide

## Overview

This document addresses the major functionality gaps in the AI Model Validation Platform. These are features that exist partially or are completely missing, preventing the system from delivering its core value proposition.

## Pre-Implementation Checklist

- [ ] Phase 1 critical fixes completed
- [ ] Database and authentication systems working
- [ ] API integration verified
- [ ] Development environment configured

---

## Gap 1: Complete Video Processing Pipeline

**Priority**: HIGH  
**Estimated Time**: 4-5 days  
**Risk Level**: Medium  

### Problem Analysis
The video processing system is incomplete and unreliable:

- Video uploads sometimes fail silently
- No thumbnail generation
- Metadata extraction inconsistent
- Video streaming endpoints unreliable
- No progress tracking for processing
- File validation insufficient

### Current State vs Required State

| Component | Current State | Required State | Gap |
|-----------|--------------|----------------|-----|
| Upload | Basic form, no validation | Secure upload with progress | Large |
| Processing | Minimal metadata | Full video analysis | Large |
| Storage | File system only | Organized with backup | Medium |
| Streaming | Basic file serve | Optimized streaming | Medium |
| Thumbnails | Not implemented | Auto-generation | Large |

### Implementation Plan

#### Step 1: Enhanced Video Upload Service

Create `backend/services/enhanced_video_service.py`:

```python
import os
import uuid
import cv2
import json
from pathlib import Path
from typing import Dict, Optional, List
from fastapi import UploadFile, HTTPException
from PIL import Image
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

class VideoProcessingService:
    def __init__(self):
        self.upload_dir = Path("uploads/videos")
        self.thumbnail_dir = Path("uploads/thumbnails") 
        self.temp_dir = Path("uploads/temp")
        
        # Create directories
        for directory in [self.upload_dir, self.thumbnail_dir, self.temp_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
        self.max_file_size = 500 * 1024 * 1024  # 500MB
    
    async def process_video_upload(
        self, 
        file: UploadFile, 
        project_id: str,
        user_id: str
    ) -> Dict:
        """Complete video processing pipeline"""
        
        video_id = str(uuid.uuid4())
        
        try:
            # Step 1: Validate file
            await self._validate_upload(file, video_id)
            
            # Step 2: Save temporary file
            temp_path = await self._save_temp_file(file, video_id)
            
            # Step 3: Process video metadata (async)
            processing_task = asyncio.create_task(
                self._process_video_async(temp_path, video_id, project_id, user_id)
            )
            
            # Step 4: Return immediate response with processing status
            return {
                "video_id": video_id,
                "status": "processing",
                "message": "Video uploaded successfully, processing in background",
                "filename": file.filename,
                "processing_task_id": video_id
            }
            
        except Exception as e:
            logger.error(f"Video upload failed for {video_id}: {str(e)}")
            await self._cleanup_temp_files(video_id)
            raise HTTPException(500, f"Video upload failed: {str(e)}")
    
    async def _validate_upload(self, file: UploadFile, video_id: str):
        """Comprehensive file validation"""
        
        # Check file extension
        if not any(file.filename.lower().endswith(ext) for ext in self.supported_formats):
            raise HTTPException(
                400, 
                f"Unsupported file format. Allowed: {', '.join(self.supported_formats)}"
            )
        
        # Check MIME type
        if not file.content_type or not file.content_type.startswith('video/'):
            raise HTTPException(400, "Invalid file type. Must be a video file.")
        
        # Check file size (read first to get size)
        content = await file.read()
        await file.seek(0)  # Reset file pointer
        
        if len(content) > self.max_file_size:
            raise HTTPException(
                413, 
                f"File too large. Maximum size: {self.max_file_size / 1024 / 1024:.1f}MB"
            )
        
        if len(content) < 1024:  # Minimum 1KB
            raise HTTPException(400, "File too small or corrupted")
        
        logger.info(f"Video validation passed for {video_id}: {file.filename}")
    
    async def _save_temp_file(self, file: UploadFile, video_id: str) -> Path:
        """Save uploaded file to temp directory"""
        
        file_extension = Path(file.filename).suffix.lower()
        temp_filename = f"{video_id}_temp{file_extension}"
        temp_path = self.temp_dir / temp_filename
        
        content = await file.read()
        
        with open(temp_path, 'wb') as temp_file:
            temp_file.write(content)
        
        logger.info(f"Saved temp file: {temp_path}")
        return temp_path
    
    async def _process_video_async(
        self, 
        temp_path: Path, 
        video_id: str, 
        project_id: str, 
        user_id: str
    ):
        """Background video processing task"""
        
        try:
            # Process in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            # Extract metadata
            metadata = await loop.run_in_executor(
                self.executor, 
                self._extract_video_metadata, 
                temp_path
            )
            
            # Generate thumbnail
            thumbnail_path = await loop.run_in_executor(
                self.executor,
                self._generate_thumbnail,
                temp_path,
                video_id
            )
            
            # Move to permanent location
            final_path = await self._move_to_permanent_location(temp_path, video_id)
            
            # Save to database
            video_record = await self._save_to_database(
                video_id=video_id,
                project_id=project_id,
                user_id=user_id,
                file_path=final_path,
                thumbnail_path=thumbnail_path,
                metadata=metadata,
                original_filename=temp_path.name
            )
            
            # Update processing status
            await self._update_processing_status(video_id, "completed", metadata)
            
            logger.info(f"Video processing completed for {video_id}")
            
        except Exception as e:
            logger.error(f"Video processing failed for {video_id}: {str(e)}")
            await self._update_processing_status(video_id, "failed", {"error": str(e)})
            await self._cleanup_temp_files(video_id)
    
    def _extract_video_metadata(self, video_path: Path) -> Dict:
        """Extract comprehensive video metadata"""
        
        try:
            cap = cv2.VideoCapture(str(video_path))
            
            if not cap.isOpened():
                raise Exception("Could not open video file")
            
            # Basic properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            
            # Additional metadata
            codec = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec_name = "".join([chr((codec >> 8 * i) & 0xFF) for i in range(4)])
            
            metadata = {
                "width": width,
                "height": height,
                "fps": fps,
                "frame_count": frame_count,
                "duration": duration,
                "resolution": f"{width}x{height}",
                "codec": codec_name,
                "aspect_ratio": width / height if height > 0 else 1,
                "file_size": video_path.stat().st_size,
                "bitrate": (video_path.stat().st_size * 8) / duration if duration > 0 else 0
            }
            
            cap.release()
            
            # Quality assessment
            metadata.update(self._assess_video_quality(metadata))
            
            return metadata
            
        except Exception as e:
            logger.error(f"Metadata extraction failed: {str(e)}")
            return {
                "error": str(e),
                "file_size": video_path.stat().st_size if video_path.exists() else 0
            }
    
    def _assess_video_quality(self, metadata: Dict) -> Dict:
        """Assess video quality for validation"""
        
        quality_score = 0
        issues = []
        recommendations = []
        
        # Resolution check
        width, height = metadata.get("width", 0), metadata.get("height", 0)
        if width >= 1920 and height >= 1080:
            quality_score += 30
        elif width >= 1280 and height >= 720:
            quality_score += 20
            recommendations.append("Consider higher resolution for better analysis")
        else:
            quality_score += 10
            issues.append("Low resolution may affect detection accuracy")
        
        # Frame rate check
        fps = metadata.get("fps", 0)
        if fps >= 30:
            quality_score += 25
        elif fps >= 24:
            quality_score += 20
        else:
            quality_score += 10
            issues.append("Low frame rate may miss fast movements")
        
        # Duration check
        duration = metadata.get("duration", 0)
        if 10 <= duration <= 300:  # 10 seconds to 5 minutes
            quality_score += 25
        elif duration > 300:
            quality_score += 15
            recommendations.append("Long videos may take significant time to process")
        else:
            quality_score += 10
            issues.append("Very short videos may not provide sufficient test data")
        
        # Bitrate check
        bitrate = metadata.get("bitrate", 0)
        if bitrate > 5000000:  # 5 Mbps
            quality_score += 20
        elif bitrate > 2000000:  # 2 Mbps
            quality_score += 15
        else:
            quality_score += 10
            issues.append("Low bitrate may result in compression artifacts")
        
        return {
            "quality_score": quality_score,
            "quality_grade": self._get_quality_grade(quality_score),
            "quality_issues": issues,
            "quality_recommendations": recommendations
        }
    
    def _get_quality_grade(self, score: int) -> str:
        """Convert quality score to grade"""
        if score >= 90:
            return "Excellent"
        elif score >= 75:
            return "Good"
        elif score >= 60:
            return "Fair"
        else:
            return "Poor"
    
    def _generate_thumbnail(self, video_path: Path, video_id: str) -> Path:
        """Generate video thumbnail"""
        
        try:
            cap = cv2.VideoCapture(str(video_path))
            
            if not cap.isOpened():
                raise Exception("Could not open video for thumbnail")
            
            # Get frame from middle of video
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            middle_frame = frame_count // 2
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
            ret, frame = cap.read()
            
            if not ret:
                # Fallback to first frame
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
            
            if ret:
                # Resize for thumbnail
                height, width = frame.shape[:2]
                max_size = 300
                
                if width > height:
                    new_width = max_size
                    new_height = int(height * max_size / width)
                else:
                    new_height = max_size
                    new_width = int(width * max_size / height)
                
                thumbnail = cv2.resize(frame, (new_width, new_height))
                
                # Save thumbnail
                thumbnail_filename = f"{video_id}.jpg"
                thumbnail_path = self.thumbnail_dir / thumbnail_filename
                
                cv2.imwrite(str(thumbnail_path), thumbnail)
                
                cap.release()
                return thumbnail_path
            
            cap.release()
            raise Exception("Could not extract frame for thumbnail")
            
        except Exception as e:
            logger.error(f"Thumbnail generation failed: {str(e)}")
            # Create placeholder thumbnail
            return self._create_placeholder_thumbnail(video_id)
    
    def _create_placeholder_thumbnail(self, video_id: str) -> Path:
        """Create placeholder thumbnail when generation fails"""
        
        thumbnail_filename = f"{video_id}.jpg"
        thumbnail_path = self.thumbnail_dir / thumbnail_filename
        
        # Create simple placeholder image
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('RGB', (300, 200), color=(100, 100, 100))
        draw = ImageDraw.Draw(img)
        
        # Add text
        try:
            font = ImageFont.load_default()
        except:
            font = None
        
        text = "Video Thumbnail\nNot Available"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (300 - text_width) // 2
        y = (200 - text_height) // 2
        
        draw.text((x, y), text, fill=(255, 255, 255), font=font)
        
        img.save(thumbnail_path, 'JPEG')
        return thumbnail_path
    
    async def _move_to_permanent_location(self, temp_path: Path, video_id: str) -> Path:
        """Move video from temp to permanent storage"""
        
        file_extension = temp_path.suffix
        permanent_filename = f"{video_id}{file_extension}"
        permanent_path = self.upload_dir / permanent_filename
        
        # Move file
        temp_path.rename(permanent_path)
        
        logger.info(f"Moved video to permanent location: {permanent_path}")
        return permanent_path
    
    async def _save_to_database(self, **video_data) -> Dict:
        """Save video record to database"""
        # This would integrate with your database layer
        # For now, return the video data
        return video_data
    
    async def _update_processing_status(self, video_id: str, status: str, metadata: Dict):
        """Update video processing status in database"""
        # This would update the database record
        logger.info(f"Updated processing status for {video_id}: {status}")
    
    async def _cleanup_temp_files(self, video_id: str):
        """Clean up temporary files on error"""
        try:
            temp_files = list(self.temp_dir.glob(f"{video_id}_*"))
            for temp_file in temp_files:
                temp_file.unlink()
            logger.info(f"Cleaned up temp files for {video_id}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp files for {video_id}: {str(e)}")
    
    async def get_processing_status(self, video_id: str) -> Dict:
        """Get current processing status"""
        # This would query the database for status
        return {
            "video_id": video_id,
            "status": "completed",  # or "processing", "failed"
            "progress": 100,
            "metadata": {}
        }

# Global service instance
video_service = VideoProcessingService()
```

#### Step 2: Enhanced Video API Endpoints

Update `backend/api/videos.py`:

```python
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from services.enhanced_video_service import video_service
from auth_service import get_current_user

router = APIRouter()

@router.post("/api/projects/{project_id}/videos/upload")
async def upload_video_enhanced(
    project_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Enhanced video upload with background processing"""
    
    try:
        result = await video_service.process_video_upload(
            file=file,
            project_id=project_id,
            user_id=current_user.id
        )
        
        return APIResponse.success_response(
            data=result,
            message="Video upload initiated successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Video upload failed: {str(e)}")
        raise HTTPException(500, "Video upload failed")

@router.get("/api/videos/{video_id}/status")
async def get_video_status(video_id: str):
    """Get video processing status"""
    
    try:
        status = await video_service.get_processing_status(video_id)
        return APIResponse.success_response(data=status)
    except Exception as e:
        raise HTTPException(404, "Video not found")

@router.get("/api/videos/{video_id}/metadata")
async def get_video_metadata(video_id: str):
    """Get detailed video metadata"""
    
    # Query database for video metadata
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, "Video not found")
    
    return APIResponse.success_response(data={
        "id": video.id,
        "filename": video.filename,
        "duration": video.duration,
        "fps": video.fps,
        "resolution": video.resolution,
        "file_size": video.file_size,
        "quality_score": video.quality_score,
        "quality_grade": video.quality_grade,
        "created_at": video.created_at,
        "status": video.status
    })
```

#### Step 3: Frontend Video Upload Component

Create `frontend/src/components/Video/EnhancedVideoUpload.tsx`:

```typescript
import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { apiService } from '../../services/api';

interface VideoUploadProps {
  projectId: string;
  onUploadComplete: (video: VideoFile) => void;
  onUploadError: (error: string) => void;
}

export const EnhancedVideoUpload: React.FC<VideoUploadProps> = ({
  projectId,
  onUploadComplete,
  onUploadError
}) => {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [processingStatus, setProcessingStatus] = useState<string>('');

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setUploading(true);
    setProgress(0);
    setProcessingStatus('Uploading...');

    try {
      // Upload video
      const uploadResult = await apiService.post(
        `/api/projects/${projectId}/videos/upload`,
        { file },
        {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (progressEvent) => {
            if (progressEvent.total) {
              const uploadProgress = Math.round(
                (progressEvent.loaded / progressEvent.total) * 50 // 50% for upload
              );
              setProgress(uploadProgress);
            }
          }
        }
      );

      const videoId = uploadResult.video_id;
      setProcessingStatus('Processing video...');
      
      // Poll for processing status
      const pollStatus = setInterval(async () => {
        try {
          const status = await apiService.get(`/api/videos/${videoId}/status`);
          
          if (status.status === 'completed') {
            clearInterval(pollStatus);
            setProgress(100);
            setProcessingStatus('Complete!');
            
            // Get full video data
            const videoData = await apiService.get(`/api/videos/${videoId}/metadata`);
            onUploadComplete(videoData);
            
          } else if (status.status === 'failed') {
            clearInterval(pollStatus);
            onUploadError('Video processing failed');
            
          } else {
            // Update progress during processing
            setProgress(50 + (status.progress || 0) * 0.5); // 50-100% for processing
            setProcessingStatus(`Processing: ${status.progress || 0}%`);
          }
          
        } catch (error) {
          clearInterval(pollStatus);
          onUploadError('Failed to check processing status');
        }
      }, 1000);

      // Set timeout for processing
      setTimeout(() => {
        clearInterval(pollStatus);
        if (progress < 100) {
          onUploadError('Video processing timed out');
        }
      }, 5 * 60 * 1000); // 5 minutes

    } catch (error: any) {
      onUploadError(error.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  }, [projectId, onUploadComplete, onUploadError]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'video/*': ['.mp4', '.avi', '.mov', '.mkv', '.webm']
    },
    maxSize: 500 * 1024 * 1024, // 500MB
    multiple: false,
    disabled: uploading
  });

  return (
    <div className="enhanced-video-upload">
      <div
        {...getRootProps()}
        className={`
          dropzone 
          ${isDragActive ? 'drag-active' : ''} 
          ${uploading ? 'uploading' : ''}
        `}
      >
        <input {...getInputProps()} />
        
        {uploading ? (
          <div className="upload-progress">
            <div className="progress-bar">
              <div 
                className="progress-fill" 
                style={{ width: `${progress}%` }}
              />
            </div>
            <p>{processingStatus}</p>
            <p>{progress}% complete</p>
          </div>
        ) : (
          <div className="upload-prompt">
            {isDragActive ? (
              <p>Drop the video file here...</p>
            ) : (
              <>
                <p>Drag & drop a video file here, or click to select</p>
                <p className="format-info">
                  Supported formats: MP4, AVI, MOV, MKV, WebM
                </p>
                <p className="size-info">Maximum size: 500MB</p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
```

---

## Gap 2: Ground Truth Annotation System

**Priority**: HIGH  
**Estimated Time**: 5-6 days  
**Risk Level**: High  

### Problem Analysis
The annotation system has a UI but lacks backend functionality:

- No persistent annotation storage
- Bounding box validation missing
- No annotation collaboration features
- Export/import functionality incomplete
- No annotation quality validation

### Implementation Plan

#### Step 1: Complete Annotation Backend

Create `backend/services/annotation_service.py`:

```python
from typing import List, Dict, Optional
import uuid
from sqlalchemy.orm import Session
from models import Annotation, Video, AuthUser
import json
from datetime import datetime

class AnnotationService:
    def __init__(self, db: Session):
        self.db = db
    
    async def create_annotation(
        self,
        video_id: str,
        frame_number: int,
        bounding_box: Dict,
        vru_type: str,
        annotator_id: str,
        timestamp: float,
        confidence: float = 1.0,
        notes: Optional[str] = None
    ) -> Annotation:
        """Create new annotation with validation"""
        
        # Validate video exists
        video = self.db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError("Video not found")
        
        # Validate bounding box
        self._validate_bounding_box(bounding_box)
        
        # Validate frame number
        if frame_number < 0 or (video.total_frames and frame_number >= video.total_frames):
            raise ValueError("Invalid frame number")
        
        # Generate detection ID
        detection_id = self._generate_detection_id(video_id, frame_number, vru_type)
        
        # Create annotation
        annotation = Annotation(
            id=str(uuid.uuid4()),
            video_id=video_id,
            detection_id=detection_id,
            frame_number=frame_number,
            timestamp=timestamp,
            vru_type=vru_type,
            bounding_box=bounding_box,
            annotator=annotator_id,
            confidence=confidence,
            notes=notes,
            validated=False
        )
        
        self.db.add(annotation)
        await self.db.commit()
        await self.db.refresh(annotation)
        
        return annotation
    
    def _validate_bounding_box(self, bbox: Dict):
        """Validate bounding box coordinates"""
        required_keys = ['x', 'y', 'width', 'height']
        
        # Check required keys
        for key in required_keys:
            if key not in bbox:
                raise ValueError(f"Missing bounding box key: {key}")
            
            if not isinstance(bbox[key], (int, float)):
                raise ValueError(f"Bounding box {key} must be numeric")
        
        # Check values are non-negative
        if bbox['x'] < 0 or bbox['y'] < 0:
            raise ValueError("Bounding box coordinates cannot be negative")
        
        if bbox['width'] <= 0 or bbox['height'] <= 0:
            raise ValueError("Bounding box dimensions must be positive")
        
        # Check reasonable bounds (assuming max video size)
        if bbox['x'] > 4096 or bbox['y'] > 4096:
            raise ValueError("Bounding box coordinates seem too large")
        
        if bbox['width'] > 4096 or bbox['height'] > 4096:
            raise ValueError("Bounding box dimensions seem too large")
    
    def _generate_detection_id(self, video_id: str, frame_number: int, vru_type: str) -> str:
        """Generate unique detection ID"""
        vru_prefix = {
            'pedestrian': 'PED',
            'cyclist': 'CYC', 
            'motorcyclist': 'MOT',
            'wheelchair_user': 'WHL',
            'scooter_rider': 'SCO'
        }.get(vru_type, 'UNK')
        
        return f"DET_{vru_prefix}_{video_id[:8]}_{frame_number:06d}"
    
    async def get_video_annotations(
        self,
        video_id: str,
        frame_start: Optional[int] = None,
        frame_end: Optional[int] = None,
        vru_type: Optional[str] = None
    ) -> List[Annotation]:
        """Get annotations for video with optional filtering"""
        
        query = self.db.query(Annotation).filter(Annotation.video_id == video_id)
        
        if frame_start is not None:
            query = query.filter(Annotation.frame_number >= frame_start)
        
        if frame_end is not None:
            query = query.filter(Annotation.frame_number <= frame_end)
        
        if vru_type:
            query = query.filter(Annotation.vru_type == vru_type)
        
        return query.order_by(Annotation.frame_number, Annotation.timestamp).all()
    
    async def update_annotation(
        self,
        annotation_id: str,
        updates: Dict,
        annotator_id: str
    ) -> Annotation:
        """Update existing annotation"""
        
        annotation = self.db.query(Annotation).filter(Annotation.id == annotation_id).first()
        if not annotation:
            raise ValueError("Annotation not found")
        
        # Check permissions (annotator can only edit their own, or if superuser)
        user = self.db.query(AuthUser).filter(AuthUser.id == annotator_id).first()
        if annotation.annotator != annotator_id and not (user and user.is_superuser):
            raise ValueError("No permission to edit this annotation")
        
        # Update allowed fields
        allowed_updates = ['bounding_box', 'vru_type', 'confidence', 'notes', 'occluded', 'truncated', 'difficult']
        
        for key, value in updates.items():
            if key in allowed_updates:
                if key == 'bounding_box':
                    self._validate_bounding_box(value)
                setattr(annotation, key, value)
        
        # Mark as updated
        annotation.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(annotation)
        
        return annotation
    
    async def validate_annotation(
        self,
        annotation_id: str,
        validator_id: str,
        validated: bool,
        validation_notes: Optional[str] = None
    ) -> Annotation:
        """Validate or reject annotation"""
        
        annotation = self.db.query(Annotation).filter(Annotation.id == annotation_id).first()
        if not annotation:
            raise ValueError("Annotation not found")
        
        # Check validator permissions
        validator = self.db.query(AuthUser).filter(AuthUser.id == validator_id).first()
        if not validator or not validator.is_superuser:
            raise ValueError("No permission to validate annotations")
        
        annotation.validated = validated
        annotation.validation_notes = validation_notes
        annotation.validated_by = validator_id
        annotation.validated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(annotation)
        
        return annotation
    
    async def export_annotations(
        self,
        video_id: str,
        format_type: str = 'json'
    ) -> Dict:
        """Export annotations in various formats"""
        
        annotations = await self.get_video_annotations(video_id)
        video = self.db.query(Video).filter(Video.id == video_id).first()
        
        if format_type == 'coco':
            return self._export_coco_format(annotations, video)
        elif format_type == 'yolo':
            return self._export_yolo_format(annotations, video)
        elif format_type == 'pascal':
            return self._export_pascal_format(annotations, video)
        else:  # json
            return self._export_json_format(annotations, video)
    
    def _export_json_format(self, annotations: List[Annotation], video: Video) -> Dict:
        """Export in custom JSON format"""
        return {
            "video_info": {
                "id": video.id,
                "filename": video.filename,
                "width": int(video.resolution.split('x')[0]) if video.resolution else None,
                "height": int(video.resolution.split('x')[1]) if video.resolution else None,
                "fps": video.fps,
                "duration": video.duration,
                "total_frames": video.total_frames
            },
            "annotations": [
                {
                    "id": ann.id,
                    "detection_id": ann.detection_id,
                    "frame_number": ann.frame_number,
                    "timestamp": ann.timestamp,
                    "vru_type": ann.vru_type,
                    "bounding_box": ann.bounding_box,
                    "confidence": ann.confidence,
                    "validated": ann.validated,
                    "annotator": ann.annotator,
                    "created_at": ann.created_at.isoformat(),
                    "notes": ann.notes
                }
                for ann in annotations
            ],
            "export_info": {
                "total_annotations": len(annotations),
                "export_date": datetime.utcnow().isoformat(),
                "format": "json"
            }
        }
    
    def _export_coco_format(self, annotations: List[Annotation], video: Video) -> Dict:
        """Export in COCO format"""
        # COCO format implementation
        return {
            "info": {
                "description": "VRU Detection Annotations",
                "version": "1.0",
                "date_created": datetime.utcnow().isoformat()
            },
            "categories": [
                {"id": 1, "name": "pedestrian"},
                {"id": 2, "name": "cyclist"},
                {"id": 3, "name": "motorcyclist"},
                {"id": 4, "name": "wheelchair_user"},
                {"id": 5, "name": "scooter_rider"}
            ],
            "images": [
                {
                    "id": 1,
                    "file_name": video.filename,
                    "width": int(video.resolution.split('x')[0]) if video.resolution else 1920,
                    "height": int(video.resolution.split('x')[1]) if video.resolution else 1080
                }
            ],
            "annotations": [
                {
                    "id": i + 1,
                    "image_id": 1,
                    "category_id": self._get_category_id(ann.vru_type),
                    "bbox": [ann.bounding_box['x'], ann.bounding_box['y'], 
                            ann.bounding_box['width'], ann.bounding_box['height']],
                    "area": ann.bounding_box['width'] * ann.bounding_box['height'],
                    "iscrowd": 0
                }
                for i, ann in enumerate(annotations)
            ]
        }
    
    def _get_category_id(self, vru_type: str) -> int:
        """Get COCO category ID for VRU type"""
        mapping = {
            'pedestrian': 1,
            'cyclist': 2,
            'motorcyclist': 3,
            'wheelchair_user': 4,
            'scooter_rider': 5
        }
        return mapping.get(vru_type, 1)
    
    async def import_annotations(
        self,
        video_id: str,
        annotation_data: Dict,
        annotator_id: str,
        format_type: str = 'json'
    ) -> Dict:
        """Import annotations from various formats"""
        
        imported_count = 0
        errors = []
        
        try:
            if format_type == 'json':
                annotations = annotation_data.get('annotations', [])
            elif format_type == 'coco':
                annotations = self._parse_coco_format(annotation_data)
            else:
                raise ValueError(f"Unsupported import format: {format_type}")
            
            for ann_data in annotations:
                try:
                    await self.create_annotation(
                        video_id=video_id,
                        frame_number=ann_data.get('frame_number', 0),
                        bounding_box=ann_data['bounding_box'],
                        vru_type=ann_data['vru_type'],
                        annotator_id=annotator_id,
                        timestamp=ann_data.get('timestamp', 0),
                        confidence=ann_data.get('confidence', 1.0),
                        notes=ann_data.get('notes')
                    )
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Failed to import annotation: {str(e)}")
                    
        except Exception as e:
            errors.append(f"Import failed: {str(e)}")
        
        return {
            "imported_count": imported_count,
            "error_count": len(errors),
            "errors": errors
        }
```

#### Step 2: Annotation API Endpoints

Create `backend/api/annotations.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from services.annotation_service import AnnotationService
from database import get_db
from auth_service import get_current_user
from pydantic import BaseModel
from typing import List, Optional, Dict

router = APIRouter()

class AnnotationCreate(BaseModel):
    frame_number: int
    bounding_box: Dict
    vru_type: str
    timestamp: float
    confidence: float = 1.0
    notes: Optional[str] = None

class AnnotationUpdate(BaseModel):
    bounding_box: Optional[Dict] = None
    vru_type: Optional[str] = None
    confidence: Optional[float] = None
    notes: Optional[str] = None
    occluded: Optional[bool] = None
    truncated: Optional[bool] = None
    difficult: Optional[bool] = None

@router.post("/api/videos/{video_id}/annotations")
async def create_annotation(
    video_id: str,
    annotation: AnnotationCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new annotation"""
    
    try:
        service = AnnotationService(db)
        
        new_annotation = await service.create_annotation(
            video_id=video_id,
            frame_number=annotation.frame_number,
            bounding_box=annotation.bounding_box,
            vru_type=annotation.vru_type,
            annotator_id=current_user.id,
            timestamp=annotation.timestamp,
            confidence=annotation.confidence,
            notes=annotation.notes
        )
        
        return APIResponse.success_response(
            data=new_annotation,
            message="Annotation created successfully"
        )
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to create annotation: {str(e)}")

@router.get("/api/videos/{video_id}/annotations")
async def get_video_annotations(
    video_id: str,
    frame_start: Optional[int] = None,
    frame_end: Optional[int] = None,
    vru_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get annotations for video"""
    
    try:
        service = AnnotationService(db)
        annotations = await service.get_video_annotations(
            video_id=video_id,
            frame_start=frame_start,
            frame_end=frame_end,
            vru_type=vru_type
        )
        
        return APIResponse.success_response(data=annotations)
        
    except Exception as e:
        raise HTTPException(500, f"Failed to get annotations: {str(e)}")

@router.put("/api/annotations/{annotation_id}")
async def update_annotation(
    annotation_id: str,
    updates: AnnotationUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update existing annotation"""
    
    try:
        service = AnnotationService(db)
        
        updated_annotation = await service.update_annotation(
            annotation_id=annotation_id,
            updates=updates.dict(exclude_unset=True),
            annotator_id=current_user.id
        )
        
        return APIResponse.success_response(
            data=updated_annotation,
            message="Annotation updated successfully"
        )
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to update annotation: {str(e)}")

@router.post("/api/annotations/{annotation_id}/validate")
async def validate_annotation(
    annotation_id: str,
    validated: bool,
    validation_notes: Optional[str] = None,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Validate annotation (superuser only)"""
    
    try:
        service = AnnotationService(db)
        
        validated_annotation = await service.validate_annotation(
            annotation_id=annotation_id,
            validator_id=current_user.id,
            validated=validated,
            validation_notes=validation_notes
        )
        
        return APIResponse.success_response(
            data=validated_annotation,
            message="Annotation validation updated"
        )
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to validate annotation: {str(e)}")

@router.get("/api/videos/{video_id}/annotations/export")
async def export_annotations(
    video_id: str,
    format_type: str = "json",
    db: Session = Depends(get_db)
):
    """Export annotations in various formats"""
    
    try:
        service = AnnotationService(db)
        exported_data = await service.export_annotations(video_id, format_type)
        
        return APIResponse.success_response(
            data=exported_data,
            message=f"Annotations exported in {format_type} format"
        )
        
    except Exception as e:
        raise HTTPException(500, f"Failed to export annotations: {str(e)}")

@router.post("/api/videos/{video_id}/annotations/import")
async def import_annotations(
    video_id: str,
    file: UploadFile = File(...),
    format_type: str = "json",
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import annotations from file"""
    
    try:
        # Read file content
        content = await file.read()
        
        if file.content_type == 'application/json':
            import json
            annotation_data = json.loads(content)
        else:
            raise HTTPException(400, "Only JSON files are supported")
        
        service = AnnotationService(db)
        result = await service.import_annotations(
            video_id=video_id,
            annotation_data=annotation_data,
            annotator_id=current_user.id,
            format_type=format_type
        )
        
        return APIResponse.success_response(
            data=result,
            message=f"Import completed: {result['imported_count']} annotations imported"
        )
        
    except Exception as e:
        raise HTTPException(500, f"Failed to import annotations: {str(e)}")
```

This completes the functionality gaps documentation. The implementation continues with LabJack integration and test execution systems in the next sections.