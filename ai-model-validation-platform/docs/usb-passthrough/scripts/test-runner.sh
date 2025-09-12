#!/bin/bash

# LabJack USB Passthrough Test Runner
# Comprehensive testing script for validating USB passthrough functionality

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$DOCS_DIR")"
LOG_DIR="$SCRIPT_DIR/logs"
REPORT_DIR="$SCRIPT_DIR/reports"

# Create directories
mkdir -p "$LOG_DIR" "$REPORT_DIR"

# Logging setup
LOG_FILE="$LOG_DIR/test_run_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "========================================="
echo "LabJack USB Passthrough Test Runner"
echo "========================================="
echo "Started: $(date)"
echo "Log file: $LOG_FILE"
echo ""

# Functions
log_info() {
    echo "[INFO] $(date '+%H:%M:%S') $1"
}

log_error() {
    echo "[ERROR] $(date '+%H:%M:%S') $1" >&2
}

log_success() {
    echo "[SUCCESS] $(date '+%H:%M:%S') $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing_deps=0
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 is not installed"
        ((missing_deps++))
    else
        log_info "Python3: $(python3 --version)"
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        log_error "pip3 is not installed"
        ((missing_deps++))
    fi
    
    # Check required Python packages
    local python_packages=("u3" "numpy" "matplotlib" "scipy" "psutil")
    for package in "${python_packages[@]}"; do
        if ! python3 -c "import $package" &>/dev/null; then
            log_error "Python package '$package' is not installed"
            ((missing_deps++))
        fi
    done
    
    # Check USB tools
    if ! command -v lsusb &> /dev/null; then
        log_error "lsusb is not installed (install usbutils)"
        ((missing_deps++))
    fi
    
    # Check for LabJack device
    if ! lsusb | grep -q "0cd5:"; then
        log_error "No LabJack device detected"
        log_info "Connect a LabJack device and ensure it's attached to this environment"
        ((missing_deps++))
    else
        log_success "LabJack device detected: $(lsusb | grep '0cd5:')"
    fi
    
    if [ $missing_deps -gt 0 ]; then
        log_error "$missing_deps prerequisite(s) missing"
        return 1
    fi
    
    log_success "All prerequisites met"
    return 0
}

install_test_dependencies() {
    log_info "Installing test dependencies..."
    
    # Update package list
    sudo apt update -qq
    
    # Install system dependencies
    sudo apt install -y \
        python3-pip \
        python3-venv \
        usbutils \
        build-essential \
        libusb-1.0-0-dev
    
    # Install Python dependencies
    pip3 install --user \
        u3 \
        numpy \
        matplotlib \
        scipy \
        psutil \
        pytest \
        pytest-html \
        pytest-json-report
    
    log_success "Test dependencies installed"
}

run_basic_functionality_tests() {
    log_info "Running basic functionality tests..."
    
    local test_script="$SCRIPT_DIR/basic_functionality_test.py"
    
    cat > "$test_script" << 'EOF'
#!/usr/bin/env python3
import sys
import time
import traceback

def test_device_connection():
    """Test basic device connection"""
    print("Testing device connection...")
    try:
        import u3
        device = u3.U3()
        name = device.getName()
        print(f"✓ Connected to: {name}")
        device.close()
        return True
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

def test_analog_input():
    """Test analog input reading"""
    print("Testing analog input...")
    try:
        import u3
        device = u3.U3()
        
        voltages = []
        for channel in range(4):
            voltage = device.getAIN(channel)
            voltages.append(voltage)
            print(f"  Channel {channel}: {voltage:.3f}V")
        
        device.close()
        
        # Check if readings are reasonable
        if all(-10 <= v <= 10 for v in voltages):
            print("✓ Analog input test passed")
            return True
        else:
            print("✗ Analog input readings out of range")
            return False
            
    except Exception as e:
        print(f"✗ Analog input test failed: {e}")
        return False

def test_digital_io():
    """Test digital I/O"""
    print("Testing digital I/O...")
    try:
        import u3
        device = u3.U3()
        
        # Test digital output
        device.setDIOState(4, 1)  # Set FIO4 high
        time.sleep(0.1)
        device.setDIOState(4, 0)  # Set FIO4 low
        
        print("✓ Digital I/O test passed")
        device.close()
        return True
        
    except Exception as e:
        print(f"✗ Digital I/O test failed: {e}")
        return False

def test_streaming():
    """Test streaming mode"""
    print("Testing streaming mode...")
    try:
        import u3
        device = u3.U3()
        
        # Configure streaming
        device.streamConfig(
            NumChannels=2,
            ChannelNumbers=[0, 1],
            ChannelOptions=[0, 0],
            SettlingFactor=0,
            ResolutionIndex=0,
            SampleFrequency=1000
        )
        
        # Start streaming
        device.streamStart()
        
        try:
            # Collect some data
            data = device.streamData()
            sample_count = len(data['AIN0'])
            print(f"  Collected {sample_count} samples")
            
            if sample_count > 0:
                print("✓ Streaming test passed")
                return True
            else:
                print("✗ No streaming data received")
                return False
                
        finally:
            device.streamStop()
            device.close()
            
    except Exception as e:
        print(f"✗ Streaming test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all basic functionality tests"""
    tests = [
        test_device_connection,
        test_analog_input,
        test_digital_io,
        test_streaming
    ]
    
    passed = 0
    failed = 0
    
    print("=" * 50)
    print("Basic Functionality Tests")
    print("=" * 50)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            failed += 1
        print("")
    
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All basic functionality tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
EOF

    chmod +x "$test_script"
    
    if python3 "$test_script"; then
        log_success "Basic functionality tests passed"
        return 0
    else
        log_error "Basic functionality tests failed"
        return 1
    fi
}

run_performance_tests() {
    log_info "Running performance tests..."
    
    local test_script="$SCRIPT_DIR/performance_test.py"
    
    cat > "$test_script" << 'EOF'
#!/usr/bin/env python3
import sys
import time
import statistics
import threading

def test_read_latency():
    """Test single read latency"""
    print("Testing read latency...")
    try:
        import u3
        device = u3.U3()
        
        latencies = []
        for _ in range(100):
            start_time = time.perf_counter()
            voltage = device.getAIN(0)
            end_time = time.perf_counter()
            latencies.append((end_time - start_time) * 1000)  # Convert to ms
        
        device.close()
        
        mean_latency = statistics.mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        
        print(f"  Mean latency: {mean_latency:.2f}ms")
        print(f"  Min/Max: {min_latency:.2f}ms / {max_latency:.2f}ms")
        print(f"  Rate: {1000/mean_latency:.1f} reads/sec")
        
        if mean_latency < 5.0:  # 5ms threshold
            print("✓ Latency test passed")
            return True, {'mean_ms': mean_latency, 'rate_hz': 1000/mean_latency}
        else:
            print("✗ Latency too high")
            return False, {'mean_ms': mean_latency, 'rate_hz': 1000/mean_latency}
            
    except Exception as e:
        print(f"✗ Latency test failed: {e}")
        return False, None

def test_streaming_throughput():
    """Test streaming throughput"""
    print("Testing streaming throughput...")
    try:
        import u3
        device = u3.U3()
        
        sample_rate = 1000
        duration = 5
        
        # Configure streaming
        device.streamConfig(
            NumChannels=4,
            ChannelNumbers=[0, 1, 2, 3],
            ChannelOptions=[0, 0, 0, 0],
            SettlingFactor=0,
            ResolutionIndex=0,
            SampleFrequency=sample_rate
        )
        
        device.streamStart()
        
        try:
            start_time = time.time()
            total_samples = 0
            
            while time.time() - start_time < duration:
                data = device.streamData()
                total_samples += len(data['AIN0'])
                time.sleep(0.01)
            
            actual_duration = time.time() - start_time
            actual_rate = total_samples / actual_duration
            rate_accuracy = (actual_rate / sample_rate) * 100
            
            print(f"  Target rate: {sample_rate} Hz")
            print(f"  Actual rate: {actual_rate:.1f} Hz")
            print(f"  Accuracy: {rate_accuracy:.1f}%")
            print(f"  Total samples: {total_samples}")
            
            if rate_accuracy >= 90:
                print("✓ Throughput test passed")
                return True, {'actual_rate': actual_rate, 'accuracy': rate_accuracy}
            else:
                print("✗ Throughput accuracy too low")
                return False, {'actual_rate': actual_rate, 'accuracy': rate_accuracy}
                
        finally:
            device.streamStop()
            device.close()
            
    except Exception as e:
        print(f"✗ Throughput test failed: {e}")
        return False, None

def test_concurrent_access():
    """Test concurrent device access"""
    print("Testing concurrent access...")
    try:
        import u3
        import queue
        
        num_threads = 2
        duration = 3
        results_queue = queue.Queue()
        
        def worker_thread(thread_id):
            try:
                device = u3.U3()
                start_time = time.time()
                read_count = 0
                
                while time.time() - start_time < duration:
                    voltage = device.getAIN(thread_id % 4)
                    read_count += 1
                    time.sleep(0.01)
                
                device.close()
                actual_duration = time.time() - start_time
                results_queue.put({
                    'thread_id': thread_id,
                    'read_count': read_count,
                    'rate': read_count / actual_duration
                })
            except Exception as e:
                results_queue.put({'thread_id': thread_id, 'error': str(e)})
        
        # Start threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Collect results
        total_reads = 0
        total_rate = 0
        errors = 0
        
        while not results_queue.empty():
            result = results_queue.get()
            if 'error' in result:
                print(f"  Thread {result['thread_id']} error: {result['error']}")
                errors += 1
            else:
                print(f"  Thread {result['thread_id']}: {result['read_count']} reads, {result['rate']:.1f} Hz")
                total_reads += result['read_count']
                total_rate += result['rate']
        
        if errors == 0:
            print(f"  Combined rate: {total_rate:.1f} Hz")
            print("✓ Concurrent access test passed")
            return True, {'total_rate': total_rate, 'threads': num_threads}
        else:
            print("✗ Concurrent access test failed")
            return False, None
            
    except Exception as e:
        print(f"✗ Concurrent access test failed: {e}")
        return False, None

def main():
    """Run performance tests"""
    tests = [
        ('Latency', test_read_latency),
        ('Throughput', test_streaming_throughput),
        ('Concurrent Access', test_concurrent_access)
    ]
    
    results = {}
    passed = 0
    failed = 0
    
    print("=" * 50)
    print("Performance Tests")
    print("=" * 50)
    
    for test_name, test_func in tests:
        print(f"\n{test_name} Test:")
        try:
            success, metrics = test_func()
            results[test_name.lower().replace(' ', '_')] = {
                'success': success,
                'metrics': metrics
            }
            
            if success:
                passed += 1
            else:
                failed += 1
                
        except Exception as e:
            print(f"✗ {test_name} test crashed: {e}")
            results[test_name.lower().replace(' ', '_')] = {
                'success': False,
                'error': str(e)
            }
            failed += 1
    
    print(f"\nPerformance Test Results: {passed} passed, {failed} failed")
    
    # Save results
    import json
    with open('performance_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    if failed == 0:
        print("🎉 All performance tests passed!")
        return 0
    else:
        print("❌ Some performance tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
EOF

    chmod +x "$test_script"
    
    if python3 "$test_script"; then
        log_success "Performance tests passed"
        return 0
    else
        log_error "Performance tests failed"
        return 1
    fi
}

run_stress_tests() {
    log_info "Running stress tests..."
    
    local test_script="$SCRIPT_DIR/stress_test.py"
    
    cat > "$test_script" << 'EOF'
#!/usr/bin/env python3
import sys
import time
import gc
import psutil
import threading
from concurrent.futures import ThreadPoolExecutor

def stress_test_continuous_reading():
    """Stress test with continuous reading"""
    print("Stress test: Continuous reading for 60 seconds...")
    try:
        import u3
        device = u3.U3()
        
        start_time = time.time()
        read_count = 0
        errors = 0
        
        # Monitor memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        while time.time() - start_time < 60:  # 1 minute
            try:
                voltage = device.getAIN(0)
                read_count += 1
                
                # Check every 1000 reads
                if read_count % 1000 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_increase = current_memory - initial_memory
                    elapsed = time.time() - start_time
                    rate = read_count / elapsed
                    
                    print(f"  {read_count} reads, {rate:.1f} Hz, Memory: {current_memory:.1f}MB (+{memory_increase:.1f}MB)")
                    
                    # Force garbage collection
                    gc.collect()
                    
            except Exception as e:
                errors += 1
                if errors % 10 == 0:
                    print(f"  Errors: {errors}")
        
        device.close()
        
        elapsed = time.time() - start_time
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        print(f"  Total reads: {read_count}")
        print(f"  Average rate: {read_count/elapsed:.1f} Hz")
        print(f"  Errors: {errors}")
        print(f"  Memory increase: {memory_increase:.1f}MB")
        
        # Pass if error rate < 1% and memory increase < 50MB
        error_rate = errors / read_count * 100 if read_count > 0 else 100
        if error_rate < 1.0 and memory_increase < 50:
            print("✓ Continuous reading stress test passed")
            return True
        else:
            print(f"✗ Stress test failed (error rate: {error_rate:.1f}%, memory: {memory_increase:.1f}MB)")
            return False
            
    except Exception as e:
        print(f"✗ Continuous reading stress test failed: {e}")
        return False

def stress_test_streaming():
    """Stress test streaming mode"""
    print("Stress test: High-rate streaming...")
    try:
        import u3
        device = u3.U3()
        
        # Configure high-rate streaming
        sample_rate = 5000  # 5kHz
        duration = 30  # 30 seconds
        
        device.streamConfig(
            NumChannels=4,
            ChannelNumbers=[0, 1, 2, 3],
            ChannelOptions=[0, 0, 0, 0],
            SettlingFactor=0,
            ResolutionIndex=0,
            SampleFrequency=sample_rate
        )
        
        device.streamStart()
        
        try:
            start_time = time.time()
            total_samples = 0
            buffer_overruns = 0
            
            while time.time() - start_time < duration:
                try:
                    data = device.streamData()
                    samples = len(data['AIN0'])
                    total_samples += samples
                    
                    if total_samples % 50000 == 0:  # Every 50k samples
                        elapsed = time.time() - start_time
                        actual_rate = total_samples / elapsed
                        print(f"  {total_samples} samples, {actual_rate:.1f} Hz actual")
                        
                except Exception as e:
                    if "buffer overrun" in str(e).lower():
                        buffer_overruns += 1
                    else:
                        raise
            
            elapsed = time.time() - start_time
            actual_rate = total_samples / elapsed
            rate_accuracy = (actual_rate / sample_rate) * 100
            
            print(f"  Target rate: {sample_rate} Hz")
            print(f"  Actual rate: {actual_rate:.1f} Hz")
            print(f"  Accuracy: {rate_accuracy:.1f}%")
            print(f"  Buffer overruns: {buffer_overruns}")
            
            # Pass if accuracy > 80% and buffer overruns < 10
            if rate_accuracy > 80 and buffer_overruns < 10:
                print("✓ Streaming stress test passed")
                return True
            else:
                print("✗ Streaming stress test failed")
                return False
                
        finally:
            device.streamStop()
            device.close()
            
    except Exception as e:
        print(f"✗ Streaming stress test failed: {e}")
        return False

def stress_test_multiple_devices():
    """Stress test multiple device connections"""
    print("Stress test: Multiple device connections...")
    try:
        import u3
        
        # Try to open multiple connections (simulating multiple processes)
        max_connections = 5
        successful_connections = 0
        
        devices = []
        
        for i in range(max_connections):
            try:
                device = u3.U3()
                devices.append(device)
                successful_connections += 1
                print(f"  Connection {i+1}: Success")
            except Exception as e:
                print(f"  Connection {i+1}: Failed - {e}")
                break
        
        # Test reading from all connected devices
        if successful_connections > 0:
            print(f"  Testing {successful_connections} simultaneous connections...")
            
            def read_from_device(device_id):
                device = devices[device_id]
                readings = []
                for _ in range(10):
                    voltage = device.getAIN(0)
                    readings.append(voltage)
                    time.sleep(0.01)
                return readings
            
            with ThreadPoolExecutor(max_workers=successful_connections) as executor:
                futures = [executor.submit(read_from_device, i) for i in range(successful_connections)]
                
                for i, future in enumerate(futures):
                    try:
                        readings = future.result(timeout=10)
                        print(f"    Device {i+1}: {len(readings)} readings completed")
                    except Exception as e:
                        print(f"    Device {i+1}: Failed - {e}")
        
        # Close all devices
        for device in devices:
            try:
                device.close()
            except:
                pass
        
        if successful_connections >= 1:
            print("✓ Multiple devices stress test passed")
            return True
        else:
            print("✗ Multiple devices stress test failed")
            return False
            
    except Exception as e:
        print(f"✗ Multiple devices stress test failed: {e}")
        return False

def main():
    """Run stress tests"""
    tests = [
        stress_test_continuous_reading,
        stress_test_streaming,
        stress_test_multiple_devices
    ]
    
    passed = 0
    failed = 0
    
    print("=" * 50)
    print("Stress Tests")
    print("=" * 50)
    
    for test in tests:
        print(f"\n{test.__name__.replace('stress_test_', '').replace('_', ' ').title()}:")
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print(f"\nStress Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All stress tests passed!")
        return 0
    else:
        print("❌ Some stress tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
EOF

    chmod +x "$test_script"
    
    if python3 "$test_script"; then
        log_success "Stress tests passed"
        return 0
    else
        log_error "Stress tests failed"
        return 1
    fi
}

generate_test_report() {
    log_info "Generating test report..."
    
    local report_file="$REPORT_DIR/test_report_$(date +%Y%m%d_%H%M%S).html"
    
    cat > "$report_file" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>LabJack USB Passthrough Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 15px; border-radius: 5px; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .pass { color: green; font-weight: bold; }
        .fail { color: red; font-weight: bold; }
        .info { color: blue; }
        pre { background-color: #f5f5f5; padding: 10px; border-radius: 3px; overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>LabJack USB Passthrough Test Report</h1>
        <p><strong>Generated:</strong> $(date)</p>
        <p><strong>Platform:</strong> $(uname -a)</p>
        <p><strong>LabJack Device:</strong> $(lsusb | grep '0cd5:' || echo "Not detected")</p>
    </div>

    <div class="section">
        <h2>Test Environment</h2>
        <table>
            <tr><th>Component</th><th>Version/Status</th></tr>
            <tr><td>Python</td><td>$(python3 --version)</td></tr>
            <tr><td>USB Tools</td><td>$(lsusb --version 2>/dev/null || echo "Unknown")</td></tr>
            <tr><td>LabJack u3 Library</td><td>$(python3 -c "import u3; print('Available')" 2>/dev/null || echo "Not available")</td></tr>
        </table>
    </div>

    <div class="section">
        <h2>Test Results Summary</h2>
        <p>Detailed test results are available in the log file: <code>$LOG_FILE</code></p>
        <p>For complete test output and debugging information, please refer to the log file.</p>
    </div>

    <div class="section">
        <h2>Recommendations</h2>
        <ul>
            <li>Ensure all tests pass before using in production</li>
            <li>Monitor performance metrics during actual usage</li>
            <li>Regular testing is recommended after system updates</li>
            <li>Check log files for any warnings or errors</li>
        </ul>
    </div>

    <div class="section">
        <h2>Log Files</h2>
        <p><strong>Test Log:</strong> $LOG_FILE</p>
        <p><strong>Performance Results:</strong> $(find "$SCRIPT_DIR" -name "performance_results.json" -newer "$LOG_FILE" 2>/dev/null | head -1 || echo "Not generated")</p>
    </div>
</body>
</html>
EOF

    log_success "Test report generated: $report_file"
    
    # Try to open report in browser if available
    if command -v xdg-open &> /dev/null; then
        xdg-open "$report_file" 2>/dev/null &
    elif command -v open &> /dev/null; then
        open "$report_file" 2>/dev/null &
    fi
}

# Main execution
main() {
    local test_mode="${1:-full}"
    local exit_code=0
    
    case "$test_mode" in
        "prereq"|"prerequisites")
            if ! check_prerequisites; then
                log_info "Installing missing dependencies..."
                install_test_dependencies
                if ! check_prerequisites; then
                    log_error "Prerequisites check failed after installation"
                    exit_code=1
                fi
            fi
            ;;
        "basic"|"functionality")
            if ! run_basic_functionality_tests; then
                exit_code=1
            fi
            ;;
        "performance"|"perf")
            if ! run_performance_tests; then
                exit_code=1
            fi
            ;;
        "stress")
            if ! run_stress_tests; then
                exit_code=1
            fi
            ;;
        "all"|"full"|*)
            log_info "Running full test suite..."
            
            # Check prerequisites
            if ! check_prerequisites; then
                log_info "Installing missing dependencies..."
                install_test_dependencies
                if ! check_prerequisites; then
                    log_error "Prerequisites check failed"
                    exit_code=1
                fi
            fi
            
            # Run all tests if prerequisites are met
            if [ $exit_code -eq 0 ]; then
                if ! run_basic_functionality_tests; then
                    exit_code=1
                fi
                
                if ! run_performance_tests; then
                    exit_code=1
                fi
                
                if ! run_stress_tests; then
                    exit_code=1
                fi
            fi
            
            # Generate report
            generate_test_report
            ;;
    esac
    
    echo ""
    echo "========================================="
    if [ $exit_code -eq 0 ]; then
        log_success "All tests completed successfully!"
    else
        log_error "Some tests failed. Check log file for details."
    fi
    echo "Test log: $LOG_FILE"
    echo "Completed: $(date)"
    echo "========================================="
    
    return $exit_code
}

# Handle command line arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 [test_mode]"
    echo ""
    echo "Test modes:"
    echo "  prereq|prerequisites  - Check and install prerequisites only"
    echo "  basic|functionality   - Run basic functionality tests"
    echo "  performance|perf      - Run performance tests"
    echo "  stress                - Run stress tests"
    echo "  all|full              - Run all tests (default)"
    echo ""
    echo "Examples:"
    echo "  $0 prereq       # Check prerequisites"
    echo "  $0 basic        # Run basic tests only"
    echo "  $0 all          # Run complete test suite"
    echo ""
fi

# Run main function with arguments
main "$@"
exit $?