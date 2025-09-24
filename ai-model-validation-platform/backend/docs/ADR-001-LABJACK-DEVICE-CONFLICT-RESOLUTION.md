# ADR-001: LabJack Device Conflict Resolution

## Status
**PROPOSED** - Awaiting implementation

## Context

The HIL testing system experiences device conflicts where the LabJack T7 hardware can only be claimed by one process at a time. The current architecture has multiple services attempting to access the device independently, resulting in `LJME_DEVICE_CURRENTLY_CLAIMED_BY_ANOTHER_PROCESS` errors and 0 detection events captured during HIL tests.

### Current Problems:
- Main FastAPI backend (PID 276320) claims the LabJack device through signal validation service
- Monitoring service thread cannot access the same device simultaneously 
- Multiple services create independent LabJack handles causing resource conflicts
- HIL testing fails due to missing real-time signal detection

### Technical Constraints:
- LabJack LJM library allows only one process to claim a device at a time
- HIL testing requires sub-5ms latency for signal detection
- High-frequency sampling up to 50 kHz needed
- Thread-safe operations required for concurrent access

## Decision

**We will implement a Shared Handle Pattern with a centralized LabJack Connection Manager.**

This decision provides:
1. **Single point of device access** - One shared handle across all services
2. **Thread-safe operations** - Mutex-protected device operations
3. **Minimal architectural changes** - Refactor existing services to use shared manager
4. **Optimal performance** - No IPC overhead for HIL testing requirements

## Alternatives Considered

### Alternative 1: Dedicated Hardware Process
**Description**: Separate process owns LabJack device, others communicate via IPC

**Pros:**
- Complete process isolation
- Fault tolerance (daemon restart doesn't affect main app)
- Scalable to multiple devices

**Cons:**
- IPC latency (10-50µs) may impact HIL testing performance
- Additional process management complexity
- Requires monitoring and restart logic

**Rejected because**: HIL testing latency requirements favor direct hardware access

### Alternative 2: Event-Driven Service Bus
**Description**: Centralized event bus coordinates all LabJack operations

**Pros:**
- Loose coupling between services
- Event-driven real-time processing
- Easy to add new consumers

**Cons:**
- Complex event routing logic
- Potential message delivery issues
- Higher latency than direct access

**Rejected because**: Adds unnecessary complexity for the device conflict problem

### Alternative 3: HTTP API Wrapper
**Description**: Single HTTP service wraps LabJack operations

**Pros:**
- Simple REST interface
- Language agnostic
- Easy debugging

**Cons:**
- HTTP latency (1-5ms) too high for HIL requirements
- Network overhead
- Not suitable for high-frequency sampling

**Rejected because**: Violates HIL testing performance requirements

## Implementation Plan

### Phase 1: Shared Handle Implementation

1. **Create LabJack Connection Manager** (`services/labjack_connection_manager.py`)
   ```python
   class LabJackConnectionManager:
       _instance = None
       _handle = None
       _lock = threading.RLock()
       
       @classmethod
       def get_instance(cls):
           if cls._instance is None:
               cls._instance = cls()
           return cls._instance
       
       def get_shared_handle(self):
           with self._lock:
               if self._handle is None:
                   self._handle = ljm.openS("ANY", "ANY", "ANY")
               return self._handle
   ```

2. **Refactor Existing Services**
   - `LabJackHardwareService`: Remove direct `ljm.openS()`, use shared manager
   - `RealLabJackService`: Replace handle creation with shared access
   - `SignalValidationService`: Update to use connection manager
   - `LabJackMonitoringService`: Remove independent connection

3. **Thread-Safe Operation Wrapper**
   ```python
   class ThreadSafeLabJackOperations:
       def __init__(self, connection_manager):
           self.connection_manager = connection_manager
       
       def read_voltage(self, channel: str) -> float:
           with self.connection_manager._lock:
               handle = self.connection_manager.get_shared_handle()
               return ljm.eReadName(handle, channel)
   ```

### Phase 2: Testing and Validation

1. **Unit Tests**
   - Mock LabJack behavior for testing
   - Concurrent access simulation
   - Thread safety validation

2. **Integration Tests**
   - Multi-service startup sequence
   - HIL testing workflow
   - Error recovery scenarios

3. **Performance Tests**
   - Latency measurements
   - High-frequency sampling
   - Load testing

### Phase 3: Migration Strategy

1. **Backward Compatibility**
   - Keep existing service interfaces
   - Gradual migration of device access points
   - Feature flags for rollback

2. **Deployment Plan**
   - Test environment validation
   - Staged rollout
   - Monitoring and rollback procedures

## Consequences

### Positive Consequences:
- ✅ **Resolves device conflicts** - Single shared handle eliminates competition
- ✅ **Maintains HIL performance** - No IPC overhead, direct hardware access
- ✅ **Thread-safe operations** - Mutex protection prevents race conditions  
- ✅ **Minimal code changes** - Existing service interfaces preserved
- ✅ **Improved reliability** - Centralized error handling and recovery

### Negative Consequences:
- ⚠️ **Service coupling** - All services depend on shared connection manager
- ⚠️ **Single point of failure** - Shared handle failure affects all services
- ⚠️ **Thread contention** - High-frequency access may cause blocking
- ⚠️ **Resource management** - Need careful handle lifecycle management

### Risks and Mitigations:

**Risk**: Thread contention under heavy load
**Mitigation**: 
- Use fine-grained locking
- Implement read/write lock separation
- Add performance monitoring

**Risk**: Shared handle corruption
**Mitigation**:
- Add handle validation checks
- Implement automatic reconnection
- Error isolation and recovery

**Risk**: Service startup dependencies
**Mitigation**:
- Lazy initialization of shared handle
- Graceful degradation for unavailable hardware
- Clear dependency documentation

## Future Considerations

### Upgrade Path to Process Separation
If performance or reliability issues arise, the architecture can be upgraded to dedicated process pattern:

1. **Phase A**: Implement daemon mode alongside shared handle
2. **Phase B**: Add configuration-based mode switching  
3. **Phase C**: Gradual migration to process separation
4. **Phase D**: Remove shared handle mode if no longer needed

### Multi-Device Support
The connection manager can be extended to support multiple LabJack devices:
```python
class MultiDeviceLabJackManager:
    def __init__(self):
        self.devices = {}  # device_id -> handle
        
    def get_device_handle(self, device_id: str):
        # Device-specific handle management
```

### Performance Optimization
Future optimizations may include:
- Lock-free circular buffers for high-frequency data
- NUMA-aware threading for multi-core systems
- Hardware-specific optimizations

## References
- [LabJack LJM Library Documentation](https://labjack.com/support/software/api/ljm)
- [Threading Best Practices in Python](https://docs.python.org/3/library/threading.html)
- [HIL Testing Requirements Specification](./HIL_TESTING_REQUIREMENTS.md)

---

**Decision Date**: 2024-09-16
**Last Updated**: 2024-09-16
**Next Review**: 2024-10-16