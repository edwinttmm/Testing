# LabJack USB Passthrough Setup Guide

A comprehensive guide for configuring USB passthrough to enable LabJack device connectivity across different environments including WSL2, Docker containers, and virtual machines.

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [USB/IP (usbipd-win) Setup](#usbip-usbipd-win-setup)
4. [Alternative Methods](#alternative-methods)
5. [Troubleshooting](#troubleshooting)
6. [Performance Optimization](#performance-optimization)
7. [Security Considerations](#security-considerations)
8. [Validation & Testing](#validation--testing)
9. [Automation Scripts](#automation-scripts)

## Overview

This guide covers three primary methods for USB passthrough:

- **USB/IP (usbipd-win)**: Recommended method for WSL2 and remote access
- **Bridge Service**: Custom service for direct device access
- **Direct Windows Backend**: Native Windows application approach

### Supported Environments
- Windows 11/10 with WSL2
- Docker Desktop for Windows
- Virtual machines (VMware, VirtualBox)
- Remote development environments

### Supported LabJack Models
- LabJack U3-HV, U3-LV
- LabJack U6, U6-Pro
- LabJack UE9, UE9-Pro
- LabJack T4, T7, T7-Pro
- LabJack T8

## Prerequisites

### System Requirements
- Windows 10 version 21H1 (build 19043) or later
- WSL2 with Ubuntu 20.04+ (if using WSL)
- PowerShell 5.1 or later
- Administrator privileges

### Required Software
```bash
# Check Windows version
winver

# Check WSL version
wsl --version

# Check PowerShell version
$PSVersionTable.PSVersion
```

### Hardware Requirements
- USB 2.0 or higher port
- Minimum 2GB available RAM
- At least 1GB free disk space

## Next Steps

Follow the detailed guides in each section:

- [USB/IP Setup Guide](./01-usbip-setup.md) - Primary method (recommended)
- [Alternative Methods](./02-alternative-methods.md) - Bridge service and direct access
- [Troubleshooting Guide](./03-troubleshooting.md) - Common issues and solutions
- [Performance Optimization](./04-performance.md) - Speed and reliability improvements
- [Security Guide](./05-security.md) - Best practices and considerations
- [Validation Procedures](./06-validation.md) - Testing and verification

## Quick Start

For experienced users, here's a minimal setup:

```powershell
# Install usbipd-win
winget install usbipd

# List USB devices
usbipd list

# Attach LabJack device (replace BUSID with your device's bus ID)
usbipd bind --busid 1-4
usbipd attach --wsl --busid 1-4

# Verify in WSL
lsusb | grep -i labjack
```

## Support

- [LabJack Support](https://labjack.com/support)
- [WSL Documentation](https://docs.microsoft.com/en-us/windows/wsl/)
- [USB/IP Project](https://github.com/dorssel/usbipd-win)

---
*Last updated: $(date +"%B %Y")*