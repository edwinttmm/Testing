# Authentication System Documentation

## Overview

A comprehensive JWT-based authentication system for the AI Model Validation Platform with the following features:

- **Secure User Registration and Login**
- **JWT Token Management** (Access & Refresh Tokens)
- **Session Tracking** with automatic cleanup
- **Password Security** using bcrypt hashing
- **Rate Limiting** and brute force protection
- **Role-Based Access Control** (RBAC)
- **Comprehensive Error Handling**
- **Security Headers** and CORS protection

## Files Created

### Core Authentication Files

1. **`auth_endpoints.py`** - Main authentication endpoints
2. **`auth_middleware.py`** - JWT validation middleware  
3. **`auth_dependencies.py`** - FastAPI dependencies for authentication
4. **`test_auth.py`** - Comprehensive test suite

### Database Models (Already Existed)

- **`AuthUser`** - User account model with password hashing
- **`UserSession`** - Session tracking model with expiration

## API Endpoints

### Authentication Endpoints

All endpoints are prefixed with `/auth`

#### 1. POST `/auth/register`
Register a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "SecurePass123!",
  "full_name": "John Doe"
}
```

**Password Requirements:**
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character

**Response (201 Created):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "user-id-123",
    "email": "user@example.com",
    "username": "johndoe",
    "full_name": "John Doe",
    "is_active": true,
    "is_verified": false,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

#### 2. POST `/auth/login`
Authenticate user and return JWT tokens.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "remember_me": false
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "user-id-123",
    "email": "user@example.com",
    "username": "johndoe",
    "full_name": "John Doe",
    "is_active": true,
    "is_verified": false,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

#### 3. POST `/auth/logout`
Logout user and invalidate session.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "message": "Successfully logged out",
  "logged_out_at": "2024-01-01T12:30:00Z"
}
```

#### 4. GET `/auth/me`
Get current user profile information.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "id": "user-id-123",
  "email": "user@example.com",
  "username": "johndoe",
  "full_name": "John Doe",
  "is_active": true,
  "is_verified": false,
  "is_superuser": false,
  "last_login": "2024-01-01T12:00:00Z",
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### 5. POST `/auth/refresh`
Refresh JWT access token using refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "user-id-123",
    "email": "user@example.com",
    "username": "johndoe",
    "full_name": "John Doe",
    "is_active": true,
    "is_verified": false,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

## Security Features

### JWT Token Management

- **Access Tokens**: Short-lived (30 minutes by default)
- **Refresh Tokens**: Long-lived (7 days by default)
- **Token Validation**: Signature, expiration, and type validation
- **Session Tracking**: All tokens tied to database sessions

### Password Security

- **bcrypt Hashing**: Industry-standard password hashing
- **Strong Password Requirements**: Enforced complexity rules
- **No Plain Text Storage**: Passwords never stored in plain text

### Rate Limiting & Protection

- **Rate Limiting**: 100 requests per minute per IP
- **Brute Force Protection**: Auto-block after 10 failed attempts
- **Session Management**: Automatic cleanup of expired sessions
- **IP Tracking**: Log and monitor suspicious activity

### Security Headers

When `security_headers_enabled=true` in config:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security` (when HSTS enabled)
- `Content-Security-Policy` (when CSP enabled)

## FastAPI Dependencies

Import and use these dependencies in your endpoints:

### Basic Authentication

```python
from auth_dependencies import get_current_user, get_current_active_user

@app.get("/protected")
async def protected_endpoint(user: AuthUser = Depends(get_current_active_user)):
    return {"message": f"Hello {user.email}"}
```

### Role-Based Access Control

```python
from auth_dependencies import get_current_superuser, require_permission, Permission

@app.get("/admin")
async def admin_endpoint(user: AuthUser = Depends(get_current_superuser)):
    return {"message": "Admin access granted"}

@app.put("/admin/users")
async def manage_users(user: AuthUser = Depends(require_permission(Permission.USER_ADMIN))):
    return {"message": "User management access"}
```

### Optional Authentication

```python
from auth_dependencies import get_optional_current_user

@app.get("/public")
async def public_endpoint(user: Optional[AuthUser] = Depends(get_optional_current_user)):
    if user:
        return {"message": f"Welcome back, {user.email}"}
    else:
        return {"message": "Welcome, guest"}
```

## Configuration

Configure authentication in `config.py`:

```python
# JWT Configuration
jwt_secret_key: str = "your-secret-key"
jwt_algorithm: str = "HS256"
jwt_expire_minutes: int = 30

# Security Features
security_headers_enabled: bool = True
hsts_enabled: bool = False  # Enable in production with HTTPS
csp_enabled: bool = True
```

## Database Models

### AuthUser Model

Key fields:
- `id` - UUID primary key
- `email` - Unique email address
- `username` - Unique username
- `hashed_password` - bcrypt hashed password
- `is_active` - Account status
- `is_verified` - Email verification status
- `is_superuser` - Admin privileges
- `last_login` - Last login timestamp

### UserSession Model

Key fields:
- `id` - UUID primary key
- `user_id` - Foreign key to AuthUser
- `session_token` - JWT access token
- `ip_address` - Client IP address
- `user_agent` - Client browser/app info
- `is_active` - Session status
- `expires_at` - Session expiration time

## Testing

### Manual Testing

1. Start the FastAPI server:
```bash
cd backend
python main.py
```

2. Run the test suite:
```bash
python test_auth.py
```

### API Testing with cURL

#### Register a user:
```bash
curl -X POST "http://localhost:8000/auth/register" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "test@example.com",
       "username": "testuser",
       "password": "TestPass123!",
       "full_name": "Test User"
     }'
```

#### Login:
```bash
curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "test@example.com",
       "password": "TestPass123!"
     }'
```

#### Access protected endpoint:
```bash
curl -X GET "http://localhost:8000/auth/me" \
     -H "Authorization: Bearer <your-access-token>"
```

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "detail": "Email address is already registered"
}
```

#### 401 Unauthorized
```json
{
  "detail": "Invalid email or password"
}
```

#### 403 Forbidden
```json
{
  "detail": "Superuser privileges required"
}
```

#### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "password"],
      "msg": "Password must contain at least one uppercase letter",
      "type": "value_error"
    }
  ]
}
```

## Best Practices

### For Developers

1. **Always use HTTPS in production**
2. **Set strong JWT secret keys** (32+ characters)
3. **Enable security headers** in production
4. **Implement proper CORS** for your frontend
5. **Monitor failed login attempts**
6. **Regularly clean up expired sessions**

### For Frontend Integration

1. **Store tokens securely** (httpOnly cookies preferred)
2. **Handle token expiration** gracefully
3. **Implement automatic token refresh**
4. **Clear tokens on logout**
5. **Validate user permissions** on protected routes

## Production Deployment

### Environment Variables

Set these environment variables in production:

```bash
# Required - Change from default!
AIVALIDATION_JWT_SECRET_KEY="your-super-secret-32-character-key"

# Security
AIVALIDATION_SECURITY_HEADERS_ENABLED="true"
AIVALIDATION_HSTS_ENABLED="true"  # Only with HTTPS
AIVALIDATION_CSP_ENABLED="true"

# Database
DATABASE_URL="postgresql://user:pass@host:5432/db"

# SSL/TLS (recommended)
AIVALIDATION_SSL_ENABLED="true"
AIVALIDATION_SSL_CERT_FILE="/path/to/cert.pem"
AIVALIDATION_SSL_KEY_FILE="/path/to/key.pem"
```

### Security Checklist

- [ ] Strong JWT secret key configured
- [ ] HTTPS enabled with valid SSL certificate
- [ ] Security headers enabled
- [ ] Database connections encrypted
- [ ] CORS properly configured for your domain
- [ ] Rate limiting enabled
- [ ] Regular security updates applied
- [ ] Monitoring and alerting configured

## Troubleshooting

### Common Issues

#### "Token has expired"
- Implement automatic token refresh
- Check system clock synchronization

#### "User not found"
- Verify user exists in database
- Check if account is active

#### "Session expired or invalid"
- Clear stored tokens and re-login
- Check session cleanup isn't too aggressive

#### "Rate limit exceeded"
- Implement exponential backoff
- Check if rate limits are appropriate

### Logging

Authentication events are logged with these levels:

- **INFO**: Successful logins, registrations, logouts
- **WARNING**: Invalid passwords, inactive accounts, rate limits
- **ERROR**: System errors, database issues

Check application logs for detailed error information.

## Support

For issues with the authentication system:

1. Check the logs for detailed error messages
2. Verify configuration settings
3. Test with the provided test suite
4. Review the FastAPI documentation for dependencies

## Future Enhancements

Planned features:

- [ ] Email verification system
- [ ] Password reset functionality  
- [ ] Two-factor authentication (2FA)
- [ ] OAuth integration (Google, GitHub)
- [ ] Granular permission system
- [ ] User profile management
- [ ] Account lockout policies
- [ ] Audit log improvements