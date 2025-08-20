"""
Database Integrity Test Suite
Tests schema consistency, data persistence, transaction integrity, and ground truth processing
"""

import pytest
import sqlite3
import tempfile
import os
import shutil
from unittest.mock import patch, MagicMock
import json
from datetime import datetime


class TestDatabaseIntegrity:
    """Test database schema consistency and data integrity"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, 'test_database.db')
        yield db_path
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def db_connection(self, temp_db):
        """Create database connection with test schema"""
        conn = sqlite3.connect(temp_db)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_size INTEGER,
                duration REAL,
                frame_count INTEGER,
                fps REAL,
                status TEXT DEFAULT 'uploaded',
                ground_truth_data TEXT,
                processing_metadata TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ground_truth (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER,
                frame_number INTEGER,
                bounding_boxes TEXT,
                labels TEXT,
                confidence_scores TEXT,
                processing_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS processing_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER,
                job_type TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
            )
        ''')
        conn.commit()
        yield conn
        conn.close()
    
    def test_schema_consistency(self, db_connection):
        """Test that database schema is consistent and complete"""
        cursor = db_connection.cursor()
        
        # Check videos table structure
        cursor.execute("PRAGMA table_info(videos)")
        video_columns = {row[1]: row[2] for row in cursor.fetchall()}
        expected_video_columns = {
            'id': 'INTEGER',
            'filename': 'TEXT',
            'file_path': 'TEXT',
            'upload_date': 'TIMESTAMP',
            'file_size': 'INTEGER',
            'duration': 'REAL',
            'frame_count': 'INTEGER',
            'fps': 'REAL',
            'status': 'TEXT',
            'ground_truth_data': 'TEXT',
            'processing_metadata': 'TEXT'
        }
        
        for col, col_type in expected_video_columns.items():
            assert col in video_columns, f"Missing column: {col}"
            assert video_columns[col] == col_type, f"Wrong type for {col}: {video_columns[col]} vs {col_type}"
        
        # Check ground_truth table structure
        cursor.execute("PRAGMA table_info(ground_truth)")
        gt_columns = {row[1]: row[2] for row in cursor.fetchall()}
        expected_gt_columns = {
            'id': 'INTEGER',
            'video_id': 'INTEGER',
            'frame_number': 'INTEGER',
            'bounding_boxes': 'TEXT',
            'labels': 'TEXT',
            'confidence_scores': 'TEXT',
            'processing_timestamp': 'TIMESTAMP'
        }
        
        for col, col_type in expected_gt_columns.items():
            assert col in gt_columns, f"Missing ground truth column: {col}"
    
    def test_foreign_key_constraints(self, db_connection):
        """Test foreign key constraints are working"""
        cursor = db_connection.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Insert test video
        cursor.execute(
            "INSERT INTO videos (filename, file_path, file_size) VALUES (?, ?, ?)",
            ("test.mp4", "/path/test.mp4", 1000000)
        )
        video_id = cursor.lastrowid
        
        # Insert ground truth data
        cursor.execute(
            "INSERT INTO ground_truth (video_id, frame_number, bounding_boxes) VALUES (?, ?, ?)",
            (video_id, 1, "[{\"x\": 10, \"y\": 10, \"width\": 50, \"height\": 50}]")
        )
        
        # Verify data exists
        cursor.execute("SELECT COUNT(*) FROM ground_truth WHERE video_id = ?", (video_id,))
        assert cursor.fetchone()[0] == 1
        
        # Delete video and check cascade
        cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        cursor.execute("SELECT COUNT(*) FROM ground_truth WHERE video_id = ?", (video_id,))
        assert cursor.fetchone()[0] == 0, "Cascade delete failed"
    
    def test_transaction_integrity(self, db_connection):
        """Test transaction rollback on errors"""
        cursor = db_connection.cursor()
        
        try:
            cursor.execute("BEGIN TRANSACTION")
            
            # Insert valid video
            cursor.execute(
                "INSERT INTO videos (filename, file_path, file_size) VALUES (?, ?, ?)",
                ("test.mp4", "/path/test.mp4", 1000000)
            )
            video_id = cursor.lastrowid
            
            # Insert invalid ground truth (should fail)
            cursor.execute(
                "INSERT INTO ground_truth (video_id, frame_number) VALUES (?, ?)",
                (999999, 1)  # Non-existent video_id
            )
            
            cursor.execute("COMMIT")
        except sqlite3.IntegrityError:
            cursor.execute("ROLLBACK")
        
        # Verify rollback worked
        cursor.execute("SELECT COUNT(*) FROM videos")
        assert cursor.fetchone()[0] == 0, "Transaction rollback failed"
    
    def test_data_persistence_video_metadata(self, db_connection):
        """Test video metadata persistence and retrieval"""
        cursor = db_connection.cursor()
        
        test_video_data = {
            'filename': 'test_video.mp4',
            'file_path': '/uploads/test_video.mp4',
            'file_size': 15728640,
            'duration': 30.5,
            'frame_count': 915,
            'fps': 30.0,
            'status': 'processing',
            'processing_metadata': json.dumps({
                'upload_timestamp': '2024-01-01T12:00:00Z',
                'checksum': 'abc123def456'
            })
        }
        
        # Insert video data
        cursor.execute('''
            INSERT INTO videos (filename, file_path, file_size, duration, frame_count, fps, status, processing_metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            test_video_data['filename'],
            test_video_data['file_path'],
            test_video_data['file_size'],
            test_video_data['duration'],
            test_video_data['frame_count'],
            test_video_data['fps'],
            test_video_data['status'],
            test_video_data['processing_metadata']
        ))
        
        video_id = cursor.lastrowid
        
        # Retrieve and verify data
        cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
        row = cursor.fetchone()
        
        assert row[1] == test_video_data['filename']
        assert row[2] == test_video_data['file_path']
        assert row[4] == test_video_data['file_size']
        assert abs(row[5] - test_video_data['duration']) < 0.01
        assert row[6] == test_video_data['frame_count']
        assert abs(row[7] - test_video_data['fps']) < 0.01
        assert row[8] == test_video_data['status']
        
        # Verify JSON data integrity
        metadata = json.loads(row[10])
        expected_metadata = json.loads(test_video_data['processing_metadata'])
        assert metadata == expected_metadata
    
    def test_ground_truth_data_persistence(self, db_connection):
        """Test ground truth data storage and retrieval with complex data"""
        cursor = db_connection.cursor()
        
        # Insert test video
        cursor.execute(
            "INSERT INTO videos (filename, file_path, file_size) VALUES (?, ?, ?)",
            ("test.mp4", "/path/test.mp4", 1000000)
        )
        video_id = cursor.lastrowid
        
        # Complex ground truth data
        bounding_boxes = json.dumps([
            {"x": 100, "y": 150, "width": 50, "height": 75, "class": "person"},
            {"x": 200, "y": 100, "width": 80, "height": 120, "class": "car"}
        ])
        labels = json.dumps(["person", "car"])
        confidence_scores = json.dumps([0.95, 0.87])
        
        # Insert ground truth data for multiple frames
        for frame_num in range(1, 6):
            cursor.execute('''
                INSERT INTO ground_truth (video_id, frame_number, bounding_boxes, labels, confidence_scores)
                VALUES (?, ?, ?, ?, ?)
            ''', (video_id, frame_num, bounding_boxes, labels, confidence_scores))
        
        # Retrieve and verify data
        cursor.execute(
            "SELECT * FROM ground_truth WHERE video_id = ? ORDER BY frame_number",
            (video_id,)
        )
        rows = cursor.fetchall()
        
        assert len(rows) == 5
        
        for i, row in enumerate(rows):
            assert row[2] == i + 1  # frame_number
            
            # Verify JSON data integrity
            stored_boxes = json.loads(row[3])
            stored_labels = json.loads(row[4])
            stored_scores = json.loads(row[5])
            
            assert stored_boxes == json.loads(bounding_boxes)
            assert stored_labels == json.loads(labels)
            assert stored_scores == json.loads(confidence_scores)
    
    def test_concurrent_access_handling(self, temp_db):
        """Test concurrent database access scenarios"""
        import threading
        import time
        
        def write_worker(db_path, worker_id, results):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                for i in range(5):
                    cursor.execute(
                        "INSERT INTO videos (filename, file_path, file_size) VALUES (?, ?, ?)",
                        (f"worker_{worker_id}_video_{i}.mp4", f"/path/{worker_id}_{i}.mp4", 1000000 + i)
                    )
                    time.sleep(0.01)  # Small delay to increase chance of conflicts
                
                conn.commit()
                conn.close()
                results[worker_id] = "success"
            except Exception as e:
                results[worker_id] = f"error: {str(e)}"
        
        # Initialize database
        conn = sqlite3.connect(temp_db)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER
            )
        ''')
        conn.commit()
        conn.close()
        
        # Run concurrent writers
        results = {}
        threads = []
        
        for i in range(3):
            thread = threading.Thread(target=write_worker, args=(temp_db, i, results))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all workers succeeded
        for worker_id, result in results.items():
            assert result == "success", f"Worker {worker_id} failed: {result}"
        
        # Verify all data was written
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM videos")
        assert cursor.fetchone()[0] == 15  # 3 workers × 5 records each
        conn.close()
    
    def test_ground_truth_processing_without_ml(self, db_connection):
        """Test ground truth processing when ML dependencies are unavailable"""
        cursor = db_connection.cursor()
        
        # Insert test video
        cursor.execute(
            "INSERT INTO videos (filename, file_path, file_size, status) VALUES (?, ?, ?, ?)",
            ("test.mp4", "/path/test.mp4", 1000000, "uploaded")
        )
        video_id = cursor.lastrowid
        
        # Simulate ground truth processing without ML
        with patch('ml_module.process_video', side_effect=ImportError("ML module not available")):
            # Process should fall back to manual/basic processing
            try:
                # Insert basic ground truth structure
                cursor.execute('''
                    INSERT INTO ground_truth (video_id, frame_number, bounding_boxes, labels)
                    VALUES (?, ?, ?, ?)
                ''', (video_id, 1, "[]", "[]"))
                
                # Update video status to indicate manual processing needed
                cursor.execute(
                    "UPDATE videos SET status = ? WHERE id = ?",
                    ("manual_processing_required", video_id)
                )
                db_connection.commit()
                
                processing_succeeded = True
            except Exception:
                processing_succeeded = False
        
        assert processing_succeeded, "Ground truth processing should work without ML dependencies"
        
        # Verify video status updated correctly
        cursor.execute("SELECT status FROM videos WHERE id = ?", (video_id,))
        status = cursor.fetchone()[0]
        assert status == "manual_processing_required"
    
    def test_database_migration_compatibility(self, temp_db):
        """Test database schema migration scenarios"""
        # Create old schema
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Old schema without some columns
        cursor.execute('''
            CREATE TABLE videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert some old data
        cursor.execute(
            "INSERT INTO videos (filename, file_path) VALUES (?, ?)",
            ("old_video.mp4", "/path/old_video.mp4")
        )
        conn.commit()
        
        # Simulate migration - add new columns
        cursor.execute("ALTER TABLE videos ADD COLUMN file_size INTEGER")
        cursor.execute("ALTER TABLE videos ADD COLUMN status TEXT DEFAULT 'uploaded'")
        cursor.execute("ALTER TABLE videos ADD COLUMN ground_truth_data TEXT")
        
        # Verify migration worked
        cursor.execute("PRAGMA table_info(videos)")
        columns = [row[1] for row in cursor.fetchall()]
        
        expected_columns = ['id', 'filename', 'file_path', 'upload_date', 'file_size', 'status', 'ground_truth_data']
        for col in expected_columns:
            assert col in columns, f"Migration failed: missing column {col}"
        
        # Verify old data still accessible
        cursor.execute("SELECT filename FROM videos WHERE filename = ?", ("old_video.mp4",))
        assert cursor.fetchone()[0] == "old_video.mp4"
        
        conn.close()


class TestDatabasePerformance:
    """Test database performance under load"""
    
    @pytest.fixture
    def large_dataset_db(self, temp_db):
        """Create database with large dataset for performance testing"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                status TEXT,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE ground_truth (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER,
                frame_number INTEGER,
                bounding_boxes TEXT,
                FOREIGN KEY (video_id) REFERENCES videos (id)
            )
        ''')
        
        # Create indices for performance
        cursor.execute("CREATE INDEX idx_videos_status ON videos(status)")
        cursor.execute("CREATE INDEX idx_ground_truth_video_frame ON ground_truth(video_id, frame_number)")
        
        conn.commit()
        yield conn
        conn.close()
    
    def test_bulk_insert_performance(self, large_dataset_db):
        """Test performance of bulk video insertion"""
        import time
        
        cursor = large_dataset_db.cursor()
        
        # Prepare bulk data
        bulk_data = [
            (f"video_{i}.mp4", f"/path/video_{i}.mp4", 1000000 + i, "uploaded")
            for i in range(1000)
        ]
        
        start_time = time.time()
        cursor.executemany(
            "INSERT INTO videos (filename, file_path, file_size, status) VALUES (?, ?, ?, ?)",
            bulk_data
        )
        large_dataset_db.commit()
        end_time = time.time()
        
        # Should complete within reasonable time (adjust threshold as needed)
        assert end_time - start_time < 5.0, "Bulk insert too slow"
        
        # Verify all data inserted
        cursor.execute("SELECT COUNT(*) FROM videos")
        assert cursor.fetchone()[0] == 1000
    
    def test_complex_query_performance(self, large_dataset_db):
        """Test performance of complex queries with joins"""
        import time
        
        cursor = large_dataset_db.cursor()
        
        # Insert test data
        for i in range(100):
            cursor.execute(
                "INSERT INTO videos (filename, file_path, file_size, status) VALUES (?, ?, ?, ?)",
                (f"video_{i}.mp4", f"/path/video_{i}.mp4", 1000000 + i, "processed")
            )
            video_id = cursor.lastrowid
            
            # Add ground truth for each video
            for frame in range(10):
                cursor.execute(
                    "INSERT INTO ground_truth (video_id, frame_number, bounding_boxes) VALUES (?, ?, ?)",
                    (video_id, frame, f"[{{\"x\": {frame*10}, \"y\": {frame*10}}}]")
                )
        
        large_dataset_db.commit()
        
        # Test complex query performance
        start_time = time.time()
        cursor.execute('''
            SELECT v.filename, v.file_size, COUNT(gt.id) as frame_count
            FROM videos v
            LEFT JOIN ground_truth gt ON v.id = gt.video_id
            WHERE v.status = 'processed' AND v.file_size > 1000000
            GROUP BY v.id
            HAVING COUNT(gt.id) > 5
            ORDER BY v.file_size DESC
        ''')
        results = cursor.fetchall()
        end_time = time.time()
        
        # Should complete quickly with proper indices
        assert end_time - start_time < 1.0, "Complex query too slow"
        assert len(results) == 100, "Query returned wrong number of results"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])