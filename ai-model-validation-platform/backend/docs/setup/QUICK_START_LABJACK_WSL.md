# LabJack WSL Quick Start Guide

## TL;DR - Get LabJack Working Fast

### Prerequisites Check
- [ ] Windows 10/11 with WSL2 enabled
- [ ] LabJack device physically connected via USB
- [ ] Administrator privileges on Windows

### Method 1: Automated Setup (Recommended)

**Windows PowerShell (Run as Administrator):**
```powershell
# Navigate to setup scripts directory
cd ai-model-validation-platform\backend\scripts\windows-setup

# Run automated setup
.\setup-labjack-usbip.ps1
```

**WSL Terminal:**
```bash
# Test connection
python scripts/test_labjack_connection.py

# Start backend
source .venv/bin/activate
python main.py
```

### Method 2: Manual Setup

**Windows PowerShell (as Administrator):**
```powershell
# Install USB/IP bridge
winget install usbipd-win

# Find LabJack device
usbipd list

# Bind device (replace X-Y with your BUSID)
usbipd bind --busid X-Y

# Attach to WSL
usbipd attach --wsl --busid X-Y
```

**WSL Terminal:**
```bash
# Install USB tools
sudo apt update
sudo apt install linux-tools-virtual hwdata usbutils

# Verify device
lsusb | grep -i labjack

# Install Python library
pip install labjack-ljm

# Test connection
python -c "import labjack.ljm; print('LabJack ready!')"
```

## Connection Methods Quick Reference

| Method | Best For | Setup Time | Performance |
|--------|----------|------------|-------------|
| **USB/IP Bridge** | Most users | 5 minutes | Excellent |
| **Network LabJack** | T7-Pro/T8 only | 10 minutes | Good |
| **Shared Folder** | Fallback option | 15 minutes | Fair |

## Troubleshooting Quick Fixes

### Issue: "usbipd: command not found"
```powershell
winget install usbipd-win
# Restart PowerShell
```

### Issue: "No LabJack devices found"
```powershell
# Check Windows Device Manager
devmgmt.msc
# Look for LabJack device, install drivers if needed
```

### Issue: Device attached but not accessible
```bash
# In WSL
sudo chmod 666 /dev/bus/usb/*/*
lsusb | grep -i labjack
```

### Issue: ImportError: No module named 'labjack'
```bash
# In WSL virtual environment
source .venv/bin/activate
pip install labjack-ljm
```

## Verification Commands

**Check USB/IP Bridge Status:**
```powershell
usbipd list | findstr LabJack
```

**Test in WSL:**
```bash
lsusb | grep -i labjack
python -c "import labjack.ljm as ljm; print('Available:', ljm.listAll(ljm.constants.dtANY, ljm.constants.ctANY))"
```

**Test Backend API:**
```bash
curl http://localhost:8000/api/labjack/status
```

## File Locations

| Component | Location |
|-----------|----------|
| **Setup Guide** | `backend/docs/setup/LABJACK_WSL_SETUP_GUIDE.md` |
| **PowerShell Scripts** | `backend/scripts/windows-setup/` |
| **Connection Test** | `backend/scripts/test_labjack_connection.py` |
| **Bridge Service** | `backend/scripts/windows-setup/labjack_bridge_service.py` |
| **Configuration** | `backend/config/labjack_config.py` |

## Success Indicators

You know it's working when:
- [ ] `usbipd list` shows LabJack as "Attached"
- [ ] `lsusb` in WSL shows LabJack device
- [ ] Python import works: `import labjack.ljm`
- [ ] Backend API returns `"connected": true`
- [ ] HIL tests can detect TTL signals

## Need Help?

1. **Run diagnostic test:** `python scripts/test_labjack_connection.py`
2. **Check logs:** Backend logs show LabJack connection status
3. **Review full guide:** `docs/setup/LABJACK_WSL_SETUP_GUIDE.md`
4. **Common issues:** Most problems are USB/IP binding or driver related

## Next Steps After Setup

1. **Configure TTL channel:** Update `labjack_config.py` with your channel
2. **Test HIL workflow:** Upload test video and annotations
3. **Run validation:** Execute end-to-end HIL test
4. **Monitor performance:** Check timing precision in results

---

**Estimated Total Setup Time:** 5-15 minutes depending on method chosen.