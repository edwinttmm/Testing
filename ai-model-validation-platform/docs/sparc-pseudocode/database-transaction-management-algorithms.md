# SPARC Pseudocode Phase: Database Transaction Management Algorithms

## Overview
Comprehensive database transaction management algorithms including ACID compliance, concurrency control, deadlock prevention, and distributed transaction coordination.

## 1. TRANSACTION MANAGEMENT ALGORITHMS

### 1.1 Universal Transaction Manager Algorithm

```
ALGORITHM: ExecuteTransaction
INPUT: operations (List<DatabaseOperation>), isolation_level (IsolationLevel), timeout_ms (int), options (TransactionOptions)
OUTPUT: transaction_result (TransactionResult) or error (TransactionError)

PRECONDITIONS:
    - operations list is not empty
    - isolation_level is valid
    - timeout_ms > 0

BEGIN
    transaction_id ← GenerateTransactionID()
    transaction_start_time ← CurrentTimestamp()
    transaction_context ← InitializeTransactionContext(transaction_id, isolation_level, timeout_ms)
    
    // Phase 1: Transaction Initialization
    connection ← AcquireConnection(options.connection_pool)
    IF connection is null THEN
        RETURN TransactionError("Failed to acquire database connection")
    END IF
    
    TRY
        // Set isolation level
        SetIsolationLevel(connection, isolation_level)
        
        // Begin transaction
        BeginTransaction(connection, options)
        
        // Phase 2: Deadlock Prevention - Sort operations by resource
        IF options.enable_deadlock_prevention THEN
            operations ← SortOperationsByResource(operations)
        END IF
        
        // Phase 3: Acquire locks in predetermined order
        acquired_locks ← EmptyList()
        
        IF options.enable_pessimistic_locking THEN
            FOR EACH operation IN operations DO
                locks ← DetermineLocks(operation)
                FOR EACH lock IN locks DO
                    acquired_lock ← AcquireLock(connection, lock, timeout_ms)
                    IF acquired_lock is null THEN
                        ReleaseLocks(acquired_locks)
                        THROW LockAcquisitionTimeoutException("Failed to acquire lock: " + lock.resource)
                    END IF
                    acquired_locks.Add(acquired_lock)
                END FOR
            END FOR
        END IF
        
        // Phase 4: Execute operations with optimistic concurrency control
        operation_results ← EmptyList()
        savepoint_counter ← 0
        
        FOR EACH operation IN operations DO
            operation_start_time ← CurrentTimestamp()
            
            // Create savepoint for partial rollback
            IF options.enable_savepoints THEN
                savepoint_name ← "sp_" + savepoint_counter
                CreateSavepoint(connection, savepoint_name)
                savepoint_counter += 1
            END IF
            
            TRY
                // Check for timeout
                elapsed_time ← CurrentTimestamp() - transaction_start_time
                IF elapsed_time >= timeout_ms THEN
                    THROW TransactionTimeoutException("Transaction timeout exceeded")
                END IF
                
                // Execute operation with retry logic
                result ← ExecuteOperationWithRetry(connection, operation, transaction_context)
                operation_results.Add(result)
                
                // Update transaction context
                UpdateTransactionContext(transaction_context, operation, result)
                
            CATCH operation_error
                // Handle operation failure
                IF options.enable_savepoints THEN
                    RollbackToSavepoint(connection, savepoint_name)
                END IF
                
                // Determine if we should continue or abort
                IF ShouldAbortTransaction(operation_error, operation, options) THEN
                    THROW TransactionAbortException("Transaction aborted due to operation failure", operation_error)
                ELSE
                    // Log warning and continue
                    LogWarning("Operation failed but transaction continues", operation_error)
                    operation_results.Add(OperationResult{
                        success: false,
                        error: operation_error,
                        operation: operation
                    })
                END IF
            END TRY
        END FOR
        
        // Phase 5: Pre-commit validation
        validation_result ← ValidateTransactionState(connection, operations, operation_results, transaction_context)
        IF NOT validation_result.is_valid THEN
            THROW TransactionValidationException("Transaction validation failed", validation_result.errors)
        END IF
        
        // Phase 6: Commit transaction
        CommitTransaction(connection, options)
        
        // Phase 7: Post-commit operations
        ExecutePostCommitOperations(operation_results, transaction_context)
        
        transaction_end_time ← CurrentTimestamp()
        transaction_duration ← transaction_end_time - transaction_start_time
        
        // Release locks
        ReleaseLocks(acquired_locks)
        
        // Update metrics
        UpdateTransactionMetrics(transaction_id, transaction_duration, operations.Length, "COMMITTED")
        
        RETURN TransactionResult{
            transaction_id: transaction_id,
            status: "COMMITTED",
            duration: transaction_duration,
            operations_executed: operations.Length,
            operation_results: operation_results,
            isolation_level: isolation_level
        }
        
    CATCH transaction_error
        // Phase 8: Error handling and rollback
        TRY
            RollbackTransaction(connection)
            ReleaseLocks(acquired_locks)
            
            transaction_end_time ← CurrentTimestamp()
            transaction_duration ← transaction_end_time - transaction_start_time
            
            UpdateTransactionMetrics(transaction_id, transaction_duration, operations.Length, "ROLLED_BACK")
            
            LogError("Transaction rolled back", transaction_error, transaction_id)
            
        CATCH rollback_error
            LogCritical("Failed to rollback transaction", rollback_error, transaction_id)
            MarkConnectionAsCorrupted(connection)
        END TRY
        
        RETURN TransactionError{
            transaction_id: transaction_id,
            error_type: ClassifyTransactionError(transaction_error),
            original_error: transaction_error,
            duration: transaction_end_time - transaction_start_time
        }
        
    FINALLY
        ReleaseConnection(connection, options.connection_pool)
    END TRY
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(n * log n + m) where n = operations, m = lock acquisition time
    Space Complexity: O(n + l) where n = operation results, l = acquired locks
    Database Operations: n operations + transaction management overhead
```

### 1.2 Optimistic Concurrency Control Algorithm

```
ALGORITHM: ExecuteWithOptimisticLocking
INPUT: operation (DatabaseOperation), connection (DatabaseConnection), max_retries (int)
OUTPUT: operation_result (OperationResult) or error (ConcurrencyError)

BEGIN
    retry_count ← 0
    base_delay ← 50  // 50ms base delay
    
    WHILE retry_count <= max_retries DO
        TRY
            // Phase 1: Read current version/timestamp
            current_version ← GetCurrentVersion(connection, operation.target_table, operation.target_id)
            
            // Phase 2: Execute operation with version check
            CASE operation.type OF
                "UPDATE":
                    result ← ExecuteOptimisticUpdate(connection, operation, current_version)
                    
                "DELETE":
                    result ← ExecuteOptimisticDelete(connection, operation, current_version)
                    
                "INSERT":
                    // Inserts don't typically need optimistic locking
                    result ← ExecuteInsert(connection, operation)
                    
                DEFAULT:
                    result ← ExecuteGenericOperation(connection, operation)
            END CASE
            
            // Success - return result
            RETURN OperationResult{
                success: true,
                rows_affected: result.rows_affected,
                operation: operation,
                version_after: result.new_version
            }
            
        CATCH concurrency_error WHEN IsConcurrencyConflict(concurrency_error)
            retry_count += 1
            
            IF retry_count > max_retries THEN
                RETURN ConcurrencyError{
                    error_type: "MAX_RETRIES_EXCEEDED",
                    message: "Optimistic locking failed after " + max_retries + " retries",
                    operation: operation,
                    final_error: concurrency_error
                }
            END IF
            
            // Exponential backoff with jitter
            delay ← base_delay * (2 ^ retry_count) + Random(0, 50)
            Sleep(delay)
            
            LogInfo("Optimistic locking conflict, retrying", {
                operation: operation.type,
                target: operation.target_table,
                retry_count: retry_count,
                delay: delay
            })
            
        CATCH other_error
            // Non-concurrency error - don't retry
            RETURN OperationResult{
                success: false,
                error: other_error,
                operation: operation
            }
        END TRY
    END WHILE
END

SUBROUTINE: ExecuteOptimisticUpdate
INPUT: connection, operation, expected_version
OUTPUT: update_result (UpdateResult)

BEGIN
    // Build update query with version check
    update_query ← BuildUpdateQuery(operation)
    version_condition ← BuildVersionCondition(operation.target_table, operation.target_id, expected_version)
    
    // Execute update with version check
    full_query ← update_query + " AND " + version_condition
    
    // Include version increment in update
    IF operation.auto_increment_version THEN
        full_query ← AddVersionIncrement(full_query, operation.target_table)
    END IF
    
    result ← ExecuteSQL(connection, full_query, operation.parameters)
    
    // Check if any rows were affected (version check passed)
    IF result.rows_affected == 0 THEN
        // Version check failed - concurrent modification detected
        current_version ← GetCurrentVersion(connection, operation.target_table, operation.target_id)
        THROW OptimisticLockingException("Concurrent modification detected", {
            expected_version: expected_version,
            current_version: current_version,
            table: operation.target_table,
            id: operation.target_id
        })
    END IF
    
    // Get new version after update
    new_version ← null
    IF operation.auto_increment_version THEN
        new_version ← GetCurrentVersion(connection, operation.target_table, operation.target_id)
    END IF
    
    RETURN UpdateResult{
        rows_affected: result.rows_affected,
        new_version: new_version
    }
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(r * t) where r = retry attempts, t = operation time
    Space Complexity: O(1) for operation state
```

### 1.3 Deadlock Detection and Resolution Algorithm

```
ALGORITHM: DetectAndResolveDeadlocks
INPUT: active_transactions (List<Transaction>), wait_for_graph (WaitForGraph)
OUTPUT: resolution_result (DeadlockResolutionResult)

BEGIN
    // Phase 1: Build wait-for graph
    updated_graph ← UpdateWaitForGraph(active_transactions, wait_for_graph)
    
    // Phase 2: Detect cycles (deadlocks) using DFS
    deadlock_cycles ← DetectCycles(updated_graph)
    
    IF deadlock_cycles.IsEmpty() THEN
        RETURN DeadlockResolutionResult{
            deadlocks_detected: false,
            resolved_deadlocks: 0,
            victim_transactions: EmptyList()
        }
    END IF
    
    // Phase 3: Select victims for each deadlock
    victim_transactions ← EmptyList()
    resolution_actions ← EmptyList()
    
    FOR EACH cycle IN deadlock_cycles DO
        victim ← SelectDeadlockVictim(cycle)
        victim_transactions.Add(victim)
        
        // Create resolution action
        resolution_action ← DeadlockResolutionAction{
            victim_transaction: victim,
            deadlock_cycle: cycle,
            resolution_strategy: "ABORT_AND_RETRY",
            estimated_cost: CalculateAbortCost(victim)
        }
        
        resolution_actions.Add(resolution_action)
    END FOR
    
    // Phase 4: Execute resolution actions
    resolved_count ← 0
    
    FOR EACH action IN resolution_actions DO
        TRY
            ExecuteDeadlockResolution(action)
            resolved_count += 1
            
            LogInfo("Deadlock resolved by aborting transaction", {
                victim_transaction: action.victim_transaction.id,
                cycle_length: action.deadlock_cycle.Length
            })
            
        CATCH resolution_error
            LogError("Failed to resolve deadlock", resolution_error, {
                victim_transaction: action.victim_transaction.id
            })
        END TRY
    END FOR
    
    RETURN DeadlockResolutionResult{
        deadlocks_detected: true,
        deadlocks_found: deadlock_cycles.Length,
        resolved_deadlocks: resolved_count,
        victim_transactions: victim_transactions,
        resolution_actions: resolution_actions
    }
END

SUBROUTINE: SelectDeadlockVictim
INPUT: deadlock_cycle (List<Transaction>)
OUTPUT: victim_transaction (Transaction)

BEGIN
    // Use multiple criteria to select the best victim
    best_victim ← null
    lowest_cost ← INFINITY
    
    FOR EACH transaction IN deadlock_cycle DO
        cost ← CalculateVictimCost(transaction)
        
        IF cost < lowest_cost THEN
            lowest_cost ← cost
            best_victim ← transaction
        END IF
    END FOR
    
    RETURN best_victim
END

SUBROUTINE: CalculateVictimCost
INPUT: transaction (Transaction)
OUTPUT: cost (float)

BEGIN
    cost ← 0.0
    
    // Factor 1: Transaction age (newer transactions are cheaper to abort)
    age_weight ← 0.3
    transaction_age ← CurrentTimestamp() - transaction.start_time
    normalized_age ← MIN(transaction_age / MAX_TRANSACTION_AGE, 1.0)
    cost += age_weight * (1.0 - normalized_age)  // Newer = lower cost
    
    // Factor 2: Amount of work done (fewer operations = cheaper to abort)
    work_weight ← 0.4
    operations_completed ← transaction.completed_operations.Length
    normalized_work ← MIN(operations_completed / MAX_OPERATIONS_PER_TRANSACTION, 1.0)
    cost += work_weight * normalized_work
    
    // Factor 3: Transaction priority (lower priority = cheaper to abort)
    priority_weight ← 0.2
    normalized_priority ← transaction.priority / MAX_TRANSACTION_PRIORITY
    cost += priority_weight * (1.0 - normalized_priority)  // Lower priority = lower cost
    
    // Factor 4: Resources held (fewer locks = cheaper to abort)
    resource_weight ← 0.1
    locks_held ← transaction.held_locks.Length
    normalized_locks ← MIN(locks_held / MAX_LOCKS_PER_TRANSACTION, 1.0)
    cost += resource_weight * normalized_locks
    
    RETURN cost
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(V + E) for cycle detection where V = transactions, E = wait relationships
    Space Complexity: O(V + E) for wait-for graph storage
```

### 1.4 Distributed Transaction Coordinator (Two-Phase Commit)

```
ALGORITHM: ExecuteDistributedTransaction
INPUT: operations (List<DistributedOperation>), participants (List<DatabaseNode>), timeout_ms (int)
OUTPUT: distributed_result (DistributedTransactionResult)

BEGIN
    coordinator_id ← GenerateCoordinatorID()
    transaction_id ← GenerateGlobalTransactionID()
    
    // Phase 1: Prepare Phase
    prepare_results ← EmptyMap()
    prepare_start_time ← CurrentTimestamp()
    
    // Send prepare requests to all participants
    FOR EACH participant IN participants DO
        participant_operations ← GetOperationsForParticipant(operations, participant)
        
        IF participant_operations.IsEmpty() THEN
            CONTINUE  // Skip participants with no operations
        END IF
        
        TRY
            prepare_request ← PrepareRequest{
                transaction_id: transaction_id,
                coordinator_id: coordinator_id,
                operations: participant_operations,
                timeout_ms: timeout_ms
            }
            
            prepare_response ← SendPrepareRequest(participant, prepare_request)
            prepare_results[participant.id] ← prepare_response
            
        CATCH prepare_error
            prepare_results[participant.id] ← PrepareResponse{
                status: "ABORTED",
                error: prepare_error,
                participant_id: participant.id
            }
        END TRY
    END FOR
    
    // Check if all participants voted to commit
    all_prepared ← true
    abort_reason ← null
    
    FOR EACH participant_id, response IN prepare_results DO
        IF response.status != "PREPARED" THEN
            all_prepared ← false
            abort_reason ← "Participant " + participant_id + " vote: " + response.status
            BREAK
        END IF
    END FOR
    
    // Check for timeout during prepare phase
    prepare_duration ← CurrentTimestamp() - prepare_start_time
    IF prepare_duration >= timeout_ms THEN
        all_prepared ← false
        abort_reason ← "Prepare phase timeout"
    END IF
    
    // Phase 2: Decision Phase
    IF all_prepared THEN
        // Commit phase
        commit_results ← EmptyMap()
        commit_start_time ← CurrentTimestamp()
        
        FOR EACH participant IN participants DO
            IF NOT prepare_results.ContainsKey(participant.id) THEN
                CONTINUE  // Skip participants that weren't involved
            END IF
            
            TRY
                commit_request ← CommitRequest{
                    transaction_id: transaction_id,
                    coordinator_id: coordinator_id
                }
                
                commit_response ← SendCommitRequest(participant, commit_request)
                commit_results[participant.id] ← commit_response
                
            CATCH commit_error
                // Log error but don't fail the transaction
                // Participant must eventually commit (2PC guarantee)
                LogError("Commit request failed, participant will eventually commit", commit_error, {
                    participant_id: participant.id,
                    transaction_id: transaction_id
                })
                
                commit_results[participant.id] ← CommitResponse{
                    status: "COMMIT_FAILED",
                    error: commit_error,
                    participant_id: participant.id
                }
            END TRY
        END FOR
        
        transaction_status ← "COMMITTED"
        
    ELSE
        // Abort phase
        abort_results ← EmptyMap()
        
        FOR EACH participant IN participants DO
            IF NOT prepare_results.ContainsKey(participant.id) THEN
                CONTINUE  // Skip participants that weren't involved
            END IF
            
            TRY
                abort_request ← AbortRequest{
                    transaction_id: transaction_id,
                    coordinator_id: coordinator_id,
                    reason: abort_reason
                }
                
                abort_response ← SendAbortRequest(participant, abort_request)
                abort_results[participant.id] ← abort_response
                
            CATCH abort_error
                LogError("Abort request failed", abort_error, {
                    participant_id: participant.id,
                    transaction_id: transaction_id
                })
                
                abort_results[participant.id] ← AbortResponse{
                    status: "ABORT_FAILED",
                    error: abort_error,
                    participant_id: participant.id
                }
            END TRY
        END FOR
        
        transaction_status ← "ABORTED"
    END IF
    
    // Phase 3: Cleanup and logging
    transaction_end_time ← CurrentTimestamp()
    total_duration ← transaction_end_time - prepare_start_time
    
    LogDistributedTransaction(transaction_id, coordinator_id, transaction_status, 
        prepare_results, commit_results OR abort_results, total_duration)
    
    RETURN DistributedTransactionResult{
        transaction_id: transaction_id,
        coordinator_id: coordinator_id,
        status: transaction_status,
        participants_count: participants.Length,
        prepare_results: prepare_results,
        final_results: commit_results OR abort_results,
        total_duration: total_duration,
        abort_reason: abort_reason
    }
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(n * t) where n = participants, t = network/operation time
    Space Complexity: O(n) for participant responses
    Network Operations: 2n messages in best case (n prepare + n commit/abort)
```

## 2. CONNECTION POOL MANAGEMENT ALGORITHMS

### 2.1 Adaptive Connection Pool Algorithm

```
ALGORITHM: ManageConnectionPool
INPUT: pool_config (PoolConfiguration), usage_metrics (PoolMetrics)
OUTPUT: pool_adjustments (PoolAdjustments)

BEGIN
    current_stats ← GetCurrentPoolStats()
    
    // Phase 1: Analyze current performance
    performance_metrics ← AnalyzePoolPerformance(current_stats, usage_metrics)
    
    // Phase 2: Determine if adjustments are needed
    adjustments_needed ← false
    suggested_adjustments ← EmptyList()
    
    // Check wait time threshold
    IF performance_metrics.avg_wait_time > pool_config.max_acceptable_wait_time THEN
        IF current_stats.pool_size < pool_config.max_pool_size THEN
            suggested_adjustments.Add(PoolAdjustment{
                type: "INCREASE_POOL_SIZE",
                current_value: current_stats.pool_size,
                suggested_value: MIN(current_stats.pool_size + pool_config.pool_growth_step, pool_config.max_pool_size),
                reason: "High wait times detected"
            })
            adjustments_needed ← true
        END IF
    END IF
    
    // Check utilization threshold for downsizing
    IF performance_metrics.avg_utilization < pool_config.min_utilization_threshold THEN
        IF current_stats.pool_size > pool_config.min_pool_size THEN
            suggested_adjustments.Add(PoolAdjustment{
                type: "DECREASE_POOL_SIZE",
                current_value: current_stats.pool_size,
                suggested_value: MAX(current_stats.pool_size - pool_config.pool_shrink_step, pool_config.min_pool_size),
                reason: "Low utilization detected"
            })
            adjustments_needed ← true
        END IF
    END IF
    
    // Check connection health
    unhealthy_connections ← GetUnhealthyConnections(current_stats.connections)
    IF NOT unhealthy_connections.IsEmpty() THEN
        suggested_adjustments.Add(PoolAdjustment{
            type: "REPLACE_UNHEALTHY_CONNECTIONS",
            current_value: unhealthy_connections.Length,
            suggested_value: 0,
            reason: "Unhealthy connections detected",
            affected_connections: unhealthy_connections
        })
        adjustments_needed ← true
    END IF
    
    // Phase 3: Apply adjustments if needed
    applied_adjustments ← EmptyList()
    
    IF adjustments_needed THEN
        FOR EACH adjustment IN suggested_adjustments DO
            TRY
                result ← ApplyPoolAdjustment(adjustment)
                applied_adjustments.Add(result)
                
                LogInfo("Pool adjustment applied", {
                    type: adjustment.type,
                    old_value: adjustment.current_value,
                    new_value: adjustment.suggested_value,
                    reason: adjustment.reason
                })
                
            CATCH adjustment_error
                LogError("Failed to apply pool adjustment", adjustment_error, adjustment)
            END TRY
        END FOR
    END IF
    
    RETURN PoolAdjustments{
        adjustments_made: applied_adjustments.Length > 0,
        applied_adjustments: applied_adjustments,
        pool_stats_before: current_stats,
        pool_stats_after: GetCurrentPoolStats()
    }
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(n) where n = connections in pool
    Space Complexity: O(n) for connection health tracking
```

## 3. TRANSACTION ALGORITHM CONSTANTS

```
TRANSACTION_CONSTANTS:
    DEFAULT_TRANSACTION_TIMEOUT = 30000      // 30 seconds
    MAX_TRANSACTION_TIMEOUT = 300000         // 5 minutes
    DEFAULT_LOCK_TIMEOUT = 10000            // 10 seconds
    MAX_RETRY_ATTEMPTS = 5                  // Maximum optimistic locking retries
    DEADLOCK_DETECTION_INTERVAL = 5000      // 5 seconds
    CONNECTION_POOL_CHECK_INTERVAL = 60000  // 1 minute
    
ISOLATION_LEVELS:
    READ_UNCOMMITTED = 1
    READ_COMMITTED = 2
    REPEATABLE_READ = 3
    SERIALIZABLE = 4
    
LOCK_TYPES:
    SHARED = "S"         // Read lock
    EXCLUSIVE = "X"      // Write lock
    INTENTION_SHARED = "IS"
    INTENTION_EXCLUSIVE = "IX"
    SHARED_INTENTION_EXCLUSIVE = "SIX"
    
PERFORMANCE_THRESHOLDS:
    SLOW_TRANSACTION_THRESHOLD = 5000        // 5 seconds
    HIGH_CONTENTION_THRESHOLD = 10           // Lock waits per second
    CONNECTION_LEAK_THRESHOLD = 3600000      // 1 hour connection age
    DEADLOCK_ALERT_THRESHOLD = 5             // Deadlocks per minute
```

This comprehensive transaction management system provides ACID compliance, concurrency control, deadlock prevention and resolution, and distributed transaction support with robust error handling and performance optimization.