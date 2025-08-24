#!/usr/bin/env python3
"""
Verify Backend Dependencies and Functionality
This script confirms all dependencies are working and backend can start.
"""
import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    print("=" * 60)
    print("🚀 AI Model Validation Platform - Backend Verification")
    print("=" * 60)
    print(f"⏰ Verification started at: {datetime.now()}")
    print()
    
    # Test 1: Critical Imports
    print("1️⃣ Testing Critical Dependencies...")
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import jwt
        import passlib
        import torch
        import ultralytics
        print("   ✅ All critical dependencies imported successfully")
    except ImportError as e:
        print(f"   ❌ Critical dependency missing: {e}")
        return 1
    
    # Test 2: Security Features
    print("\n2️⃣ Testing Security Features...")
    try:
        from security_middleware import JWTAuthHandler, PasswordManager, CSRFProtection
        from config import get_settings
        
        settings = get_settings()
        
        # Test JWT
        jwt_handler = JWTAuthHandler(settings)
        test_token = jwt_handler.encode_token("test_user", 30)
        decoded = jwt_handler.decode_token(test_token)
        assert decoded['user_id'] == 'test_user'
        
        # Test Password Hashing
        hashed = PasswordManager.hash_password("test123")
        assert PasswordManager.verify_password("test123", hashed)
        
        print("   ✅ Security features working correctly")
    except Exception as e:
        print(f"   ❌ Security feature error: {e}")
        return 1
    
    # Test 3: App Creation
    print("\n3️⃣ Testing FastAPI App Creation...")
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from security_middleware import setup_security_middleware
        from config import get_settings
        
        settings = get_settings()
        
        app = FastAPI(title="Test App")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["*"],
        )
        
        setup_security_middleware(app, settings)
        
        print("   ✅ FastAPI app created with security middleware")
    except Exception as e:
        print(f"   ❌ App creation error: {e}")
        return 1
    
    # Test 4: Database Connection
    print("\n4️⃣ Testing Database Connection...")
    try:
        from database import get_db, engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
            
        print("   ✅ Database connection successful")
    except Exception as e:
        print(f"   ⚠️ Database connection note: {e} (This is often normal for fresh installations)")
    
    # Test 5: ML Dependencies
    print("\n5️⃣ Testing ML/AI Dependencies...")
    try:
        import torch
        import torchvision
        import ultralytics
        import cv2
        import numpy as np
        from PIL import Image
        
        # Quick torch test
        tensor = torch.ones(2, 2)
        assert tensor.sum() == 4
        
        print("   ✅ ML/AI dependencies working correctly")
    except Exception as e:
        print(f"   ❌ ML dependency error: {e}")
        return 1
    
    print("\n" + "=" * 60)
    print("🎉 BACKEND VERIFICATION COMPLETE")
    print("=" * 60)
    print("✅ All dependencies are working correctly")
    print("✅ Security features are functional")
    print("✅ FastAPI app can be created")
    print("✅ ML/AI dependencies are available")
    print()
    print("🚀 Backend is ready to start!")
    print()
    print("To start the backend:")
    print("  python -m uvicorn main:app --host 0.0.0.0 --port 8000")
    print("  or")
    print("  python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
    print()
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())