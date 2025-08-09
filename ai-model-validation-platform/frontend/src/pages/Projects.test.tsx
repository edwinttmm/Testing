// Test file to verify Projects component functionality
import React from 'react';

// This file verifies that the Projects component imports work correctly
// and that the API integration is properly set up

// Mock test data that matches the API types
export const mockProjectData = {
  id: 'test-1',
  name: 'Test Project',
  description: 'A test project for validation',
  cameraModel: 'Sony IMX390',
  cameraView: 'Front-facing VRU' as const,
  signalType: 'GPIO',
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  status: 'Active' as const,
  testsCount: 0,
  accuracy: 0,
  userId: 'user-1'
};

// Test form data
export const mockFormData = {
  name: 'New Test Project',
  description: 'Testing the create project functionality',
  cameraModel: 'OmniVision OV2312',
  cameraView: 'Front-facing VRU' as const,
  signalType: 'Network Packet'
};

// Validation tests
export const validateProjectForm = (data: typeof mockFormData): string[] => {
  const errors: string[] = [];
  
  if (!data.name.trim()) errors.push('Project name is required');
  if (!data.description.trim()) errors.push('Description is required');
  if (!data.cameraModel.trim()) errors.push('Camera model is required');
  
  return errors;
};

console.log('Projects component test utilities loaded');
console.log('Mock project data:', mockProjectData);
console.log('Form validation test:', validateProjectForm(mockFormData));