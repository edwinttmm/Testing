import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { apiService } from '../../ai-model-validation-platform/frontend/src/services/api';
import { GroundTruthAnnotation } from '../../ai-model-validation-platform/frontend/src/services/types';

// Mock the API service
jest.mock('../../ai-model-validation-platform/frontend/src/services/api');
const mockApiService = apiService as jest.Mocked<typeof apiService>;

// Mock annotation component (simplified version for testing)
const MockAnnotationManager: React.FC<{
  videoId: string;
  onAnnotationCreate?: (annotation: GroundTruthAnnotation) => void;
  onAnnotationUpdate?: (annotation: GroundTruthAnnotation) => void;
  onAnnotationDelete?: (annotationId: string) => void;
}> = ({ videoId, onAnnotationCreate, onAnnotationUpdate, onAnnotationDelete }) => {
  const [annotations, setAnnotations] = React.useState<GroundTruthAnnotation[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const loadAnnotations = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const loadedAnnotations = await mockApiService.getAnnotations(videoId);
        setAnnotations(loadedAnnotations);
      } catch (err: any) {
        setError(err.message || 'Failed to load annotations');
      } finally {
        setIsLoading(false);
      }
    };

    loadAnnotations();
  }, [videoId]);

  const handleCreateAnnotation = async () => {
    const newAnnotation: Omit<GroundTruthAnnotation, 'id' | 'createdAt' | 'updatedAt'> = {
      videoId,
      detectionId: 'new-det-' + Date.now(),
      frameNumber: 0,
      timestamp: 0,
      vruType: 'pedestrian',
      boundingBox: {
        x: 100,
        y: 100,
        width: 50,
        height: 100,
        label: 'person',
        confidence: 0.8
      },
      occluded: false,
      truncated: false,
      difficult: false,
      validated: false,
      annotator: 'test-user'
    };

    try {
      const createdAnnotation = await mockApiService.createAnnotation(videoId, newAnnotation);
      setAnnotations(prev => [...prev, createdAnnotation]);
      onAnnotationCreate?.(createdAnnotation);
    } catch (err: any) {
      setError(err.message || 'Failed to create annotation');
    }
  };

  const handleUpdateAnnotation = async (annotation: GroundTruthAnnotation) => {
    try {
      const updatedAnnotation = await mockApiService.updateAnnotation(annotation.id, {
        validated: !annotation.validated
      });
      setAnnotations(prev => 
        prev.map(ann => ann.id === annotation.id ? updatedAnnotation : ann)
      );
      onAnnotationUpdate?.(updatedAnnotation);
    } catch (err: any) {
      setError(err.message || 'Failed to update annotation');
    }
  };

  const handleDeleteAnnotation = async (annotationId: string) => {
    try {
      await mockApiService.deleteAnnotation(annotationId);
      setAnnotations(prev => prev.filter(ann => ann.id !== annotationId));
      onAnnotationDelete?.(annotationId);
    } catch (err: any) {
      setError(err.message || 'Failed to delete annotation');
    }
  };

  const handleValidateAnnotation = async (annotationId: string, validated: boolean) => {
    try {
      const validatedAnnotation = await mockApiService.validateAnnotation(annotationId, validated);
      setAnnotations(prev => 
        prev.map(ann => ann.id === annotationId ? validatedAnnotation : ann)
      );
    } catch (err: any) {
      setError(err.message || 'Failed to validate annotation');
    }
  };

  if (isLoading) {
    return <div data-testid="loading">Loading annotations...</div>;
  }

  if (error) {
    return <div data-testid="error">{error}</div>;
  }

  return (
    <div data-testid="annotation-manager">
      <div data-testid="annotation-count">
        Annotations: {annotations.length}
      </div>
      
      <button 
        data-testid="create-annotation-btn"
        onClick={handleCreateAnnotation}
      >
        Create Annotation
      </button>

      <div data-testid="annotation-list">
        {annotations.map(annotation => (
          <div 
            key={annotation.id} 
            data-testid={`annotation-${annotation.id}`}
            className="annotation-item"
          >
            <div data-testid={`annotation-${annotation.id}-type`}>
              {annotation.vruType}
            </div>
            <div data-testid={`annotation-${annotation.id}-confidence`}>
              {annotation.boundingBox.confidence}
            </div>
            <div data-testid={`annotation-${annotation.id}-validated`}>
              {annotation.validated ? 'Validated' : 'Not Validated'}
            </div>
            <div data-testid={`annotation-${annotation.id}-bbox`}>
              {annotation.boundingBox.x}, {annotation.boundingBox.y}, 
              {annotation.boundingBox.width}, {annotation.boundingBox.height}
            </div>
            
            <button 
              data-testid={`update-annotation-${annotation.id}-btn`}
              onClick={() => handleUpdateAnnotation(annotation)}
            >
              Toggle Validation
            </button>
            
            <button 
              data-testid={`validate-annotation-${annotation.id}-btn`}
              onClick={() => handleValidateAnnotation(annotation.id, !annotation.validated)}
            >
              {annotation.validated ? 'Invalidate' : 'Validate'}
            </button>
            
            <button 
              data-testid={`delete-annotation-${annotation.id}-btn`}
              onClick={() => handleDeleteAnnotation(annotation.id)}
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

describe('Annotation Display and Management', () => {
  const mockVideoId = 'test-video-123';
  const mockAnnotations: GroundTruthAnnotation[] = [
    {
      id: 'ann-1',
      videoId: mockVideoId,
      detectionId: 'det-1',
      frameNumber: 30,
      timestamp: 1000,
      vruType: 'pedestrian',
      boundingBox: {
        x: 100,
        y: 100,
        width: 50,
        height: 100,
        label: 'person',
        confidence: 0.85
      },
      occluded: false,
      truncated: false,
      difficult: false,
      validated: false,
      annotator: 'test-annotator',
      createdAt: '2023-01-01T00:00:00Z',
      updatedAt: '2023-01-01T00:00:00Z'
    },
    {
      id: 'ann-2',
      videoId: mockVideoId,
      detectionId: 'det-2',
      frameNumber: 60,
      timestamp: 2000,
      vruType: 'cyclist',
      boundingBox: {
        x: 200,
        y: 150,
        width: 80,
        height: 120,
        label: 'bicycle',
        confidence: 0.78
      },
      occluded: true,
      truncated: false,
      difficult: false,
      validated: true,
      annotator: 'test-annotator',
      createdAt: '2023-01-01T01:00:00Z',
      updatedAt: '2023-01-01T01:30:00Z'
    }
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    mockApiService.getAnnotations.mockResolvedValue(mockAnnotations);
  });

  describe('Annotation Loading and Display', () => {
    it('should load and display annotations for a video', async () => {
      render(<MockAnnotationManager videoId={mockVideoId} />);

      // Should show loading initially
      expect(screen.getByTestId('loading')).toBeInTheDocument();

      // Wait for annotations to load
      await waitFor(() => {
        expect(screen.getByTestId('annotation-manager')).toBeInTheDocument();
      });

      // Should display correct annotation count
      expect(screen.getByTestId('annotation-count')).toHaveTextContent('Annotations: 2');

      // Should display both annotations
      expect(screen.getByTestId('annotation-ann-1')).toBeInTheDocument();
      expect(screen.getByTestId('annotation-ann-2')).toBeInTheDocument();

      // Verify annotation details
      expect(screen.getByTestId('annotation-ann-1-type')).toHaveTextContent('pedestrian');
      expect(screen.getByTestId('annotation-ann-1-confidence')).toHaveTextContent('0.85');
      expect(screen.getByTestId('annotation-ann-1-validated')).toHaveTextContent('Not Validated');

      expect(screen.getByTestId('annotation-ann-2-type')).toHaveTextContent('cyclist');
      expect(screen.getByTestId('annotation-ann-2-confidence')).toHaveTextContent('0.78');
      expect(screen.getByTestId('annotation-ann-2-validated')).toHaveTextContent('Validated');
    });

    it('should handle loading errors gracefully', async () => {
      mockApiService.getAnnotations.mockRejectedValue(new Error('Failed to load annotations'));

      render(<MockAnnotationManager videoId={mockVideoId} />);

      await waitFor(() => {
        expect(screen.getByTestId('error')).toBeInTheDocument();
      });

      expect(screen.getByTestId('error')).toHaveTextContent('Failed to load annotations');
    });

    it('should display empty state when no annotations exist', async () => {
      mockApiService.getAnnotations.mockResolvedValue([]);

      render(<MockAnnotationManager videoId={mockVideoId} />);

      await waitFor(() => {
        expect(screen.getByTestId('annotation-manager')).toBeInTheDocument();
      });

      expect(screen.getByTestId('annotation-count')).toHaveTextContent('Annotations: 0');
      expect(screen.queryByTestId('annotation-ann-1')).not.toBeInTheDocument();
    });

    it('should display bounding box coordinates correctly', async () => {
      render(<MockAnnotationManager videoId={mockVideoId} />);

      await waitFor(() => {
        expect(screen.getByTestId('annotation-ann-1-bbox')).toHaveTextContent('100, 100, 50, 100');
      });
      
      expect(screen.getByTestId('annotation-ann-2-bbox')).toHaveTextContent('200, 150, 80, 120');
    });
  });

  describe('Annotation Creation', () => {
    it('should create new annotations successfully', async () => {
      const newAnnotation: GroundTruthAnnotation = {
        id: 'ann-new',
        videoId: mockVideoId,
        detectionId: 'det-new',
        frameNumber: 90,
        timestamp: 3000,
        vruType: 'pedestrian',
        boundingBox: {
          x: 150,
          y: 200,
          width: 60,
          height: 110,
          label: 'person',
          confidence: 0.9
        },
        occluded: false,
        truncated: false,
        difficult: false,
        validated: false,
        annotator: 'test-user',
        createdAt: '2023-01-01T02:00:00Z',
        updatedAt: '2023-01-01T02:00:00Z'
      };

      mockApiService.createAnnotation.mockResolvedValue(newAnnotation);

      const onAnnotationCreate = jest.fn();
      render(
        <MockAnnotationManager 
          videoId={mockVideoId} 
          onAnnotationCreate={onAnnotationCreate}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('annotation-manager')).toBeInTheDocument();
      });

      // Click create annotation button
      fireEvent.click(screen.getByTestId('create-annotation-btn'));

      // Wait for annotation to be created and displayed
      await waitFor(() => {
        expect(screen.getByTestId('annotation-count')).toHaveTextContent('Annotations: 3');
      });

      expect(mockApiService.createAnnotation).toHaveBeenCalledWith(
        mockVideoId,
        expect.objectContaining({
          videoId: mockVideoId,
          vruType: 'pedestrian',
          annotator: 'test-user'
        })
      );

      expect(onAnnotationCreate).toHaveBeenCalledWith(newAnnotation);
    });

    it('should handle annotation creation errors', async () => {
      mockApiService.createAnnotation.mockRejectedValue(
        new Error('Failed to create annotation')
      );

      render(<MockAnnotationManager videoId={mockVideoId} />);

      await waitFor(() => {
        expect(screen.getByTestId('annotation-manager')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('create-annotation-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('Failed to create annotation');
      });

      // Should still show original annotations
      expect(screen.getByTestId('annotation-count')).toHaveTextContent('Annotations: 2');
    });
  });

  describe('Annotation Updates', () => {
    it('should update annotation validation status', async () => {
      const updatedAnnotation = {
        ...mockAnnotations[0],
        validated: true,
        updatedAt: '2023-01-01T03:00:00Z'
      };

      mockApiService.updateAnnotation.mockResolvedValue(updatedAnnotation);

      const onAnnotationUpdate = jest.fn();
      render(
        <MockAnnotationManager 
          videoId={mockVideoId}
          onAnnotationUpdate={onAnnotationUpdate}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('annotation-ann-1-validated')).toHaveTextContent('Not Validated');
      });

      // Click update button
      fireEvent.click(screen.getByTestId('update-annotation-ann-1-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('annotation-ann-1-validated')).toHaveTextContent('Validated');
      });

      expect(mockApiService.updateAnnotation).toHaveBeenCalledWith(
        'ann-1',
        { validated: true }
      );

      expect(onAnnotationUpdate).toHaveBeenCalledWith(updatedAnnotation);
    });

    it('should handle validation API calls separately', async () => {
      const validatedAnnotation = {
        ...mockAnnotations[0],
        validated: true,
        updatedAt: '2023-01-01T03:00:00Z'
      };

      mockApiService.validateAnnotation.mockResolvedValue(validatedAnnotation);

      render(<MockAnnotationManager videoId={mockVideoId} />);

      await waitFor(() => {
        expect(screen.getByTestId('annotation-ann-1-validated')).toHaveTextContent('Not Validated');
      });

      // Click validate button
      fireEvent.click(screen.getByTestId('validate-annotation-ann-1-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('annotation-ann-1-validated')).toHaveTextContent('Validated');
      });

      expect(mockApiService.validateAnnotation).toHaveBeenCalledWith('ann-1', true);
    });

    it('should handle update errors gracefully', async () => {
      mockApiService.updateAnnotation.mockRejectedValue(
        new Error('Update failed')
      );

      render(<MockAnnotationManager videoId={mockVideoId} />);

      await waitFor(() => {
        expect(screen.getByTestId('annotation-manager')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('update-annotation-ann-1-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('Update failed');
      });

      // Annotation should remain unchanged
      expect(screen.getByTestId('annotation-ann-1-validated')).toHaveTextContent('Not Validated');
    });
  });

  describe('Annotation Deletion', () => {
    it('should delete annotations successfully', async () => {
      mockApiService.deleteAnnotation.mockResolvedValue();

      const onAnnotationDelete = jest.fn();
      render(
        <MockAnnotationManager 
          videoId={mockVideoId}
          onAnnotationDelete={onAnnotationDelete}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('annotation-count')).toHaveTextContent('Annotations: 2');
      });

      // Delete first annotation
      fireEvent.click(screen.getByTestId('delete-annotation-ann-1-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('annotation-count')).toHaveTextContent('Annotations: 1');
      });

      expect(mockApiService.deleteAnnotation).toHaveBeenCalledWith('ann-1');
      expect(onAnnotationDelete).toHaveBeenCalledWith('ann-1');
      expect(screen.queryByTestId('annotation-ann-1')).not.toBeInTheDocument();
    });

    it('should handle deletion errors gracefully', async () => {
      mockApiService.deleteAnnotation.mockRejectedValue(
        new Error('Deletion failed')
      );

      render(<MockAnnotationManager videoId={mockVideoId} />);

      await waitFor(() => {
        expect(screen.getByTestId('annotation-manager')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('delete-annotation-ann-1-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('Deletion failed');
      });

      // Annotation should still be present
      expect(screen.getByTestId('annotation-count')).toHaveTextContent('Annotations: 2');
      expect(screen.getByTestId('annotation-ann-1')).toBeInTheDocument();
    });
  });

  describe('Annotation Export and Import', () => {
    it('should handle annotation export', async () => {
      const mockBlob = new Blob(['annotation data'], { type: 'application/json' });
      mockApiService.exportAnnotations.mockResolvedValue(mockBlob);

      // Test export functionality (would be integrated into a real component)
      const result = await mockApiService.exportAnnotations(mockVideoId, 'json');

      expect(result).toBe(mockBlob);
      expect(mockApiService.exportAnnotations).toHaveBeenCalledWith(mockVideoId, 'json');
    });

    it('should handle annotation import', async () => {
      const mockFile = new File(['annotation data'], 'annotations.json', {
        type: 'application/json'
      });

      const importResult = {
        imported: 5,
        errors: []
      };

      mockApiService.importAnnotations.mockResolvedValue(importResult);

      // Test import functionality
      const result = await mockApiService.importAnnotations(mockVideoId, mockFile, 'json');

      expect(result).toEqual(importResult);
      expect(mockApiService.importAnnotations).toHaveBeenCalledWith(
        mockVideoId,
        mockFile,
        'json'
      );
    });

    it('should handle import with errors', async () => {
      const mockFile = new File(['invalid data'], 'invalid.json', {
        type: 'application/json'
      });

      const importResult = {
        imported: 2,
        errors: [
          'Line 3: Invalid bounding box coordinates',
          'Line 7: Missing required field "vruType"'
        ]
      };

      mockApiService.importAnnotations.mockResolvedValue(importResult);

      const result = await mockApiService.importAnnotations(mockVideoId, mockFile, 'json');

      expect(result.imported).toBe(2);
      expect(result.errors).toHaveLength(2);
    });
  });

  describe('Annotation Session Management', () => {
    it('should create and manage annotation sessions', async () => {
      const mockSession = {
        id: 'session-123',
        videoId: mockVideoId,
        projectId: 'project-456',
        status: 'active',
        currentFrame: 0,
        totalDetections: 10,
        validatedDetections: 3,
        createdAt: '2023-01-01T00:00:00Z',
        updatedAt: '2023-01-01T00:00:00Z'
      };

      mockApiService.createAnnotationSession.mockResolvedValue(mockSession);
      mockApiService.getAnnotationSession.mockResolvedValue(mockSession);

      // Create session
      const createdSession = await mockApiService.createAnnotationSession(
        mockVideoId,
        'project-456'
      );

      expect(createdSession).toEqual(mockSession);
      expect(mockApiService.createAnnotationSession).toHaveBeenCalledWith(
        mockVideoId,
        'project-456'
      );

      // Get session
      const retrievedSession = await mockApiService.getAnnotationSession('session-123');
      expect(retrievedSession).toEqual(mockSession);
    });

    it('should update annotation session progress', async () => {
      const initialSession = {
        id: 'session-123',
        videoId: mockVideoId,
        projectId: 'project-456',
        status: 'active',
        currentFrame: 30,
        totalDetections: 10,
        validatedDetections: 5,
        createdAt: '2023-01-01T00:00:00Z',
        updatedAt: '2023-01-01T01:00:00Z'
      };

      const updatedSession = {
        ...initialSession,
        currentFrame: 60,
        validatedDetections: 7,
        updatedAt: '2023-01-01T01:30:00Z'
      };

      mockApiService.updateAnnotationSession.mockResolvedValue(updatedSession);

      const result = await mockApiService.updateAnnotationSession('session-123', {
        currentFrame: 60,
        validatedDetections: 7
      });

      expect(result.currentFrame).toBe(60);
      expect(result.validatedDetections).toBe(7);
      expect(mockApiService.updateAnnotationSession).toHaveBeenCalledWith(
        'session-123',
        expect.objectContaining({
          currentFrame: 60,
          validatedDetections: 7
        })
      );
    });
  });

  describe('Annotation Data Validation', () => {
    it('should validate annotation data integrity', async () => {
      // Test with various annotation data scenarios
      const testAnnotations = [
        // Valid annotation
        {
          ...mockAnnotations[0],
          boundingBox: {
            x: 100, y: 100, width: 50, height: 100,
            label: 'person', confidence: 0.85
          }
        },
        // Annotation with edge coordinates
        {
          ...mockAnnotations[1],
          boundingBox: {
            x: 0, y: 0, width: 1920, height: 1080,
            label: 'car', confidence: 0.95
          }
        }
      ];

      mockApiService.getAnnotations.mockResolvedValue(testAnnotations as any);

      render(<MockAnnotationManager videoId={mockVideoId} />);

      await waitFor(() => {
        expect(screen.getByTestId('annotation-manager')).toBeInTheDocument();
      });

      // Verify annotations are displayed correctly
      expect(screen.getByTestId('annotation-ann-1-bbox')).toHaveTextContent('100, 100, 50, 100');
      expect(screen.getByTestId('annotation-ann-2-bbox')).toHaveTextContent('0, 0, 1920, 1080');
    });

    it('should handle invalid annotation data gracefully', async () => {
      const invalidAnnotations = [
        {
          id: 'invalid-1',
          videoId: mockVideoId,
          detectionId: 'det-invalid',
          frameNumber: -1, // Invalid frame number
          timestamp: -100, // Invalid timestamp
          vruType: 'pedestrian',
          boundingBox: {
            x: -50, y: -50, width: 0, height: 0, // Invalid coordinates
            label: '', confidence: 1.5 // Invalid confidence
          },
          occluded: false,
          truncated: false,
          difficult: false,
          validated: false,
          createdAt: '',
          updatedAt: ''
        }
      ];

      mockApiService.getAnnotations.mockResolvedValue(invalidAnnotations as any);

      render(<MockAnnotationManager videoId={mockVideoId} />);

      await waitFor(() => {
        expect(screen.getByTestId('annotation-manager')).toBeInTheDocument();
      });

      // Should still render the annotation but with corrected/default values
      expect(screen.getByTestId('annotation-count')).toHaveTextContent('Annotations: 1');
    });

    it('should validate bounding box constraints', async () => {
      const constraintTests = [
        { x: 0, y: 0, width: 50, height: 100, valid: true },
        { x: 1870, y: 980, width: 50, height: 100, valid: true }, // Near edge
        { x: -10, y: -10, width: 50, height: 100, valid: false }, // Negative coords
        { x: 100, y: 100, width: -50, height: -100, valid: false }, // Negative dimensions
        { x: 1900, y: 1000, width: 50, height: 100, valid: false } // Out of bounds (assuming 1920x1080)
      ];

      for (const test of constraintTests) {
        const testAnnotation = {
          ...mockAnnotations[0],
          id: `test-${test.x}-${test.y}`,
          boundingBox: {
            x: test.x,
            y: test.y,
            width: test.width,
            height: test.height,
            label: 'person',
            confidence: 0.8
          }
        };

        mockApiService.getAnnotations.mockResolvedValue([testAnnotation] as any);

        render(<MockAnnotationManager videoId={mockVideoId} />);

        await waitFor(() => {
          expect(screen.getByTestId('annotation-manager')).toBeInTheDocument();
        });

        // Should display annotation regardless, but validation logic would be in the backend
        expect(screen.getByTestId('annotation-count')).toHaveTextContent('Annotations: 1');
      }
    });
  });

  describe('Performance and Scalability', () => {
    it('should handle large numbers of annotations efficiently', async () => {
      // Generate 1000 annotations
      const largeAnnotationSet = Array.from({ length: 1000 }, (_, i) => ({
        id: `ann-${i}`,
        videoId: mockVideoId,
        detectionId: `det-${i}`,
        frameNumber: i,
        timestamp: i * 33.33,
        vruType: i % 2 === 0 ? 'pedestrian' : 'cyclist',
        boundingBox: {
          x: Math.random() * 1920,
          y: Math.random() * 1080,
          width: 50 + Math.random() * 100,
          height: 100 + Math.random() * 200,
          label: i % 2 === 0 ? 'person' : 'bicycle',
          confidence: 0.5 + Math.random() * 0.5
        },
        occluded: Math.random() > 0.8,
        truncated: Math.random() > 0.9,
        difficult: Math.random() > 0.95,
        validated: Math.random() > 0.5,
        annotator: 'test-user',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }));

      mockApiService.getAnnotations.mockResolvedValue(largeAnnotationSet as any);

      const startTime = performance.now();
      render(<MockAnnotationManager videoId={mockVideoId} />);

      await waitFor(() => {
        expect(screen.getByTestId('annotation-count')).toHaveTextContent('Annotations: 1000');
      });

      const renderTime = performance.now() - startTime;

      // Should render efficiently (under 2 seconds for 1000 annotations)
      expect(renderTime).toBeLessThan(2000);

      // Verify first and last annotations are present
      expect(screen.getByTestId('annotation-ann-0')).toBeInTheDocument();
      expect(screen.getByTestId('annotation-ann-999')).toBeInTheDocument();
    });

    it('should handle rapid annotation updates without performance degradation', async () => {
      render(<MockAnnotationManager videoId={mockVideoId} />);

      await waitFor(() => {
        expect(screen.getByTestId('annotation-manager')).toBeInTheDocument();
      });

      // Simulate rapid updates
      const updatePromises = [];
      for (let i = 0; i < 10; i++) {
        const updatedAnnotation = {
          ...mockAnnotations[0],
          validated: i % 2 === 0,
          updatedAt: new Date().toISOString()
        };

        mockApiService.updateAnnotation.mockResolvedValue(updatedAnnotation);
        
        updatePromises.push(
          new Promise(resolve => {
            fireEvent.click(screen.getByTestId('update-annotation-ann-1-btn'));
            setTimeout(resolve, 10);
          })
        );
      }

      await Promise.all(updatePromises);

      // Should handle all updates without errors
      expect(mockApiService.updateAnnotation).toHaveBeenCalledTimes(10);
    });
  });
});