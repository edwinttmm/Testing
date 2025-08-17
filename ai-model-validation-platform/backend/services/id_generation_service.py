import time
import uuid
import secrets
import hashlib
import threading
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class IDType(Enum):
    VIDEO = "video"
    DETECTION = "detection" 
    SESSION = "session"
    PROJECT = "project"
    GROUND_TRUTH = "ground_truth"
    SIGNAL_EVENT = "signal_event"
    AUDIT_LOG = "audit_log"

@dataclass
class IDGenerationConfig:
    """Configuration for ID generation strategies"""
    include_timestamp: bool = True
    include_node_id: bool = True
    include_sequence: bool = True
    use_secure_random: bool = True
    collision_detection: bool = True

class NodeIdentifier:
    """Manages node identification for distributed ID generation"""
    
    def __init__(self):
        self._node_id = None
        self._lock = threading.Lock()
    
    def get_node_id(self) -> str:
        """Get or generate unique node identifier"""
        if self._node_id is None:
            with self._lock:
                if self._node_id is None:
                    self._node_id = self._generate_node_id()
        return self._node_id
    
    def _generate_node_id(self) -> str:
        """Generate unique node identifier"""
        # Use MAC address and hostname for uniqueness
        import socket
        import os
        
        try:
            hostname = socket.gethostname()
            process_id = os.getpid()
            
            # Create hash from system information
            system_info = f"{hostname}:{process_id}:{time.time()}"
            hash_digest = hashlib.md5(system_info.encode()).hexdigest()
            
            # Use first 8 characters as node ID
            return hash_digest[:8].upper()
            
        except Exception as e:
            logger.warning(f"Could not generate system-based node ID: {e}")
            # Fallback to random node ID
            return secrets.token_hex(4).upper()

class SequenceGenerator:
    """Thread-safe sequence number generator"""
    
    def __init__(self):
        self._sequences = {}
        self._lock = threading.Lock()
    
    def get_next_sequence(self, namespace: str = "default") -> int:
        """Get next sequence number for a namespace"""
        with self._lock:
            if namespace not in self._sequences:
                self._sequences[namespace] = 0
            
            self._sequences[namespace] += 1
            return self._sequences[namespace]
    
    def reset_sequence(self, namespace: str = "default"):
        """Reset sequence counter for a namespace"""
        with self._lock:
            self._sequences[namespace] = 0

class CollisionDetector:
    """Detects and prevents ID collisions"""
    
    def __init__(self, max_cache_size: int = 10000):
        self.generated_ids = set()
        self.max_cache_size = max_cache_size
        self._lock = threading.Lock()
    
    def check_collision(self, generated_id: str) -> bool:
        """Check if ID has been generated before"""
        with self._lock:
            if generated_id in self.generated_ids:
                return True
            
            # Add to cache
            self.generated_ids.add(generated_id)
            
            # Prevent cache from growing too large
            if len(self.generated_ids) > self.max_cache_size:
                # Remove oldest half
                ids_list = list(self.generated_ids)
                self.generated_ids = set(ids_list[len(ids_list)//2:])
            
            return False

class TimestampGenerator:
    """High-precision timestamp generation"""
    
    def __init__(self):
        self.last_timestamp = 0
        self._lock = threading.Lock()
    
    def get_timestamp_ms(self) -> int:
        """Get current timestamp in milliseconds"""
        return int(time.time() * 1000)
    
    def get_timestamp_us(self) -> int:
        """Get current timestamp in microseconds"""
        return int(time.time_ns() // 1000)
    
    def get_monotonic_timestamp(self) -> int:
        """Get monotonic timestamp that never goes backwards"""
        with self._lock:
            current_timestamp = self.get_timestamp_ms()
            
            if current_timestamp <= self.last_timestamp:
                current_timestamp = self.last_timestamp + 1
            
            self.last_timestamp = current_timestamp
            return current_timestamp

class IDGenerator:
    """Main ID generation system with multiple strategies"""
    
    def __init__(self, config: IDGenerationConfig = None):
        self.config = config or IDGenerationConfig()
        self.node_identifier = NodeIdentifier()
        self.sequence_generator = SequenceGenerator()
        self.collision_detector = CollisionDetector()
        self.timestamp_generator = TimestampGenerator()
        
        # ID type specific configurations
        self.type_configs = {
            IDType.VIDEO: {"strategy": "uuid4", "prefix": "vid"},
            IDType.DETECTION: {"strategy": "snowflake", "prefix": "det"},
            IDType.SESSION: {"strategy": "composite", "prefix": "ses"},
            IDType.PROJECT: {"strategy": "uuid4", "prefix": "prj"},
            IDType.GROUND_TRUTH: {"strategy": "uuid4", "prefix": "gt"},
            IDType.SIGNAL_EVENT: {"strategy": "snowflake", "prefix": "sig"},
            IDType.AUDIT_LOG: {"strategy": "snowflake", "prefix": "aud"}
        }
    
    def generate_id(self, id_type: IDType, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate ID based on type and context"""
        type_config = self.type_configs.get(id_type, {"strategy": "uuid4", "prefix": ""})
        strategy = type_config["strategy"]
        prefix = type_config.get("prefix", "")
        
        # Generate ID based on strategy
        if strategy == "uuid4":
            generated_id = self._generate_uuid4_id(prefix, context)
        elif strategy == "snowflake":
            generated_id = self._generate_snowflake_id(prefix, context)
        elif strategy == "composite":
            generated_id = self._generate_composite_id(prefix, context)
        else:
            generated_id = self._generate_uuid4_id(prefix, context)
        
        # Check for collisions if enabled
        if self.config.collision_detection:
            retry_count = 0
            max_retries = 5
            
            while self.collision_detector.check_collision(generated_id) and retry_count < max_retries:
                logger.warning(f"ID collision detected for {generated_id}, regenerating...")
                retry_count += 1
                
                if strategy == "uuid4":
                    generated_id = self._generate_uuid4_id(prefix, context)
                elif strategy == "snowflake":
                    generated_id = self._generate_snowflake_id(prefix, context)
                elif strategy == "composite":
                    generated_id = self._generate_composite_id(prefix, context)
            
            if retry_count >= max_retries:
                logger.error(f"Failed to generate unique ID after {max_retries} attempts")
                # Fallback to UUID4 with timestamp
                generated_id = f"{prefix}_{uuid.uuid4()}_{int(time.time())}"
        
        logger.debug(f"Generated {id_type.value} ID: {generated_id}")
        return generated_id
    
    def _generate_uuid4_id(self, prefix: str = "", context: Optional[Dict] = None) -> str:
        """Generate UUID4-based ID"""
        base_id = str(uuid.uuid4())
        
        if prefix:
            return f"{prefix}_{base_id}"
        return base_id
    
    def _generate_snowflake_id(self, prefix: str = "", context: Optional[Dict] = None) -> str:
        """Generate Snowflake-style ID (timestamp + node + sequence)"""
        timestamp_ms = self.timestamp_generator.get_monotonic_timestamp()
        node_id = int(self.node_identifier.get_node_id()[:4], 16)  # Use first 4 chars as hex
        sequence = self.sequence_generator.get_next_sequence("snowflake")
        
        # Snowflake format: 42 bits timestamp + 10 bits node + 12 bits sequence
        snowflake_id = (timestamp_ms << 22) | (node_id << 12) | (sequence & 0xFFF)
        
        if prefix:
            return f"{prefix}_{snowflake_id:016x}"
        return f"{snowflake_id:016x}"
    
    def _generate_composite_id(self, prefix: str = "", context: Optional[Dict] = None) -> str:
        """Generate composite ID with multiple components"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Add context-specific components
        components = [timestamp]
        
        if context:
            project_id = context.get("project_id")
            if project_id:
                # Use short hash of project ID
                project_hash = hashlib.md5(project_id.encode()).hexdigest()[:6]
                components.append(project_hash)
        
        # Add random component for uniqueness
        random_suffix = secrets.token_hex(4)
        components.append(random_suffix)
        
        composite_id = "_".join(components)
        
        if prefix:
            return f"{prefix}_{composite_id}"
        return composite_id
    
    # Convenience methods for specific ID types
    def generate_video_id(self) -> str:
        """Generate video ID"""
        return self.generate_id(IDType.VIDEO)
    
    def generate_detection_id(self, frame_number: Optional[int] = None) -> str:
        """Generate detection ID with optional frame context"""
        context = {"frame_number": frame_number} if frame_number else None
        return self.generate_id(IDType.DETECTION, context)
    
    def generate_session_id(self, project_id: str) -> str:
        """Generate session ID with project context"""
        context = {"project_id": project_id}
        return self.generate_id(IDType.SESSION, context)
    
    def generate_project_id(self) -> str:
        """Generate project ID"""
        return self.generate_id(IDType.PROJECT)
    
    def generate_ground_truth_id(self) -> str:
        """Generate ground truth object ID"""
        return self.generate_id(IDType.GROUND_TRUTH)
    
    def generate_signal_event_id(self) -> str:
        """Generate signal event ID"""
        return self.generate_id(IDType.SIGNAL_EVENT)
    
    def generate_audit_log_id(self) -> str:
        """Generate audit log ID"""
        return self.generate_id(IDType.AUDIT_LOG)

class IDValidator:
    """Validates and analyzes generated IDs"""
    
    @staticmethod
    def validate_uuid4(id_string: str) -> bool:
        """Validate if string is a valid UUID4"""
        try:
            # Remove prefix if present
            if "_" in id_string:
                uuid_part = id_string.split("_", 1)[1]
            else:
                uuid_part = id_string
            
            uuid.UUID(uuid_part, version=4)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_snowflake(id_string: str) -> bool:
        """Validate if string is a valid Snowflake ID"""
        try:
            # Remove prefix if present
            if "_" in id_string:
                snowflake_part = id_string.split("_", 1)[1]
            else:
                snowflake_part = id_string
            
            # Should be 16 character hex string
            if len(snowflake_part) == 16:
                int(snowflake_part, 16)
                return True
            return False
        except ValueError:
            return False
    
    @staticmethod
    def extract_timestamp_from_snowflake(id_string: str) -> Optional[datetime]:
        """Extract timestamp from Snowflake ID"""
        try:
            if "_" in id_string:
                snowflake_part = id_string.split("_", 1)[1]
            else:
                snowflake_part = id_string
            
            snowflake_int = int(snowflake_part, 16)
            timestamp_ms = snowflake_int >> 22
            
            return datetime.fromtimestamp(timestamp_ms / 1000)
        except (ValueError, OSError):
            return None
    
    @staticmethod
    def get_id_info(id_string: str) -> Dict[str, Any]:
        """Get information about an ID"""
        info = {
            "id": id_string,
            "valid": False,
            "type": "unknown",
            "timestamp": None,
            "components": {}
        }
        
        # Check for prefix
        if "_" in id_string:
            parts = id_string.split("_", 1)
            info["prefix"] = parts[0]
            main_part = parts[1]
        else:
            info["prefix"] = None
            main_part = id_string
        
        # Validate different formats
        if IDValidator.validate_uuid4(id_string):
            info["valid"] = True
            info["type"] = "uuid4"
        elif IDValidator.validate_snowflake(id_string):
            info["valid"] = True
            info["type"] = "snowflake"
            info["timestamp"] = IDValidator.extract_timestamp_from_snowflake(id_string)
        
        return info

# Global ID generator instance
_global_id_generator = None
_generator_lock = threading.Lock()

def get_global_id_generator() -> IDGenerator:
    """Get global ID generator instance (singleton)"""
    global _global_id_generator
    
    if _global_id_generator is None:
        with _generator_lock:
            if _global_id_generator is None:
                config = IDGenerationConfig(
                    include_timestamp=True,
                    include_node_id=True,
                    include_sequence=True,
                    use_secure_random=True,
                    collision_detection=True
                )
                _global_id_generator = IDGenerator(config)
    
    return _global_id_generator

# Convenience functions using global generator
def generate_unique_id(id_type: IDType, context: Optional[Dict] = None) -> str:
    """Generate unique ID using global generator"""
    generator = get_global_id_generator()
    return generator.generate_id(id_type, context)

def generate_video_id() -> str:
    """Generate unique video ID"""
    return generate_unique_id(IDType.VIDEO)

def generate_detection_id() -> str:
    """Generate unique detection ID"""
    return generate_unique_id(IDType.DETECTION)

def generate_session_id(project_id: str) -> str:
    """Generate unique session ID with project context"""
    return generate_unique_id(IDType.SESSION, {"project_id": project_id})

def generate_project_id() -> str:
    """Generate unique project ID"""
    return generate_unique_id(IDType.PROJECT)

def generate_ground_truth_id() -> str:
    """Generate unique ground truth ID"""
    return generate_unique_id(IDType.GROUND_TRUTH)

def generate_signal_event_id() -> str:
    """Generate unique signal event ID"""
    return generate_unique_id(IDType.SIGNAL_EVENT)

def generate_audit_log_id() -> str:
    """Generate unique audit log ID"""
    return generate_unique_id(IDType.AUDIT_LOG)

# Performance testing and monitoring
class IDGenerationMetrics:
    """Collect metrics on ID generation performance"""
    
    def __init__(self):
        self.generation_count = 0
        self.collision_count = 0
        self.total_generation_time = 0.0
        self.max_generation_time = 0.0
        self.min_generation_time = float('inf')
        self._lock = threading.Lock()
    
    def record_generation(self, generation_time: float, had_collision: bool = False):
        """Record ID generation metrics"""
        with self._lock:
            self.generation_count += 1
            self.total_generation_time += generation_time
            
            if had_collision:
                self.collision_count += 1
            
            self.max_generation_time = max(self.max_generation_time, generation_time)
            self.min_generation_time = min(self.min_generation_time, generation_time)
    
    def get_statistics(self) -> Dict[str, float]:
        """Get generation statistics"""
        with self._lock:
            if self.generation_count == 0:
                return {"count": 0}
            
            return {
                "total_generated": self.generation_count,
                "collision_rate": self.collision_count / self.generation_count,
                "average_generation_time_ms": (self.total_generation_time / self.generation_count) * 1000,
                "max_generation_time_ms": self.max_generation_time * 1000,
                "min_generation_time_ms": self.min_generation_time * 1000
            }
    
    def reset(self):
        """Reset all metrics"""
        with self._lock:
            self.generation_count = 0
            self.collision_count = 0
            self.total_generation_time = 0.0
            self.max_generation_time = 0.0
            self.min_generation_time = float('inf')

# Global metrics instance
_global_metrics = IDGenerationMetrics()

def get_id_generation_metrics() -> Dict[str, float]:
    """Get global ID generation metrics"""
    return _global_metrics.get_statistics()

def reset_id_generation_metrics():
    """Reset global ID generation metrics"""
    _global_metrics.reset()