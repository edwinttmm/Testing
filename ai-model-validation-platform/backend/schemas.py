from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
# Using str for UUID compatibility with SQLite

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Project schemas
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    camera_model: str = Field(alias="cameraModel")
    camera_view: str = Field(alias="cameraView")  # 'Front-facing VRU', 'Rear-facing VRU', 'In-Cab Driver Behavior'
    lens_type: Optional[str] = Field(None, alias="lensType")
    resolution: Optional[str] = None
    frame_rate: Optional[int] = Field(None, alias="frameRate")
    signal_type: str = Field(alias="signalType")  # 'GPIO', 'Network Packet', 'Serial'
    
    class Config:
        populate_by_name = True

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(ProjectBase):
    name: Optional[str] = None
    camera_model: Optional[str] = None
    camera_view: Optional[str] = None
    signal_type: Optional[str] = None
    status: Optional[str] = None

class ProjectResponse(ProjectBase):
    id: str
    status: str
    owner_id: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Video schemas
class VideoBase(BaseModel):
    filename: str
    file_size: Optional[int] = None
    duration: Optional[float] = None
    fps: Optional[float] = None
    resolution: Optional[str] = None

class VideoResponse(VideoBase):
    id: str
    status: str
    ground_truth_generated: bool
    project_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class VideoUploadResponse(BaseModel):
    video_id: str
    filename: str
    status: str
    message: str

# Ground Truth schemas
class GroundTruthObject(BaseModel):
    id: str
    timestamp: float
    class_label: str
    bounding_box: Dict[str, Any]
    confidence: float

    class Config:
        from_attributes = True

class GroundTruthResponse(BaseModel):
    video_id: str
    objects: List[GroundTruthObject]
    total_detections: int
    status: str

# Test Session schemas
class TestSessionBase(BaseModel):
    name: str
    project_id: str
    video_id: str
    tolerance_ms: Optional[int] = 100

class TestSessionCreate(TestSessionBase):
    pass

class TestSessionResponse(TestSessionBase):
    id: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

# Detection Event schemas
class DetectionEvent(BaseModel):
    test_session_id: str
    timestamp: float
    confidence: Optional[float] = None
    class_label: Optional[str] = None

class DetectionEventResponse(DetectionEvent):
    id: str
    validation_result: Optional[str]
    ground_truth_match_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# Validation Result schemas
class ValidationMetrics(BaseModel):
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float

class ValidationResult(BaseModel):
    test_session_id: str
    metrics: ValidationMetrics
    detection_events: List[DetectionEventResponse]
    total_ground_truth: int
    total_detections: int

# Audit Log schemas
class AuditLogCreate(BaseModel):
    event_type: str
    event_data: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class AuditLogResponse(AuditLogCreate):
    id: str
    user_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# Authentication schemas
class LoginCredentials(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Dashboard schemas
class DashboardStats(BaseModel):
    project_count: int
    video_count: int
    test_session_count: int
    detection_event_count: int