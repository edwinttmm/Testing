/**
 * Enhanced Fullscreen Hook with DOM Analysis and Robust Error Handling
 * Addresses common fullscreen issues in HIL test execution
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { fullscreenAnalyzer, type FullscreenDiagnostics } from '../utils/fullscreenDomAnalyzer';

interface UseEnhancedFullscreenOptions {
  onEnter?: () => void;
  onExit?: () => void;
  onError?: (error: Error) => void;
  fallbackMode?: 'css' | 'none';
  debugMode?: boolean;
  retryAttempts?: number;
  retryDelay?: number;
}

interface FullscreenState {
  isFullscreen: boolean;
  isSupported: boolean;
  isPending: boolean;
  error: Error | null;
  diagnostics: FullscreenDiagnostics | null;
  fallbackActive: boolean;
}

export const useEnhancedFullscreen = (options: UseEnhancedFullscreenOptions = {}) => {
  const {
    onEnter,
    onExit,
    onError,
    fallbackMode = 'css',
    debugMode = false,
    retryAttempts = 3,
    retryDelay = 500,
  } = options;

  const [state, setState] = useState<FullscreenState>({
    isFullscreen: false,
    isSupported: false,
    isPending: false,
    error: null,
    diagnostics: null,
    fallbackActive: false,
  });

  const retryCountRef = useRef(0);
  const fallbackElementRef = useRef<HTMLElement | null>(null);

  // Check browser support on mount
  useEffect(() => {
    const checkSupport = () => {
      const supported = !!(
        document.fullscreenEnabled ||
        (document as any).webkitFullscreenEnabled ||
        (document as any).mozFullScreenEnabled ||
        (document as any).msFullscreenEnabled
      );

      setState(prev => ({
        ...prev,
        isSupported: supported,
        diagnostics: fullscreenAnalyzer.runComprehensiveAnalysis(),
      }));

      if (debugMode) {
        console.log('🔍 Fullscreen support check:', {
          supported,
          fullscreenEnabled: document.fullscreenEnabled,
          userAgent: navigator.userAgent,
        });
      }
    };

    checkSupport();
  }, [debugMode]);

  // Set up fullscreen event listeners
  useEffect(() => {
    const handleFullscreenChange = () => {
      const isCurrentlyFullscreen = !!(
        document.fullscreenElement ||
        (document as any).webkitFullscreenElement ||
        (document as any).mozFullScreenElement ||
        (document as any).msFullscreenElement
      );

      setState(prev => ({
        ...prev,
        isFullscreen: isCurrentlyFullscreen,
        isPending: false,
        error: null,
      }));

      if (debugMode) {
        console.log('🔄 Fullscreen change detected:', isCurrentlyFullscreen);
      }

      if (isCurrentlyFullscreen) {
        onEnter?.();
      } else {
        onExit?.();
      }
    };

    const handleFullscreenError = (event: Event) => {
      const error = new Error('Fullscreen request failed');
      setState(prev => ({
        ...prev,
        isPending: false,
        error,
      }));

      if (debugMode) {
        console.error('❌ Fullscreen error:', event);
      }

      onError?.(error);
    };

    // Add event listeners with vendor prefixes
    const events = [
      'fullscreenchange',
      'webkitfullscreenchange',
      'mozfullscreenchange',
      'MSFullscreenChange',
    ];

    const errorEvents = [
      'fullscreenerror',
      'webkitfullscreenerror',
      'mozfullscreenerror',
      'MSFullscreenError',
    ];

    events.forEach(event => {
      document.addEventListener(event, handleFullscreenChange);
    });

    errorEvents.forEach(event => {
      document.addEventListener(event, handleFullscreenError);
    });

    return () => {
      events.forEach(event => {
        document.removeEventListener(event, handleFullscreenChange);
      });

      errorEvents.forEach(event => {
        document.removeEventListener(event, handleFullscreenError);
      });
    };
  }, [onEnter, onExit, onError, debugMode]);

  // Robust enter fullscreen function
  const enterFullscreen = useCallback(async (element?: HTMLElement): Promise<boolean> => {
    if (!state.isSupported && fallbackMode === 'none') {
      const error = new Error('Fullscreen not supported and fallback disabled');
      setState(prev => ({ ...prev, error }));
      onError?.(error);
      return false;
    }

    const targetElement = element || document.documentElement;

    if (debugMode) {
      console.log('🚀 Attempting to enter fullscreen...', {
        element: targetElement,
        retryCount: retryCountRef.current,
      });
    }

    setState(prev => ({ ...prev, isPending: true, error: null }));

    try {
      // Run pre-fullscreen diagnostics
      const diagnostics = fullscreenAnalyzer.runComprehensiveAnalysis();
      
      if (debugMode) {
        console.log('🔍 Pre-fullscreen diagnostics:', diagnostics);
      }

      // Check for critical issues
      const criticalIssues = diagnostics.recommendations.filter(r => r.category === 'critical');
      if (criticalIssues.length > 0) {
        throw new Error(`Critical fullscreen issues detected: ${criticalIssues.map(i => i.issue).join(', ')}`);
      }

      // Wait for element to be ready
      await waitForElementReady(targetElement);

      // Attempt native fullscreen
      if (state.isSupported) {
        const success = await attemptNativeFullscreen(targetElement);
        if (success) {
          retryCountRef.current = 0;
          return true;
        }
      }

      // Fallback to CSS fullscreen if enabled
      if (fallbackMode === 'css') {
        if (debugMode) {
          console.log('🔄 Falling back to CSS fullscreen');
        }
        
        return enterCSSFullscreen(targetElement);
      }

      throw new Error('All fullscreen methods failed');

    } catch (error) {
      if (debugMode) {
        console.error('❌ Fullscreen attempt failed:', error);
      }

      // Retry logic
      if (retryCountRef.current < retryAttempts) {
        retryCountRef.current++;
        
        if (debugMode) {
          console.log(`🔄 Retrying fullscreen (attempt ${retryCountRef.current}/${retryAttempts})...`);
        }

        await new Promise(resolve => setTimeout(resolve, retryDelay));
        return enterFullscreen(element);
      }

      setState(prev => ({ 
        ...prev, 
        isPending: false, 
        error: error instanceof Error ? error : new Error(String(error)) 
      }));
      
      onError?.(error instanceof Error ? error : new Error(String(error)));
      return false;
    }
  }, [state.isSupported, fallbackMode, debugMode, retryAttempts, retryDelay, onError]);

  // Exit fullscreen function
  const exitFullscreen = useCallback(async (): Promise<boolean> => {
    if (debugMode) {
      console.log('🚪 Attempting to exit fullscreen...');
    }

    setState(prev => ({ ...prev, isPending: true }));

    try {
      // Exit CSS fallback if active
      if (state.fallbackActive && fallbackElementRef.current) {
        exitCSSFullscreen();
        return true;
      }

      // Exit native fullscreen
      if (document.exitFullscreen) {
        await document.exitFullscreen();
      } else if ((document as any).webkitExitFullscreen) {
        await (document as any).webkitExitFullscreen();
      } else if ((document as any).mozCancelFullScreen) {
        await (document as any).mozCancelFullScreen();
      } else if ((document as any).msExitFullscreen) {
        await (document as any).msExitFullscreen();
      } else {
        throw new Error('No exit fullscreen method available');
      }

      return true;

    } catch (error) {
      if (debugMode) {
        console.error('❌ Exit fullscreen failed:', error);
      }

      setState(prev => ({ 
        ...prev, 
        isPending: false, 
        error: error instanceof Error ? error : new Error(String(error)) 
      }));
      
      onError?.(error instanceof Error ? error : new Error(String(error)));
      return false;
    }
  }, [state.fallbackActive, debugMode, onError]);

  // Toggle fullscreen
  const toggleFullscreen = useCallback(async (element?: HTMLElement): Promise<boolean> => {
    if (state.isFullscreen || state.fallbackActive) {
      return exitFullscreen();
    } else {
      return enterFullscreen(element);
    }
  }, [state.isFullscreen, state.fallbackActive, enterFullscreen, exitFullscreen]);

  // Analyze current DOM state
  const analyzeDOMState = useCallback((
    videoRef?: React.RefObject<HTMLVideoElement>,
    containerRef?: React.RefObject<HTMLDivElement>
  ) => {
    const diagnostics = fullscreenAnalyzer.runComprehensiveAnalysis(videoRef, containerRef);
    setState(prev => ({ ...prev, diagnostics }));
    return diagnostics;
  }, []);

  // Helper function: Wait for element to be ready
  const waitForElementReady = (element: HTMLElement): Promise<void> => {
    return new Promise((resolve, reject) => {
      if (!element.isConnected) {
        reject(new Error('Element not connected to DOM'));
        return;
      }

      // If element is a video, wait for it to be ready
      if (element instanceof HTMLVideoElement) {
        if (element.readyState >= 3) { // HAVE_FUTURE_DATA
          resolve();
        } else {
          const handleCanPlay = () => {
            element.removeEventListener('canplay', handleCanPlay);
            resolve();
          };
          
          element.addEventListener('canplay', handleCanPlay);
          
          // Timeout after 10 seconds
          setTimeout(() => {
            element.removeEventListener('canplay', handleCanPlay);
            reject(new Error('Video load timeout'));
          }, 10000);
        }
      } else {
        // For non-video elements, just check if they're visible
        const rect = element.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          resolve();
        } else {
          // Wait a bit for layout
          setTimeout(() => resolve(), 100);
        }
      }
    });
  };

  // Helper function: Attempt native fullscreen
  const attemptNativeFullscreen = (element: HTMLElement): Promise<boolean> => {
    return new Promise((resolve) => {
      const requestFullscreen = 
        element.requestFullscreen ||
        (element as any).webkitRequestFullscreen ||
        (element as any).mozRequestFullScreen ||
        (element as any).msRequestFullscreen;

      if (!requestFullscreen) {
        resolve(false);
        return;
      }

      const timeoutId = setTimeout(() => {
        resolve(false);
      }, 5000); // 5 second timeout

      const handleChange = () => {
        clearTimeout(timeoutId);
        document.removeEventListener('fullscreenchange', handleChange);
        resolve(!!document.fullscreenElement);
      };

      document.addEventListener('fullscreenchange', handleChange);

      try {
        const result = requestFullscreen.call(element);
        if (result && typeof result.catch === 'function') {
          result.catch(() => {
            clearTimeout(timeoutId);
            document.removeEventListener('fullscreenchange', handleChange);
            resolve(false);
          });
        }
      } catch (error) {
        clearTimeout(timeoutId);
        document.removeEventListener('fullscreenchange', handleChange);
        resolve(false);
      }
    });
  };

  // Helper function: Enter CSS fullscreen
  const enterCSSFullscreen = (element: HTMLElement): boolean => {
    try {
      // Store original styles
      const originalStyles = {
        position: element.style.position,
        top: element.style.top,
        left: element.style.left,
        width: element.style.width,
        height: element.style.height,
        zIndex: element.style.zIndex,
        background: element.style.background,
      };

      // Apply fullscreen styles
      Object.assign(element.style, {
        position: 'fixed',
        top: '0',
        left: '0',
        width: '100vw',
        height: '100vh',
        zIndex: '10000',
        background: 'black',
      });

      element.dataset.originalStyles = JSON.stringify(originalStyles);
      fallbackElementRef.current = element;

      setState(prev => ({ 
        ...prev, 
        isFullscreen: true, 
        fallbackActive: true, 
        isPending: false 
      }));

      onEnter?.();
      return true;

    } catch (error) {
      if (debugMode) {
        console.error('❌ CSS fullscreen failed:', error);
      }
      return false;
    }
  };

  // Helper function: Exit CSS fullscreen
  const exitCSSFullscreen = (): boolean => {
    try {
      const element = fallbackElementRef.current;
      if (!element) return false;

      const originalStyles = JSON.parse(element.dataset.originalStyles || '{}');
      
      // Restore original styles
      Object.assign(element.style, originalStyles);
      
      delete element.dataset.originalStyles;
      fallbackElementRef.current = null;

      setState(prev => ({ 
        ...prev, 
        isFullscreen: false, 
        fallbackActive: false, 
        isPending: false 
      }));

      onExit?.();
      return true;

    } catch (error) {
      if (debugMode) {
        console.error('❌ CSS fullscreen exit failed:', error);
      }
      return false;
    }
  };

  return {
    ...state,
    enterFullscreen,
    exitFullscreen,
    toggleFullscreen,
    analyzeDOMState,
  };
};