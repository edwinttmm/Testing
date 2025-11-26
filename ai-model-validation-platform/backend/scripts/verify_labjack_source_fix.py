#!/usr/bin/env python3
"""
Verification Script for LabJack Detection Source Fix

This script verifies that the duplicate detection source issue has been resolved.
It checks:
1. Which detection services are active
2. Database records for source="labjack" vs source="dedicated_labjack_monitor"
3. Identifies any remaining duplicates
4. Provides recommendations

ISSUE: Both "labjack" and "dedicated_labjack_monitor" were writing detections,
causing 100% duplication (167 detections each = 334 total).

ROOT CAUSE:
- services/labjack_detection_service.py (line 2193): source='labjack'
- services/dedicated_labjack_monitor.py (lines 1365, 2099): source='dedicated_labjack_monitor'
- Both services were active simultaneously
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from database import SessionLocal
from models import DetectionEvent
from sqlalchemy import func, distinct


def check_detection_sources() -> Dict[str, any]:
    """Check all detection sources in the database"""
    db = SessionLocal()
    results = {
        'success': True,
        'total_detections': 0,
        'sources': {},
        'duplicates': [],
        'errors': []
    }

    try:
        # Count all detections by source
        source_counts = db.query(
            DetectionEvent.source,
            func.count(DetectionEvent.id).label('count'),
            func.min(DetectionEvent.timestamp).label('first_ts'),
            func.max(DetectionEvent.timestamp).label('last_ts')
        ).group_by(DetectionEvent.source).all()

        for source, count, first_ts, last_ts in source_counts:
            source_name = source or 'NULL'
            results['sources'][source_name] = {
                'count': count,
                'first_detection': datetime.fromtimestamp(first_ts) if first_ts else None,
                'last_detection': datetime.fromtimestamp(last_ts) if last_ts else None
            }
            results['total_detections'] += count

        # Check for duplicate timestamps (potential duplicate writes)
        recent_time = datetime.utcnow() - timedelta(hours=24)
        duplicates = db.query(
            DetectionEvent.timestamp,
            func.count(DetectionEvent.id).label('count'),
            func.group_concat(distinct(DetectionEvent.source)).label('sources')
        ).filter(
            DetectionEvent.timestamp >= recent_time.timestamp()
        ).group_by(
            DetectionEvent.timestamp
        ).having(
            func.count(DetectionEvent.id) > 1
        ).all()

        for ts, count, sources in duplicates:
            results['duplicates'].append({
                'timestamp': datetime.fromtimestamp(ts),
                'count': count,
                'sources': sources.split(',') if sources else []
            })

    except Exception as e:
        results['success'] = False
        results['errors'].append(f"Database query failed: {e}")
    finally:
        db.close()

    return results


def analyze_active_services() -> Dict[str, any]:
    """Analyze which detection services are currently active"""
    analysis = {
        'labjack_detection_service': None,
        'dedicated_labjack_monitor': None,
        'status': 'unknown'
    }

    # Check if labjack_detection_service is instantiated
    try:
        from services.labjack_detection_service import _detection_service_instance
        if _detection_service_instance is not None:
            analysis['labjack_detection_service'] = {
                'active': True,
                'source_name': 'labjack',
                'location': 'services/labjack_detection_service.py:2193'
            }
    except Exception as e:
        analysis['labjack_detection_service'] = {
            'active': False,
            'error': str(e)
        }

    # Check if dedicated_labjack_monitor is active
    try:
        from services.dedicated_labjack_monitor import _monitor_instance
        if _monitor_instance is not None:
            analysis['dedicated_labjack_monitor'] = {
                'active': True,
                'source_name': 'dedicated_labjack_monitor',
                'locations': [
                    'services/dedicated_labjack_monitor.py:1365',
                    'services/dedicated_labjack_monitor.py:2099'
                ]
            }
    except Exception as e:
        analysis['dedicated_labjack_monitor'] = {
            'active': False,
            'error': str(e)
        }

    # Determine status
    labjack_active = analysis['labjack_detection_service'] and \
                     analysis['labjack_detection_service'].get('active', False)
    monitor_active = analysis['dedicated_labjack_monitor'] and \
                     analysis['dedicated_labjack_monitor'].get('active', False)

    if labjack_active and monitor_active:
        analysis['status'] = 'DUPLICATE_SERVICES_ACTIVE'
    elif labjack_active:
        analysis['status'] = 'LABJACK_SERVICE_ONLY'
    elif monitor_active:
        analysis['status'] = 'MONITOR_SERVICE_ONLY'
    else:
        analysis['status'] = 'NO_SERVICES_ACTIVE'

    return analysis


def print_report(source_data: Dict, service_data: Dict):
    """Print comprehensive verification report"""
    print("=" * 80)
    print("LABJACK DETECTION SOURCE VERIFICATION REPORT")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Service Status
    print("🔍 ACTIVE SERVICES:")
    print("-" * 80)
    print(f"Overall Status: {service_data['status']}")
    print()

    if service_data['labjack_detection_service']:
        print("LabJackDetectionService:")
        for key, value in service_data['labjack_detection_service'].items():
            print(f"  {key}: {value}")
    print()

    if service_data['dedicated_labjack_monitor']:
        print("DedicatedLabJackMonitor:")
        for key, value in service_data['dedicated_labjack_monitor'].items():
            print(f"  {key}: {value}")
    print()

    # Detection Sources
    print("📊 DETECTION SOURCES IN DATABASE:")
    print("-" * 80)
    print(f"Total Detections: {source_data['total_detections']}")
    print()

    for source_name, data in source_data['sources'].items():
        print(f"{source_name}:")
        print(f"  Count: {data['count']}")
        if data['first_detection']:
            print(f"  First: {data['first_detection'].strftime('%Y-%m-%d %H:%M:%S')}")
        if data['last_detection']:
            print(f"  Last:  {data['last_detection'].strftime('%Y-%m-%d %H:%M:%S')}")
        print()

    # Duplicate Analysis
    print("🔎 DUPLICATE DETECTION CHECK:")
    print("-" * 80)
    if source_data['duplicates']:
        print(f"⚠️  FOUND {len(source_data['duplicates'])} DUPLICATE TIMESTAMPS!")
        print()
        for dup in source_data['duplicates'][:10]:  # Show first 10
            print(f"Timestamp: {dup['timestamp'].strftime('%Y-%m-%d %H:%M:%S.%f')}")
            print(f"  Count: {dup['count']}")
            print(f"  Sources: {', '.join(dup['sources'])}")
            print()
    else:
        print("✅ No duplicate timestamps detected (last 24 hours)")
    print()

    # Recommendations
    print("💡 RECOMMENDATIONS:")
    print("-" * 80)

    if service_data['status'] == 'DUPLICATE_SERVICES_ACTIVE':
        print("🚨 CRITICAL: Both services are active!")
        print("   ACTION REQUIRED: Disable one of the services to prevent duplicates")
        print()
        print("   Option 1: Disable LabJackDetectionService")
        print("     - Comment out source='labjack' in services/labjack_detection_service.py:2193")
        print()
        print("   Option 2: Disable DedicatedLabJackMonitor")
        print("     - Comment out source='dedicated_labjack_monitor' in services/dedicated_labjack_monitor.py")

    elif service_data['status'] == 'NO_SERVICES_ACTIVE':
        print("⚠️  WARNING: No detection services are active")
        print("   This is normal if no test is currently running")

    else:
        print("✅ Configuration looks correct")
        print(f"   Active service: {service_data['status']}")

    # Source Analysis
    labjack_count = source_data['sources'].get('labjack', {}).get('count', 0)
    monitor_count = source_data['sources'].get('dedicated_labjack_monitor', {}).get('count', 0)

    if labjack_count > 0 and monitor_count > 0:
        print()
        print("⚠️  DETECTED: Both sources have written to database")
        print(f"   labjack: {labjack_count} detections")
        print(f"   dedicated_labjack_monitor: {monitor_count} detections")

        if labjack_count == monitor_count:
            print()
            print("🚨 EQUAL COUNTS = LIKELY 100% DUPLICATION")
            print("   Every detection is being written twice!")

    print()
    print("=" * 80)


def main():
    """Main verification function"""
    print("Starting LabJack detection source verification...\n")

    # Check database sources
    print("Querying database for detection sources...")
    source_data = check_detection_sources()

    if not source_data['success']:
        print("❌ Database check failed!")
        for error in source_data['errors']:
            print(f"   {error}")
        return 1

    # Analyze active services
    print("Analyzing active detection services...")
    service_data = analyze_active_services()

    # Print comprehensive report
    print()
    print_report(source_data, service_data)

    # Return exit code
    if service_data['status'] == 'DUPLICATE_SERVICES_ACTIVE':
        return 1  # Error: duplicates active
    elif len(source_data['duplicates']) > 0:
        return 2  # Warning: duplicates in database
    else:
        return 0  # Success


if __name__ == "__main__":
    sys.exit(main())
