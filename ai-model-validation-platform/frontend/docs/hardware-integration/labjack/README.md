# LabJack Windows Integration Guide

## Overview

This directory contains comprehensive documentation, diagnostic tools, and scripts for integrating LabJack hardware devices with the AI Model Validation Platform on Windows systems.

## Contents

### 📚 Documentation
- **[Windows Diagnostic Guide](./windows-diagnostic-guide.md)** - Complete diagnostic and troubleshooting procedures
- **[Troubleshooting Commands](./troubleshooting-commands.md)** - Quick reference for common issues and solutions

### 🔧 Scripts and Tools
- **[PowerShell Diagnostics](../../scripts/labjack-diagnostics.ps1)** - Automated diagnostic script
- **[Python Hardware Validator](../../scripts/labjack-hardware-validator.py)** - Comprehensive hardware testing
- **[Quick Fix Batch Script](../../scripts/labjack-quick-fix.bat)** - Interactive troubleshooting tool

### 🧪 Test Suites
- **[Integration Validation Tests](../../tests/labjack-integration-validation.test.ts)** - Jest-based validation suite

## Quick Start

### For System Administrators

1. **Run Quick Diagnostic**:
   ```cmd
   # Navigate to scripts directory
   cd scripts
   
   # Run quick fix tool (interactive)
   labjack-quick-fix.bat
   
   # Or run full diagnostic
   powershell -ExecutionPolicy Bypass -File labjack-diagnostics.ps1 -ExportResults
   ```

2. **Check Common Issues**:
   - Verify LabJack software is installed
   - Check Device Manager for driver issues
   - Test network connectivity (for Ethernet devices)
   - Validate Windows Firewall rules

### For Developers

1. **Run Integration Tests**:
   ```bash
   # Run the Jest test suite
   npm test -- labjack-integration-validation.test.ts
   
   # Or run with coverage
   npm test -- --coverage labjack-integration-validation.test.ts
   ```

2. **Python Hardware Validation**:
   ```bash
   # Run comprehensive hardware validation
   python scripts/labjack-hardware-validator.py --verbose --export-results
   
   # Test specific device type
   python scripts/labjack-hardware-validator.py --device-type T7 --connection-type USB
   ```

### For Hardware Technicians

1. **Use the Windows Diagnostic Guide** for step-by-step troubleshooting procedures
2. **Reference Troubleshooting Commands** for immediate solutions
3. **Run automated diagnostics** to identify system-specific issues

## Common Issues and Solutions

### Issue: Device Not Detected
**Solution**: 
1. Check USB/power connections
2. Install/update LabJack drivers
3. Run hardware scan: `pnputil /scan-devices`

### Issue: Communication Timeouts
**Solution**:
1. Check Windows Firewall settings
2. Verify network configuration (for Ethernet devices)
3. Test with different USB ports/cables

### Issue: API Connection Failed
**Solution**:
1. Ensure backend service is running
2. Check API endpoints are accessible
3. Validate environment variables

## System Requirements

### Windows Compatibility
- **Supported**: Windows 10 (1903+), Windows 11
- **Architecture**: x64 recommended, x86 supported
- **Prerequisites**: .NET Framework 4.7.2+, Visual C++ Redistributable

### LabJack Device Support
- **T4**: Full support (USB/Ethernet)
- **T7**: Full support (USB/Ethernet/WiFi)  
- **T8**: Full support (USB/Ethernet)
- **U3/U6**: Limited support (USB only)

### Software Dependencies
- LabJack LJM Library (1.21.0+)
- Python 3.6+ (for hardware validation)
- PowerShell 5.0+ (for diagnostics)
- Node.js 16+ (for integration tests)

## Script Usage Examples

### PowerShell Diagnostics
```powershell
# Basic diagnostic
.\labjack-diagnostics.ps1

# Full diagnostic with auto-fix and export
.\labjack-diagnostics.ps1 -FixIssues -ExportResults -Detailed

# Check specific issues
.\labjack-diagnostics.ps1 -ExportResults -OutputPath "my-results.json"
```

### Python Hardware Validator
```bash
# Test all devices
python labjack-hardware-validator.py --verbose

# Test specific Ethernet device
python labjack-hardware-validator.py --device-type T7 --connection-type ETHERNET --ip-address 192.168.1.207

# Export detailed results
python labjack-hardware-validator.py --export-results --output-file validation-results.json --run-performance
```

### Quick Fix Options
The batch script provides interactive options:
1. Restart LabJack USB Service
2. Scan for Hardware Changes
3. Reset USB Devices
4. Create Firewall Rules
5. Test Device Connection
6. Open Device Manager
7. Open Kipling
8. Check System Status
9. Run Full Diagnostic

## Integration with AI Model Validation Platform

The LabJack integration supports:

### Signal Validation
- Real-time voltage monitoring
- Configurable detection thresholds
- Multi-channel data acquisition
- Streaming data to WebSocket clients

### Test Execution
- Automated test workflows
- Hardware-in-the-loop validation
- Performance benchmarking
- Result correlation with video processing

### API Endpoints
- `/api/signal-validation/labjack/status` - Device status
- `/api/signal-validation/labjack/initialize` - Device initialization
- `/api/signal-validation/monitoring/start` - Start monitoring
- `/api/signal-validation/monitoring/stop` - Stop monitoring

## Troubleshooting Workflow

1. **Quick Check**: Run `labjack-quick-fix.bat` for immediate diagnosis
2. **Detailed Analysis**: Use PowerShell diagnostic script for comprehensive testing
3. **Hardware Validation**: Run Python validator for device communication testing
4. **Integration Testing**: Execute Jest test suite for API connectivity
5. **System Review**: Check Windows logs and device manager for system-level issues

## Support Resources

### LabJack Resources
- [LabJack Support Site](https://labjack.com/support)
- [LJM Library Documentation](https://labjack.com/support/software/api/ljm)
- [Device Configuration Guide](https://labjack.com/support/datasheets)

### Project Resources  
- **Issues**: Report integration issues via project issue tracker
- **Documentation**: Refer to main project documentation
- **API Reference**: Check backend API documentation

### Windows Resources
- [Device Manager Troubleshooting](https://docs.microsoft.com/en-us/windows-hardware/drivers/install/troubleshooting-device-and-driver-installations)
- [USB Device Issues](https://docs.microsoft.com/en-us/windows-hardware/drivers/usbcon/)
- [Windows Firewall Configuration](https://docs.microsoft.com/en-us/windows/security/threat-protection/windows-firewall/)

## Best Practices

### For Development
1. Always test with mock mode first
2. Handle device disconnection gracefully
3. Implement proper timeout handling
4. Log all hardware interactions
5. Validate configuration parameters

### For Deployment
1. Install LabJack software before application
2. Configure Windows Firewall rules
3. Set up appropriate user permissions
4. Test all connection types (USB/Ethernet)
5. Validate system performance under load

### For Maintenance
1. Run diagnostics regularly
2. Keep drivers updated
3. Monitor system logs for errors
4. Test backup connection methods
5. Document configuration changes

## Contributing

When adding new LabJack features or fixing issues:

1. **Update Tests**: Add corresponding test cases to the validation suite
2. **Update Documentation**: Keep diagnostic guides current with changes
3. **Test Multiple Platforms**: Verify compatibility across Windows versions
4. **Performance Impact**: Measure and document any performance changes
5. **Error Handling**: Ensure robust error handling and user feedback

## License and Support

This integration guide and associated tools are provided as part of the AI Model Validation Platform project. For hardware-specific support, consult LabJack's official documentation and support channels.