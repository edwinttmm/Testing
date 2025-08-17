# Architecture Decision Records (ADRs)

## ADR-001: Database Technology Selection

**Status:** Accepted  
**Date:** 2024-08-17  
**Deciders:** System Architecture Team, Database Team  

### Context
The VRU detection system requires a robust database solution to handle:
- High-volume video metadata and detection results
- Complex temporal queries for latency analysis
- Real-time data ingestion from detection pipelines
- ACID compliance for critical safety data
- Scalability for automotive industry adoption

### Decision
We will use **PostgreSQL 14+** as the primary database with the following configuration:
- Primary-replica setup for read scaling
- Connection pooling with PgBouncer
- Specialized indexing for temporal queries
- JSONB for flexible metadata storage

### Rationale

**Considered Options:**
1. **PostgreSQL** ✓ Selected
2. **MySQL** - Rejected
3. **MongoDB** - Rejected
4. **TimescaleDB** - Considered for time-series data

**PostgreSQL Advantages:**
- ACID compliance critical for safety-critical automotive data
- Advanced indexing (GIN, GiST) for complex queries
- JSONB support for flexible metadata without schema rigidity
- Mature ecosystem with proven scalability
- Strong consistency guarantees
- PostGIS extension available for spatial data
- Excellent performance for analytical workloads

**MySQL Disadvantages:**
- Limited JSON support compared to PostgreSQL JSONB
- Less sophisticated indexing options
- MyISAM tables don't support transactions

**MongoDB Disadvantages:**
- Eventual consistency model unsuitable for safety-critical data
- Complex query patterns for relational-style analytics
- Memory usage concerns for large datasets

**TimescaleDB Consideration:**
- Excellent for time-series data but adds complexity
- PostgreSQL native capabilities sufficient for current requirements
- Can be evaluated as extension if needed

### Consequences

**Positive:**
- Strong data consistency for safety-critical applications
- Rich query capabilities for complex analytics
- Excellent tooling and monitoring ecosystem
- Horizontal scaling through read replicas
- Future-proof with advanced features (parallel queries, partitioning)

**Negative:**
- Learning curve for teams familiar with NoSQL
- Requires careful query optimization for large datasets
- Write scaling requires application-level sharding

**Migration Impact:**
- Existing SQLAlchemy models require minimal changes
- Current application already uses PostgreSQL-compatible features
- No breaking changes to API layer

---

## ADR-002: Real-time Processing Architecture

**Status:** Accepted  
**Date:** 2024-08-17  
**Deciders:** System Architecture Team, ML Engineering Team  

### Context
The system requires real-time video processing with strict latency requirements:
- <50ms processing latency for safety applications
- Support for multiple concurrent video streams
- GPU acceleration for ML inference
- Scalable processing pipeline
- Integration with existing FastAPI backend

### Decision
We will implement an **Event-Driven Microservices Architecture** using:
- **Message Queue:** RabbitMQ for reliable message delivery
- **Processing Engine:** Dedicated GPU-enabled containers
- **Coordination:** AsyncIO for concurrent processing
- **Communication:** WebSocket for real-time updates

### Rationale

**Considered Options:**
1. **Event-Driven Microservices** ✓ Selected
2. **Monolithic Processing** - Rejected
3. **Apache Kafka + Stream Processing** - Considered
4. **Direct API Calls** - Rejected

**Event-Driven Advantages:**
- Decouples video processing from main API
- Enables horizontal scaling of processing nodes
- Message persistence ensures no data loss
- Back-pressure handling for resource constraints
- Easy to add new processing stages

**Monolithic Processing Disadvantages:**
- Tight coupling between components
- Difficult to scale processing independently
- Single point of failure
- Resource contention between API and processing

**Kafka Consideration:**
- Excellent for high-throughput scenarios
- Complex setup and operational overhead
- RabbitMQ sufficient for current volume requirements
- Can migrate to Kafka if throughput demands increase

**Direct API Disadvantages:**
- Synchronous blocking affects API responsiveness
- No retry mechanism for failed processing
- Difficult to implement back-pressure

### Consequences

**Positive:**
- Independent scaling of processing components
- Fault tolerance through message persistence
- Clear separation of concerns
- Easy to add new processing algorithms
- Monitoring and debugging capabilities

**Negative:**
- Added complexity of distributed system
- Network latency between components
- Message queue becomes critical dependency
- Eventual consistency considerations

**Implementation Requirements:**
- RabbitMQ cluster setup for high availability
- GPU resource management and allocation
- Comprehensive monitoring of message flows
- Error handling and dead letter queues

---

## ADR-003: Frontend State Management

**Status:** Accepted  
**Date:** 2024-08-17  
**Deciders:** Frontend Team, UX Team  

### Context
The React frontend needs to manage complex state including:
- Real-time video processing updates
- Large datasets (video lists, detection results)
- User authentication and authorization
- WebSocket connections for live updates
- Form state for complex project configurations

### Decision
We will use **React Query (TanStack Query) + Zustand** combination:
- **React Query:** Server state management and caching
- **Zustand:** Client state management (UI state, user preferences)
- **WebSocket integration:** Custom hooks for real-time updates
- **Form management:** React Hook Form for complex forms

### Rationale

**Considered Options:**
1. **React Query + Zustand** ✓ Selected
2. **Redux Toolkit** - Rejected
3. **Apollo Client** - Rejected
4. **SWR + Context API** - Considered

**React Query + Zustand Advantages:**
- React Query handles server state caching and synchronization
- Zustand provides simple client state management
- Excellent TypeScript support
- Built-in loading and error states
- Optimistic updates support
- Automatic background refetching

**Redux Toolkit Disadvantages:**
- Boilerplate code for simple state updates
- Steeper learning curve
- Overkill for current application complexity
- Requires additional middleware for async operations

**Apollo Client Disadvantages:**
- GraphQL dependency (we use REST APIs)
- Larger bundle size
- Complex caching strategies

**SWR + Context Consideration:**
- SWR good for data fetching but less feature-rich than React Query
- Context API can become unwieldy for complex state
- No built-in optimistic updates

### Consequences

**Positive:**
- Reduced boilerplate for API interactions
- Automatic caching and revalidation
- Great developer experience with DevTools
- Type-safe state management
- Easy to implement real-time features

**Negative:**
- Learning curve for team unfamiliar with React Query
- Additional dependencies in bundle
- Need to carefully manage cache invalidation

**Migration Strategy:**
- Gradual migration from existing Context-based state
- Start with new features using React Query
- Migrate existing API calls to React Query hooks
- Preserve existing form state management

---

## ADR-004: Authentication and Authorization

**Status:** Accepted  
**Date:** 2024-08-17  
**Deciders:** Security Team, Backend Team  

### Context
The system requires secure authentication and fine-grained authorization:
- Role-based access control (Admin, Engineer, Analyst, User)
- API endpoint protection
- Resource-level permissions (project ownership)
- Session management for web application
- Integration with enterprise identity providers (future)

### Decision
We will implement **JWT-based Authentication with RBAC**:
- **Authentication:** JWT tokens with refresh mechanism
- **Authorization:** Role-Based Access Control (RBAC)
- **Storage:** HTTPOnly cookies for web, localStorage for mobile
- **Backend:** FastAPI dependency injection for route protection
- **Future:** OIDC integration for enterprise SSO

### Rationale

**Considered Options:**
1. **JWT + RBAC** ✓ Selected
2. **Session-based Authentication** - Rejected
3. **OAuth 2.0 + External Provider** - Future consideration
4. **API Keys Only** - Rejected

**JWT + RBAC Advantages:**
- Stateless authentication scales horizontally
- Self-contained tokens reduce database queries
- Standard format with good library support
- Flexible payload for user claims and roles
- Easy integration with frontend frameworks

**Session-based Disadvantages:**
- Requires session storage (Redis/Database)
- Difficult to scale across multiple servers
- CSRF vulnerability considerations
- Less suitable for API-first architecture

**OAuth 2.0 Consideration:**
- Required for enterprise integration
- Will be implemented as additional option
- JWT structure allows easy migration

**API Keys Disadvantages:**
- No user context or roles
- Difficult to revoke granularly
- Not suitable for user-facing applications

### Consequences

**Positive:**
- Scalable authentication system
- Clear role-based permissions
- Mobile app friendly
- Standard security practices
- Audit trail capabilities

**Negative:**
- Token management complexity
- Refresh token rotation required
- Potential security risks if not implemented correctly

**Security Measures:**
- Short-lived access tokens (15 minutes)
- Secure refresh token rotation
- HTTPOnly cookies for web applications
- Rate limiting for authentication endpoints
- Comprehensive audit logging

**Implementation Details:**
```python
# Role definitions
class UserRole(Enum):
    ADMIN = "admin"          # Full system access
    ENGINEER = "engineer"    # Project management, video upload
    ANALYST = "analyst"      # Results analysis, reporting
    USER = "user"           # Read-only access

# Permission matrix
ROLE_PERMISSIONS = {
    UserRole.ADMIN: ["*"],
    UserRole.ENGINEER: [
        "projects:create", "projects:edit", "projects:delete",
        "videos:upload", "videos:delete",
        "test_sessions:create", "test_sessions:run"
    ],
    UserRole.ANALYST: [
        "projects:view", "videos:view",
        "test_sessions:view", "results:view", "results:export"
    ],
    UserRole.USER: [
        "projects:view", "videos:view", "results:view"
    ]
}
```

---

## ADR-005: Video Storage Strategy

**Status:** Accepted  
**Date:** 2024-08-17  
**Deciders:** Infrastructure Team, System Architecture Team  

### Context
The system needs to handle large video files efficiently:
- Video files ranging from 100MB to 10GB
- Concurrent uploads from multiple users
- Long-term storage with archival requirements
- Content delivery for playback and analysis
- Cost optimization for storage tiers

### Decision
We will use **S3-Compatible Object Storage** with intelligent tiering:
- **Primary Storage:** S3 Standard for active videos
- **Archive Storage:** Glacier for videos >90 days old
- **CDN:** CloudFront for video delivery
- **Upload:** Direct S3 upload with presigned URLs
- **Processing:** Lambda/Function triggers for metadata extraction

### Rationale

**Considered Options:**
1. **S3-Compatible Object Storage** ✓ Selected
2. **Network File System (NFS)** - Rejected
3. **Block Storage (EBS)** - Rejected
4. **Hybrid Local + Cloud** - Considered

**S3 Advantages:**
- Virtually unlimited scalability
- Built-in redundancy and durability (99.999999999%)
- Cost-effective storage tiers
- Global content delivery through CDN
- Event-driven processing triggers
- Integration with cloud ecosystem

**NFS Disadvantages:**
- Limited scalability
- Single points of failure
- Manual backup and redundancy
- Higher operational overhead

**Block Storage Disadvantages:**
- Limited to single instance attachment
- Manual scaling required
- Higher cost per GB
- No built-in content delivery

**Hybrid Consideration:**
- Local storage for active processing
- Could reduce latency for frequent access
- Added complexity of data synchronization
- Cost benefits unclear with current scale

### Consequences

**Positive:**
- Infinite scalability for storage growth
- Automatic durability and backup
- Cost optimization through storage tiers
- Global content delivery
- Event-driven processing capabilities

**Negative:**
- Network latency for video access
- Data transfer costs for large files
- Dependency on cloud provider
- Need for robust error handling

**Implementation Strategy:**
```javascript
// Upload workflow
1. Client requests upload URL
2. Backend generates presigned S3 URL
3. Client uploads directly to S3
4. S3 event triggers metadata extraction
5. Backend updates database with file info
6. Background job processes video for thumbnails

// Storage lifecycle
- Standard: 0-30 days (frequent access)
- Infrequent Access: 30-90 days (occasional access)
- Glacier: 90+ days (archival, rare access)
```

**Cost Optimization:**
- Intelligent tiering based on access patterns
- Multipart uploads for large files
- Compression for archived videos
- Regular cleanup of incomplete uploads

---

## ADR Template for Future Decisions

### Status
[Proposed | Accepted | Rejected | Deprecated | Superseded]

### Date
YYYY-MM-DD

### Deciders
List of people involved in the decision

### Context
Describe the forces at play, including technological, political, social, and project local. These forces are probably in tension, and should be called out as such.

### Decision
State the architecture decision and provide detailed justification.

### Rationale
Describe why you selected a solution and rejected alternatives.

**Considered Options:**
1. Option 1 - Status
2. Option 2 - Status  
3. Option 3 - Status

**Selection Criteria:**
- Criterion 1
- Criterion 2
- Criterion 3

**Detailed Analysis:**
Provide detailed comparison of options against criteria.

### Consequences
Describe the resulting context, after applying the decision. All consequences should be listed here, not just the "positive" ones.

**Positive:**
- Benefit 1
- Benefit 2

**Negative:**
- Cost 1
- Risk 1

**Neutral:**
- Trade-off 1

### Implementation Notes
Specific technical details, timelines, or migration strategies.

### Related Decisions
Link to related ADRs or reference external decisions.

### Compliance and Validation
How will we verify this decision was implemented correctly?