#!/usr/bin/env python3
"""
Fix Pydantic v2 Regex Compatibility - Replace 'regex=' with 'pattern='
==================================================================

This script fixes Pydantic v1 to v2 migration issues by replacing deprecated
'regex=' parameters with 'pattern=' in Field() definitions.
"""

import os
import re
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_pydantic_regex_in_file(file_path):
    """Fix Pydantic regex issues in a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Replace regex= with pattern= in Field() calls
        # Pattern: Field(..., regex="...", ...)
        content = re.sub(
            r'\bField\(([^)]*?)regex=',
            r'Field(\1pattern=',
            content,
            flags=re.MULTILINE | re.DOTALL
        )
        
        # Pattern: regex="..." in Query() calls  
        content = re.sub(
            r'\bQuery\(([^)]*?)regex=',
            r'Query(\1pattern=',
            content,
            flags=re.MULTILINE | re.DOTALL
        )
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            changes = len(re.findall(r'\bpattern=', content)) - len(re.findall(r'\bpattern=', original_content))
            logger.info(f"✅ Fixed {changes} regex parameters in {file_path}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"❌ Error fixing {file_path}: {e}")
        return False

def main():
    """Main function to fix Pydantic regex issues."""
    logger.info("🚀 Starting Pydantic v2 Regex Compatibility Fix")
    
    # Files and directories to check
    backend_dir = Path(".")
    python_files = []
    
    # Find relevant Python files
    for pattern in ["*.py", "src/**/*.py", "routes/**/*.py", "api/**/*.py"]:
        python_files.extend(backend_dir.glob(pattern))
    
    # Remove duplicates and filter
    unique_files = list(set(python_files))
    source_files = [f for f in unique_files if "lib/python" not in str(f) and "venv" not in str(f)]
    
    logger.info(f"📋 Found {len(source_files)} Python files to check")
    
    fixed_count = 0
    
    for file_path in source_files:
        if fix_pydantic_regex_in_file(file_path):
            fixed_count += 1
    
    logger.info(f"🎉 Fix completed! Updated {fixed_count} files")
    
    if fixed_count > 0:
        logger.info("\n" + "="*60)
        logger.info("📋 Next Steps:")
        logger.info("1. Test backend startup: python3 main.py")
        logger.info("2. Verify Pydantic v2 compatibility")
        logger.info("3. Check for any remaining import errors")
        logger.info("="*60)

if __name__ == "__main__":
    main()