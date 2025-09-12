#!/usr/bin/env python3
"""
Test Automation Validation Script
Tests the complete hands-off automation workflow for video processing
"""

import asyncio
import aiohttp
import json
import time
import logging
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AutomationTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_api_connection(self) -> bool:
        """Test basic API connectivity"""
        try:
            async with self.session.get(f"{self.base_url}/api/health") as response:
                if response.status == 200:
                    logger.info("✅ API connection successful")
                    return True
                else:
                    logger.error(f"❌ API connection failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"❌ API connection error: {e}")
            return False
    
    async def get_projects(self) -> List[Dict[str, Any]]:
        """Get available projects for testing"""
        try:
            async with self.session.get(f"{self.base_url}/api/enhanced-test-workflow/projects") as response:
                if response.status == 200:
                    data = await response.json()
                    projects = data.get('projects', [])
                    logger.info(f"✅ Found {len(projects)} projects")
                    for project in projects:
                        logger.info(f"   - {project['name']} ({project['video_count']} videos)")
                    return projects
                else:
                    logger.error(f"❌ Failed to get projects: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"❌ Error getting projects: {e}")
            return []
    
    async def start_automated_test(self, project_id: str) -> Dict[str, Any]:
        """Start the automated test workflow"""
        config = {
            "project_id": project_id,
            "detection_window_ms": 500.0,
            "voltage_threshold": 2.5,
            "sample_rate": 1000,
            "channels": ["AIN0", "AIN1"],
            "tolerance_ms": 100
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/enhanced-test-workflow/start-test",
                json=config
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"✅ Automated test started: {result['test_session_id']}")
                    logger.info(f"   - Project: {result['project_id']}")
                    logger.info(f"   - Videos: {result['video_count']}")
                    logger.info(f"   - LabJack Mode: {result['labjack_mode']}")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to start test: {response.status} - {error_text}")
                    return {}
        except Exception as e:
            logger.error(f"❌ Error starting test: {e}")
            return {}
    
    async def monitor_test_progress(self, test_session_id: str) -> None:
        """Monitor test progress via WebSocket"""
        import websockets
        
        ws_url = self.base_url.replace('http', 'ws') + '/api/enhanced-test-workflow/ws'
        logger.info(f"🔄 Connecting to WebSocket: {ws_url}")
        
        try:
            async with websockets.connect(ws_url) as websocket:
                logger.info("✅ WebSocket connected - monitoring automation...")
                
                start_time = time.time()
                video_count = 0
                detections = 0
                
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        msg_type = data.get('type', 'unknown')
                        
                        if msg_type == 'video_start_playback':
                            video_count += 1
                            video_name = data.get('video_name', 'Unknown')
                            index = data.get('index', 0)
                            total = data.get('total', 0)
                            logger.info(f"📹 AUTO-PLAYING: Video {index + 1}/{total} - {video_name}")
                            
                        elif msg_type == 'detection_event':
                            detections += 1
                            voltage = data.get('voltage', 0)
                            delay_ms = data.get('detection_delay_ms', 0)
                            status = data.get('status', 'unknown')
                            logger.info(f"⚡ DETECTION: {voltage:.2f}V, {delay_ms:.1f}ms delay - {status.upper()}")
                            
                        elif msg_type == 'workflow_progress':
                            progress = data.get('progress', 0)
                            completed = data.get('completed_videos', 0)
                            total = data.get('total_videos', 0)
                            logger.info(f"📊 PROGRESS: {progress:.1f}% ({completed}/{total} videos)")
                            
                        elif msg_type == 'test_complete':
                            elapsed = time.time() - start_time
                            summary = data.get('summary', {})
                            logger.info("🎉 AUTOMATION COMPLETE!")
                            logger.info(f"   - Total Time: {elapsed:.1f}s")
                            logger.info(f"   - Videos Processed: {video_count}")
                            logger.info(f"   - Detections Found: {detections}")
                            if summary:
                                logger.info(f"   - Pass Rate: {summary.get('pass_rate_percentage', 0):.1f}%")
                                logger.info(f"   - Avg Delay: {summary.get('average_delay_ms', 0):.1f}ms")
                            break
                            
                        elif msg_type == 'workflow_error':
                            error = data.get('error', 'Unknown error')
                            logger.error(f"❌ WORKFLOW ERROR: {error}")
                            break
                            
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ Invalid JSON message: {message}")
                    except Exception as e:
                        logger.error(f"❌ Message processing error: {e}")
                        
        except Exception as e:
            logger.error(f"❌ WebSocket error: {e}")
    
    async def get_final_results(self, test_session_id: str) -> Dict[str, Any]:
        """Get final test results"""
        try:
            async with self.session.get(
                f"{self.base_url}/api/enhanced-test-workflow/results/{test_session_id}"
            ) as response:
                if response.status == 200:
                    results = await response.json()
                    logger.info("📋 FINAL RESULTS:")
                    
                    if 'summary' in results:
                        summary = results['summary']
                        logger.info(f"   - Total Detections: {summary.get('total_detections', 0)}")
                        logger.info(f"   - True Positives: {summary.get('true_positives', 0)}")
                        logger.info(f"   - False Positives: {summary.get('false_positives', 0)}")
                        logger.info(f"   - Accuracy: {summary.get('accuracy', 0):.3f}")
                    
                    return results
                else:
                    logger.error(f"❌ Failed to get results: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"❌ Error getting results: {e}")
            return {}

async def main():
    """Main test execution"""
    logger.info("🚀 Starting Automation Validation Test")
    logger.info("=" * 60)
    
    async with AutomationTester() as tester:
        # Step 1: Test API connection
        if not await tester.test_api_connection():
            logger.error("❌ API connection failed - aborting test")
            return
        
        # Step 2: Get available projects
        projects = await tester.get_projects()
        if not projects:
            logger.error("❌ No projects found - aborting test")
            return
        
        # Step 3: Select first project with videos
        test_project = None
        for project in projects:
            if project.get('video_count', 0) > 0:
                test_project = project
                break
        
        if not test_project:
            logger.error("❌ No projects with videos found - aborting test")
            return
        
        logger.info(f"🎯 Testing with project: {test_project['name']}")
        
        # Step 4: Start automated test
        result = await tester.start_automated_test(test_project['id'])
        if not result:
            logger.error("❌ Failed to start automated test - aborting")
            return
        
        test_session_id = result.get('test_session_id')
        if not test_session_id:
            logger.error("❌ No test session ID returned - aborting")
            return
        
        # Step 5: Monitor automation progress
        logger.info("👁️ Monitoring automation progress...")
        await tester.monitor_test_progress(test_session_id)
        
        # Step 6: Get final results
        logger.info("📊 Retrieving final results...")
        await asyncio.sleep(2)  # Allow time for results to be stored
        final_results = await tester.get_final_results(test_session_id)
        
        # Step 7: Validation summary
        logger.info("=" * 60)
        if final_results:
            logger.info("✅ AUTOMATION TEST SUCCESSFUL!")
            logger.info("🎉 Complete hands-off automation validated!")
        else:
            logger.warning("⚠️ AUTOMATION TEST COMPLETED WITH ISSUES")
        
        logger.info("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⏹️ Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test execution error: {e}")
        raise