#!/usr/bin/env python3
"""
FINAL COMPLETE CLEANUP - Move ALL remaining .md files to proper documentation structure
This addresses the 347+ scattered files that were missed in the previous cleanup
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
            date_part = date_str.split()[0]
            return date_part
    except:
        pass
    return "2025-08-22"

def categorize_by_content(file_path):
    """Smart categorization by content and location"""
    file_name = os.path.basename(file_path).lower()
    dir_path = str(file_path).lower()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(1000).lower()
    except:
        content = ""
    
    # Backend files
    if any(keyword in file_name or keyword in content or keyword in dir_path for keyword in [
        'backend', 'api', 'database', 'detection', 'pipeline', 'schema', 'migration', 
        'postgres', 'sql', 'yolo', 'ml', 'model'
    ]):
        return 'backend'
    
    # Frontend files  
    elif any(keyword in file_name or keyword in content or keyword in dir_path for keyword in [
        'frontend', 'react', 'typescript', 'ui', 'component', 'websocket', 'dashboard',
        'error-boundary', 'keyboard-navigation'
    ]):
        return 'frontend'
    
    # Testing files
    elif any(keyword in file_name or keyword in content or keyword in dir_path for keyword in [
        'test', 'spec', 'validation', 'mingw64', 'comprehensive-suite', 'e2e', 'tdd'
    ]):
        return 'fixes'  # Put tests in fixes for analysis
    
    # Database files
    elif any(keyword in file_name or keyword in content or keyword in dir_path for keyword in [
        'database', 'db', 'postgres', 'migration', 'schema'
    ]):
        return 'database'
    
    # Deployment files
    elif any(keyword in file_name or keyword in content or keyword in dir_path for keyword in [
        'deploy', 'docker', 'environment', 'setup'
    ]):
        return 'deployment'
    
    # Analysis/Fix files
    elif any(keyword in file_name or keyword in content or keyword in dir_path for keyword in [
        'fix', 'analysis', 'summary', 'investigation', 'troubleshooting', 'comprehensive',
        'final', 'complete', 'integration', 'results'
    ]):
        return 'fixes'
    
    # Memory/Hive-mind files
    elif any(keyword in dir_path for keyword in ['memory', 'hive-mind', 'agents']):
        return 'general'
    
    # Documentation files
    elif any(keyword in dir_path for keyword in ['docs', 'documentation']):
        return 'analysis'
    
    else:
        return 'general'

def find_all_scattered_files():
    """Find ALL .md files not in the organized documentation structure"""
    
    testing_path = Path('/home/user/Testing')
    doc_path = Path('/home/user/Testing/ai-model-validation-platform/documentation')
    
    # Find all .md files in Testing directory
    all_md_files = []
    
    for root, dirs, files in os.walk(testing_path):
        # Skip node_modules and the organized documentation
        if 'node_modules' in root:
            continue
        if '/documentation/2025-' in root:
            continue
            
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                # Skip the master summary
                if file != 'PROJECT_DOCUMENTATION_MASTER_SUMMARY.md':
                    all_md_files.append(file_path)
    
    return all_md_files

def move_all_scattered_files():
    """Move ALL scattered files to proper documentation structure"""
    
    scattered_files = find_all_scattered_files()
    doc_path = Path('/home/user/Testing/ai-model-validation-platform/documentation')
    
    print(f"🧹 Found {len(scattered_files)} scattered files to organize")
    
    moved_count = 0
    skipped_count = 0
    error_count = 0
    
    for file_path in scattered_files:
        try:
            # Get file info
            date = get_file_creation_date(file_path)
            category = categorize_by_content(file_path)
            
            # Create target directory
            target_dir = doc_path / date / category
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Handle duplicate names
            file_name = os.path.basename(file_path)
            target_file = target_dir / file_name
            counter = 1
            original_target = target_file
            
            while target_file.exists():
                # Check if it's the same file (same content)
                try:
                    with open(file_path, 'r') as f1, open(target_file, 'r') as f2:
                        if f1.read() == f2.read():
                            print(f"  🔄 Duplicate: {file_name} (same content, skipping)")
                            skipped_count += 1
                            break
                except:
                    pass
                
                # Create new name for different file
                name_part = original_target.stem
                ext_part = original_target.suffix
                target_file = target_dir / f"{name_part}_{counter}{ext_part}"
                counter += 1
            else:
                # Move the file
                shutil.move(str(file_path), str(target_file))
                moved_count += 1
                print(f"  ✅ Moved: {file_name} → {date}/{category}/")
                
        except Exception as e:
            print(f"  ❌ Error with {file_path}: {e}")
            error_count += 1
    
    print(f"\n📊 FINAL CLEANUP RESULTS:")
    print(f"Files moved: {moved_count}")
    print(f"Duplicates skipped: {skipped_count}")
    print(f"Errors: {error_count}")
    print(f"Total processed: {len(scattered_files)}")
    
    return moved_count

def final_verification():
    """Final verification that ALL files are organized"""
    
    testing_path = Path('/home/user/Testing')
    doc_path = Path('/home/user/Testing/ai-model-validation-platform/documentation')
    
    # Check for remaining scattered files
    remaining_files = find_all_scattered_files()
    
    # Count organized files
    organized_count = 0
    for date_dir in doc_path.glob('2025-*'):
        if date_dir.is_dir():
            count = len(list(date_dir.glob('**/*.md')))
            organized_count += count
            print(f"  {date_dir.name}: {count} files")
    
    print(f"\n📈 FINAL STATUS:")
    print(f"Organized files: {organized_count}")
    print(f"Remaining scattered: {len(remaining_files)}")
    
    if remaining_files:
        print(f"\n⚠️ Still found {len(remaining_files)} scattered files:")
        for f in remaining_files[:10]:  # Show first 10
            print(f"  - {f}")
        if len(remaining_files) > 10:
            print(f"  ... and {len(remaining_files) - 10} more")
        return False
    else:
        print("🎉 ALL FILES SUCCESSFULLY ORGANIZED!")
        return True

def main():
    print("🧹 FINAL COMPLETE DOCUMENTATION CLEANUP")
    print("="*70)
    print("This will move ALL remaining scattered .md files")
    print("Addressing the 347+ files missed in previous cleanup")
    print("="*70)
    
    # Move all scattered files
    moved_count = move_all_scattered_files()
    
    # Final verification
    success = final_verification()
    
    if success:
        print("\n🎉 CLEANUP FINALLY COMPLETE!")
        print("✅ All .md files are now properly organized")
        print("✅ Zero scattered files remaining")
    else:
        print("\n⚠️ Some files may still need manual attention")

if __name__ == "__main__":
    main()