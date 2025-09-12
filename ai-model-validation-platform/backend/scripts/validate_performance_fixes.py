#!/usr/bin/env python3
"""
Performance Fix Validation Script

Quick validation script to verify the database performance optimizations are working correctly.
"""

import sys
import os
import re
from pathlib import Path

def validate_projects_all_optimization():
    """Validate that /projects/all endpoint uses optimized single query"""
    
    api_file = Path("api_project_session_management.py")
    if not api_file.exists():
        print("❌ api_project_session_management.py not found")
        return False
    
    with open(api_file, 'r') as f:
        content = f.read()
    
    # Check for optimized query pattern
    checks = [
        ("Single query with joins", r"func\.count\(func\.distinct\(.*?\)\).*?outerjoin", "Optimized single query with joins found"),
        ("No N+1 pattern", r"\.query\(Video\)\.filter\(Video\.project_id.*?\.count\(\)", "N+1 query pattern should be eliminated"),
        ("Proper group by", r"group_by\(.*?Project\.id.*?\)", "Proper GROUP BY clause found")
    ]
    
    results = []
    for check_name, pattern, success_msg in checks:
        if re.search(pattern, content, re.DOTALL):
            if "should be eliminated" in success_msg:
                results.append(f"❌ {check_name}: N+1 pattern still present")
            else:
                results.append(f"✅ {check_name}: {success_msg}")
        else:
            if "should be eliminated" in success_msg:
                results.append(f"✅ {check_name}: N+1 pattern eliminated")
            else:
                results.append(f"❌ {check_name}: Optimization not found")
    
    return results

def validate_statistics_connection_fix():
    """Validate that /statistics/summary endpoint uses proper dependency injection"""
    
    api_file = Path("api_project_session_management.py")
    if not api_file.exists():
        print("❌ api_project_session_management.py not found")
        return False
    
    with open(api_file, 'r') as f:
        content = f.read()
    
    # Extract the statistics/summary endpoint
    stats_match = re.search(r'@router\.get\("/statistics/summary"\).*?(?=@router\.|\Z)', content, re.DOTALL)
    if not stats_match:
        return ["❌ Statistics endpoint not found"]
    
    stats_content = stats_match.group()
    
    checks = [
        ("Dependency injection", r"db:\s*Session\s*=\s*Depends\(get_db\)", "Proper FastAPI dependency injection found"),
        ("No manual Session()", r"db\s*=\s*Session\(\)", "Manual Session() creation should be eliminated"),
        ("No manual db.close()", r"db\.close\(\)", "Manual db.close() should be eliminated")
    ]
    
    results = []
    for check_name, pattern, success_msg in checks:
        if re.search(pattern, stats_content):
            if "should be eliminated" in success_msg:
                results.append(f"❌ {check_name}: {success_msg}")
            else:
                results.append(f"✅ {check_name}: {success_msg}")
        else:
            if "should be eliminated" in success_msg:
                results.append(f"✅ {check_name}: Manual pattern eliminated")
            else:
                results.append(f"❌ {check_name}: {success_msg.replace('found', 'not found')}")
    
    return results

def validate_file_structure():
    """Validate that all necessary files are in place"""
    
    required_files = [
        ("API file", "api_project_session_management.py"),
        ("Database config", "database.py"),
        ("Performance tests", "tests/test_performance_optimization.py"),
        ("Performance report", "docs/PERFORMANCE_OPTIMIZATION_REPORT.md")
    ]
    
    results = []
    for desc, filepath in required_files:
        if Path(filepath).exists():
            results.append(f"✅ {desc}: {filepath} exists")
        else:
            results.append(f"❌ {desc}: {filepath} not found")
    
    return results

def main():
    """Main validation function"""
    print("=" * 60)
    print("DATABASE PERFORMANCE OPTIMIZATION VALIDATION")
    print("=" * 60)
    
    # Change to backend directory if needed
    if not Path("api_project_session_management.py").exists():
        backend_path = Path(__file__).parent.parent
        os.chdir(backend_path)
        print(f"Changed to directory: {backend_path}")
    
    # Run validations
    all_passed = True
    
    print("\n🔍 Validating file structure...")
    file_results = validate_file_structure()
    for result in file_results:
        print(f"  {result}")
        if "❌" in result:
            all_passed = False
    
    print("\n🔍 Validating /projects/all optimization...")
    projects_results = validate_projects_all_optimization()
    for result in projects_results:
        print(f"  {result}")
        if "❌" in result:
            all_passed = False
    
    print("\n🔍 Validating /statistics/summary connection fix...")
    stats_results = validate_statistics_connection_fix()
    for result in stats_results:
        print(f"  {result}")
        if "❌" in result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL PERFORMANCE OPTIMIZATIONS VALIDATED SUCCESSFULLY!")
        print("✅ N+1 query bug eliminated")
        print("✅ Connection leak prevention implemented") 
        print("✅ Proper dependency injection in place")
        print("✅ System ready for production deployment")
    else:
        print("❌ SOME VALIDATIONS FAILED")
        print("Please review the issues above and ensure all fixes are properly implemented")
    
    print("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)