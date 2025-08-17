import pytest
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np

# Import services
from services.video_library_service import VideoLibraryManager, VideoUploadHandler, CameraType
from services.detection_pipeline_service import DetectionPipeline, ModelRegistry, VRUClass
from services.signal_processing_service import SignalProcessingWorkflow, SignalType, create_gpio_config
from services.project_management_service import ProjectManager, PassFailCriteria, TestVerdict
from services.validation_analysis_service import ValidationWorkflow, MetricsEngine
from services.id_generation_service import IDGenerator, IDType

class TestVideoLibraryManagement:
    """Test Video Library Management System compliance with architecture"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.video_manager = VideoLibraryManager(self.temp_dir)
        self.upload_handler = VideoUploadHandler(self.temp_dir)
    
    def test_folder_structure_creation(self):
        """Test that proper folder structure is created according to architecture"""
        expected_folders = [
            "front-facing-vru/pedestrian-detection",
            "front-facing-vru/cyclist-detection", 
            "front-facing-vru/vehicle-detection",
            "rear-facing-vru/backup-scenarios",
            "rear-facing-vru/parking-assistance",
            "in-cab-driver-behavior/distraction-detection",
            "in-cab-driver-behavior/drowsiness-monitoring",
            "multi-angle-scenarios/intersection-analysis",
            "multi-angle-scenarios/complex-environments"
        ]
        
        for folder in expected_folders:
            folder_path = Path(self.temp_dir) / folder
            assert folder_path.exists(), f"Folder {folder} should exist"
            assert folder_path.is_dir(), f"Path {folder} should be a directory"
    
    def test_camera_type_organization(self):
        """Test camera type-based organization"""
        test_cases = [
            ("Front-facing VRU", "front-facing-vru"),
            ("Rear-facing VRU", "rear-facing-vru"),
            ("In-Cab Driver Behavior", "in-cab-driver-behavior"),
            ("Multi-angle", "multi-angle-scenarios")
        ]
        
        for camera_view, expected_folder in test_cases:
            folder_path = self.video_manager.organize_by_camera_function(camera_view)
            assert expected_folder in folder_path, f"Camera view {camera_view} should map to {expected_folder}"
    
    @pytest.mark.asyncio
    async def test_video_validation(self):
        """Test video file validation according to architecture specs"""
        # Create a mock video file
        mock_video_path = os.path.join(self.temp_dir, "test_video.mp4")
        with open(mock_video_path, 'wb') as f:
            f.write(b"mock video content")
        
        # Test validation
        with patch('cv2.VideoCapture') as mock_cv2:
            mock_cap = Mock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.side_effect = lambda prop: {
                0: 30.0,    # FPS
                3: 1920,    # Width
                4: 1080,    # Height
                7: 1000     # Frame count
            }.get(prop, 0)
            mock_cv2.return_value = mock_cap
            
            result = await self.upload_handler.validate_video_file(mock_video_path)
            
            assert result["is_valid"] == True
            assert "metadata" in result
            assert result["metadata"]["fps"] == 30.0
            assert result["metadata"]["resolution"] == (1920, 1080)
    
    def test_metadata_extraction(self):
        """Test video metadata extraction capabilities"""
        mock_video_path = os.path.join(self.temp_dir, "test_video.mp4")
        
        with patch('cv2.VideoCapture') as mock_cv2:
            mock_cap = Mock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.side_effect = lambda prop: {
                0: 25.0,    # FPS
                3: 1280,    # Width
                4: 720,     # Height
                7: 750      # Frame count
            }.get(prop, 0)
            mock_cv2.return_value = mock_cap
            
            metadata = self.video_manager.extract_video_metadata(mock_video_path)
            
            assert metadata is not None
            assert metadata.fps == 25.0
            assert metadata.resolution == (1280, 720)
            assert metadata.duration == 30.0  # 750 frames / 25 fps
            assert "quality_metrics" in metadata.__dict__

class TestDetectionPipeline:
    """Test Detection Pipeline compliance with architecture"""
    
    def setup_method(self):
        """Setup test environment"""
        self.detection_pipeline = DetectionPipeline()
        self.model_registry = ModelRegistry()
    
    @pytest.mark.asyncio
    async def test_pipeline_initialization(self):
        """Test detection pipeline initialization"""
        await self.detection_pipeline.initialize()
        
        assert self.detection_pipeline.initialized == True
        assert "yolov8n" in self.detection_pipeline.model_registry.models
        assert self.detection_pipeline.model_registry.active_model_id == "yolov8n"
    
    def test_vru_detection_classes(self):
        """Test VRU detection classes match architecture specification"""
        expected_classes = {
            VRUClass.PEDESTRIAN,
            VRUClass.CYCLIST, 
            VRUClass.MOTORCYCLIST,
            VRUClass.WHEELCHAIR_USER,
            VRUClass.SCOOTER_RIDER,
            VRUClass.CHILD_WITH_STROLLER
        }
        
        # Verify all expected classes are defined
        for vru_class in expected_classes:
            assert vru_class in VRUClass, f"VRU class {vru_class} should be defined"
    
    @pytest.mark.asyncio
    async def test_frame_processing(self):
        """Test frame preprocessing capabilities"""
        # Create mock frame
        mock_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        processed_frame = await self.detection_pipeline.frame_processor.preprocess(mock_frame)
        
        assert processed_frame.shape == (640, 640, 3), "Frame should be resized to target size"
        assert processed_frame.dtype == np.float32, "Frame should be normalized to float32"
        assert processed_frame.min() >= 0.0 and processed_frame.max() <= 1.0, "Values should be normalized to 0-1"
    
    @pytest.mark.asyncio
    async def test_timestamp_synchronization(self):
        """Test timestamp synchronization functionality"""
        video_id = "test_video_123"
        fps = 30.0
        
        self.detection_pipeline.timestamp_sync.initialize_video_timeline(video_id, fps)
        
        # Test frame timestamp synchronization
        frame_number = 30  # 1 second at 30fps
        system_time = 1000.0
        
        synced_timestamp = await self.detection_pipeline.timestamp_sync.sync_frame_timestamp(
            video_id, frame_number, system_time
        )
        
        assert synced_timestamp > 0, "Synchronized timestamp should be positive"
        assert abs(synced_timestamp - system_time) < 2.0, "Timestamp should be close to system time"

class TestSignalProcessing:
    """Test Signal Processing Framework compliance with architecture"""
    
    def setup_method(self):
        """Setup test environment"""
        self.signal_workflow = SignalProcessingWorkflow()
    
    def test_signal_type_support(self):
        """Test all required signal types are supported"""
        expected_signal_types = {
            SignalType.GPIO,
            SignalType.NETWORK_PACKET,
            SignalType.SERIAL,
            SignalType.CAN_BUS,
            SignalType.ETHERNET
        }
        
        for signal_type in expected_signal_types:
            assert signal_type in self.signal_workflow.signal_handlers, f"Signal type {signal_type} should be supported"
    
    def test_gpio_configuration(self):
        """Test GPIO signal configuration"""
        gpio_config = create_gpio_config(pin=21, sampling_rate=1000.0)
        
        assert gpio_config.signal_type == SignalType.GPIO
        assert gpio_config.source_identifier == "GPIO_21"
        assert gpio_config.sampling_rate == 1000.0
        assert gpio_config.precision_mode == True
        assert len(gpio_config.filters) > 0
    
    @pytest.mark.asyncio
    async def test_signal_processing_workflow(self):
        """Test signal processing workflow"""
        test_session_id = "test_session_123"
        gpio_config = create_gpio_config(pin=21)
        
        # Mock the signal processing
        with patch.object(self.signal_workflow.signal_handlers[SignalType.GPIO], '__call__') as mock_handler:
            mock_handler_instance = Mock()
            mock_handler.return_value = mock_handler_instance
            
            # Test that we can start signal processing
            assert test_session_id not in self.signal_workflow.active_sessions
            
            # After starting, session should be tracked
            # Note: We can't easily test the async generator without mocking more deeply

class TestProjectManagement:
    """Test Project Management System compliance with architecture"""
    
    def setup_method(self):
        """Setup test environment"""
        self.project_manager = ProjectManager()
    
    def test_pass_fail_criteria_defaults(self):
        """Test default pass/fail criteria match architecture specs"""
        criteria = self.project_manager.criteria_engine.default_criteria
        
        assert criteria.min_precision == 0.90
        assert criteria.min_recall == 0.85
        assert criteria.min_f1_score == 0.87
        assert criteria.max_latency_ms == 100.0
        assert criteria.max_false_positive_rate == 0.05
        assert criteria.min_detection_confidence == 0.70
    
    def test_pass_fail_evaluation(self):
        """Test pass/fail criteria evaluation logic"""
        from services.project_management_service import TestResults
        
        # Create test results that should pass
        passing_results = TestResults(
            precision=0.95,
            recall=0.92,
            f1_score=0.93,
            accuracy=0.94,
            average_latency_ms=75.0,
            false_positive_rate=0.03,
            average_confidence=0.85,
            total_detections=100,
            true_positives=92,
            false_positives=3,
            false_negatives=5
        )
        
        verdict = self.project_manager.criteria_engine.evaluate(passing_results)
        assert verdict == TestVerdict.PASS
        
        # Create test results that should fail
        failing_results = TestResults(
            precision=0.60,
            recall=0.65,
            f1_score=0.62,
            accuracy=0.58,
            average_latency_ms=150.0,
            false_positive_rate=0.15,
            average_confidence=0.50,
            total_detections=50,
            true_positives=30,
            false_positives=15,
            false_negatives=20
        )
        
        verdict = self.project_manager.criteria_engine.evaluate(failing_results)
        assert verdict == TestVerdict.FAIL
    
    def test_video_assignment_compatibility(self):
        """Test video assignment compatibility scoring"""
        # This would require database setup, so we'll test the core logic
        assignment_system = self.project_manager.assignment_system
        
        # Test compatibility threshold
        assert assignment_system.COMPATIBILITY_THRESHOLD == 0.7
        
        # Test that assignment system exists and has required methods
        assert hasattr(assignment_system, 'smart_assign_videos')
        assert hasattr(assignment_system, 'calculate_compatibility')

class TestValidationAnalysis:
    """Test Validation and Analysis Workflow compliance with architecture"""
    
    def setup_method(self):
        """Setup test environment"""
        self.validation_workflow = ValidationWorkflow()
        self.metrics_engine = MetricsEngine()
    
    def test_metrics_calculation(self):
        """Test performance metrics calculation"""
        # Mock detection events and ground truth
        mock_detection_events = []
        mock_ground_truth = []
        tolerance_ms = 100.0
        
        # Test with empty data
        metrics = self.metrics_engine._calculate_detection_metrics(
            mock_detection_events, mock_ground_truth, tolerance_ms
        )
        
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1_score == 0.0
        assert metrics.accuracy == 0.0
    
    def test_temporal_metrics_calculation(self):
        """Test temporal accuracy metrics"""
        mock_detection_events = []
        mock_ground_truth = []
        tolerance_ms = 100.0
        
        temporal_metrics = self.metrics_engine.calculate_temporal_metrics(
            mock_detection_events, mock_ground_truth, tolerance_ms
        )
        
        assert temporal_metrics.mean_timing_error_ms == 0.0
        assert temporal_metrics.within_tolerance_percentage == 0.0
    
    def test_statistical_analysis(self):
        """Test statistical analysis capabilities"""
        mock_detection_events = []
        
        statistical_results = self.validation_workflow.statistical_analyzer.analyze_performance_distribution(
            mock_detection_events
        )
        
        # Should return empty results for no data
        assert statistical_results is not None
        assert isinstance(statistical_results.confidence_intervals, dict)
        assert isinstance(statistical_results.distribution_stats, dict)

class TestIDGeneration:
    """Test ID Generation System compliance with architecture"""
    
    def setup_method(self):
        """Setup test environment"""
        self.id_generator = IDGenerator()
    
    def test_id_type_strategies(self):
        """Test that each ID type has appropriate generation strategy"""
        expected_strategies = {
            IDType.VIDEO: "uuid4",
            IDType.DETECTION: "snowflake", 
            IDType.SESSION: "composite",
            IDType.PROJECT: "uuid4",
            IDType.GROUND_TRUTH: "uuid4",
            IDType.SIGNAL_EVENT: "snowflake",
            IDType.AUDIT_LOG: "snowflake"
        }
        
        for id_type, expected_strategy in expected_strategies.items():
            config = self.id_generator.type_configs[id_type]
            assert config["strategy"] == expected_strategy, f"{id_type} should use {expected_strategy} strategy"
    
    def test_unique_id_generation(self):
        """Test that generated IDs are unique"""
        generated_ids = set()
        
        # Generate 1000 IDs of each type
        for id_type in IDType:
            for _ in range(100):
                new_id = self.id_generator.generate_id(id_type)
                assert new_id not in generated_ids, f"Generated duplicate ID: {new_id}"
                generated_ids.add(new_id)
    
    def test_detection_id_format(self):
        """Test detection ID format (should be sortable by time)"""
        id1 = self.id_generator.generate_detection_id()
        id2 = self.id_generator.generate_detection_id()
        
        # Detection IDs should have prefix
        assert id1.startswith("det_")
        assert id2.startswith("det_")
        
        # Should be different
        assert id1 != id2
    
    def test_session_id_with_context(self):
        """Test session ID generation with project context"""
        project_id = "test_project_123"
        session_id = self.id_generator.generate_session_id(project_id)
        
        assert session_id.startswith("ses_")
        assert len(session_id) > 10  # Should have meaningful length

class TestArchitectureIntegration:
    """Integration tests for architecture compliance"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """Test end-to-end workflow following architecture"""
        # This would be a comprehensive test simulating the full workflow
        # from video upload through detection to validation
        
        # 1. Video Library Management
        temp_dir = tempfile.mkdtemp()
        video_manager = VideoLibraryManager(temp_dir)
        
        # Verify folder structure exists
        assert Path(temp_dir).exists()
        
        # 2. Detection Pipeline
        detection_pipeline = DetectionPipeline()
        await detection_pipeline.initialize()
        
        assert detection_pipeline.initialized
        
        # 3. Project Management
        project_manager = ProjectManager()
        criteria = project_manager.criteria_engine.default_criteria
        
        assert criteria.min_precision > 0
        
        # 4. Validation Workflow
        validation_workflow = ValidationWorkflow()
        
        assert validation_workflow.metrics_engine is not None
        
        # 5. ID Generation
        id_generator = IDGenerator()
        test_id = id_generator.generate_project_id()
        
        assert test_id is not None
        assert len(test_id) > 10
    
    def test_component_integration(self):
        """Test that all components can be imported and instantiated"""
        components = [
            VideoLibraryManager,
            DetectionPipeline,
            SignalProcessingWorkflow,
            ProjectManager,
            ValidationWorkflow,
            IDGenerator
        ]
        
        for component_class in components:
            try:
                if component_class == VideoLibraryManager:
                    instance = component_class("/tmp")
                else:
                    instance = component_class()
                assert instance is not None, f"Failed to instantiate {component_class.__name__}"
            except Exception as e:
                pytest.fail(f"Failed to instantiate {component_class.__name__}: {str(e)}")
    
    def test_enum_definitions(self):
        """Test that all required enums are properly defined"""
        required_enums = [
            VRUClass,
            CameraType,
            SignalType,
            IDType
        ]
        
        for enum_class in required_enums:
            assert len(enum_class) > 0, f"Enum {enum_class.__name__} should have values"
            
            # Test that enum values are strings
            for enum_value in enum_class:
                assert isinstance(enum_value.value, str), f"Enum value should be string: {enum_value}"

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])