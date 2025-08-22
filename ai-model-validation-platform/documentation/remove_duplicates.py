#!/usr/bin/env python3
"""
Remove duplicate .md files that have identical content to files already organized
"""

import os
import shutil
from pathlib import Path

def find_remaining_scattered_files():
    """Find remaining scattered files"""
    testing_path = Path('/home/user/Testing')
    scattered_files = []
    
    for root, dirs, files in os.walk(testing_path):
        if 'node_modules' in root or '/documentation/2025-' in root:
            continue
            
        for file in files:
            if file.endswith('.md') and file != 'PROJECT_DOCUMENTATION_MASTER_SUMMARY.md':
                file_path = os.path.join(root, file)
                scattered_files.append(file_path)
    
    return scattered_files

def find_organized_duplicate(scattered_file, doc_path):
    """Find if there's an organized file with same content"""
    
    try:
        with open(scattered_file, 'r', encoding='utf-8') as f:
            scattered_content = f.read().strip()
    except:
        return None
    
    # Search through organized files
    for date_dir in doc_path.glob('2025-*'):
        if date_dir.is_dir():
            for organized_file in date_dir.glob('**/*.md'):
                try:
                    with open(organized_file, 'r', encoding='utf-8') as f:
                        organized_content = f.read().strip()
                    
                    if scattered_content == organized_content:
                        return str(organized_file)
                except:
                    continue
    
    return None

def remove_duplicate_files():
    """Remove duplicate files that already exist in organized structure"""
    
    doc_path = Path('/home/user/Testing/ai-model-validation-platform/documentation')
    scattered_files = find_remaining_scattered_files()
    
    print(f"🔍 Checking {len(scattered_files)} remaining files for duplicates...")
    
    removed_count = 0
    kept_count = 0
    
    for scattered_file in scattered_files:
        organized_duplicate = find_organized_duplicate(scattered_file, doc_path)
        
        if organized_duplicate:
            # This is a duplicate - safe to remove
            try:
                os.remove(scattered_file)
                print(f"  🗑️ Removed duplicate: {os.path.basename(scattered_file)}")
                print(f"     (Same content as: {organized_duplicate.replace(str(doc_path), 'docs')})")
                removed_count += 1
            except Exception as e:
                print(f"  ❌ Error removing {scattered_file}: {e}")
        else:
            # This is unique content - keep it
            print(f"  ⚠️ Keeping unique file: {scattered_file}")
            kept_count += 1
    
    print(f"\n📊 DUPLICATE REMOVAL RESULTS:")
    print(f"Duplicate files removed: {removed_count}")
    print(f"Unique files kept: {kept_count}")
    
    return removed_count, kept_count

def final_verification():
    """Final verification of organization"""
    
    doc_path = Path('/home/user/Testing/ai-model-validation-platform/documentation')
    remaining_files = find_remaining_scattered_files()
    
    # Count organized files
    organized_count = 0
    for date_dir in doc_path.glob('2025-*'):
        if date_dir.is_dir():
            count = len(list(date_dir.glob('**/*.md')))
            organized_count += count
            print(f"  {date_dir.name}: {count} files")
    
    print(f"\n📈 FINAL ORGANIZATION STATUS:")
    print(f"Organized files: {organized_count}")
    print(f"Remaining scattered: {len(remaining_files)}")
    
    if remaining_files:
        print(f"\n⚠️ Remaining files (unique content):")
        for f in remaining_files:
            print(f"  - {f}")
        return False
    else:
        print("🎉 PERFECT! ALL FILES ORGANIZED!")
        return True

def main():
    print("🧹 REMOVING DUPLICATE MARKDOWN FILES")
    print("="*50)
    
    removed, kept = remove_duplicate_files()
    success = final_verification()
    
    if success:
        print("\n🎉 DOCUMENTATION ORGANIZATION COMPLETE!")
        print("✅ All duplicate files removed")
        print("✅ All unique files properly organized")
        print("✅ Zero scattered files remaining")
    else:
        print("\n📋 Organization mostly complete")
        print(f"✅ Removed {removed} duplicate files")
        print(f"⚠️ {kept} unique files may need manual review")

if __name__ == "__main__":
    main()