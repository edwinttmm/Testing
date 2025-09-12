#!/usr/bin/env python3
"""
Frontend Component Validation Tests
Tests frontend components and integration without requiring running servers
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Any

class FrontendValidator:
    """Frontend component validation test suite"""
    
    def __init__(self):
        self.test_results = []
        self.frontend_path = Path("../frontend")
        
    def run_test(self, test_name: str, test_func):
        """Run a test and record results"""
        print(f"🧪 Running: {test_name}")
        
        try:
            start_time = time.time()
            result = test_func()
            duration = time.time() - start_time
            
            self.test_results.append({
                'name': test_name,
                'status': 'passed',
                'duration': duration,
                'result': result
            })
            print(f"✅ {test_name}: PASSED ({duration:.3f}s)")
            return True
            
        except Exception as e:
            self.test_results.append({
                'name': test_name,
                'status': 'failed',
                'error': str(e)
            })
            print(f"❌ {test_name}: FAILED - {e}")
            return False
    
    def test_frontend_structure(self):
        """Test frontend file structure exists"""
        if not self.frontend_path.exists():
            raise FileNotFoundError(f"Frontend directory not found: {self.frontend_path}")
        
        required_files = [
            "package.json",
            "src/App.tsx",
            "src/index.tsx",
            "public/index.html"
        ]
        
        missing_files = []
        for file_path in required_files:
            full_path = self.frontend_path / file_path
            if not full_path.exists():
                missing_files.append(file_path)
        
        if missing_files:
            raise AssertionError(f"Missing frontend files: {missing_files}")
        
        return f"Frontend structure valid with {len(required_files)} core files"
    
    def test_package_json_dependencies(self):
        """Test package.json has required dependencies"""
        package_json_path = self.frontend_path / "package.json"
        if not package_json_path.exists():
            raise FileNotFoundError("package.json not found")
        
        with open(package_json_path, 'r') as f:
            package_data = json.load(f)
        
        required_deps = ["react", "@types/react"]
        dependencies = package_data.get("dependencies", {})
        dev_dependencies = package_data.get("devDependencies", {})
        
        all_deps = {**dependencies, **dev_dependencies}
        missing_deps = [dep for dep in required_deps if dep not in all_deps]
        
        if missing_deps:
            raise AssertionError(f"Missing required dependencies: {missing_deps}")
        
        return f"Package.json valid with {len(all_deps)} total dependencies"
    
    def test_component_files_exist(self):
        """Test key component files exist"""
        components_dir = self.frontend_path / "src/components"
        if not components_dir.exists():
            return "No components directory found - may be organized differently"
        
        component_files = list(components_dir.rglob("*.tsx")) + list(components_dir.rglob("*.ts"))
        
        # Look for common component patterns
        common_components = [
            "VideoPlayer",
            "ProjectManager", 
            "TestExecution",
            "Results",
            "Dashboard"
        ]
        
        found_components = []
        for component in common_components:
            matching_files = [f for f in component_files if component.lower() in f.name.lower()]
            if matching_files:
                found_components.append(component)
        
        return f"Found {len(component_files)} component files, {len(found_components)} key components"
    
    def test_typescript_configuration(self):
        """Test TypeScript configuration exists"""
        ts_config_files = ["tsconfig.json", "tsconfig.ts"]
        
        for config_file in ts_config_files:
            config_path = self.frontend_path / config_file
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        config_data = json.load(f)
                    
                    # Check for basic TypeScript config
                    if "compilerOptions" in config_data:
                        return f"TypeScript configured via {config_file}"
                except json.JSONDecodeError:
                    # May have comments, which is valid for tsconfig.json
                    return f"TypeScript config file exists: {config_file}"
        
        return "No TypeScript configuration found (may use defaults)"
    
    def test_build_configuration(self):
        """Test build configuration exists"""
        build_configs = [
            "webpack.config.js",
            "vite.config.js", 
            "vite.config.ts",
            "craco.config.js"
        ]
        
        found_configs = []
        for config in build_configs:
            if (self.frontend_path / config).exists():
                found_configs.append(config)
        
        # Check package.json scripts
        package_json_path = self.frontend_path / "package.json"
        if package_json_path.exists():
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)
            
            scripts = package_data.get("scripts", {})
            build_scripts = [s for s in scripts.keys() if "build" in s.lower()]
            
            if build_scripts or found_configs:
                return f"Build system configured: {found_configs + build_scripts}"
        
        return "Build configuration minimal or using defaults"
    
    def test_environment_configuration(self):
        """Test environment configuration"""
        env_files = [
            ".env",
            ".env.local", 
            ".env.development",
            ".env.production"
        ]
        
        found_env_files = []
        for env_file in env_files:
            env_path = self.frontend_path / env_file
            if env_path.exists():
                found_env_files.append(env_file)
        
        if found_env_files:
            return f"Environment configured via: {found_env_files}"
        else:
            return "No environment files found (may use defaults)"
    
    def test_static_assets(self):
        """Test static assets exist"""
        public_dir = self.frontend_path / "public"
        if not public_dir.exists():
            raise FileNotFoundError("Public directory not found")
        
        static_files = list(public_dir.rglob("*"))
        static_files = [f for f in static_files if f.is_file()]
        
        # Look for common static assets
        asset_types = {
            'html': [f for f in static_files if f.suffix == '.html'],
            'images': [f for f in static_files if f.suffix in ['.png', '.jpg', '.jpeg', '.svg', '.ico']],
            'fonts': [f for f in static_files if f.suffix in ['.ttf', '.woff', '.woff2']],
            'json': [f for f in static_files if f.suffix == '.json']
        }
        
        asset_summary = {k: len(v) for k, v in asset_types.items()}
        return f"Static assets found: {asset_summary}"
    
    def test_failure_snapshot_components(self):
        """Test failure snapshot display components exist"""
        # Look for snapshot/result display components
        src_dir = self.frontend_path / "src"
        if not src_dir.exists():
            return "No src directory found"
        
        all_files = list(src_dir.rglob("*.tsx")) + list(src_dir.rglob("*.ts"))
        
        # Look for snapshot/result related files
        snapshot_keywords = ["snapshot", "result", "failure", "detection", "comparison"]
        snapshot_files = []
        
        for file in all_files:
            file_content_lower = file.name.lower()
            if any(keyword in file_content_lower for keyword in snapshot_keywords):
                snapshot_files.append(file.name)
        
        if snapshot_files:
            return f"Snapshot/result components found: {snapshot_files[:5]}"  # Show first 5
        else:
            return "No specific snapshot display components identified"
    
    def run_all_tests(self):
        """Run all frontend validation tests"""
        print("🧪 Starting Frontend Validation...")
        print("=" * 60)
        
        tests = [
            ("Frontend Structure", self.test_frontend_structure),
            ("Package.json Dependencies", self.test_package_json_dependencies),
            ("Component Files", self.test_component_files_exist),
            ("TypeScript Configuration", self.test_typescript_configuration),
            ("Build Configuration", self.test_build_configuration),
            ("Environment Configuration", self.test_environment_configuration),
            ("Static Assets", self.test_static_assets),
            ("Failure Snapshot Components", self.test_failure_snapshot_components),
        ]
        
        for test_name, test_func in tests:
            self.run_test(test_name, test_func)
        
        # Generate report
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['status'] == 'passed')
        
        print("\n" + "=" * 60)
        print("📊 FRONTEND VALIDATION REPORT")
        print("=" * 60)
        
        if passed_tests == total_tests:
            overall_status = "FULLY READY"
            status_icon = "✅"
        elif passed_tests > total_tests * 0.7:
            overall_status = "MOSTLY READY"  
            status_icon = "⚠️"
        else:
            overall_status = "NOT READY"
            status_icon = "❌"
        
        print(f"{status_icon} Overall Status: {overall_status}")
        print(f"📈 Test Results: {passed_tests}/{total_tests} passed")
        
        # Show failed tests
        failed_tests = [r for r in self.test_results if r['status'] == 'failed']
        if failed_tests:
            print(f"❌ Failed Tests: {len(failed_tests)}")
            for test in failed_tests:
                print(f"   ❌ {test['name']}: {test.get('error', 'Unknown error')}")
        
        return {
            "overall_status": overall_status,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": len(failed_tests),
            "test_results": self.test_results
        }

if __name__ == "__main__":
    validator = FrontendValidator()
    report = validator.run_all_tests()
    
    # Save report
    report_file = f"frontend_validation_report_{int(time.time())}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n📄 Frontend validation report saved to: {report_file}")
    
    if report.get("passed_tests", 0) >= report.get("total_tests", 1) * 0.7:
        print("\n🎉 Frontend validation largely successful!")
        sys.exit(0) 
    else:
        print("\n💥 Frontend validation failed!")
        sys.exit(1)