import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Alert,
  Divider,
} from '@mui/material';
import AccessibleFormField from '../components/ui/AccessibleFormField';

interface FormData {
  projectName: string;
  description: string;
  cameraModel: string;
  cameraView: string;
  signalType: string;
  email: string;
  accuracy: number;
}

interface FormErrors {
  projectName?: string;
  description?: string;
  cameraModel?: string;
  cameraView?: string;
  signalType?: string;
  email?: string;
  accuracy?: string;
}

const FormValidationTest: React.FC = () => {
  const [formData, setFormData] = useState<FormData>({
    projectName: '',
    description: '',
    cameraModel: '',
    cameraView: '',
    signalType: '',
    email: '',
    accuracy: 0,
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isValid, setIsValid] = useState(false);

  const cameraOptions = [
    { value: '', label: 'Select camera model' },
    { value: 'axis-m1065', label: 'Axis M1065' },
    { value: 'hikvision-ds', label: 'Hikvision DS Series' },
    { value: 'bosch-flexidome', label: 'Bosch FlexiDome' },
  ];

  const viewOptions = [
    { value: '', label: 'Select camera view' },
    { value: 'front-facing', label: 'Front-facing' },
    { value: 'side-view', label: 'Side view' },
    { value: 'aerial', label: 'Aerial view' },
    { value: 'mixed-angle', label: 'Mixed angle' },
  ];

  const signalOptions = [
    { value: '', label: 'Select signal type' },
    { value: 'pedestrian', label: 'Pedestrian Signal' },
    { value: 'bicycle', label: 'Bicycle Signal' },
    { value: 'mixed', label: 'Mixed VRU Signal' },
  ];

  // Comprehensive validation function
  const validateForm = (): FormErrors => {
    const newErrors: FormErrors = {};

    // Project name validation
    if (!formData.projectName.trim()) {
      newErrors.projectName = 'Project name is required';
    } else if (formData.projectName.length < 3) {
      newErrors.projectName = 'Project name must be at least 3 characters';
    } else if (formData.projectName.length > 50) {
      newErrors.projectName = 'Project name cannot exceed 50 characters';
    }

    // Description validation
    if (!formData.description.trim()) {
      newErrors.description = 'Project description is required';
    } else if (formData.description.length < 10) {
      newErrors.description = 'Description must be at least 10 characters';
    } else if (formData.description.length > 500) {
      newErrors.description = 'Description cannot exceed 500 characters';
    }

    // Camera model validation
    if (!formData.cameraModel) {
      newErrors.cameraModel = 'Camera model selection is required';
    }

    // Camera view validation
    if (!formData.cameraView) {
      newErrors.cameraView = 'Camera view selection is required';
    }

    // Signal type validation
    if (!formData.signalType) {
      newErrors.signalType = 'Signal type selection is required';
    }

    // Email validation
    if (!formData.email.trim()) {
      newErrors.email = 'Email address is required';
    } else {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(formData.email)) {
        newErrors.email = 'Please enter a valid email address';
      }
    }

    // Accuracy validation
    if (formData.accuracy < 0) {
      newErrors.accuracy = 'Accuracy cannot be negative';
    } else if (formData.accuracy > 100) {
      newErrors.accuracy = 'Accuracy cannot exceed 100%';
    }

    return newErrors;
  };

  // Real-time field validation
  const validateField = (fieldName: keyof FormData) => {
    const fieldErrors = validateForm();
    setErrors(prev => ({
      ...prev,
      [fieldName]: fieldErrors[fieldName],
    }));
  };

  // Handle form data changes
  const handleFieldChange = (field: keyof FormData) => (value: string | number) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));
    
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({
        ...prev,
        [field]: undefined,
      }));
    }
  };

  // Handle form submission
  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setIsSubmitted(true);
    
    const formErrors = validateForm();
    setErrors(formErrors);
    
    const hasErrors = Object.keys(formErrors).length > 0;
    setIsValid(!hasErrors);
    
    if (!hasErrors) {
      // Form is valid - would normally submit to API
      console.log('Form submitted successfully:', formData);
    } else {
      // Focus on first error field
      const firstErrorField = Object.keys(formErrors)[0];
      const element = document.getElementById(firstErrorField);
      element?.focus();
    }
  };

  // Reset form
  const handleReset = () => {
    setFormData({
      projectName: '',
      description: '',
      cameraModel: '',
      cameraView: '',
      signalType: '',
      email: '',
      accuracy: 0,
    });
    setErrors({});
    setIsSubmitted(false);
    setIsValid(false);
  };

  const errorCount = Object.keys(errors).length;

  return (
    <Box sx={{ maxWidth: 800, mx: 'auto', p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Form Validation Testing
      </Typography>
      
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        This form tests comprehensive validation patterns, error handling, and accessibility features.
        Try submitting without filling fields, entering invalid data, and using keyboard navigation.
      </Typography>

      {isSubmitted && (
        <Alert 
          severity={isValid ? 'success' : 'error'} 
          sx={{ mb: 3 }}
          role="alert"
          aria-live="polite"
        >
          {isValid 
            ? 'Form submitted successfully! All validation passed.' 
            : `Form submission failed. Please correct ${errorCount} error${errorCount > 1 ? 's' : ''} below.`
          }
        </Alert>
      )}

      <Card>
        <CardContent>
          <form onSubmit={handleSubmit} noValidate>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              
              <Typography variant="h6" component="h2">
                Project Information
              </Typography>
              
              <AccessibleFormField
                id="projectName"
                label="Project Name"
                type="text"
                value={formData.projectName}
                onChange={handleFieldChange('projectName')}
                onBlur={() => validateField('projectName')}
                error={errors.projectName}
                required
                maxLength={50}
                helperText="Enter a descriptive name for your AI model validation project"
                data-testid="project-name-input"
              />

              <AccessibleFormField
                id="description"
                label="Project Description"
                type="textarea"
                value={formData.description}
                onChange={handleFieldChange('description')}
                onBlur={() => validateField('description')}
                error={errors.description}
                required
                multiline
                rows={4}
                maxLength={500}
                helperText="Provide details about the validation objectives and scope"
                data-testid="description-input"
              />

              <Divider />
              
              <Typography variant="h6" component="h2">
                Camera Configuration
              </Typography>

              <AccessibleFormField
                id="cameraModel"
                label="Camera Model"
                type="select"
                value={formData.cameraModel}
                onChange={handleFieldChange('cameraModel')}
                onBlur={() => validateField('cameraModel')}
                error={errors.cameraModel}
                required
                options={cameraOptions}
                helperText="Select the camera model used for data collection"
                data-testid="camera-model-select"
              />

              <AccessibleFormField
                id="cameraView"
                label="Camera View"
                type="select"
                value={formData.cameraView}
                onChange={handleFieldChange('cameraView')}
                onBlur={() => validateField('cameraView')}
                error={errors.cameraView}
                required
                options={viewOptions}
                helperText="Select the camera angle and positioning"
                data-testid="camera-view-select"
              />

              <AccessibleFormField
                id="signalType"
                label="Signal Type"
                type="select"
                value={formData.signalType}
                onChange={handleFieldChange('signalType')}
                onBlur={() => validateField('signalType')}
                error={errors.signalType}
                required
                options={signalOptions}
                helperText="Select the type of VRU signal being detected"
                data-testid="signal-type-select"
              />

              <Divider />
              
              <Typography variant="h6" component="h2">
                Additional Settings
              </Typography>

              <AccessibleFormField
                id="email"
                label="Contact Email"
                type="email"
                value={formData.email}
                onChange={handleFieldChange('email')}
                onBlur={() => validateField('email')}
                error={errors.email}
                required
                autoComplete="email"
                helperText="Email for project notifications and updates"
                data-testid="email-input"
              />

              <AccessibleFormField
                id="accuracy"
                label="Target Accuracy (%)"
                type="number"
                value={formData.accuracy}
                onChange={handleFieldChange('accuracy')}
                onBlur={() => validateField('accuracy')}
                error={errors.accuracy}
                min={0}
                max={100}
                helperText="Set the target accuracy threshold for model validation (0-100%)"
                data-testid="accuracy-input"
              />

              <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 3 }}>
                <Button
                  type="button"
                  variant="outlined"
                  onClick={handleReset}
                  data-testid="reset-button"
                >
                  Reset Form
                </Button>
                <Button
                  type="submit"
                  variant="contained"
                  data-testid="submit-button"
                >
                  Create Project
                </Button>
              </Box>
            </Box>
          </form>
        </CardContent>
      </Card>

      {/* Testing Instructions */}
      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Testing Instructions
          </Typography>
          
          <Typography variant="body2" component="div" sx={{ mb: 2 }}>
            <strong>Validation Testing:</strong>
          </Typography>
          <Typography variant="body2" component="ul" sx={{ ml: 2, mb: 2 }}>
            <li>Try submitting the form without filling any fields</li>
            <li>Enter text shorter than minimum requirements</li>
            <li>Enter text longer than maximum requirements</li>
            <li>Enter invalid email formats</li>
            <li>Enter negative or greater than 100% accuracy values</li>
          </Typography>
          
          <Typography variant="body2" component="div" sx={{ mb: 2 }}>
            <strong>Keyboard Testing:</strong>
          </Typography>
          <Typography variant="body2" component="ul" sx={{ ml: 2, mb: 2 }}>
            <li>Navigate through all fields using Tab key</li>
            <li>Use Shift+Tab to navigate backwards</li>
            <li>Use Enter to submit the form</li>
            <li>Use arrow keys in select dropdowns</li>
            <li>Verify focus indicators are visible</li>
          </Typography>
          
          <Typography variant="body2" component="div" sx={{ mb: 2 }}>
            <strong>Accessibility Testing:</strong>
          </Typography>
          <Typography variant="body2" component="ul" sx={{ ml: 2 }}>
            <li>Check that error messages are announced by screen readers</li>
            <li>Verify all form fields have proper labels</li>
            <li>Confirm required fields are marked appropriately</li>
            <li>Test that form validation occurs on blur and submit</li>
            <li>Verify focus moves to first error field on failed submission</li>
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
};

export default FormValidationTest;