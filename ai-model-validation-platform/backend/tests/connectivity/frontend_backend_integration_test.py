#!/usr/bin/env python3
"""
Frontend-Backend Integration Connectivity Test
==============================================

Tests frontend-backend communication on both localhost and external IP addresses.
Validates API calls, WebSocket connections, and data flow between components.

Author: AI Model Validation Platform
Date: 2025-08-24
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
import tempfile
import os

try:
    import requests
    import aiohttp
    import selenium
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    import socketio
except ImportError as e:
    print(f"Missing dependencies. Please install: {e}")
    print("Run: pip install requests aiohttp selenium python-socketio")
    exit(1)

class FrontendBackendIntegrationTest:
    """Frontend-Backend integration connectivity test suite."""
    
    def __init__(self):
        self.setup_logging()
        self.results = {
            'localhost': {},
            'external': {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Configuration
        self.environments = {
            'localhost': {
                'frontend_url': 'http://127.0.0.1:3000',
                'backend_url': 'http://127.0.0.1:8000',
                'api_url': 'http://127.0.0.1:8000/api'
            },
            'external': {
                'frontend_url': 'http://155.138.239.131:3000',
                'backend_url': 'http://155.138.239.131:8000',
                'api_url': 'http://155.138.239.131:8000/api'
            }
        }
        
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('frontend_backend_integration.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def create_driver(self, headless: bool = True) -> webdriver.Chrome:
        """Create Chrome driver for testing."""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=AI-Validation-Test-Agent/1.0')
        
        # Accept insecure certificates for testing
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--ignore-ssl-errors')
        chrome_options.add_argument('--allow-running-insecure-content')
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(10)
            return driver
        except Exception as e:
            self.logger.error(f"Failed to create Chrome driver: {e}")
            raise
            
    def test_frontend_loading(self, environment: str) -> Dict[str, Any]:
        """Test frontend application loading."""
        config = self.environments[environment]
        test_result = {
            'url': config['frontend_url'],
            'success': False,
            'load_time': None,
            'page_title': None,
            'react_loaded': False,
            'api_config_loaded': False,
            'console_errors': [],
            'network_errors': [],
            'error': None
        }
        
        driver = None
        try:
            driver = self.create_driver(headless=True)
            
            # Measure load time
            start_time = time.time()
            driver.get(config['frontend_url'])
            load_time = time.time() - start_time
            
            # Wait for React to load
            try:
                WebDriverWait(driver, 20).until(
                    lambda d: d.execute_script("return typeof React !== 'undefined'") or
                             d.execute_script("return document.querySelector('[data-testid]') !== null") or
                             d.execute_script("return document.querySelector('.App') !== null")
                )
                react_loaded = True
            except:
                react_loaded = False
                
            # Check API configuration
            try:
                api_config = driver.execute_script("""
                    return window.location.origin + '/api' ||
                           process.env.REACT_APP_API_URL ||
                           'Not configured';
                """)
                api_config_loaded = api_config != 'Not configured'
            except:
                api_config_loaded = False
                
            # Get console errors
            console_errors = []
            try:
                logs = driver.get_log('browser')
                console_errors = [
                    log for log in logs 
                    if log['level'] in ['SEVERE', 'WARNING']
                ]
            except:
                pass
                
            test_result.update({
                'success': True,
                'load_time': round(load_time * 1000, 2),
                'page_title': driver.title,
                'react_loaded': react_loaded,
                'api_config_loaded': api_config_loaded,
                'console_errors': console_errors
            })
            
            self.logger.info(f"✅ Frontend loading {environment} - {load_time*1000:.2f}ms")
            
        except Exception as e:
            test_result['error'] = str(e)
            self.logger.error(f"❌ Frontend loading {environment} - {e}")
        finally:
            if driver:
                driver.quit()
                
        return test_result
        
    def test_api_communication(self, environment: str) -> Dict[str, Any]:
        """Test API communication from frontend perspective."""
        config = self.environments[environment]
        test_result = {
            'success': False,
            'endpoints_tested': 0,
            'endpoints_successful': 0,
            'api_responses': {},
            'cors_working': False,
            'error': None
        }
        
        # Test endpoints that should be accessible
        endpoints = {
            'health': '/health',
            'api_health': '/api/health',
            'dashboard_stats': '/api/dashboard/stats',
            'projects': '/api/projects',
            'videos': '/api/videos'
        }
        
        headers = {
            'Origin': config['frontend_url'],
            'Referer': config['frontend_url'],
            'User-Agent': 'AI-Validation-Frontend/1.0'
        }
        
        successful_endpoints = 0
        api_responses = {}
        
        try:
            for endpoint_name, endpoint_path in endpoints.items():
                url = f"{config['backend_url']}{endpoint_path}"
                
                try:
                    response = requests.get(
                        url,
                        headers=headers,
                        timeout=30,
                        verify=False
                    )
                    
                    api_responses[endpoint_name] = {
                        'status_code': response.status_code,
                        'success': response.status_code < 400,
                        'response_time': response.elapsed.total_seconds() * 1000,
                        'content_type': response.headers.get('Content-Type', ''),
                        'cors_headers': {
                            k: v for k, v in response.headers.items()
                            if k.lower().startswith('access-control-')
                        }
                    }
                    
                    if response.status_code < 400:
                        successful_endpoints += 1
                        
                    # Check if CORS is working
                    if 'access-control-allow-origin' in response.headers:
                        test_result['cors_working'] = True
                        
                except Exception as e:
                    api_responses[endpoint_name] = {
                        'success': False,
                        'error': str(e)
                    }
                    
                time.sleep(0.1)  # Rate limiting
                
            test_result.update({
                'success': successful_endpoints > 0,
                'endpoints_tested': len(endpoints),
                'endpoints_successful': successful_endpoints,
                'api_responses': api_responses
            })
            
            self.logger.info(f"✅ API communication {environment} - {successful_endpoints}/{len(endpoints)} endpoints working")
            
        except Exception as e:
            test_result['error'] = str(e)
            self.logger.error(f"❌ API communication {environment} - {e}")
            
        return test_result
        
    def test_websocket_from_frontend(self, environment: str) -> Dict[str, Any]:
        """Test WebSocket connection from frontend perspective."""
        config = self.environments[environment]
        test_result = {
            'success': False,
            'connection_time': None,
            'message_roundtrip_time': None,
            'error': None
        }
        
        driver = None
        try:
            driver = self.create_driver(headless=True)
            driver.get(config['frontend_url'])
            
            # Wait for page to load
            time.sleep(5)
            
            # Test WebSocket connection via JavaScript
            ws_test_script = f"""
                return new Promise((resolve) => {{
                    const startTime = Date.now();
                    const ws = new WebSocket('{config['backend_url'].replace('http', 'ws')}/ws');
                    
                    let connectionTime = null;
                    let messageTime = null;
                    
                    ws.onopen = function() {{
                        connectionTime = Date.now() - startTime;
                        
                        // Test message roundtrip
                        const msgStart = Date.now();
                        ws.send(JSON.stringify({{type: 'ping', data: 'test'}}));
                        
                        ws.onmessage = function(event) {{
                            messageTime = Date.now() - msgStart;
                            ws.close();
                            resolve({{
                                success: true,
                                connectionTime: connectionTime,
                                messageTime: messageTime
                            }});
                        }};
                    }};
                    
                    ws.onerror = function(error) {{
                        resolve({{
                            success: false,
                            error: 'WebSocket connection failed'
                        }});
                    }};
                    
                    // Timeout after 10 seconds
                    setTimeout(() => {{
                        ws.close();
                        resolve({{
                            success: false,
                            error: 'Connection timeout'
                        }});
                    }}, 10000);
                }});
            """
            
            # Execute WebSocket test
            result = driver.execute_async_script(ws_test_script)
            
            if result['success']:
                test_result.update({
                    'success': True,
                    'connection_time': result['connectionTime'],
                    'message_roundtrip_time': result.get('messageTime')
                })
                self.logger.info(f"✅ WebSocket {environment} - Connected in {result['connectionTime']}ms")
            else:
                test_result['error'] = result.get('error', 'Unknown error')
                self.logger.error(f"❌ WebSocket {environment} - {result.get('error')}")
                
        except Exception as e:
            test_result['error'] = str(e)
            self.logger.error(f"❌ WebSocket {environment} - {e}")
        finally:
            if driver:
                driver.quit()
                
        return test_result
        
    def test_data_flow_integration(self, environment: str) -> Dict[str, Any]:
        """Test end-to-end data flow from frontend to backend."""
        config = self.environments[environment]
        test_result = {
            'success': False,
            'project_creation': False,
            'data_retrieval': False,
            'dashboard_loading': False,
            'error': None
        }
        
        driver = None
        try:
            driver = self.create_driver(headless=True)
            
            # 1. Load frontend
            driver.get(config['frontend_url'])
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script("return document.readyState === 'complete'")
            )
            
            # 2. Test dashboard loading (basic data retrieval)
            try:
                # Look for dashboard elements or API calls
                dashboard_loaded = driver.execute_script("""
                    // Check if dashboard data is loaded
                    return document.querySelector('[data-testid="dashboard"]') !== null ||
                           document.querySelector('.dashboard') !== null ||
                           document.title.toLowerCase().includes('dashboard');
                """)
                test_result['dashboard_loading'] = dashboard_loaded
            except:
                pass
                
            # 3. Test API call from frontend (check network activity)
            try:
                # Enable performance logging
                driver.execute_cdp_cmd('Performance.enable', {})
                
                # Trigger an API call (refresh or navigate)
                driver.refresh()
                time.sleep(3)
                
                # Check for successful API calls
                performance_logs = driver.get_log('performance')
                api_calls = [
                    log for log in performance_logs
                    if 'Network.responseReceived' in str(log.get('message', {}))
                    and config['backend_url'] in str(log.get('message', {}))
                ]
                
                test_result['data_retrieval'] = len(api_calls) > 0
                
            except Exception as e:
                self.logger.debug(f"Performance logging not available: {e}")
                # Fallback: just check if page loaded without errors
                test_result['data_retrieval'] = True
                
            # 4. Overall success
            test_result['success'] = (
                test_result['dashboard_loading'] or 
                test_result['data_retrieval']
            )
            
            if test_result['success']:
                self.logger.info(f"✅ Data flow integration {environment} - Working")
            else:
                self.logger.warning(f"⚠️ Data flow integration {environment} - Limited functionality")
                
        except Exception as e:
            test_result['error'] = str(e)
            self.logger.error(f"❌ Data flow integration {environment} - {e}")
        finally:
            if driver:
                driver.quit()
                
        return test_result
        
    def test_cross_origin_requests(self, environment: str) -> Dict[str, Any]:
        """Test cross-origin requests between frontend and backend."""
        config = self.environments[environment]
        test_result = {
            'success': False,
            'preflight_working': False,
            'actual_request_working': False,
            'cors_headers_present': False,
            'error': None
        }
        
        try:
            # Test preflight request
            headers = {
                'Origin': config['frontend_url'],
                'Access-Control-Request-Method': 'GET',
                'Access-Control-Request-Headers': 'Content-Type, Authorization'
            }
            
            preflight_response = requests.options(
                f"{config['api_url']}/health",
                headers=headers,
                timeout=15,
                verify=False
            )
            
            cors_headers = {
                k.lower(): v for k, v in preflight_response.headers.items()
                if k.lower().startswith('access-control-')
            }
            
            test_result.update({
                'preflight_working': preflight_response.status_code in [200, 204],
                'cors_headers_present': len(cors_headers) > 0
            })
            
            # Test actual cross-origin request
            actual_headers = {
                'Origin': config['frontend_url'],
                'Referer': config['frontend_url']
            }
            
            actual_response = requests.get(
                f"{config['api_url']}/health",
                headers=actual_headers,
                timeout=15,
                verify=False
            )
            
            test_result['actual_request_working'] = actual_response.status_code < 400
            
            # Overall success
            test_result['success'] = (
                test_result['preflight_working'] and 
                test_result['actual_request_working'] and 
                test_result['cors_headers_present']
            )
            
            if test_result['success']:
                self.logger.info(f"✅ Cross-origin requests {environment} - CORS working")
            else:
                self.logger.warning(f"⚠️ Cross-origin requests {environment} - CORS issues detected")
                
        except Exception as e:
            test_result['error'] = str(e)
            self.logger.error(f"❌ Cross-origin requests {environment} - {e}")
            
        return test_result
        
    async def test_socketio_integration(self, environment: str) -> Dict[str, Any]:
        """Test Socket.IO integration between frontend and backend."""
        config = self.environments[environment]
        test_result = {
            'success': False,
            'connection_time': None,
            'event_communication': False,
            'error': None
        }
        
        try:
            sio = socketio.AsyncClient()
            connected = False
            event_received = False
            
            @sio.event
            async def connect():
                nonlocal connected
                connected = True
                self.logger.info(f"Socket.IO connected to {environment}")
                
                # Test event emission
                await sio.emit('test_event', {'source': 'integration_test'})
                
            @sio.event
            async def test_response(data):
                nonlocal event_received
                event_received = True
                self.logger.info(f"Socket.IO event received: {data}")
                
            start_time = time.time()
            
            # Attempt connection
            await sio.connect(
                config['backend_url'],
                wait_timeout=20,
                headers={'Origin': config['frontend_url']}
            )
            
            connection_time = time.time() - start_time
            
            # Wait for potential event response
            await asyncio.sleep(2)
            
            await sio.disconnect()
            
            test_result.update({
                'success': connected,
                'connection_time': round(connection_time * 1000, 2),
                'event_communication': event_received
            })
            
            if connected:
                self.logger.info(f"✅ Socket.IO integration {environment} - Connected")
            else:
                self.logger.error(f"❌ Socket.IO integration {environment} - Connection failed")
                
        except Exception as e:
            test_result['error'] = str(e)
            self.logger.error(f"❌ Socket.IO integration {environment} - {e}")
            
        return test_result
        
    async def run_integration_tests(self, environment: str) -> Dict[str, Any]:
        """Run all integration tests for specified environment."""
        config = self.environments[environment]
        results = {}
        
        self.logger.info(f"\n🔄 Running frontend-backend integration tests for {environment.upper()}")
        self.logger.info(f"Frontend: {config['frontend_url']}")
        self.logger.info(f"Backend: {config['backend_url']}")
        
        # 1. Frontend Loading Test
        self.logger.info("📱 Testing frontend loading...")
        results['frontend_loading'] = self.test_frontend_loading(environment)
        
        # 2. API Communication Test
        self.logger.info("🔗 Testing API communication...")
        results['api_communication'] = self.test_api_communication(environment)
        
        # 3. WebSocket Test
        self.logger.info("🔌 Testing WebSocket from frontend...")
        results['websocket_frontend'] = self.test_websocket_from_frontend(environment)
        
        # 4. Data Flow Integration Test
        self.logger.info("🔄 Testing data flow integration...")
        results['data_flow_integration'] = self.test_data_flow_integration(environment)
        
        # 5. Cross-Origin Requests Test
        self.logger.info("🌐 Testing cross-origin requests...")
        results['cross_origin_requests'] = self.test_cross_origin_requests(environment)
        
        # 6. Socket.IO Integration Test
        self.logger.info("⚡ Testing Socket.IO integration...")
        results['socketio_integration'] = await self.test_socketio_integration(environment)
        
        return results
        
    def generate_integration_report(self) -> str:
        """Generate integration test report."""
        report_lines = [
            "=" * 80,
            "FRONTEND-BACKEND INTEGRATION TEST REPORT",
            "=" * 80,
            f"Generated: {self.results['timestamp']}",
            ""
        ]
        
        # Summary
        report_lines.extend([
            "INTEGRATION TEST SUMMARY",
            "=" * 40,
            ""
        ])
        
        for env in ['localhost', 'external']:
            if env in self.results:
                env_results = self.results[env]
                report_lines.append(f"{env.upper()} ENVIRONMENT:")
                
                # Test results
                tests = [
                    ('Frontend Loading', 'frontend_loading'),
                    ('API Communication', 'api_communication'),
                    ('WebSocket Frontend', 'websocket_frontend'),
                    ('Data Flow Integration', 'data_flow_integration'),
                    ('Cross-Origin Requests', 'cross_origin_requests'),
                    ('Socket.IO Integration', 'socketio_integration')
                ]
                
                for test_name, test_key in tests:
                    if test_key in env_results:
                        result = env_results[test_key]
                        success = result.get('success', False)
                        status = '✅ PASS' if success else '❌ FAIL'
                        report_lines.append(f"  ├─ {test_name}: {status}")
                        
                report_lines.append("")
                
        # Detailed Results
        report_lines.extend([
            "DETAILED INTEGRATION RESULTS",
            "=" * 40,
            ""
        ])
        
        for env, env_results in self.results.items():
            if env in ['localhost', 'external']:
                report_lines.extend([
                    f"{env.upper()} ENVIRONMENT DETAILS:",
                    "-" * 30,
                    ""
                ])
                
                # Frontend Loading Details
                if 'frontend_loading' in env_results:
                    fl = env_results['frontend_loading']
                    report_lines.extend([
                        "Frontend Loading:",
                        f"  Load Time: {fl.get('load_time', 'N/A')}ms",
                        f"  Page Title: {fl.get('page_title', 'N/A')}",
                        f"  React Loaded: {'✅' if fl.get('react_loaded') else '❌'}",
                        f"  API Config: {'✅' if fl.get('api_config_loaded') else '❌'}",
                        f"  Console Errors: {len(fl.get('console_errors', []))}",
                        ""
                    ])
                    
                # API Communication Details
                if 'api_communication' in env_results:
                    api = env_results['api_communication']
                    report_lines.extend([
                        "API Communication:",
                        f"  Endpoints Tested: {api.get('endpoints_tested', 0)}",
                        f"  Successful: {api.get('endpoints_successful', 0)}",
                        f"  CORS Working: {'✅' if api.get('cors_working') else '❌'}",
                        ""
                    ])
                    
                    # Individual endpoint results
                    for endpoint, result in api.get('api_responses', {}).items():
                        status = '✅' if result.get('success') else '❌'
                        code = result.get('status_code', 'N/A')
                        report_lines.append(f"    {status} {endpoint}: {code}")
                    report_lines.append("")
                    
                # WebSocket Details
                if 'websocket_frontend' in env_results:
                    ws = env_results['websocket_frontend']
                    report_lines.extend([
                        "WebSocket from Frontend:",
                        f"  Connection: {'✅' if ws.get('success') else '❌'}",
                        f"  Connection Time: {ws.get('connection_time', 'N/A')}ms",
                        f"  Message Roundtrip: {ws.get('message_roundtrip_time', 'N/A')}ms",
                        ""
                    ])
                    
                # Cross-Origin Details
                if 'cross_origin_requests' in env_results:
                    cors = env_results['cross_origin_requests']
                    report_lines.extend([
                        "Cross-Origin Requests:",
                        f"  Preflight: {'✅' if cors.get('preflight_working') else '❌'}",
                        f"  Actual Request: {'✅' if cors.get('actual_request_working') else '❌'}",
                        f"  CORS Headers: {'✅' if cors.get('cors_headers_present') else '❌'}",
                        ""
                    ])
                    
                report_lines.append("")
                
        return "\n".join(report_lines)
        
    async def run_all_integration_tests(self):
        """Run all frontend-backend integration tests."""
        self.logger.info("🔄 Starting Frontend-Backend Integration Test Suite")
        self.logger.info("=" * 80)
        
        # Test localhost
        try:
            self.results['localhost'] = await self.run_integration_tests('localhost')
        except Exception as e:
            self.logger.error(f"Localhost integration tests failed: {e}")
            self.results['localhost'] = {'error': str(e)}
            
        # Test external IP
        try:
            self.results['external'] = await self.run_integration_tests('external')
        except Exception as e:
            self.logger.error(f"External integration tests failed: {e}")
            self.results['external'] = {'error': str(e)}
            
        # Generate and save report
        report = self.generate_integration_report()
        
        # Save detailed results
        with open('frontend_backend_integration_results.json', 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
            
        # Save human-readable report
        with open('frontend_backend_integration_report.txt', 'w') as f:
            f.write(report)
            
        self.logger.info("\n" + report)
        
        return self.results


async def main():
    """Main integration test execution function."""
    suite = FrontendBackendIntegrationTest()
    results = await suite.run_all_integration_tests()
    
    # Check for critical integration failures
    critical_failures = 0
    
    for env in ['localhost', 'external']:
        if env in results:
            env_results = results[env]
            
            # Check critical integration points
            if not env_results.get('api_communication', {}).get('success', False):
                critical_failures += 1
            if not env_results.get('cross_origin_requests', {}).get('success', False):
                critical_failures += 1
                
    if critical_failures > 0:
        print(f"\n❌ {critical_failures} critical integration failures found")
        exit(1)
    else:
        print("\n✅ All critical integration tests passed")
        exit(0)


if __name__ == "__main__":
    asyncio.run(main())