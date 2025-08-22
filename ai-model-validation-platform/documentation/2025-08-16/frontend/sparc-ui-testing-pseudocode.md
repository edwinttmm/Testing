# SPARC Phase 2: UI Testing Pseudocode Algorithms
*Comprehensive Feature Testing Methodology*

## 🧩 Core Testing Algorithms

### **Algorithm 1: Page Component Discovery**
```pseudocode
FUNCTION discoverPageComponents(page_path):
    NAVIGATE to page_path
    WAIT for page_load_complete()
    
    components = EMPTY_LIST
    
    // Discover all interactive elements
    buttons = FIND_ALL_ELEMENTS("button, [role='button']")
    links = FIND_ALL_ELEMENTS("a[href], [role='link']")
    inputs = FIND_ALL_ELEMENTS("input, textarea, select")
    icons = FIND_ALL_ELEMENTS("[data-testid*='icon'], svg, .icon")
    forms = FIND_ALL_ELEMENTS("form")
    modals = FIND_ALL_ELEMENTS("[role='dialog'], .modal, .drawer")
    tables = FIND_ALL_ELEMENTS("table, [role='table']")
    tabs = FIND_ALL_ELEMENTS("[role='tab'], .tab")
    menus = FIND_ALL_ELEMENTS("[role='menu'], .dropdown-menu")
    
    // Catalog each component with metadata
    FOR each element IN [buttons, links, inputs, icons, forms, modals, tables, tabs, menus]:
        component_info = {
            type: element.tagName,
            id: element.id,
            classes: element.className,
            text: element.textContent,
            attributes: element.attributes,
            parent_context: element.parentElement.tagName,
            accessibility: {
                aria_label: element.getAttribute('aria-label'),
                aria_role: element.getAttribute('role'),
                tab_index: element.tabIndex,
                is_focusable: element.matches(':focusable')
            },
            visibility: {
                is_visible: element.offsetParent !== null,
                is_in_viewport: isInViewport(element),
                computed_style: getComputedStyle(element)
            }
        }
        components.APPEND(component_info)
    
    RETURN components
END FUNCTION
```

### **Algorithm 2: Interactive Element Testing**
```pseudocode
FUNCTION testInteractiveElement(element, expected_behavior):
    test_results = {
        element_id: element.id,
        test_timestamp: getCurrentTimestamp(),
        tests_passed: 0,
        tests_failed: 0,
        issues: EMPTY_LIST
    }
    
    // Test 1: Element Existence and Visibility
    TRY:
        ASSERT element.exists() == TRUE
        ASSERT element.isDisplayed() == TRUE
        test_results.tests_passed += 1
    CATCH assertion_error:
        test_results.issues.APPEND("Element not visible or doesn't exist")
        test_results.tests_failed += 1
    
    // Test 2: Accessibility Compliance
    TRY:
        IF element.type IN ['button', 'link', 'input']:
            ASSERT element.hasAttribute('aria-label') OR element.textContent != ""
            ASSERT element.tabIndex >= 0
            ASSERT element.hasRole() == TRUE
        test_results.tests_passed += 1
    CATCH assertion_error:
        test_results.issues.APPEND("Accessibility requirements not met")
        test_results.tests_failed += 1
    
    // Test 3: Click/Interaction Behavior
    IF element.type == 'button' OR element.type == 'link':
        initial_state = capturePageState()
        
        TRY:
            CLICK element
            WAIT for state_change() OR timeout(5000)
            
            final_state = capturePageState()
            state_changed = (initial_state != final_state)
            
            IF expected_behavior.should_navigate:
                ASSERT current_url != initial_state.url
            ELIF expected_behavior.should_open_modal:
                ASSERT modal_is_visible() == TRUE
            ELIF expected_behavior.should_update_data:
                ASSERT data_has_changed() == TRUE
            
            test_results.tests_passed += 1
        CATCH assertion_error:
            test_results.issues.APPEND("Expected behavior not observed: " + expected_behavior)
            test_results.tests_failed += 1
    
    // Test 4: Form Validation (if applicable)
    IF element.type IN ['input', 'textarea', 'select']:
        TRY:
            // Test invalid input
            CLEAR element
            TYPE invalid_data INTO element
            TRIGGER validation()
            ASSERT validation_error_shown() == TRUE
            
            // Test valid input
            CLEAR element
            TYPE valid_data INTO element
            TRIGGER validation()
            ASSERT validation_error_shown() == FALSE
            
            test_results.tests_passed += 2
        CATCH assertion_error:
            test_results.issues.APPEND("Form validation not working correctly")
            test_results.tests_failed += 1
    
    // Test 5: Loading States and Error Handling
    IF element.triggers_async_action():
        TRY:
            CLICK element
            ASSERT loading_indicator_shown() == TRUE
            WAIT for loading_complete() OR timeout(30000)
            ASSERT loading_indicator_hidden() == TRUE
            
            // Test error states if API fails
            MOCK_API_FAILURE()
            CLICK element
            WAIT for error_message() OR timeout(10000)
            ASSERT error_message_shown() == TRUE
            
            test_results.tests_passed += 2
        CATCH assertion_error:
            test_results.issues.APPEND("Loading states or error handling issues")
            test_results.tests_failed += 1
    
    RETURN test_results
END FUNCTION
```

### **Algorithm 3: Form Workflow Testing**
```pseudocode
FUNCTION testFormWorkflow(form_element, test_data):
    workflow_results = {
        form_id: form_element.id,
        workflow_steps: EMPTY_LIST,
        overall_success: FALSE
    }
    
    // Step 1: Form Discovery and Field Mapping
    form_fields = FIND_ALL_ELEMENTS("input, textarea, select", within: form_element)
    required_fields = FILTER(form_fields, field => field.hasAttribute('required'))
    optional_fields = FILTER(form_fields, field => !field.hasAttribute('required'))
    
    step_1_result = {
        step: "Form Discovery",
        fields_found: form_fields.length,
        required_fields: required_fields.length,
        optional_fields: optional_fields.length,
        success: form_fields.length > 0
    }
    workflow_results.workflow_steps.APPEND(step_1_result)
    
    // Step 2: Empty Form Submission (Should Fail)
    TRY:
        submit_button = FIND_ELEMENT("button[type='submit'], input[type='submit']", within: form_element)
        CLICK submit_button
        WAIT for validation_errors() OR timeout(3000)
        
        validation_errors = FIND_ALL_ELEMENTS(".error, [role='alert'], .invalid-feedback")
        expected_error_count = required_fields.length
        
        step_2_result = {
            step: "Empty Form Validation",
            expected_errors: expected_error_count,
            actual_errors: validation_errors.length,
            success: validation_errors.length >= expected_error_count
        }
        workflow_results.workflow_steps.APPEND(step_2_result)
    CATCH error:
        step_2_result = {
            step: "Empty Form Validation",
            success: FALSE,
            error: error.message
        }
        workflow_results.workflow_steps.APPEND(step_2_result)
    
    // Step 3: Progressive Form Filling
    FOR each field IN form_fields:
        field_test_data = test_data.get(field.name) OR generateTestData(field.type)
        
        TRY:
            // Test invalid data first (if validation exists)
            IF field.hasValidation():
                TYPE invalid_data INTO field
                TRIGGER validation()
                ASSERT validation_error_shown(field) == TRUE
                CLEAR field
            
            // Test valid data
            TYPE field_test_data INTO field
            TRIGGER validation()
            ASSERT validation_error_shown(field) == FALSE
            
            field_result = {
                field_name: field.name,
                field_type: field.type,
                test_data: field_test_data,
                success: TRUE
            }
        CATCH error:
            field_result = {
                field_name: field.name,
                field_type: field.type,
                test_data: field_test_data,
                success: FALSE,
                error: error.message
            }
        
        workflow_results.workflow_steps.APPEND(field_result)
    
    // Step 4: Successful Form Submission
    TRY:
        CLICK submit_button
        WAIT for submission_success() OR timeout(10000)
        
        // Check for success indicators
        success_indicators = [
            modal_closed(),
            success_message_shown(),
            page_redirected(),
            data_updated(),
            loading_complete()
        ]
        
        submission_successful = ANY(success_indicators)
        
        step_4_result = {
            step: "Form Submission",
            success: submission_successful,
            indicators_found: FILTER(success_indicators, indicator => indicator == TRUE)
        }
        workflow_results.workflow_steps.APPEND(step_4_result)
        
        workflow_results.overall_success = submission_successful
        
    CATCH error:
        step_4_result = {
            step: "Form Submission",
            success: FALSE,
            error: error.message
        }
        workflow_results.workflow_steps.APPEND(step_4_result)
    
    RETURN workflow_results
END FUNCTION
```

### **Algorithm 4: Navigation Flow Testing**
```pseudocode
FUNCTION testNavigationFlow(navigation_map):
    navigation_results = {
        total_routes: navigation_map.length,
        successful_navigations: 0,
        failed_navigations: 0,
        route_results: EMPTY_LIST
    }
    
    FOR each route IN navigation_map:
        route_test = {
            from_page: route.from,
            to_page: route.to,
            trigger_element: route.trigger,
            navigation_method: route.method
        }
        
        TRY:
            // Navigate to starting page
            NAVIGATE_TO route.from
            WAIT for page_load_complete()
            
            // Capture initial state
            initial_url = getCurrentURL()
            initial_page_title = getPageTitle()
            
            // Trigger navigation
            SWITCH route.method:
                CASE 'click':
                    trigger_element = FIND_ELEMENT(route.trigger)
                    ASSERT trigger_element.exists() == TRUE
                    CLICK trigger_element
                    
                CASE 'form_submit':
                    form = FIND_ELEMENT(route.trigger)
                    fillFormWithValidData(form)
                    submitForm(form)
                    
                CASE 'direct_navigation':
                    NAVIGATE_TO route.to
            
            // Wait for navigation completion
            WAIT for url_changed() OR timeout(10000)
            
            // Verify navigation success
            final_url = getCurrentURL()
            final_page_title = getPageTitle()
            
            route_test.initial_url = initial_url
            route_test.final_url = final_url
            route_test.url_changed = (initial_url != final_url)
            route_test.title_changed = (initial_page_title != final_page_title)
            
            // Check for expected elements on destination page
            expected_elements = route.expected_elements OR EMPTY_LIST
            found_elements = 0
            
            FOR each expected_element IN expected_elements:
                element = FIND_ELEMENT(expected_element)
                IF element.exists():
                    found_elements += 1
            
            route_test.expected_elements_found = found_elements
            route_test.expected_elements_total = expected_elements.length
            route_test.success = (
                route_test.url_changed AND 
                found_elements == expected_elements.length
            )
            
            IF route_test.success:
                navigation_results.successful_navigations += 1
            ELSE:
                navigation_results.failed_navigations += 1
                
        CATCH error:
            route_test.success = FALSE
            route_test.error = error.message
            navigation_results.failed_navigations += 1
        
        navigation_results.route_results.APPEND(route_test)
    
    RETURN navigation_results
END FUNCTION
```

### **Algorithm 5: API Integration Testing**
```pseudocode
FUNCTION testAPIIntegration(page_components):
    api_test_results = {
        total_api_calls: 0,
        successful_calls: 0,
        failed_calls: 0,
        api_endpoints_tested: EMPTY_LIST
    }
    
    // Monitor network requests during component interactions
    ENABLE_NETWORK_MONITORING()
    
    FOR each component IN page_components:
        IF component.triggers_api_call():
            api_test = {
                component_id: component.id,
                expected_endpoint: component.api_endpoint,
                expected_method: component.api_method
            }
            
            TRY:
                // Clear previous network logs
                CLEAR_NETWORK_LOG()
                
                // Trigger component action
                INTERACT_WITH component
                
                // Wait for network request completion
                WAIT for network_idle() OR timeout(15000)
                
                // Analyze network requests
                network_requests = GET_NETWORK_LOG()
                api_requests = FILTER(network_requests, req => req.type == 'XHR' OR req.type == 'fetch')
                
                api_test.actual_requests = api_requests.length
                api_test.api_calls_made = EMPTY_LIST
                
                FOR each request IN api_requests:
                    call_details = {
                        url: request.url,
                        method: request.method,
                        status: request.status,
                        response_time: request.duration,
                        success: request.status >= 200 AND request.status < 300
                    }
                    
                    api_test.api_calls_made.APPEND(call_details)
                    api_test_results.total_api_calls += 1
                    
                    IF call_details.success:
                        api_test_results.successful_calls += 1
                    ELSE:
                        api_test_results.failed_calls += 1
                
                // Verify expected API behavior
                expected_call = FIND(api_requests, req => 
                    req.url.includes(api_test.expected_endpoint) AND 
                    req.method == api_test.expected_method
                )
                
                api_test.expected_call_made = expected_call != NULL
                api_test.success = (
                    api_test.expected_call_made AND 
                    expected_call.status >= 200 AND 
                    expected_call.status < 300
                )
                
                // Test error handling
                MOCK_API_ERROR(api_test.expected_endpoint, 500)
                INTERACT_WITH component
                WAIT for error_message() OR timeout(5000)
                
                api_test.error_handling_works = error_message_shown()
                
            CATCH error:
                api_test.success = FALSE
                api_test.error = error.message
            
            api_test_results.api_endpoints_tested.APPEND(api_test)
    
    DISABLE_NETWORK_MONITORING()
    RETURN api_test_results
END FUNCTION
```

### **Algorithm 6: Performance Testing**
```pseudocode
FUNCTION testPagePerformance(page_url):
    performance_results = {
        page_url: page_url,
        load_time_ms: 0,
        first_contentful_paint: 0,
        largest_contentful_paint: 0,
        cumulative_layout_shift: 0,
        first_input_delay: 0,
        bundle_size_kb: 0,
        memory_usage_mb: 0,
        performance_score: 0
    }
    
    // Start performance monitoring
    START_PERFORMANCE_MONITORING()
    
    // Navigate and measure load time
    start_time = getCurrentTime()
    NAVIGATE_TO page_url
    WAIT for page_load_complete()
    end_time = getCurrentTime()
    
    performance_results.load_time_ms = end_time - start_time
    
    // Get Web Vitals metrics
    performance_metrics = GET_PERFORMANCE_METRICS()
    performance_results.first_contentful_paint = performance_metrics.fcp
    performance_results.largest_contentful_paint = performance_metrics.lcp
    performance_results.cumulative_layout_shift = performance_metrics.cls
    performance_results.first_input_delay = performance_metrics.fid
    
    // Measure resource usage
    resource_info = GET_RESOURCE_USAGE()
    performance_results.bundle_size_kb = resource_info.total_size / 1024
    performance_results.memory_usage_mb = resource_info.memory_used / (1024 * 1024)
    
    // Calculate performance score
    score_factors = {
        load_time_weight: 0.3,
        fcp_weight: 0.2,
        lcp_weight: 0.2,
        cls_weight: 0.15,
        fid_weight: 0.15
    }
    
    // Score based on Google PageSpeed thresholds
    load_time_score = calculateScore(performance_results.load_time_ms, [1000, 3000])
    fcp_score = calculateScore(performance_results.first_contentful_paint, [1800, 3000])
    lcp_score = calculateScore(performance_results.largest_contentful_paint, [2500, 4000])
    cls_score = calculateScore(performance_results.cumulative_layout_shift, [0.1, 0.25])
    fid_score = calculateScore(performance_results.first_input_delay, [100, 300])
    
    performance_results.performance_score = (
        load_time_score * score_factors.load_time_weight +
        fcp_score * score_factors.fcp_weight +
        lcp_score * score_factors.lcp_weight +
        cls_score * score_factors.cls_weight +
        fid_score * score_factors.fid_weight
    ) * 100
    
    STOP_PERFORMANCE_MONITORING()
    RETURN performance_results
END FUNCTION
```

### **Algorithm 7: Accessibility Testing**
```pseudocode
FUNCTION testAccessibility(page_components):
    accessibility_results = {
        total_elements: page_components.length,
        accessible_elements: 0,
        issues_found: EMPTY_LIST,
        wcag_compliance_level: 'UNKNOWN'
    }
    
    FOR each component IN page_components:
        accessibility_test = {
            element_id: component.id,
            element_type: component.type,
            issues: EMPTY_LIST,
            passes: EMPTY_LIST
        }
        
        // Test 1: Semantic HTML
        IF component.type IN ['button', 'link', 'input', 'form']:
            IF component.tagName.toLowerCase() == component.type:
                accessibility_test.passes.APPEND("Semantic HTML used")
            ELSE:
                accessibility_test.issues.APPEND("Non-semantic HTML - should use proper tags")
        
        // Test 2: ARIA Labels and Roles
        IF component.hasAttribute('aria-label') OR component.textContent.trim() != "":
            accessibility_test.passes.APPEND("Has accessible name")
        ELSE:
            accessibility_test.issues.APPEND("Missing accessible name (aria-label or text content)")
        
        // Test 3: Keyboard Navigation
        IF component.type IN ['button', 'link', 'input']:
            TRY:
                FOCUS component
                ASSERT document.activeElement == component
                accessibility_test.passes.APPEND("Keyboard focusable")
                
                // Test Enter/Space key activation
                IF component.type == 'button':
                    PRESS_KEY 'Enter'
                    // Should trigger click behavior
                    accessibility_test.passes.APPEND("Enter key activation works")
                    
            CATCH error:
                accessibility_test.issues.APPEND("Not keyboard accessible")
        
        // Test 4: Color Contrast
        computed_style = getComputedStyle(component)
        foreground_color = computed_style.color
        background_color = computed_style.backgroundColor
        
        contrast_ratio = calculateContrastRatio(foreground_color, background_color)
        
        IF contrast_ratio >= 4.5:  // WCAG AA standard
            accessibility_test.passes.APPEND("Sufficient color contrast")
        ELSE:
            accessibility_test.issues.APPEND(`Low color contrast: ${contrast_ratio}:1`)
        
        // Test 5: Focus Indicators
        TRY:
            FOCUS component
            focus_style = getComputedStyle(component, ':focus')
            has_focus_indicator = (
                focus_style.outline != 'none' OR
                focus_style.boxShadow != 'none' OR
                focus_style.border != computed_style.border
            )
            
            IF has_focus_indicator:
                accessibility_test.passes.APPEND("Has focus indicator")
            ELSE:
                accessibility_test.issues.APPEND("Missing focus indicator")
                
        CATCH error:
            accessibility_test.issues.APPEND("Focus testing failed")
        
        // Test 6: Screen Reader Compatibility
        screen_reader_text = getScreenReaderText(component)
        IF screen_reader_text.trim() != "":
            accessibility_test.passes.APPEND("Has screen reader accessible text")
        ELSE:
            accessibility_test.issues.APPEND("No screen reader accessible text")
        
        // Calculate element accessibility score
        total_tests = accessibility_test.passes.length + accessibility_test.issues.length
        passed_tests = accessibility_test.passes.length
        
        IF accessibility_test.issues.length == 0:
            accessibility_results.accessible_elements += 1
        ELSE:
            accessibility_results.issues_found.APPEND(accessibility_test)
    
    // Determine WCAG compliance level
    accessibility_percentage = (accessibility_results.accessible_elements / accessibility_results.total_elements) * 100
    
    IF accessibility_percentage >= 95:
        accessibility_results.wcag_compliance_level = 'AAA'
    ELIF accessibility_percentage >= 85:
        accessibility_results.wcag_compliance_level = 'AA'
    ELIF accessibility_percentage >= 70:
        accessibility_results.wcag_compliance_level = 'A'
    ELSE:
        accessibility_results.wcag_compliance_level = 'NON_COMPLIANT'
    
    RETURN accessibility_results
END FUNCTION
```

### **Algorithm 8: Cross-Browser Compatibility Testing**
```pseudocode
FUNCTION testCrossBrowserCompatibility(test_pages, browsers):
    compatibility_results = {
        browsers_tested: browsers.length,
        pages_tested: test_pages.length,
        total_tests: browsers.length * test_pages.length,
        passed_tests: 0,
        failed_tests: 0,
        browser_results: EMPTY_MAP
    }
    
    FOR each browser IN browsers:
        browser_result = {
            browser_name: browser.name,
            browser_version: browser.version,
            page_results: EMPTY_LIST,
            overall_compatibility: 0
        }
        
        LAUNCH_BROWSER browser
        
        FOR each page IN test_pages:
            page_test = {
                page_url: page.url,
                layout_correct: FALSE,
                functionality_works: FALSE,
                javascript_errors: EMPTY_LIST,
                css_issues: EMPTY_LIST
            }
            
            TRY:
                NAVIGATE_TO page.url
                WAIT for page_load_complete()
                
                // Test 1: Layout and Styling
                screenshot = TAKE_SCREENSHOT()
                layout_differences = compareWithBaseline(screenshot, page.baseline_screenshot)
                page_test.layout_correct = layout_differences.score > 0.95
                
                // Test 2: JavaScript Functionality
                js_errors = GET_CONSOLE_ERRORS()
                page_test.javascript_errors = FILTER(js_errors, error => error.level == 'error')
                
                // Test core functionality
                core_features = page.core_features OR EMPTY_LIST
                working_features = 0
                
                FOR each feature IN core_features:
                    TRY:
                        EXECUTE_FEATURE_TEST feature
                        working_features += 1
                    CATCH error:
                        page_test.javascript_errors.APPEND(error.message)
                
                page_test.functionality_works = (working_features == core_features.length)
                
                // Test 3: CSS Compatibility
                computed_styles = GET_ALL_COMPUTED_STYLES()
                css_issues = EMPTY_LIST
                
                FOR each element_style IN computed_styles:
                    unsupported_properties = FILTER(element_style.properties, prop => 
                        !browser.supports(prop.name, prop.value)
                    )
                    css_issues.EXTEND(unsupported_properties)
                
                page_test.css_issues = css_issues
                
                // Calculate page compatibility score
                page_score = 0
                IF page_test.layout_correct: page_score += 40
                IF page_test.functionality_works: page_score += 40
                IF page_test.javascript_errors.length == 0: page_score += 10
                IF page_test.css_issues.length == 0: page_score += 10
                
                page_test.compatibility_score = page_score
                
                IF page_score >= 80:
                    compatibility_results.passed_tests += 1
                ELSE:
                    compatibility_results.failed_tests += 1
                
            CATCH error:
                page_test.compatibility_score = 0
                page_test.error = error.message
                compatibility_results.failed_tests += 1
            
            browser_result.page_results.APPEND(page_test)
        
        // Calculate overall browser compatibility
        total_score = SUM(page_result.compatibility_score for page_result in browser_result.page_results)
        max_possible_score = test_pages.length * 100
        browser_result.overall_compatibility = (total_score / max_possible_score) * 100
        
        CLOSE_BROWSER()
        compatibility_results.browser_results[browser.name] = browser_result
    
    RETURN compatibility_results
END FUNCTION
```

---

## 🧪 TDD Test Implementation Strategy

### **Red-Green-Refactor Cycle for UI Testing**:

```pseudocode
FUNCTION implementTDDForFeature(feature_specification):
    // RED: Write failing test
    test_case = CREATE_TEST_CASE(feature_specification)
    ASSERT test_case.run() == FAIL
    
    // GREEN: Implement minimal functionality
    implementation = IMPLEMENT_FEATURE(feature_specification)
    ASSERT test_case.run() == PASS
    
    // REFACTOR: Improve implementation
    enhanced_implementation = REFACTOR_FEATURE(implementation)
    ASSERT test_case.run() == PASS
    ASSERT performance_acceptable(enhanced_implementation)
    
    RETURN enhanced_implementation
END FUNCTION
```

### **Test Data Generation**:

```pseudocode
FUNCTION generateTestData(field_type, validation_rules):
    SWITCH field_type:
        CASE 'email':
            valid_data = 'test@example.com'
            invalid_data = 'invalid-email'
        CASE 'password':
            valid_data = generateStrongPassword(validation_rules.min_length)
            invalid_data = 'weak'
        CASE 'number':
            valid_data = RANDOM_INT(validation_rules.min, validation_rules.max)
            invalid_data = validation_rules.max + 1
        DEFAULT:
            valid_data = 'Valid test data'
            invalid_data = ''
    
    RETURN {valid: valid_data, invalid: invalid_data}
END FUNCTION
```

---

*These pseudocode algorithms form the foundation for systematic UI testing using SPARC+TDD methodology.*