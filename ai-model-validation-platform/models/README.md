# VRU AI Model Validation Platform - Models Directory

## Overview
This directory contains the machine learning models used by the VRU AI Model Validation Platform for vehicle detection, pedestrian detection, and other computer vision tasks.

## Model Files

### YOLO Models
- `yolov8n.pt` - YOLOv8 Nano model (lightweight, fast inference)
- `yolov8s.pt` - YOLOv8 Small model (balanced performance)
- `yolov8m.pt` - YOLOv8 Medium model (higher accuracy)
- `yolov8l.pt` - YOLOv8 Large model (best accuracy)
- `yolo11n.pt` - YOLO11 Nano model (latest version)

### Custom Models
- `vru_custom_model.pt` - Custom trained model for VRU detection
- `traffic_light_model.pt` - Traffic light detection model

## Automatic Model Download

The platform includes automatic model downloading functionality:

1. **Development Mode**: Models are downloaded on first startup
2. **Production Mode**: Models should be pre-downloaded or mounted as volumes
3. **Docker Mode**: Models are automatically downloaded during container build

## Model Configuration

Models are configured in the following files:
- `backend/config.py` - Model paths and settings
- `config/production/ml_config.yaml` - Production ML configuration
- `backend/auto_install_ml.py` - Automatic model installation

## Storage Requirements

- **yolov8n.pt**: ~6MB
- **yolov8s.pt**: ~22MB  
- **yolov8m.pt**: ~52MB
- **yolov8l.pt**: ~87MB
- **Custom models**: Variable size

## Performance Considerations

### CPU-Only Mode
- Use nano or small models for best performance
- Recommended: `yolov8n.pt` for development

### GPU Mode
- Larger models (medium/large) benefit from GPU acceleration
- CUDA/ROCm support automatically detected

### Production Deployment
- Pre-download models to avoid startup delays
- Use volume mounts for persistent model storage
- Consider model quantization for edge deployment

## Model Updates

To update models:
1. Replace model files in this directory
2. Update configuration in `config.py`
3. Restart services or rebuild containers

## Security Notes

- Models are loaded with PyTorch safe loading
- Verify model integrity before deployment
- Use checksums to validate model files

## Troubleshooting

If models fail to load:
1. Check file permissions (`chmod 644 *.pt`)
2. Verify disk space availability
3. Check network connectivity for downloads
4. Review logs in `backend/logs/`

## License

Model licenses vary by source:
- YOLO models: GPL-3.0 (Ultralytics)
- Custom models: Project-specific license