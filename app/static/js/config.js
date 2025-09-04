/**
 * Configuration Management Module for Erik Image Manager
 * Handles centralized application configuration, camera settings, and dynamic values
 */

class AppConfig {
    constructor() {
        this.config = null;
        this.loaded = false;
        this.cache = new Map();
        this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
    }

    /**
     * Load configuration from server
     */
    async load() {
        if (this.loaded && this.config) {
            return this.config;
        }

        try {
            const response = await fetch('/api/config/client');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.config = await response.json();
            this.loaded = true;
            
            console.log('✅ Application configuration loaded:', this.config);
            return this.config;
        } catch (error) {
            console.error('Failed to load configuration:', error);
            // Return fallback configuration
            this.config = this.getFallbackConfig();
            this.loaded = true;
            return this.config;
        }
    }

    /**
     * Get nested configuration value by dot notation
     * @param {string} path - Configuration path (e.g., 'colmap.max_video_size')
     * @param {*} defaultValue - Default value if path not found
     */
    get(path, defaultValue = null) {
        if (!this.config) {
            console.warn('Configuration not loaded, using default value');
            return defaultValue;
        }

        const keys = path.split('.');
        let value = this.config;
        
        for (const key of keys) {
            if (value && typeof value === 'object' && key in value) {
                value = value[key];
            } else {
                return defaultValue;
            }
        }
        
        return value;
    }

    /**
     * Check if a feature is enabled
     * @param {string} feature - Feature name
     */
    isFeatureEnabled(feature) {
        return this.get(`features.${feature}`, false);
    }

    /**
     * Get file size limits
     */
    getFileLimits() {
        return {
            maxImageSize: this.get('images.max_file_size', 16 * 1024 * 1024),
            maxVideoSize: this.get('colmap.max_video_size', 500 * 1024 * 1024),
            maxMeshSize: this.get('mesh.max_file_size', 16 * 1024 * 1024)
        };
    }

    /**
     * Get supported file formats
     */
    getSupportedFormats() {
        return {
            images: this.get('images.supported_formats', ['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'webp']),
            videos: this.get('colmap.supported_video_formats', ['mp4', 'avi', 'mov', 'mkv']),
            meshes: this.get('mesh.supported_formats', ['ply', 'obj', 'stl'])
        };
    }

    /**
     * Get UI configuration values
     */
    getUIConfig() {
        return {
            appTitle: this.get('ui.app_title', 'Erik Image Manager'),
            appDescription: this.get('ui.app_description', 'Image and tracking management'),
            autoRefreshInterval: this.get('ui.auto_refresh_interval', 30000),
            erikTrackingInterval: this.get('ui.erik_tracking_interval', 2000),
            matchRefreshInterval: this.get('ui.match_refresh_interval', 30000)
        };
    }

    /**
     * Get network configuration
     */
    getNetworkConfig() {
        return {
            externalIP: this.get('network.external_ip', '192.168.1.1'),
            mqttHost: this.get('network.mqtt_host', 'localhost'),
            mqttPort: this.get('network.mqtt_port', 1883)
        };
    }

    /**
     * Get paths configuration
     */
    getPaths() {
        return {
            uploadFolder: this.get('images.upload_folder', './erik_images'),
            meshFolder: this.get('mesh.mesh_folder', './meshes'),
            yardMapPath: this.get('yard_map.map_path', './yard_map.png'),
            activeYardMapPath: this.get('yard_map.active_map_path', './active_yard_map.png'),
            colmapProjectsDir: this.get('colmap.projects_dir', './reconstruction')
        };
    }

    /**
     * Cached API call with timeout
     */
    async getCached(key, fetchFunction, timeout = this.cacheTimeout) {
        const cached = this.cache.get(key);
        const now = Date.now();
        
        if (cached && (now - cached.timestamp) < timeout) {
            return cached.data;
        }
        
        try {
            const data = await fetchFunction();
            this.cache.set(key, {
                data: data,
                timestamp: now
            });
            return data;
        } catch (error) {
            // Return cached data if available, even if expired
            if (cached) {
                console.warn(`Using expired cache for ${key}:`, error);
                return cached.data;
            }
            throw error;
        }
    }

    /**
     * Clear configuration cache
     */
    clearCache() {
        this.cache.clear();
        this.loaded = false;
        this.config = null;
    }

    /**
     * Reload configuration from server
     */
    async reload() {
        this.clearCache();
        return await this.load();
    }

    /**
     * Get fallback configuration when server is unavailable
     */
    getFallbackConfig() {
        return {
            colmap: {
                projects_dir: './reconstruction',
                supported_video_formats: ['mp4', 'avi', 'mov', 'mkv'],
                max_video_size: 500 * 1024 * 1024,
                max_file_size: 16 * 1024 * 1024
            },
            images: {
                upload_folder: './erik_images',
                supported_formats: ['png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp'],
                max_file_size: 16 * 1024 * 1024,
                thumbnail_size: [200, 200]
            },
            mesh: {
                mesh_folder: './meshes',
                supported_formats: ['ply', 'obj', 'stl'],
                max_file_size: 16 * 1024 * 1024
            },
            yard_map: {
                map_path: './yard_map.png',
                active_map_path: './active_yard_map.png',
                active_map_json: './active_yard_map.json'
            },
            network: {
                external_ip: '192.168.1.1',
                mqtt_host: 'localhost',
                mqtt_port: 1883
            },
            ui: {
                app_title: 'Erik Image Manager',
                app_description: 'Manage reference images and view live detections',
                auto_refresh_interval: 30000,
                erik_tracking_interval: 2000,
                match_refresh_interval: 30000
            },
            features: {
                live_mapping: true,
                colmap_reconstruction: true,
                frigate_integration: true,
                erik_tracking: true,
                camera_management: true,
                yard_mapping: true
            }
        };
    }
}

class ConfigManager {
    constructor(apiClient) {
        this.api = apiClient;
        this.currentSettings = {};
        this.cameraConfigs = {};
        this.externalIP = null;
        this.appConfig = new AppConfig();
    }

    /**
     * Initialize configuration management
     */
    async initialize() {
        try {
            // Load centralized configuration first
            await this.appConfig.load();
            
            // Load legacy settings for backwards compatibility
            await this.loadExternalIP();
            await this.loadGlobalSettings();
            
            // Make configuration globally available
            window.appConfig = this.appConfig;
            window.externalIP = this.externalIP;
            
            console.log('✅ Configuration manager initialized');
        } catch (error) {
            console.error('Failed to initialize configuration:', error);
        }
    }

    /**
     * Load external IP configuration
     */
    async loadExternalIP() {
        try {
            // Try to get from centralized config first
            this.externalIP = this.appConfig.get('network.external_ip');
            
            if (!this.externalIP) {
                // Fallback to legacy API
                const result = await this.api.getExternalIP();
                this.externalIP = result.external_ip;
            }
        } catch (error) {
            console.error('Error loading external IP:', error);
            this.externalIP = '192.168.68.54'; // Fallback IP
        }
    }

    /**
     * Load global settings
     */
    async loadGlobalSettings() {
        try {
            const result = await this.api.getGlobalSettings();
            if (result.success) {
                this.currentSettings = result.settings;
                this.applySettingsToUI();
            }
        } catch (error) {
            console.error('Error loading global settings:', error);
        }
    }

    /**
     * Apply settings to UI elements
     */
    applySettingsToUI() {
        const settings = this.currentSettings;
        
        Utils.safeElementOperation('trackErik', el => el.checked = settings.track_erik || false);
        Utils.safeElementOperation('trackOthers', el => el.checked = settings.track_others || false);
        Utils.safeElementOperation('trackAnimals', el => el.checked = settings.track_animals || false);
        Utils.safeElementOperation('pushoverEnabled', el => el.checked = settings.pushover_enabled || false);
        Utils.safeElementOperation('pushoverUserKey', el => el.value = settings.pushover_user_key || '');
        Utils.safeElementOperation('pushoverAppToken', el => el.value = settings.pushover_app_token || '');
        
        this.togglePushoverConfig();
    }

    /**
     * Save global settings
     */
    async saveGlobalSettings() {
        const settings = {
            track_erik: document.getElementById('trackErik')?.checked || false,
            track_others: document.getElementById('trackOthers')?.checked || false,
            track_animals: document.getElementById('trackAnimals')?.checked || false,
            pushover_enabled: document.getElementById('pushoverEnabled')?.checked || false,
            pushover_user_key: document.getElementById('pushoverUserKey')?.value || '',
            pushover_app_token: document.getElementById('pushoverAppToken')?.value || ''
        };
        
        try {
            const result = await this.api.saveGlobalSettings(settings);
            if (result.success) {
                this.currentSettings = settings;
                Utils.showToast('✅ Settings saved successfully!', 'success');
                
                if (result.services_restarted) {
                    Utils.showToast('🔄 Services restarted to apply changes', 'info');
                }
            } else {
                Utils.showToast(`❌ Failed to save settings: ${result.error}`, 'error');
            }
        } catch (error) {
            Utils.showToast(`❌ Error saving settings: ${error.message}`, 'error');
        }
    }

    /**
     * Toggle Pushover configuration visibility
     */
    togglePushoverConfig() {
        const enabled = document.getElementById('pushoverEnabled')?.checked || false;
        const config = document.getElementById('pushoverConfig');
        const userKey = document.getElementById('pushoverUserKey');
        const appToken = document.getElementById('pushoverAppToken');
        
        if (config && userKey && appToken) {
            if (enabled) {
                config.style.opacity = '1';
                config.style.pointerEvents = 'auto';
                userKey.disabled = false;
                appToken.disabled = false;
            } else {
                config.style.opacity = '0.5';
                config.style.pointerEvents = 'none';
                userKey.disabled = true;
                appToken.disabled = true;
            }
        }
    }

    /**
     * Download Frigate configuration
     */
    async downloadConfig() {
        try {
            const data = await this.api.getFrigateConfig();
            const dataStr = JSON.stringify(data, null, 2);
            const dataBlob = new Blob([dataStr], {type: 'application/json'});
            const url = URL.createObjectURL(dataBlob);
            const link = document.createElement('a');
            link.href = url;
            link.download = 'frigate_config.json';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Error downloading config:', error);
            alert('Error downloading configuration');
        }
    }

    /**
     * Create Frigate configuration backup
     */
    async createBackup() {
        if (!confirm('Create a backup of the current Frigate configuration?')) {
            return;
        }

        try {
            const response = await this.api.createFrigateBackup();
            if (response.ok) {
                location.reload();
            } else {
                alert('Error creating backup');
            }
        } catch (error) {
            console.error('Error creating backup:', error);
            alert('Error creating backup');
        }
    }

    /**
     * Restore Frigate configuration from backup
     */
    restoreBackup() {
        if (confirm('Are you sure you want to restore the configuration from backup? This will overwrite the current configuration.')) {
            window.location.href = '/frigate/config/backup/restore';
        }
    }

    /**
     * Get camera configuration
     * @param {string} cameraName - Camera name
     */
    async getCameraConfig(cameraName) {
        try {
            const config = await this.api.getCameraConfig(cameraName);
            this.cameraConfigs[cameraName] = config;
            return config;
        } catch (error) {
            console.error('Error fetching camera config:', error);
            throw error;
        }
    }

    /**
     * Save camera configuration
     * @param {string} cameraName - Camera name
     * @param {Object} formData - Configuration data
     */
    async saveCameraConfig(cameraName, formData) {
        try {
            const result = await this.api.saveCameraConfig(cameraName, formData);
            if (result.status === 'success') {
                this.cameraConfigs[cameraName] = formData;
                Utils.closeModal();
                location.reload();
            } else {
                alert('Error saving configuration: ' + (result.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error saving camera config:', error);
            alert('Error saving configuration');
        }
    }

    /**
     * Add new camera
     * @param {Object} data - Camera data
     */
    async addNewCamera(data) {
        try {
            const result = await this.api.addCamera(data);
            if (result.status === 'success') {
                Utils.closeModal();
                location.reload();
            } else {
                alert('Error adding camera: ' + (result.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error adding camera:', error);
            alert('Error adding camera');
        }
    }

    /**
     * Remove camera
     * @param {string} cameraName - Camera name
     */
    async removeCamera(cameraName) {
        if (!confirm(`Are you sure you want to remove camera '${cameraName}'? This action cannot be undone.`)) {
            return;
        }

        try {
            const result = await this.api.removeCamera(cameraName);
            if (result.status === 'success') {
                delete this.cameraConfigs[cameraName];
                location.reload();
            } else {
                alert('Error removing camera: ' + (result.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error removing camera:', error);
            alert('Error removing camera');
        }
    }

    /**
     * Create camera configuration form
     * @param {string} cameraName - Camera name
     * @param {Object} config - Current configuration
     * @returns {HTMLElement} Form element
     */
    createCameraForm(cameraName, config) {
        const form = document.createElement('div');
        
        const detectInput = config.ffmpeg?.inputs?.find(input => input.roles?.includes('detect'));
        const recordInput = config.ffmpeg?.inputs?.find(input => input.roles?.includes('record'));
        
        form.innerHTML = `
            <div class="form-group">
                <label for="detectPath">Detection Stream URL:</label>
                <input type="url" id="detectPath" name="detectPath" 
                       value="${detectInput?.path || ''}" 
                       placeholder="rtsp://username:password@ip:port/stream">
            </div>
            
            <div class="form-group">
                <label for="recordPath">Recording Stream URL:</label>
                <input type="url" id="recordPath" name="recordPath" 
                       value="${recordInput?.path || ''}" 
                       placeholder="rtsp://username:password@ip:port/stream">
            </div>
            
            <div class="form-group">
                <label for="detectWidth">Detection Width:</label>
                <input type="number" id="detectWidth" name="detectWidth" 
                       value="${config.detect?.width || 640}" min="320" max="1920">
            </div>
            
            <div class="form-group">
                <label for="detectHeight">Detection Height:</label>
                <input type="number" id="detectHeight" name="detectHeight" 
                       value="${config.detect?.height || 360}" min="240" max="1080">
            </div>
            
            <div class="form-group">
                <label for="detectFps">Detection FPS:</label>
                <input type="number" id="detectFps" name="detectFps" 
                       value="${config.detect?.fps || 10}" min="1" max="30">
            </div>
            
            <div class="form-group">
                <label for="motionArea">Motion Contour Area:</label>
                <input type="number" id="motionArea" name="motionArea" 
                       value="${config.motion?.contour_area || 2000}" min="100" max="10000">
            </div>
            
            <div class="modal-actions">
                <button type="button" class="btn-cancel" onclick="configManager.closeModal()">Cancel</button>
                <button type="button" class="btn-save" onclick="configManager.saveFormData('${cameraName}')">Save Configuration</button>
            </div>
        `;
        
        return form;
    }

    /**
     * Create add camera form
     * @returns {HTMLElement} Form element
     */
    createAddCameraForm() {
        const form = document.createElement('div');
        form.innerHTML = `
            <div class="form-group">
                <label for="newCameraName">Camera Name:</label>
                <input type="text" id="newCameraName" name="newCameraName" 
                       placeholder="e.g. front_door, backyard, garage" 
                       pattern="[a-z][a-z0-9_]*" 
                       title="Use lowercase letters, numbers, and underscores only">
            </div>
            
            <div class="form-group">
                <label for="newDetectPath">Detection Stream URL:</label>
                <input type="url" id="newDetectPath" name="newDetectPath" 
                       placeholder="rtsp://username:password@ip:port/stream" required>
            </div>
            
            <div class="form-group">
                <label for="newRecordPath">Recording Stream URL:</label>
                <input type="url" id="newRecordPath" name="newRecordPath" 
                       placeholder="rtsp://username:password@ip:port/stream" required>
            </div>
            
            <div class="form-group">
                <label for="newDetectWidth">Detection Width:</label>
                <input type="number" id="newDetectWidth" name="newDetectWidth" 
                       value="640" min="320" max="1920">
            </div>
            
            <div class="form-group">
                <label for="newDetectHeight">Detection Height:</label>
                <input type="number" id="newDetectHeight" name="newDetectHeight" 
                       value="360" min="240" max="1080">
            </div>
            
            <div class="form-group">
                <label for="newDetectFps">Detection FPS:</label>
                <input type="number" id="newDetectFps" name="newDetectFps" 
                       value="10" min="1" max="30">
            </div>
            
            <div class="form-group">
                <label for="newMotionArea">Motion Contour Area:</label>
                <input type="number" id="newMotionArea" name="newMotionArea" 
                       value="2000" min="100" max="10000">
            </div>
            
            <div class="modal-actions">
                <button type="button" class="btn-cancel" onclick="configManager.closeModal()">Cancel</button>
                <button type="button" class="btn-save" onclick="configManager.saveNewCameraForm()">Add Camera</button>
            </div>
        `;
        
        return form;
    }

    /**
     * Extract form data and save camera configuration
     * @param {string} cameraName - Camera name
     */
    saveFormData(cameraName) {
        const modal = document.getElementById('configModal');
        
        const formData = {
            ffmpeg: {
                hwaccel_args: 'preset-nvidia',
                inputs: []
            },
            detect: {
                fps: parseInt(modal.querySelector('#detectFps').value),
                width: parseInt(modal.querySelector('#detectWidth').value),
                height: parseInt(modal.querySelector('#detectHeight').value)
            },
            motion: {
                contour_area: parseInt(modal.querySelector('#motionArea').value)
            }
        };
        
        const detectPath = modal.querySelector('#detectPath').value;
        const recordPath = modal.querySelector('#recordPath').value;
        
        if (detectPath) {
            formData.ffmpeg.inputs.push({
                path: detectPath,
                roles: ['detect']
            });
        }
        
        if (recordPath) {
            formData.ffmpeg.inputs.push({
                path: recordPath,
                roles: ['record']
            });
        }
        
        this.saveCameraConfig(cameraName, formData);
    }

    /**
     * Save new camera form data
     */
    saveNewCameraForm() {
        const modal = document.getElementById('configModal');
        const cameraName = modal.querySelector('#newCameraName').value.trim();
        
        if (!cameraName) {
            alert('Please enter a camera name');
            return;
        }
        
        if (!/^[a-z][a-z0-9_]*$/.test(cameraName)) {
            alert('Camera name must start with lowercase letter and contain only lowercase letters, numbers, and underscores');
            return;
        }
        
        const formData = {
            camera_name: cameraName,
            camera_config: {
                ffmpeg: {
                    hwaccel_args: 'preset-nvidia',
                    inputs: []
                },
                detect: {
                    fps: parseInt(modal.querySelector('#newDetectFps').value),
                    width: parseInt(modal.querySelector('#newDetectWidth').value),
                    height: parseInt(modal.querySelector('#newDetectHeight').value)
                },
                motion: {
                    contour_area: parseInt(modal.querySelector('#newMotionArea').value)
                }
            }
        };
        
        const detectPath = modal.querySelector('#newDetectPath').value;
        const recordPath = modal.querySelector('#newRecordPath').value;
        
        if (detectPath) {
            formData.camera_config.ffmpeg.inputs.push({
                path: detectPath,
                roles: ['detect']
            });
        }
        
        if (recordPath) {
            formData.camera_config.ffmpeg.inputs.push({
                path: recordPath,
                roles: ['record']
            });
        }
        
        this.addNewCamera(formData);
    }

    /**
     * Close modal (wrapper for Utils.closeModal)
     */
    closeModal() {
        Utils.closeModal();
    }
}

// Create global configuration instances
let configManager;
let appConfig;

// Initialize when API is available
if (typeof window !== 'undefined') {
    document.addEventListener('DOMContentLoaded', async () => {
        if (window.api) {
            // Initialize app config first
            appConfig = new AppConfig();
            await appConfig.load();
            
            // Then initialize config manager
            configManager = new ConfigManager(window.api);
            await configManager.initialize();
            
            // Make available globally
            window.appConfig = appConfig;
            window.configManager = configManager;
        }
    });
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AppConfig, ConfigManager };
}

// Make available globally
window.AppConfig = AppConfig;
window.ConfigManager = ConfigManager;