import { useState, useEffect, useCallback, RefObject } from 'react';

interface UseResponsiveVideoPlayerProps {
  videoRef: RefObject<HTMLVideoElement>;
  containerRef: RefObject<HTMLDivElement>;
}

interface ResponsiveVideoPlayerState {
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  orientation: 'portrait' | 'landscape';
  screenSize: { width: number; height: number };
  isTouchDevice: boolean;
  isHighDensity: boolean;
  preferredControlSize: 'small' | 'medium' | 'large';
}

export const useResponsiveVideoPlayer = ({
  videoRef,
  containerRef
}: UseResponsiveVideoPlayerProps) => {
  const [state, setState] = useState<ResponsiveVideoPlayerState>({
    isMobile: false,
    isTablet: false,
    isDesktop: true,
    orientation: 'landscape',
    screenSize: { width: window.innerWidth, height: window.innerHeight },
    isTouchDevice: false,
    isHighDensity: false,
    preferredControlSize: 'small'
  });

  // Check if device supports touch
  const checkTouchSupport = useCallback(() => {
    return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  }, []);

  // Check if display is high density
  const checkHighDensity = useCallback(() => {
    return window.devicePixelRatio > 1.5;
  }, []);

  // Get screen size category
  const getScreenCategory = useCallback((width: number) => {
    if (width < 600) return 'mobile';
    if (width < 960) return 'tablet';
    return 'desktop';
  }, []);

  // Get preferred control size based on screen and touch
  const getPreferredControlSize = useCallback((width: number, isTouchDevice: boolean) => {
    if (isTouchDevice && width < 600) return 'large';
    if (width < 600) return 'medium';
    return 'small';
  }, []);

  // Update responsive state
  const updateResponsiveState = useCallback(() => {
    const width = window.innerWidth;
    const height = window.innerHeight;
    const isTouchDevice = checkTouchSupport();
    const isHighDensity = checkHighDensity();
    const category = getScreenCategory(width);
    
    setState({
      isMobile: category === 'mobile',
      isTablet: category === 'tablet',
      isDesktop: category === 'desktop',
      orientation: width > height ? 'landscape' : 'portrait',
      screenSize: { width, height },
      isTouchDevice,
      isHighDensity,
      preferredControlSize: getPreferredControlSize(width, isTouchDevice) as 'small' | 'medium' | 'large'
    });
  }, [checkTouchSupport, checkHighDensity, getScreenCategory, getPreferredControlSize]);

  // Handle resize events
  useEffect(() => {
    updateResponsiveState();

    const handleResize = () => {
      updateResponsiveState();
    };

    window.addEventListener('resize', handleResize);
    window.addEventListener('orientationchange', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('orientationchange', handleResize);
    };
  }, [updateResponsiveState]);

  // Get responsive video dimensions
  const getResponsiveVideoDimensions = useCallback(() => {
    const { width, height } = state.screenSize;
    const { orientation, isMobile } = state;

    if (isMobile) {
      if (orientation === 'portrait') {
        return {
          maxHeight: Math.min(height * 0.7, 500),
          minHeight: 200,
          width: '100%'
        };
      } else {
        return {
          maxHeight: Math.min(height * 0.85, 400),
          minHeight: 180,
          width: '100%'
        };
      }
    }

    return {
      maxHeight: 500,
      minHeight: 200,
      width: '100%'
    };
  }, [state]);

  // Get responsive slider props
  const getResponsiveSliderProps = useCallback(() => {
    const { isMobile, isTouchDevice } = state;
    
    return {
      size: (isMobile ? 'medium' : 'small') as 'small' | 'medium',
      sx: {
        height: isMobile ? 8 : 4,
        '& .MuiSlider-thumb': {
          width: isTouchDevice ? 24 : 20,
          height: isTouchDevice ? 24 : 20,
          '&:hover': {
            boxShadow: `0px 0px 0px 8px rgba(25, 118, 210, 0.16)`
          }
        }
      }
    };
  }, [state]);

  // Get responsive button props
  const getResponsiveButtonProps = useCallback(() => {
    const { isMobile, isTouchDevice } = state;
    
    return {
      size: (isMobile ? 'medium' : 'small') as 'small' | 'medium',
      sx: {
        minHeight: isTouchDevice ? 44 : 'auto',
        minWidth: isTouchDevice ? 44 : 'auto',
        fontSize: isMobile ? '0.8rem' : '0.875rem',
        touchAction: 'manipulation',
        '&:active': {
          transform: 'scale(0.95)',
          transition: 'transform 0.1s ease'
        },
        '@media (prefers-reduced-motion: reduce)': {
          '&:active': {
            transform: 'none',
            transition: 'none'
          }
        }
      }
    };
  }, [state]);

  // Get responsive icon button props
  const getResponsiveIconButtonProps = useCallback(() => {
    const { isMobile, isTouchDevice } = state;
    
    return {
      size: (isMobile ? 'medium' : 'small') as 'small' | 'medium',
      sx: {
        padding: isTouchDevice ? '12px' : '8px',
        minWidth: isTouchDevice ? 48 : 'auto',
        minHeight: isTouchDevice ? 48 : 'auto',
        touchAction: 'manipulation'
      }
    };
  }, [state]);

  // Get responsive layout props
  const getResponsiveLayoutProps = useCallback(() => {
    const { isMobile, isTablet } = state;
    
    return {
      spacing: isMobile ? 0.5 : isTablet ? 1 : 1,
      direction: (isMobile ? 'column' : 'row') as 'row' | 'column',
      alignItems: isMobile ? 'stretch' : 'center',
      justifyContent: isMobile ? 'center' : 'flex-start',
      sx: {
        flexWrap: isMobile ? 'wrap' : 'nowrap',
        gap: isMobile ? 0.5 : 1,
        width: isMobile ? '100%' : 'auto'
      }
    };
  }, [state]);

  // Get responsive annotation props
  const getResponsiveAnnotationProps = useCallback(() => {
    const { isMobile, isTouchDevice } = state;
    
    return {
      sx: {
        gap: isMobile ? 0.5 : 1,
        px: isMobile ? 1 : 2,
        py: isMobile ? 0.5 : 1,
        minHeight: isTouchDevice ? 36 : 'auto',
        fontSize: isMobile ? '0.7rem' : '0.75rem',
        borderRadius: isMobile ? 0.5 : 1,
        touchAction: 'manipulation',
        '&:active': {
          transform: 'scale(0.95)',
          transition: 'transform 0.1s ease'
        },
        '@media (prefers-reduced-motion: reduce)': {
          '&:active': {
            transform: 'none',
            transition: 'none'
          }
        }
      },
      indicatorSize: isMobile ? 8 : 12
    };
  }, [state]);

  // Handle touch gestures for video seeking
  const handleTouchSeek = useCallback((touchEvent: TouchEvent) => {
    if (!videoRef.current || !containerRef.current || !state.isTouchDevice) return;

    const video = videoRef.current;
    const container = containerRef.current;
    const rect = container.getBoundingClientRect();
    const touch = touchEvent.touches[0];
    const x = touch.clientX - rect.left;
    const progress = Math.max(0, Math.min(1, x / rect.width));
    const newTime = progress * video.duration;

    if (isFinite(newTime)) {
      video.currentTime = newTime;
    }
  }, [videoRef, containerRef, state.isTouchDevice]);

  // Optimize canvas for high-density displays
  const optimizeCanvasForDisplay = useCallback((canvas: HTMLCanvasElement) => {
    if (!state.isHighDensity) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const devicePixelRatio = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();

    canvas.width = rect.width * devicePixelRatio;
    canvas.height = rect.height * devicePixelRatio;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';

    ctx.scale(devicePixelRatio, devicePixelRatio);
  }, [state.isHighDensity]);

  return {
    ...state,
    getResponsiveVideoDimensions,
    getResponsiveSliderProps,
    getResponsiveButtonProps,
    getResponsiveIconButtonProps,
    getResponsiveLayoutProps,
    getResponsiveAnnotationProps,
    handleTouchSeek,
    optimizeCanvasForDisplay
  };
};