# Implementation Fixes Guided by London School TDD

## Overview
This document outlines the specific fixes needed to resolve the issues identified through SPARC TDD analysis, with implementations guided by London School TDD principles.

## Critical Fixes Required

### 1. Backend Schema Consistency Issues

**Problem**: Field name mismatches between Pydantic schemas and database models.

**London School TDD Fix**:
```python
# First, write the test that specifies the desired behavior
def test_project_schema_serialization_matches_api_contract():
    # GIVEN - Mock database project with snake_case fields
    mock_db_project = Project(
        id="123",
        camera_model="Test Camera",
        camera_view="Front View",
        signal_type="GPIO"
    )
    
    # Mock database session
    mock_db = Mock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_db_project
    
    # WHEN - API endpoint serializes response
    response = get_project_endpoint(project_id="123", db=mock_db)
    
    # THEN - Response should use camelCase as per API contract
    assert response["cameraModel"] == "Test Camera"
    assert response["cameraView"] == "Front View"
    assert response["signalType"] == "GPIO"

# Implementation guided by test:
class ProjectResponse(ProjectBase):
    id: str
    status: str
    owner_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Fix: Use field aliases to match frontend expectations
    camera_model: str = Field(alias="cameraModel")
    camera_view: str = Field(alias="cameraView")
    signal_type: str = Field(alias="signalType")

    class Config:
        from_attributes = True
        populate_by_name = True  # Allow both snake_case and camelCase
```

### 2. Frontend Dependency and Configuration Issues

**Problem**: Missing react-router-dom and incorrect API base URL.

**London School TDD Fix**:
```typescript
// First, write integration test to specify expected behavior
describe('App Router Integration', () => {
  it('should navigate between routes using router service', () => {
    // GIVEN - Mock router service
    const mockRouterService = {
      navigate: jest.fn(),
      getCurrentRoute: jest.fn().mockReturnValue('/projects')
    };
    
    // WHEN - User navigates to projects
    const appController = new AppController(mockRouterService);
    appController.navigateToProjects();
    
    // THEN - Router service should be called
    expect(mockRouterService.navigate).toHaveBeenCalledWith('/projects');
  });
});

// Fix dependencies in package.json:
{
  "dependencies": {
    "react-router-dom": "^6.8.0",  // Add missing dependency
    // ... other deps
  }
}

// Fix API base URL configuration:
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
// Changed from 8001 to 8000 to match backend
```

### 3. Test Configuration Issues

**Problem**: Jest not configured for ES modules and missing test setup.

**London School TDD Fix**:
```json
// jest.config.js
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.ts'],
  transform: {
    '^.+\\.(ts|tsx)$': 'ts-jest',
    '^.+\\.(js|jsx)$': 'babel-jest',
  },
  transformIgnorePatterns: [
    'node_modules/(?!(axios)/)'  // Transform axios ES modules
  ],
  moduleNameMapper: {
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
  },
};

// setupTests.ts - Mock all external dependencies
import '@testing-library/jest-dom';

// Mock API service for all tests
jest.mock('./services/api', () => ({
  createProject: jest.fn(),
  getProjects: jest.fn(),
  // ... other API methods
}));

// Mock react-router-dom
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => jest.fn(),
  useLocation: () => ({ pathname: '/test' }),
}));
```

### 4. Backend Test Database Session Issues

**Problem**: Test database session setup is incorrect.

**London School TDD Fix**:
```python
# conftest.py - Proper test fixtures with mocked dependencies
import pytest
from unittest.mock import Mock
from sqlalchemy.orm import Session

@pytest.fixture
def mock_db_session():
    """Mock database session following London School principles"""
    mock_session = Mock(spec=Session)
    
    # Setup default mock behaviors
    mock_session.add = Mock()
    mock_session.commit = Mock()
    mock_session.rollback = Mock()
    mock_session.query = Mock()
    
    return mock_session

@pytest.fixture
def mock_project_service(mock_db_session):
    """Mock project service with injected dependencies"""
    return ProjectService(
        db_session=mock_db_session,
        audit_service=Mock(),
        notification_service=Mock()
    )

# Updated test using proper mocks:
def test_create_project_success(mock_project_service, mock_db_session):
    # GIVEN - Project data and expected result
    project_data = ProjectCreate(
        name="Test Project",
        camera_model="Test Camera",
        camera_view="Front-facing VRU", 
        signal_type="GPIO"
    )
    
    expected_project = Project(id="123", name="Test Project")
    mock_db_session.refresh.return_value = expected_project
    
    # WHEN - Project is created
    result = mock_project_service.create(project_data, user_id="test-user")
    
    # THEN - Verify database interactions
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    assert result == expected_project
```

### 5. CORS and API Contract Issues

**Problem**: CORS not properly configured and API contract mismatches.

**London School TDD Fix**:
```python
# First, write test to specify CORS behavior
def test_cors_headers_allow_frontend_requests():
    # GIVEN - Mock request from frontend origin
    mock_request = Mock()
    mock_request.headers = {"Origin": "http://localhost:3000"}
    
    cors_handler = CorsHandler(allowed_origins=["http://localhost:3000"])
    
    # WHEN - CORS headers are processed
    headers = cors_handler.get_response_headers(mock_request)
    
    # THEN - Proper CORS headers should be set
    assert headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert "GET" in headers["Access-Control-Allow-Methods"]
    assert "POST" in headers["Access-Control-Allow-Methods"]

# Implementation fix:
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Fix API contract consistency:
@app.post("/api/projects", response_model=ProjectResponse)
async def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    # Ensure response uses correct field names
    db_project = create_project_crud(db=db, project=project)
    
    # Convert to response model with proper field aliases
    return ProjectResponse.from_orm(db_project)
```

## Implementation Priority (Test-Driven)

### Phase 1: Core Contract Fixes
1. Fix Pydantic schema field aliases
2. Update API response serialization
3. Correct frontend API base URL
4. Install missing dependencies

### Phase 2: Test Infrastructure
1. Configure Jest for ES modules
2. Setup proper mock dependencies
3. Create test fixtures and utilities
4. Implement London School test patterns

### Phase 3: Service Integration
1. Implement dependency injection
2. Add proper error handling
3. Create service orchestration
4. Add audit and logging

### Phase 4: End-to-End Validation
1. Integration tests with real API calls
2. Frontend-backend contract verification
3. Complete user workflow testing
4. Performance and error scenario testing

## London School TDD Implementation Pattern

Every fix follows this pattern:

```typescript
// 1. Write failing test that specifies desired behavior
describe('Feature Name', () => {
  it('should coordinate with dependencies to achieve outcome', () => {
    // GIVEN - Mock all external dependencies
    const mockDependency = jest.fn();
    
    // WHEN - Execute the behavior
    const result = serviceUnderTest.method(mockDependency);
    
    // THEN - Verify interactions, not state
    expect(mockDependency).toHaveBeenCalledWith(expectedArgs);
    expect(result).toBe(expectedOutcome);
  });
});

// 2. Implement minimal code to make test pass
// 3. Refactor while keeping tests green
// 4. Add more behaviors through additional tests
```

## Success Metrics

- All backend tests pass (currently 5 failing)
- All frontend tests pass (currently 6 failing)  
- API contracts match between frontend and backend
- Complete user workflows function end-to-end
- Proper error handling and user feedback
- 95%+ test coverage with London School style tests

This implementation plan ensures that every fix is driven by tests that specify the desired behavior, following London School TDD principles of mocking dependencies and testing interactions.