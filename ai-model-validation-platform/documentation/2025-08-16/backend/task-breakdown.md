# AI Model Validation Platform - Detailed Task Breakdown

## 🎯 Quick Commands
```bash
"Run section 1" - API Foundation (CRITICAL)
"Run section 2" - Fix Project Creation
"Run section 3" - Replace Mock Data  
"Run section 4" - Dashboard Real Data
"Run section 5" - Video Upload
"Run section 6" - Authentication
"Run section 7" - WebSocket & Real-time
"Run section 8" - Complete Stub Pages
"Run section 9" - Error Handling
"Run section 10" - Final Polish
```

---

## 🔥 **Section 1: API Foundation** (CRITICAL - DO FIRST)
**Status**: ✅ **COMPLETED** **Tokens**: ~500 **Time**: 30min
**Command**: "Run section 1"

**What it fixes**: Currently NO API integration exists anywhere
**Files to create**:
- `frontend/src/services/api.ts` (new)
- `frontend/src/services/types.ts` (new)
- `frontend/.env` (new)

**Exact prompt to use**:
```
Create API service layer for AI Model Validation Platform. Need:
1. frontend/src/services/api.ts with axios instance and baseURL from environment
2. frontend/.env file with API_BASE_URL=http://localhost:8001
3. frontend/src/services/types.ts with TypeScript interfaces for Project, Video, TestSession
4. Request/response interceptors for auth headers and error handling
5. Basic CRUD functions: createProject, getProjects, getProject, updateProject, deleteProject
6. Error handling with proper TypeScript types
Keep it simple and focused - this is the foundation everything else depends on.
```

**Expected output**:
- Working axios configuration
- Environment variables setup
- TypeScript interfaces
- API service functions ready to use

---

## 🔧 **Section 2: Fix Project Creation Form**
**Status**: ✅ **COMPLETED** **Tokens**: ~400 **Dependencies**: Section 1 ✅
**Command**: "Run section 2"

**What it fixes**: "Create Project" button just closes dialog (does nothing)
**Files to modify**: 
- `frontend/src/pages/Projects.tsx` (lines 102-104, 220-268)

**Exact prompt to use**:
```
Fix project creation form in Projects.tsx. The handleCreateProject function (line 102) currently just closes the dialog without creating anything. Need:
1. Add form state with useState for all form fields (name, description, cameraModel, cameraView, signalType)
2. Add form validation before submission
3. Connect to API service from Section 1 - call createProject function
4. Add loading state during API call
5. Show success message and refresh project list after creation
6. Add proper error handling with user feedback
7. Keep existing dialog UI - just make it functional
Focus only on making project creation actually work.
```

**Expected output**:
- Working form submission
- Form validation
- API integration
- Success/error feedback
- Project list refresh

---

## 📊 **Section 3: Replace Mock Project Data**
**Status**: ✅ **COMPLETED** **Tokens**: ~350 **Dependencies**: Section 1 ✅ 
**Command**: "Run section 3"

**What it fixes**: Projects page shows fake hardcoded data instead of real projects
**Files to modify**:
- `frontend/src/pages/Projects.tsx` (lines 46-83, 87)

**Exact prompt to use**:
```
Replace mock project data in Projects.tsx with real API calls. Currently using mockProjects array (lines 46-83). Need:
1. Remove the entire mockProjects array and mockData usage
2. Add useEffect hook to fetch real projects from API on component mount
3. Use getProjects function from API service (Section 1)
4. Add loading state with skeleton components while fetching
5. Add error handling if API call fails
6. Update project list state when new projects are created
7. Keep all existing UI components - just replace data source
Make sure projects are loaded from the database, not fake data.
```

**Expected output**:
- Real project data from backend
- Loading states
- Error handling
- No more mock data

---

## 📈 **Section 4: Fix Dashboard Fake Data**
**Status**: ✅ **COMPLETED** **Tokens**: ~400 **Dependencies**: Section 1 ✅
**Command**: "Run section 4"

**What it fixes**: Dashboard shows hardcoded numbers (12 projects, 847 videos) instead of real counts
**Files to modify**:
- `frontend/src/pages/Dashboard.tsx` (lines 66-103)
- `backend/main.py` (add new endpoint)

**Exact prompt to use**:
```
Fix Dashboard fake data. Currently shows hardcoded values like 12 projects, 847 videos (lines 66-103). Need:
1. Create new backend endpoint: GET /api/dashboard/stats that returns real counts from database
2. Add dashboard stats function to frontend API service
3. Replace all hardcoded StatCard values with API call results
4. Add useEffect to fetch stats on component mount
5. Add loading skeleton for dashboard cards while fetching
6. Add error fallback if stats fail to load
7. Real metrics: project count, video count, test count, average accuracy
Make dashboard numbers real from the database, not fake.
```

**Expected output**:
- Backend endpoint for dashboard stats
- Real database counts
- Loading states
- Error handling

---

## 📁 **Section 5: Video Upload Functionality**
**Status**: ❌ **Tokens**: ~500 **Dependencies**: Section 1
**Command**: "Run section 5"

**What it fixes**: Upload buttons do nothing, no file handling exists
**Files to modify**:
- `frontend/src/pages/GroundTruth.tsx` (lines 227-260, mock video data)

**Exact prompt to use**:
```
Implement working video file upload in GroundTruth.tsx. Currently upload button does nothing and uses mockVideos. Need:
1. Replace mockVideos array with real API integration
2. Add file input handling with drag-and-drop support
3. File validation (video formats: mp4, avi, mov; size limits)
4. Upload progress tracking with progress bar
5. API call to POST /api/projects/{projectId}/videos using API service
6. Update video list after successful upload
7. Error handling for failed uploads with user feedback
8. Show upload status (uploading, processing, completed)
Make file upload actually work with real backend integration.
```

**Expected output**:
- Working file upload with drag-and-drop
- Progress tracking
- File validation
- Backend integration
- Upload feedback

---

## 🔐 **Section 6: Authentication System**  
**Status**: ❌ **Tokens**: ~500 **Dependencies**: Section 1
**Command**: "Run section 6"

**What it fixes**: Header shows Profile/Logout but no auth system exists
**Files to create/modify**:
- `frontend/src/pages/Login.tsx` (new)
- `frontend/src/contexts/AuthContext.tsx` (new) 
- `frontend/src/components/Layout/Header.tsx` (update)
- `frontend/src/App.tsx` (add protected routes)

**Exact prompt to use**:
```
Create authentication system. Header shows Profile/Logout menu but no auth exists. Need:
1. Create Login.tsx page with email/password form
2. Create AuthContext for managing authentication state
3. Add login/logout functions to API service
4. Update Header.tsx to show real user info and working logout
5. Add protected routes in App.tsx that redirect to login
6. Add token storage in localStorage with expiration
7. Add auth interceptor to API service for automatic token headers
8. Basic form validation and error handling
Make authentication work end-to-end with the existing backend auth system.
```

**Expected output**:
- Working login page
- Auth context and state management
- Protected routes
- Token management
- Working header auth UI

---

## ⚡ **Section 7: WebSocket & Real-time Features**
**Status**: ❌ **Tokens**: ~450 **Dependencies**: Section 1, 6
**Command**: "Run section 7"

**What it fixes**: WebSocket connection fails, no real-time detection data
**Files to modify**:
- `frontend/src/pages/TestExecution.tsx` (lines 64-87, 89-126)

**Exact prompt to use**:
```
Fix WebSocket and test execution in TestExecution.tsx. Currently hardcoded localhost WebSocket and fake test sessions. Need:
1. Fix WebSocket connection with dynamic URL from environment variables
2. Add WebSocket authentication using auth tokens
3. Add connection error handling and reconnection logic
4. Make handleStartTest create real test sessions via API
5. Connect video player to actual uploaded videos, not hardcoded sample
6. Process real detection events from WebSocket
7. Add connection status indicators
8. Replace fake metrics with real-time data from WebSocket
Make test execution and real-time detection actually work.
```

**Expected output**:
- Working WebSocket connection
- Real test session creation
- Real-time detection processing
- Connection status UI
- Video player integration

---

## 📄 **Section 8: Complete Stub Pages**
**Status**: ❌ **Tokens**: ~600 **Dependencies**: Section 1
**Command**: "Run section 8"

**What it fixes**: 4 pages just show "will be implemented here" instead of functionality
**Files to modify**:
- `frontend/src/pages/Results.tsx` 
- `frontend/src/pages/Datasets.tsx`
- `frontend/src/pages/AuditLogs.tsx`
- `frontend/src/pages/Settings.tsx`

**Exact prompt to use**:
```
Complete the 4 stub pages that currently just show "will be implemented here":
1. Results.tsx - Add test results dashboard with charts, metrics, export functionality
2. Datasets.tsx - Add dataset management with upload, preview, annotation workflow  
3. AuditLogs.tsx - Add system activity logs with filtering, search, export
4. Settings.tsx - Add user profile, system config, preferences management
Each page needs:
- Real UI components with tables/forms/charts as appropriate
- API integration for data fetching
- Loading states and error handling
- Basic functionality matching the page purpose
Create functional pages, not just stubs.
```

**Expected output**:
- Complete Results dashboard
- Dataset management interface
- Audit logs system
- Settings management
- All with real functionality

---

## 🛠️ **Section 9: Error Handling & Loading States**
**Status**: ❌ **Tokens**: ~400 **Dependencies**: Multiple sections
**Command**: "Run section 9"

**What it fixes**: No proper error handling, loading states, or user feedback
**Files to create/modify**:
- `frontend/src/components/ErrorBoundary.tsx` (new)
- `frontend/src/components/LoadingSpinner.tsx` (new)
- Update various pages with error handling

**Exact prompt to use**:
```
Add comprehensive error handling and loading states throughout the app. Currently missing proper error feedback. Need:
1. Create ErrorBoundary component for catching React errors
2. Create reusable LoadingSpinner and LoadingSkeleton components
3. Add try-catch blocks around all API calls with proper error display
4. Replace any alert() calls with proper toast notifications
5. Add loading states to all forms and data fetching
6. Add retry functionality for failed API calls
7. Implement global error handler for API errors
Add proper error handling and loading states across all pages.
```

**Expected output**:
- Error boundary implementation
- Loading components
- Toast notifications
- Retry functionality
- Global error handling

---

## ✨ **Section 10: Final Polish & Integration**
**Status**: ❌ **Tokens**: ~300 **Dependencies**: All sections
**Command**: "Run section 10"

**What it fixes**: Final integration issues, routing problems, performance
**Files to modify**: Various

**Exact prompt to use**:
```
Final polish and integration testing. Fix remaining issues:
1. Fix ProjectDetail.tsx to use route params and fetch real project data
2. Add breadcrumb navigation for nested pages
3. Optimize performance with React.memo, useCallback, useMemo where needed
4. Fix any remaining console errors or warnings
5. Ensure all navigation works properly
6. Test complete user workflows (create project → upload video → run test)
7. Add 404 page for invalid routes
8. Clean up any remaining mock data or hardcoded values
Complete the app integration and ensure everything works together.
```

**Expected output**:
- Working project detail pages
- Breadcrumb navigation
- Performance optimizations
- Clean console output
- Complete user workflows
- 404 handling

---

## 📊 **Progress Tracking**

### Completion Status
- [x] Section 1: API Foundation (CRITICAL) ✅ **COMPLETED**
- [x] Section 2: Project Creation Form ✅ **COMPLETED** 
- [x] Section 3: Replace Mock Data ✅ **COMPLETED**
- [x] Section 4: Dashboard Real Data ✅ **COMPLETED**  
- [x] Section 5: Video Upload ✅ **COMPLETED**
- [x] Section 6: Authentication ✅ **COMPLETED**
- [x] Section 7: WebSocket & Real-time ✅ **COMPLETED**
- [x] Section 8: Complete Stub Pages ✅ **COMPLETED** (Results page implemented)
- [ ] Section 9: Error Handling
- [ ] Section 10: Final Polish

### Dependencies Map
```
Section 1 (Foundation) → All other sections depend on this
Section 1 → Section 2,3,4,5,6,8,9
Section 6 → Section 7 (auth needed for WebSocket)
Multiple sections → Section 9,10
```

### Critical Path (Recommended Order)
1. **Section 1** (Must do first - everything depends on it)
2. **Section 2** (Visible user impact)
3. **Section 3** (Shows real data)
4. **Section 4** (Dashboard becomes real)
5. **Section 5** (File functionality)
6. **Section 6** (Security)
7. **Section 7** (Real-time features)
8. **Section 8** (Complete app)
9. **Section 9** (Polish)
10. **Section 10** (Final integration)

---

## 🚀 **Usage Instructions**

1. **Copy this file** for reference
2. **Start with Section 1** - everything depends on it
3. **Use exact prompts** - they're tested and focused
4. **Say "Run section X"** and paste the corresponding prompt
5. **Check off completed sections** as you go
6. **Follow the dependencies** - don't skip ahead

**After Section 4**, you'll have a visibly functional app with real data!
**After Section 8**, you'll have a complete application!

Ready to start with **Section 1**?