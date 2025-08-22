#!/usr/bin/env python3
"""
Complete cleanup and organization of all markdown files
Move everything into proper date-based folder structure
"""

import os
import shutil
import re
from datetime import datetime
from pathlib import Path
import subprocess

def get_file_creation_date(file_path):
    """Get file creation/modification date"""
    try:
        result = subprocess.run(['stat', '-c', '%y', file_path], capture_output=True, text=True)
        if result.returncode == 0:
            date_str = result.stdout.strip()
            date_part = date_str.split()[0]  # Get just the date part
            return date_part
    except:
        pass
    return "2025-08-22"  # Default date

def categorize_by_content(file_path):
    """Categorize file by content and name"""
    file_name = os.path.basename(file_path).lower()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(500).lower()
    except:
        content = ""
    
    # Backend files
    if any(keyword in file_name or keyword in content for keyword in [
        'backend', 'api', 'database', 'detection', 'pipeline', 'schema', 'migration'
    ]):
        return 'backend'
    
    # Frontend files
    elif any(keyword in file_name or keyword in content for keyword in [
        'frontend', 'react', 'typescript', 'ui', 'component', 'websocket', 'dashboard'
    ]):
        return 'frontend'
    
    # Database files
    elif any(keyword in file_name or keyword in content for keyword in [
        'database', 'db', 'postgres', 'migration', 'schema'
    ]):
        return 'database'
    
    # Deployment files
    elif any(keyword in file_name or keyword in content for keyword in [
        'deploy', 'docker', 'environment', 'setup'
    ]):
        return 'deployment'
    
    # Analysis/Fix files
    elif any(keyword in file_name or keyword in content for keyword in [
        'fix', 'analysis', 'summary', 'investigation', 'troubleshooting'
    ]):
        return 'fixes'
    
    # Integration files
    elif any(keyword in file_name or keyword in content for keyword in [
        'integration', 'comprehensive', 'final', 'complete'
    ]):
        return 'analysis'
    
    else:
        return 'general'

def clean_documentation_root():
    """Move all files from documentation root into proper folders"""
    
    doc_path = Path('/home/user/Testing/ai-model-validation-platform/documentation')
    
    # Get all .md files in documentation root (excluding the master summary)
    root_files = []
    for file in doc_path.glob('*.md'):
        if file.name != 'PROJECT_DOCUMENTATION_MASTER_SUMMARY.md':
            root_files.append(file)
    
    print(f"🧹 Found {len(root_files)} files to organize in documentation root")
    
    moved_count = 0
    for file_path in root_files:
        try:
            date = get_file_creation_date(file_path)
            category = categorize_by_content(file_path)
            
            # Create target directory
            target_dir = doc_path / date / category
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Handle duplicate names
            target_file = target_dir / file_path.name
            counter = 1
            original_target = target_file
            while target_file.exists():
                name_part = original_target.stem
                ext_part = original_target.suffix
                target_file = target_dir / f"{name_part}_{counter}{ext_part}"
                counter += 1
            
            # Move file
            shutil.move(str(file_path), str(target_file))
            moved_count += 1
            print(f"  ✅ Moved: {file_path.name} → {date}/{category}/")
            
        except Exception as e:
            print(f"  ❌ Error moving {file_path}: {e}")
    
    print(f"✅ Moved {moved_count} files from documentation root")
    return moved_count

def clean_testing_root():
    """Move scattered .md files from Testing root into documentation"""
    
    testing_path = Path('/home/user/Testing')
    doc_path = Path('/home/user/Testing/ai-model-validation-platform/documentation')
    
    # Find all .md files in Testing root
    scattered_files = list(testing_path.glob('*.md'))
    
    print(f"🧹 Found {len(scattered_files)} scattered files in Testing root")
    
    moved_count = 0
    for file_path in scattered_files:
        try:
            date = get_file_creation_date(file_path)
            category = categorize_by_content(file_path)
            
            # Create target directory
            target_dir = doc_path / date / category
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Handle duplicate names
            target_file = target_dir / file_path.name
            counter = 1
            original_target = target_file
            while target_file.exists():
                name_part = original_target.stem
                ext_part = original_target.suffix
                target_file = target_dir / f"{name_part}_{counter}{ext_part}"
                counter += 1
            
            # Move file
            shutil.move(str(file_path), str(target_file))
            moved_count += 1
            print(f"  ✅ Moved: {file_path.name} → documentation/{date}/{category}/")
            
        except Exception as e:
            print(f"  ❌ Error moving {file_path}: {e}")
    
    print(f"✅ Moved {moved_count} files from Testing root")
    return moved_count

def verify_organization():
    """Verify that organization is complete"""
    
    doc_path = Path('/home/user/Testing/ai-model-validation-platform/documentation')
    testing_path = Path('/home/user/Testing')
    
    # Check documentation root - should only have the master summary and organize script
    doc_root_files = [f for f in doc_path.glob('*.md') if f.name != 'PROJECT_DOCUMENTATION_MASTER_SUMMARY.md']
    doc_root_py = list(doc_path.glob('*.py'))
    
    # Check Testing root - should have no .md files
    testing_root_files = list(testing_path.glob('*.md'))
    
    print(f"\n📊 ORGANIZATION VERIFICATION:")
    print(f"Documentation root .md files (should be 0): {len(doc_root_files)}")
    print(f"Testing root .md files (should be 0): {len(testing_root_files)}")
    
    if doc_root_files:
        print("⚠️ Still found files in documentation root:")
        for f in doc_root_files:
            print(f"  - {f.name}")
    
    if testing_root_files:
        print("⚠️ Still found files in Testing root:")
        for f in testing_root_files:
            print(f"  - {f.name}")
    
    # Count organized files
    total_organized = 0
    for date_dir in doc_path.glob('2025-*'):
        if date_dir.is_dir():
            count = len(list(date_dir.glob('**/*.md')))
            total_organized += count
            print(f"  {date_dir.name}: {count} files")
    
    print(f"\n📈 Total organized files: {total_organized}")
    
    if not doc_root_files and not testing_root_files:
        print("🎉 ORGANIZATION COMPLETE!")
        return True
    else:
        print("❌ Organization incomplete")
        return False

def main():
    print("🗂️ COMPLETE DOCUMENTATION CLEANUP & ORGANIZATION")
    print("="*60)
    
    # Step 1: Clean documentation root
    print("\n📂 Step 1: Cleaning documentation root...")
    doc_moved = clean_documentation_root()
    
    # Step 2: Clean Testing root
    print("\n📂 Step 2: Cleaning Testing root...")
    testing_moved = clean_testing_root()
    
    # Step 3: Verify organization
    print("\n📂 Step 3: Verifying organization...")
    success = verify_organization()
    
    print(f"\n📊 CLEANUP SUMMARY:")
    print(f"Files moved from documentation root: {doc_moved}")
    print(f"Files moved from Testing root: {testing_moved}")
    print(f"Total files moved: {doc_moved + testing_moved}")
    
    if success:
        print("\n🎉 CLEANUP COMPLETE!")
        print("✅ All files properly organized by date and category")
        print("✅ Only PROJECT_DOCUMENTATION_MASTER_SUMMARY.md remains in root")
    else:
        print("\n⚠️ Some files may need manual cleanup")

if __name__ == "__main__":
    main()