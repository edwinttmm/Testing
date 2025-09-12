#!/usr/bin/env python3
"""
ML Pipeline Analysis Report Generator
====================================

Creates a comprehensive analysis report of the ML pipeline based on code inspection,
file analysis, and available test data without requiring full ML dependencies.
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path
import uuid

def analyze_ml_pipeline_architecture():
    """Analyze ML pipeline architecture from source code"""
    analysis = {
        "timestamp": datetime.now().isoformat(),
        "analysis_type": "static_code_analysis",
        "findings": {}
    }
    
    # Analyze detection pipeline service
    detection_service_path = Path("backend/services/detection_pipeline_service.py")
    if detection_service_path.exists():
        with open(detection_service_path, 'r') as f:
            content = f.read()
            
        analysis["findings"]["detection_pipeline"] = {
            "file_size": len(content),
            "lines_of_code": len(content.split('\n')),
            "key_components": {
                "model_registry": "ModelRegistry" in content,
                "real_yolo_wrapper": "RealYOLOv8Wrapper" in content,
                "detection_pipeline": "DetectionPipeline" in content,
                "frame_processor": "FrameProcessor" in content,
                "screenshot_capture": "ScreenshotCapture" in content,
                "batch_processor": "BatchProcessor" in content
            },
            "ml_models_supported": {
                "yolo11l": "yolo11l" in content,
                "yolov8": "yolov8" in content,
                "torch_integration": "torch" in content,
                "ultralytics_integration": "ultralytics" in content
            },
            "vru_detection_classes": {
                "pedestrian": "pedestrian" in content,
                "cyclist": "cyclist" in content,
                "motorcyclist": "motorcyclist" in content,
                "wheelchair_user": "wheelchair_user" in content,
                "scooter_rider": "scooter_rider" in content
            },
            "advanced_features": {
                "async_processing": "async def" in content,
                "batch_processing": "batch" in content.lower(),
                "screenshot_capture": "screenshot" in content.lower(),
                "performance_optimization": "performance" in content.lower(),
                "error_handling": "except" in content,
                "confidence_thresholds": "confidence" in content
            }
        }
    
    # Analyze main application
    main_app_path = Path("backend/main.py")
    if main_app_path.exists():
        with open(main_app_path, 'r') as f:
            content = f.read()
            
        analysis["findings"]["main_application"] = {
            "fastapi_integration": "FastAPI" in content,
            "ml_auto_install": "auto_install_ml" in content,
            "detection_endpoints": "/detection" in content,
            "video_upload": "upload" in content,
            "socketio_support": "socketio" in content,
            "health_check": "health" in content
        }
    
    return analysis

def analyze_test_videos():
    """Analyze available test videos"""
    analysis = {
        "timestamp": datetime.now().isoformat(),
        "video_analysis": {}
    }
    
    uploads_dir = Path("backend/uploads")
    if uploads_dir.exists():
        video_files = list(uploads_dir.glob("*.mp4")) + list(uploads_dir.glob("*.avi"))
        
        analysis["video_analysis"] = {
            "total_videos": len(video_files),
            "video_files": [],
            "total_size_mb": 0
        }
        
        for video_file in video_files:
            file_size_mb = video_file.stat().st_size / (1024 * 1024)
            analysis["video_analysis"]["video_files"].append({
                "filename": video_file.name,
                "size_mb": file_size_mb,
                "path": str(video_file)
            })
            analysis["video_analysis"]["total_size_mb"] += file_size_mb
    
    # Also check for test videos
    test_videos = list(Path(".").rglob("*.mp4"))
    analysis["video_analysis"]["all_test_videos"] = len(test_videos)
    
    return analysis

def analyze_ml_dependencies():
    """Analyze ML dependency requirements"""
    analysis = {
        "timestamp": datetime.now().isoformat(),
        "dependency_analysis": {}
    }
    
    # Check requirements files
    req_files = [
        "backend/requirements-ml-auto.txt",
        "backend/requirements.txt",
        "requirements.txt"
    ]
    
    for req_file in req_files:
        req_path = Path(req_file)
        if req_path.exists():
            with open(req_path, 'r') as f:
                content = f.read()
                
            analysis["dependency_analysis"][req_file] = {
                "pytorch": "torch" in content,
                "ultralytics": "ultralytics" in content,
                "opencv": "opencv" in content,
                "numpy": "numpy" in content,
                "pillow": "pillow" in content or "PIL" in content,
                "cpu_only": "+cpu" in content,
                "gpu_support": "cuda" in content or "+cu" in content
            }
    
    return analysis

def analyze_api_endpoints():
    """Analyze ML-related API endpoints"""
    analysis = {
        "timestamp": datetime.now().isoformat(),
        "api_analysis": {}
    }
    
    # Check main.py for ML endpoints
    main_path = Path("backend/main.py")
    if main_path.exists():
        with open(main_path, 'r') as f:
            content = f.read()
        
        analysis["api_analysis"]["ml_endpoints"] = {
            "video_upload": "/api/videos/upload" in content or "upload" in content,
            "detection_processing": "detection" in content.lower(),
            "ground_truth": "ground_truth" in content or "ground-truth" in content,
            "validation": "validation" in content,
            "health_check": "/health" in content
        }
    
    # Check for additional API files
    api_files = list(Path("backend").rglob("api_*.py")) + list(Path("backend").rglob("*_api.py"))
    analysis["api_analysis"]["additional_api_files"] = len(api_files)
    
    return analysis

def generate_performance_expectations():
    """Generate performance expectations based on code analysis"""
    expectations = {
        "timestamp": datetime.now().isoformat(),
        "performance_expectations": {
            "model_loading": {
                "yolo11n": "< 5 seconds",
                "yolo11l": "< 15 seconds",
                "expected_memory": "500MB - 2GB"
            },
            "inference_performance": {
                "single_frame_640x640": "< 100ms (CPU), < 20ms (GPU)",
                "batch_processing_8_frames": "< 500ms (CPU), < 100ms (GPU)",
                "video_processing_fps": "5-15 FPS (CPU), 20-60 FPS (GPU)"
            },
            "detection_accuracy": {
                "pedestrian_detection": "> 80% recall",
                "cyclist_detection": "> 70% recall",
                "false_positive_rate": "< 10%",
                "confidence_threshold": "0.4-0.5 for production"
            },
            "system_requirements": {
                "minimum_ram": "4GB",
                "recommended_ram": "8GB+",
                "cpu_cores": "4+ cores recommended",
                "gpu": "Optional but significantly improves performance"
            }
        }
    }
    return expectations

def assess_production_readiness():
    """Assess production readiness of ML pipeline"""
    assessment = {
        "timestamp": datetime.now().isoformat(),
        "production_readiness": {}
    }
    
    # Check for production features
    features_to_check = [
        ("Error handling", Path("backend/services/detection_pipeline_service.py")),
        ("Logging", Path("backend/services/detection_pipeline_service.py")),
        ("Health checks", Path("backend/health_check.py")),
        ("Configuration management", Path("backend/config.py")),
        ("Database integration", Path("backend/database.py")),
        ("API documentation", Path("backend/main.py"))
    ]
    
    production_score = 0
    max_score = len(features_to_check)
    
    for feature_name, file_path in features_to_check:
        if file_path.exists():
            with open(file_path, 'r') as f:
                content = f.read()
                
            has_feature = False
            if feature_name == "Error handling":
                has_feature = "try:" in content and "except" in content
            elif feature_name == "Logging":
                has_feature = "logging" in content or "logger" in content
            elif feature_name == "Health checks":
                has_feature = "health" in content.lower()
            elif feature_name == "Configuration management":
                has_feature = "config" in content.lower() or "settings" in content
            elif feature_name == "Database integration":
                has_feature = "database" in content.lower() or "db" in content
            elif feature_name == "API documentation":
                has_feature = "swagger" in content or "docs" in content
            
            if has_feature:
                production_score += 1
            
            assessment["production_readiness"][feature_name] = has_feature
    
    assessment["production_readiness"]["overall_score"] = f"{production_score}/{max_score}"
    assessment["production_readiness"]["percentage"] = (production_score / max_score * 100) if max_score > 0 else 0
    
    return assessment

def generate_comprehensive_report():
    """Generate comprehensive ML pipeline analysis report"""
    report = {
        "report_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "report_type": "ML Pipeline Comprehensive Analysis",
        "version": "1.0",
        "sections": {}
    }
    
    print("🔍 Analyzing ML Pipeline Architecture...")
    report["sections"]["architecture"] = analyze_ml_pipeline_architecture()
    
    print("🎬 Analyzing Test Videos...")
    report["sections"]["test_videos"] = analyze_test_videos()
    
    print("📦 Analyzing ML Dependencies...")
    report["sections"]["dependencies"] = analyze_ml_dependencies()
    
    print("🌐 Analyzing API Endpoints...")
    report["sections"]["api_endpoints"] = analyze_api_endpoints()
    
    print("⚡ Generating Performance Expectations...")
    report["sections"]["performance_expectations"] = generate_performance_expectations()
    
    print("🏭 Assessing Production Readiness...")
    report["sections"]["production_readiness"] = assess_production_readiness()
    
    return report

def generate_test_recommendations(report):
    """Generate testing recommendations based on analysis"""
    recommendations = {
        "timestamp": datetime.now().isoformat(),
        "recommendations": []
    }
    
    # Architecture-based recommendations
    if report["sections"]["architecture"]["findings"].get("detection_pipeline", {}).get("key_components", {}).get("model_registry"):
        recommendations["recommendations"].append({
            "priority": "HIGH",
            "category": "Model Testing",
            "recommendation": "Test model registry with different YOLO model sizes (nano, small, medium, large)",
            "reason": "ModelRegistry component found - should test model loading and switching"
        })
    
    if report["sections"]["architecture"]["findings"].get("detection_pipeline", {}).get("advanced_features", {}).get("batch_processing"):
        recommendations["recommendations"].append({
            "priority": "HIGH",
            "category": "Performance Testing",
            "recommendation": "Test batch processing with different batch sizes (1, 4, 8, 16)",
            "reason": "Batch processing capability detected - critical for performance"
        })
    
    # Video-based recommendations
    video_count = report["sections"]["test_videos"]["video_analysis"].get("total_videos", 0)
    if video_count > 0:
        recommendations["recommendations"].append({
            "priority": "HIGH",
            "category": "Video Processing",
            "recommendation": f"Test video processing pipeline with all {video_count} available videos",
            "reason": f"Found {video_count} test videos available for comprehensive testing"
        })
    else:
        recommendations["recommendations"].append({
            "priority": "CRITICAL",
            "category": "Test Data",
            "recommendation": "Upload test videos for comprehensive ML pipeline testing",
            "reason": "No test videos found - cannot validate video processing functionality"
        })
    
    # Dependency-based recommendations
    has_gpu_support = any(
        dep_info.get("gpu_support", False) 
        for dep_info in report["sections"]["dependencies"]["dependency_analysis"].values()
    )
    
    if has_gpu_support:
        recommendations["recommendations"].append({
            "priority": "MEDIUM",
            "category": "Performance Testing",
            "recommendation": "Test both CPU and GPU inference performance",
            "reason": "GPU support detected - should validate performance differences"
        })
    
    # Production readiness recommendations
    prod_percentage = report["sections"]["production_readiness"]["production_readiness"].get("percentage", 0)
    if prod_percentage < 80:
        recommendations["recommendations"].append({
            "priority": "HIGH",
            "category": "Production Readiness",
            "recommendation": "Improve production readiness features (error handling, logging, monitoring)",
            "reason": f"Production readiness score is {prod_percentage:.1f}% - below 80% threshold"
        })
    
    return recommendations

def main():
    """Main analysis execution"""
    print("🔬 ML Pipeline Comprehensive Analysis Report")
    print("=" * 60)
    
    # Generate comprehensive report
    report = generate_comprehensive_report()
    
    # Generate recommendations
    print("💡 Generating Test Recommendations...")
    recommendations = generate_test_recommendations(report)
    report["recommendations"] = recommendations
    
    # Save reports
    report_file = f"tests/ml_pipeline_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    Path("tests").mkdir(exist_ok=True)
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    # Generate summary
    print("\n" + "=" * 60)
    print("📊 ML PIPELINE ANALYSIS SUMMARY")
    print("=" * 60)
    
    # Architecture summary
    arch_findings = report["sections"]["architecture"]["findings"]
    if "detection_pipeline" in arch_findings:
        pipeline_components = arch_findings["detection_pipeline"]["key_components"]
        active_components = sum(1 for v in pipeline_components.values() if v)
        print(f"🏗️  Pipeline Components: {active_components}/6 detected")
        
        ml_models = arch_findings["detection_pipeline"]["ml_models_supported"]
        active_models = sum(1 for v in ml_models.values() if v)
        print(f"🤖 ML Models Supported: {active_models}/4 detected")
        
        vru_classes = arch_findings["detection_pipeline"]["vru_detection_classes"]
        active_vru = sum(1 for v in vru_classes.values() if v)
        print(f"🚶 VRU Classes: {active_vru}/5 supported")
    
    # Video analysis summary
    video_analysis = report["sections"]["test_videos"]["video_analysis"]
    print(f"🎬 Test Videos: {video_analysis.get('total_videos', 0)} available ({video_analysis.get('total_size_mb', 0):.1f} MB)")
    
    # Production readiness
    prod_readiness = report["sections"]["production_readiness"]["production_readiness"]
    print(f"🏭 Production Readiness: {prod_readiness.get('percentage', 0):.1f}%")
    
    # Recommendations
    rec_count = len(recommendations["recommendations"])
    high_priority = len([r for r in recommendations["recommendations"] if r["priority"] == "HIGH"])
    critical_priority = len([r for r in recommendations["recommendations"] if r["priority"] == "CRITICAL"])
    
    print(f"💡 Recommendations: {rec_count} total ({critical_priority} critical, {high_priority} high priority)")
    
    print(f"\n📄 Full report saved to: {report_file}")
    
    # Print key recommendations
    if critical_priority > 0:
        print("\n🚨 CRITICAL RECOMMENDATIONS:")
        for rec in recommendations["recommendations"]:
            if rec["priority"] == "CRITICAL":
                print(f"   • {rec['recommendation']}")
    
    if high_priority > 0:
        print("\n⚠️  HIGH PRIORITY RECOMMENDATIONS:")
        for rec in recommendations["recommendations"][:3]:  # Show top 3
            if rec["priority"] == "HIGH":
                print(f"   • {rec['recommendation']}")
    
    print("\n🎯 OVERALL ASSESSMENT:")
    if prod_readiness.get('percentage', 0) >= 80 and video_analysis.get('total_videos', 0) > 0:
        print("✅ ML Pipeline appears well-structured and ready for comprehensive testing")
    elif prod_readiness.get('percentage', 0) >= 60:
        print("⚠️  ML Pipeline is functional but needs improvements for production readiness")
    else:
        print("🚨 ML Pipeline needs significant work before comprehensive testing")
    
    return report

if __name__ == "__main__":
    main()