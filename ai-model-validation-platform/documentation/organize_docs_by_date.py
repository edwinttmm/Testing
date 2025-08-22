#!/usr/bin/env python3
"""
Organize all markdown files in Testing directory by date into proper documentation structure
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
            # Parse date like "2025-08-22 10:39:17.637330182 +0000"
            date_part = date_str.split()[0]  # Get just the date part
            return date_part
    except:
        pass
    return None

def categorize_by_content(file_path):
    """Categorize file by content and name"""
    file_name = os.path.basename(file_path).lower()
    
    # Read first few lines to understand content
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
        'frontend', 'react', 'typescript', 'ui', 'component', 'websocket'
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

def organize_documentation():
    """Organize all markdown files by date and category"""
    
    base_path = Path('/home/user/Testing')
    doc_path = Path('/home/user/Testing/ai-model-validation-platform/documentation')
    
    # Find all markdown files
    md_files = []
    for root, dirs, files in os.walk(base_path):
        # Skip node_modules
        if 'node_modules' in root:
            continue
        for file in files:
            if file.endswith('.md'):
                md_files.append(os.path.join(root, file))
    
    print(f"Found {len(md_files)} markdown files")
    
    # Organize by date and category
    organized_files = {}
    
    for file_path in md_files:
        date = get_file_creation_date(file_path)
        if not date:
            date = '2025-08-22'  # Default date
        
        category = categorize_by_content(file_path)
        
        if date not in organized_files:
            organized_files[date] = {}
        if category not in organized_files[date]:
            organized_files[date][category] = []
        
        organized_files[date][category].append(file_path)
    
    # Create directory structure and move files
    moved_count = 0
    
    for date, categories in organized_files.items():
        print(f"\n📅 Processing date: {date}")
        
        for category, files in categories.items():
            print(f"  📂 Category: {category} ({len(files)} files)")
            
            # Create target directory
            target_dir = doc_path / date / category
            target_dir.mkdir(parents=True, exist_ok=True)
            
            for file_path in files:
                try:
                    file_name = os.path.basename(file_path)
                    target_file = target_dir / file_name
                    
                    # Handle duplicate names
                    counter = 1
                    original_target = target_file
                    while target_file.exists():
                        name_part = original_target.stem
                        ext_part = original_target.suffix
                        target_file = target_dir / f"{name_part}_{counter}{ext_part}"
                        counter += 1
                    
                    # Copy file (don't move to preserve originals)
                    shutil.copy2(file_path, target_file)
                    moved_count += 1
                    print(f"    ✅ Copied: {file_name}")
                    
                except Exception as e:
                    print(f"    ❌ Error copying {file_path}: {e}")
    
    print(f"\n🎉 Successfully organized {moved_count} files")
    return organized_files

def generate_updated_master_summary(organized_files):
    """Generate updated master summary with new organization"""
    
    summary_content = f"""# AI Model Validation Platform - Master Documentation Summary

## Project Documentation Timeline & Organization
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC  
**Total Documents**: {sum(len(files) for date_files in organized_files.values() for files in date_files.values())} markdown files

---

## 📁 **New Date-Based Organization Structure**

```
documentation/
├── 2025-08-16/          # Initial Setup & Foundation
│   ├── backend/         # Backend services and APIs
│   ├── frontend/        # UI components and React code
│   ├── database/        # Database schemas and migrations
│   ├── deployment/      # Docker and environment setup
│   ├── fixes/           # Bug fixes and patches
│   └── analysis/        # Technical analysis and reports
├── 2025-08-17/          # Integration Phase
├── 2025-08-18/          # WebSocket & TypeScript
├── 2025-08-19/          # Deployment & Docker
├── 2025-08-20/          # Environment Configuration
├── 2025-08-21/          # Detection System Improvements
└── 2025-08-22/          # Latest Updates & Schema Fixes
```

---

## 📊 **Documentation by Date**

"""
    
    for date in sorted(organized_files.keys(), reverse=True):
        categories = organized_files[date]
        total_files = sum(len(files) for files in categories.values())
        
        summary_content += f"""### {date} ({total_files} documents)

"""
        
        for category in sorted(categories.keys()):
            files = categories[category]
            summary_content += f"""**{category.title()}** ({len(files)} files)
"""
            for file_path in sorted(files):
                file_name = os.path.basename(file_path)
                summary_content += f"""- `{file_name}`
"""
            summary_content += "\n"
    
    summary_content += f"""---

## 🎯 **Quick Navigation by Category**

### Backend Development
- Detection pipeline services
- API endpoint implementations  
- Database schema and migrations
- Performance optimizations

### Frontend Development
- React component implementations
- TypeScript configuration fixes
- UI/UX improvements
- WebSocket eliminations

### Database & Schema
- PostgreSQL table definitions
- Migration scripts and fixes
- Schema validation tools
- Performance indexes

### Deployment & DevOps
- Docker container configurations
- Environment setup guides
- CI/CD pipeline definitions
- Troubleshooting guides

### Analysis & Fixes
- Bug investigation reports
- Performance analysis
- Integration summaries
- Comprehensive fix documentation

---

## 📋 **Development Timeline Summary**

### Phase 1 (Aug 16): Foundation
- Initial project setup and architecture
- Basic API and database structure
- Error diagnostics and analysis

### Phase 2 (Aug 17-18): Integration
- Frontend-backend integration
- WebSocket implementation
- TypeScript migration

### Phase 3 (Aug 19): Deployment
- Docker containerization
- Environment configuration
- Database migrations

### Phase 4 (Aug 20-21): Optimization
- Performance improvements
- Detection system enhancements
- UI/UX refinements

### Phase 5 (Aug 22): Schema Fixes
- Database schema corrections
- Detection pipeline validation
- Final system integration

---

## 🚀 **Current Project Status**

### ✅ Completed Systems
- YOLO v11 detection pipeline
- React frontend with TypeScript
- PostgreSQL database with migrations
- Docker containerization
- API endpoint implementations
- Error handling and logging

### 🔧 Recent Fixes (Aug 22)
- Detection events schema validation
- Video ID mapping corrections
- Database column additions
- Annotation system integration

### 📈 System Metrics
- **Detection Accuracy**: 24/24 pedestrian detections processed
- **Video Processing**: 121 frames, 24fps, 5.04s duration
- **Database Tables**: Complete schema with all required columns
- **API Endpoints**: Full CRUD operations for annotations

---

**Documentation Organization**: ✅ **COMPLETE**  
**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
    
    # Write updated summary
    summary_path = Path('/home/user/Testing/ai-model-validation-platform/documentation/PROJECT_DOCUMENTATION_MASTER_SUMMARY.md')
    with open(summary_path, 'w') as f:
        f.write(summary_content)
    
    print(f"✅ Updated master summary: {summary_path}")

def main():
    print("🗂️ ORGANIZING ALL MARKDOWN DOCUMENTATION")
    print("="*60)
    
    organized_files = organize_documentation()
    generate_updated_master_summary(organized_files)
    
    print("\n📊 ORGANIZATION COMPLETE!")
    print("- All .md files organized by date and category")
    print("- Master summary updated with new structure")
    print("- Documentation ready for easy navigation")

if __name__ == "__main__":
    main()