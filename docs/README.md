# Erik NVR System Documentation

This directory contains comprehensive documentation for the Erik NVR (Network Video Recorder) system, a computer vision project for tracking and monitoring using 3D reconstruction, COLMAP, and real-time detection.

## 📁 Documentation Structure

### 📖 Core Documentation (`/docs/`)
- **[erik_image_manager.md](erik_image_manager.md)** - Complete Erik Image Manager application documentation and API reference
- **[reconstruction_architecture.md](reconstruction_architecture.md)** - 3D reconstruction system architecture and technical details
- **[camera_pose_approach.md](camera_pose_approach.md)** - Camera pose estimation methodology and algorithms
- **[erik_live_projection.md](erik_live_projection.md)** - Live projection and real-time tracking implementation
- **[project_info.md](project_info.md)** - Overall project information and system overview

### 🛠️ Setup & Configuration Guides (`/guides/`)
- **[erik_tracker_setup.md](../guides/erik_tracker_setup.md)** - Erik tracking system installation and configuration
- **[YARD_IMAGE_SETUP.md](../guides/YARD_IMAGE_SETUP.md)** - Yard mapping and image setup procedures
- **[COLMAP_PHOTO_GUIDE.md](../guides/COLMAP_PHOTO_GUIDE.md)** - COLMAP photogrammetry workflow guide
- **[CALIBRATION_GUIDE.md](../guides/CALIBRATION_GUIDE.md)** - Camera calibration procedures
- **[CUSTOM_FUSION_GUIDE.md](../guides/CUSTOM_FUSION_GUIDE.md)** - Custom fusion system setup
- **[ERIK_COLOR_NOTIFICATION_SETUP.md](../guides/ERIK_COLOR_NOTIFICATION_SETUP.md)** - Color detection notification setup
- **[RTSP_STREAMING_SETUP.md](../guides/RTSP_STREAMING_SETUP.md)** - RTSP streaming configuration

### 🏠 Home Assistant Integration (`/homeassistant/`)
- **[erik_setup_guide.md](../homeassistant/erik_setup_guide.md)** - Home Assistant integration setup
- **[iphone_push_guide.md](../homeassistant/iphone_push_guide.md)** - iPhone push notification configuration
- **[sms_setup_guide.md](../homeassistant/sms_setup_guide.md)** - SMS notification setup
- **[pushover_setup.md](../homeassistant/pushover_setup.md)** - Pushover notification integration

### 📋 Project Requirements (`/requirements/`)
- **[functional_requirements.md](../requirements/functional_requirements.md)** - System functional requirements specification

### 📝 Project Planning (`/plans/`)
- **[refactoring.md](../plans/refactoring.md)** - System refactoring plans and roadmap
- **[index_refactoring.md](../plans/index_refactoring.md)** - Index refactoring specifications
- **[PHASE1_COMPLETE.md](../plans/PHASE1_COMPLETE.md)** - Phase 1 completion status
- **[PHASE2_COMPLETE.md](../plans/PHASE2_COMPLETE.md)** - Phase 2 completion status
- **[PHASE3_COMPLETE.md](../plans/PHASE3_COMPLETE.md)** - Phase 3 completion status
- **[PHASE4_COMPLETE.md](../plans/PHASE4_COMPLETE.md)** - Phase 4 completion status

### 📊 Logs & Status (`/logs/`)
- **[erik_tracker_log.md](../logs/erik_tracker_log.md)** - Erik tracker operational logs
- **[colmap_progress_tracking.md](../logs/colmap_progress_tracking.md)** - COLMAP processing progress logs
- **[REFACTORING_COMPLETE.md](../logs/REFACTORING_COMPLETE.md)** - Refactoring completion log

## 🚀 Quick Start

1. **Main Documentation**: Start with [readme.md](../readme.md) in the project root
2. **System Setup**: Follow [erik_tracker_setup.md](../guides/erik_tracker_setup.md)
3. **Image Manager**: Reference [erik_image_manager.md](erik_image_manager.md) for the web interface
4. **3D Reconstruction**: See [reconstruction_architecture.md](reconstruction_architecture.md) for technical details

## 🏗️ System Architecture

The Erik NVR system consists of several integrated components:

- **Image Manager**: Flask web application for image upload, 3D reconstruction, and yard mapping
- **Hybrid Tracker**: Real-time Erik detection and tracking using computer vision
- **COLMAP Integration**: 3D reconstruction pipeline for generating point clouds and meshes
- **Home Assistant Integration**: Smart home automation and notification system
- **Camera System**: Multi-camera setup with RTSP streaming and object detection

## 🛠️ Technology Stack

- **Backend**: Python/Flask, COLMAP, OpenCV, CUDA
- **Frontend**: HTML/JavaScript with real-time updates
- **Infrastructure**: Docker, MQTT, PostgreSQL
- **Computer Vision**: SIFT features, photogrammetry, point cloud processing
- **Integration**: Frigate NVR, Home Assistant, various notification services

## 📞 Support

For issues or questions:
1. Check the relevant documentation file for your component
2. Review the logs in `/logs/` for debugging information
3. Consult the setup guides in `/guides/` for configuration help

---

*Last updated: 2025-09-03*
*Documentation organized and consolidated for improved maintainability*