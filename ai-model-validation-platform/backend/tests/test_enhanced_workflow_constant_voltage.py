"""
Verification test for constant_voltage_mode parameter in Enhanced Test Workflow API
Tests that the parameter is correctly added to DetectionTestConfig
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_enhanced_test_workflow_integrated import DetectionTestConfig


def test_constant_voltage_mode_parameter():
    """Test that constant_voltage_mode parameter exists and works correctly"""

    print("Testing constant_voltage_mode parameter...")
    print()

    # Test 1: Default value should be False
    config1 = DetectionTestConfig(project_id="test-project")
    assert config1.constant_voltage_mode == False, "Default should be False"
    print("✅ Test 1 PASSED: Default value is False")

    # Test 2: Can be set to True
    config2 = DetectionTestConfig(
        project_id="test-project",
        constant_voltage_mode=True
    )
    assert config2.constant_voltage_mode == True, "Should be able to set to True"
    print("✅ Test 2 PASSED: Can be set to True")

    # Test 3: Can be set to False explicitly
    config3 = DetectionTestConfig(
        project_id="test-project",
        constant_voltage_mode=False
    )
    assert config3.constant_voltage_mode == False, "Should be able to set to False"
    print("✅ Test 3 PASSED: Can be set to False explicitly")

    # Test 4: Parameter appears in dict/model output
    config_dict = config2.model_dump()
    assert "constant_voltage_mode" in config_dict, "Parameter should be in model output"
    assert config_dict["constant_voltage_mode"] == True, "Value should match in model output"
    print("✅ Test 4 PASSED: Parameter appears in model output")

    # Test 5: Full configuration with all parameters
    config4 = DetectionTestConfig(
        project_id="test-project",
        detection_window_ms=1000.0,
        voltage_threshold=3.5,
        sample_rate=2000,
        channels=["AIN0", "AIN1", "AIN2"],
        constant_voltage_mode=True
    )
    assert config4.constant_voltage_mode == True, "Should work with full config"
    assert config4.voltage_threshold == 3.5, "Other parameters should be preserved"
    assert config4.sample_rate == 2000, "Other parameters should be preserved"
    print("✅ Test 5 PASSED: Works with full configuration")

    print()
    print("="*60)
    print("ALL TESTS PASSED ✅")
    print("="*60)
    print()
    print("Summary:")
    print("- constant_voltage_mode parameter successfully added to DetectionTestConfig")
    print("- Default value: False (maintains backward compatibility)")
    print("- Can be set to True to bypass debounce for constant voltage testing")
    print("- Parameter is accessible and appears in model output")
    print()
    print("Next Steps:")
    print("1. Frontend UI should add checkbox for 'Constant Voltage Mode'")
    print("2. Backend should integrate with detection service when called")
    print("3. Expected behavior:")
    print("   - False: Uses 100ms debounce (33% detection rate)")
    print("   - True: Bypasses debounce (100% detection rate)")


if __name__ == "__main__":
    test_constant_voltage_mode_parameter()
