#!/usr/bin/env python3
"""
Security Test Suite Runner
==========================

Comprehensive security test runner that executes all security test suites
and generates detailed vulnerability reports.

This script orchestrates the execution of:
1. Multi-tenancy security tests
2. Authentication bypass tests  
3. Injection vulnerability tests
4. Data access control tests

EXPECTED BEHAVIOR:
- Initial runs should FAIL, demonstrating vulnerabilities
- After applying fixes, all tests should PASS
- Detailed reports are generated for remediation guidance
"""

import os
import sys
import json
import subprocess
import datetime
from pathlib import Path
from typing import Dict, List, Any
import argparse

# Add the current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_multi_tenant_security import SecurityTestHarness as MultiTenantHarness
from test_authentication_bypass import run_comprehensive_auth_test
from test_injection_vulnerabilities import run_comprehensive_injection_test  
from test_data_access_control import run_comprehensive_access_control_test


class SecurityTestSuiteRunner:
    """Orchestrates execution of all security test suites"""
    
    def __init__(self, output_dir: str = "/home/rigade/Testing/tests/security/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.test_suites = {
            "multi_tenancy": {
                "name": "Multi-Tenancy Security",
                "description": "Tests user isolation and data segregation",
                "runner": self.run_multi_tenancy_tests,
                "critical": True
            },
            "authentication": {
                "name": "Authentication & Authorization",
                "description": "Tests authentication bypass and privilege escalation",
                "runner": run_comprehensive_auth_test,
                "critical": True
            },
            "injection": {
                "name": "Injection Vulnerabilities", 
                "description": "Tests SQL, command, and script injection attacks",
                "runner": run_comprehensive_injection_test,
                "critical": True
            },
            "access_control": {
                "name": "Data Access Control",
                "description": "Tests resource ownership and authorization",
                "runner": run_comprehensive_access_control_test,
                "critical": True
            }
        }
        
        self.results = {}
        self.overall_status = "UNKNOWN"
        
    def run_multi_tenancy_tests(self) -> bool:
        """Run multi-tenancy security tests using pytest"""
        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest", 
                "test_multi_tenant_security.py",
                "-v", "--tb=short", "--capture=no"
            ], capture_output=True, text=True, cwd=os.path.dirname(__file__))
            
            return result.returncode == 0
        except Exception as e:
            print(f"Error running multi-tenancy tests: {e}")
            return False
    
    def run_all_tests(self, verbose: bool = True) -> Dict[str, Any]:
        """Run all security test suites"""
        if verbose:
            self.print_banner()
        
        overall_success = True
        
        for suite_id, suite_info in self.test_suites.items():
            if verbose:
                print(f"\n{'='*70}")
                print(f"🔒 RUNNING: {suite_info['name']}")
                print(f"📝 {suite_info['description']}")
                print(f"{'='*70}")
            
            try:
                success = suite_info["runner"]()
                
                self.results[suite_id] = {
                    "name": suite_info["name"],
                    "description": suite_info["description"],
                    "success": success,
                    "critical": suite_info["critical"],
                    "timestamp": datetime.datetime.now().isoformat()
                }
                
                if suite_info["critical"] and not success:
                    overall_success = False
                    
                if verbose:
                    status_icon = "✅" if success else "🚨"
                    print(f"\n{status_icon} {suite_info['name']}: {'PASSED' if success else 'FAILED'}")
                
            except Exception as e:
                self.results[suite_id] = {
                    "name": suite_info["name"],
                    "description": suite_info["description"], 
                    "success": False,
                    "critical": suite_info["critical"],
                    "error": str(e),
                    "timestamp": datetime.datetime.now().isoformat()
                }
                overall_success = False
                
                if verbose:
                    print(f"\n⚠️ {suite_info['name']}: ERROR - {e}")
        
        self.overall_status = "PASS" if overall_success else "FAIL"
        
        if verbose:
            self.print_summary()
            
        return {
            "overall_status": self.overall_status,
            "results": self.results,
            "timestamp": datetime.datetime.now().isoformat()
        }
    
    def print_banner(self):
        """Print test suite banner"""
        print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                     🔐 SECURITY TEST SUITE RUNNER 🔐                      ║
║                                                                           ║
║  Comprehensive security testing for AI Model Validation Platform         ║
║                                                                           ║
║  ⚠️  WARNING: These tests are designed to find vulnerabilities!          ║
║      Initial runs should FAIL, demonstrating security issues.            ║
║      After applying fixes, all tests should PASS.                        ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
        """)
    
    def print_summary(self):
        """Print test execution summary"""
        print("\n" + "="*80)
        print("📊 SECURITY TEST SUITE SUMMARY")
        print("="*80)
        
        total_suites = len(self.test_suites)
        passed_suites = len([r for r in self.results.values() if r["success"]])
        failed_suites = len([r for r in self.results.values() if not r["success"]])
        critical_failures = len([r for r in self.results.values() 
                                if not r["success"] and r.get("critical", False)])
        
        print(f"Total Test Suites: {total_suites}")
        print(f"Passed: {passed_suites} ✅")
        print(f"Failed: {failed_suites} 🚨")
        print(f"Critical Failures: {critical_failures} ⚠️")
        
        print(f"\nOverall Status: {self.overall_status}")
        
        if failed_suites > 0:
            print(f"\n🚨 CRITICAL SECURITY ISSUES DETECTED!")
            print("The following test suites failed:")
            
            for suite_id, result in self.results.items():
                if not result["success"]:
                    criticality = " (CRITICAL)" if result.get("critical") else ""
                    print(f"  ❌ {result['name']}{criticality}")
                    if result.get("error"):
                        print(f"     Error: {result['error']}")
            
            print("\n📋 NEXT STEPS:")
            print("1. Review individual test outputs above for specific vulnerabilities")
            print("2. Apply security fixes based on test failures") 
            print("3. Re-run this test suite to verify fixes")
            print("4. Implement additional security monitoring")
            
        else:
            print("\n✅ ALL SECURITY TESTS PASSED!")
            print("The application appears to be properly secured against tested vulnerabilities.")
    
    def generate_detailed_report(self) -> str:
        """Generate detailed security test report"""
        report_data = {
            "title": "AI Model Validation Platform - Security Test Report",
            "generated_at": datetime.datetime.now().isoformat(),
            "overall_status": self.overall_status,
            "executive_summary": self._generate_executive_summary(),
            "test_results": self.results,
            "recommendations": self._generate_recommendations(),
            "remediation_guide": self._generate_remediation_guide()
        }
        
        # Save JSON report
        json_report_path = self.output_dir / f"security_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        # Generate markdown report
        md_report_path = self.output_dir / f"security_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(md_report_path, 'w') as f:
            f.write(self._generate_markdown_report(report_data))
        
        print(f"\n📄 Detailed reports generated:")
        print(f"   JSON: {json_report_path}")
        print(f"   Markdown: {md_report_path}")
        
        return str(md_report_path)
    
    def _generate_executive_summary(self) -> str:
        """Generate executive summary of security test results"""
        failed_critical = [r for r in self.results.values() 
                          if not r["success"] and r.get("critical", False)]
        
        if not failed_critical:
            return """
            ✅ SECURE: All critical security tests passed. The AI Model Validation Platform
            demonstrates proper implementation of multi-tenancy, authentication, authorization,
            and injection prevention controls.
            """
        else:
            return f"""
            🚨 CRITICAL SECURITY VULNERABILITIES DETECTED: {len(failed_critical)} critical security 
            test suites failed, indicating serious security vulnerabilities that must be addressed
            immediately before production deployment.
            
            Failed Critical Tests:
            {chr(10).join('- ' + r['name'] for r in failed_critical)}
            
            Immediate action required to secure the application.
            """
    
    def _generate_recommendations(self) -> List[str]:
        """Generate security recommendations based on test results"""
        recommendations = []
        
        for suite_id, result in self.results.items():
            if not result["success"]:
                if suite_id == "multi_tenancy":
                    recommendations.append("Implement proper user context filtering in all database queries")
                    recommendations.append("Add authorization middleware to validate resource ownership")
                elif suite_id == "authentication":
                    recommendations.append("Implement robust authentication middleware on all protected endpoints")
                    recommendations.append("Add proper JWT token validation and expiry checking")
                elif suite_id == "injection":
                    recommendations.append("Implement parameterized queries to prevent SQL injection")
                    recommendations.append("Add input sanitization and validation for all user inputs")
                elif suite_id == "access_control":
                    recommendations.append("Implement resource ownership validation in all CRUD operations")
                    recommendations.append("Add privilege escalation prevention controls")
        
        if not recommendations:
            recommendations = [
                "✅ No critical security issues detected",
                "Continue regular security testing and monitoring", 
                "Consider implementing additional security headers",
                "Maintain security-focused code reviews"
            ]
        
        return recommendations
    
    def _generate_remediation_guide(self) -> Dict[str, List[str]]:
        """Generate detailed remediation guide"""
        guide = {}
        
        for suite_id, result in self.results.items():
            if not result["success"]:
                if suite_id == "multi_tenancy":
                    guide["Multi-Tenancy Fixes"] = [
                        "Add user_id filtering to all database queries",
                        "Implement middleware to inject user context",
                        "Add resource ownership validation decorators",
                        "Review all API endpoints for proper authorization"
                    ]
                elif suite_id == "authentication":
                    guide["Authentication Fixes"] = [
                        "Implement JWT token validation middleware",
                        "Add authentication requirement to all protected routes",
                        "Implement proper session management",
                        "Add brute force protection to login endpoints"
                    ]
                elif suite_id == "injection":
                    guide["Injection Prevention"] = [
                        "Replace string concatenation with parameterized queries",
                        "Add input validation and sanitization layers", 
                        "Implement content security policies",
                        "Add command injection prevention in file operations"
                    ]
                elif suite_id == "access_control":
                    guide["Access Control Improvements"] = [
                        "Add resource ownership checks to all CRUD operations",
                        "Implement role-based access control (RBAC)",
                        "Add privilege escalation detection",
                        "Review bulk operation authorization logic"
                    ]
        
        return guide
    
    def _generate_markdown_report(self, report_data: Dict[str, Any]) -> str:
        """Generate markdown format security report"""
        md_content = f"""# {report_data['title']}

**Generated:** {report_data['generated_at']}  
**Overall Status:** {'🚨 CRITICAL VULNERABILITIES' if report_data['overall_status'] == 'FAIL' else '✅ SECURE'}

## Executive Summary

{report_data['executive_summary']}

## Test Results Summary

| Test Suite | Status | Critical | Description |
|------------|--------|----------|-------------|
"""
        
        for suite_id, result in report_data['test_results'].items():
            status_icon = "✅ PASS" if result['success'] else "🚨 FAIL"
            critical_icon = "⚠️ Yes" if result.get('critical') else "No"
            md_content += f"| {result['name']} | {status_icon} | {critical_icon} | {result['description']} |\n"
        
        md_content += f"""

## Detailed Test Results

"""
        
        for suite_id, result in report_data['test_results'].items():
            status = "PASSED" if result['success'] else "FAILED"
            md_content += f"""### {result['name']} - {status}

**Description:** {result['description']}  
**Critical:** {result.get('critical', False)}  
**Timestamp:** {result['timestamp']}

"""
            if result.get('error'):
                md_content += f"**Error:** {result['error']}\n\n"
        
        md_content += """## Security Recommendations

"""
        for i, rec in enumerate(report_data['recommendations'], 1):
            md_content += f"{i}. {rec}\n"
        
        md_content += """

## Remediation Guide

"""
        
        for category, steps in report_data['remediation_guide'].items():
            md_content += f"""### {category}

"""
            for i, step in enumerate(steps, 1):
                md_content += f"{i}. {step}\n"
            md_content += "\n"
        
        md_content += """## Next Steps

1. **Immediate Action Required** (if tests failed):
   - Review failed test details above
   - Apply security fixes based on remediation guide
   - Re-run security tests to verify fixes

2. **Ongoing Security Practices**:
   - Run security tests regularly (weekly/monthly)
   - Implement security code review practices  
   - Monitor for new vulnerability patterns
   - Keep dependencies updated

3. **Production Deployment**:
   - ⚠️ **DO NOT DEPLOY** to production until all critical tests pass
   - Implement additional security monitoring
   - Consider third-party security auditing

---
*Report generated by AI Model Validation Platform Security Test Suite*
"""
        
        return md_content


def main():
    """Main entry point for security test runner"""
    parser = argparse.ArgumentParser(description='AI Model Validation Platform Security Test Suite')
    parser.add_argument('--output-dir', '-o', 
                       default='/home/rigade/Testing/tests/security/reports',
                       help='Directory to save test reports')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Run tests quietly (minimal output)')
    parser.add_argument('--report-only', '-r', action='store_true',
                       help='Generate report from previous run (skip test execution)')
    
    args = parser.parse_args()
    
    runner = SecurityTestSuiteRunner(args.output_dir)
    
    if not args.report_only:
        # Run all security tests
        results = runner.run_all_tests(verbose=not args.quiet)
        
        # Generate detailed report
        report_path = runner.generate_detailed_report()
        
        # Exit with appropriate code
        exit_code = 0 if results["overall_status"] == "PASS" else 1
        
        if not args.quiet:
            if exit_code == 0:
                print(f"\n🎉 All security tests passed! Application is secure.")
            else:
                print(f"\n⚠️  Security vulnerabilities detected. Review report: {report_path}")
        
        sys.exit(exit_code)
    else:
        print("Report-only mode not implemented yet.")
        sys.exit(1)


if __name__ == "__main__":
    main()