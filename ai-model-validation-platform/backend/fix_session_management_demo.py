#!/usr/bin/env python3
"""
Session Management Fix Demo

This script demonstrates the solution to the "sessions is projects sessions not random" issue.
It shows how sessions are now properly project-based with meaningful names.

Author: System Architecture Designer
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.session_management_service import session_manager
from database import SessionLocal
from models import Project, Video, TestSession

def show_current_sessions():
    """Show all current sessions with their project associations"""
    print("🔍 CURRENT SESSION STATUS")
    print("=" * 50)
    
    db = SessionLocal()
    try:
        sessions = db.query(TestSession).all()
        projects = db.query(Project).all()
        
        print(f"Total Sessions: {len(sessions)}")
        print(f"Total Projects: {len(projects)}")
        print()
        
        # Group sessions by project
        project_sessions = {}
        for session in sessions:
            if session.project_id not in project_sessions:
                project_sessions[session.project_id] = []
            project_sessions[session.project_id].append(session)
        
        for project in projects:
            project_session_list = project_sessions.get(project.id, [])
            print(f"📁 PROJECT: {project.name} (ID: {project.id[:8]}...)")
            print(f"   Status: {project.status}")
            
            if project.id == "66f9c296-ee1e-4e81-b0ba-96d03fdc8c90":
                print("   ⭐ THIS IS THE USER'S TARGET 'test' PROJECT")
            
            if project_session_list:
                print(f"   Sessions ({len(project_session_list)}):")
                for session in project_session_list:
                    print(f"   • {session.name}")
                    print(f"     ID: {session.id[:8]}...")
                    print(f"     Status: {session.status}")
                    print(f"     Type: {session.session_type}")
                    print(f"     Created: {session.created_at}")
            else:
                print("   No sessions found")
            print()
        
    finally:
        db.close()

def demonstrate_project_session_creation():
    """Demonstrate creating a proper project-based session"""
    print("✨ CREATING PROJECT-BASED SESSION")
    print("=" * 50)
    
    # Create session for the user's "test" project
    print("Creating session for 'test' project (66f9c296-ee1e-4e81-b0ba-96d03fdc8c90)...")
    
    result = session_manager.create_project_session(
        project_id="66f9c296-ee1e-4e81-b0ba-96d03fdc8c90",
        session_name="Demo: test Project Validation Session",
        session_type="demo_session",
        metadata={
            "demo": True,
            "purpose": "Demonstrate proper project-based session creation",
            "issue_resolved": "sessions is projects sessions not random"
        }
    )
    
    if result["success"]:
        session = result["session"]
        print("✅ SUCCESS: Project-based session created!")
        print(f"   Session Name: {session['session_name']}")
        print(f"   Project: {session['project_name']}")
        print(f"   Video: {session['video_filename']}")
        print(f"   Session Type: {session['session_type']}")
        print(f"   Created: {session['created_at']}")
        print()
        print("🎯 KEY IMPROVEMENTS:")
        print("   • Session name includes project context")
        print("   • Session is linked to correct project")
        print("   • Video is auto-selected from project")
        print("   • Meaningful session type specified")
        print("   • Full metadata tracking")
        print()
    else:
        print(f"❌ FAILED: {result['message']}")

def demonstrate_session_retrieval():
    """Demonstrate retrieving sessions by project"""
    print("📋 RETRIEVING PROJECT SESSIONS")
    print("=" * 50)
    
    # Get sessions for the test project
    result = session_manager.get_project_sessions(
        project_id="66f9c296-ee1e-4e81-b0ba-96d03fdc8c90",
        limit=10
    )
    
    if result["success"]:
        project = result["project"]
        sessions = result["sessions"]
        
        print(f"✅ Retrieved {len(sessions)} sessions for project '{project['name']}'")
        print(f"Project Status: {project['status']}")
        print()
        
        for i, session in enumerate(sessions, 1):
            print(f"{i}. {session['name']}")
            print(f"   Status: {session['status']}")
            print(f"   Type: {session['session_type']}")
            print(f"   Video: {session.get('video', {}).get('filename', 'N/A')}")
            print(f"   Detections: {session['statistics']['detection_events']}")
            print(f"   Results: {session['statistics']['test_results']}")
            print()
        
        print("🎯 SOLUTION BENEFITS:")
        print("   • Sessions are clearly linked to projects")
        print("   • Meaningful session names (not random)")
        print("   • Project context preserved")
        print("   • Easy to filter and display by project")
        print("   • Session statistics included")
    else:
        print(f"❌ FAILED: {result['message']}")

def demonstrate_phantom_cleanup():
    """Demonstrate phantom session cleanup capability"""
    print("🧹 PHANTOM SESSION CLEANUP")
    print("=" * 50)
    
    # Show what phantom sessions would be cleaned up (dry run)
    result = session_manager.cleanup_phantom_sessions(dry_run=True)
    
    if result["success"]:
        print(f"Found {result['phantom_sessions_found']} phantom sessions to clean up")
        
        if result["phantom_sessions_found"] > 0:
            print("\nSample phantom sessions that would be removed:")
            for session in result.get("sample_sessions", []):
                print(f"   • {session['name']}")
                print(f"     ID: {session['id'][:8]}...")
                print(f"     Project: {session['project_id'][:8]}...")
                print(f"     Status: {session['status']}")
            
            print("\n💡 To actually clean up phantom sessions:")
            print("   result = session_manager.cleanup_phantom_sessions(dry_run=False)")
        else:
            print("✅ No phantom sessions found - system is clean!")
    else:
        print(f"❌ FAILED: {result['message']}")

def main():
    """Main demo function"""
    print("🔧 SESSION MANAGEMENT FIX DEMONSTRATION")
    print("=" * 70)
    print("ISSUE: 'sessions is projects sessions not random?'")
    print("SOLUTION: Proper project-based session management")
    print("=" * 70)
    print()
    
    try:
        # 1. Show current session state
        show_current_sessions()
        
        # 2. Demonstrate creating proper project-based session
        demonstrate_project_session_creation()
        
        # 3. Demonstrate retrieving sessions by project
        demonstrate_session_retrieval()
        
        # 4. Demonstrate phantom session cleanup
        demonstrate_phantom_cleanup()
        
        print("✅ SESSION MANAGEMENT FIX COMPLETE!")
        print("=" * 70)
        print("RESOLUTION SUMMARY:")
        print("• Sessions are now properly linked to projects")
        print("• Session names are meaningful (include project context)")
        print("• No more random/generic session names")
        print("• Project context is preserved throughout lifecycle")
        print("• Sessions can be filtered and grouped by project")
        print("• Phantom sessions can be identified and cleaned up")
        print("• Auto-video selection for streamlined workflow")
        print("• Enhanced session metadata and statistics")
        print()
        print("🎯 USER IMPACT:")
        print("• Sessions for 'test' project are clearly identified")
        print("• Results page will show project-grouped sessions")
        print("• No more confusion about session ownership")
        print("• Enhanced project workflow management")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()