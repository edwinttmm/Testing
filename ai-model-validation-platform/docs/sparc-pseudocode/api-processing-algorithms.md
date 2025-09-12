# SPARC Pseudocode Phase: API Request/Response Processing Algorithms

## Overview
Comprehensive API processing algorithms including request validation, response formatting, rate limiting, caching, and middleware orchestration.

## 1. REQUEST PROCESSING ALGORITHMS

### 1.1 Universal API Request Handler Algorithm

```
ALGORITHM: ProcessAPIRequest
INPUT: request (HTTPRequest), endpoint_config (EndpointConfiguration), context (RequestContext)
OUTPUT: response (HTTPResponse) or error (APIError)

PRECONDITIONS:
    - request is valid HTTP request
    - endpoint_config contains routing and validation rules
    - context contains authentication and authorization data

BEGIN
    request_id ← GenerateRequestID()
    request_start_time ← CurrentTimestamp()
    
    // Phase 1: Request Initialization and Logging
    request_context ← InitializeRequestContext(request, request_id, request_start_time)
    LogRequest(request_context)
    
    TRY
        // Phase 2: Pre-processing Middleware Chain
        middleware_result ← ExecutePreProcessingMiddleware(request, request_context, endpoint_config)
        
        IF NOT middleware_result.success THEN
            RETURN CreateErrorResponse(middleware_result.error, request_context)
        END IF
        
        // Update request with middleware modifications
        processed_request ← middleware_result.modified_request
        
        // Phase 3: Rate Limiting
        rate_limit_result ← CheckRateLimit(processed_request, request_context, endpoint_config.rate_limiting)
        
        IF NOT rate_limit_result.allowed THEN
            RETURN CreateRateLimitResponse(rate_limit_result, request_context)
        END IF
        
        // Phase 4: Authentication and Authorization
        auth_result ← AuthenticateAndAuthorize(processed_request, request_context, endpoint_config.security)
        
        IF NOT auth_result.authenticated THEN
            RETURN CreateAuthenticationErrorResponse(auth_result.error, request_context)
        END IF
        
        IF NOT auth_result.authorized THEN
            RETURN CreateAuthorizationErrorResponse(auth_result.error, request_context)
        END IF
        
        // Update context with user information
        request_context.user ← auth_result.user
        request_context.permissions ← auth_result.permissions
        
        // Phase 5: Input Validation and Sanitization
        validation_result ← ValidateAndSanitizeInput(processed_request, endpoint_config.validation_schema)
        
        IF NOT validation_result.valid THEN
            RETURN CreateValidationErrorResponse(validation_result.errors, request_context)
        END IF
        
        // Phase 6: Cache Check (for GET requests)
        IF processed_request.method == "GET" AND endpoint_config.caching.enabled THEN
            cache_key ← GenerateCacheKey(processed_request, request_context)
            cached_response ← GetFromCache(cache_key, endpoint_config.caching)
            
            IF cached_response is not null THEN
                // Cache hit - return cached response
                cached_response.headers["X-Cache-Status"] ← "HIT"
                cached_response.headers["X-Request-ID"] ← request_id
                
                LogCacheHit(request_context, cache_key)
                RETURN cached_response
            END IF
            
            LogCacheMiss(request_context, cache_key)
        END IF
        
        // Phase 7: Business Logic Execution
        business_logic_start_time ← CurrentTimestamp()
        
        business_result ← ExecuteBusinessLogic(
            processed_request,
            validation_result.sanitized_data,
            request_context,
            endpoint_config.business_logic
        )
        
        business_logic_end_time ← CurrentTimestamp()
        business_logic_duration ← business_logic_end_time - business_logic_start_time
        
        // Phase 8: Response Formatting
        formatted_response ← FormatResponse(
            business_result,
            endpoint_config.response_format,
            request_context
        )
        
        // Phase 9: Post-processing Middleware
        post_processing_result ← ExecutePostProcessingMiddleware(
            formatted_response,
            request_context,
            endpoint_config
        )
        
        final_response ← post_processing_result.response
        
        // Phase 10: Response Caching (for successful GET requests)
        IF processed_request.method == "GET" AND 
           endpoint_config.caching.enabled AND 
           final_response.status_code == 200 THEN
            
            cache_key ← GenerateCacheKey(processed_request, request_context)
            CacheResponse(cache_key, final_response, endpoint_config.caching)
        END IF
        
        // Phase 11: Metrics and Logging
        request_end_time ← CurrentTimestamp()
        total_duration ← request_end_time - request_start_time
        
        UpdateAPIMetrics(request_context, final_response, total_duration, business_logic_duration)
        LogResponse(request_context, final_response, total_duration)
        
        // Add standard headers
        final_response.headers["X-Request-ID"] ← request_id
        final_response.headers["X-Response-Time"] ← total_duration + "ms"
        final_response.headers["X-API-Version"] ← endpoint_config.api_version
        
        RETURN final_response
        
    CATCH api_error
        // Phase 12: Error Handling
        error_response ← HandleAPIError(api_error, request_context, endpoint_config)
        
        request_end_time ← CurrentTimestamp()
        total_duration ← request_end_time - request_start_time
        
        LogError(api_error, request_context, total_duration)
        UpdateErrorMetrics(request_context, api_error)
        
        error_response.headers["X-Request-ID"] ← request_id
        error_response.headers["X-Response-Time"] ← total_duration + "ms"
        
        RETURN error_response
    END TRY
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(n + m + v) where n = middleware count, m = validation rules, v = business logic
    Space Complexity: O(k) where k = request/response data size
    I/O Operations: Database queries, cache operations, external service calls
```

### 1.2 Request Validation and Sanitization Algorithm

```
ALGORITHM: ValidateAndSanitizeInput
INPUT: request (HTTPRequest), validation_schema (ValidationSchema)
OUTPUT: validation_result (ValidationResult)

BEGIN
    validation_result ← ValidationResult{
        valid: true,
        errors: EmptyList(),
        warnings: EmptyList(),
        sanitized_data: EmptyMap()
    }
    
    // Phase 1: Extract and validate request components
    request_components ← ExtractRequestComponents(request)
    
    // Phase 2: Validate HTTP method
    IF validation_schema.allowed_methods is not null THEN
        IF request.method NOT IN validation_schema.allowed_methods THEN
            validation_result.errors.Add(ValidationError{
                field: "method",
                code: "METHOD_NOT_ALLOWED",
                message: "HTTP method " + request.method + " not allowed for this endpoint"
            })
            validation_result.valid ← false
        END IF
    END IF
    
    // Phase 3: Validate Content-Type
    IF validation_schema.required_content_type is not null THEN
        content_type ← request.headers["Content-Type"]
        
        IF NOT MatchesContentType(content_type, validation_schema.required_content_type) THEN
            validation_result.errors.Add(ValidationError{
                field: "content-type",
                code: "INVALID_CONTENT_TYPE",
                message: "Expected content type: " + validation_schema.required_content_type
            })
            validation_result.valid ← false
        END IF
    END IF
    
    // Phase 4: Validate and sanitize path parameters
    IF validation_schema.path_parameters is not null THEN
        FOR EACH param_name, param_schema IN validation_schema.path_parameters DO
            param_value ← request_components.path_parameters[param_name]
            
            param_validation ← ValidateParameter(param_value, param_schema, param_name)
            validation_result.errors.AddAll(param_validation.errors)
            validation_result.warnings.AddAll(param_validation.warnings)
            
            IF param_validation.valid THEN
                validation_result.sanitized_data["path_" + param_name] ← param_validation.sanitized_value
            ELSE
                validation_result.valid ← false
            END IF
        END FOR
    END IF
    
    // Phase 5: Validate and sanitize query parameters
    IF validation_schema.query_parameters is not null THEN
        FOR EACH param_name, param_schema IN validation_schema.query_parameters DO
            param_values ← request_components.query_parameters[param_name]
            
            // Handle array parameters
            IF param_schema.is_array THEN
                sanitized_array ← EmptyList()
                
                FOR EACH value IN param_values DO
                    param_validation ← ValidateParameter(value, param_schema.element_schema, param_name)
                    validation_result.errors.AddAll(param_validation.errors)
                    validation_result.warnings.AddAll(param_validation.warnings)
                    
                    IF param_validation.valid THEN
                        sanitized_array.Add(param_validation.sanitized_value)
                    ELSE
                        validation_result.valid ← false
                    END IF
                END FOR
                
                validation_result.sanitized_data["query_" + param_name] ← sanitized_array
            ELSE
                param_value ← param_values.IsEmpty() ? null : param_values[0]
                
                param_validation ← ValidateParameter(param_value, param_schema, param_name)
                validation_result.errors.AddAll(param_validation.errors)
                validation_result.warnings.AddAll(param_validation.warnings)
                
                IF param_validation.valid THEN
                    validation_result.sanitized_data["query_" + param_name] ← param_validation.sanitized_value
                ELSE
                    validation_result.valid ← false
                END IF
            END IF
        END FOR
    END IF
    
    // Phase 6: Validate and sanitize request body
    IF validation_schema.body_schema is not null AND request.body is not null THEN
        body_validation ← ValidateRequestBody(request.body, validation_schema.body_schema)
        validation_result.errors.AddAll(body_validation.errors)
        validation_result.warnings.AddAll(body_validation.warnings)
        
        IF body_validation.valid THEN
            validation_result.sanitized_data["body"] ← body_validation.sanitized_data
        ELSE
            validation_result.valid ← false
        END IF
    END IF
    
    // Phase 7: Validate headers
    IF validation_schema.required_headers is not null THEN
        FOR EACH header_name IN validation_schema.required_headers DO
            header_value ← request.headers[header_name]
            
            IF header_value is null OR IsEmpty(header_value) THEN
                validation_result.errors.Add(ValidationError{
                    field: "headers." + header_name,
                    code: "REQUIRED_HEADER_MISSING",
                    message: "Required header missing: " + header_name
                })
                validation_result.valid ← false
            END IF
        END FOR
    END IF
    
    // Phase 8: Validate request size limits
    IF validation_schema.max_request_size is not null THEN
        request_size ← CalculateRequestSize(request)
        
        IF request_size > validation_schema.max_request_size THEN
            validation_result.errors.Add(ValidationError{
                field: "request_size",
                code: "REQUEST_TOO_LARGE",
                message: "Request size exceeds limit: " + validation_schema.max_request_size + " bytes"
            })
            validation_result.valid ← false
        END IF
    END IF
    
    RETURN validation_result
END

SUBROUTINE: ValidateParameter
INPUT: param_value (Any), param_schema (ParameterSchema), param_name (string)
OUTPUT: param_validation (ParameterValidation)

BEGIN
    validation ← ParameterValidation{
        valid: true,
        errors: EmptyList(),
        warnings: EmptyList(),
        sanitized_value: param_value
    }
    
    // Check if parameter is required
    IF param_schema.required AND (param_value is null OR IsEmpty(param_value)) THEN
        validation.errors.Add(ValidationError{
            field: param_name,
            code: "REQUIRED_PARAMETER_MISSING",
            message: "Required parameter missing: " + param_name
        })
        validation.valid ← false
        RETURN validation
    END IF
    
    // Skip further validation for optional empty parameters
    IF NOT param_schema.required AND (param_value is null OR IsEmpty(param_value)) THEN
        validation.sanitized_value ← param_schema.default_value
        RETURN validation
    END IF
    
    // Type validation and conversion
    type_validation ← ValidateAndConvertType(param_value, param_schema.type)
    validation.errors.AddAll(type_validation.errors)
    
    IF NOT type_validation.valid THEN
        validation.valid ← false
        RETURN validation
    END IF
    
    converted_value ← type_validation.converted_value
    
    // Range validation for numeric types
    IF param_schema.type IN ["integer", "number"] THEN
        IF param_schema.minimum is not null AND converted_value < param_schema.minimum THEN
            validation.errors.Add(ValidationError{
                field: param_name,
                code: "VALUE_TOO_SMALL",
                message: param_name + " must be >= " + param_schema.minimum
            })
            validation.valid ← false
        END IF
        
        IF param_schema.maximum is not null AND converted_value > param_schema.maximum THEN
            validation.errors.Add(ValidationError{
                field: param_name,
                code: "VALUE_TOO_LARGE", 
                message: param_name + " must be <= " + param_schema.maximum
            })
            validation.valid ← false
        END IF
    END IF
    
    // Length validation for string types
    IF param_schema.type == "string" THEN
        string_value ← ToString(converted_value)
        
        IF param_schema.min_length is not null AND Length(string_value) < param_schema.min_length THEN
            validation.errors.Add(ValidationError{
                field: param_name,
                code: "STRING_TOO_SHORT",
                message: param_name + " must be at least " + param_schema.min_length + " characters"
            })
            validation.valid ← false
        END IF
        
        IF param_schema.max_length is not null AND Length(string_value) > param_schema.max_length THEN
            validation.errors.Add(ValidationError{
                field: param_name,
                code: "STRING_TOO_LONG",
                message: param_name + " must be at most " + param_schema.max_length + " characters"
            })
            validation.valid ← false
        END IF
        
        // Pattern validation
        IF param_schema.pattern is not null AND NOT RegexMatch(string_value, param_schema.pattern) THEN
            validation.errors.Add(ValidationError{
                field: param_name,
                code: "INVALID_FORMAT",
                message: param_name + " format is invalid"
            })
            validation.valid ← false
        END IF
    END IF
    
    // Enum validation
    IF param_schema.enum is not null AND converted_value NOT IN param_schema.enum THEN
        validation.errors.Add(ValidationError{
            field: param_name,
            code: "INVALID_ENUM_VALUE",
            message: param_name + " must be one of: " + Join(param_schema.enum, ", ")
        })
        validation.valid ← false
    END IF
    
    // Sanitization
    IF validation.valid THEN
        validation.sanitized_value ← SanitizeValue(converted_value, param_schema.sanitization)
    END IF
    
    RETURN validation
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(n * m) where n = parameters, m = validation rules per parameter
    Space Complexity: O(n) for sanitized parameter storage
```

### 1.3 Rate Limiting Algorithm

```
ALGORITHM: CheckRateLimit
INPUT: request (HTTPRequest), context (RequestContext), rate_config (RateLimitConfiguration)
OUTPUT: rate_limit_result (RateLimitResult)

BEGIN
    // Phase 1: Determine rate limit key
    rate_limit_key ← GenerateRateLimitKey(request, context, rate_config)
    
    // Phase 2: Get current rate limit state
    current_state ← GetRateLimitState(rate_limit_key)
    current_time ← CurrentTimestamp()
    
    // Phase 3: Apply rate limiting algorithm
    CASE rate_config.algorithm OF
        "TOKEN_BUCKET":
            result ← ApplyTokenBucketRateLimit(current_state, current_time, rate_config)
            
        "SLIDING_WINDOW":
            result ← ApplySlidingWindowRateLimit(current_state, current_time, rate_config)
            
        "FIXED_WINDOW":
            result ← ApplyFixedWindowRateLimit(current_state, current_time, rate_config)
            
        "LEAKY_BUCKET":
            result ← ApplyLeakyBucketRateLimit(current_state, current_time, rate_config)
            
        DEFAULT:
            result ← ApplyTokenBucketRateLimit(current_state, current_time, rate_config)
    END CASE
    
    // Phase 4: Update rate limit state
    UpdateRateLimitState(rate_limit_key, result.new_state)
    
    // Phase 5: Add rate limit headers
    rate_limit_headers ← CreateRateLimitHeaders(result, rate_config)
    
    RETURN RateLimitResult{
        allowed: result.allowed,
        remaining_requests: result.remaining_requests,
        reset_time: result.reset_time,
        retry_after: result.retry_after,
        headers: rate_limit_headers,
        rate_limit_key: rate_limit_key
    }
END

SUBROUTINE: ApplyTokenBucketRateLimit
INPUT: current_state (RateLimitState), current_time (timestamp), config (RateLimitConfiguration)
OUTPUT: bucket_result (TokenBucketResult)

BEGIN
    // Initialize state if not exists
    IF current_state is null THEN
        current_state ← RateLimitState{
            tokens: config.bucket_size,
            last_refill: current_time
        }
    END IF
    
    // Calculate tokens to add based on time elapsed
    time_elapsed ← current_time - current_state.last_refill
    tokens_to_add ← (time_elapsed / 1000.0) * config.refill_rate  // refill_rate per second
    
    // Update token count (don't exceed bucket size)
    new_token_count ← MIN(current_state.tokens + tokens_to_add, config.bucket_size)
    
    // Check if request can be allowed
    request_allowed ← new_token_count >= 1.0
    
    IF request_allowed THEN
        // Consume one token
        final_token_count ← new_token_count - 1.0
        remaining_requests ← FLOOR(final_token_count)
        
        // Calculate when bucket will be full again
        time_to_full ← (config.bucket_size - final_token_count) / config.refill_rate * 1000
        reset_time ← current_time + time_to_full
        
        RETURN TokenBucketResult{
            allowed: true,
            remaining_requests: remaining_requests,
            reset_time: reset_time,
            retry_after: null,
            new_state: RateLimitState{
                tokens: final_token_count,
                last_refill: current_time
            }
        }
    ELSE
        // Request denied - calculate retry after time
        time_to_next_token ← (1.0 - new_token_count) / config.refill_rate * 1000
        retry_after ← CEIL(time_to_next_token / 1000.0)  // Convert to seconds
        
        RETURN TokenBucketResult{
            allowed: false,
            remaining_requests: 0,
            reset_time: current_time + time_to_next_token,
            retry_after: retry_after,
            new_state: RateLimitState{
                tokens: new_token_count,
                last_refill: current_time
            }
        }
    END IF
END

SUBROUTINE: ApplySlidingWindowRateLimit
INPUT: current_state (RateLimitState), current_time (timestamp), config (RateLimitConfiguration)
OUTPUT: sliding_window_result (SlidingWindowResult)

BEGIN
    window_size_ms ← config.window_size * 1000  // Convert to milliseconds
    
    // Initialize state if not exists
    IF current_state is null OR current_state.request_timestamps is null THEN
        current_state ← RateLimitState{
            request_timestamps: EmptyList(),
            last_cleanup: current_time
        }
    END IF
    
    // Clean up old timestamps outside the window
    window_start ← current_time - window_size_ms
    current_state.request_timestamps ← current_state.request_timestamps.Filter(
        timestamp → timestamp >= window_start
    )
    
    // Check if we can allow this request
    current_request_count ← current_state.request_timestamps.Length
    request_allowed ← current_request_count < config.max_requests
    
    IF request_allowed THEN
        // Add current request timestamp
        current_state.request_timestamps.Add(current_time)
        remaining_requests ← config.max_requests - current_request_count - 1
        
        // Calculate reset time (when oldest request will expire)
        IF current_state.request_timestamps.Length > 0 THEN
            oldest_timestamp ← current_state.request_timestamps.Min()
            reset_time ← oldest_timestamp + window_size_ms
        ELSE
            reset_time ← current_time + window_size_ms
        END IF
        
        RETURN SlidingWindowResult{
            allowed: true,
            remaining_requests: remaining_requests,
            reset_time: reset_time,
            retry_after: null,
            new_state: current_state
        }
    ELSE
        // Request denied - calculate retry after time
        oldest_timestamp ← current_state.request_timestamps.Min()
        retry_after_ms ← (oldest_timestamp + window_size_ms) - current_time
        retry_after ← CEIL(retry_after_ms / 1000.0)
        
        RETURN SlidingWindowResult{
            allowed: false,
            remaining_requests: 0,
            reset_time: oldest_timestamp + window_size_ms,
            retry_after: retry_after,
            new_state: current_state
        }
    END IF
END

COMPLEXITY ANALYSIS:
    Token Bucket: O(1) time, O(1) space
    Sliding Window: O(n) time where n = requests in window, O(n) space
    Fixed Window: O(1) time, O(1) space
```

## 2. RESPONSE FORMATTING ALGORITHMS

### 2.1 Universal Response Formatter Algorithm

```
ALGORITHM: FormatResponse
INPUT: business_result (BusinessResult), format_config (ResponseFormatConfiguration), context (RequestContext)
OUTPUT: formatted_response (HTTPResponse)

BEGIN
    // Phase 1: Determine response format
    response_format ← DetermineResponseFormat(context.request, format_config)
    
    // Phase 2: Handle different result types
    CASE business_result.type OF
        "SUCCESS":
            response ← FormatSuccessResponse(business_result, response_format, context)
            
        "ERROR":
            response ← FormatErrorResponse(business_result, response_format, context)
            
        "PARTIAL_SUCCESS":
            response ← FormatPartialSuccessResponse(business_result, response_format, context)
            
        "REDIRECT":
            response ← FormatRedirectResponse(business_result, response_format, context)
            
        DEFAULT:
            response ← FormatGenericResponse(business_result, response_format, context)
    END CASE
    
    // Phase 3: Add standard metadata
    response.data ← AddStandardMetadata(response.data, business_result, context)
    
    // Phase 4: Apply response transformations
    IF format_config.transformations is not null THEN
        FOR EACH transformation IN format_config.transformations DO
            response ← ApplyTransformation(response, transformation, context)
        END FOR
    END IF
    
    // Phase 5: Set appropriate headers
    response.headers ← SetStandardHeaders(response.headers, response_format, context)
    
    // Phase 6: Apply compression if needed
    IF ShouldCompress(response, context.request) THEN
        response ← ApplyCompression(response, GetCompressionAlgorithm(context.request))
    END IF
    
    RETURN response
END

SUBROUTINE: FormatSuccessResponse
INPUT: business_result (BusinessResult), format (ResponseFormat), context (RequestContext)
OUTPUT: success_response (HTTPResponse)

BEGIN
    CASE format.type OF
        "JSON":
            response_body ← FormatJSONSuccessResponse(business_result, format, context)
            content_type ← "application/json"
            
        "XML":
            response_body ← FormatXMLSuccessResponse(business_result, format, context)
            content_type ← "application/xml"
            
        "CSV":
            response_body ← FormatCSVSuccessResponse(business_result, format, context)
            content_type ← "text/csv"
            
        "BINARY":
            response_body ← business_result.data
            content_type ← business_result.content_type OR "application/octet-stream"
            
        DEFAULT:
            response_body ← FormatJSONSuccessResponse(business_result, format, context)
            content_type ← "application/json"
    END CASE
    
    RETURN HTTPResponse{
        status_code: DetermineSuccessStatusCode(business_result),
        headers: {"Content-Type": content_type},
        body: response_body
    }
END

SUBROUTINE: FormatJSONSuccessResponse
INPUT: business_result (BusinessResult), format (ResponseFormat), context (RequestContext)
OUTPUT: json_response (JSONObject)

BEGIN
    response_structure ← format.response_structure OR "standard"
    
    CASE response_structure OF
        "standard":
            RETURN {
                "success": true,
                "data": business_result.data,
                "message": business_result.message OR "Operation completed successfully",
                "timestamp": CurrentISOTimestamp(),
                "request_id": context.request_id
            }
            
        "minimal":
            RETURN business_result.data
            
        "envelope":
            RETURN {
                "status": "success",
                "result": {
                    "data": business_result.data,
                    "metadata": {
                        "timestamp": CurrentISOTimestamp(),
                        "request_id": context.request_id,
                        "api_version": format.api_version
                    }
                }
            }
            
        "paginated":
            RETURN {
                "success": true,
                "data": business_result.data.items,
                "pagination": {
                    "page": business_result.data.page,
                    "limit": business_result.data.limit,
                    "total": business_result.data.total,
                    "has_next": business_result.data.has_next,
                    "has_previous": business_result.data.has_previous
                },
                "timestamp": CurrentISOTimestamp(),
                "request_id": context.request_id
            }
            
        DEFAULT:
            RETURN {
                "data": business_result.data,
                "meta": {
                    "success": true,
                    "timestamp": CurrentISOTimestamp(),
                    "request_id": context.request_id
                }
            }
    END CASE
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(n + t) where n = data size, t = transformation complexity
    Space Complexity: O(n) for formatted response data
```

## 3. MIDDLEWARE ORCHESTRATION ALGORITHMS

### 3.1 Middleware Chain Executor Algorithm

```
ALGORITHM: ExecuteMiddlewareChain
INPUT: request (HTTPRequest), context (RequestContext), middleware_config (List<MiddlewareConfiguration>)
OUTPUT: middleware_result (MiddlewareResult)

BEGIN
    modified_request ← request.Clone()
    middleware_states ← EmptyMap()
    
    // Phase 1: Execute pre-processing middleware
    FOR EACH middleware_config IN middleware_config DO
        IF NOT middleware_config.enabled THEN
            CONTINUE
        END IF
        
        middleware_start_time ← CurrentTimestamp()
        
        TRY
            // Create middleware instance
            middleware ← CreateMiddleware(middleware_config)
            
            // Execute middleware
            middleware_result ← middleware.Execute(modified_request, context, middleware_states)
            
            // Update request with middleware modifications
            IF middleware_result.request_modified THEN
                modified_request ← middleware_result.modified_request
            END IF
            
            // Update context with middleware data
            IF middleware_result.context_data is not null THEN
                context.middleware_data[middleware_config.name] ← middleware_result.context_data
            END IF
            
            // Store middleware state for cleanup
            middleware_states[middleware_config.name] ← middleware_result.state
            
            // Check if middleware wants to short-circuit
            IF middleware_result.short_circuit THEN
                RETURN MiddlewareResult{
                    success: middleware_result.success,
                    modified_request: modified_request,
                    error: middleware_result.error,
                    short_circuit_response: middleware_result.response
                }
            END IF
            
        CATCH middleware_error
            // Handle middleware execution error
            LogError("Middleware execution failed", middleware_error, {
                middleware_name: middleware_config.name,
                request_id: context.request_id
            })
            
            // Determine error handling strategy
            CASE middleware_config.error_handling OF
                "FAIL_FAST":
                    RETURN MiddlewareResult{
                        success: false,
                        error: middleware_error,
                        failed_middleware: middleware_config.name
                    }
                    
                "CONTINUE":
                    LogWarning("Continuing despite middleware failure", middleware_error)
                    CONTINUE
                    
                "DEFAULT_BEHAVIOR":
                    // Execute default behavior for this middleware
                    ExecuteDefaultMiddlewareBehavior(middleware_config, modified_request, context)
                    CONTINUE
                    
                DEFAULT:
                    RETURN MiddlewareResult{
                        success: false,
                        error: middleware_error,
                        failed_middleware: middleware_config.name
                    }
            END CASE
        END TRY
        
        middleware_end_time ← CurrentTimestamp()
        middleware_duration ← middleware_end_time - middleware_start_time
        
        // Update middleware performance metrics
        UpdateMiddlewareMetrics(middleware_config.name, middleware_duration)
    END FOR
    
    RETURN MiddlewareResult{
        success: true,
        modified_request: modified_request,
        middleware_states: middleware_states
    }
END

CLASS: CommonMiddleware

MIDDLEWARE: AuthenticationMiddleware
ALGORITHM: Execute
INPUT: request, context, states
OUTPUT: middleware_result

BEGIN
    // Extract authentication token
    auth_header ← request.headers["Authorization"]
    IF auth_header is null THEN
        RETURN MiddlewareResult{
            success: false,
            short_circuit: true,
            response: CreateUnauthorizedResponse("Missing authentication token")
        }
    END IF
    
    // Validate token
    token ← ExtractToken(auth_header)
    validation_result ← ValidateToken(token)
    
    IF NOT validation_result.valid THEN
        RETURN MiddlewareResult{
            success: false,
            short_circuit: true,
            response: CreateUnauthorizedResponse("Invalid authentication token")
        }
    END IF
    
    // Add user information to context
    context.user ← validation_result.user
    context.permissions ← validation_result.permissions
    
    RETURN MiddlewareResult{
        success: true,
        context_data: {
            "user_id": validation_result.user.id,
            "authenticated_at": CurrentTimestamp()
        }
    }
END

MIDDLEWARE: RequestLoggingMiddleware
ALGORITHM: Execute
INPUT: request, context, states
OUTPUT: middleware_result

BEGIN
    log_entry ← {
        "request_id": context.request_id,
        "method": request.method,
        "path": request.path,
        "query_params": request.query_params,
        "headers": FilterSensitiveHeaders(request.headers),
        "user_agent": request.headers["User-Agent"],
        "ip_address": ExtractClientIP(request),
        "timestamp": CurrentISOTimestamp()
    }
    
    LogRequest(log_entry)
    
    RETURN MiddlewareResult{
        success: true,
        state: log_entry
    }
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(m) where m = number of middleware
    Space Complexity: O(m) for middleware states
```

## 4. API ALGORITHM CONSTANTS

```
API_CONSTANTS:
    MAX_REQUEST_SIZE = 10485760         // 10MB default max request size
    DEFAULT_TIMEOUT = 30000             // 30 seconds default timeout
    MAX_QUERY_PARAMS = 100              // Maximum query parameters
    MAX_HEADER_SIZE = 8192              // 8KB maximum header size
    DEFAULT_PAGE_SIZE = 20              // Default pagination limit
    MAX_PAGE_SIZE = 1000                // Maximum pagination limit
    
RATE_LIMITING_DEFAULTS:
    DEFAULT_RATE_LIMIT = 100            // requests per minute
    DEFAULT_BURST_SIZE = 10             // burst capacity
    DEFAULT_WINDOW_SIZE = 60            // 60 seconds
    TOKEN_BUCKET_REFILL_RATE = 1.67     // tokens per second (100/min)
    
RESPONSE_FORMATS:
    JSON = "application/json"
    XML = "application/xml"
    CSV = "text/csv"
    HTML = "text/html"
    BINARY = "application/octet-stream"
    
CACHE_SETTINGS:
    DEFAULT_CACHE_TTL = 300             // 5 minutes
    MAX_CACHE_TTL = 86400               // 24 hours
    CACHE_KEY_MAX_LENGTH = 256          // Maximum cache key length
    
HTTP_STATUS_CODES:
    SUCCESS_OK = 200
    SUCCESS_CREATED = 201
    SUCCESS_ACCEPTED = 202
    SUCCESS_NO_CONTENT = 204
    REDIRECT_MOVED_PERMANENTLY = 301
    REDIRECT_FOUND = 302
    CLIENT_ERROR_BAD_REQUEST = 400
    CLIENT_ERROR_UNAUTHORIZED = 401
    CLIENT_ERROR_FORBIDDEN = 403
    CLIENT_ERROR_NOT_FOUND = 404
    CLIENT_ERROR_METHOD_NOT_ALLOWED = 405
    CLIENT_ERROR_CONFLICT = 409
    CLIENT_ERROR_UNPROCESSABLE_ENTITY = 422
    CLIENT_ERROR_TOO_MANY_REQUESTS = 429
    SERVER_ERROR_INTERNAL = 500
    SERVER_ERROR_BAD_GATEWAY = 502
    SERVER_ERROR_SERVICE_UNAVAILABLE = 503
    SERVER_ERROR_GATEWAY_TIMEOUT = 504
```

This comprehensive API processing system provides robust request handling, validation, rate limiting, response formatting, and middleware orchestration with proper error handling and performance optimization.