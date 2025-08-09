#!/usr/bin/env python3
"""
Create database tables
"""
from database import engine, Base
from models import User, Project, Video, GroundTruthObject, TestSession, DetectionEvent, AuditLog

def create_tables():
    """Create all database tables"""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    create_tables()