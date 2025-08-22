# Unit Test Specifications - AI Model Validation Platform

## Backend Unit Test Specifications

### 1. FastAPI Endpoints (`main.py`)

#### Authentication Endpoints
```python
class TestAuthEndpoints:
    """Test authentication and user management endpoints."""
    
    def test_root_endpoint_returns_welcome_message(self):
        """Test the root endpoint returns correct welcome message."""
        # Expected: {"message": "AI Model Validation Platform API"}
        
    def test_health_check_endpoint_returns_healthy_status(self):
        """Test health check endpoint returns system status."""
        # Expected: {"status": "healthy"}
```

#### Project Management Endpoints
```python
class TestProjectEndpoints:
    """Test project CRUD operations."""
    
    def test_create_project_with_valid_data(self, authenticated_user):
        """Test creating a new project with valid data."""
        # Input: Valid ProjectCreate schema
        # Expected: ProjectResponse with generated UUID
        
    def test_create_project_requires_authentication(self):
        """Test project creation fails without authentication."""
        # Input: Valid project data without auth token
        # Expected: 401 Unauthorized
        
    def test_get_projects_returns_user_projects_only(self, authenticated_user):
        """Test project list returns only current user's projects."""
        # Setup: Create projects for multiple users
        # Expected: Only authenticated user's projects returned
        
    def test_get_project_detail_with_valid_id(self, authenticated_user):
        """Test retrieving specific project details."""
        # Setup: Create project with known ID
        # Expected: Complete project data returned
        
    def test_get_project_detail_with_invalid_id_returns_404(self):
        """Test retrieving non-existent project returns 404."""
        # Input: Non-existent project UUID
        # Expected: 404 Not Found error
        
    def test_get_project_detail_unauthorized_access_forbidden(self):
        """Test accessing another user's project returns 403."""
        # Setup: Project owned by different user
        # Expected: 403 Forbidden error
```

#### Video Upload Endpoints
```python
class TestVideoEndpoints:
    """Test video upload and management."""
    
    def test_upload_video_with_valid_file(self, authenticated_user, test_project):
        """Test successful video upload."""
        # Input: Valid video file, project ID
        # Expected: VideoUploadResponse with file details
        
    def test_upload_video_invalid_file_type_rejected(self):
        """Test non-video file upload rejection."""
        # Input: Text file with .mp4 extension
        # Expected: 400 Bad Request with validation error
        
    def test_upload_video_oversized_file_rejected(self):
        """Test file size limit enforcement."""
        # Input: Video file exceeding size limit
        # Expected: 413 Payload Too Large
        
    def test_upload_video_triggers_ground_truth_processing(self):
        """Test video upload starts background processing."""
        # Expected: ground_truth_service.process_video_async called
        
    def test_get_ground_truth_with_valid_video_id(self):
        """Test ground truth data retrieval."""
        # Setup: Video with processed ground truth
        # Expected: GroundTruthResponse with annotations
        
    def test_get_ground_truth_not_found_returns_404(self):
        """Test ground truth retrieval for non-existent video."""
        # Input: Invalid video ID
        # Expected: 404 Not Found error
```

#### Test Session Endpoints
```python
class TestSessionEndpoints:
    """Test session management and execution."""
    
    def test_create_test_session_with_valid_data(self):
        """Test test session creation."""
        # Input: Valid TestSessionCreate schema
        # Expected: TestSessionResponse with session details
        
    def test_list_test_sessions_with_project_filter(self):
        """Test filtering test sessions by project."""
        # Setup: Multiple sessions across different projects
        # Expected: Only sessions for specified project
        
    def test_get_test_results_with_completed_session(self):
        """Test results retrieval for completed session."""
        # Setup: Completed test session with results
        # Expected: ValidationResult with metrics
        
    def test_receive_detection_event_valid_data(self):
        """Test detection event processing from Raspberry Pi."""
        # Input: Valid DetectionEvent schema
        # Expected: Detection stored and validated
```

### 2. Authentication Service (`auth_service.py`)

```python
class TestAuthService:
    """Test authentication service functionality."""
    
    def test_password_hashing_and_verification(self):
        """Test password hashing is secure and verifiable."""
        # Input: Plain text password
        # Expected: Hash generated, verification succeeds
        
    def test_password_verification_fails_wrong_password(self):
        """Test incorrect password verification fails."""
        # Input: Wrong password for hash
        # Expected: Verification returns False
        
    def test_jwt_token_creation_valid_payload(self):
        """Test JWT token creation with user data."""
        # Input: User data dictionary
        # Expected: Valid JWT token string
        
    def test_jwt_token_verification_valid_token(self):
        """Test JWT token verification returns user data."""
        # Input: Valid JWT token
        # Expected: User data dictionary returned
        
    def test_jwt_token_verification_expired_token(self):
        """Test expired token verification fails."""
        # Input: Expired JWT token
        # Expected: None returned
        
    def test_jwt_token_verification_invalid_signature(self):
        """Test tampered token verification fails."""
        # Input: Token with modified signature
        # Expected: None returned
        
    def test_authenticate_user_valid_credentials(self):
        """Test user authentication with correct credentials."""
        # Setup: User in database with hashed password
        # Input: Correct email and password
        # Expected: User data returned
        
    def test_authenticate_user_invalid_email(self):
        """Test authentication fails with non-existent email."""
        # Input: Non-existent email address
        # Expected: None returned
        
    def test_authenticate_user_invalid_password(self):
        """Test authentication fails with wrong password."""
        # Setup: User in database
        # Input: Correct email, wrong password
        # Expected: None returned
        
    def test_register_user_new_email(self):
        """Test new user registration succeeds."""
        # Input: Valid UserCreate data
        # Expected: UserResponse with user details
        
    def test_register_user_existing_email_fails(self):
        """Test registration fails with existing email."""
        # Setup: User already exists with email
        # Input: UserCreate with same email
        # Expected: ValueError raised
```

### 3. Validation Service (`validation_service.py`)

```python
class TestValidationService:
    """Test detection validation logic."""
    
    def test_validate_detection_true_positive(self):
        """Test detection validation identifies true positive."""
        # Setup: Ground truth object at timestamp 10.5s
        # Input: Detection at timestamp 10.6s (within tolerance)
        # Expected: "TP" returned
        
    def test_validate_detection_false_positive(self):
        """Test detection validation identifies false positive."""
        # Setup: No ground truth objects
        # Input: Detection at any timestamp
        # Expected: "FP" returned
        
    def test_validate_detection_within_tolerance(self):
        """Test tolerance window correctly applied."""
        # Setup: Ground truth at 10.0s, tolerance 500ms
        # Input: Detection at 10.4s (within tolerance)
        # Expected: "TP" returned
        
    def test_validate_detection_outside_tolerance(self):
        """Test detection outside tolerance is false positive."""
        # Setup: Ground truth at 10.0s, tolerance 100ms
        # Input: Detection at 10.2s (outside tolerance)
        # Expected: "FP" returned
        
    def test_calculate_metrics_perfect_detection(self):
        """Test metrics calculation with 100% accuracy."""
        # Setup: 5 ground truth objects, 5 matching detections
        # Expected: precision=1.0, recall=1.0, f1=1.0
        
    def test_calculate_metrics_no_detections(self):
        """Test metrics calculation with no detections."""
        # Setup: 5 ground truth objects, 0 detections
        # Expected: precision=0, recall=0, f1=0
        
    def test_calculate_metrics_false_positives_only(self):
        """Test metrics calculation with only false positives."""
        # Setup: 0 ground truth objects, 3 detections
        # Expected: precision=0, recall=0, f1=0
        
    def test_calculate_metrics_mixed_results(self):
        """Test metrics calculation with mixed TP/FP/FN."""
        # Setup: 10 GT objects, 7 TP, 3 FP, 3 FN
        # Expected: precision=0.7, recall=0.7, f1=0.7
        
    def test_get_session_results_valid_session(self):
        """Test session results compilation."""
        # Setup: Completed test session with events
        # Expected: ValidationResult with complete metrics
        
    def test_get_session_results_invalid_session(self):
        """Test results retrieval for non-existent session."""
        # Input: Invalid session ID
        # Expected: None returned
        
    def test_generate_report_creates_summary(self):
        """Test report generation creates summary data."""
        # Setup: Test session with results
        # Expected: Report dictionary with formatted metrics
```

### 4. Database Models (`models.py`)

```python
class TestDatabaseModels:
    """Test SQLAlchemy model definitions and relationships."""
    
    def test_user_model_creation(self):
        """Test User model instance creation."""
        # Input: Valid user data
        # Expected: User instance with UUID, timestamps
        
    def test_user_model_email_uniqueness(self):
        """Test User email field uniqueness constraint."""
        # Setup: User with email "test@example.com"
        # Input: Another user with same email
        # Expected: IntegrityError raised
        
    def test_project_model_creation(self):
        """Test Project model instance creation."""
        # Input: Valid project data with user reference
        # Expected: Project instance with relationships
        
    def test_project_user_relationship(self):
        """Test Project-User relationship integrity."""
        # Setup: User and associated projects
        # Expected: user.projects returns correct projects
        
    def test_video_model_file_validation(self):
        """Test Video model file path validation."""
        # Input: Video with file path and metadata
        # Expected: Valid video instance
        
    def test_ground_truth_object_bbox_json_storage(self):
        """Test ground truth bounding box JSON serialization."""
        # Input: Bounding box dictionary
        # Expected: Proper JSON storage and retrieval
        
    def test_test_session_cascade_delete(self):
        """Test cascade deletion of related records."""
        # Setup: Test session with detection events
        # Action: Delete test session
        # Expected: Related detection events also deleted
        
    def test_detection_event_validation_result_enum(self):
        """Test detection event validation result values."""
        # Input: DetectionEvent with validation_result
        # Expected: Only 'TP', 'FP', 'FN' values accepted
        
    def test_audit_log_event_data_json_storage(self):
        """Test audit log JSON event data storage."""
        # Input: Complex event data dictionary
        # Expected: Proper serialization and deserialization
```

### 5. Database Operations (`crud.py`)

```python
class TestCRUDOperations:
    """Test database CRUD operations."""
    
    def test_create_user_valid_data(self, db_session):
        """Test user creation with valid data."""
        # Input: User email, hashed password, full name
        # Expected: User record created with UUID
        
    def test_get_user_by_email_existing_user(self, db_session):
        """Test user retrieval by email."""
        # Setup: User in database
        # Input: User's email address
        # Expected: User record returned
        
    def test_get_user_by_email_non_existent(self, db_session):
        """Test user retrieval with invalid email."""
        # Input: Non-existent email address
        # Expected: None returned
        
    def test_create_project_with_user_association(self, db_session):
        """Test project creation linked to user."""
        # Setup: User in database
        # Input: Project data with user_id
        # Expected: Project created with proper user relationship
        
    def test_get_projects_filtered_by_user(self, db_session):
        """Test project retrieval filtered by user."""
        # Setup: Multiple projects for different users
        # Input: Specific user_id
        # Expected: Only that user's projects returned
        
    def test_create_video_with_project_association(self, db_session):
        """Test video creation linked to project."""
        # Setup: Project in database
        # Input: Video data with project_id
        # Expected: Video created with proper project relationship
        
    def test_create_ground_truth_object_valid_data(self, db_session):
        """Test ground truth object creation."""
        # Setup: Video in database
        # Input: Ground truth data with video_id
        # Expected: Ground truth object created
        
    def test_get_ground_truth_objects_by_video(self, db_session):
        """Test ground truth retrieval for video."""
        # Setup: Video with multiple ground truth objects
        # Input: Video ID
        # Expected: All ground truth objects for video returned
        
    def test_create_test_session_valid_data(self, db_session):
        """Test test session creation."""
        # Setup: Project and video in database
        # Input: Test session data
        # Expected: Test session created with relationships
        
    def test_create_detection_event_valid_data(self, db_session):
        """Test detection event creation."""
        # Setup: Test session in database
        # Input: Detection event data
        # Expected: Detection event created and stored
```

## Frontend Unit Test Specifications

### 1. React Components

#### App Component (`App.tsx`)
```javascript
describe('App Component', () => {
  test('renders without crashing', () => {
    // Expected: Component mounts successfully
  });
  
  test('applies Material-UI theme correctly', () => {
    // Expected: Theme provider wraps application
  });
  
  test('renders router with all routes', () => {
    // Expected: All route components accessible
  });
  
  test('displays sidebar and header layout', () => {
    // Expected: Layout components rendered
  });
});
```

#### Dashboard Component
```javascript
describe('Dashboard Component', () => {
  test('displays project statistics cards', () => {
    // Setup: Mock project data
    // Expected: Statistics cards rendered
  });
  
  test('shows recent activity list', () => {
    // Setup: Mock activity data
    // Expected: Activity items displayed
  });
  
  test('handles loading state correctly', () => {
    // Setup: Async data loading
    // Expected: Loading indicators shown
  });
  
  test('handles error state gracefully', () => {
    // Setup: API error response
    // Expected: Error message displayed
  });
});
```

#### Project Components
```javascript
describe('Projects Component', () => {
  test('displays projects in data grid', () => {
    // Setup: Mock projects array
    // Expected: Projects listed in table
  });
  
  test('filters projects by search term', () => {
    // Input: Search query
    // Expected: Filtered results shown
  });
  
  test('opens create project dialog', () => {
    // Action: Click create button
    // Expected: Dialog opens with form
  });
  
  test('submits new project form', () => {
    // Input: Valid project data
    // Expected: API call made, project created
  });
  
  test('validates required project fields', () => {
    // Input: Incomplete project data
    // Expected: Validation errors shown
  });
});
```

### 2. Utility Functions and Services

#### API Client
```javascript
describe('API Client', () => {
  test('authenticates requests with JWT token', () => {
    // Setup: Mock token in localStorage
    // Expected: Authorization header added
  });
  
  test('handles 401 responses by redirecting to login', () => {
    // Setup: 401 response from API
    // Expected: Redirect to login page
  });
  
  test('retries failed requests with exponential backoff', () => {
    // Setup: Network failure simulation
    // Expected: Retry attempts made
  });
  
  test('transforms response data correctly', () => {
    // Setup: Raw API response
    // Expected: Transformed data structure
  });
});
```

## Test Data Fixtures

### Backend Test Fixtures
```python
@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "securepassword123"
    }

@pytest.fixture  
def sample_project_data():
    """Sample project data for testing."""
    return {
        "name": "Highway VRU Detection",
        "description": "Test project for highway pedestrian detection",
        "camera_model": "FLIR Blackfly S",
        "camera_view": "Front-facing VRU",
        "lens_type": "Wide-angle",
        "resolution": "1920x1080",
        "frame_rate": 30,
        "signal_type": "GPIO"
    }

@pytest.fixture
def sample_detection_event():
    """Sample detection event for validation testing."""
    return {
        "test_session_id": "test-session-uuid",
        "timestamp": 15.5,
        "confidence": 0.87,
        "class_label": "pedestrian"
    }
```

### Frontend Test Fixtures
```javascript
const mockProjectData = [
  {
    id: '1',
    name: 'Highway Detection',
    status: 'Active',
    created_at: '2024-01-15T10:00:00Z'
  },
  {
    id: '2', 
    name: 'Urban Intersection',
    status: 'Completed',
    created_at: '2024-01-14T15:30:00Z'
  }
];

const mockUser = {
  id: 'user-123',
  email: 'test@example.com',
  full_name: 'Test User'
};
```

## Coverage Requirements

### Backend Coverage Targets
- **Unit Tests**: 90% line coverage
- **Critical Paths**: 100% coverage
- **Error Handling**: 85% coverage
- **Service Layer**: 95% coverage

### Frontend Coverage Targets  
- **Components**: 85% coverage
- **Utility Functions**: 90% coverage
- **API Client**: 95% coverage
- **Form Validation**: 100% coverage

## Test Execution Commands

### Backend Testing
```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=src --cov-report=html

# Run specific test categories
pytest -m unit tests/
pytest -m "not slow" tests/

# Run with performance profiling
pytest tests/unit/ --profile
```

### Frontend Testing
```bash
# Run all unit tests
npm test

# Run with coverage
npm test -- --coverage

# Run in watch mode
npm test -- --watch

# Update snapshots
npm test -- --updateSnapshot
```

This comprehensive unit test specification ensures thorough testing of all individual components while maintaining clear test organization and high coverage standards.