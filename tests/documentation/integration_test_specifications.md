# Integration Test Specifications - AI Model Validation Platform

## Overview

Integration tests validate the interaction between different components of the AI Model Validation Platform. These tests ensure that the system works correctly when components are combined, focusing on data flow, API contracts, and service interactions.

## Backend Integration Tests

### 1. API-Database Integration Tests

#### Project Management Integration
```python
class TestProjectIntegration:
    """Test project management with real database operations."""
    
    def test_create_project_full_workflow(self, client, auth_headers, test_db):
        """Test complete project creation workflow with database persistence."""
        # Arrange
        project_data = {
            "name": "Highway VRU Detection Test",
            "description": "Integration test project",
            "camera_model": "FLIR Blackfly S",
            "camera_view": "Front-facing VRU",
            "lens_type": "Wide-angle",
            "resolution": "1920x1080",
            "frame_rate": 30,
            "signal_type": "GPIO"
        }
        
        # Act
        response = client.post(
            "/api/projects",
            json=project_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 201
        project_response = response.json()
        assert project_response["name"] == project_data["name"]
        assert "id" in project_response
        
        # Verify database persistence
        db_project = test_db.query(Project).filter_by(
            id=project_response["id"]
        ).first()
        assert db_project is not None
        assert db_project.name == project_data["name"]
    
    def test_get_projects_with_pagination(self, client, auth_headers, test_db):
        """Test project retrieval with pagination and database queries."""
        # Arrange - Create multiple projects
        projects = []
        for i in range(15):
            project = Project(
                name=f"Test Project {i}",
                camera_model="Test Camera",
                camera_view="Front-facing VRU",
                signal_type="GPIO",
                owner_id=get_current_user_id(auth_headers)
            )
            test_db.add(project)
            projects.append(project)
        test_db.commit()
        
        # Act - Get first page
        response = client.get(
            "/api/projects?skip=0&limit=10",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        projects_response = response.json()
        assert len(projects_response) == 10
        
        # Act - Get second page
        response = client.get(
            "/api/projects?skip=10&limit=10",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        projects_response = response.json()
        assert len(projects_response) == 5
```

#### Video Upload and Processing Integration
```python
class TestVideoProcessingIntegration:
    """Test video upload with file storage and database integration."""
    
    def test_video_upload_with_file_storage(
        self, 
        client, 
        auth_headers, 
        test_project, 
        test_video_file,
        mock_file_storage
    ):
        """Test video upload creates database record and stores file."""
        # Act
        with open(test_video_file, 'rb') as video:
            response = client.post(
                f"/api/projects/{test_project.id}/videos",
                files={"file": ("test_video.mp4", video, "video/mp4")},
                headers=auth_headers
            )
        
        # Assert API response
        assert response.status_code == 200
        video_response = response.json()
        assert video_response["filename"] == "test_video.mp4"
        assert video_response["status"] == "uploaded"
        
        # Verify database record
        video_record = test_db.query(Video).filter_by(
            id=video_response["video_id"]
        ).first()
        assert video_record is not None
        assert video_record.project_id == test_project.id
        
        # Verify file storage
        mock_file_storage.save_file.assert_called_once()
    
    def test_ground_truth_generation_integration(
        self,
        client,
        auth_headers,
        test_video_with_ground_truth,
        mock_ground_truth_service
    ):
        """Test ground truth retrieval after video processing."""
        # Arrange - Video with processed ground truth
        video_id = test_video_with_ground_truth.id
        mock_ground_truth_service.get_ground_truth.return_value = {
            "video_id": video_id,
            "objects": [
                {
                    "timestamp": 10.5,
                    "class_label": "pedestrian",
                    "bounding_box": {"x": 100, "y": 100, "width": 50, "height": 100},
                    "confidence": 0.95
                }
            ]
        }
        
        # Act
        response = client.get(
            f"/api/videos/{video_id}/ground-truth",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        ground_truth = response.json()
        assert len(ground_truth["objects"]) == 1
        assert ground_truth["objects"][0]["class_label"] == "pedestrian"
```

### 2. Service Layer Integration Tests

#### Authentication Service Integration
```python
class TestAuthServiceIntegration:
    """Test authentication service with database and JWT operations."""
    
    def test_user_registration_and_login_flow(self, test_db, client):
        """Test complete user registration and authentication flow."""
        # Step 1: Register new user
        user_data = {
            "email": "integration@test.com",
            "password": "securepassword123",
            "full_name": "Integration Test User"
        }
        
        auth_service = AuthService()
        user_response = auth_service.register_user(UserCreate(**user_data))
        
        # Verify user creation in database
        db_user = test_db.query(User).filter_by(
            email=user_data["email"]
        ).first()
        assert db_user is not None
        assert db_user.email == user_data["email"]
        
        # Step 2: Authenticate user
        authenticated_user = auth_service.authenticate_user(
            user_data["email"],
            user_data["password"]
        )
        assert authenticated_user is not None
        assert authenticated_user["email"] == user_data["email"]
        
        # Step 3: Create JWT token
        token = auth_service.create_access_token(
            data={"sub": authenticated_user["id"], "email": authenticated_user["email"]}
        )
        assert token is not None
        
        # Step 4: Verify token
        verified_user = auth_service.verify_token(token)
        assert verified_user is not None
        assert verified_user["email"] == user_data["email"]
    
    def test_protected_endpoint_with_auth_integration(self, client, test_user):
        """Test protected endpoint access with authentication."""
        # Create valid JWT token
        auth_service = AuthService()
        token = auth_service.create_access_token(
            data={"sub": str(test_user.id), "email": test_user.email}
        )
        
        # Test access to protected endpoint
        response = client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        
        # Test access without token
        response = client.get("/api/projects")
        assert response.status_code == 401
        
        # Test access with invalid token
        response = client.get(
            "/api/projects",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401
```

#### Validation Service Integration  
```python
class TestValidationServiceIntegration:
    """Test validation service with database and detection processing."""
    
    def test_detection_validation_with_database_lookup(
        self,
        test_db,
        test_session_with_ground_truth
    ):
        """Test detection validation against stored ground truth."""
        # Arrange
        validation_service = ValidationService()
        test_session = test_session_with_ground_truth
        
        # Create ground truth objects in database
        ground_truth_objects = [
            GroundTruthObject(
                video_id=test_session.video_id,
                timestamp=10.5,
                class_label="pedestrian",
                bounding_box={"x": 100, "y": 100, "width": 50, "height": 100},
                confidence=0.95
            ),
            GroundTruthObject(
                video_id=test_session.video_id,
                timestamp=25.2,
                class_label="cyclist", 
                bounding_box={"x": 300, "y": 150, "width": 60, "height": 80},
                confidence=0.88
            )
        ]
        
        for obj in ground_truth_objects:
            test_db.add(obj)
        test_db.commit()
        
        # Act - Test True Positive detection
        result_tp = validation_service.validate_detection(
            test_session_id=str(test_session.id),
            timestamp=10.6,  # Within 100ms tolerance
            confidence=0.87
        )
        assert result_tp == "TP"
        
        # Act - Test False Positive detection  
        result_fp = validation_service.validate_detection(
            test_session_id=str(test_session.id),
            timestamp=15.0,  # No ground truth at this time
            confidence=0.75
        )
        assert result_fp == "FP"
    
    def test_session_results_compilation(
        self,
        test_db,
        test_session_with_complete_data
    ):
        """Test complete session results compilation from database."""
        # Arrange
        validation_service = ValidationService()
        test_session = test_session_with_complete_data
        
        # Create detection events
        detection_events = [
            DetectionEvent(
                test_session_id=test_session.id,
                timestamp=10.5,
                confidence=0.87,
                class_label="pedestrian",
                validation_result="TP"
            ),
            DetectionEvent(
                test_session_id=test_session.id,
                timestamp=15.0,
                confidence=0.75,
                class_label="pedestrian", 
                validation_result="FP"
            ),
            DetectionEvent(
                test_session_id=test_session.id,
                timestamp=25.1,
                confidence=0.82,
                class_label="cyclist",
                validation_result="TP"
            )
        ]
        
        for event in detection_events:
            test_db.add(event)
        test_db.commit()
        
        # Act
        results = validation_service.get_session_results(str(test_session.id))
        
        # Assert
        assert results is not None
        assert results.total_detections == 3
        assert results.metrics.true_positives == 2
        assert results.metrics.false_positives == 1
        assert results.metrics.precision == 2/3  # TP/(TP+FP)
```

### 3. WebSocket Integration Tests

#### Real-time Detection Processing
```python  
class TestWebSocketIntegration:
    """Test WebSocket connections for real-time detection events."""
    
    def test_raspberry_pi_detection_stream(
        self,
        websocket_client,
        test_session,
        mock_validation_service
    ):
        """Test real-time detection event processing via WebSocket."""
        # Arrange
        websocket_client.connect("ws://localhost:8000/ws/detection")
        
        # Mock validation service responses
        mock_validation_service.validate_detection.return_value = "TP"
        
        # Act - Send detection event
        detection_event = {
            "test_session_id": str(test_session.id),
            "timestamp": 12.5,
            "confidence": 0.89,
            "class_label": "pedestrian"
        }
        websocket_client.send(detection_event)
        
        # Wait for response
        time.sleep(0.5)
        messages = websocket_client.get_messages()
        
        # Assert
        assert len(messages) == 1
        response = messages[0]
        assert response["validation_result"] == "TP"
        assert response["status"] == "processed"
    
    def test_multiple_client_connection_handling(
        self,
        websocket_client_factory
    ):
        """Test handling multiple WebSocket connections simultaneously."""
        # Arrange
        clients = []
        for i in range(5):
            client = websocket_client_factory()
            client.connect("ws://localhost:8000/ws/detection")
            clients.append(client)
        
        # Act - Send events from multiple clients
        for i, client in enumerate(clients):
            detection_event = {
                "test_session_id": f"session-{i}",
                "timestamp": 10.0 + i,
                "confidence": 0.8 + (i * 0.02),
                "class_label": "pedestrian"
            }
            client.send(detection_event)
        
        # Wait for all responses
        time.sleep(1.0)
        
        # Assert all clients received responses
        for client in clients:
            messages = client.get_messages()
            assert len(messages) == 1
```

## Frontend Integration Tests

### 1. API Client Integration

#### Authentication Integration
```javascript
describe('Authentication Integration', () => {
  test('login flow with token storage', async () => {
    // Arrange
    const mockResponse = {
      access_token: 'mock-jwt-token',
      token_type: 'bearer',
      user: {
        id: '123',
        email: 'test@example.com',
        full_name: 'Test User'
      }
    };
    
    jest.spyOn(window, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse)
    });
    
    // Act
    const authService = new AuthService();
    const result = await authService.login('test@example.com', 'password');
    
    // Assert
    expect(result).toEqual(mockResponse);
    expect(localStorage.getItem('access_token')).toBe('mock-jwt-token');
    expect(localStorage.getItem('user')).toBe(JSON.stringify(mockResponse.user));
  });
  
  test('automatic token refresh on 401 response', async () => {
    // Arrange - Mock 401 response followed by successful refresh
    jest.spyOn(window, 'fetch')
      .mockResolvedValueOnce({
        ok: false,
        status: 401
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ access_token: 'new-token' })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ data: 'success' })
      });
    
    // Act
    const apiClient = new ApiClient();
    const result = await apiClient.get('/api/projects');
    
    // Assert
    expect(result.data).toBe('success');
    expect(localStorage.getItem('access_token')).toBe('new-token');
  });
});
```

#### Project Management Integration
```javascript
describe('Project Management Integration', () => {
  test('create project with form validation', async () => {
    // Arrange
    render(
      <BrowserRouter>
        <CreateProjectDialog open={true} onClose={() => {}} />
      </BrowserRouter>
    );
    
    const mockCreateProject = jest.spyOn(projectService, 'createProject')
      .mockResolvedValue({
        id: '123',
        name: 'Test Project',
        status: 'Active'
      });
    
    // Act - Fill form and submit
    fireEvent.change(screen.getByLabelText('Project Name'), {
      target: { value: 'Test Project' }
    });
    fireEvent.change(screen.getByLabelText('Camera Model'), {
      target: { value: 'FLIR Blackfly S' }
    });
    fireEvent.click(screen.getByText('Create Project'));
    
    // Wait for async operations
    await waitFor(() => {
      expect(mockCreateProject).toHaveBeenCalledWith({
        name: 'Test Project',
        camera_model: 'FLIR Blackfly S',
        // ... other form fields
      });
    });
    
    // Assert success state
    expect(screen.getByText('Project created successfully')).toBeInTheDocument();
  });
  
  test('project list with real-time updates', async () => {
    // Arrange - Mock WebSocket connection
    const mockWebSocket = {
      onmessage: null,
      send: jest.fn(),
      close: jest.fn()
    };
    global.WebSocket = jest.fn(() => mockWebSocket);
    
    render(<ProjectsList />);
    
    // Assert initial render
    expect(screen.getByText('Loading projects...')).toBeInTheDocument();
    
    // Act - Simulate WebSocket project update
    await act(async () => {
      mockWebSocket.onmessage({
        data: JSON.stringify({
          type: 'project_updated',
          project: {
            id: '123',
            name: 'Updated Project',
            status: 'Completed'
          }
        })
      });
    });
    
    // Assert real-time update
    expect(screen.getByText('Updated Project')).toBeInTheDocument();
    expect(screen.getByText('Completed')).toBeInTheDocument();
  });
});
```

### 2. Component Integration Tests

#### Dashboard Integration
```javascript
describe('Dashboard Integration', () => {
  test('dashboard data aggregation from multiple services', async () => {
    // Arrange - Mock multiple service calls
    jest.spyOn(projectService, 'getProjects').mockResolvedValue([
      { id: '1', name: 'Project 1', status: 'Active' },
      { id: '2', name: 'Project 2', status: 'Completed' }
    ]);
    
    jest.spyOn(sessionService, 'getRecentSessions').mockResolvedValue([
      { id: '1', name: 'Session 1', status: 'Running' }
    ]);
    
    jest.spyOn(analyticsService, 'getSystemMetrics').mockResolvedValue({
      totalTests: 150,
      successRate: 0.92,
      averageAccuracy: 0.87
    });
    
    // Act
    render(<Dashboard />);
    
    // Wait for all async data loading
    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument(); // Project count
      expect(screen.getByText('1')).toBeInTheDocument(); // Active sessions
      expect(screen.getByText('92%')).toBeInTheDocument(); // Success rate
    });
    
    // Assert data integration
    expect(projectService.getProjects).toHaveBeenCalled();
    expect(sessionService.getRecentSessions).toHaveBeenCalled();
    expect(analyticsService.getSystemMetrics).toHaveBeenCalled();
  });
});
```

## Database Integration Tests

### 1. Transaction Management

```python
class TestDatabaseTransactions:
    """Test database transaction handling and rollback scenarios."""
    
    def test_transaction_rollback_on_service_error(
        self,
        test_db,
        mock_file_storage_error
    ):
        """Test database rollback when service operation fails."""
        # Arrange
        initial_project_count = test_db.query(Project).count()
        
        project_data = {
            "name": "Test Project",
            "camera_model": "Test Camera",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        # Mock file storage to raise exception
        mock_file_storage_error.side_effect = Exception("Storage failed")
        
        # Act & Assert
        with pytest.raises(Exception, match="Storage failed"):
            with test_db.begin():
                # This should be rolled back
                create_project(test_db, project_data, user_id="test-user")
                # Simulate file storage operation that fails
                mock_file_storage_error()
        
        # Assert rollback occurred
        final_project_count = test_db.query(Project).count()
        assert final_project_count == initial_project_count
    
    def test_concurrent_database_operations(self, test_db):
        """Test handling of concurrent database operations."""
        import threading
        import time
        
        results = []
        errors = []
        
        def create_project_worker(worker_id):
            try:
                project = Project(
                    name=f"Concurrent Project {worker_id}",
                    camera_model="Test Camera",
                    camera_view="Front-facing VRU", 
                    signal_type="GPIO",
                    owner_id="test-user"
                )
                test_db.add(project)
                test_db.commit()
                results.append(project.id)
            except Exception as e:
                errors.append(str(e))
        
        # Act - Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_project_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Assert
        assert len(errors) == 0
        assert len(results) == 10
        assert len(set(results)) == 10  # All unique IDs
```

### 2. Data Consistency Tests

```python
class TestDataConsistency:
    """Test data consistency across related entities."""
    
    def test_cascade_operations_maintain_consistency(self, test_db):
        """Test cascade delete maintains referential integrity."""
        # Arrange - Create project with videos and sessions
        project = Project(
            name="Test Project",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO",
            owner_id="test-user"
        )
        test_db.add(project)
        test_db.flush()
        
        video = Video(
            filename="test.mp4",
            file_path="/test/path.mp4",
            project_id=project.id
        )
        test_db.add(video)
        test_db.flush()
        
        test_session = TestSession(
            name="Test Session",
            project_id=project.id,
            video_id=video.id
        )
        test_db.add(test_session)
        test_db.commit()
        
        # Record initial counts
        initial_video_count = test_db.query(Video).count()
        initial_session_count = test_db.query(TestSession).count()
        
        # Act - Delete project
        test_db.delete(project)
        test_db.commit()
        
        # Assert cascade deletion
        final_video_count = test_db.query(Video).count()
        final_session_count = test_db.query(TestSession).count()
        
        assert final_video_count == initial_video_count - 1
        assert final_session_count == initial_session_count - 1
```

## Performance Integration Tests

### 1. API Performance Under Load

```python
class TestAPIPerformanceIntegration:
    """Test API performance with realistic load scenarios."""
    
    @pytest.mark.performance
    def test_concurrent_video_uploads(
        self,
        client,
        auth_headers,
        test_project,
        performance_monitor
    ):
        """Test API performance with concurrent video uploads."""
        import threading
        import time
        
        upload_times = []
        errors = []
        
        def upload_video_worker():
            try:
                start_time = time.time()
                
                with open("test_video.mp4", "rb") as video:
                    response = client.post(
                        f"/api/projects/{test_project.id}/videos",
                        files={"file": ("test.mp4", video, "video/mp4")},
                        headers=auth_headers
                    )
                
                end_time = time.time()
                upload_times.append(end_time - start_time)
                
                if response.status_code != 200:
                    errors.append(f"HTTP {response.status_code}")
                    
            except Exception as e:
                errors.append(str(e))
        
        # Act - Simulate 10 concurrent uploads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=upload_video_worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Assert performance requirements
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(upload_times) == 10
        
        avg_upload_time = sum(upload_times) / len(upload_times)
        max_upload_time = max(upload_times)
        
        # Performance assertions (adjust based on requirements)
        assert avg_upload_time < 5.0, f"Average upload time too slow: {avg_upload_time}s"
        assert max_upload_time < 10.0, f"Max upload time too slow: {max_upload_time}s"
```

## Test Configuration and Fixtures

### Backend Integration Test Configuration
```python
# conftest.py additions for integration tests

@pytest.fixture(scope="function")
def test_db_with_data(test_db):
    """Test database with sample data loaded."""
    # Create sample users
    user1 = User(
        email="user1@test.com",
        hashed_password="hashed_password",
        full_name="Test User 1"
    )
    user2 = User(
        email="user2@test.com", 
        hashed_password="hashed_password",
        full_name="Test User 2"
    )
    test_db.add_all([user1, user2])
    test_db.flush()
    
    # Create sample projects
    project1 = Project(
        name="Integration Test Project 1",
        camera_model="FLIR Blackfly S",
        camera_view="Front-facing VRU",
        signal_type="GPIO",
        owner_id=user1.id
    )
    test_db.add(project1)
    test_db.commit()
    
    return test_db

@pytest.fixture
def integration_test_client(test_db_with_data):
    """Test client configured for integration testing."""
    app.dependency_overrides[get_db] = lambda: test_db_with_data
    
    with TestClient(app) as client:
        yield client
    
    # Cleanup
    app.dependency_overrides.clear()
```

### Frontend Integration Test Setup
```javascript
// setupTests.js for React integration tests

import '@testing-library/jest-dom';
import { server } from './mocks/server';

// Mock WebSocket globally for integration tests
global.WebSocket = jest.fn(() => ({
  close: jest.fn(),
  send: jest.fn(),
  onopen: null,
  onmessage: null,
  onerror: null,
  onclose: null
}));

// Setup MSW server for API mocking
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
global.localStorage = localStorageMock;
```

This comprehensive integration test specification ensures that all component interactions are thoroughly tested while maintaining realistic test scenarios that validate the complete system workflow.