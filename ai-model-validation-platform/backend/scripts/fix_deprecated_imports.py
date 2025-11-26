#!/usr/bin/env python3
"""
Automated script to fix deprecated service imports in test files.
Fixes 29 deprecated import errors by mapping to correct service paths.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Service mapping: deprecated -> correct (or DEPRECATED for removal)
SERVICE_MAPPING = {
    'services.timing_synchronization_calculator': 'DEPRECATED',
    'services.labjack_detection_service': 'services.simple_labjack_detection',
    'services.detection_queue_service': 'DEPRECATED',
    'services.hil_screenshot_service': 'DEPRECATED',
    'services.websocket_rooms': 'DEPRECATED',
    'services.labjack_monitoring_service': 'services.dedicated_labjack_monitor',
    'services.standalone_labjack_monitor': 'services.dedicated_labjack_monitor',
    'services.video_timing_service': 'DEPRECATED',
    'services.detection_pipeline_service': 'DEPRECATED',
    'services.clock_sync_service': 'services.clock_sync_service_v2',
    'services.video_sequence_orchestrator': 'services.video_lifecycle_orchestrator',
    'services.hil_validation_service': 'DEPRECATED',
    'services.labjack_service': 'services.labjack_service_manager',
    'services.video_validation_service': 'DEPRECATED',
    'services.labjack_monitoring_service_enhanced': 'services.dedicated_labjack_monitor',
    'services.heartbeat_service': 'DEPRECATED',
    'services.session_monitor': 'DEPRECATED',
    'services.video_state_machine': 'DEPRECATED',
    'services.camera_latency_measurement_service': 'DEPRECATED',
    'services.precision_timing_service': 'services.labjack_timing_service',
    'services.detection_boundary_service': 'DEPRECATED',
    'services.detection_metrics': 'DEPRECATED',
    'services.detection_window_clamp_service': 'DEPRECATED',
    'services.labjack_hardware_service': 'services.simple_labjack_detection',
    'services.frame_aware_quality_assessment': 'DEPRECATED',
    'services.video_id_resolver': 'DEPRECATED',
    'services.monitoring_process_manager': 'DEPRECATED',
    'services.dedicated_monitoring_service': 'services.dedicated_labjack_monitor',
    'services.monitoring_service_client': 'services.labjack_monitor_client',
    'services.detection_buffer': 'DEPRECATED',
    'services.labjack_integration_service': 'DEPRECATED',
    'services.labjack_config_manager': 'DEPRECATED',
    'services.labjack_error_handler': 'DEPRECATED',
    'services.timing_validation_service': 'DEPRECATED',
    'services.video_hardware_sync_service': 'DEPRECATED',
    'services.test_execution_service': 'DEPRECATED',
    'services.enhanced_detection_service': 'services.simple_labjack_detection',
    'services.websocket_service': 'DEPRECATED',
    'services.latency_validation_service': 'DEPRECATED',
    'services.optimal_matching_service': 'services.ground_truth_matching_service',
    'services.failure_snapshot_service': 'DEPRECATED',
    'services.report_generation_service': 'DEPRECATED',
    'services.test_report_generator': 'DEPRECATED',
    'services.detection_video_assignment': 'DEPRECATED',
    'services.detection_video_reassignment': 'DEPRECATED',
    'services.timing_orchestration_service': 'DEPRECATED',
    'services.transaction_manager': 'DEPRECATED',
    'services.session_cleanup': 'DEPRECATED',
    'services.video_lifecycle_websocket_handlers': 'DEPRECATED',
    'services.timestamp_conversion_utils': 'DEPRECATED',
    'services.enhanced_ml_service': 'services.ml_generation_service',
    'services.project_management_service': 'DEPRECATED',
    'services.validation_service': 'services.detection_validation_service',
    'services.video_processing_service': 'DEPRECATED',
    'services.video_ingestion_service': 'DEPRECATED',
    'services.vru_tracking_service': 'DEPRECATED',
    'services.quality_warnings': 'DEPRECATED',
}


class ImportFixer:
    def __init__(self):
        self.fixed_files = []
        self.deprecated_files = []
        self.changes = []

    def fix_file(self, filepath: str) -> Tuple[bool, List[str]]:
        """Fix imports in a single file. Returns (was_fixed, changes)"""
        try:
            with open(filepath, 'r') as f:
                content = f.read()
                original_content = content

            file_changes = []
            should_deprecate = False
            deprecated_count = 0
            fixed_count = 0

            # Find all service imports
            for old_service, new_service in SERVICE_MAPPING.items():
                # Check if this service is imported
                old_module = old_service.split('.')[-1]

                # Pattern 1: from services.xxx import ...
                pattern1 = rf'from {re.escape(old_service)} import'
                if re.search(pattern1, content):
                    if new_service == 'DEPRECATED':
                        deprecated_count += 1
                    else:
                        content = re.sub(pattern1, f'from {new_service} import', content)
                        file_changes.append(f"  - Changed: from {old_service} import -> from {new_service} import")
                        fixed_count += 1

                # Pattern 2: import services.xxx
                pattern2 = rf'import {re.escape(old_service)}'
                if re.search(pattern2, content):
                    if new_service == 'DEPRECATED':
                        deprecated_count += 1
                    else:
                        content = re.sub(pattern2, f'import {new_service}', content)
                        file_changes.append(f"  - Changed: import {old_service} -> import {new_service}")
                        fixed_count += 1

            # Determine if file should be deprecated
            if deprecated_count > 0 and fixed_count == 0:
                should_deprecate = True
                file_changes.append(f"  ⚠️  File has {deprecated_count} deprecated imports with no alternatives")
                file_changes.append(f"  → Should be moved to tests/deprecated/")

            # Only write if content changed
            if content != original_content:
                with open(filepath, 'w') as f:
                    f.write(content)
                return True, file_changes
            elif should_deprecate:
                return False, file_changes
            else:
                return False, []

        except Exception as e:
            return False, [f"  ❌ Error: {str(e)}"]

    def process_all_tests(self, test_dir: str = 'tests'):
        """Process all test files"""
        print("🔍 Scanning test directory for deprecated imports...")

        for root, dirs, files in os.walk(test_dir):
            # Skip deprecated directory
            if 'deprecated' in root:
                continue

            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    was_fixed, changes = self.fix_file(filepath)

                    if changes:
                        rel_path = os.path.relpath(filepath, test_dir)
                        self.changes.append((rel_path, changes))

                        if was_fixed:
                            self.fixed_files.append(filepath)
                        elif any('deprecated' in c.lower() for c in changes):
                            self.deprecated_files.append(filepath)

    def generate_report(self) -> str:
        """Generate a detailed report of all changes"""
        report = []
        report.append("# Deprecated Import Fixes Report\n")
        report.append(f"Generated: {Path.cwd()}\n")
        report.append(f"Date: 2025-11-20\n\n")

        report.append("## Summary\n")
        report.append(f"- **Files Fixed**: {len(self.fixed_files)}\n")
        report.append(f"- **Files to Deprecate**: {len(self.deprecated_files)}\n")
        report.append(f"- **Total Changes**: {len(self.changes)}\n\n")

        report.append("## Service Mappings Applied\n\n")
        report.append("| Deprecated Service | New Service |\n")
        report.append("|-------------------|-------------|\n")
        for old, new in sorted(SERVICE_MAPPING.items()):
            if new != 'DEPRECATED':
                report.append(f"| `{old}` | `{new}` |\n")

        report.append("\n## Files Marked for Deprecation\n\n")
        report.append("These files import only deprecated services with no alternatives:\n\n")
        for old, new in sorted(SERVICE_MAPPING.items()):
            if new == 'DEPRECATED':
                report.append(f"- `{old}`\n")

        report.append("\n## Detailed Changes\n\n")
        for filepath, changes in self.changes:
            report.append(f"### `{filepath}`\n\n")
            for change in changes:
                report.append(f"{change}\n")
            report.append("\n")

        report.append("\n## Next Steps\n\n")
        report.append("1. Run: `python -m pytest --collect-only tests/ 2>&1 | grep -E \"(ImportError|ModuleNotFoundError)\" | wc -l`\n")
        report.append("2. Expected result: **0 import errors**\n")
        report.append("3. Move deprecated test files to `tests/deprecated/` directory\n")
        report.append("4. Add deprecation notices to moved files\n")

        return ''.join(report)


def main():
    """Main execution"""
    print("=" * 70)
    print("  Deprecated Service Import Fixer")
    print("=" * 70)
    print()

    fixer = ImportFixer()
    fixer.process_all_tests('tests')

    print(f"\n✅ Fixed {len(fixer.fixed_files)} files")
    print(f"⚠️  {len(fixer.deprecated_files)} files need deprecation")

    # Generate report
    report = fixer.generate_report()

    # Save report
    os.makedirs('docs', exist_ok=True)
    report_path = 'docs/deprecated_imports_fixes.md'
    with open(report_path, 'w') as f:
        f.write(report)

    print(f"\n📄 Report saved to: {report_path}")
    print("\n" + "=" * 70)
    print("  Summary")
    print("=" * 70)
    print(f"Total service mappings: {len(SERVICE_MAPPING)}")
    print(f"Files fixed: {len(fixer.fixed_files)}")
    print(f"Files to deprecate: {len(fixer.deprecated_files)}")
    print("\nRun verification command:")
    print("  python -m pytest --collect-only tests/ 2>&1 | grep -E \"(ImportError|ModuleNotFoundError)\" | wc -l")


if __name__ == '__main__':
    main()
