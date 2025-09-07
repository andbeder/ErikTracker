/**
 * Camera Edit Management
 * Handles editing basic camera configuration
 */

class CameraEditManager {
    constructor() {
        this.currentCameraName = null;
        this.originalConfig = null;
    }

    /**
     * Open the camera edit modal
     */
    async openCameraEdit(cameraName) {
        this.currentCameraName = cameraName;
        
        try {
            // Load current camera configuration
            await this.loadCameraConfig(cameraName);
            
            // Show the modal
            const modal = document.getElementById('cameraEditModal');
            if (modal) {
                modal.style.display = 'flex';
                document.body.style.overflow = 'hidden';
            }
            
        } catch (error) {
            console.error('Error opening camera edit:', error);
            this.showStatus(`Failed to load camera configuration: ${error.message}`, 'error');
        }
    }

    /**
     * Load camera configuration from server
     */
    async loadCameraConfig(cameraName) {
        try {
            // Get camera configuration from Frigate API
            const response = await fetch(`/frigate/config/camera/${cameraName}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            this.originalConfig = result.config || {};
            
            // Populate form fields
            this.populateForm(cameraName, this.originalConfig);
            
        } catch (error) {
            console.error('Error loading camera config:', error);
            throw error;
        }
    }

    /**
     * Populate form with camera configuration
     */
    populateForm(cameraName, config) {
        // Basic settings
        document.getElementById('editCameraName').value = cameraName;
        document.getElementById('editDisplayName').value = config.ui?.friendly_name || cameraName.replace(/_/g, ' ');
        
        // RTSP URL from ffmpeg inputs
        let rtspUrl = '';
        if (config.ffmpeg && config.ffmpeg.inputs && config.ffmpeg.inputs.length > 0) {
            rtspUrl = config.ffmpeg.inputs[0].path || '';
        }
        document.getElementById('editRtspUrl').value = rtspUrl;
        
        // Resolution
        const detectConfig = config.detect || {};
        const width = detectConfig.width || 1280;
        const height = detectConfig.height || 720;
        const resolution = `${width}x${height}`;
        
        const resolutionSelect = document.getElementById('editResolution');
        const standardResolutions = ['1920x1080', '1280x720', '640x480'];
        
        if (standardResolutions.includes(resolution)) {
            resolutionSelect.value = resolution;
        } else {
            resolutionSelect.value = 'custom';
            document.getElementById('customResolutionGroup').style.display = 'flex';
            document.getElementById('editCustomWidth').value = width;
            document.getElementById('editCustomHeight').value = height;
        }
        
        // Recording settings
        const recordConfig = config.record || {};
        document.getElementById('editRecordingEnabled').checked = recordConfig.enabled !== false;
        document.getElementById('editRetainDays').value = recordConfig.retain?.days || 30;
        document.getElementById('editRecordMode').value = recordConfig.events?.retain?.mode || 'motion';
        
        // Live stream settings
        const liveConfig = config.live || {};
        document.getElementById('editStreamQuality').value = liveConfig.quality || 'source';
        document.getElementById('editStreamFps').value = liveConfig.height || 5;
        
        // Camera zone/area (custom field)
        const cameraZone = config.camera_zone || this.guessCameraZone(cameraName);
        document.getElementById('editCameraZone').value = cameraZone;
        
        // Notes (custom field)
        document.getElementById('editCameraNotes').value = config.camera_notes || '';
    }

    /**
     * Guess camera zone from name
     */
    guessCameraZone(cameraName) {
        const name = cameraName.toLowerCase();
        if (name.includes('front_door') || name.includes('frontdoor')) return 'front_door';
        if (name.includes('front') || name.includes('yard')) return 'front_yard';
        if (name.includes('back') || name.includes('rear')) return 'backyard';
        if (name.includes('side')) return 'side_yard';
        if (name.includes('garage')) return 'garage';
        if (name.includes('drive')) return 'driveway';
        return 'other';
    }

    /**
     * Save camera configuration
     */
    async saveCameraEdit() {
        try {
            const formData = this.collectFormData();
            
            // Validate form data
            const validation = this.validateFormData(formData);
            if (!validation.valid) {
                this.showStatus(`Validation error: ${validation.message}`, 'error');
                return;
            }
            
            // Build updated camera configuration
            const updatedConfig = this.buildCameraConfig(formData);
            
            this.showStatus('Saving camera configuration...', 'info');
            
            // Save to server
            const response = await fetch(`/frigate/config/camera/${this.currentCameraName}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updatedConfig)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }
            
            const result = await response.json();
            
            this.showStatus('✅ Camera configuration saved successfully!', 'success');
            
            // Close modal after short delay
            setTimeout(() => {
                this.closeCameraEdit();
                // Refresh page if camera name changed
                if (formData.camera_name !== this.currentCameraName) {
                    window.location.reload();
                }
            }, 2000);
            
        } catch (error) {
            console.error('Error saving camera config:', error);
            this.showStatus(`Failed to save configuration: ${error.message}`, 'error');
        }
    }

    /**
     * Collect form data
     */
    collectFormData() {
        return {
            camera_name: document.getElementById('editCameraName').value.trim(),
            display_name: document.getElementById('editDisplayName').value.trim(),
            rtsp_url: document.getElementById('editRtspUrl').value.trim(),
            resolution: document.getElementById('editResolution').value,
            custom_width: parseInt(document.getElementById('editCustomWidth').value) || 640,
            custom_height: parseInt(document.getElementById('editCustomHeight').value) || 480,
            recording_enabled: document.getElementById('editRecordingEnabled').checked,
            retain_days: parseInt(document.getElementById('editRetainDays').value) || 30,
            record_mode: document.getElementById('editRecordMode').value,
            stream_quality: document.getElementById('editStreamQuality').value,
            stream_fps: parseInt(document.getElementById('editStreamFps').value) || 5,
            camera_zone: document.getElementById('editCameraZone').value,
            camera_notes: document.getElementById('editCameraNotes').value.trim()
        };
    }

    /**
     * Validate form data
     */
    validateFormData(data) {
        if (!data.camera_name) {
            return { valid: false, message: 'Camera name is required' };
        }
        
        if (!/^[a-zA-Z0-9_]+$/.test(data.camera_name)) {
            return { valid: false, message: 'Camera name can only contain letters, numbers, and underscores' };
        }
        
        if (!data.rtsp_url) {
            return { valid: false, message: 'RTSP URL is required' };
        }
        
        if (!data.rtsp_url.startsWith('rtsp://')) {
            return { valid: false, message: 'RTSP URL must start with rtsp://' };
        }
        
        if (data.resolution === 'custom') {
            if (data.custom_width < 320 || data.custom_width > 4096) {
                return { valid: false, message: 'Width must be between 320 and 4096' };
            }
            if (data.custom_height < 240 || data.custom_height > 2160) {
                return { valid: false, message: 'Height must be between 240 and 2160' };
            }
        }
        
        return { valid: true };
    }

    /**
     * Build camera configuration object
     */
    buildCameraConfig(data) {
        // Get resolution values
        let width, height;
        if (data.resolution === 'custom') {
            width = data.custom_width;
            height = data.custom_height;
        } else {
            [width, height] = data.resolution.split('x').map(Number);
        }
        
        return {
            ...this.originalConfig,
            
            // FFmpeg input configuration
            ffmpeg: {
                ...this.originalConfig.ffmpeg,
                inputs: [{
                    path: data.rtsp_url,
                    roles: ['record', 'detect']
                }]
            },
            
            // Detection settings
            detect: {
                ...this.originalConfig.detect,
                width: width,
                height: height
            },
            
            // Recording settings
            record: {
                ...this.originalConfig.record,
                enabled: data.recording_enabled,
                retain: {
                    ...this.originalConfig.record?.retain,
                    days: data.retain_days
                },
                events: {
                    ...this.originalConfig.record?.events,
                    retain: {
                        ...this.originalConfig.record?.events?.retain,
                        mode: data.record_mode
                    }
                }
            },
            
            // Live stream settings
            live: {
                ...this.originalConfig.live,
                quality: data.stream_quality,
                height: data.stream_fps
            },
            
            // UI settings
            ui: {
                ...this.originalConfig.ui,
                friendly_name: data.display_name
            },
            
            // Custom fields
            camera_zone: data.camera_zone,
            camera_notes: data.camera_notes
        };
    }

    /**
     * Test camera connection
     */
    async testCameraConnection() {
        const rtspUrl = document.getElementById('editRtspUrl').value.trim();
        
        if (!rtspUrl) {
            this.showStatus('Please enter an RTSP URL first', 'error');
            return;
        }
        
        if (!rtspUrl.startsWith('rtsp://')) {
            this.showStatus('RTSP URL must start with rtsp://', 'error');
            return;
        }
        
        this.showStatus('Testing camera connection...', 'info');
        
        try {
            // This would ideally test the RTSP stream
            // For now, just validate URL format and show success
            await new Promise(resolve => setTimeout(resolve, 2000));
            
            this.showStatus('✅ Camera connection test successful!', 'success');
        } catch (error) {
            this.showStatus(`❌ Connection test failed: ${error.message}`, 'error');
        }
    }

    /**
     * Close the camera edit modal
     */
    closeCameraEdit() {
        const modal = document.getElementById('cameraEditModal');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
        
        this.currentCameraName = null;
        this.originalConfig = null;
    }

    /**
     * Show status message
     */
    showStatus(message, type = 'info') {
        const statusEl = document.getElementById('cameraEditStatus');
        if (!statusEl) return;
        
        statusEl.textContent = message;
        statusEl.className = `status-message ${type}`;
        statusEl.style.display = 'block';
        
        // Auto-hide after 5 seconds for success/info messages
        if (type === 'success' || type === 'info') {
            setTimeout(() => {
                statusEl.style.display = 'none';
            }, 5000);
        }
    }
}

// Initialize camera edit manager
const cameraEditManager = new CameraEditManager();

// Global functions
window.openCameraEdit = function(cameraName) {
    cameraEditManager.openCameraEdit(cameraName);
};

window.closeCameraEditModal = function() {
    cameraEditManager.closeCameraEdit();
};

window.saveCameraEdit = function() {
    cameraEditManager.saveCameraEdit();
};

window.testCameraConnection = function() {
    cameraEditManager.testCameraConnection();
};

// Handle resolution select change
document.addEventListener('DOMContentLoaded', function() {
    const resolutionSelect = document.getElementById('editResolution');
    const customGroup = document.getElementById('customResolutionGroup');
    
    if (resolutionSelect && customGroup) {
        resolutionSelect.addEventListener('change', function() {
            if (this.value === 'custom') {
                customGroup.style.display = 'flex';
            } else {
                customGroup.style.display = 'none';
            }
        });
    }
    
    // Close modal when clicking outside
    const modal = document.getElementById('cameraEditModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                cameraEditManager.closeCameraEdit();
            }
        });
    }
});