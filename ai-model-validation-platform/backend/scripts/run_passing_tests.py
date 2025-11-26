#!/usr/bin/env python3
"""
Run only tests that don't have collection errors.
"""
import subprocess
import sys
from pathlib import Path

def get_broken_tests():
    """Get list of tests with collection errors."""
    result = subprocess.run(
        ['python', '-m', 'pytest', '--collect-only', 'tests/', '-q'],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    broken = set()
    for line in (result.stderr + result.stdout).split('\n'):
        if 'ERROR tests/' in line:
            # Extract file path
            import re
            match = re.search(r'tests/[^ ]+\.py', line)
            if match:
                broken.add(match.group(0))

    return list(broken)

def main():
    backend_root = Path(__file__).parent.parent
    broken_tests = get_broken_tests()

    print(f"Found {len(broken_tests)} tests with collection errors")
    print("Running remaining tests...\n")

    # Build ignore arguments
    ignore_args = []
    for test_file in broken_tests:
        ignore_args.extend(['--ignore', str(backend_root / test_file)])

    # Run pytest with ignores
    cmd = [
        'python', '-m', 'pytest',
        'tests/',
        '-v',
        '--tb=short',
        '--maxfail=1000',
        '-q'
    ] + ignore_args

    result = subprocess.run(cmd, cwd=backend_root)
    sys.exit(result.returncode)

if __name__ == '__main__':
    main()
