/**
 * Detection Settings Management
 * Handles comprehensive Frigate object detection configuration
 */

class DetectionSettings {
    constructor() {
        this.currentCamera = null;
        this.currentSettings = {};
        this.objectFilters = {};
        this.zones = [];
        this.isDrawingZone = false;
        this.currentZonePoints = [];
        this.previewInterval = null;
        
        // Default presets
        this.presets = {
            'high-security': {
                detect: { enabled: true, fps: 15, width: 1280, height: 720 },
                motion: { threshold: 30, contour_area: 1000 },
                objects: {
                    track: ['person', 'car', 'dog', 'cat'],
                    filters: {
                        person: { min_area: 2000, max_area: 200000, threshold: 0.8 }
                    }
                }
            },
            'balanced': {
                detect: { enabled: true, fps: 10, width: 640, height: 480 },
                motion: { threshold: 50, contour_area: 2000 },
                objects: {
                    track: ['person'],
                    filters: {
                        person: { min_area: 3000, max_area: 100000, threshold: 0.7 }
                    }
                }
            },
            'performance': {
                detect: { enabled: true, fps: 5, width: 320, height: 240 },
                motion: { threshold: 70, contour_area: 3000 },
                objects: {
                    track: ['person'],
                    filters: {
                        person: { min_area: 5000, max_area: 50000, threshold: 0.6 }
                    }
                }
            },
            'erik-tracking': {
                detect: { enabled: true, fps: 10, width: 640, height: 480 },
                motion: { threshold: 40, contour_area: 1500 },
                objects: {
                    track: ['person'],
                    filters: {
                        person: { min_area: 2000, max_area: 100000, threshold: 0.75 }
                    }
                },
                erik_detection: {
                    enabled: true,
                    confidence_threshold: 0.8,
                    tracking_modes: ['face', 'body']
                }
            }
        };
    }

    // Open detection settings for a specific camera
    openDetectionSettings(cameraName) {
        this.currentCamera = cameraName;
        document.getElementById('detection-camera-name').textContent = cameraName;
        
        // Load current settings
        this.loadCameraSettings(cameraName);
        
        // Show modal
        document.getElementById('detection-settings-modal').style.display = 'block';
        
        // Set active tab to basic
        this.switchDetectionTab('basic');
    }

    // Load camera settings from API
    async loadCameraSettings(cameraName) {
        try {
            const response = await fetch(`/api/frigate/camera-config/${cameraName}`);
            if (response.ok) {
                this.currentSettings = await response.json();
                this.populateSettingsForm();
            } else {
                console.warn('Using default settings for camera:', cameraName);
                this.currentSettings = this.getDefaultSettings();
                this.populateSettingsForm();
            }
        } catch (error) {
            console.error('Error loading camera settings:', error);
            this.currentSettings = this.getDefaultSettings();
            this.populateSettingsForm();
        }
    }

    // Get default settings structure
    getDefaultSettings() {
        return {
            detect: {
                enabled: true,
                fps: 10,
                width: 640,
                height: 480,
                stationary: {
                    interval: 30,
                    threshold: 50
                },
                max_disappeared: 15
            },
            objects: {
                track: ['person'],
                filters: {
                    person: {
                        min_area: 3000,
                        max_area: 100000,
                        min_ratio: 0.5,
                        max_ratio: 3.0,
                        threshold: 0.7,
                        min_score: 0.5
                    }
                }
            },
            motion: {
                threshold: 50,
                contour_area: 2000,
                delta_alpha: 0.2,
                frame_alpha: 0.2,
                frame_height: 100,
                improve_contrast: false,
                mqtt_off_delay: 30,
                mask: []
            },
            zones: {},
            record: {
                enabled: true,
                mode: 'motion',
                retain: { days: 7 },
                events: {
                    pre_capture: 10,
                    post_capture: 15,
                    retain: { default: 10 }
                }
            },
            snapshots: {
                enabled: true,
                bounding_box: true,
                crop: false,
                height: 270,
                quality: 85,
                retain: { default: 10 }
            },
            erik_detection: {
                enabled: false,
                reference_images: 5,
                confidence_threshold: 0.8,
                tracking_modes: ['face', 'body'],
                update_interval: 3
            }
        };
    }

    // Populate form with current settings
    populateSettingsForm() {
        const settings = this.currentSettings;
        
        // Basic Detection Settings
        document.getElementById('detect-enabled').checked = settings.detect?.enabled || false;
        document.getElementById('detect-fps').value = settings.detect?.fps || 10;
        document.getElementById('detect-width').value = settings.detect?.width || 640;
        document.getElementById('detect-height').value = settings.detect?.height || 480;
        document.getElementById('stationary-interval').value = settings.detect?.stationary?.interval || 30;
        document.getElementById('stationary-threshold').value = settings.detect?.stationary?.threshold || 50;
        document.getElementById('max-disappeared').value = settings.detect?.max_disappeared || 15;
        
        // Update slider values
        this.updateSliderValue(document.getElementById('detect-fps'));
        
        // Object Tracking
        const trackObjects = settings.objects?.track || ['person'];
        document.querySelectorAll('input[name="track-object"]').forEach(checkbox => {
            checkbox.checked = trackObjects.includes(checkbox.value);
        });
        
        // Load first object filters
        if (trackObjects.length > 0) {
            this.loadObjectFilters(trackObjects[0]);
        }
        
        // Motion Settings
        if (settings.motion) {
            document.getElementById('motion-threshold').value = settings.motion.threshold || 50;
            document.getElementById('motion-contour-area').value = settings.motion.contour_area || 2000;
            document.getElementById('motion-delta-alpha').value = settings.motion.delta_alpha || 0.2;
            document.getElementById('motion-frame-alpha').value = settings.motion.frame_alpha || 0.2;
            document.getElementById('motion-frame-height').value = settings.motion.frame_height || 100;
            document.getElementById('motion-improve-contrast').checked = settings.motion.improve_contrast || false;
            document.getElementById('motion-mqtt-delay').value = settings.motion.mqtt_off_delay || 30;
            
            // Update slider values
            this.updateSliderValue(document.getElementById('motion-threshold'));
            this.updateSliderValue(document.getElementById('motion-delta-alpha'));
            this.updateSliderValue(document.getElementById('motion-frame-alpha'));
        }
        
        // Recording Settings
        if (settings.record) {
            document.getElementById('record-enabled').checked = settings.record.enabled || false;
            document.getElementById('record-mode').value = settings.record.mode || 'motion';
            document.getElementById('record-retain-days').value = settings.record.retain?.days || 7;
            document.getElementById('record-pre-capture').value = settings.record.events?.pre_capture || 10;
            document.getElementById('record-post-capture').value = settings.record.events?.post_capture || 15;
        }
        
        // Snapshot Settings
        if (settings.snapshots) {
            document.getElementById('snapshot-enabled').checked = settings.snapshots.enabled || false;
            document.getElementById('snapshot-bounding-box').checked = settings.snapshots.bounding_box || false;
            document.getElementById('snapshot-crop').checked = settings.snapshots.crop || false;
            document.getElementById('snapshot-height').value = settings.snapshots.height || 270;
            document.getElementById('snapshot-quality').value = settings.snapshots.quality || 85;
            document.getElementById('snapshot-retain-days').value = settings.snapshots.retain?.default || 10;
            
            this.updateSliderValue(document.getElementById('snapshot-quality'));
        }
        
        // Erik Detection Settings
        if (settings.erik_detection) {
            document.getElementById('erik-detection-enabled').checked = settings.erik_detection.enabled || false;
            document.getElementById('erik-reference-images').value = settings.erik_detection.reference_images || 5;
            document.getElementById('erik-confidence').value = settings.erik_detection.confidence_threshold || 0.8;
            document.getElementById('erik-update-interval').value = settings.erik_detection.update_interval || 3;
            
            this.updateSliderValue(document.getElementById('erik-confidence'));
            
            // Erik tracking modes
            const trackingModes = settings.erik_detection.tracking_modes || ['face', 'body'];
            document.querySelectorAll('input[name="erik-mode"]').forEach(checkbox => {
                checkbox.checked = trackingModes.includes(checkbox.value);
            });
        }
        
        // Load zones
        this.loadZones(settings.zones || {});
    }

    // Switch between detection tabs
    switchDetectionTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.detection-tab').forEach(tab => tab.classList.remove('active'));
        document.querySelector(`.detection-tab[onclick="switchDetectionTab('${tabName}')"]`).classList.add('active');
        
        // Update panels
        document.querySelectorAll('.detection-panel').forEach(panel => panel.classList.remove('active'));
        document.getElementById(`${tabName}-detection-panel`).classList.add('active');
    }

    // Update slider value display
    updateSliderValue(slider) {
        const valueSpan = slider.nextElementSibling;
        if (valueSpan && valueSpan.classList.contains('slider-value')) {
            valueSpan.textContent = slider.value;
        }
    }

    // Load object filters for specific object type
    loadObjectFilters(objectType) {
        const settings = this.currentSettings;
        const filters = settings.objects?.filters?.[objectType] || {};
        
        document.getElementById('filter-min-area').value = filters.min_area || 3000;
        document.getElementById('filter-max-area').value = filters.max_area || 100000;
        document.getElementById('filter-min-ratio').value = filters.min_ratio || 0.5;
        document.getElementById('filter-max-ratio').value = filters.max_ratio || 3.0;
        document.getElementById('filter-threshold').value = filters.threshold || 0.7;
        document.getElementById('filter-min-score').value = filters.min_score || 0.5;
        
        // Update slider values
        this.updateSliderValue(document.getElementById('filter-threshold'));
        this.updateSliderValue(document.getElementById('filter-min-score'));
    }

    // Apply preset configuration
    applyPreset(presetName) {
        if (!this.presets[presetName]) {
            console.error('Unknown preset:', presetName);
            return;
        }
        
        const preset = this.presets[presetName];
        
        // Apply preset to current settings
        this.currentSettings = { ...this.currentSettings, ...preset };
        
        // Repopulate form
        this.populateSettingsForm();
        
        // Show feedback
        this.showNotification(`Applied ${presetName.replace('-', ' ').toUpperCase()} preset`, 'success');
    }

    // Load zones into the zones list
    loadZones(zones) {
        this.zones = Object.entries(zones).map(([name, config]) => ({
            name,
            ...config
        }));
        
        this.renderZonesList();
    }

    // Render zones list
    renderZonesList() {
        const container = document.getElementById('zones-list');
        
        if (this.zones.length === 0) {
            container.innerHTML = '<p style="color: #888; text-align: center;">No zones configured</p>';
            return;
        }
        
        container.innerHTML = this.zones.map(zone => `
            <div class="zone-item">
                <div>
                    <h5>${zone.name}</h5>
                    <div class="zone-objects">
                        ${(zone.objects || []).map(obj => `<span class="zone-object-tag">${obj}</span>`).join('')}
                    </div>
                </div>
                <div>
                    <button onclick="detectionSettings.editZone('${zone.name}')" class="action-btn" style="margin-right: 10px;">Edit</button>
                    <button onclick="detectionSettings.deleteZone('${zone.name}')" class="action-btn danger">Delete</button>
                </div>
            </div>
        `).join('');
    }

    // Add new zone
    addNewZone() {
        const name = prompt('Enter zone name:');
        if (!name || name.trim() === '') return;
        
        const zone = {
            name: name.trim(),
            coordinates: [],
            objects: ['person'],
            filters: {}
        };
        
        this.zones.push(zone);
        this.renderZonesList();
        this.editZone(name.trim());
    }

    // Edit zone
    editZone(zoneName) {
        // Implementation for zone editing would go here
        console.log('Editing zone:', zoneName);
        this.openZoneEditor();
    }

    // Delete zone
    deleteZone(zoneName) {
        if (!confirm(`Delete zone "${zoneName}"?`)) return;
        
        this.zones = this.zones.filter(zone => zone.name !== zoneName);
        this.renderZonesList();
    }

    // Open visual zone editor
    openZoneEditor() {
        const container = document.getElementById('zone-editor-container');
        const canvas = document.getElementById('zone-editor-canvas');
        
        container.style.display = 'block';
        
        // Initialize canvas with camera feed
        this.initializeZoneCanvas(canvas);
    }

    // Initialize zone editor canvas
    initializeZoneCanvas(canvas) {
        const ctx = canvas.getContext('2d');
        
        // Load camera feed as background
        const img = new Image();
        img.onload = () => {
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);
        };
        img.src = `/api/${this.currentCamera}/latest.jpg?timestamp=${Date.now()}`;
        
        // Add click handlers for zone drawing
        canvas.addEventListener('click', (e) => this.handleZoneCanvasClick(e, canvas));
    }

    // Handle zone canvas clicks
    handleZoneCanvasClick(event, canvas) {
        if (!this.isDrawingZone) return;
        
        const rect = canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        
        this.currentZonePoints.push([x, y]);
        
        // Redraw canvas with current points
        this.redrawZoneCanvas(canvas);
    }

    // Redraw zone canvas
    redrawZoneCanvas(canvas) {
        const ctx = canvas.getContext('2d');
        
        // Redraw background
        const img = new Image();
        img.onload = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0);
            
            // Draw existing zones
            this.drawExistingZones(ctx);
            
            // Draw current zone being drawn
            if (this.currentZonePoints.length > 0) {
                this.drawCurrentZone(ctx);
            }
        };
        img.src = `/api/${this.currentCamera}/latest.jpg?timestamp=${Date.now()}`;
    }

    // Draw existing zones on canvas
    drawExistingZones(ctx) {
        this.zones.forEach((zone, index) => {
            if (!zone.coordinates || zone.coordinates.length < 3) return;
            
            ctx.beginPath();
            ctx.moveTo(zone.coordinates[0][0], zone.coordinates[0][1]);
            for (let i = 1; i < zone.coordinates.length; i++) {
                ctx.lineTo(zone.coordinates[i][0], zone.coordinates[i][1]);
            }
            ctx.closePath();
            
            // Different colors for different zones
            const colors = ['rgba(255, 0, 0, 0.3)', 'rgba(0, 255, 0, 0.3)', 'rgba(0, 0, 255, 0.3)'];
            ctx.fillStyle = colors[index % colors.length];
            ctx.fill();
            
            ctx.strokeStyle = colors[index % colors.length].replace('0.3', '0.8');
            ctx.lineWidth = 2;
            ctx.stroke();
            
            // Draw zone name
            if (zone.coordinates.length > 0) {
                ctx.fillStyle = 'white';
                ctx.font = '14px Arial';
                ctx.fillText(zone.name, zone.coordinates[0][0], zone.coordinates[0][1] - 5);
            }
        });
    }

    // Draw current zone being drawn
    drawCurrentZone(ctx) {
        if (this.currentZonePoints.length < 2) {
            // Just draw points
            this.currentZonePoints.forEach(point => {
                ctx.beginPath();
                ctx.arc(point[0], point[1], 4, 0, 2 * Math.PI);
                ctx.fillStyle = 'yellow';
                ctx.fill();
            });
            return;
        }
        
        // Draw polygon
        ctx.beginPath();
        ctx.moveTo(this.currentZonePoints[0][0], this.currentZonePoints[0][1]);
        for (let i = 1; i < this.currentZonePoints.length; i++) {
            ctx.lineTo(this.currentZonePoints[i][0], this.currentZonePoints[i][1]);
        }
        
        ctx.strokeStyle = 'yellow';
        ctx.lineWidth = 3;
        ctx.stroke();
        
        ctx.fillStyle = 'rgba(255, 255, 0, 0.2)';
        ctx.fill();
    }

    // Start drawing new zone
    startDrawingZone() {
        this.isDrawingZone = true;
        this.currentZonePoints = [];
        document.getElementById('zone-name-input').value = '';
    }

    // Finish drawing zone
    finishZone() {
        if (this.currentZonePoints.length < 3) {
            alert('A zone must have at least 3 points');
            return;
        }
        
        const name = document.getElementById('zone-name-input').value.trim();
        if (!name) {
            alert('Please enter a zone name');
            return;
        }
        
        // Add zone to list
        const zone = {
            name: name,
            coordinates: this.currentZonePoints.slice(),
            objects: ['person'],
            filters: {}
        };
        
        this.zones.push(zone);
        this.renderZonesList();
        
        // Reset drawing state
        this.isDrawingZone = false;
        this.currentZonePoints = [];
        document.getElementById('zone-name-input').value = '';
        
        // Hide editor
        document.getElementById('zone-editor-container').style.display = 'none';
    }

    // Cancel zone drawing
    cancelZone() {
        this.isDrawingZone = false;
        this.currentZonePoints = [];
        document.getElementById('zone-editor-container').style.display = 'none';
    }

    // Clear all zones
    clearAllZones() {
        if (!confirm('Delete all zones?')) return;
        
        this.zones = [];
        this.renderZonesList();
    }

    // Test detection settings
    async testDetectionSettings() {
        const testData = this.collectSettingsData();
        
        try {
            document.getElementById('detection-preview-overlay').style.display = 'flex';
            
            // Start test preview
            await this.startDetectionPreview(testData);
            
        } catch (error) {
            console.error('Error testing settings:', error);
            this.showNotification('Error testing settings: ' + error.message, 'error');
        }
    }

    // Start detection preview
    async startDetectionPreview(settings) {
        const canvas = document.getElementById('detection-preview-canvas');
        const ctx = canvas.getContext('2d');
        
        // Initialize preview with current camera feed
        const updatePreview = async () => {
            try {
                const img = new Image();
                img.onload = () => {
                    canvas.width = img.width;
                    canvas.height = img.height;
                    ctx.drawImage(img, 0, 0);
                    
                    // Simulate detection overlays based on settings
                    this.drawDetectionOverlays(ctx, settings);
                };
                img.src = `/api/${this.currentCamera}/latest.jpg?timestamp=${Date.now()}`;
                
                // Update stats (simulated)
                this.updatePreviewStats();
                
            } catch (error) {
                console.error('Preview update error:', error);
            }
        };
        
        // Update every 500ms
        this.previewInterval = setInterval(updatePreview, 500);
        updatePreview();
    }

    // Draw detection overlays on preview canvas
    drawDetectionOverlays(ctx, settings) {
        // This is a simplified simulation - in reality this would show actual detections
        
        // Draw motion areas (simulated)
        if (settings.motion?.enabled !== false) {
            ctx.fillStyle = 'rgba(255, 255, 0, 0.2)';
            ctx.fillRect(50, 50, 100, 150); // Simulated motion area
        }
        
        // Draw detection boxes (simulated)
        if (settings.detect?.enabled) {
            ctx.strokeStyle = '#00ff00';
            ctx.lineWidth = 3;
            ctx.strokeRect(60, 60, 80, 130);
            
            // Detection label
            ctx.fillStyle = '#00ff00';
            ctx.font = '14px Arial';
            ctx.fillText('Person (0.85)', 65, 55);
        }
        
        // Draw zones
        if (this.zones.length > 0) {
            this.zones.forEach((zone, index) => {
                if (!zone.coordinates || zone.coordinates.length < 3) return;
                
                ctx.beginPath();
                ctx.moveTo(zone.coordinates[0][0], zone.coordinates[0][1]);
                for (let i = 1; i < zone.coordinates.length; i++) {
                    ctx.lineTo(zone.coordinates[i][0], zone.coordinates[i][1]);
                }
                ctx.closePath();
                
                const colors = ['rgba(255, 0, 0, 0.2)', 'rgba(0, 255, 0, 0.2)', 'rgba(0, 0, 255, 0.2)'];
                ctx.fillStyle = colors[index % colors.length];
                ctx.fill();
                
                ctx.strokeStyle = colors[index % colors.length].replace('0.2', '0.8');
                ctx.lineWidth = 2;
                ctx.stroke();
            });
        }
    }

    // Update preview stats
    updatePreviewStats() {
        // Simulate real-time stats
        document.getElementById('preview-fps').textContent = Math.floor(Math.random() * 5) + 8;
        document.getElementById('preview-objects').textContent = Math.floor(Math.random() * 3);
        document.getElementById('preview-motion').textContent = Math.random() > 0.7 ? 'Yes' : 'No';
    }

    // Close preview
    closePreview() {
        document.getElementById('detection-preview-overlay').style.display = 'none';
        
        if (this.previewInterval) {
            clearInterval(this.previewInterval);
            this.previewInterval = null;
        }
    }

    // Reset settings to default
    resetDetectionSettings() {
        if (!confirm('Reset all settings to default values?')) return;
        
        this.currentSettings = this.getDefaultSettings();
        this.populateSettingsForm();
        this.showNotification('Settings reset to defaults', 'info');
    }

    // Collect all settings data from form
    collectSettingsData() {
        return {
            detect: {
                enabled: document.getElementById('detect-enabled').checked,
                fps: parseInt(document.getElementById('detect-fps').value),
                width: parseInt(document.getElementById('detect-width').value),
                height: parseInt(document.getElementById('detect-height').value),
                stationary: {
                    interval: parseInt(document.getElementById('stationary-interval').value),
                    threshold: parseInt(document.getElementById('stationary-threshold').value)
                },
                max_disappeared: parseInt(document.getElementById('max-disappeared').value)
            },
            objects: {
                track: Array.from(document.querySelectorAll('input[name="track-object"]:checked'))
                    .map(cb => cb.value),
                filters: this.collectObjectFilters()
            },
            motion: {
                threshold: parseInt(document.getElementById('motion-threshold').value),
                contour_area: parseInt(document.getElementById('motion-contour-area').value),
                delta_alpha: parseFloat(document.getElementById('motion-delta-alpha').value),
                frame_alpha: parseFloat(document.getElementById('motion-frame-alpha').value),
                frame_height: parseInt(document.getElementById('motion-frame-height').value),
                improve_contrast: document.getElementById('motion-improve-contrast').checked,
                mqtt_off_delay: parseInt(document.getElementById('motion-mqtt-delay').value)
            },
            zones: this.collectZonesData(),
            record: {
                enabled: document.getElementById('record-enabled').checked,
                mode: document.getElementById('record-mode').value,
                retain: {
                    days: parseInt(document.getElementById('record-retain-days').value)
                },
                events: {
                    pre_capture: parseInt(document.getElementById('record-pre-capture').value),
                    post_capture: parseInt(document.getElementById('record-post-capture').value),
                    retain: {
                        default: parseInt(document.getElementById('record-retain-days').value)
                    }
                }
            },
            snapshots: {
                enabled: document.getElementById('snapshot-enabled').checked,
                bounding_box: document.getElementById('snapshot-bounding-box').checked,
                crop: document.getElementById('snapshot-crop').checked,
                height: parseInt(document.getElementById('snapshot-height').value),
                quality: parseInt(document.getElementById('snapshot-quality').value),
                retain: {
                    default: parseInt(document.getElementById('snapshot-retain-days').value)
                }
            },
            erik_detection: {
                enabled: document.getElementById('erik-detection-enabled').checked,
                reference_images: parseInt(document.getElementById('erik-reference-images').value),
                confidence_threshold: parseFloat(document.getElementById('erik-confidence').value),
                tracking_modes: Array.from(document.querySelectorAll('input[name="erik-mode"]:checked'))
                    .map(cb => cb.value),
                update_interval: parseInt(document.getElementById('erik-update-interval').value)
            }
        };
    }

    // Collect object filters for all tracked objects
    collectObjectFilters() {
        const filters = {};
        const trackedObjects = Array.from(document.querySelectorAll('input[name="track-object"]:checked'))
            .map(cb => cb.value);
        
        // For now, apply the same filters to all objects
        // In a more sophisticated UI, each object would have its own filter settings
        const currentFilters = {
            min_area: parseInt(document.getElementById('filter-min-area').value),
            max_area: parseInt(document.getElementById('filter-max-area').value),
            min_ratio: parseFloat(document.getElementById('filter-min-ratio').value),
            max_ratio: parseFloat(document.getElementById('filter-max-ratio').value),
            threshold: parseFloat(document.getElementById('filter-threshold').value),
            min_score: parseFloat(document.getElementById('filter-min-score').value)
        };
        
        trackedObjects.forEach(obj => {
            filters[obj] = { ...currentFilters };
        });
        
        return filters;
    }

    // Collect zones data
    collectZonesData() {
        const zonesData = {};
        this.zones.forEach(zone => {
            zonesData[zone.name] = {
                coordinates: zone.coordinates,
                objects: zone.objects || ['person'],
                filters: zone.filters || {}
            };
        });
        return zonesData;
    }

    // Save settings to backend
    async saveDetectionSettings() {
        try {
            const settingsData = this.collectSettingsData();
            
            const response = await fetch(`/api/frigate/camera-config/${this.currentCamera}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(settingsData)
            });
            
            if (response.ok) {
                this.showNotification('Detection settings saved successfully', 'success');
                this.closeDetectionSettings();
                
                // Refresh camera display
                if (window.refreshCameraThumbnails) {
                    window.refreshCameraThumbnails();
                }
            } else {
                const error = await response.text();
                throw new Error(error);
            }
            
        } catch (error) {
            console.error('Error saving settings:', error);
            this.showNotification('Error saving settings: ' + error.message, 'error');
        }
    }

    // Close detection settings modal
    closeDetectionSettings() {
        document.getElementById('detection-settings-modal').style.display = 'none';
        this.currentCamera = null;
        this.currentSettings = {};
        
        // Close any open previews
        this.closePreview();
    }

    // Show notification
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        // Add to page
        document.body.appendChild(notification);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    }

    // Open motion mask editor
    openMotionMaskEditor() {
        // Implementation for motion mask editor
        console.log('Opening motion mask editor for', this.currentCamera);
        // This would open a similar canvas-based editor for drawing motion masks
    }
}

// Global instance
const detectionSettings = new DetectionSettings();

// Global functions for HTML onclick handlers
function openDetectionSettings(cameraName) {
    detectionSettings.openDetectionSettings(cameraName);
}

function closeDetectionSettings() {
    detectionSettings.closeDetectionSettings();
}

function switchDetectionTab(tabName) {
    detectionSettings.switchDetectionTab(tabName);
}

function updateSliderValue(slider) {
    detectionSettings.updateSliderValue(slider);
}

function loadObjectFilters(objectType) {
    detectionSettings.loadObjectFilters(objectType);
}

function applyPreset(presetName) {
    detectionSettings.applyPreset(presetName);
}

function addNewZone() {
    detectionSettings.addNewZone();
}

function openZoneEditor() {
    detectionSettings.openZoneEditor();
}

function clearAllZones() {
    detectionSettings.clearAllZones();
}

function startDrawingZone() {
    detectionSettings.startDrawingZone();
}

function finishZone() {
    detectionSettings.finishZone();
}

function cancelZone() {
    detectionSettings.cancelZone();
}

function testDetectionSettings() {
    detectionSettings.testDetectionSettings();
}

function closePreview() {
    detectionSettings.closePreview();
}

function resetDetectionSettings() {
    detectionSettings.resetDetectionSettings();
}

function saveDetectionSettings() {
    detectionSettings.saveDetectionSettings();
}

function openMotionMaskEditor() {
    detectionSettings.openMotionMaskEditor();
}