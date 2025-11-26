#!/bin/bash
# Add missing pytest imports to all test files that use pytest decorators
# but don't import pytest

find tests/ -name "test_*.py" -type f | while read file; do
    # Check if file uses pytest but doesn't import it
    if grep -q "@pytest\." "$file" && ! grep -q "^import pytest" "$file"; then
        echo "Adding pytest import to: $file"
        # Create temp file with import added after first line (usually docstring or shebang)
        awk 'NR==1{print; print "import pytest"} NR>1' "$file" > "$file.tmp" && mv "$file.tmp" "$file"
    fi
done

echo "Done adding pytest imports"
