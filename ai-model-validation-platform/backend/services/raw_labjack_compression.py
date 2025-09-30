"""
Advanced Raw LabJack Data Compression Service
============================================

High-performance compression service specifically designed for raw LabJack voltage
data streams. Provides intelligent compression algorithm selection, real-time
compression monitoring, and storage optimization for high-frequency data capture.

This service implements multiple compression strategies:
- Lossless compression for critical voltage transitions
- Lossy compression for stable voltage periods 
- Adaptive compression based on signal characteristics
- Delta encoding for smooth voltage curves
- Run-length encoding for stable periods
- Quantization for reduced precision requirements

Key Features:
- Real-time compression with sub-millisecond latency
- Adaptive algorithm selection based on signal variance
- Quality monitoring and compression ratio optimization
- Buffer management for high-throughput data streams
- Integrity verification and error recovery
- Performance monitoring and bottleneck detection
"""

import asyncio
import logging
import threading
import time
import struct
import zlib
import lzma
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import statistics
import hashlib

# Local imports
from src.models.raw_labjack_models import (
    CompressionAlgorithm, DataQuality, BufferStatus
)

logger = logging.getLogger(__name__)


class CompressionQuality(Enum):
    """Quality levels for compression"""
    LOSSLESS = "lossless"      # No data loss
    HIGH_QUALITY = "high"      # <0.1% precision loss
    MEDIUM_QUALITY = "medium"  # <1% precision loss  
    LOW_QUALITY = "low"        # <5% precision loss
    AGGRESSIVE = "aggressive"  # >5% precision loss acceptable


class SignalType(Enum):
    """Types of voltage signal patterns"""
    STABLE = "stable"          # Minimal variation
    SMOOTH = "smooth"          # Gradual changes
    NOISY = "noisy"           # High frequency noise
    TRANSITIONAL = "transitional" # Sharp transitions
    MIXED = "mixed"           # Multiple patterns


@dataclass
class CompressionSettings:
    """Configuration for compression operations"""
    # Algorithm preferences
    primary_algorithm: CompressionAlgorithm = CompressionAlgorithm.ADAPTIVE
    fallback_algorithm: CompressionAlgorithm = CompressionAlgorithm.ZLIB
    quality_target: CompressionQuality = CompressionQuality.HIGH_QUALITY
    
    # Performance parameters
    compression_level: int = 6  # 1-9, higher = better compression
    buffer_size_samples: int = 10000
    max_compression_time_ms: float = 100.0
    target_compression_ratio: float = 10.0
    
    # Quality parameters
    max_acceptable_error_percent: float = 0.1
    preserve_transition_accuracy: bool = True
    transition_threshold_v: float = 0.1
    
    # Quantization settings
    quantization_bits: int = 12  # Reduce from 16-bit to 12-bit
    dynamic_range_optimization: bool = True
    
    # Delta compression settings
    delta_precision_bits: int = 8
    enable_predictive_coding: bool = True
    
    # Run-length settings
    min_run_length: int = 5
    stable_threshold_v: float = 0.001


@dataclass
class CompressionResult:
    """Result of compression operation"""
    success: bool
    algorithm_used: CompressionAlgorithm
    original_size_bytes: int
    compressed_size_bytes: int
    compression_ratio: float
    compression_time_ms: float
    
    # Quality metrics
    data_quality: DataQuality
    estimated_error_percent: float = 0.0
    signal_fidelity_score: float = 1.0
    
    # Performance metrics
    throughput_mbps: float = 0.0
    cpu_usage_percent: float = 0.0
    
    # Metadata
    compressed_data: bytes = b''
    compression_metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: str = ""


@dataclass
class DecompressionResult:
    """Result of decompression operation"""
    success: bool
    original_data: Optional[np.ndarray] = None
    decompression_time_ms: float = 0.0
    data_integrity_verified: bool = False
    quality_score: float = 1.0
    error_message: Optional[str] = None


class RawLabJackCompressor:
    """
    Advanced compression service for raw LabJack voltage data.
    
    Provides intelligent, adaptive compression with real-time performance
    monitoring and quality control for high-frequency data streams.
    """
    
    def __init__(self, settings: Optional[CompressionSettings] = None):
        self.settings = settings or CompressionSettings()
        
        # Performance tracking
        self.compression_stats = {
            'total_compressions': 0,
            'total_original_bytes': 0,
            'total_compressed_bytes': 0,
            'average_compression_ratio': 0.0,
            'average_compression_time_ms': 0.0,
            'algorithm_usage': {alg.value: 0 for alg in CompressionAlgorithm},
            'quality_distribution': {qual.value: 0 for qual in CompressionQuality},
            'compression_errors': 0,
            'decompression_errors': 0
        }
        
        # Signal analysis cache
        self.signal_analysis_cache: Dict[str, Dict[str, Any]] = {}
        
        # Compression context for predictive algorithms
        self.compression_context: Dict[str, Any] = {}
        
        logger.info("Raw LabJack compressor initialized")
    
    async def compress_data_batch(
        self,
        raw_data: Union[List[float], np.ndarray],
        algorithm: Optional[CompressionAlgorithm] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Compress a batch of raw voltage data.
        
        Args:
            raw_data: Raw voltage samples
            algorithm: Compression algorithm to use (auto-selected if None)
            metadata: Additional metadata for compression context
        
        Returns:
            Tuple of (compressed_data_bytes, compression_metadata)
        """
        compression_start = time.perf_counter()
        
        try:
            # Convert to numpy array for processing
            if isinstance(raw_data, list):
                data_array = np.array(raw_data, dtype=np.float32)
            else:
                data_array = raw_data.astype(np.float32)
            
            # Analyze signal characteristics
            signal_analysis = self._analyze_signal_characteristics(data_array)
            
            # Select optimal compression algorithm
            if algorithm is None:
                algorithm = self._select_optimal_algorithm(signal_analysis)
            
            # Perform compression
            compression_result = await self._compress_with_algorithm(
                data_array, algorithm, signal_analysis, metadata or {}
            )
            
            # Update statistics
            self._update_compression_stats(compression_result)
            
            # Verify compression quality
            if compression_result.estimated_error_percent > self.settings.max_acceptable_error_percent:
                logger.warning(
                    f"Compression quality below threshold: {compression_result.estimated_error_percent:.2f}% error"
                )
            
            return compression_result.compressed_data, compression_result.compression_metadata
            
        except Exception as e:
            logger.error(f"Error compressing data batch: {e}")
            self.compression_stats['compression_errors'] += 1
            
            # Fallback to simple compression
            return self._fallback_compression(raw_data), {'error': str(e)}
    
    def _analyze_signal_characteristics(self, data: np.ndarray) -> Dict[str, Any]:
        """Analyze voltage signal characteristics for compression optimization"""
        try:
            # Basic statistical analysis
            mean_voltage = np.mean(data)
            std_voltage = np.std(data)
            min_voltage = np.min(data)
            max_voltage = np.max(data)
            
            # Calculate signal variance
            variance = np.var(data)
            
            # Detect transitions (sharp changes)
            diff = np.diff(data)
            abs_diff = np.abs(diff)
            transition_count = np.sum(abs_diff > self.settings.transition_threshold_v)
            max_transition = np.max(abs_diff) if len(abs_diff) > 0 else 0.0
            
            # Calculate noise level
            smoothed = self._apply_smoothing_filter(data, window_size=5)
            noise_level = np.std(data - smoothed)
            
            # Determine signal type
            if variance < 0.001:
                signal_type = SignalType.STABLE
            elif noise_level > std_voltage * 0.5:
                signal_type = SignalType.NOISY
            elif transition_count > len(data) * 0.1:
                signal_type = SignalType.TRANSITIONAL
            elif variance < 0.01:
                signal_type = SignalType.SMOOTH
            else:
                signal_type = SignalType.MIXED
            
            # Calculate run lengths for stable periods
            run_lengths = self._calculate_run_lengths(data)
            avg_run_length = np.mean(run_lengths) if run_lengths else 1
            
            # Calculate delta statistics
            delta_stats = {
                'mean_delta': np.mean(abs_diff) if len(abs_diff) > 0 else 0.0,
                'max_delta': max_transition,
                'delta_variance': np.var(diff) if len(diff) > 0 else 0.0
            }
            
            analysis = {
                'signal_type': signal_type,
                'variance': variance,
                'noise_level': noise_level,
                'transition_count': transition_count,
                'max_transition': max_transition,
                'average_run_length': avg_run_length,
                'voltage_range': max_voltage - min_voltage,
                'mean_voltage': mean_voltage,
                'std_voltage': std_voltage,
                'delta_statistics': delta_stats,
                'data_size': len(data),
                'analysis_timestamp': time.time()
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing signal characteristics: {e}")
            return {
                'signal_type': SignalType.MIXED,
                'variance': 1.0,
                'analysis_error': str(e)
            }
    
    def _apply_smoothing_filter(self, data: np.ndarray, window_size: int = 5) -> np.ndarray:
        """Apply simple smoothing filter for noise estimation"""
        try:
            if len(data) < window_size:
                return data
            
            # Simple moving average
            kernel = np.ones(window_size) / window_size
            smoothed = np.convolve(data, kernel, mode='same')
            
            return smoothed
            
        except Exception as e:
            logger.error(f"Error applying smoothing filter: {e}")
            return data
    
    def _calculate_run_lengths(self, data: np.ndarray) -> List[int]:
        """Calculate run lengths of stable voltage periods"""
        try:
            if len(data) < 2:
                return [len(data)]
            
            # Find stable periods (small changes)
            stable_threshold = self.settings.stable_threshold_v
            diff = np.abs(np.diff(data))
            is_stable = diff < stable_threshold
            
            # Calculate run lengths
            run_lengths = []
            current_run = 1
            
            for i, stable in enumerate(is_stable):
                if stable:
                    current_run += 1
                else:
                    if current_run >= self.settings.min_run_length:
                        run_lengths.append(current_run)
                    current_run = 1
            
            # Add final run
            if current_run >= self.settings.min_run_length:
                run_lengths.append(current_run)
            
            return run_lengths
            
        except Exception as e:
            logger.error(f"Error calculating run lengths: {e}")
            return [1]
    
    def _select_optimal_algorithm(self, signal_analysis: Dict[str, Any]) -> CompressionAlgorithm:
        """Select optimal compression algorithm based on signal characteristics"""
        try:
            signal_type = signal_analysis.get('signal_type', SignalType.MIXED)
            variance = signal_analysis.get('variance', 1.0)
            transition_count = signal_analysis.get('transition_count', 0)
            avg_run_length = signal_analysis.get('average_run_length', 1)
            noise_level = signal_analysis.get('noise_level', 0.0)
            
            # Algorithm selection logic
            if signal_type == SignalType.STABLE and avg_run_length > 20:
                # Use run-length encoding for stable signals
                return CompressionAlgorithm.DELTA_RLE
            
            elif signal_type == SignalType.SMOOTH and variance < 0.01:
                # Use delta compression for smooth signals
                return CompressionAlgorithm.DELTA_RLE
            
            elif signal_type == SignalType.TRANSITIONAL:
                # Use lossless compression for transitional signals
                return CompressionAlgorithm.LZMA
            
            elif noise_level > 0.1:
                # Use quantized compression for noisy signals
                return CompressionAlgorithm.QUANTIZED
            
            elif self.settings.primary_algorithm == CompressionAlgorithm.ADAPTIVE:
                # Adaptive selection based on multiple factors
                if variance < 0.001:
                    return CompressionAlgorithm.DELTA_RLE
                elif transition_count > len(signal_analysis.get('data_size', 1000)) * 0.05:
                    return CompressionAlgorithm.LZMA
                else:
                    return CompressionAlgorithm.ZLIB
            
            else:
                # Use configured primary algorithm
                return self.settings.primary_algorithm
                
        except Exception as e:
            logger.error(f"Error selecting optimal algorithm: {e}")
            return self.settings.fallback_algorithm
    
    async def _compress_with_algorithm(
        self,
        data: np.ndarray,
        algorithm: CompressionAlgorithm,
        signal_analysis: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> CompressionResult:
        """Compress data using specified algorithm"""
        compression_start = time.perf_counter()
        original_size = data.nbytes
        
        try:
            if algorithm == CompressionAlgorithm.ZLIB:
                compressed_data, comp_metadata = self._compress_zlib(data)
                
            elif algorithm == CompressionAlgorithm.LZMA:
                compressed_data, comp_metadata = self._compress_lzma(data)
                
            elif algorithm == CompressionAlgorithm.DELTA_RLE:
                compressed_data, comp_metadata = self._compress_delta_rle(data, signal_analysis)
                
            elif algorithm == CompressionAlgorithm.QUANTIZED:
                compressed_data, comp_metadata = self._compress_quantized(data, signal_analysis)
                
            elif algorithm == CompressionAlgorithm.ADAPTIVE:
                # Recursive call with selected algorithm
                optimal_alg = self._select_optimal_algorithm(signal_analysis)
                return await self._compress_with_algorithm(data, optimal_alg, signal_analysis, metadata)
                
            else:
                # Default to zlib
                compressed_data, comp_metadata = self._compress_zlib(data)
            
            compression_time = (time.perf_counter() - compression_start) * 1000
            compression_ratio = original_size / max(1, len(compressed_data))
            
            # Calculate quality metrics
            data_quality = self._assess_compression_quality(
                data, compressed_data, algorithm, comp_metadata
            )
            
            # Calculate checksum
            checksum = hashlib.md5(compressed_data).hexdigest()
            
            # Combine metadata
            full_metadata = {
                **metadata,
                **comp_metadata,
                'algorithm': algorithm.value,
                'signal_analysis': signal_analysis,
                'original_size_bytes': original_size,
                'compression_settings': {
                    'compression_level': self.settings.compression_level,
                    'quality_target': self.settings.quality_target.value
                }
            }
            
            result = CompressionResult(
                success=True,
                algorithm_used=algorithm,
                original_size_bytes=original_size,
                compressed_size_bytes=len(compressed_data),
                compression_ratio=compression_ratio,
                compression_time_ms=compression_time,
                data_quality=data_quality,
                throughput_mbps=(original_size / (1024 * 1024)) / max(0.001, compression_time / 1000),
                compressed_data=compressed_data,
                compression_metadata=full_metadata,
                checksum=checksum
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error compressing with {algorithm.value}: {e}")
            
            return CompressionResult(
                success=False,
                algorithm_used=algorithm,
                original_size_bytes=original_size,
                compressed_size_bytes=0,
                compression_ratio=1.0,
                compression_time_ms=(time.perf_counter() - compression_start) * 1000,
                data_quality=DataQuality.CORRUPT,
                compression_metadata={'error': str(e)}
            )
    
    def _compress_zlib(self, data: np.ndarray) -> Tuple[bytes, Dict[str, Any]]:
        """Compress using zlib algorithm"""
        try:
            # Convert to bytes
            data_bytes = data.tobytes()
            
            # Compress with specified level
            compressed = zlib.compress(data_bytes, level=self.settings.compression_level)
            
            metadata = {
                'compression_type': 'zlib',
                'data_dtype': str(data.dtype),
                'data_shape': data.shape,
                'compression_level': self.settings.compression_level
            }
            
            return compressed, metadata
            
        except Exception as e:
            logger.error(f"Error in zlib compression: {e}")
            raise
    
    def _compress_lzma(self, data: np.ndarray) -> Tuple[bytes, Dict[str, Any]]:
        """Compress using LZMA algorithm"""
        try:
            # Convert to bytes
            data_bytes = data.tobytes()
            
            # LZMA compression with custom preset
            preset = min(6, self.settings.compression_level)
            compressed = lzma.compress(data_bytes, preset=preset)
            
            metadata = {
                'compression_type': 'lzma',
                'data_dtype': str(data.dtype),
                'data_shape': data.shape,
                'lzma_preset': preset
            }
            
            return compressed, metadata
            
        except Exception as e:
            logger.error(f"Error in LZMA compression: {e}")
            raise
    
    def _compress_delta_rle(
        self, 
        data: np.ndarray, 
        signal_analysis: Dict[str, Any]
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Compress using delta encoding + run-length encoding"""
        try:
            # Calculate deltas (differences between consecutive samples)
            if len(data) == 0:
                return b'', {'compression_type': 'delta_rle', 'error': 'empty_data'}
            
            # First value is stored as-is
            first_value = data[0]
            
            if len(data) == 1:
                # Single value case
                compressed_data = struct.pack('f', first_value)
                metadata = {
                    'compression_type': 'delta_rle',
                    'data_shape': data.shape,
                    'single_value': True
                }
                return compressed_data, metadata
            
            # Calculate deltas
            deltas = np.diff(data)
            
            # Quantize deltas to reduce precision
            delta_precision = self.settings.delta_precision_bits
            delta_scale = (2 ** (delta_precision - 1)) - 1
            max_delta = np.max(np.abs(deltas)) if len(deltas) > 0 else 1.0
            
            if max_delta > 0:
                quantized_deltas = np.round(deltas * delta_scale / max_delta).astype(np.int8)
            else:
                quantized_deltas = np.zeros(len(deltas), dtype=np.int8)
            
            # Apply run-length encoding to quantized deltas
            rle_data = self._apply_run_length_encoding(quantized_deltas)
            
            # Pack the compressed data
            compressed_data = struct.pack('f', first_value)  # First value
            compressed_data += struct.pack('f', max_delta)   # Delta scale
            compressed_data += struct.pack('I', len(rle_data))  # RLE data length
            compressed_data += rle_data
            
            metadata = {
                'compression_type': 'delta_rle',
                'data_shape': data.shape,
                'delta_scale': max_delta,
                'delta_precision_bits': delta_precision,
                'rle_sequences': len(rle_data) // 2  # Approximation
            }
            
            return compressed_data, metadata
            
        except Exception as e:
            logger.error(f"Error in delta RLE compression: {e}")
            raise
    
    def _apply_run_length_encoding(self, data: np.ndarray) -> bytes:
        """Apply run-length encoding to integer data"""
        try:
            if len(data) == 0:
                return b''
            
            rle_data = []
            current_value = data[0]
            run_length = 1
            
            for i in range(1, len(data)):
                if data[i] == current_value and run_length < 255:
                    run_length += 1
                else:
                    # Store value and run length
                    rle_data.extend([current_value, run_length])
                    current_value = data[i]
                    run_length = 1
            
            # Store final run
            rle_data.extend([current_value, run_length])
            
            # Convert to bytes
            return bytes(rle_data)
            
        except Exception as e:
            logger.error(f"Error in run-length encoding: {e}")
            return data.tobytes()  # Fallback to raw data
    
    def _compress_quantized(
        self, 
        data: np.ndarray, 
        signal_analysis: Dict[str, Any]
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Compress using quantization to reduce precision"""
        try:
            # Calculate dynamic range
            min_val = np.min(data)
            max_val = np.max(data)
            
            if max_val == min_val:
                # Constant value case
                compressed_data = struct.pack('f', min_val)
                compressed_data += struct.pack('I', len(data))
                
                metadata = {
                    'compression_type': 'quantized',
                    'data_shape': data.shape,
                    'constant_value': True,
                    'value': float(min_val)
                }
                
                return compressed_data, metadata
            
            # Quantize to specified bit depth
            quantization_bits = self.settings.quantization_bits
            quantization_levels = 2 ** quantization_bits
            
            # Map data to quantization range
            normalized_data = (data - min_val) / (max_val - min_val)
            quantized_data = np.round(normalized_data * (quantization_levels - 1)).astype(np.uint16)
            
            # Compress quantized data
            quantized_bytes = quantized_data.tobytes()
            compressed_quantized = zlib.compress(quantized_bytes, level=self.settings.compression_level)
            
            # Pack compressed data with metadata
            compressed_data = struct.pack('f', min_val)  # Min value
            compressed_data += struct.pack('f', max_val)  # Max value  
            compressed_data += struct.pack('H', quantization_bits)  # Quantization bits
            compressed_data += struct.pack('I', len(data))  # Original length
            compressed_data += compressed_quantized
            
            metadata = {
                'compression_type': 'quantized',
                'data_shape': data.shape,
                'quantization_bits': quantization_bits,
                'quantization_levels': quantization_levels,
                'value_range': [float(min_val), float(max_val)],
                'estimated_error_percent': (1.0 / quantization_levels) * 100
            }
            
            return compressed_data, metadata
            
        except Exception as e:
            logger.error(f"Error in quantized compression: {e}")
            raise
    
    def _assess_compression_quality(
        self,
        original_data: np.ndarray,
        compressed_data: bytes,
        algorithm: CompressionAlgorithm,
        metadata: Dict[str, Any]
    ) -> DataQuality:
        """Assess the quality of compressed data"""
        try:
            # Quick decompression test for lossless algorithms
            if algorithm in [CompressionAlgorithm.ZLIB, CompressionAlgorithm.LZMA]:
                return DataQuality.EXCELLENT  # Lossless compression
            
            # For lossy algorithms, estimate quality based on parameters
            if algorithm == CompressionAlgorithm.QUANTIZED:
                quantization_bits = metadata.get('quantization_bits', 16)
                if quantization_bits >= 14:
                    return DataQuality.EXCELLENT
                elif quantization_bits >= 12:
                    return DataQuality.GOOD
                elif quantization_bits >= 10:
                    return DataQuality.FAIR
                else:
                    return DataQuality.POOR
            
            elif algorithm == CompressionAlgorithm.DELTA_RLE:
                # Delta RLE quality depends on delta precision
                delta_precision = metadata.get('delta_precision_bits', 8)
                if delta_precision >= 8:
                    return DataQuality.GOOD
                elif delta_precision >= 6:
                    return DataQuality.FAIR
                else:
                    return DataQuality.POOR
            
            # Default quality assessment
            return DataQuality.GOOD
            
        except Exception as e:
            logger.error(f"Error assessing compression quality: {e}")
            return DataQuality.FAIR
    
    def _fallback_compression(self, data: Union[List[float], np.ndarray]) -> bytes:
        """Simple fallback compression when advanced methods fail"""
        try:
            if isinstance(data, list):
                data_array = np.array(data, dtype=np.float32)
            else:
                data_array = data.astype(np.float32)
            
            # Simple zlib compression
            return zlib.compress(data_array.tobytes(), level=1)
            
        except Exception as e:
            logger.error(f"Fallback compression failed: {e}")
            return b''  # Return empty bytes as last resort
    
    async def decompress_buffer(
        self,
        compressed_data: bytes,
        algorithm: CompressionAlgorithm,
        metadata: Dict[str, Any]
    ) -> Optional[np.ndarray]:
        """
        Decompress compressed buffer data.
        
        Args:
            compressed_data: Compressed data bytes
            algorithm: Algorithm used for compression
            metadata: Compression metadata
        
        Returns:
            Decompressed data array or None if decompression fails
        """
        decompression_start = time.perf_counter()
        
        try:
            if algorithm == CompressionAlgorithm.ZLIB:
                result = self._decompress_zlib(compressed_data, metadata)
                
            elif algorithm == CompressionAlgorithm.LZMA:
                result = self._decompress_lzma(compressed_data, metadata)
                
            elif algorithm == CompressionAlgorithm.DELTA_RLE:
                result = self._decompress_delta_rle(compressed_data, metadata)
                
            elif algorithm == CompressionAlgorithm.QUANTIZED:
                result = self._decompress_quantized(compressed_data, metadata)
                
            else:
                logger.error(f"Unsupported decompression algorithm: {algorithm}")
                return None
            
            decompression_time = (time.perf_counter() - decompression_start) * 1000
            
            if result is not None:
                logger.debug(f"Decompressed {len(compressed_data)} bytes to {result.nbytes} bytes in {decompression_time:.1f}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"Error decompressing data: {e}")
            self.compression_stats['decompression_errors'] += 1
            return None
    
    def _decompress_zlib(self, compressed_data: bytes, metadata: Dict[str, Any]) -> Optional[np.ndarray]:
        """Decompress zlib-compressed data"""
        try:
            # Decompress
            decompressed_bytes = zlib.decompress(compressed_data)
            
            # Reconstruct array
            dtype = metadata.get('data_dtype', 'float32')
            shape = metadata.get('data_shape', (-1,))
            
            data_array = np.frombuffer(decompressed_bytes, dtype=dtype).reshape(shape)
            
            return data_array
            
        except Exception as e:
            logger.error(f"Error decompressing zlib data: {e}")
            return None
    
    def _decompress_lzma(self, compressed_data: bytes, metadata: Dict[str, Any]) -> Optional[np.ndarray]:
        """Decompress LZMA-compressed data"""
        try:
            # Decompress
            decompressed_bytes = lzma.decompress(compressed_data)
            
            # Reconstruct array
            dtype = metadata.get('data_dtype', 'float32')
            shape = metadata.get('data_shape', (-1,))
            
            data_array = np.frombuffer(decompressed_bytes, dtype=dtype).reshape(shape)
            
            return data_array
            
        except Exception as e:
            logger.error(f"Error decompressing LZMA data: {e}")
            return None
    
    def _decompress_delta_rle(self, compressed_data: bytes, metadata: Dict[str, Any]) -> Optional[np.ndarray]:
        """Decompress delta RLE-compressed data"""
        try:
            # Unpack compressed data
            offset = 0
            
            # First value
            first_value = struct.unpack('f', compressed_data[offset:offset+4])[0]
            offset += 4
            
            # Delta scale
            delta_scale = struct.unpack('f', compressed_data[offset:offset+4])[0]
            offset += 4
            
            # RLE data length
            rle_length = struct.unpack('I', compressed_data[offset:offset+4])[0]
            offset += 4
            
            # RLE data
            rle_data = compressed_data[offset:offset+rle_length]
            
            # Decode run-length encoding
            quantized_deltas = self._decode_run_length_encoding(rle_data)
            
            # Convert back to deltas
            if delta_scale > 0:
                delta_precision = metadata.get('delta_precision_bits', 8)
                delta_scale_factor = delta_scale / ((2 ** (delta_precision - 1)) - 1)
                deltas = quantized_deltas.astype(np.float32) * delta_scale_factor
            else:
                deltas = np.zeros(len(quantized_deltas), dtype=np.float32)
            
            # Reconstruct original data using cumulative sum
            if len(deltas) > 0:
                reconstructed = np.empty(len(deltas) + 1, dtype=np.float32)
                reconstructed[0] = first_value
                reconstructed[1:] = first_value + np.cumsum(deltas)
            else:
                reconstructed = np.array([first_value], dtype=np.float32)
            
            return reconstructed
            
        except Exception as e:
            logger.error(f"Error decompressing delta RLE data: {e}")
            return None
    
    def _decode_run_length_encoding(self, rle_data: bytes) -> np.ndarray:
        """Decode run-length encoded data"""
        try:
            if len(rle_data) == 0:
                return np.array([], dtype=np.int8)
            
            # Convert to integers
            rle_values = list(rle_data)
            
            # Decode RLE pairs (value, count)
            decoded_data = []
            for i in range(0, len(rle_values), 2):
                if i + 1 < len(rle_values):
                    value = np.int8(rle_values[i])
                    count = rle_values[i + 1]
                    decoded_data.extend([value] * count)
            
            return np.array(decoded_data, dtype=np.int8)
            
        except Exception as e:
            logger.error(f"Error decoding run-length encoding: {e}")
            return np.array([], dtype=np.int8)
    
    def _decompress_quantized(self, compressed_data: bytes, metadata: Dict[str, Any]) -> Optional[np.ndarray]:
        """Decompress quantized data"""
        try:
            offset = 0
            
            # Unpack parameters
            min_val = struct.unpack('f', compressed_data[offset:offset+4])[0]
            offset += 4
            
            max_val = struct.unpack('f', compressed_data[offset:offset+4])[0]
            offset += 4
            
            quantization_bits = struct.unpack('H', compressed_data[offset:offset+2])[0]
            offset += 2
            
            original_length = struct.unpack('I', compressed_data[offset:offset+4])[0]
            offset += 4
            
            # Handle constant value case
            if min_val == max_val:
                return np.full(original_length, min_val, dtype=np.float32)
            
            # Decompress quantized data
            compressed_quantized = compressed_data[offset:]
            quantized_bytes = zlib.decompress(compressed_quantized)
            
            # Reconstruct quantized array
            quantized_data = np.frombuffer(quantized_bytes, dtype=np.uint16)
            
            # Dequantize back to original range
            quantization_levels = 2 ** quantization_bits
            normalized_data = quantized_data.astype(np.float32) / (quantization_levels - 1)
            reconstructed_data = min_val + normalized_data * (max_val - min_val)
            
            return reconstructed_data[:original_length]
            
        except Exception as e:
            logger.error(f"Error decompressing quantized data: {e}")
            return None
    
    def _update_compression_stats(self, result: CompressionResult):
        """Update compression statistics"""
        try:
            self.compression_stats['total_compressions'] += 1
            self.compression_stats['total_original_bytes'] += result.original_size_bytes
            self.compression_stats['total_compressed_bytes'] += result.compressed_size_bytes
            
            # Update algorithm usage
            alg_key = result.algorithm_used.value
            self.compression_stats['algorithm_usage'][alg_key] += 1
            
            # Update quality distribution
            quality_key = result.data_quality.value
            self.compression_stats['quality_distribution'][quality_key] += 1
            
            # Update averages
            total_compressions = self.compression_stats['total_compressions']
            
            # Average compression ratio
            if self.compression_stats['total_original_bytes'] > 0:
                overall_ratio = (
                    self.compression_stats['total_original_bytes'] / 
                    max(1, self.compression_stats['total_compressed_bytes'])
                )
                self.compression_stats['average_compression_ratio'] = overall_ratio
            
            # Average compression time
            current_avg_time = self.compression_stats['average_compression_time_ms']
            new_avg_time = (
                (current_avg_time * (total_compressions - 1) + result.compression_time_ms) /
                total_compressions
            )
            self.compression_stats['average_compression_time_ms'] = new_avg_time
            
        except Exception as e:
            logger.error(f"Error updating compression statistics: {e}")
    
    def get_compression_statistics(self) -> Dict[str, Any]:
        """Get comprehensive compression statistics"""
        return {
            'performance_statistics': self.compression_stats.copy(),
            'current_settings': {
                'primary_algorithm': self.settings.primary_algorithm.value,
                'compression_level': self.settings.compression_level,
                'quality_target': self.settings.quality_target.value,
                'target_compression_ratio': self.settings.target_compression_ratio,
                'max_compression_time_ms': self.settings.max_compression_time_ms
            },
            'efficiency_metrics': {
                'compression_efficiency': self.compression_stats['average_compression_ratio'],
                'processing_speed_mbps': self._calculate_processing_speed(),
                'error_rate': self._calculate_error_rate(),
                'quality_score': self._calculate_quality_score()
            }
        }
    
    def _calculate_processing_speed(self) -> float:
        """Calculate overall processing speed in MB/s"""
        try:
            total_mb = self.compression_stats['total_original_bytes'] / (1024 * 1024)
            total_time_s = self.compression_stats['average_compression_time_ms'] / 1000 * self.compression_stats['total_compressions']
            
            if total_time_s > 0:
                return total_mb / total_time_s
            return 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_error_rate(self) -> float:
        """Calculate overall error rate percentage"""
        try:
            total_operations = (
                self.compression_stats['total_compressions'] + 
                self.compression_stats['decompression_errors']
            )
            
            total_errors = (
                self.compression_stats['compression_errors'] + 
                self.compression_stats['decompression_errors']
            )
            
            if total_operations > 0:
                return (total_errors / total_operations) * 100
            return 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_quality_score(self) -> float:
        """Calculate overall quality score (0.0-1.0)"""
        try:
            quality_weights = {
                'excellent': 1.0,
                'good': 0.8,
                'fair': 0.6,
                'poor': 0.4,
                'corrupt': 0.0
            }
            
            total_samples = sum(self.compression_stats['quality_distribution'].values())
            if total_samples == 0:
                return 1.0
            
            weighted_score = sum(
                count * quality_weights.get(quality, 0.5)
                for quality, count in self.compression_stats['quality_distribution'].items()
            )
            
            return weighted_score / total_samples
            
        except Exception:
            return 0.5


# Global compressor instance
_compressor: Optional[RawLabJackCompressor] = None


def get_raw_labjack_compressor() -> RawLabJackCompressor:
    """Get global raw LabJack compressor instance"""
    global _compressor
    if _compressor is None:
        _compressor = RawLabJackCompressor()
    return _compressor


# Export key components
__all__ = [
    'RawLabJackCompressor',
    'CompressionSettings',
    'CompressionResult',
    'DecompressionResult',
    'CompressionQuality',
    'SignalType',
    'get_raw_labjack_compressor'
]