#!/usr/bin/env python3
"""
Quick Browser UI Test
Tests basic frontend functionality using curl and HTML parsing
"""

import requests
import re
from html.parser import HTMLParser

class ReactAppParser(HTMLParser):
    """Parse React app HTML to extract useful information"""
    
    def __init__(self):
        super().__init__()
        self.title = ""
        self.scripts = []
        self.stylesheets = []
        self.meta_viewport = False
        self.root_div = False
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag == "title":
            self.in_title = True
        elif tag == "script" and "src" in attrs_dict:
            self.scripts.append(attrs_dict["src"])
        elif tag == "link" and attrs_dict.get("rel") == "stylesheet":
            self.stylesheets.append(attrs_dict.get("href", ""))
        elif tag == "meta" and attrs_dict.get("name") == "viewport":
            self.meta_viewport = True
        elif tag == "div" and attrs_dict.get("id") == "root":
            self.root_div = True
    
    def handle_data(self, data):
        if hasattr(self, 'in_title') and self.in_title:
            self.title = data.strip()
    
    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

def test_react_app_structure():
    """Test React app structure and components"""
    print("🖥️ Testing React App Structure...")
    
    try:
        response = requests.get("http://localhost:3000", timeout=10)
        if response.status_code != 200:
            print(f"❌ Frontend not accessible: {response.status_code}")
            return False
        
        # Parse HTML
        parser = ReactAppParser()
        parser.feed(response.text)
        
        results = []
        
        # Check React root div
        if parser.root_div:
            results.append(("React root div", True, "Found id='root'"))
        else:
            results.append(("React root div", False, "Missing id='root'"))
        
        # Check viewport meta tag (responsive design)
        if parser.meta_viewport:
            results.append(("Viewport meta tag", True, "Responsive design setup"))
        else:
            results.append(("Viewport meta tag", False, "Missing viewport meta"))
        
        # Check for JavaScript files
        if parser.scripts:
            results.append(("JavaScript files", True, f"Found {len(parser.scripts)} scripts"))
        else:
            results.append(("JavaScript files", False, "No script files found"))
        
        # Check for CSS files
        if parser.stylesheets:
            results.append(("CSS files", True, f"Found {len(parser.stylesheets)} stylesheets"))
        else:
            results.append(("CSS files", False, "No CSS files found"))
        
        # Check page title
        if parser.title:
            results.append(("Page title", True, f"Title: '{parser.title}'"))
        else:
            results.append(("Page title", False, "No page title"))
        
        # Print results
        passed = 0
        for test, success, details in results:
            status = "✅" if success else "❌"
            print(f"  {status} {test}: {details}")
            if success:
                passed += 1
        
        success_rate = passed / len(results)
        if success_rate >= 0.8:
            print(f"✅ React app structure GOOD ({passed}/{len(results)} checks passed)")
            return True
        else:
            print(f"⚠️ React app structure PARTIAL ({passed}/{len(results)} checks passed)")
            return False
            
    except Exception as e:
        print(f"❌ Error testing React app: {e}")
        return False

def test_api_endpoints_from_frontend():
    """Test that API endpoints are accessible from frontend perspective"""
    print("\n🔌 Testing API Endpoints (Frontend Perspective)...")
    
    endpoints = [
        ("/health", "Health check"),
        ("/api/projects", "Projects API"),
        ("/api/videos", "Videos API")
    ]
    
    passed = 0
    base_url = "http://localhost:8000"
    
    for endpoint, name in endpoints:
        try:
            # Add CORS headers as if from frontend
            headers = {
                'Origin': 'http://localhost:3000',
                'Accept': 'application/json'
            }
            
            response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=5)
            
            if response.status_code == 200:
                # Check CORS headers
                cors_origin = response.headers.get('Access-Control-Allow-Origin', '')
                if '*' in cors_origin or 'localhost:3000' in cors_origin:
                    print(f"  ✅ {name}: API accessible with CORS")
                    passed += 1
                else:
                    print(f"  ⚠️ {name}: API accessible but CORS may be limited")
                    passed += 0.5
            else:
                print(f"  ❌ {name}: HTTP {response.status_code}")
        
        except Exception as e:
            print(f"  ❌ {name}: Error - {str(e)[:50]}...")
    
    if passed >= len(endpoints) * 0.8:
        print(f"✅ API endpoints accessible from frontend ({passed}/{len(endpoints)})")
        return True
    else:
        print(f"⚠️ Some API issues from frontend perspective ({passed}/{len(endpoints)})")
        return False

def test_responsive_indicators():
    """Test for responsive design indicators in HTML"""
    print("\n📱 Testing Responsive Design Indicators...")
    
    try:
        response = requests.get("http://localhost:3000", timeout=10)
        content = response.text.lower()
        
        responsive_patterns = [
            (r'name=["\']viewport["\']', "Viewport meta tag"),
            (r'@media', "CSS media queries"),
            (r'responsive', "Responsive classes/text"),
            (r'mobile', "Mobile-related content"),
            (r'flex', "Flexbox layout"),
            (r'grid', "CSS Grid layout")
        ]
        
        found_patterns = 0
        for pattern, description in responsive_patterns:
            if re.search(pattern, content):
                print(f"  ✅ {description}: Found")
                found_patterns += 1
            else:
                print(f"  ❌ {description}: Not found")
        
        if found_patterns >= 2:
            print(f"✅ Responsive design indicators present ({found_patterns}/6)")
            return True
        else:
            print(f"⚠️ Limited responsive design indicators ({found_patterns}/6)")
            return False
            
    except Exception as e:
        print(f"❌ Error checking responsive indicators: {e}")
        return False

def main():
    """Run all UI tests"""
    print("🎨 Quick Browser UI Testing")
    print("=" * 50)
    
    tests = [
        ("React App Structure", test_react_app_structure),
        ("API Frontend Integration", test_api_endpoints_from_frontend), 
        ("Responsive Design", test_responsive_indicators)
    ]
    
    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 50)
    print("📊 UI TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ NEEDS ATTENTION"
        print(f"{test_name:25} : {status}")
    
    print(f"\nUI Tests: {passed}/{total} passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 UI TESTS ALL PASSED!")
        return 0
    elif passed >= total * 0.7:
        print("✅ UI MOSTLY FUNCTIONAL")
        return 0
    else:
        print("⚠️ UI NEEDS IMPROVEMENTS")
        return 1

if __name__ == "__main__":
    exit(main())