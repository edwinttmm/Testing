#!/usr/bin/env python3

import sys
import os

# Add the backend directory to Python path
backend_path = os.path.join(os.path.dirname(__file__), '..', 'ai-model-validation-platform', 'backend')
sys.path.insert(0, backend_path)

from database import SessionLocal
from models import User
import uuid

def create_demo_user():
    """Create a demo user for testing"""
    db = SessionLocal()
    try:
        # Check if demo user already exists
        existing_user = db.query(User).filter(User.id == "demo-user-id").first()
        if existing_user:
            print("Demo user already exists!")
            return
        
        # Create demo user
        demo_user = User(
            id="demo-user-id",
            email="demo@example.com",
            hashed_password="hashed_demo_password",  # Not used since auth is disabled
            full_name="Demo User",
            is_active=True
        )
        
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)
        
        print(f"Demo user created successfully!")
        print(f"ID: {demo_user.id}")
        print(f"Email: {demo_user.email}")
        print(f"Name: {demo_user.full_name}")
        
    except Exception as e:
        print(f"Error creating demo user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_demo_user()