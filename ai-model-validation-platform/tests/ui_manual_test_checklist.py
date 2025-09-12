#!/usr/bin/env python3
"""
Manual UI/UX Testing Checklist Generator
========================================

Generates comprehensive manual testing checklists for UI/UX validation.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any

class ManualTestChecklist:
    """Generates comprehensive manual testing checklists"""
    
    def __init__(self):
        self.test_categories = self._define_test_categories()
        
    def _define_test_categories(self) -> Dict[str, List[Dict]]:
        """Define comprehensive test categories"""
        return {
            "navigation": [
                {
                    "id": "nav-001",
                    "title": "Dashboard Navigation",
                    "description": "Navigate to dashboard and verify all widgets load",
                    "steps": [
                        "Click on Dashboard in sidebar",
                        "Verify page loads without errors", 
                        "Check all stats cards display data",
                        "Verify charts render correctly"
                    ],
                    "expected": "Dashboard loads with all widgets showing data",
                    "priority": "high"
                },
                {
                    "id": "nav-002", 
                    "title": "Projects Page Navigation",
                    "description": "Navigate to projects page and test functionality",
                    "steps": [
                        "Click on Projects in sidebar",
                        "Verify projects list loads",
                        "Check Create Project button is available",
                        "Test project card interactions"
                    ],
                    "expected": "Projects page loads with project list and controls",
                    "priority": "high"
                },
                {
                    "id": "nav-003",
                    "title": "Ground Truth Navigation", 
                    "description": "Test ground truth page navigation",
                    "steps": [
                        "Navigate to Ground Truth page",
                        "Verify video library loads",
                        "Check annotation tools are available",
                        "Test video player functionality"
                    ],
                    "expected": "Ground truth page loads with video library and tools",
                    "priority": "medium"
                },
                {
                    "id": "nav-004",
                    "title": "Settings Navigation",
                    "description": "Navigate to settings and verify configuration options",
                    "steps": [
                        "Click on Settings in sidebar",
                        "Verify settings categories load",
                        "Check configuration options are editable",
                        "Test save functionality"
                    ],
                    "expected": "Settings page loads with editable configurations",
                    "priority": "low"
                }
            ],
            
            "forms_interaction": [
                {
                    "id": "form-001",
                    "title": "Project Creation Form",
                    "description": "Test project creation form validation and submission",
                    "steps": [
                        "Click 'Create New Project' button",
                        "Fill out project name field",
                        "Select camera type from dropdown",
                        "Choose signal type",
                        "Click Create button",
                        "Verify project appears in list"
                    ],
                    "expected": "New project created successfully with form validation",
                    "priority": "high"
                },
                {
                    "id": "form-002",
                    "title": "Video Upload Form",
                    "description": "Test video file upload functionality", 
                    "steps": [
                        "Navigate to video upload area",
                        "Click upload button or drag-drop zone",
                        "Select a valid video file (.mp4)",
                        "Verify upload progress indicator",
                        "Check uploaded video appears in library"
                    ],
                    "expected": "Video uploads successfully with progress feedback",
                    "priority": "high"
                },
                {
                    "id": "form-003",
                    "title": "Form Validation",
                    "description": "Test form validation for required fields",
                    "steps": [
                        "Try to submit forms with empty required fields",
                        "Check for validation error messages",
                        "Verify field highlighting for errors",
                        "Test invalid data format inputs"
                    ],
                    "expected": "Clear validation messages appear for invalid inputs",
                    "priority": "medium"
                }
            ],
            
            "data_display": [
                {
                    "id": "data-001",
                    "title": "Dashboard Statistics",
                    "description": "Verify dashboard stats display correctly",
                    "steps": [
                        "Open dashboard page",
                        "Check project count accuracy", 
                        "Verify video count matches actual videos",
                        "Check test session statistics",
                        "Verify accuracy percentage display"
                    ],
                    "expected": "All statistics display accurate, current data",
                    "priority": "high"
                },
                {
                    "id": "data-002",
                    "title": "Project List Display",
                    "description": "Test projects list data display",
                    "steps": [
                        "Navigate to Projects page",
                        "Verify all projects are listed",
                        "Check project metadata displays correctly",
                        "Test sorting functionality",
                        "Verify search/filter works"
                    ],
                    "expected": "Projects display with correct metadata and controls",
                    "priority": "medium"
                },
                {
                    "id": "data-003",
                    "title": "Video Library Display",
                    "description": "Test video library data presentation",
                    "steps": [
                        "Go to video library section",
                        "Verify videos display with thumbnails",
                        "Check video metadata (duration, size, etc.)",
                        "Test video filtering options",
                        "Verify pagination if applicable"
                    ],
                    "expected": "Videos display with correct metadata and controls",
                    "priority": "medium"
                },
                {
                    "id": "data-004",
                    "title": "Test Results Display",
                    "description": "Verify test results and analytics display",
                    "steps": [
                        "Navigate to Results page",
                        "Check test session results display",
                        "Verify charts and graphs render",
                        "Test result filtering and sorting",
                        "Check export functionality"
                    ],
                    "expected": "Test results display with charts and export options",
                    "priority": "medium"
                }
            ],
            
            "file_operations": [
                {
                    "id": "file-001",
                    "title": "Video Upload",
                    "description": "Test video file upload end-to-end",
                    "steps": [
                        "Prepare test video files (various formats)",
                        "Use drag-and-drop upload",
                        "Monitor upload progress",
                        "Verify file validation (reject invalid files)",
                        "Check uploaded files appear in library"
                    ],
                    "expected": "Videos upload successfully with progress tracking",
                    "priority": "high"
                },
                {
                    "id": "file-002",
                    "title": "Annotation Export",
                    "description": "Test annotation data export functionality",
                    "steps": [
                        "Create some annotations on videos",
                        "Navigate to export options",
                        "Select export format (JSON/CSV/etc.)",
                        "Download exported file",
                        "Verify exported data completeness"
                    ],
                    "expected": "Annotations export successfully in selected format",
                    "priority": "medium"
                },
                {
                    "id": "file-003",
                    "title": "File Management",
                    "description": "Test file deletion and management",
                    "steps": [
                        "Select a video file to delete",
                        "Click delete button",
                        "Confirm deletion in dialog",
                        "Verify file removed from library",
                        "Check database consistency"
                    ],
                    "expected": "Files can be deleted safely with confirmation",
                    "priority": "medium"
                }
            ],
            
            "error_handling": [
                {
                    "id": "error-001",
                    "title": "Network Error Handling",
                    "description": "Test behavior when backend is unavailable",
                    "steps": [
                        "Disconnect backend/network",
                        "Try to perform actions in frontend",
                        "Check error messages displayed",
                        "Verify retry mechanisms",
                        "Test recovery when connection restored"
                    ],
                    "expected": "Graceful error handling with clear user feedback",
                    "priority": "high"
                },
                {
                    "id": "error-002",
                    "title": "Invalid File Upload",
                    "description": "Test error handling for invalid files",
                    "steps": [
                        "Try uploading non-video files",
                        "Upload extremely large files",
                        "Upload corrupted video files",
                        "Check error messages are clear",
                        "Verify system remains stable"
                    ],
                    "expected": "Clear error messages for invalid uploads",
                    "priority": "medium"
                },
                {
                    "id": "error-003",
                    "title": "Browser Error Recovery",
                    "description": "Test recovery from JavaScript errors",
                    "steps": [
                        "Intentionally cause JS errors (if possible)",
                        "Check error boundary behavior",
                        "Verify app doesn't completely crash",
                        "Test refresh/retry options",
                        "Check error reporting"
                    ],
                    "expected": "App recovers gracefully from errors",
                    "priority": "medium"
                }
            ],
            
            "responsive_design": [
                {
                    "id": "resp-001",
                    "title": "Mobile Layout",
                    "description": "Test UI on mobile viewport",
                    "steps": [
                        "Resize browser to mobile dimensions (375px)",
                        "Check sidebar collapses properly",
                        "Verify navigation works on mobile",
                        "Test touch interactions",
                        "Check text readability"
                    ],
                    "expected": "UI adapts properly to mobile viewport",
                    "priority": "medium"
                },
                {
                    "id": "resp-002", 
                    "title": "Tablet Layout",
                    "description": "Test UI on tablet viewport",
                    "steps": [
                        "Resize browser to tablet dimensions (768px)",
                        "Check layout adapts appropriately",
                        "Test navigation and interactions",
                        "Verify content remains accessible",
                        "Check video player responsiveness"
                    ],
                    "expected": "UI works well on tablet-sized screens",
                    "priority": "low"
                },
                {
                    "id": "resp-003",
                    "title": "Desktop Layout Scaling",
                    "description": "Test UI at various desktop sizes",
                    "steps": [
                        "Test at 1920x1080 resolution",
                        "Test at 1366x768 resolution", 
                        "Check ultra-wide monitor compatibility",
                        "Verify content doesn't get too stretched",
                        "Test window resizing behavior"
                    ],
                    "expected": "UI scales properly across desktop resolutions",
                    "priority": "low"
                }
            ],
            
            "accessibility": [
                {
                    "id": "a11y-001",
                    "title": "Keyboard Navigation",
                    "description": "Test complete keyboard navigation",
                    "steps": [
                        "Use only Tab/Shift+Tab to navigate",
                        "Verify all interactive elements are reachable",
                        "Check focus indicators are visible",
                        "Test Enter/Space for button activation",
                        "Verify skip links work properly"
                    ],
                    "expected": "All functionality accessible via keyboard",
                    "priority": "high"
                },
                {
                    "id": "a11y-002",
                    "title": "Screen Reader Compatibility",
                    "description": "Test with screen reader software",
                    "steps": [
                        "Enable screen reader (NVDA/JAWS/VoiceOver)",
                        "Navigate through main pages",
                        "Check form label announcements",
                        "Verify heading structure",
                        "Test image alt text"
                    ],
                    "expected": "Content is properly announced by screen readers",
                    "priority": "medium"
                },
                {
                    "id": "a11y-003",
                    "title": "Color Contrast",
                    "description": "Verify color contrast meets WCAG standards",
                    "steps": [
                        "Use color contrast analyzer tool",
                        "Check text against backgrounds",
                        "Verify interactive element states",
                        "Test error message visibility",
                        "Check chart/graph accessibility"
                    ],
                    "expected": "All colors meet WCAG AA contrast requirements",
                    "priority": "medium"
                }
            ],
            
            "performance": [
                {
                    "id": "perf-001",
                    "title": "Initial Page Load",
                    "description": "Measure initial page load performance",
                    "steps": [
                        "Clear browser cache",
                        "Navigate to application",
                        "Measure time to interactive",
                        "Check for loading indicators",
                        "Verify progressive loading"
                    ],
                    "expected": "Page loads within 3 seconds on fast connection",
                    "priority": "medium"
                },
                {
                    "id": "perf-002",
                    "title": "Large File Handling",
                    "description": "Test performance with large video files",
                    "steps": [
                        "Upload large video file (>50MB)",
                        "Monitor memory usage",
                        "Check upload progress feedback",
                        "Verify browser doesn't freeze",
                        "Test video playback performance"
                    ],
                    "expected": "Large files handled efficiently without freezing",
                    "priority": "medium"
                },
                {
                    "id": "perf-003",
                    "title": "Multiple Tab Performance",
                    "description": "Test performance with multiple browser tabs",
                    "steps": [
                        "Open application in multiple tabs",
                        "Perform actions in different tabs",
                        "Monitor memory usage",
                        "Check for memory leaks",
                        "Verify WebSocket connections"
                    ],
                    "expected": "Application performs well across multiple tabs",
                    "priority": "low"
                }
            ]
        }
    
    def generate_test_session(self, categories: List[str] = None) -> Dict[str, Any]:
        """Generate a test session with selected categories"""
        if categories is None:
            categories = list(self.test_categories.keys())
        
        test_session = {
            "session_info": {
                "id": f"ui-test-{int(datetime.now().timestamp())}",
                "created_at": datetime.now().isoformat(),
                "tester": "UI/UX Integration Specialist",
                "categories": categories,
                "total_tests": 0
            },
            "test_categories": {}
        }
        
        total_tests = 0
        for category in categories:
            if category in self.test_categories:
                test_session["test_categories"][category] = {
                    "name": category.replace("_", " ").title(),
                    "tests": self.test_categories[category],
                    "count": len(self.test_categories[category])
                }
                total_tests += len(self.test_categories[category])
        
        test_session["session_info"]["total_tests"] = total_tests
        return test_session
    
    def generate_checklist_html(self, test_session: Dict[str, Any]) -> str:
        """Generate HTML checklist for manual testing"""
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UI/UX Manual Testing Checklist</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 30px; }}
        .category {{ margin-bottom: 30px; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }}
        .category-header {{ background: #e3f2fd; padding: 15px; font-weight: bold; font-size: 1.2em; }}
        .test-item {{ padding: 20px; border-bottom: 1px solid #eee; }}
        .test-item:last-child {{ border-bottom: none; }}
        .test-header {{ display: flex; justify-content: between; align-items: center; margin-bottom: 10px; }}
        .test-id {{ background: #666; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; }}
        .priority {{ padding: 2px 8px; border-radius: 4px; font-size: 0.8em; color: white; }}
        .priority.high {{ background: #d32f2f; }}
        .priority.medium {{ background: #f57c00; }}
        .priority.low {{ background: #388e3c; }}
        .steps {{ margin: 10px 0; }}
        .steps li {{ margin: 5px 0; }}
        .checkbox-container {{ display: flex; align-items: center; margin-top: 15px; }}
        .checkbox-container input {{ margin-right: 10px; transform: scale(1.2); }}
        .notes {{ width: 100%; margin-top: 10px; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }}
        .summary {{ background: #f9f9f9; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
        @media print {{ body {{ font-size: 12px; }} .notes {{ min-height: 30px; }} }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 UI/UX Manual Testing Checklist</h1>
        <div class="summary">
            <strong>Session ID:</strong> {test_session['session_info']['id']}<br>
            <strong>Created:</strong> {test_session['session_info']['created_at']}<br>
            <strong>Total Tests:</strong> {test_session['session_info']['total_tests']}<br>
            <strong>Categories:</strong> {', '.join(test_session['session_info']['categories'])}
        </div>
        <p><strong>Instructions:</strong> For each test, follow the steps and check the box when complete. 
        Add notes about any issues found or observations.</p>
    </div>
"""
        
        for category_key, category_data in test_session["test_categories"].items():
            html += f"""
    <div class="category">
        <div class="category-header">
            📋 {category_data['name']} ({category_data['count']} tests)
        </div>
"""
            
            for test in category_data["tests"]:
                priority_class = test.get('priority', 'medium')
                html += f"""
        <div class="test-item">
            <div class="test-header">
                <div>
                    <span class="test-id">{test['id']}</span>
                    <span class="priority {priority_class}">{priority_class.upper()}</span>
                </div>
            </div>
            <h3>{test['title']}</h3>
            <p><strong>Description:</strong> {test['description']}</p>
            <div class="steps">
                <strong>Test Steps:</strong>
                <ol>
"""
                for step in test['steps']:
                    html += f"<li>{step}</li>"
                
                html += f"""
                </ol>
            </div>
            <p><strong>Expected Result:</strong> {test['expected']}</p>
            
            <div class="checkbox-container">
                <input type="checkbox" id="{test['id']}-pass">
                <label for="{test['id']}-pass">✅ Test Passed</label>
            </div>
            <div class="checkbox-container">
                <input type="checkbox" id="{test['id']}-fail">
                <label for="{test['id']}-fail">❌ Test Failed</label>
            </div>
            <div class="checkbox-container">
                <input type="checkbox" id="{test['id']}-skip">
                <label for="{test['id']}-skip">⏭️ Test Skipped</label>
            </div>
            
            <textarea class="notes" placeholder="Notes, observations, or issues found..." rows="3"></textarea>
        </div>
"""
            
            html += "</div>"
        
        html += """
    <div class="summary" style="margin-top: 40px;">
        <h3>📊 Test Summary</h3>
        <p>Complete this section after finishing all tests:</p>
        <div>
            <strong>Tests Passed:</strong> _____ / """ + str(test_session['session_info']['total_tests']) + """<br>
            <strong>Tests Failed:</strong> _____<br>
            <strong>Tests Skipped:</strong> _____<br>
            <strong>Overall Success Rate:</strong> _____%
        </div>
        <div style="margin-top: 15px;">
            <strong>Key Issues Found:</strong><br>
            <textarea class="notes" rows="5" placeholder="List the most important issues that need to be addressed..."></textarea>
        </div>
        <div style="margin-top: 15px;">
            <strong>Recommendations:</strong><br>
            <textarea class="notes" rows="5" placeholder="Recommendations for UI/UX improvements..."></textarea>
        </div>
    </div>
    
    <script>
        // Auto-save to localStorage
        document.addEventListener('change', function(e) {
            if (e.target.type === 'checkbox' || e.target.tagName === 'TEXTAREA') {
                const sessionId = '""" + test_session['session_info']['id'] + """';
                const key = `ui-test-${sessionId}`;
                const data = JSON.parse(localStorage.getItem(key) || '{}');
                
                if (e.target.type === 'checkbox') {
                    data[e.target.id] = e.target.checked;
                } else {
                    data[e.target.className + '-' + Math.random()] = e.target.value;
                }
                
                localStorage.setItem(key, JSON.stringify(data));
            }
        });
        
        // Restore from localStorage
        window.addEventListener('load', function() {
            const sessionId = '""" + test_session['session_info']['id'] + """';
            const key = `ui-test-${sessionId}`;
            const data = JSON.parse(localStorage.getItem(key) || '{}');
            
            Object.keys(data).forEach(key => {
                const element = document.getElementById(key);
                if (element && element.type === 'checkbox') {
                    element.checked = data[key];
                }
            });
        });
    </script>
</body>
</html>
        """
        
        return html
    
    def save_checklist(self, test_session: Dict[str, Any], output_dir: str = "/home/rigade/Testing/ai-model-validation-platform/tests") -> str:
        """Save test checklist to files"""
        os.makedirs(output_dir, exist_ok=True)
        
        session_id = test_session['session_info']['id']
        
        # Save JSON version
        json_path = os.path.join(output_dir, f"{session_id}.json")
        with open(json_path, 'w') as f:
            json.dump(test_session, f, indent=2)
        
        # Save HTML checklist
        html_path = os.path.join(output_dir, f"{session_id}_checklist.html")
        html_content = self.generate_checklist_html(test_session)
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        return html_path

def main():
    """Generate comprehensive UI testing checklist"""
    print("🎯 Generating Manual UI/UX Testing Checklist")
    
    checklist = ManualTestChecklist()
    
    # Generate comprehensive test session
    test_session = checklist.generate_test_session()
    
    # Save checklist
    html_path = checklist.save_checklist(test_session)
    
    print(f"✅ Generated UI/UX Manual Testing Checklist:")
    print(f"   📄 HTML Checklist: {html_path}")
    print(f"   📊 Total Tests: {test_session['session_info']['total_tests']}")
    print(f"   📋 Categories: {', '.join(test_session['session_info']['categories'])}")
    print(f"\n🎯 Open the HTML file in your browser to start manual testing!")

if __name__ == "__main__":
    main()