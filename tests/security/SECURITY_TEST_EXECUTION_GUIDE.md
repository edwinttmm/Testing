# Security Test Execution Guide

## 🚨 CRITICAL: Multi-Tenancy Security Validation

This guide provides step-by-step instructions for executing comprehensive security tests to validate multi-tenancy fixes and prevent unauthorized data access vulnerabilities.

## 📋 Quick Start

### 1. Run Basic Security Validation (No Dependencies)
```bash
cd /home/rigade/Testing/tests/security
python3 run_basic_security_validation.py
```

### 2. Install Dependencies for Full Testing
```bash
# Install required packages
pip3 install pytest fastapi sqlalchemy

# Or use existing backend environment
source /home/rigade/Testing/ai-model-validation-platform/backend/venv/bin/activate
```

### 3. Run Full Security Test Suite
```bash
# Run comprehensive security tests
python3 test_security_runner.py

# Run individual test suites
python3 test_multi_tenant_security.py
python3 test_authentication_bypass.py  
python3 test_injection_vulnerabilities.py
python3 test_data_access_control.py
```

## 🎯 Expected Test Results

### ⚠️ Initial Run (Before Security Fixes)
```
🚨 EXPECTED BEHAVIOR: Tests should FAIL
✅ This demonstrates vulnerabilities exist
📋 Use failures to guide security implementation
```

**Example Expected Failures:**
```
🚨 VULNERABILITY: cross_user_project_access - Bob can access Alice's project
🚨 VULNERABILITY: unauthenticated_access - API endpoints accessible without auth  
🚨 VULNERABILITY: sql_injection_success - Database queries vulnerable to injection
🚨 VULNERABILITY: privilege_escalation - Regular user accessed admin endpoint
```

### ✅ After Security Fixes Applied
```
✅ EXPECTED BEHAVIOR: All tests should PASS
🔒 This proves vulnerabilities are fixed
🎉 Application ready for production
```

## 🔧 Security Fix Implementation

### Step 1: Identify Vulnerabilities
Run tests to see specific failures:
```bash
python3 run_basic_security_validation.py > security_results.txt 2>&1
```

### Step 2: Apply Multi-Tenancy Fixes

#### Database Query Filtering
```python
# ❌ VULNERABLE: Returns all projects
def get_projects(db: Session):
    return db.query(Project).all()

# ✅ SECURE: Filter by current user
def get_projects(db: Session, current_user: User):
    return db.query(Project).filter(
        Project.owner_id == current_user.id
    ).all()
```

#### Authentication Middleware
```python
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(token: str = Depends(security)):
    try:
        # Validate JWT token
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return get_user_by_id(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Apply to all protected endpoints
@app.get("/api/projects")
async def get_projects(current_user: User = Depends(get_current_user)):
    return get_user_projects(current_user.id)
```

#### Resource Ownership Validation
```python
def require_project_ownership(project_id: str, current_user: User):
    project = get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return project

@app.get("/api/projects/{project_id}")
async def get_project(
    project_id: str, 
    current_user: User = Depends(get_current_user)
):
    project = require_project_ownership(project_id, current_user)
    return project
```

#### SQL Injection Prevention
```python
# ❌ VULNERABLE: String concatenation
def search_projects(search_term: str):
    query = f"SELECT * FROM projects WHERE name LIKE '%{search_term}%'"
    return db.execute(query).fetchall()

# ✅ SECURE: Parameterized queries  
def search_projects(db: Session, search_term: str, user_id: str):
    return db.execute(
        text("SELECT * FROM projects WHERE name LIKE :search AND owner_id = :user_id"),
        {"search": f"%{search_term}%", "user_id": user_id}
    ).fetchall()
```

### Step 3: Verify Fixes
```bash
# Re-run security tests
python3 run_basic_security_validation.py

# Should now show:
# ✅ All security tests passed!
```

## 📊 Test Categories & Validation

### 1. Multi-Tenancy Security Tests
**File**: `test_multi_tenant_security.py`

**Tests**:
- ✅ User can access own projects
- 🚨 User cannot access other users' projects  
- 🚨 User cannot list other users' projects
- 🚨 User cannot modify other users' projects
- 🚨 User cannot delete other users' projects

**Expected Failures Before Fix**:
```python
def test_user_cannot_access_other_user_projects(self, harness):
    # This should FAIL initially, proving vulnerability exists
    response = client.get(f"/api/projects/{alice_project_id}", 
                         headers=bob_auth_headers)
    assert response.status_code in [403, 404]  # Should fail here
```

### 2. Authentication & Authorization Tests  
**File**: `test_authentication_bypass.py`

**Tests**:
- 🚨 Protected endpoints require authentication
- 🚨 Invalid tokens are rejected
- 🚨 Role-based access control enforced
- 🚨 Session security implemented

### 3. Injection Vulnerability Tests
**File**: `test_injection_vulnerabilities.py`

**Tests**:
- 🚨 SQL injection blocked in query parameters
- 🚨 Command injection blocked in file operations
- 🚨 Script injection (XSS) properly escaped
- 🚨 Path traversal attacks prevented

### 4. Data Access Control Tests
**File**: `test_data_access_control.py`

**Tests**:
- 🚨 Resource ownership validated
- 🚨 Privilege escalation prevented  
- 🚨 File system access restricted
- 🚨 Bulk operations respect ownership

## 🛡️ Security Test Patterns

### Vulnerability Demonstration Pattern
```python
def test_cross_user_access_vulnerability(self, harness):
    """This test should FAIL initially, demonstrating the vulnerability"""
    
    # Alice creates a project
    alice_project = harness.create_project_as_user("alice")
    
    # Bob attempts to access Alice's project
    response = harness.client.get(
        f"/api/projects/{alice_project['id']}",
        headers=harness.get_auth_headers("bob")
    )
    
    # CRITICAL: This assertion should FAIL before fixes are applied
    assert response.status_code in [403, 404], \
        f"SECURITY VULNERABILITY: Bob accessed Alice's project! Status: {response.status_code}"
```

### Security Fix Validation Pattern
```python
def test_proper_authorization_after_fix(self, harness):
    """This test should PASS after security fixes are applied"""
    
    # Create user-specific resources
    alice_project = harness.create_project_as_user("alice") 
    bob_project = harness.create_project_as_user("bob")
    
    # Alice should only see her project
    alice_projects = harness.get_user_projects("alice")
    assert len(alice_projects) == 1
    assert alice_projects[0]["id"] == alice_project["id"]
    
    # Bob should only see his project
    bob_projects = harness.get_user_projects("bob")
    assert len(bob_projects) == 1
    assert bob_projects[0]["id"] == bob_project["id"]
```

## 🚨 Critical Security Checklist

### Before Running Tests
- [ ] Backend application is running
- [ ] Database is accessible
- [ ] Test environment is isolated from production
- [ ] Required Python packages are installed

### During Testing
- [ ] Review each test failure carefully
- [ ] Document specific vulnerability details
- [ ] Note which endpoints/functions are affected
- [ ] Identify root cause of each security issue

### After Testing  
- [ ] Apply security fixes based on test results
- [ ] Re-run tests to verify fixes work
- [ ] Ensure all critical tests pass
- [ ] Generate security validation report

### Before Production Deployment
- [ ] ✅ All security tests pass
- [ ] ✅ Multi-tenancy isolation verified
- [ ] ✅ Authentication properly enforced
- [ ] ✅ Injection vulnerabilities patched
- [ ] ✅ Access controls implemented

## 📞 Troubleshooting

### Common Issues

#### Import Errors
```bash
# Error: ModuleNotFoundError: No module named 'pytest'
pip3 install pytest fastapi sqlalchemy

# Or activate backend virtual environment
source /path/to/backend/venv/bin/activate
```

#### Database Connection Issues  
```bash
# Check database configuration
python3 -c "from database import engine; print(engine.url)"

# Test database connectivity
python3 -c "from database import SessionLocal; db = SessionLocal(); print('DB OK')"
```

#### FastAPI Application Issues
```bash
# Test if main app imports correctly
python3 -c "from main import app; print('App OK')"

# Check for missing dependencies
pip3 install -r requirements.txt
```

### Test Execution Issues

#### Tests Not Finding Vulnerabilities
If tests pass unexpectedly, this could indicate:
1. Security fixes are already implemented
2. Test setup is incorrect
3. Application endpoints have changed

**Solution**: Review test configuration and endpoint paths

#### Tests Failing Due to Setup Issues
If tests fail due to setup rather than security issues:
1. Check database connectivity
2. Verify test user creation
3. Review authentication token generation

## 📈 Continuous Security Testing

### Integration with Development Workflow

#### Pre-commit Security Checks
```bash
#!/bin/bash
# .git/hooks/pre-commit
cd tests/security
python3 run_basic_security_validation.py
if [ $? -ne 0 ]; then
    echo "❌ Security tests failed - commit blocked"
    exit 1
fi
```

#### CI/CD Pipeline Integration  
```yaml
name: Security Tests
on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install pytest fastapi sqlalchemy
      - name: Run Security Tests
        run: |
          cd tests/security
          python3 test_security_runner.py
        # Fail build if security tests fail
```

#### Regular Security Auditing
```bash
#!/bin/bash
# weekly-security-audit.sh
cd /home/rigade/Testing/tests/security
python3 test_security_runner.py --output-dir ./weekly-reports/$(date +%Y%m%d)
```

## 📚 Additional Resources

### Security Testing Best Practices
1. **Test Early**: Run security tests during development
2. **Test Often**: Include security tests in CI/CD pipeline  
3. **Test Thoroughly**: Cover all user interaction paths
4. **Test Realistically**: Use realistic attack scenarios

### Further Reading
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Multi-Tenant Security Best Practices](https://cheatsheetseries.owasp.org/cheatsheets/Multitenant_Architecture_Cheat_Sheet.html)

---

**Remember**: Security testing is not a one-time activity. Regularly run these tests and stay vigilant for new vulnerability patterns!