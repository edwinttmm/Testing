#!/usr/bin/env python3
"""
API Endpoints Comparison Script
==============================

Compares endpoints between the original main.py and the new organized router structure
to ensure no functionality is lost during the architectural reorganization.

Usage:
    python scripts/compare_api_endpoints.py
"""

import re
import ast
import inspect
from pathlib import Path
from typing import Dict, List, Set, Tuple
import json

class EndpointExtractor:
    """Extracts API endpoints from Python files"""
    
    def __init__(self):
        self.endpoint_patterns = [
            r'@app\.(get|post|put|delete|patch)\("([^"]+)"',
            r'@router\.(get|post|put|delete|patch)\("([^"]+)"',
            r'@.*router.*\.(get|post|put|delete|patch)\("([^"]+)"'
        ]
    
    def extract_from_file(self, file_path: str) -> List[Tuple[str, str]]:
        """Extract endpoints from a Python file"""
        endpoints = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract endpoints using regex
            for pattern in self.endpoint_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for method, path in matches:
                    # Clean up the path
                    path = path.strip()
                    method = method.upper()
                    endpoints.append((method, path))
            
            return endpoints
            
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return []
    
    def extract_from_directory(self, directory: str, pattern: str = "*.py") -> Dict[str, List[Tuple[str, str]]]:
        """Extract endpoints from all Python files in a directory"""
        results = {}
        
        dir_path = Path(directory)
        for file_path in dir_path.glob(pattern):
            if file_path.is_file():
                endpoints = self.extract_from_file(str(file_path))
                if endpoints:
                    results[str(file_path)] = endpoints
        
        return results

class EndpointComparator:
    """Compares endpoint collections and identifies differences"""
    
    def __init__(self):
        self.extractor = EndpointExtractor()
    
    def normalize_endpoint(self, method: str, path: str) -> str:
        """Normalize endpoint for comparison"""
        # Remove query parameters and fragments
        path = path.split('?')[0].split('#')[0]
        
        # Normalize path parameters
        path = re.sub(r'\{[^}]+\}', '{param}', path)
        
        # Remove trailing slashes
        path = path.rstrip('/')
        
        return f"{method.upper()} {path}"
    
    def extract_legacy_endpoints(self) -> Set[str]:
        """Extract endpoints from legacy main.py and related files"""
        legacy_files = [
            'main.py',
            'api_project_session_management.py',
            'api_video_annotation.py',
            'auth_endpoints.py'
        ]
        
        endpoints = set()
        
        for file_name in legacy_files:
            if Path(file_name).exists():
                file_endpoints = self.extractor.extract_from_file(file_name)
                for method, path in file_endpoints:
                    normalized = self.normalize_endpoint(method, path)
                    endpoints.add(normalized)
        
        return endpoints
    
    def extract_organized_endpoints(self) -> Set[str]:
        """Extract endpoints from organized router structure"""
        router_files = [
            'routers/projects.py',
            'routers/videos.py', 
            'routers/test_sessions.py',
            'routers/auth.py',
            'routers/dashboard.py'
        ]
        
        endpoints = set()
        
        for file_name in router_files:
            if Path(file_name).exists():
                file_endpoints = self.extractor.extract_from_file(file_name)
                for method, path in file_endpoints:
                    normalized = self.normalize_endpoint(method, path)
                    endpoints.add(normalized)
        
        return endpoints
    
    def categorize_endpoints(self, endpoints: Set[str]) -> Dict[str, List[str]]:
        """Categorize endpoints by resource type"""
        categories = {
            'projects': [],
            'videos': [],
            'test_sessions': [],
            'auth': [],
            'dashboard': [],
            'health': [],
            'websocket': [],
            'other': []
        }
        
        for endpoint in endpoints:
            method, path = endpoint.split(' ', 1)
            
            if '/api/projects' in path:
                categories['projects'].append(endpoint)
            elif '/api/videos' in path:
                categories['videos'].append(endpoint)
            elif '/api/test-sessions' in path or '/api/sessions' in path:
                categories['test_sessions'].append(endpoint)
            elif '/auth' in path:
                categories['auth'].append(endpoint)
            elif '/api/dashboard' in path:
                categories['dashboard'].append(endpoint)
            elif '/health' in path:
                categories['health'].append(endpoint)
            elif '/ws' in path:
                categories['websocket'].append(endpoint)
            else:
                categories['other'].append(endpoint)
        
        return categories
    
    def compare_endpoints(self) -> Dict[str, any]:
        """Compare legacy vs organized endpoints"""
        print("🔍 Extracting endpoints from legacy files...")
        legacy_endpoints = self.extract_legacy_endpoints()
        
        print("🔍 Extracting endpoints from organized routers...")
        organized_endpoints = self.extract_organized_endpoints()
        
        # Find differences
        missing_in_organized = legacy_endpoints - organized_endpoints
        new_in_organized = organized_endpoints - legacy_endpoints
        common_endpoints = legacy_endpoints & organized_endpoints
        
        # Categorize endpoints
        legacy_categories = self.categorize_endpoints(legacy_endpoints)
        organized_categories = self.categorize_endpoints(organized_endpoints)
        
        results = {
            'summary': {
                'legacy_total': len(legacy_endpoints),
                'organized_total': len(organized_endpoints),
                'common': len(common_endpoints),
                'missing_in_organized': len(missing_in_organized),
                'new_in_organized': len(new_in_organized),
                'compatibility_score': (len(common_endpoints) / len(legacy_endpoints) * 100) if legacy_endpoints else 100
            },
            'missing_endpoints': sorted(list(missing_in_organized)),
            'new_endpoints': sorted(list(new_in_organized)),
            'common_endpoints': sorted(list(common_endpoints)),
            'legacy_categories': {k: len(v) for k, v in legacy_categories.items()},
            'organized_categories': {k: len(v) for k, v in organized_categories.items()},
            'detailed_categories': {
                'legacy': legacy_categories,
                'organized': organized_categories
            }
        }
        
        return results
    
    def generate_migration_report(self) -> str:
        """Generate comprehensive migration report"""
        results = self.compare_endpoints()
        
        # Generate report
        report_lines = [
            "# API Endpoint Migration Report",
            "=" * 50,
            "",
            "## Summary",
            f"- Legacy endpoints: {results['summary']['legacy_total']}",
            f"- Organized endpoints: {results['summary']['organized_total']}",
            f"- Common endpoints: {results['summary']['common']}",
            f"- Missing in organized: {results['summary']['missing_in_organized']}",
            f"- New in organized: {results['summary']['new_in_organized']}",
            f"- Compatibility score: {results['summary']['compatibility_score']:.1f}%",
            ""
        ]
        
        # Missing endpoints analysis
        if results['missing_endpoints']:
            report_lines.extend([
                "## ⚠️ Missing Endpoints in Organized Structure",
                ""
            ])
            for endpoint in results['missing_endpoints']:
                report_lines.append(f"- `{endpoint}`")
            report_lines.append("")
        
        # New endpoints
        if results['new_endpoints']:
            report_lines.extend([
                "## ✅ New Endpoints in Organized Structure",
                ""
            ])
            for endpoint in results['new_endpoints']:
                report_lines.append(f"- `{endpoint}`")
            report_lines.append("")
        
        # Category comparison
        report_lines.extend([
            "## 📊 Endpoint Distribution by Category",
            "",
            "| Category | Legacy | Organized | Delta |",
            "|----------|---------|-----------|-------|"
        ])
        
        for category in results['legacy_categories'].keys():
            legacy_count = results['legacy_categories'][category]
            organized_count = results['organized_categories'].get(category, 0)
            delta = organized_count - legacy_count
            delta_str = f"+{delta}" if delta > 0 else str(delta) if delta < 0 else "0"
            
            report_lines.append(f"| {category.title()} | {legacy_count} | {organized_count} | {delta_str} |")
        
        report_lines.extend([
            "",
            "## 🎯 Migration Status",
            ""
        ])
        
        compatibility_score = results['summary']['compatibility_score']
        if compatibility_score >= 95:
            report_lines.append("✅ **EXCELLENT** - Migration maintains high compatibility")
        elif compatibility_score >= 90:
            report_lines.append("✅ **GOOD** - Migration maintains good compatibility")
        elif compatibility_score >= 80:
            report_lines.append("⚠️ **WARNING** - Some endpoints may be missing")
        else:
            report_lines.append("❌ **CRITICAL** - Significant endpoints missing")
        
        # Detailed endpoint lists
        report_lines.extend([
            "",
            "## 📋 Detailed Endpoint Analysis",
            "",
            "### Common Endpoints (Maintained)",
            ""
        ])
        
        for endpoint in sorted(results['common_endpoints']):
            report_lines.append(f"- `{endpoint}`")
        
        return "\n".join(report_lines)

def main():
    """Main function"""
    print("🚀 Starting API Endpoint Comparison")
    
    comparator = EndpointComparator()
    
    # Generate comparison results
    results = comparator.compare_endpoints()
    
    # Save results to JSON
    results_file = "endpoint_comparison_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Generate and save migration report
    report = comparator.generate_migration_report()
    report_file = "API_MIGRATION_REPORT.md"
    with open(report_file, 'w') as f:
        f.write(report)
    
    # Print summary
    print("\n" + "="*60)
    print("📊 API ENDPOINT COMPARISON SUMMARY")
    print("="*60)
    print(f"Legacy endpoints: {results['summary']['legacy_total']}")
    print(f"Organized endpoints: {results['summary']['organized_total']}")
    print(f"Compatibility score: {results['summary']['compatibility_score']:.1f}%")
    print(f"Results saved: {results_file}")
    print(f"Report saved: {report_file}")
    
    if results['summary']['missing_in_organized']:
        print(f"\n⚠️ {len(results['summary']['missing_in_organized'])} endpoints may need attention")
        print("See report for details.")
    else:
        print("\n✅ All legacy endpoints accounted for!")
    
    print("="*60)

if __name__ == "__main__":
    main()