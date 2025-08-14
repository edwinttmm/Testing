/**
 * GPU Detection Utility
 * Based on environment analysis from System Analysis Agent
 */

const detectGPU = () => {
  try {
    if (typeof window === 'undefined') {
      // Node.js environment - check for GPU via system commands
      const { execSync } = require('child_process');
      
      try {
        // Try NVIDIA first
        const nvidiaOutput = execSync('nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>/dev/null', {
          encoding: 'utf8',
          timeout: 5000
        });
        if (nvidiaOutput.trim()) {
          return {
            available: true,
            vendor: 'nvidia',
            name: nvidiaOutput.trim(),
            mode: 'gpu'
          };
        }
      } catch (e) {}

      try {
        // Try AMD
        const amdOutput = execSync('rocm-smi --showproductname 2>/dev/null', {
          encoding: 'utf8',
          timeout: 5000
        });
        if (amdOutput.trim()) {
          return {
            available: true,
            vendor: 'amd',
            name: amdOutput.trim(),
            mode: 'gpu'
          };
        }
      } catch (e) {}

      // No GPU detected - CPU only
      return {
        available: false,
        vendor: 'none',
        name: 'CPU-only',
        mode: 'cpu'
      };
    } else {
      // Browser environment - check WebGL
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
      
      if (gl) {
        const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
        const vendor = debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : 'unknown';
        const renderer = debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : 'unknown';
        
        return {
          available: true,
          vendor: parseGpuVendor(vendor),
          name: renderer,
          mode: 'webgl'
        };
      }

      // Check WebGPU support
      if ('gpu' in navigator) {
        return {
          available: true,
          vendor: 'unknown',
          name: 'WebGPU',
          mode: 'webgpu'
        };
      }

      return {
        available: false,
        vendor: 'none',
        name: 'CPU-only',
        mode: 'cpu'
      };
    }
  } catch (error) {
    console.warn('GPU detection failed:', error);
    return {
      available: false,
      vendor: 'error',
      name: 'CPU-only (fallback)',
      mode: 'cpu'
    };
  }
};

const parseGpuVendor = (vendor) => {
  const v = vendor.toLowerCase();
  if (v.includes('nvidia')) return 'nvidia';
  if (v.includes('amd') || v.includes('ati')) return 'amd';
  if (v.includes('intel')) return 'intel';
  return 'unknown';
};

const getOptimalConfig = (gpuInfo) => {
  if (!gpuInfo.available) {
    return {
      imageProcessing: {
        maxSize: 2048,
        quality: 0.8,
        format: 'jpeg',
        batchSize: 1
      },
      tensorflow: {
        backend: 'cpu',
        flags: {
          WEBGL_FORCE_F16_TEXTURES: false,
          WEBGL_PACK: false
        }
      }
    };
  }

  return {
    imageProcessing: {
      maxSize: 4096,
      quality: 0.9,
      format: 'webp',
      batchSize: 4
    },
    tensorflow: {
      backend: gpuInfo.mode === 'webgl' ? 'webgl' : 'cpu',
      flags: {
        WEBGL_FORCE_F16_TEXTURES: true,
        WEBGL_PACK: true
      }
    }
  };
};

module.exports = {
  detectGPU,
  getOptimalConfig,
  parseGpuVendor
};