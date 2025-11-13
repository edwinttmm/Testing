#!/usr/bin/env python3
"""Test the enhanced HIL API endpoint"""

import requests
import json
import sys
from datetime import datetime

def test_endpoint():
    """Test the corrected results endpoint"""

    base_url = "http://localhost:8000"
    session_id = "a90187aa-2237-4afe-90d5-3c8176db622f"
    endpoint = f"{base_url}/api/enhanced-hil/test-sessions/{session_id}/corrected-results"

    headers = {
        "Origin": "http://localhost:3000",
        "Accept": "application/json"
    }

    print("=" * 80)
    print("API ENDPOINT TEST")
    print("=" * 80)
    print(f"\nEndpoint: {endpoint}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Time: {datetime.now().isoformat()}\n")

    try:
        print("Making request...")
        response = requests.get(endpoint, headers=headers, timeout=10)

        print("\n" + "=" * 80)
        print("RESPONSE DETAILS")
        print("=" * 80)
        print(f"\nStatus Code: {response.status_code}")
        print(f"Reason: {response.reason}")

        print("\n" + "-" * 80)
        print("RESPONSE HEADERS")
        print("-" * 80)
        for key, value in response.headers.items():
            print(f"{key}: {value}")

        # Check CORS headers
        print("\n" + "=" * 80)
        print("CORS HEADER VERIFICATION")
        print("=" * 80)

        cors_headers = {
            'Access-Control-Allow-Origin': 'http://localhost:3000',
            'Access-Control-Allow-Credentials': 'true',
        }

        cors_ok = True
        for header, expected in cors_headers.items():
            actual = response.headers.get(header)
            if actual == expected:
                print(f"✅ {header}: {actual}")
            else:
                print(f"❌ {header}: Expected '{expected}', Got '{actual}'")
                cors_ok = False

        # Check response body
        print("\n" + "=" * 80)
        print("RESPONSE BODY")
        print("=" * 80)

        if response.status_code == 200:
            try:
                data = response.json()
                print(f"\nResponse Type: {type(data)}")

                if isinstance(data, dict):
                    # Check for required fields
                    required_fields = ['session_id', 'videos', 'aggregated']
                    print("\nRequired Fields Check:")
                    for field in required_fields:
                        if field in data:
                            print(f"✅ {field}: present")
                            if field == 'videos' and isinstance(data[field], list):
                                print(f"   - Video count: {len(data[field])}")
                                for i, video in enumerate(data[field]):
                                    print(f"   - Video {i}: {video.get('video_name', 'Unknown')}")
                        else:
                            print(f"❌ {field}: MISSING")

                    print(f"\nFull Response Preview:")
                    print(json.dumps(data, indent=2)[:1000])
                    if len(json.dumps(data, indent=2)) > 1000:
                        print("... (truncated)")
                else:
                    print(f"\nUnexpected response type: {type(data)}")
                    print(data)

                print("\n✅ REQUEST SUCCESSFUL")
                return True

            except json.JSONDecodeError as e:
                print(f"\n❌ JSON Decode Error: {e}")
                print(f"Raw Response: {response.text[:500]}")
                return False
        else:
            print(f"\n❌ REQUEST FAILED")
            print(f"Response Text: {response.text[:500]}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"\n❌ CONNECTION ERROR: Cannot connect to {base_url}")
        print("Is the backend server running?")
        return False
    except requests.exceptions.Timeout:
        print(f"\n❌ TIMEOUT: Request took longer than 10 seconds")
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_endpoint()
    print("\n" + "=" * 80)
    if success:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ TESTS FAILED")
    print("=" * 80)
    sys.exit(0 if success else 1)
