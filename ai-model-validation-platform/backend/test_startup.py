#!/usr/bin/env python3
"""
Quick test to verify backend startup without full server launch
"""
import sys
import traceback
import logging

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_imports():
    """Test all critical imports"""
    logger.info("Testing imports...")
    
    try:
        # Core FastAPI imports
        from fastapi import FastAPI, HTTPException, Depends
        from fastapi.middleware.cors import CORSMiddleware
        logger.info("✅ FastAPI imports successful")
        
        # Database imports
        from sqlalchemy.orm import Session
        from sqlalchemy import create_engine
        logger.info("✅ SQLAlchemy imports successful")
        
        # Security imports
        import jwt
        from passlib.context import CryptContext
        logger.info("✅ Security imports successful")
        
        # Local imports
        from config import settings, get_settings
        from security_middleware import SecurityHeadersMiddleware, setup_security_middleware
        from database import get_db
        logger.info("✅ Local module imports successful")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        traceback.print_exc()
        return False

def test_app_creation():
    """Test FastAPI app creation"""
    logger.info("Testing app creation...")
    
    try:
        from fastapi import FastAPI
        from config import settings
        from security_middleware import setup_security_middleware
        
        # Create basic FastAPI app
        app = FastAPI(
            title="AI Model Validation Platform Test",
            description="Test app creation",
            version="1.0.0"
        )
        
        # Add CORS
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["*"],
        )
        
        # Test security middleware setup
        setup_security_middleware(app, settings)
        
        logger.info("✅ FastAPI app creation successful")
        return True
        
    except Exception as e:
        logger.error(f"❌ App creation failed: {e}")
        traceback.print_exc()
        return False

def test_security_classes():
    """Test security classes instantiation"""
    logger.info("Testing security classes...")
    
    try:
        from security_middleware import JWTAuthHandler, PasswordManager, CSRFProtection
        from config import get_settings
        
        settings = get_settings()
        
        # Test JWT handler
        jwt_handler = JWTAuthHandler(settings)
        logger.info("✅ JWT handler created")
        
        # Test password manager
        password = PasswordManager.hash_password("test123")
        is_valid = PasswordManager.verify_password("test123", password)
        assert is_valid, "Password verification failed"
        logger.info("✅ Password manager working")
        
        # Test CSRF protection
        csrf = CSRFProtection(settings.secret_key)
        token = csrf.generate_token("test-session")
        is_valid = csrf.validate_token(token, "test-session")
        assert is_valid, "CSRF token validation failed"
        logger.info("✅ CSRF protection working")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Security classes test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    logger.info("🚀 Starting backend dependency tests...")
    
    tests = [
        ("Imports", test_imports),
        ("App Creation", test_app_creation),
        ("Security Classes", test_security_classes)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running {test_name} test...")
        logger.info(f"{'='*50}")
        
        if test_func():
            passed += 1
            logger.info(f"✅ {test_name} test PASSED")
        else:
            failed += 1
            logger.error(f"❌ {test_name} test FAILED")
    
    logger.info(f"\n{'='*50}")
    logger.info(f"Test Summary: {passed} passed, {failed} failed")
    logger.info(f"{'='*50}")
    
    if failed == 0:
        logger.info("🎉 All tests passed! Backend should start correctly.")
        return 0
    else:
        logger.error(f"💥 {failed} tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())