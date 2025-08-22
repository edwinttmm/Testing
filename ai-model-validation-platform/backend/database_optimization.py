"""
Database Performance Optimization
Handles index creation, query optimization, and performance monitoring
"""
import logging
from sqlalchemy import create_engine, text, Index
from sqlalchemy.orm import sessionmaker
from database import engine, SessionLocal
from models import (
    Project, Video, GroundTruthObject, TestSession, DetectionEvent,
    Annotation, AnnotationSession, VideoProjectLink, TestResult,
    DetectionComparison, AuditLog
)

logger = logging.getLogger(__name__)

class DatabaseOptimizer:
    """Handles database performance optimization"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def create_performance_indexes(self):
        """Create additional performance indexes for critical queries"""
        try:
            # Critical performance indexes for main queries
            performance_indexes = [
                # Video query optimizations
                "CREATE INDEX IF NOT EXISTS idx_videos_project_status_created ON videos (project_id, status, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_videos_ground_truth_processing ON videos (ground_truth_generated, processing_status)",
                "CREATE INDEX IF NOT EXISTS idx_videos_filename_search ON videos (filename)",
                "CREATE INDEX IF NOT EXISTS idx_videos_duration_range ON videos (duration)",
                
                # Ground truth optimizations
                "CREATE INDEX IF NOT EXISTS idx_gt_video_timestamp_class ON ground_truth_objects (video_id, timestamp, class_label)",
                "CREATE INDEX IF NOT EXISTS idx_gt_confidence_validated ON ground_truth_objects (confidence, validated)",
                "CREATE INDEX IF NOT EXISTS idx_gt_spatial_query ON ground_truth_objects (x, y, width, height)",
                
                # Detection event optimizations
                "CREATE INDEX IF NOT EXISTS idx_detection_session_confidence ON detection_events (test_session_id, confidence)",
                "CREATE INDEX IF NOT EXISTS idx_detection_validation_timestamp ON detection_events (validation_result, timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_detection_class_frame ON detection_events (class_label, frame_number)",
                
                # Test session optimizations
                "CREATE INDEX IF NOT EXISTS idx_test_project_status_date ON test_sessions (project_id, status, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_test_video_session ON test_sessions (video_id, id)",
                
                # Annotation optimizations
                "CREATE INDEX IF NOT EXISTS idx_annotation_video_vru_timestamp ON annotations (video_id, vru_type, timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_annotation_validated_annotator ON annotations (validated, annotator)",
                "CREATE INDEX IF NOT EXISTS idx_annotation_frame_bbox ON annotations (frame_number, bounding_box)",
                
                # Project optimizations
                "CREATE INDEX IF NOT EXISTS idx_project_owner_status ON projects (owner_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_project_camera_signal ON projects (camera_view, signal_type)",
                
                # Audit log optimizations
                "CREATE INDEX IF NOT EXISTS idx_audit_user_event_time ON audit_logs (user_id, event_type, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_audit_ip_time ON audit_logs (ip_address, created_at)"
            ]
            
            for index_sql in performance_indexes:
                try:
                    self.db.execute(text(index_sql))
                    logger.info(f"✅ Created index: {index_sql.split('idx_')[1].split(' ')[0] if 'idx_' in index_sql else 'unknown'}")
                except Exception as e:
                    logger.warning(f"⚠️ Index creation failed: {str(e)}")
            
            self.db.commit()
            logger.info("🚀 Database performance indexes created successfully")
            
        except Exception as e:
            logger.error(f"❌ Database optimization failed: {str(e)}")
            self.db.rollback()
    
    def analyze_query_performance(self):
        """Analyze common query performance"""
        try:
            performance_queries = [
                # Video listing query
                ("Video Listing", """
                    EXPLAIN QUERY PLAN 
                    SELECT v.id, v.filename, v.status, v.created_at, 
                           COUNT(gt.id) as detection_count
                    FROM videos v
                    LEFT JOIN ground_truth_objects gt ON v.id = gt.video_id
                    WHERE v.project_id = ?
                    GROUP BY v.id
                    ORDER BY v.created_at DESC
                """),
                
                # Ground truth query
                ("Ground Truth Query", """
                    EXPLAIN QUERY PLAN
                    SELECT * FROM ground_truth_objects 
                    WHERE video_id = ? AND timestamp BETWEEN ? AND ?
                    ORDER BY timestamp
                """),
                
                # Detection events query
                ("Detection Events", """
                    EXPLAIN QUERY PLAN
                    SELECT * FROM detection_events 
                    WHERE test_session_id = ? AND validation_result = ?
                    ORDER BY timestamp
                """),
                
                # Dashboard stats query
                ("Dashboard Stats", """
                    EXPLAIN QUERY PLAN
                    SELECT 
                        COUNT(DISTINCT p.id) as projects,
                        COUNT(DISTINCT v.id) as videos,
                        COUNT(DISTINCT ts.id) as test_sessions,
                        AVG(de.confidence) as avg_confidence
                    FROM projects p
                    LEFT JOIN videos v ON p.id = v.project_id
                    LEFT JOIN test_sessions ts ON p.id = ts.project_id
                    LEFT JOIN detection_events de ON ts.id = de.test_session_id
                """)
            ]
            
            for query_name, query_sql in performance_queries:
                try:
                    # For SQLite, use EXPLAIN QUERY PLAN
                    result = self.db.execute(text(query_sql), ["dummy-id", 0.0, 10.0])
                    logger.info(f"📊 {query_name} query plan analyzed")
                except Exception as e:
                    logger.warning(f"⚠️ Query analysis failed for {query_name}: {str(e)}")
            
        except Exception as e:
            logger.error(f"❌ Query performance analysis failed: {str(e)}")
    
    def get_database_statistics(self):
        """Get database size and table statistics"""
        try:
            stats_queries = [
                ("Projects", "SELECT COUNT(*) FROM projects"),
                ("Videos", "SELECT COUNT(*) FROM videos"),
                ("Ground Truth Objects", "SELECT COUNT(*) FROM ground_truth_objects"),
                ("Test Sessions", "SELECT COUNT(*) FROM test_sessions"),
                ("Detection Events", "SELECT COUNT(*) FROM detection_events"),
                ("Annotations", "SELECT COUNT(*) FROM annotations"),
                ("Annotation Sessions", "SELECT COUNT(*) FROM annotation_sessions"),
                ("Audit Logs", "SELECT COUNT(*) FROM audit_logs")
            ]
            
            statistics = {}
            total_records = 0
            
            for table_name, query in stats_queries:
                try:
                    result = self.db.execute(text(query)).scalar()
                    statistics[table_name] = result
                    total_records += result
                except Exception as e:
                    logger.warning(f"⚠️ Failed to get stats for {table_name}: {str(e)}")
                    statistics[table_name] = 0
            
            # Database file size (for SQLite)
            try:
                db_size_query = "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
                db_size = self.db.execute(text(db_size_query)).scalar()
                statistics["Database Size (bytes)"] = db_size
                statistics["Database Size (MB)"] = round(db_size / (1024 * 1024), 2) if db_size else 0
            except Exception as e:
                logger.warning(f"⚠️ Failed to get database size: {str(e)}")
            
            statistics["Total Records"] = total_records
            
            logger.info("📈 Database Statistics:")
            for key, value in statistics.items():
                logger.info(f"   {key}: {value:,}")
            
            return statistics
            
        except Exception as e:
            logger.error(f"❌ Database statistics collection failed: {str(e)}")
            return {}
    
    def optimize_database(self):
        """Run comprehensive database optimization"""
        try:
            logger.info("🔧 Starting database optimization...")
            
            # Create performance indexes
            self.create_performance_indexes()
            
            # Run VACUUM for SQLite (cleanup and defragment)
            try:
                self.db.execute(text("VACUUM"))
                self.db.commit()
                logger.info("✅ Database vacuum completed")
            except Exception as e:
                logger.warning(f"⚠️ Database vacuum failed: {str(e)}")
            
            # Update statistics
            try:
                self.db.execute(text("ANALYZE"))
                self.db.commit()
                logger.info("✅ Database statistics updated")
            except Exception as e:
                logger.warning(f"⚠️ Statistics update failed: {str(e)}")
            
            # Get database statistics
            stats = self.get_database_statistics()
            
            # Analyze query performance
            self.analyze_query_performance()
            
            logger.info("🚀 Database optimization completed successfully!")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Database optimization failed: {str(e)}")
            return {}
        finally:
            self.db.close()

def optimize_database():
    """Convenience function to optimize database"""
    optimizer = DatabaseOptimizer()
    return optimizer.optimize_database()

if __name__ == "__main__":
    # Run optimization
    import sys
    import os
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 Starting database optimization...")
    stats = optimize_database()
    
    if stats:
        print("\n📊 Optimization completed successfully!")
        print(f"   Total records: {stats.get('Total Records', 0):,}")
        print(f"   Database size: {stats.get('Database Size (MB)', 0)} MB")
    else:
        print("❌ Optimization failed!")
        sys.exit(1)