#!/usr/bin/env python3
"""
Demo: Project-Video Many-to-Many Migration Usage
Shows how to use the migration and work with the new relationship structure
"""

import os
import sys
import sqlite3
import uuid
import json
from datetime import datetime
from pathlib import Path

def demo_migration_usage():
    """Demonstrate the complete migration usage workflow"""
    
    print("🎯 Project-Video Many-to-Many Migration Demo")
    print("=" * 50)
    
    # Step 1: Setup demo database
    demo_db_path = "./demo_migration.db"
    setup_demo_database(demo_db_path)
    
    # Step 2: Show pre-migration state
    print("\n📋 PRE-MIGRATION STATE:")
    show_database_state(demo_db_path, "pre-migration")
    
    # Step 3: Run migration suite
    print("\n🚀 RUNNING MIGRATION SUITE:")
    run_migration_demo(demo_db_path)
    
    # Step 4: Show post-migration state  
    print("\n📊 POST-MIGRATION STATE:")
    show_database_state(demo_db_path, "post-migration")
    
    # Step 5: Demonstrate new capabilities
    print("\n✨ NEW CAPABILITIES DEMO:")
    demonstrate_new_features(demo_db_path)
    
    # Step 6: Performance comparison
    print("\n⚡ PERFORMANCE COMPARISON:")
    demonstrate_performance_improvements(demo_db_path)
    
    # Step 7: Cleanup
    if os.path.exists(demo_db_path):
        os.remove(demo_db_path)
    
    print("\n🎉 Demo completed successfully!")

def setup_demo_database(db_path: str):
    """Setup demo database with sample data"""
    print("Setting up demo database with sample data...")
    
    # Remove existing database
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create old-style schema (before migration)
    cursor.execute("""
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            camera_model TEXT NOT NULL,
            camera_view TEXT NOT NULL,
            lens_type TEXT,
            resolution TEXT,
            frame_rate INTEGER,
            signal_type TEXT NOT NULL,
            status TEXT DEFAULT 'Active',
            owner_id TEXT DEFAULT 'demo_user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE videos (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            duration REAL,
            fps REAL,
            resolution TEXT,
            status TEXT DEFAULT 'uploaded',
            ground_truth_generated BOOLEAN DEFAULT FALSE,
            project_id TEXT,
            upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    
    # Insert sample data
    projects = [
        {
            'id': str(uuid.uuid4()),
            'name': 'Urban VRU Detection',
            'description': 'Downtown pedestrian crossing detection',
            'camera_model': 'Sony IMX490',
            'camera_view': 'Front-facing VRU',
            'lens_type': 'Wide Angle 120°',
            'resolution': '1920x1080',
            'frame_rate': 30,
            'signal_type': 'GPIO'
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'Highway Safety Monitoring',
            'description': 'High-speed VRU detection on highway ramps',
            'camera_model': 'Aptina AR0233',
            'camera_view': 'Rear-facing VRU',
            'lens_type': 'Telephoto 85mm',
            'resolution': '1920x1200',
            'frame_rate': 60,
            'signal_type': 'Network Packet'
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'Driver Behavior Study',
            'description': 'In-cabin driver attention monitoring',
            'camera_model': 'OV9286 IR',
            'camera_view': 'In-Cab Driver Behavior',
            'lens_type': 'IR Enhanced 50mm',
            'resolution': '1280x720',
            'frame_rate': 30,
            'signal_type': 'Serial'
        }
    ]
    
    for project in projects:
        cursor.execute("""
            INSERT INTO projects (
                id, name, description, camera_model, camera_view, lens_type,
                resolution, frame_rate, signal_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project['id'], project['name'], project['description'],
            project['camera_model'], project['camera_view'], project['lens_type'],
            project['resolution'], project['frame_rate'], project['signal_type']
        ))
    
    # Insert sample videos (multiple videos per project + shared videos)
    videos = [
        # Urban VRU Detection videos
        {'filename': 'urban_crosswalk_morning.mp4', 'project_id': projects[0]['id'], 'duration': 180.5},
        {'filename': 'urban_crosswalk_evening.mp4', 'project_id': projects[0]['id'], 'duration': 165.2},
        {'filename': 'urban_intersection_busy.mp4', 'project_id': projects[0]['id'], 'duration': 220.8},
        
        # Highway Safety videos
        {'filename': 'highway_ramp_entry.mp4', 'project_id': projects[1]['id'], 'duration': 300.0},
        {'filename': 'highway_emergency_stop.mp4', 'project_id': projects[1]['id'], 'duration': 95.5},
        
        # Driver Behavior videos
        {'filename': 'driver_distraction_test.mp4', 'project_id': projects[2]['id'], 'duration': 420.3},
        {'filename': 'driver_fatigue_detection.mp4', 'project_id': projects[2]['id'], 'duration': 380.7},
        
        # Shared videos that will be used in multiple projects after migration
        {'filename': 'shared_validation_clip_001.mp4', 'project_id': projects[0]['id'], 'duration': 60.0},
        {'filename': 'shared_validation_clip_002.mp4', 'project_id': projects[1]['id'], 'duration': 45.5},
    ]
    
    for video in videos:
        cursor.execute("""
            INSERT INTO videos (
                id, filename, file_path, file_size, duration, fps, 
                resolution, project_id, ground_truth_generated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            video['filename'],
            f'/uploads/{video["filename"]}',
            int(video['duration'] * 1024 * 200),  # Approximate file size
            video['duration'],
            30.0,
            '1920x1080',
            video['project_id'],
            False
        ))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Demo database created: {db_path}")
    print(f"   📁 {len(projects)} projects")
    print(f"   🎥 {len(videos)} videos")

def show_database_state(db_path: str, phase: str):
    """Show current database state"""
    print(f"Database state ({phase}):")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Show tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"   📋 Tables: {', '.join(tables)}")
    
    # Show counts
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   📊 {table}: {count} records")
    
    # Show relationships if available
    if 'project_videos' in tables:
        cursor.execute("""
            SELECT COUNT(*) as relationships,
                   COUNT(DISTINCT project_id) as projects_with_videos,
                   COUNT(DISTINCT video_id) as videos_with_projects
            FROM project_videos
        """)
        rel_stats = cursor.fetchone()
        print(f"   🔗 Many-to-Many Relationships: {rel_stats[0]}")
        print(f"   📁 Projects with videos: {rel_stats[1]}")
        print(f"   🎥 Videos with projects: {rel_stats[2]}")
    
    elif 'videos' in tables and phase == "pre-migration":
        cursor.execute("""
            SELECT COUNT(*) as relationships,
                   COUNT(DISTINCT project_id) as projects_with_videos
            FROM videos 
            WHERE project_id IS NOT NULL
        """)
        rel_stats = cursor.fetchone()
        print(f"   🔗 One-to-Many Relationships: {rel_stats[0]}")
        print(f"   📁 Projects with videos: {rel_stats[1]}")
    
    conn.close()

def run_migration_demo(db_path: str):
    """Run migration on demo database"""
    print("Running migration suite...")
    
    try:
        # Import the migration suite runner
        sys.path.append('.')
        from run_migration_suite import MigrationSuiteRunner
        
        # Run migration in non-dry-run mode for demo
        suite = MigrationSuiteRunner(db_path, dry_run=False)
        results = suite.run_complete_migration_suite()
        
        if results['overall_success']:
            print("✅ Migration completed successfully!")
        else:
            print("❌ Migration failed!")
            print("Error details:", results.get('error', 'Unknown error'))
            
    except Exception as e:
        print(f"❌ Migration demo failed: {e}")
        # For demo purposes, let's manually run a simplified migration
        print("🔄 Running simplified migration for demo...")
        run_simplified_migration(db_path)

def run_simplified_migration(db_path: str):
    """Run simplified version of migration for demo"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create project_videos junction table
        cursor.execute("""
            CREATE TABLE project_videos (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                video_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                UNIQUE(project_id, video_id)
            )
        """)
        
        # Migrate existing relationships
        cursor.execute("""
            INSERT INTO project_videos (id, project_id, video_id, created_at)
            SELECT 
                hex(randomblob(16)) as id,
                v.project_id,
                v.id as video_id,
                datetime('now') as created_at
            FROM videos v
            WHERE v.project_id IS NOT NULL
        """)
        
        # Add new fields to videos
        cursor.execute("ALTER TABLE videos ADD COLUMN camera_model TEXT")
        cursor.execute("ALTER TABLE videos ADD COLUMN camera_view TEXT")
        cursor.execute("ALTER TABLE videos ADD COLUMN lens_type TEXT")
        cursor.execute("ALTER TABLE videos ADD COLUMN video_resolution TEXT")
        cursor.execute("ALTER TABLE videos ADD COLUMN frame_rate INTEGER")
        cursor.execute("ALTER TABLE videos ADD COLUMN signal_type TEXT")
        
        # Update videos with project technical specs
        cursor.execute("""
            UPDATE videos SET
                camera_model = (SELECT p.camera_model FROM projects p WHERE p.id = videos.project_id),
                camera_view = (SELECT p.camera_view FROM projects p WHERE p.id = videos.project_id),
                lens_type = (SELECT p.lens_type FROM projects p WHERE p.id = videos.project_id),
                video_resolution = (SELECT p.resolution FROM projects p WHERE p.id = videos.project_id),
                frame_rate = (SELECT p.frame_rate FROM projects p WHERE p.id = videos.project_id),
                signal_type = (SELECT p.signal_type FROM projects p WHERE p.id = videos.project_id)
            WHERE project_id IS NOT NULL
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX idx_project_videos_project_id ON project_videos(project_id)")
        cursor.execute("CREATE INDEX idx_project_videos_video_id ON project_videos(video_id)")
        cursor.execute("CREATE INDEX idx_videos_camera_model ON videos(camera_model)")
        cursor.execute("CREATE INDEX idx_videos_camera_view ON videos(camera_view)")
        
        conn.commit()
        print("✅ Simplified migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Simplified migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

def demonstrate_new_features(db_path: str):
    """Demonstrate new many-to-many relationship features"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("New capabilities after migration:")
    
    # 1. Videos can now belong to multiple projects
    print("\n1️⃣ Assigning videos to multiple projects:")
    
    # Get a video and assign it to multiple projects
    cursor.execute("SELECT id, filename FROM videos LIMIT 1")
    video = cursor.fetchone()
    
    cursor.execute("SELECT id, name FROM projects LIMIT 2")
    projects = cursor.fetchall()
    
    if video and len(projects) >= 2:
        video_id, video_filename = video
        
        # Assign video to second project (already assigned to first)
        cursor.execute("""
            INSERT OR IGNORE INTO project_videos (id, project_id, video_id, created_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (str(uuid.uuid4()), projects[1][0], video_id))
        
        # Show which projects this video belongs to
        cursor.execute("""
            SELECT p.name 
            FROM projects p
            INNER JOIN project_videos pv ON p.id = pv.project_id
            WHERE pv.video_id = ?
        """, (video_id,))
        
        project_names = [row[0] for row in cursor.fetchall()]
        print(f"   🎥 Video '{video_filename}' now belongs to {len(project_names)} projects:")
        for name in project_names:
            print(f"      📁 {name}")
    
    # 2. Enhanced video search by technical specifications
    print("\n2️⃣ Enhanced video search by technical specifications:")
    
    cursor.execute("""
        SELECT filename, camera_model, camera_view, frame_rate
        FROM videos 
        WHERE camera_model LIKE '%Sony%'
        ORDER BY frame_rate DESC
        LIMIT 3
    """)
    
    sony_videos = cursor.fetchall()
    if sony_videos:
        print("   📹 Sony camera videos:")
        for filename, camera_model, camera_view, frame_rate in sony_videos:
            print(f"      🎥 {filename} - {camera_model} ({camera_view}) @ {frame_rate}fps")
    
    # 3. Project video statistics
    print("\n3️⃣ Project video statistics:")
    
    cursor.execute("""
        SELECT 
            p.name,
            COUNT(pv.video_id) as video_count,
            AVG(v.duration) as avg_duration,
            COUNT(DISTINCT v.camera_model) as camera_models
        FROM projects p
        LEFT JOIN project_videos pv ON p.id = pv.project_id
        LEFT JOIN videos v ON pv.video_id = v.id
        GROUP BY p.id, p.name
        ORDER BY video_count DESC
    """)
    
    project_stats = cursor.fetchall()
    for name, video_count, avg_duration, camera_models in project_stats:
        avg_dur = f"{avg_duration:.1f}s" if avg_duration else "N/A"
        print(f"   📁 {name}: {video_count} videos, avg {avg_dur}, {camera_models} camera types")
    
    conn.commit()
    conn.close()

def demonstrate_performance_improvements(db_path: str):
    """Demonstrate performance improvements with new indexes"""
    import time
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Performance improvements with new indexes:")
    
    # Test 1: Project-video relationship queries
    start_time = time.time()
    cursor.execute("""
        SELECT p.name, COUNT(pv.video_id) as video_count
        FROM projects p
        LEFT JOIN project_videos pv ON p.id = pv.project_id
        GROUP BY p.id, p.name
        ORDER BY video_count DESC
    """)
    results = cursor.fetchall()
    query_time = time.time() - start_time
    
    print(f"   ⚡ Project-video aggregation: {query_time:.4f}s ({len(results)} projects)")
    
    # Test 2: Video search by technical specs
    start_time = time.time()
    cursor.execute("""
        SELECT filename, camera_model, camera_view, duration
        FROM videos
        WHERE camera_model IS NOT NULL 
          AND frame_rate >= 30
        ORDER BY duration DESC
    """)
    results = cursor.fetchall()
    query_time = time.time() - start_time
    
    print(f"   ⚡ Technical specification search: {query_time:.4f}s ({len(results)} videos)")
    
    # Test 3: Complex join with filtering
    start_time = time.time()
    cursor.execute("""
        SELECT p.name, v.filename, v.camera_model, v.duration
        FROM projects p
        INNER JOIN project_videos pv ON p.id = pv.project_id
        INNER JOIN videos v ON pv.video_id = v.id
        WHERE v.duration > 60
          AND v.camera_view = 'Front-facing VRU'
        ORDER BY v.duration DESC
    """)
    results = cursor.fetchall()
    query_time = time.time() - start_time
    
    print(f"   ⚡ Complex filtered join: {query_time:.4f}s ({len(results)} matches)")
    
    # Show query plan for optimization verification
    print("\n📊 Query optimization verification:")
    cursor.execute("""
        EXPLAIN QUERY PLAN
        SELECT p.name, COUNT(pv.video_id) as video_count
        FROM projects p
        LEFT JOIN project_videos pv ON p.id = pv.project_id
        GROUP BY p.id, p.name
    """)
    
    query_plan = cursor.fetchall()
    for plan_step in query_plan:
        if 'INDEX' in str(plan_step):
            print(f"   📈 Using index optimization: {plan_step}")
    
    conn.close()

if __name__ == "__main__":
    demo_migration_usage()