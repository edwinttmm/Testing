# ADR-002: Enhanced WebSocket Architecture

## Status
Proposed

## Context
The current WebSocket implementation uses basic Socket.IO with limited scalability and room management. For real-time annotation collaboration, detection streaming, and project progress updates, we need a more robust WebSocket architecture that can handle multiple concurrent users and scale horizontally.

## Decision
Implement an enhanced WebSocket architecture using:
1. **Redis pub/sub** for cross-instance communication and horizontal scaling
2. **Structured room management** with project-based, session-based, and user-based rooms
3. **Event broadcasting service** for centralized real-time updates
4. **Connection state management** with user context and session tracking

### Key Components:
- `ScalableSocketIOManager` with Redis backend for multi-instance support
- `EventBroadcastService` for structured event broadcasting
- Enhanced connection handling with authentication and user context
- Room-based subscriptions for different types of real-time updates

## Consequences

### Positive:
- **Horizontal scalability** through Redis pub/sub backend
- **Structured room management** enabling targeted broadcasts
- **Enhanced user experience** with real-time collaboration features
- **Centralized event broadcasting** simplifying real-time update logic
- **Connection resilience** with proper state management and reconnection handling

### Negative:
- **Infrastructure complexity** requiring Redis deployment and management
- **Increased latency** due to Redis pub/sub overhead
- **Memory usage** for connection state and room management
- **Development complexity** for handling distributed WebSocket scenarios

### Risks:
- **Redis single point of failure** without proper clustering
- **Connection flooding** without proper rate limiting
- **Memory leaks** from improper room cleanup
- **Race conditions** in distributed event broadcasting

## Alternatives Considered

### 1. Basic Socket.IO without Redis
**Rejected** - Would not scale beyond single instance and lacks proper room management.

### 2. Server-Sent Events (SSE)
**Rejected** - One-way communication insufficient for collaborative features requiring bidirectional updates.

### 3. WebSocket with custom protocol
**Rejected** - Would require significant development effort and lack the ecosystem support of Socket.IO.

### 4. GraphQL Subscriptions
**Considered** - Could work but adds complexity and doesn't integrate as well with existing FastAPI architecture.

## Technical Specifications

### Room Structure:
- `project_{project_id}` - Project-wide updates
- `annotation_{session_id}` - Annotation collaboration
- `detection_stream_{test_session_id}` - Real-time detection events
- `user_{user_id}` - User-specific notifications

### Event Types:
- `connection_status` - Connection state updates
- `annotation_update` - Real-time annotation changes
- `detection_event` - Live detection results
- `project_progress_update` - Project progress notifications
- `annotation_validated` - Validation results

## Implementation Notes
- Use Redis Sentinel for high availability
- Implement exponential backoff for reconnection logic
- Add rate limiting per connection (100 events/second)
- Monitor Redis memory usage and implement cleanup policies
- Use structured logging for WebSocket events debugging