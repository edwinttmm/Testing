#!/usr/bin/env python3
"""
Raw LabJack System Integration Test

This script provides comprehensive testing of the raw LabJack logging system
including high-frequency data capture, smart compression, and integration
with existing detection systems.

Features:
- Connection testing and validation
- Performance benchmarking
- Compression algorithm testing
- Integration testing with detection systems
- Data integrity verification
"""

import asyncio
import logging
import time
import sys
import os
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List
import json

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import services
from services.raw_labjack_logger import get_raw_labjack_logger, BufferConfig, TimingConfig
from services.raw_labjack_compression import get_compressor, CompressionAlgorithm
from services.raw_labjack_integration import get_raw_labjack_integration
from services.labjack_service import get_labjack_service
from database import get_db
from models import TestSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RawLabJackSystemTester:
    """Comprehensive test suite for raw LabJack logging system"""
    
    def __init__(self):
        self.raw_logger = get_raw_labjack_logger()
        self.compressor = get_compressor()
        self.integration_service = get_raw_labjack_integration()
        self.labjack_service = get_labjack_service()
        
        self.test_results = {}
        self.test_session_id = None
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run complete test suite"""
        logger.info("🚀 Starting Raw LabJack System Integration Tests")
        
        try:
            # Hardware connection tests
            await self._test_labjack_connection()
            
            # Compression tests
            await self._test_compression_algorithms()
            
            # Raw logging tests
            await self._test_raw_logging()
            
            # Integration tests
            await self._test_integration_system()
            
            # Performance tests
            await self._test_performance()
            
            # Data integrity tests
            await self._test_data_integrity()
            
            # Generate test report
            return self._generate_test_report()
            
        except Exception as e:
            logger.error(f"Test suite failed: {e}")
            self.test_results['overall_status'] = 'FAILED'
            self.test_results['error'] = str(e)
            return self.test_results
    
    async def _test_labjack_connection(self) -> None:
        """Test LabJack hardware connection and capabilities"""
        logger.info("📡 Testing LabJack hardware connection...")
        
        try:
            # Test connection
            connection_success = await self.labjack_service.connect(allow_mock=False)
            
            if not connection_success:
                logger.warning("⚠️ Hardware connection failed - testing with mock mode")
                connection_success = await self.labjack_service.connect(allow_mock=True)
            
            # Get device info
            device_info = await self.labjack_service.get_device_info()
            status = self.labjack_service.get_status()
            
            self.test_results['hardware_connection'] = {
                'connected': connection_success,
                'device_info': device_info,
                'connection_mode': status.mode.value if status.mode else 'unknown',
                'is_mock': device_info.get('is_mock', False)
            }
            
            if connection_success:
                logger.info(f"✅ LabJack connected: {device_info.get('device_type', 'unknown')}")
                if device_info.get('is_mock'):
                    logger.warning("⚠️ Running in simulation mode - real hardware not available")
            else:
                logger.error("❌ LabJack connection failed")
                
        except Exception as e:
            logger.error(f"Hardware connection test failed: {e}")
            self.test_results['hardware_connection'] = {'error': str(e)}
    
    async def _test_compression_algorithms(self) -> None:
        """Test compression algorithms with synthetic data"""
        logger.info("🗜️ Testing compression algorithms...")
        
        try:
            # Generate test data
            sample_rate = 1000
            duration_seconds = 1
            channels = ['AIN0', 'AIN1']
            samples = sample_rate * duration_seconds
            
            # Create synthetic voltage data with different characteristics
            test_datasets = {
                'sine_wave': self._generate_sine_wave_data(samples, len(channels)),
                'noise': self._generate_noise_data(samples, len(channels)),
                'step_response': self._generate_step_data(samples, len(channels)),
                'mixed_signal': self._generate_mixed_signal_data(samples, len(channels))
            }
            
            compression_results = {}
            
            for data_type, voltage_data in test_datasets.items():
                logger.info(f"  Testing {data_type} compression...")
                
                # Test each algorithm
                algorithm_results = {}
                
                for algorithm in CompressionAlgorithm:
                    try:
                        start_time = time.time()
                        
                        result = await self.compressor.compress_buffer_async(
                            voltage_data=voltage_data,
                            channels=channels,
                            sample_rate=sample_rate,
                            timestamp_ns=int(time.time() * 1e9),
                            algorithm=algorithm
                        )
                        
                        compression_time = (time.time() - start_time) * 1000
                        
                        if result.error:
                            logger.warning(f"    {algorithm.value}: FAILED - {result.error}")
                            algorithm_results[algorithm.value] = {'error': result.error}
                        else:
                            logger.info(f"    {algorithm.value}: {result.compression_ratio:.2f}x, {compression_time:.2f}ms")
                            algorithm_results[algorithm.value] = {
                                'compression_ratio': result.compression_ratio,
                                'compression_time_ms': compression_time,
                                'original_size': result.original_size,
                                'compressed_size': result.compressed_size
                            }
                        
                    except Exception as e:
                        logger.error(f"    {algorithm.value}: ERROR - {e}")
                        algorithm_results[algorithm.value] = {'error': str(e)}
                
                compression_results[data_type] = algorithm_results
            
            self.test_results['compression_tests'] = compression_results
            logger.info("✅ Compression algorithm tests completed")
            
        except Exception as e:
            logger.error(f"Compression tests failed: {e}")
            self.test_results['compression_tests'] = {'error': str(e)}
    
    async def _test_raw_logging(self) -> None:
        """Test raw LabJack data logging functionality"""
        logger.info("📊 Testing raw LabJack logging...")
        
        try:
            # Create test session in database
            db = next(get_db())
            try:
                test_session = TestSession(
                    name="Raw_LabJack_Test_Session",
                    project_id="test-project-123",  # Mock project ID
                    video_id="test-video-123",  # Mock video ID
                    status="running"
                )
                db.add(test_session)
                db.commit()
                self.test_session_id = test_session.id
            finally:
                db.close()
            
            # Test configuration
            channels = ['AIN0', 'AIN1']
            sample_rate = 1000
            test_duration = 5  # 5 second test
            
            # Start raw logging session
            logger.info("  Starting raw logging session...")
            session_id = await self.raw_logger.start_session(
                session_name="Test_Raw_Logging_Session",
                channels=channels,
                sample_rate=sample_rate,
                test_session_id=self.test_session_id,
                compression_algorithm=CompressionAlgorithm.ADAPTIVE,
                buffer_size_samples=2000  # Small buffer for quick testing
            )
            
            if not session_id:
                raise RuntimeError("Failed to start raw logging session")
            
            logger.info(f"  Session started: {session_id}")
            
            # Monitor session for test duration
            start_time = time.time()
            while (time.time() - start_time) < test_duration:
                status = self.raw_logger.get_session_status(session_id)
                if status:
                    logger.info(f"    Samples: {status['samples_captured']}, Rate: {status['actual_sample_rate']:.1f}Hz")
                await asyncio.sleep(1)
            
            # Stop session and get statistics
            logger.info("  Stopping raw logging session...")
            session_stats = self.raw_logger.stop_session(session_id)
            
            self.test_results['raw_logging'] = {
                'session_id': session_id,
                'duration_seconds': test_duration,
                'statistics': session_stats,
                'status': 'SUCCESS'
            }
            
            logger.info(f"✅ Raw logging test completed - {session_stats.get('samples_captured', 0)} samples captured")
            
        except Exception as e:
            logger.error(f"Raw logging test failed: {e}")
            self.test_results['raw_logging'] = {'error': str(e), 'status': 'FAILED'}
    
    async def _test_integration_system(self) -> None:
        """Test integration with existing detection systems"""
        logger.info("🔗 Testing integration system...")
        
        try:
            if not self.test_session_id:
                logger.warning("Skipping integration test - no test session available")
                self.test_results['integration'] = {'skipped': 'No test session available'}
                return
            
            # Test configuration
            channels = ['AIN0']
            video_config = {
                'video_id': 'test-video-123',
                'fps': 30,
                'duration': 3,
                'enable_frame_sync': True
            }
            
            # Start integrated session
            logger.info("  Starting integrated session...")
            session_ids = await self.integration_service.start_integrated_session(
                session_name="Integration_Test_Session",
                test_session_id=self.test_session_id,
                channels=channels,
                sample_rate=1000,
                video_config=video_config
            )
            
            raw_session_id = session_ids['raw_session_id']
            logger.info(f"  Integrated session started: {raw_session_id}")
            
            # Monitor for short duration
            await asyncio.sleep(3)
            
            # Get integration status
            integration_status = self.integration_service.get_integration_status(raw_session_id)
            
            # Stop integrated session
            logger.info("  Stopping integrated session...")
            stop_results = await self.integration_service.stop_integrated_session(raw_session_id)
            
            self.test_results['integration'] = {
                'session_ids': session_ids,
                'integration_status': integration_status,
                'stop_results': stop_results,
                'status': 'SUCCESS'
            }
            
            logger.info("✅ Integration system test completed")
            
        except Exception as e:
            logger.error(f"Integration test failed: {e}")
            self.test_results['integration'] = {'error': str(e), 'status': 'FAILED'}
    
    async def _test_performance(self) -> None:
        """Test system performance and resource usage"""
        logger.info("⚡ Testing system performance...")
        
        try:
            # Get initial performance metrics
            initial_metrics = self.raw_logger.get_performance_metrics()
            
            # Get compression statistics
            compression_stats = self.compressor.get_compression_stats()
            
            # Get integration performance
            integration_metrics = self.integration_service.get_performance_metrics()
            
            self.test_results['performance'] = {
                'system_metrics': initial_metrics,
                'compression_stats': compression_stats,
                'integration_metrics': integration_metrics,
                'status': 'SUCCESS'
            }
            
            logger.info("✅ Performance tests completed")
            
        except Exception as e:
            logger.error(f"Performance test failed: {e}")
            self.test_results['performance'] = {'error': str(e), 'status': 'FAILED'}
    
    async def _test_data_integrity(self) -> None:
        """Test data integrity through compression/decompression cycle"""
        logger.info("🔍 Testing data integrity...")
        
        try:
            # Generate test data
            original_data = self._generate_sine_wave_data(1000, 2)
            channels = ['AIN0', 'AIN1']
            
            # Test compression and decompression
            integrity_results = {}
            
            for algorithm in [CompressionAlgorithm.ZLIB, CompressionAlgorithm.LZMA, CompressionAlgorithm.DELTA_RLE]:
                try:
                    # Compress data
                    compression_result = await self.compressor.compress_buffer_async(
                        voltage_data=original_data,
                        channels=channels,
                        sample_rate=1000,
                        timestamp_ns=int(time.time() * 1e9),
                        algorithm=algorithm
                    )
                    
                    if compression_result.error:
                        integrity_results[algorithm.value] = {'error': compression_result.error}
                        continue
                    
                    # Decompress data
                    decompressed_data = self.compressor.decompress_buffer(
                        compression_result.compressed_data,
                        algorithm,
                        compression_result.metadata
                    )
                    
                    if decompressed_data is not None:
                        # Calculate data difference
                        diff = np.abs(original_data - decompressed_data)
                        max_error = np.max(diff)
                        mean_error = np.mean(diff)
                        
                        integrity_results[algorithm.value] = {
                            'max_error': float(max_error),
                            'mean_error': float(mean_error),
                            'data_integrity': 'PASS' if max_error < 0.001 else 'FAIL'
                        }
                    else:
                        integrity_results[algorithm.value] = {'error': 'Decompression failed'}
                    
                except Exception as e:
                    integrity_results[algorithm.value] = {'error': str(e)}
            
            self.test_results['data_integrity'] = integrity_results
            logger.info("✅ Data integrity tests completed")
            
        except Exception as e:
            logger.error(f"Data integrity test failed: {e}")
            self.test_results['data_integrity'] = {'error': str(e)}
    
    def _generate_sine_wave_data(self, samples: int, channels: int) -> np.ndarray:
        """Generate sine wave test data"""
        t = np.linspace(0, 1, samples)
        data = []
        
        for ch in range(channels):
            frequency = 10 + ch * 5  # Different frequencies per channel
            amplitude = 2.0 + ch * 0.5
            sine_wave = amplitude * np.sin(2 * np.pi * frequency * t)
            data.append(sine_wave)
        
        return np.column_stack(data).astype(np.float32)
    
    def _generate_noise_data(self, samples: int, channels: int) -> np.ndarray:
        """Generate noise test data"""
        return np.random.normal(0, 1, (samples, channels)).astype(np.float32)
    
    def _generate_step_data(self, samples: int, channels: int) -> np.ndarray:
        """Generate step response test data"""
        data = np.zeros((samples, channels), dtype=np.float32)
        
        for ch in range(channels):
            step_point = samples // (2 + ch)
            data[step_point:, ch] = 3.0 + ch * 0.5
        
        return data
    
    def _generate_mixed_signal_data(self, samples: int, channels: int) -> np.ndarray:
        """Generate mixed signal test data"""
        sine_data = self._generate_sine_wave_data(samples, channels)
        noise_data = self._generate_noise_data(samples, channels) * 0.1
        return sine_data + noise_data
    
    def _generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        try:
            # Calculate overall status
            failed_tests = []
            passed_tests = []
            
            for test_name, results in self.test_results.items():
                if isinstance(results, dict):
                    if results.get('error') or results.get('status') == 'FAILED':
                        failed_tests.append(test_name)
                    else:
                        passed_tests.append(test_name)
            
            overall_status = 'PASSED' if not failed_tests else 'FAILED'
            
            report = {
                'test_execution_time': datetime.now(timezone.utc).isoformat(),
                'overall_status': overall_status,
                'total_tests': len(self.test_results),
                'passed_tests': len(passed_tests),
                'failed_tests': len(failed_tests),
                'test_results': self.test_results,
                'failed_test_names': failed_tests,
                'passed_test_names': passed_tests,
                'summary': self._generate_test_summary()
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating test report: {e}")
            return {
                'error': str(e),
                'test_results': self.test_results
            }
    
    def _generate_test_summary(self) -> str:
        """Generate human-readable test summary"""
        try:
            summary_lines = ["Raw LabJack System Test Summary:", ""]
            
            # Hardware connection
            hw_test = self.test_results.get('hardware_connection', {})
            if hw_test.get('connected'):
                device_type = hw_test.get('device_info', {}).get('device_type', 'Unknown')
                mode = hw_test.get('connection_mode', 'unknown')
                is_mock = hw_test.get('is_mock', False)
                mock_text = " (SIMULATION)" if is_mock else " (REAL HARDWARE)"
                summary_lines.append(f"✅ Hardware: {device_type} via {mode}{mock_text}")
            else:
                summary_lines.append("❌ Hardware: Connection failed")
            
            # Compression tests
            comp_test = self.test_results.get('compression_tests', {})
            if 'error' not in comp_test:
                successful_algorithms = 0
                total_algorithms = 0
                for data_type, algorithms in comp_test.items():
                    for alg, result in algorithms.items():
                        total_algorithms += 1
                        if 'error' not in result:
                            successful_algorithms += 1
                
                summary_lines.append(f"✅ Compression: {successful_algorithms}/{total_algorithms} algorithm tests passed")
            else:
                summary_lines.append("❌ Compression: Tests failed")
            
            # Raw logging
            raw_test = self.test_results.get('raw_logging', {})
            if raw_test.get('status') == 'SUCCESS':
                stats = raw_test.get('statistics', {})
                samples = stats.get('samples_captured', 0)
                duration = stats.get('duration_seconds', 0)
                summary_lines.append(f"✅ Raw Logging: {samples} samples captured in {duration}s")
            else:
                summary_lines.append("❌ Raw Logging: Test failed")
            
            # Integration
            int_test = self.test_results.get('integration', {})
            if int_test.get('status') == 'SUCCESS':
                summary_lines.append("✅ Integration: System integration successful")
            elif 'skipped' in int_test:
                summary_lines.append("⚠️ Integration: Skipped - no test session")
            else:
                summary_lines.append("❌ Integration: Test failed")
            
            return "\n".join(summary_lines)
            
        except Exception as e:
            return f"Error generating summary: {e}"


async def main():
    """Main test execution function"""
    try:
        print("🧪 Raw LabJack System Integration Test Suite")
        print("=" * 50)
        
        # Create tester
        tester = RawLabJackSystemTester()
        
        # Run all tests
        test_results = await tester.run_all_tests()
        
        # Print summary
        print("\n" + "=" * 50)
        print("TEST RESULTS SUMMARY")
        print("=" * 50)
        
        if 'summary' in test_results:
            print(test_results['summary'])
        
        print(f"\nOverall Status: {test_results.get('overall_status', 'UNKNOWN')}")
        print(f"Tests Passed: {test_results.get('passed_tests', 0)}")
        print(f"Tests Failed: {test_results.get('failed_tests', 0)}")
        
        if test_results.get('failed_test_names'):
            print(f"Failed Tests: {', '.join(test_results['failed_test_names'])}")
        
        # Save detailed results to file
        output_file = f"raw_labjack_test_results_{int(time.time())}.json"
        try:
            with open(output_file, 'w') as f:
                json.dump(test_results, f, indent=2, default=str)
            print(f"\n📄 Detailed results saved to: {output_file}")
        except Exception as e:
            print(f"⚠️ Could not save results file: {e}")
        
        # Return appropriate exit code
        sys.exit(0 if test_results.get('overall_status') == 'PASSED' else 1)
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())