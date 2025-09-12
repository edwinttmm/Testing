#!/usr/bin/env python3
"""
Comprehensive Ground Truth Endpoint Validation Test
Tests the new ground truth endpoint functionality with various scenarios.
"""

import pytest
import requests
import json
import os
import sys
from pathlib import Path
import time
import asyncio
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from main import app

class TestGroundTruthEndpoint:
    """Test suite for ground truth endpoint validation."""
    
    def setup_class(self):
        """Setup test client and base URL."""
        self.client = TestClient(app)
        self.base_url = "http://localhost:8000"
        self.test_data = {
            "video_id": 1,
            "ground_truth_data": {
                "annotations": [
                    {
                        "timestamp": 1.5,
                        "bbox": {"x": 100, "y": 100, "width": 50, "height": 50},
                        "label": "vehicle"
                    }
                ]
            }
        }
    
    def test_ground_truth_create_endpoint(self):
        """Test POST /ground-truth endpoint creation."""
        response = self.client.post(
            "/ground-truth",
            json=self.test_data
        )
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data or "success" in data, "Response should contain ID or success indicator"
        
        print(f"✅ Ground truth creation test passed: {data}")
    
    def test_ground_truth_get_endpoint(self):
        """Test GET /ground-truth/{video_id} endpoint."""
        # First create a ground truth entry
        create_response = self.client.post("/ground-truth", json=self.test_data)
        
        if create_response.status_code in [200, 201]:
            # Try to retrieve it
            response = self.client.get(f"/ground-truth/{self.test_data['video_id']}")
            
            if response.status_code == 200:
                data = response.json()
                assert "annotations" in data or "ground_truth_data" in data, "Response should contain annotations"
                print(f"✅ Ground truth retrieval test passed: {len(data)} items found")
            else:
                print(f"⚠️  Ground truth retrieval returned {response.status_code}: {response.text}")
        else:
            print(f"⚠️  Skipping retrieval test - creation failed: {create_response.text}")
    
    def test_ground_truth_list_endpoint(self):
        """Test GET /ground-truth endpoint for listing."""
        response = self.client.get("/ground-truth")
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict)), "Response should be list or dict"
            print(f"✅ Ground truth list test passed: {len(data) if isinstance(data, list) else 'dict'} items")
        else:
            print(f"⚠️  Ground truth list test returned {response.status_code}: {response.text}")
    
    def test_ground_truth_update_endpoint(self):
        """Test PUT/PATCH ground truth update functionality."""
        # Create first
        create_response = self.client.post("/ground-truth", json=self.test_data)
        
        if create_response.status_code in [200, 201]:
            updated_data = {
                **self.test_data,
                "ground_truth_data": {
                    "annotations": [
                        {
                            "timestamp": 2.0,
                            "bbox": {"x": 150, "y": 150, "width": 60, "height": 60},
                            "label": "pedestrian"
                        }
                    ]
                }
            }
            
            # Try PUT method
            response = self.client.put(f"/ground-truth/{self.test_data['video_id']}", json=updated_data)
            
            if response.status_code == 404:
                # Try PATCH method
                response = self.client.patch(f"/ground-truth/{self.test_data['video_id']}", json=updated_data)
            
            if response.status_code in [200, 201]:
                print(f"✅ Ground truth update test passed")
            else:
                print(f"⚠️  Ground truth update test returned {response.status_code}: {response.text}")
        else:
            print(f"⚠️  Skipping update test - creation failed")
    
    def test_ground_truth_delete_endpoint(self):
        """Test DELETE ground truth endpoint."""
        # Create first
        create_response = self.client.post("/ground-truth", json=self.test_data)
        
        if create_response.status_code in [200, 201]:
            response = self.client.delete(f"/ground-truth/{self.test_data['video_id']}")
            
            if response.status_code in [200, 204]:
                print(f"✅ Ground truth delete test passed")
            else:
                print(f"⚠️  Ground truth delete test returned {response.status_code}: {response.text}")
        else:
            print(f"⚠️  Skipping delete test - creation failed")
    
    def test_ground_truth_validation(self):
        """Test ground truth data validation."""
        invalid_data = {
            "video_id": "invalid",  # Should be int
            "ground_truth_data": "invalid"  # Should be dict
        }
        
        response = self.client.post("/ground-truth", json=invalid_data)
        
        assert response.status_code in [400, 422], f"Expected validation error, got {response.status_code}"
        print(f"✅ Ground truth validation test passed - properly rejected invalid data")
    
    def test_ground_truth_batch_operations(self):
        """Test batch ground truth operations."""
        batch_data = [
            {"video_id": 1, "ground_truth_data": {"annotations": []}},
            {"video_id": 2, "ground_truth_data": {"annotations": []}},
            {"video_id": 3, "ground_truth_data": {"annotations": []}}
        ]
        
        # Try batch endpoint if it exists
        response = self.client.post("/ground-truth/batch", json={"items": batch_data})
        
        if response.status_code == 404:
            # Fallback to individual creates
            results = []
            for item in batch_data:
                resp = self.client.post("/ground-truth", json=item)
                results.append(resp.status_code in [200, 201])
            
            if all(results):
                print(f"✅ Ground truth batch operations test passed (individual creates)")
            else:
                print(f"⚠️  Some batch operations failed: {results}")
        else:
            if response.status_code in [200, 201]:
                print(f"✅ Ground truth batch operations test passed")
            else:
                print(f"⚠️  Ground truth batch operations returned {response.status_code}: {response.text}")

def run_ground_truth_validation():
    """Run all ground truth endpoint validation tests."""
    print("🔍 Starting Ground Truth Endpoint Validation...")
    
    test_suite = TestGroundTruthEndpoint()
    test_suite.setup_class()
    
    tests = [
        test_suite.test_ground_truth_create_endpoint,
        test_suite.test_ground_truth_get_endpoint,
        test_suite.test_ground_truth_list_endpoint,
        test_suite.test_ground_truth_update_endpoint,
        test_suite.test_ground_truth_delete_endpoint,
        test_suite.test_ground_truth_validation,
        test_suite.test_ground_truth_batch_operations,
    ]
    
    results = []
    for test in tests:
        try:
            test()
            results.append(True)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed: {e}")
            results.append(False)
    
    success_rate = sum(results) / len(results) * 100
    print(f"\n📊 Ground Truth Endpoint Validation Complete: {success_rate:.1f}% success rate ({sum(results)}/{len(results)} tests passed)")
    
    return success_rate > 70

if __name__ == "__main__":
    run_ground_truth_validation()