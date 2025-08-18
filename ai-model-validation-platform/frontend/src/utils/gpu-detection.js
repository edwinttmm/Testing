/**
 * GPU Detection Utility for Browser Environment
 * Detects available GPU capabilities and provides fallback information
 */

function detectGPU() {
    try {
        // Check if we're in a browser environment
        if (typeof document === 'undefined' || typeof window === 'undefined') {
            return {
                vendor: 'Server Environment',
                renderer: 'Node.js Runtime',
                supported: false,
                webgl: false,
                environment: 'server'
            };
        }

        // Create canvas for WebGL testing
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        
        if (gl) {
            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            if (debugInfo) {
                const vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
                const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
                
                return {
                    vendor: vendor || 'Unknown Vendor',
                    renderer: renderer || 'Unknown Renderer',
                    supported: true,
                    webgl: true,
                    webglVersion: gl.getParameter(gl.VERSION),
                    shadingLanguageVersion: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
                    maxTextureSize: gl.getParameter(gl.MAX_TEXTURE_SIZE),
                    environment: 'browser'
                };
            } else {
                return {
                    vendor: 'WebGL Available',
                    renderer: 'Debug Info Not Available',
                    supported: true,
                    webgl: true,
                    webglVersion: gl.getParameter(gl.VERSION),
                    environment: 'browser'
                };
            }
        }
        
        // WebGL not available
        return {
            vendor: 'No GPU Acceleration',
            renderer: 'Software Rendering',
            supported: false,
            webgl: false,
            environment: 'browser'
        };
        
    } catch (error) {
        return {
            vendor: 'Detection Failed',
            renderer: 'CPU-only mode',
            supported: false,
            webgl: false,
            error: error.message,
            environment: typeof window !== 'undefined' ? 'browser' : 'server'
        };
    }
}

// Export for both CommonJS and ES modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { detectGPU };
} else if (typeof window !== 'undefined') {
    window.GPUDetection = { detectGPU };
}

// Default export for ES modules
export { detectGPU };