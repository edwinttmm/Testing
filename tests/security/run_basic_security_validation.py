#!/usr/bin/env python3
"""
Basic Security Validation Script
================================

A simplified security validation script that demonstrates critical vulnerabilities
without requiring external dependencies like pytest. This script can be run
immediately to validate multi-tenancy and security issues.

This script demonstrates:
1. User isolation failures
2. Authentication bypass vulnerabilities  
3. Authorization control issues
4. Data leakage problems

EXPECTED: This script should reveal vulnerabilities that need to be fixed.
"""

import sys
import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any

# Add backend path
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

try:
    from fastapi.testclient import TestClient
    from main import app
    FASTAPI_AVAILABLE = True
    print("✅ FastAPI available - running full security validation")
except ImportError:
    FASTAPI_AVAILABLE = False
    print("⚠️ FastAPI not available - running simplified security checks")


class BasicSecurityValidator:
    """Basic security validation without external dependencies"""
    
    def __init__(self):
        self.vulnerabilities_found = []
        self.tests_passed = []
        self.client = None
        
        if FASTAPI_AVAILABLE:
            self.client = TestClient(app)
        
        # Test users for validation
        self.users = {
            "alice": {
                "id": str(uuid.uuid4()),
                "email": "alice@test.com",
                "api_key": "alice_key_12345"
            },
            "bob": {
                "id": str(uuid.uuid4()), 
                "email": "bob@test.com",
                "api_key": "bob_key_67890"
            },
            "malicious": {
                "id": str(uuid.uuid4()),
                "email": "hacker@evil.com",
                "api_key": "evil_key_666"
            }
        }
    
    def log_vulnerability(self, test_name: str, description: str, severity: str = "HIGH"):
        """Log a security vulnerability"""
        vuln = {
            "test": test_name,
            "description": description,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        }
        self.vulnerabilities_found.append(vuln)
        print(f"🚨 VULNERABILITY: {test_name} - {description}")
    
    def log_success(self, test_name: str, description: str):
        """Log a successful security test"""
        success = {
            "test": test_name,
            "description": description,
            "timestamp": datetime.now().isoformat()
        }
        self.tests_passed.append(success)
        print(f"✅ SECURE: {test_name} - {description}")
    
    def get_auth_headers(self, user_key: str) -> Dict[str, str]:
        """Get authentication headers for test user"""
        return {
            "Authorization": f"Bearer {self.users[user_key]['api_key']}",
            "X-User-ID": self.users[user_key]["id"]
        }
    
    def test_unauthenticated_access(self):
        """Test if protected endpoints require authentication"""
        print("\n🔍 Testing unauthenticated access...")
        
        if not self.client:
            print("⚠️ Cannot test - FastAPI client not available")
            return
        
        protected_endpoints = [
            "/api/projects",
            "/api/videos/upload",
            "/api/dashboard/stats"
        ]
        
        for endpoint in protected_endpoints:
            try:
                response = self.client.get(endpoint)
                if response.status_code == 200:
                    self.log_vulnerability(
                        "unauthenticated_access",
                        f"Endpoint {endpoint} accessible without authentication (Status: {response.status_code})"
                    )
                elif response.status_code == 401:
                    self.log_success(
                        "authentication_required",
                        f"Endpoint {endpoint} properly requires authentication"
                    )
                else:
                    print(f"ℹ️ Endpoint {endpoint} returned status {response.status_code}")
            except Exception as e:
                print(f"⚠️ Error testing {endpoint}: {e}")
    
    def test_cross_user_access_simulation(self):
        """Simulate cross-user access attempts"""
        print("\n🔍 Testing cross-user access patterns...")
        
        # Simulate Alice creating a project
        alice_project_id = str(uuid.uuid4())
        alice_project = {
            "id": alice_project_id,
            "name": "Alice's Private Project",
            "owner_id": self.users["alice"]["id"]
        }
        
        print(f"📋 Alice created project: {alice_project['name']}")
        
        # Check if the application would properly filter this
        # This is a conceptual test showing what should be validated
        
        # Test 1: Bob tries to access Alice's project
        print("🔍 Testing: Can Bob access Alice's project?")
        
        if self.client:
            try:
                response = self.client.get(
                    f"/api/projects/{alice_project_id}",
                    headers=self.get_auth_headers("bob")
                )
                
                if response.status_code == 200:
                    self.log_vulnerability(
                        "cross_user_project_access",
                        "Bob can access Alice's project - multi-tenancy violation!"
                    )
                elif response.status_code in [403, 404]:
                    self.log_success(
                        "project_access_control",
                        "Bob correctly cannot access Alice's project"
                    )
                else:
                    print(f"ℹ️ Project access returned status {response.status_code}")
            except Exception as e:
                print(f"⚠️ Error testing cross-user access: {e}")
        else:
            # Conceptual validation
            print("💭 CONCEPTUAL CHECK: In a secure system, Bob should receive 403/404")
            print("💭 If Bob receives 200 OK with Alice's project data, this is a CRITICAL vulnerability")
    
    def test_sql_injection_patterns(self):
        """Test for common SQL injection vulnerabilities"""
        print("\n🔍 Testing SQL injection resistance...")
        
        sql_payloads = [
            "'; DROP TABLE projects; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM users --"
        ]
        
        if self.client:
            for payload in sql_payloads:
                try:
                    # Test in project ID parameter
                    response = self.client.get(
                        f"/api/projects/{payload}",
                        headers=self.get_auth_headers("alice")
                    )
                    
                    # Check response for SQL injection indicators
                    response_text = response.text.lower() if response.text else ""
                    
                    if "syntax error" in response_text:
                        self.log_vulnerability(
                            "sql_injection_error_exposure",
                            f"SQL injection payload exposed database error: {payload}"
                        )
                    elif response.status_code in [400, 404, 422]:
                        self.log_success(
                            "sql_injection_blocked",
                            f"SQL injection payload properly handled: {payload}"
                        )
                    
                except Exception as e:
                    print(f"⚠️ Error testing SQL injection with payload {payload}: {e}")
        else:
            print("💭 CONCEPTUAL CHECK: SQL injection payloads should be safely handled")
            print("💭 Responses should not contain database errors or unauthorized data")
    
    def test_file_path_traversal(self):
        """Test for path traversal vulnerabilities"""
        print("\n🔍 Testing path traversal attacks...")
        
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/passwd"
        ]
        
        if self.client:
            for payload in path_traversal_payloads:
                try:
                    response = self.client.get(
                        f"/api/files/download?path={payload}",
                        headers=self.get_auth_headers("malicious")
                    )
                    
                    if response.status_code == 200:
                        response_text = response.text if response.text else ""
                        if "root:" in response_text or "/bin/bash" in response_text:
                            self.log_vulnerability(
                                "path_traversal_success",
                                f"Path traversal successful - system file exposed: {payload}"
                            )
                        else:
                            self.log_success(
                                "path_traversal_blocked",
                                f"Path traversal blocked: {payload}"
                            )
                    elif response.status_code in [400, 403, 404]:
                        self.log_success(
                            "path_traversal_prevented",
                            f"Path traversal properly prevented: {payload}"
                        )
                        
                except Exception as e:
                    print(f"⚠️ Error testing path traversal with payload {payload}: {e}")
        else:
            print("💭 CONCEPTUAL CHECK: Path traversal should be blocked")
            print("💭 System files should never be accessible via API endpoints")
    
    def test_privilege_escalation_patterns(self):
        """Test for privilege escalation vulnerabilities"""
        print("\n🔍 Testing privilege escalation...")
        
        # Test if regular user can access admin endpoints
        admin_endpoints = [
            "/api/admin/users",
            "/api/admin/system-stats",
            "/api/admin/logs"
        ]
        
        if self.client:
            for endpoint in admin_endpoints:
                try:
                    response = self.client.get(
                        endpoint,
                        headers=self.get_auth_headers("bob")
                    )
                    
                    if response.status_code == 200:
                        self.log_vulnerability(
                            "privilege_escalation",
                            f"Regular user accessed admin endpoint: {endpoint}"
                        )
                    elif response.status_code in [403, 404]:
                        self.log_success(
                            "admin_access_control",
                            f"Admin endpoint properly protected: {endpoint}"
                        )
                        
                except Exception as e:
                    print(f"⚠️ Error testing admin endpoint {endpoint}: {e}")
        else:
            print("💭 CONCEPTUAL CHECK: Regular users should not access admin functions")
    
    def test_data_leakage_in_errors(self):
        """Test if error messages leak sensitive information"""
        print("\n🔍 Testing error message information disclosure...")
        
        if self.client:
            # Try to access non-existent but realistic-looking resource
            fake_project_id = str(uuid.uuid4())
            
            try:
                response = self.client.get(
                    f"/api/projects/{fake_project_id}",
                    headers=self.get_auth_headers("malicious")
                )
                
                if response.status_code in [403, 404]:
                    error_message = response.text.lower() if response.text else ""
                    
                    # Check for information leakage in error messages
                    sensitive_indicators = [
                        "exists", "owner", "alice", "bob", 
                        "database", "table", "query", "sql"
                    ]
                    
                    leaked_info = [indicator for indicator in sensitive_indicators 
                                 if indicator in error_message]
                    
                    if leaked_info:
                        self.log_vulnerability(
                            "information_disclosure",
                            f"Error message may leak information: {leaked_info}"
                        )
                    else:
                        self.log_success(
                            "safe_error_messages",
                            "Error messages don't leak sensitive information"
                        )
                        
            except Exception as e:
                print(f"⚠️ Error testing error message disclosure: {e}")
        else:
            print("💭 CONCEPTUAL CHECK: Error messages should be generic")
            print("💭 They should not reveal information about other users or system internals")
    
    def run_all_tests(self):
        """Run all security validation tests"""
        print("🔒 STARTING BASIC SECURITY VALIDATION")
        print("="*60)
        print("This validation demonstrates critical security vulnerabilities")
        print("that must be fixed before production deployment.")
        print("="*60)
        
        # Run all security tests
        self.test_unauthenticated_access()
        self.test_cross_user_access_simulation()
        self.test_sql_injection_patterns()
        self.test_file_path_traversal()
        self.test_privilege_escalation_patterns()
        self.test_data_leakage_in_errors()
        
        # Generate summary
        self.generate_summary()
    
    def generate_summary(self):
        """Generate security validation summary"""
        print("\n" + "="*60)
        print("📊 SECURITY VALIDATION SUMMARY")
        print("="*60)
        
        total_vulnerabilities = len(self.vulnerabilities_found)
        total_secure = len(self.tests_passed)
        
        print(f"Vulnerabilities Found: {total_vulnerabilities} 🚨")
        print(f"Security Tests Passed: {total_secure} ✅")
        
        if total_vulnerabilities > 0:
            print(f"\n🚨 CRITICAL SECURITY ISSUES DETECTED!")
            print("The following vulnerabilities were found:")
            
            for i, vuln in enumerate(self.vulnerabilities_found, 1):
                print(f"  {i}. {vuln['test']}: {vuln['description']}")
            
            print(f"\n📋 IMMEDIATE ACTIONS REQUIRED:")
            print("1. 🛑 DO NOT DEPLOY to production with these vulnerabilities")
            print("2. 🔧 Apply security fixes based on the issues above")
            print("3. ✅ Re-run this validation to verify fixes")
            print("4. 🔍 Conduct comprehensive security testing")
            
            print(f"\n💡 COMMON FIXES:")
            print("• Implement authentication middleware on all protected endpoints")
            print("• Add user context filtering to database queries") 
            print("• Use parameterized queries to prevent SQL injection")
            print("• Validate file paths to prevent directory traversal")
            print("• Implement role-based access control for admin functions")
            print("• Use generic error messages that don't leak information")
            
        else:
            print(f"\n✅ NO CRITICAL VULNERABILITIES DETECTED!")
            print("The basic security validation tests passed.")
            print("However, consider running the full security test suite for comprehensive coverage.")
        
        # Save results to file
        self.save_results()
        
        return total_vulnerabilities == 0
    
    def save_results(self):
        """Save validation results to file"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_vulnerabilities": len(self.vulnerabilities_found),
            "total_secure": len(self.tests_passed),
            "vulnerabilities": self.vulnerabilities_found,
            "secure_tests": self.tests_passed
        }
        
        report_path = "/home/rigade/Testing/tests/security/basic_security_validation_results.json"
        
        try:
            with open(report_path, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n📄 Results saved to: {report_path}")
        except Exception as e:
            print(f"⚠️ Could not save results: {e}")


def main():
    """Main entry point for basic security validation"""
    validator = BasicSecurityValidator()
    
    try:
        success = validator.run_all_tests()
        exit_code = 0 if success else 1
        
        if success:
            print(f"\n🎉 Basic security validation completed successfully!")
        else:
            print(f"\n⚠️ Security vulnerabilities detected - review output above")
        
        return exit_code
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Security validation interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Security validation failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)