#!/usr/bin/env python3
"""
LabJack Detection Workflow Validation Suite Runner

This script executes the complete suite of LabJack detection workflow validation tests,
providing comprehensive verification of the system's production readiness.

Usage:
    python tests/run_labjack_validation_suite.py
    
    or with specific test categories:
    python tests/run_labjack_validation_suite.py --tests workflow,websocket,timing
"""

import asyncio
import argparse
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, List
import json

# Import test modules
from test_labjack_detection_workflow_validation import LabJackDetectionWorkflowValidator
from test_labjack_websocket_integration import LabJackWebSocketTester, test_labjack_websocket_integration
from test_labjack_timing_synchronization import TimingSynchronizationValidator, test_labjack_timing_synchronization


class LabJackValidationSuiteRunner:
    """
    Comprehensive LabJack validation suite runner
    """
    
    def __init__(self):
        self.start_time = None
        self.results = {}
        self.summary = {}
        
    async def run_complete_validation_suite(self, test_categories: List[str] = None) -> Dict[str, Any]:
        """Run the complete LabJack validation suite"""
        
        print("🚀" + "="*78)
        print("🔍 LABJACK DETECTION WORKFLOW - COMPREHENSIVE VALIDATION SUITE")
        print("🚀" + "="*78)
        print(f"📅 Started at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        self.start_time = time.time()
        
        # Default to all tests if none specified
        if test_categories is None:
            test_categories = ["workflow", "websocket", "timing"]
        
        # Execute test categories
        if "workflow" in test_categories:
            await self._run_workflow_validation()
        
        if "websocket" in test_categories:
            await self._run_websocket_validation()
        
        if "timing" in test_categories:
            await self._run_timing_validation()
        
        # Generate comprehensive report
        return self._generate_final_report()
    
    async def _run_workflow_validation(self):
        """Run comprehensive workflow validation"""
        print(f"\n{'='*60}")
        print("🔧 EXECUTING: Complete Workflow Validation")
        print(f"{'='*60}")
        
        try:
            validator = LabJackDetectionWorkflowValidator()
            result = await validator.validate_complete_workflow()
            self.results["workflow_validation"] = result
            validator.cleanup()
            
            # Print summary for this test
            summary = result.get("validation_summary", {})
            print(f"✅ Workflow Validation Complete:")
            print(f"   Tests: {summary.get('passed_tests', 0)}/{summary.get('total_tests', 0)}")
            print(f"   Success Rate: {summary.get('success_rate', 0)}%")
            print(f"   Status: {summary.get('overall_status', 'UNKNOWN')}")
            
        except Exception as e:
            print(f"❌ Workflow validation failed: {e}")
            self.results["workflow_validation"] = {
                "error": str(e),
                "validation_summary": {
                    "total_tests": 0,
                    "passed_tests": 0,
                    "success_rate": 0,
                    "overall_status": "ERROR"
                }
            }
    
    async def _run_websocket_validation(self):
        """Run WebSocket integration validation"""
        print(f"\n{'='*60}")
        print("🌐 EXECUTING: WebSocket Integration Validation")
        print(f"{'='*60}")
        
        try:
            result = await test_labjack_websocket_integration()
            self.results["websocket_validation"] = {
                "test_results": result,
                "validation_summary": self._calculate_websocket_summary(result)
            }
            
            # Print summary for this test
            summary = self.results["websocket_validation"]["validation_summary"]
            print(f"✅ WebSocket Validation Complete:")
            print(f"   Tests: {summary.get('passed_tests', 0)}/{summary.get('total_tests', 0)}")
            print(f"   Success Rate: {summary.get('success_rate', 0)}%")
            print(f"   Status: {summary.get('overall_status', 'UNKNOWN')}")
            
        except Exception as e:
            print(f"❌ WebSocket validation failed: {e}")
            self.results["websocket_validation"] = {
                "error": str(e),
                "validation_summary": {
                    "total_tests": 0,
                    "passed_tests": 0,
                    "success_rate": 0,
                    "overall_status": "ERROR"
                }
            }
    
    async def _run_timing_validation(self):
        """Run timing synchronization validation"""
        print(f"\n{'='*60}")
        print("⏰ EXECUTING: Timing Synchronization Validation")
        print(f"{'='*60}")
        
        try:
            result = await test_labjack_timing_synchronization()
            self.results["timing_validation"] = result
            
            # Print summary for this test
            summary = result.get("timing_validation_summary", {})
            print(f"✅ Timing Validation Complete:")
            print(f"   Tests: {summary.get('passed_tests', 0)}/{summary.get('total_tests', 0)}")
            print(f"   Success Rate: {summary.get('success_rate', 0)}%")
            print(f"   Status: {summary.get('overall_status', 'UNKNOWN')}")
            
        except Exception as e:
            print(f"❌ Timing validation failed: {e}")
            self.results["timing_validation"] = {
                "error": str(e),
                "timing_validation_summary": {
                    "total_tests": 0,
                    "passed_tests": 0,
                    "success_rate": 0,
                    "overall_status": "ERROR"
                }
            }
    
    def _calculate_websocket_summary(self, websocket_results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate summary for WebSocket test results"""
        if "error" in websocket_results:
            return {
                "total_tests": 0,
                "passed_tests": 0,
                "success_rate": 0,
                "overall_status": "ERROR"
            }
        
        total_tests = len([k for k in websocket_results.keys() if k != "error"])
        passed_tests = sum(1 for v in websocket_results.values() if v is True)
        success_rate = (passed_tests / max(total_tests, 1)) * 100
        
        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": round(success_rate, 2),
            "overall_status": "PASS" if success_rate >= 70 else "FAIL"
        }
    
    def _generate_final_report(self) -> Dict[str, Any]:
        """Generate comprehensive final validation report"""
        
        end_time = time.time()
        duration = end_time - self.start_time
        
        # Aggregate results
        total_tests = 0
        total_passed = 0
        category_summaries = {}
        all_recommendations = []
        critical_issues = []
        
        for category, result in self.results.items():
            if "validation_summary" in result:
                summary = result["validation_summary"]
            elif "timing_validation_summary" in result:
                summary = result["timing_validation_summary"]
            else:
                continue
                
            category_summaries[category] = summary
            total_tests += summary.get("total_tests", 0)
            total_passed += summary.get("passed_tests", 0)
            
            # Collect recommendations
            if "recommendations" in result:
                all_recommendations.extend(result["recommendations"])
            
            # Identify critical issues
            if summary.get("overall_status") == "FAIL":
                critical_issues.append(f"{category} validation failed")
            
            if "detected_issues" in result:
                critical_issues.extend(result["detected_issues"])
        
        # Calculate overall success rate
        overall_success_rate = (total_passed / max(total_tests, 1)) * 100
        overall_status = "PASS" if overall_success_rate >= 80 else "FAIL"
        
        # Production readiness assessment
        production_ready = self._assess_production_readiness(category_summaries, critical_issues)
        
        final_report = {
            "validation_execution": {
                "start_time": datetime.fromtimestamp(self.start_time, timezone.utc).isoformat(),
                "end_time": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(duration, 2),
                "test_categories_executed": list(self.results.keys())
            },
            "overall_summary": {
                "total_tests": total_tests,
                "passed_tests": total_passed,
                "failed_tests": total_tests - total_passed,
                "success_rate": round(overall_success_rate, 2),
                "overall_status": overall_status
            },
            "category_results": category_summaries,
            "production_readiness_assessment": production_ready,
            "critical_issues": critical_issues,
            "recommendations": list(set(all_recommendations)),  # Remove duplicates
            "detailed_results": self.results
        }
        
        # Print final report
        self._print_final_report(final_report)
        
        # Save report to file
        self._save_report_to_file(final_report)
        
        return final_report
    
    def _assess_production_readiness(self, summaries: Dict[str, Any], issues: List[str]) -> Dict[str, Any]:
        """Assess overall production readiness"""
        
        critical_systems = {
            "workflow_validation": "Core Detection Workflow",
            "websocket_validation": "Real-time Streaming",
            "timing_validation": "Timing Synchronization"
        }
        
        system_status = {}
        critical_failures = []
        
        for system_key, system_name in critical_systems.items():
            if system_key in summaries:
                summary = summaries[system_key]
                success_rate = summary.get("success_rate", 0)
                status = summary.get("overall_status", "UNKNOWN")
                
                system_status[system_name] = {
                    "success_rate": success_rate,
                    "status": status,
                    "production_ready": success_rate >= 85 and status == "PASS"
                }
                
                if not system_status[system_name]["production_ready"]:
                    critical_failures.append(system_name)
            else:
                system_status[system_name] = {
                    "success_rate": 0,
                    "status": "NOT_TESTED",
                    "production_ready": False
                }
                critical_failures.append(system_name)
        
        # Overall production readiness
        all_systems_ready = all(s["production_ready"] for s in system_status.values())
        no_critical_issues = len([i for i in issues if "critical" in i.lower() or "error" in i.lower()]) == 0
        
        overall_ready = all_systems_ready and no_critical_issues
        
        return {
            "overall_production_ready": overall_ready,
            "system_readiness": system_status,
            "critical_system_failures": critical_failures,
            "blocking_issues_count": len(critical_failures) + len([i for i in issues if "critical" in i.lower()]),
            "readiness_score": sum(s["success_rate"] for s in system_status.values()) / len(system_status) if system_status else 0
        }
    
    def _print_final_report(self, report: Dict[str, Any]):
        """Print comprehensive final report"""
        
        print(f"\n{'🎯' + '='*77}")
        print("🏁 FINAL VALIDATION REPORT - LABJACK DETECTION WORKFLOW")
        print(f"{'🎯' + '='*77}")
        
        # Execution Summary
        execution = report["validation_execution"]
        print(f"\n⏱️  EXECUTION SUMMARY:")
        print(f"   Duration: {execution['duration_seconds']}s")
        print(f"   Categories: {', '.join(execution['test_categories_executed'])}")
        
        # Overall Results
        overall = report["overall_summary"]
        print(f"\n📊 OVERALL RESULTS:")
        print(f"   Total Tests: {overall['total_tests']}")
        print(f"   Passed: {overall['passed_tests']}")
        print(f"   Failed: {overall['failed_tests']}")
        print(f"   Success Rate: {overall['success_rate']}%")
        
        status_icon = "✅" if overall["overall_status"] == "PASS" else "❌"
        print(f"   Overall Status: {status_icon} {overall['overall_status']}")
        
        # Category Results
        print(f"\n📋 CATEGORY RESULTS:")
        for category, summary in report["category_results"].items():
            status_icon = "✅" if summary.get("overall_status") == "PASS" else "❌"
            success_rate = summary.get("success_rate", 0)
            category_name = category.replace("_", " ").title()
            print(f"   {category_name}: {status_icon} {success_rate}% ({summary.get('passed_tests', 0)}/{summary.get('total_tests', 0)})")
        
        # Production Readiness
        readiness = report["production_readiness_assessment"]
        print(f"\n🚀 PRODUCTION READINESS ASSESSMENT:")
        
        ready_icon = "✅" if readiness["overall_production_ready"] else "❌"
        print(f"   Overall Ready: {ready_icon} {'YES' if readiness['overall_production_ready'] else 'NO'}")
        print(f"   Readiness Score: {readiness['readiness_score']:.1f}%")
        
        print(f"\n   System Status:")
        for system, status in readiness["system_readiness"].items():
            ready_icon = "✅" if status["production_ready"] else "❌"
            print(f"     {system}: {ready_icon} {status['success_rate']:.1f}% ({status['status']})")
        
        if readiness["critical_system_failures"]:
            print(f"\n   ⚠️  Critical System Failures:")
            for failure in readiness["critical_system_failures"]:
                print(f"     - {failure}")
        
        # Critical Issues
        if report["critical_issues"]:
            print(f"\n⚠️  CRITICAL ISSUES ({len(report['critical_issues'])}):")
            for issue in report["critical_issues"]:
                print(f"   - {issue}")
        
        # Recommendations
        if report["recommendations"]:
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in report["recommendations"]:
                print(f"   - {rec}")
        
        print(f"\n{'🎯' + '='*77}")
        
        # Final verdict
        if readiness["overall_production_ready"]:
            print("🎉 SYSTEM IS PRODUCTION READY! 🎉")
        else:
            print("⚠️  SYSTEM REQUIRES FIXES BEFORE PRODUCTION DEPLOYMENT")
        
        print(f"{'🎯' + '='*77}")
    
    def _save_report_to_file(self, report: Dict[str, Any]):
        """Save detailed report to JSON file"""
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"tests/labjack_validation_report_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            print(f"\n💾 Detailed report saved to: {filename}")
        except Exception as e:
            print(f"⚠️  Could not save report to file: {e}")


async def main():
    """Main execution function"""
    
    parser = argparse.ArgumentParser(
        description="Run comprehensive LabJack detection workflow validation suite"
    )
    
    parser.add_argument(
        "--tests",
        type=str,
        help="Comma-separated list of test categories to run (workflow,websocket,timing). Default: all",
        default="workflow,websocket,timing"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        help="Output format (console,json,both). Default: both",
        default="both"
    )
    
    parser.add_argument(
        "--min-success-rate",
        type=int,
        help="Minimum success rate to consider validation passed (default: 80)",
        default=80
    )
    
    args = parser.parse_args()
    
    # Parse test categories
    if args.tests.lower() == "all":
        test_categories = ["workflow", "websocket", "timing"]
    else:
        test_categories = [t.strip().lower() for t in args.tests.split(",")]
    
    # Validate test categories
    valid_categories = {"workflow", "websocket", "timing"}
    invalid_categories = set(test_categories) - valid_categories
    
    if invalid_categories:
        print(f"❌ Invalid test categories: {invalid_categories}")
        print(f"Valid categories: {valid_categories}")
        sys.exit(1)
    
    # Run validation suite
    runner = LabJackValidationSuiteRunner()
    
    try:
        report = await runner.run_complete_validation_suite(test_categories)
        
        # Check if validation passed based on minimum success rate
        overall_success_rate = report["overall_summary"]["success_rate"]
        
        if overall_success_rate >= args.min_success_rate:
            print(f"\n🎉 VALIDATION SUITE PASSED (>{args.min_success_rate}%)")
            sys.exit(0)
        else:
            print(f"\n❌ VALIDATION SUITE FAILED (<{args.min_success_rate}%)")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n⚠️  Validation suite interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"\n💥 Validation suite crashed: {e}")
        sys.exit(3)


if __name__ == "__main__":
    # Run the validation suite
    asyncio.run(main())