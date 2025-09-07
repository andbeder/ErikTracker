/**
 * Main Application Module for Erik Image Manager
 * Handles application initialization, navigation, and live map functionality
 */

class MainApplication {
    constructor() {
        this.liveMapInitialized = false;
        this.liveUpdateInterval = null;
        
        this.initializeApplication();
    }

    /**
     * Initialize the main application
     */
    async initializeApplication() {
        console.log('Erik Image Manager - Application starting...');
        
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.onDOMReady());
        } else {
            this.onDOMReady();
        }
    }

    /**
     * Handle DOM ready event
     */
    async onDOMReady() {
        try {
            // Check for any active progress from other clients
            this.checkForActiveProgress();
            this.checkForActiveStereoFusion();
            
            // Initialize progress bars (ensure they're hidden on load)
            this.initializeProgressBars();
            
            // Clear any lingering progress sessions
            this.clearProgressSessions();
            
            // Initialize navigation based on URL hash
            this.initializeNavigation();
            
            // Load external configurations
            await this.loadInitialConfigurations();
            
            console.log('Erik Image Manager - Application initialized successfully');
            
        } catch (error) {
            console.error('Error initializing application:', error);
        }
    }

    /**
     * Initialize progress bars
     */
    initializeProgressBars() {
        const progressContainers = ['featureProgress', 'sparseProgress', 'denseProgress', 'stereoProgress', 'fusionProgress'];
        progressContainers.forEach(containerId => {
            Utils.safeElementOperation(containerId, el => el.style.display = 'none');
        });
    }

    /**
     * Clear progress sessions
     */
    clearProgressSessions() {
        // Clear any existing progress tracking
        if (window.progressTracker) {
            window.progressTracker.stopAllTracking();
        }
        
        // Clear any progress update intervals
        if (window.progressUpdateInterval) {
            clearInterval(window.progressUpdateInterval);
            window.progressUpdateInterval = null;
        }
    }

    /**
     * Initialize navigation system
     */
    initializeNavigation() {
        const hash = window.location.hash.substring(1);
        
        // Map old hash values to new navigation system
        if (hash === 'photos' || hash === 'matches' || hash === 'reconstruct' || 
            hash === 'reconstruction' || hash === 'yard' || hash === 'yardmap' || 
            hash === 'cameras' || hash === 'frigate' || hash === 'settings') {
            
            // Show Config main tab and specific sub-tab
            this.showMainTab('config');
            if (hash === 'photos') this.showConfigTab('photos');
            else if (hash === 'matches') this.showConfigTab('matches');  
            else if (hash === 'reconstruct' || hash === 'reconstruction') this.showConfigTab('reconstruct');
            else if (hash === 'yard' || hash === 'yardmap') this.showConfigTab('yard');
            else if (hash === 'cameras' || hash === 'frigate') this.showConfigTab('cameras');
            else if (hash === 'settings') this.showConfigTab('settings');
            else this.showConfigTab('photos'); // Default config sub-tab
            
        } else if (hash === 'live' || hash === 'livemap') {
            this.showMainTab('live');
        } else if (hash === 'map') {
            this.showMainTab('map');
        } else {
            // Default to Map main tab
            this.showMainTab('map');
        }
    }

    /**
     * Load initial configurations
     */
    async loadInitialConfigurations() {
        try {
            // Load centralized configuration first
            if (window.appConfig) {
                await window.appConfig.load();
                console.log('✅ Application configuration loaded');
                this.applyConfigurationToUI();
            }
            
            // Load camera URLs
            if (window.imageManager) {
                await window.imageManager.loadCameraUrls();
            }
            
            // Initialize configuration manager if available
            if (window.configManager) {
                await window.configManager.initialize();
            }
            
            // Load saved yard map
            if (window.yardMapManager) {
                window.yardMapManager.loadSavedMapThumbnail();
            }
            
            console.log('✅ All configurations loaded successfully');
        } catch (error) {
            console.error('Failed to load configurations:', error);
        }
    }

    /**
     * Apply configuration values to UI elements
     */
    applyConfigurationToUI() {
        if (!window.appConfig) return;
        
        const uiConfig = window.appConfig.getUIConfig();
        
        // Update document title
        document.title = uiConfig.appTitle;
        
        // Store configuration values globally for other modules
        window.CONFIG_VALUES = {
            autoRefreshInterval: uiConfig.autoRefreshInterval,
            erikTrackingInterval: uiConfig.erikTrackingInterval,
            matchRefreshInterval: uiConfig.matchRefreshInterval,
            ...window.appConfig.getNetworkConfig(),
            ...window.appConfig.getPaths(),
            ...window.appConfig.getFileLimits()
        };
        
        console.log('✅ UI configuration applied:', window.CONFIG_VALUES);
    }

    /**
     * Show main tab (3-tier navigation)
     * @param {string} mainTabName - Main tab name
     */
    showMainTab(mainTabName) {
        // Hide all main content sections
        const mainContents = ['map-tab', 'live-tab', 'config-tab'];
        mainContents.forEach(contentId => {
            Utils.safeElementOperation(contentId, el => {
                el.classList.remove('active');
                el.style.display = 'none';
            });
        });
        
        // Show selected main content
        Utils.safeElementOperation(mainTabName + '-tab', el => {
            el.classList.add('active');
            el.style.display = 'block';
        });
        
        // Update main tab buttons
        document.querySelectorAll('.main-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        
        const activeMainTab = document.querySelector(`[onclick="showMainTab('${mainTabName}')"]`);
        if (activeMainTab) {
            activeMainTab.classList.add('active');
        }
        
        // Show/hide config sub-tabs
        const configSubtabs = document.getElementById('config-subtabs');
        if (configSubtabs) {
            if (mainTabName === 'config') {
                configSubtabs.style.display = 'flex';
                this.showConfigTab('photos'); // Default to photos tab
            } else {
                configSubtabs.style.display = 'none';
            }
        }
        
        // Initialize tab-specific functionality
        if (mainTabName === 'live') {
            setTimeout(() => this.initializeLiveTab(), 100);
        } else if (mainTabName === 'map') {
            setTimeout(() => this.initializeLiveMap(), 100);
        }
    }

    /**
     * Show configuration sub-tab
     * @param {string} configTabName - Config tab name
     */
    showConfigTab(configTabName) {
        // Hide all config tab contents
        document.querySelectorAll('.config-tab-content').forEach(tab => {
            tab.classList.remove('active');
            tab.style.display = 'none';
        });
        
        // Show selected config tab content
        Utils.safeElementOperation(configTabName + '-config-tab', el => {
            el.classList.add('active');
            el.style.display = 'block';
        });
        
        // Update config sub-tab buttons
        document.querySelectorAll('.sub-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        
        const activeConfigTab = document.querySelector(`[onclick="showConfigTab('${configTabName}')"]`);
        if (activeConfigTab) {
            activeConfigTab.classList.add('active');
        }
        
        // Initialize tab-specific functionality
        if (configTabName === 'cameras') {
            setTimeout(() => {
                if (window.imageManager) {
                    window.imageManager.initializeCameraThumbnails();
                }
                this.initializePoseRecognition();
            }, 100);
        } else if (configTabName === 'settings') {
            this.loadGlobalSettings();
            this.loadCameraPoseList();
            setTimeout(() => this.refreshSystemStatus(), 100);
        } else if (configTabName === 'yard') {
            setTimeout(() => this.checkReconstructionStatus(), 100);
        } else if (configTabName === 'reconstruct') {
            setTimeout(() => {
                if (window.colmapManager) {
                    window.colmapManager.loadUploadedVideos();
                }
            }, 100);
        }
    }

    /**
     * Legacy showTab function for backwards compatibility
     * @param {string} tabName - Tab name
     */
    showTab(tabName) {
        this.showTabWithLiveMap(tabName);
    }

    /**
     * Enhanced showTab function with live map handling
     * @param {string} tabName - Tab name
     */
    showTabWithLiveMap(tabName) {
        // Hide all tab contents
        const tabContents = document.querySelectorAll('.tab-content');
        tabContents.forEach(content => {
            content.classList.remove('active');
        });
        
        // Remove active class from all tabs
        const tabs = document.querySelectorAll('.tab');
        tabs.forEach(tab => {
            tab.classList.remove('active');
        });
        
        // Show selected tab content
        Utils.safeElementOperation(tabName + '-tab', el => el.classList.add('active'));
        
        // Add active class to clicked tab
        const activeTab = document.querySelector(`[onclick="showTab('${tabName}')"]`);
        if (activeTab) {
            activeTab.classList.add('active');
        }
        
        // Handle tab-specific logic
        if (tabName === 'livemap') {
            setTimeout(() => this.initializeLiveMap(), 100);
        } else {
            this.stopLiveUpdates();
        }
        
        // Load camera URLs when cameras tab is opened
        if (tabName === 'cameras' && window.imageManager) {
            window.imageManager.loadCameraUrls();
        }
        
        // Check reconstruction status when Yard Map tab is shown
        if (tabName === 'yardmap') {
            setTimeout(() => this.checkReconstructionStatus(), 100);
        }
        
        // Load settings when System tab is opened
        if (tabName === 'settings') {
            this.loadGlobalSettings();
            this.loadCameraPoseList();
            setTimeout(() => this.refreshSystemStatus(), 100);
        }
    }

    /**
     * Initialize live tab
     */
    initializeLiveTab() {
        console.log('Main.js: Initializing live tab...');
        if (window.imageManager) {
            console.log('Main.js: ImageManager found, initializing...');
            window.imageManager.initializeLiveTab();
        } else {
            console.error('Main.js: ImageManager not available!');
            // Try again after a short delay
            setTimeout(() => {
                if (window.imageManager) {
                    console.log('Main.js: ImageManager found on retry, initializing...');
                    window.imageManager.initializeLiveTab();
                } else {
                    console.error('Main.js: ImageManager still not available after retry!');
                }
            }, 500);
        }
    }

    /**
     * Initialize live map functionality
     */
    initializeLiveMap() {
        if (this.liveMapInitialized) return;
        
        console.log('Initializing live map...');
        this.loadActiveYardMap();
        this.startLiveUpdates();
        this.liveMapInitialized = true;
    }

    /**
     * Load active yard map
     */
    async loadActiveYardMap() {
        try {
            const data = await window.api.getMapConfig();
            
            if (data.success && data.map_available) {
                // Show the map
                const mapContainer = document.getElementById('yard-map-container');
                const mapImage = document.getElementById('yard-map-image');
                const noMapMessage = document.getElementById('no-map-message');
                
                if (mapImage) {
                    mapImage.src = data.map_url || '/static/active_yard_map.png';
                }
                if (mapContainer) mapContainer.style.display = 'block';
                if (noMapMessage) noMapMessage.style.display = 'none';
                
                console.log('Yard map loaded successfully');
            } else {
                this.showNoMapMessage();
                console.log('No active yard map found');
            }
        } catch (error) {
            console.error('Error loading yard map:', error);
            this.showNoMapMessage();
        }
    }

    /**
     * Show no map message
     */
    showNoMapMessage() {
        Utils.safeElementOperation('yard-map-container', el => el.style.display = 'none');
        Utils.safeElementOperation('no-map-message', el => el.style.display = 'block');
    }

    /**
     * Start live updates for Erik's position
     */
    startLiveUpdates() {
        // Update Erik's position every 500ms
        if (this.liveUpdateInterval) {
            clearInterval(this.liveUpdateInterval);
        }
        
        this.liveUpdateInterval = setInterval(() => this.updateErikPosition(), 500);
        console.log('Started live position updates (500ms interval)');
    }

    /**
     * Stop live updates
     */
    stopLiveUpdates() {
        if (this.liveUpdateInterval) {
            clearInterval(this.liveUpdateInterval);
            this.liveUpdateInterval = null;
            console.log('Stopped live position updates');
        }
    }

    /**
     * Update Erik's position
     */
    async updateErikPosition() {
        try {
            const data = await window.api.getLivePosition();
            
            if (data.success && data.position) {
                this.showErikDot(data.position.pixel_x, data.position.pixel_y);
                this.updateStatusPanel(data);
            } else {
                this.hideErikDot();
                this.updateStatusPanel(data);
            }
            
            this.updateSystemStatus(true);
            
        } catch (error) {
            console.error('Error updating Erik position:', error);
            this.updateSystemStatus(false);
        }
    }

    /**
     * Show Erik's dot on the map
     * @param {number} pixelX - X pixel position
     * @param {number} pixelY - Y pixel position
     */
    showErikDot(pixelX, pixelY) {
        Utils.safeElementOperation('erik-dot', el => {
            el.style.left = pixelX + 'px';
            el.style.top = pixelY + 'px';
            el.style.display = 'block';
        });
    }

    /**
     * Hide Erik's dot
     */
    hideErikDot() {
        Utils.safeElementOperation('erik-dot', el => el.style.display = 'none');
    }

    /**
     * Update status panel with Erik's information
     * @param {Object} data - Status data
     */
    updateStatusPanel(data) {
        // Update Erik Status
        Utils.safeElementOperation('erik-status', el => {
            if (data.success && data.position) {
                el.innerHTML = '<span style="color: #28a745;">✅ Detected</span>';
            } else {
                el.innerHTML = '<span style="color: #ffa500;">⏳ Searching...</span>';
            }
        });
        
        // Update Last Seen
        Utils.safeElementOperation('last-seen', el => {
            if (data.last_detection) {
                const timeDiff = Math.round((Date.now() - new Date(data.last_detection.timestamp).getTime()) / 1000);
                el.innerHTML = `<span style="color: #4facfe;">${timeDiff}s ago</span>`;
            } else {
                el.innerHTML = '<span style="color: #888;">Never</span>';
            }
        });
        
        // Update Detection Camera
        Utils.safeElementOperation('detection-camera', el => {
            if (data.detection_info && data.detection_info.camera) {
                const cameraName = data.detection_info.camera.replace('_', ' ').toUpperCase();
                el.innerHTML = `<span style="color: #4facfe;">📷 ${cameraName}</span>`;
            } else {
                el.innerHTML = '<span style="color: #888;">None</span>';
            }
        });
        
        // Update Coordinates
        Utils.safeElementOperation('erik-coordinates', el => {
            if (data.position) {
                const x = data.position.world_x?.toFixed(2) || '?';
                const y = data.position.world_y?.toFixed(2) || '?';
                el.innerHTML = `<span style="color: #4facfe;">(${x}, ${y})</span>`;
            } else {
                el.innerHTML = '<span style="color: #888;">Unknown</span>';
            }
        });
        
        // Update Confidence
        Utils.safeElementOperation('detection-confidence', el => {
            if (data.detection_info && data.detection_info.confidence) {
                const conf = (data.detection_info.confidence * 100).toFixed(0);
                el.innerHTML = `<span style="color: #4facfe;">${conf}%</span>`;
            } else {
                el.innerHTML = '<span style="color: #888;">--</span>';
            }
        });
    }

    /**
     * Update system status
     * @param {boolean} connected - Connection status
     */
    updateSystemStatus(connected) {
        Utils.safeElementOperation('system-status', el => {
            if (connected) {
                el.innerHTML = '<span style="color: #28a745;">✅ Connected</span>';
            } else {
                el.innerHTML = '<span style="color: #dc3545;">❌ Connection Error</span>';
            }
        });
    }

    /**
     * Load global settings
     */
    async loadGlobalSettings() {
        if (window.configManager) {
            await window.configManager.loadGlobalSettings();
        }
    }

    /**
     * Load camera pose list
     */
    async loadCameraPoseList() {
        if (window.colmapManager) {
            await window.colmapManager.loadCameraPoseList();
        }
    }

    /**
     * Refresh system status
     */
    refreshSystemStatus() {
        // Implementation can be added here if needed
        console.log('Refreshing system status...');
    }

    /**
     * Check reconstruction status
     */
    async checkReconstructionStatus() {
        if (window.colmapManager) {
            await window.colmapManager.updateProcessingStates();
        }
        
        if (window.yardMapManager) {
            // Enable/disable yard map controls based on reconstruction state
            const denseComplete = window.colmapManager?.processingState?.denseReconstruction;
            if (denseComplete) {
                this.enableMapGeneration();
            } else {
                this.disableMapGeneration();
            }
        }
    }

    /**
     * Enable map generation controls
     */
    enableMapGeneration() {
        const configInputs = document.querySelectorAll('#yardmap-tab input, #yardmap-tab select, #yardmap-tab button');
        configInputs.forEach(input => {
            if (!['frameStatus', 'featureStatus', 'sparseStatus', 'denseStatus'].includes(input.id)) {
                input.disabled = false;
            }
        });
    }

    /**
     * Disable map generation controls
     */
    disableMapGeneration() {
        const configInputs = document.querySelectorAll('#yardmap-tab input, #yardmap-tab select');
        configInputs.forEach(input => {
            input.disabled = true;
        });
        
        const mapButtons = document.querySelectorAll('#yardmap-tab button');
        mapButtons.forEach(button => {
            if (!button.onclick || !button.onclick.toString().includes('showTab')) {
                button.disabled = true;
            }
        });
    }

    /**
     * Initialize pose recognition system
     */
    async initializePoseRecognition() {
        if (window.colmapManager) {
            try {
                this.fixPosePreviewImages();
                const reconstructionStatus = await window.colmapManager.checkReconstructionStatus();
                this.updatePoseRecognitionStatus(reconstructionStatus);
            } catch (error) {
                console.error('Error initializing pose recognition:', error);
                Utils.safeElementOperation('poseStatusText', el => el.textContent = '❌ Error checking status');
            }
        }
    }

    /**
     * Fix pose preview images
     */
    fixPosePreviewImages() {
        const hostname = window.location.hostname;
        const previewImages = [
            { id: 'frontDoorPreview', camera: 'front_door' },
            { id: 'backyardPreview', camera: 'backyard' },
            { id: 'garagePreview', camera: 'garage' }
        ];
        
        previewImages.forEach(({ id, camera }) => {
            Utils.safeElementOperation(id, el => {
                if (el.src.includes('http://:5000')) {
                    el.src = `http://${hostname}:5000/api/${camera}/latest.jpg`;
                }
            });
        });
    }

    /**
     * Update pose recognition status
     * @param {Object} status - Reconstruction status
     */
    updatePoseRecognitionStatus(status) {
        const statusText = document.getElementById('poseStatusText');
        const reconstructionRequired = document.getElementById('reconstructionRequired');
        const poseEnabled = document.getElementById('poseRecognitionEnabled');
        const instructions = document.getElementById('poseInstructions');
        
        if (status.reconstruction_complete && status.has_dense) {
            if (statusText) {
                statusText.textContent = '✅ Ready for pose calibration';
                statusText.parentElement.style.background = '#d4edda';
                statusText.parentElement.style.color = '#155724';
            }
            
            if (reconstructionRequired) reconstructionRequired.style.display = 'none';
            if (poseEnabled) poseEnabled.style.display = 'block';
            if (instructions) instructions.style.display = 'block';
            
            // Load existing pose calibrations
            this.loadPoseCalibrations();
        } else {
            if (statusText) {
                statusText.textContent = '⚠️ Reconstruction required';
                statusText.parentElement.style.background = '#fff3cd';
                statusText.parentElement.style.color = '#856404';
            }
            
            if (reconstructionRequired) reconstructionRequired.style.display = 'block';
            if (poseEnabled) poseEnabled.style.display = 'none';
            if (instructions) instructions.style.display = 'none';
        }
    }

    /**
     * Load pose calibrations
     */
    async loadPoseCalibrations() {
        if (window.colmapManager) {
            try {
                const response = await window.api.getCameraPoses();
                if (response.poses) {
                    this.updatePoseDisplays(response.poses);
                }
            } catch (error) {
                console.error('Error loading pose calibrations:', error);
            }
        }
    }

    /**
     * Update pose displays
     * @param {Object} poses - Camera poses
     */
    updatePoseDisplays(poses) {
        const cameras = ['front_door', 'backyard', 'garage'];
        cameras.forEach(camera => {
            const pose = poses[camera];
            const cameraKey = camera.replace('_', camera === 'front_door' ? 'Door' : '');
            
            const statusElement = document.getElementById(`${cameraKey}Status`);
            const positionElement = document.getElementById(`${cameraKey}Position`);
            const accuracyElement = document.getElementById(`${cameraKey}Accuracy`);
            
            if (pose && pose.calibrated) {
                if (statusElement) {
                    statusElement.textContent = '✅ Calibrated';
                    statusElement.style.background = '#28a745';
                    statusElement.style.color = 'white';
                }
                
                if (positionElement) {
                    positionElement.textContent = `(${pose.position.x.toFixed(2)}, ${pose.position.y.toFixed(2)}, ${pose.position.z.toFixed(2)})`;
                }
                
                if (accuracyElement) {
                    accuracyElement.textContent = `${(pose.accuracy * 100).toFixed(1)}%`;
                }
            } else {
                if (statusElement) {
                    statusElement.textContent = '🔄 Not Calibrated';
                    statusElement.style.background = '#ffc107';
                    statusElement.style.color = '#333';
                }
                
                if (positionElement) positionElement.textContent = 'Not Set';
                if (accuracyElement) accuracyElement.textContent = 'N/A';
            }
        });
    }

    /**
     * Check for active progress (placeholder)
     */
    checkForActiveProgress() {
        // Implementation for checking active progress from other clients
        console.log('Checking for active progress...');
    }

    /**
     * Check for active stereo fusion (placeholder)
     */
    checkForActiveStereoFusion() {
        // Implementation for checking active stereo fusion
        console.log('Checking for active stereo fusion...');
    }
}

// Global functions for backwards compatibility
window.showTab = function(tabName) {
    if (window.mainApp) {
        window.mainApp.showTab(tabName);
    }
};

window.showConfigTab = function(configTabName) {
    if (window.mainApp) {
        window.mainApp.showConfigTab(configTabName);
    }
};

// Navigation functions are defined in base.html to ensure they're available before DOM content loads

// Initialize main application
let mainApp;
document.addEventListener('DOMContentLoaded', () => {
    mainApp = new MainApplication();
    window.mainApp = mainApp;
    
    // Handle any pending navigation calls
    if (window.pendingMainTab) {
        mainApp.showMainTab(window.pendingMainTab);
        window.pendingMainTab = null;
    }
    if (window.pendingConfigTab) {
        mainApp.showConfigTab(window.pendingConfigTab);
        window.pendingConfigTab = null;
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MainApplication;
}

// Make available globally
window.MainApplication = MainApplication;

// === GLOBAL FUNCTIONS FOR HTML ONCLICK HANDLERS ===

// Camera functions
window.refreshCameraSnapshots = function() {
    if (window.imageManager) {
        window.imageManager.refreshCameraSnapshots();
    }
};

window.openCameraFullscreen = function(cameraName) {
    if (window.imageManager) {
        window.imageManager.openCameraFullscreen(cameraName);
    }
};

window.backToGrid = function() {
    if (window.imageManager) {
        window.imageManager.backToGrid();
    }
};

window.toggleStreamMode = function() {
    if (window.imageManager) {
        window.imageManager.toggleStreamMode();
    }
};

// System status functions
window.refreshSystemStatus = function() {
    console.log('Refreshing system status...');
    // This will be implemented when system status is ready
};

window.checkSystemStatus = function() {
    window.refreshSystemStatus();
};

// Pose recognition functions
window.startPoseCalibration = function(cameraName) {
    console.log('Starting pose calibration for:', cameraName);
    // This will be implemented when pose recognition is ready
};

// Yard map functions
window.scanBoundaries = function() {
    console.log('Scanning mesh boundaries...');
    console.log('YardMapManager available:', !!window.yardMapManager);
    console.log('API available:', !!window.api);
    
    if (window.yardMapManager) {
        window.yardMapManager.scanBoundaries();
    } else if (window.api && typeof initializeYardMapManager === 'function') {
        // Try to initialize YardMapManager
        console.log('Attempting to initialize YardMapManager...');
        if (initializeYardMapManager()) {
            window.yardMapManager.scanBoundaries();
        } else {
            console.error('Failed to initialize YardMapManager');
            Utils.showToast('❌ Failed to initialize yard map manager', 'error');
        }
    } else {
        console.error('YardMapManager not initialized and cannot be initialized');
        console.error('Missing dependencies - API:', !!window.api, 'initializeYardMapManager:', typeof initializeYardMapManager);
        Utils.showToast('❌ Yard map manager not initialized', 'error');
    }
};

window.generateYardMap = function() {
    console.log('Generating yard map...');
    
    if (window.yardMapManager) {
        window.yardMapManager.generateYardMap();
    } else if (window.api && typeof initializeYardMapManager === 'function') {
        // Try to initialize YardMapManager
        console.log('Attempting to initialize YardMapManager...');
        if (initializeYardMapManager()) {
            window.yardMapManager.generateYardMap();
        } else {
            console.error('Failed to initialize YardMapManager');
            Utils.showToast('❌ Failed to initialize yard map manager', 'error');
        }
    } else {
        console.error('YardMapManager not initialized');
        Utils.showToast('❌ Yard map manager not initialized', 'error');
    }
};

window.loadSavedMapThumbnail = function() {
    console.log('Loading saved map thumbnail...');
    // This will be implemented when yard map functionality is ready
};

window.openMapFullscreen = function() {
    console.log('Opening map in fullscreen...');
    // This will be implemented when yard map functionality is ready
};

// Clear matches function
window.clearMatches = function() {
    if (window.imageManager) {
        window.imageManager.clearMatches();
    }
};

// Camera pose estimation functions
window.selectCamera = function() {
    console.log('Global selectCamera() called');
    console.log('window.colmapManager exists:', !!window.colmapManager);
    if (window.colmapManager) {
        console.log('Calling colmapManager.selectCamera()');
        window.colmapManager.selectCamera();
    } else {
        console.log('ERROR: colmapManager not initialized!');
    }
};

window.orientCamera = function() {
    console.log('Global orientCamera() called');
    if (window.colmapManager) {
        window.colmapManager.orientCamera();
    } else {
        console.log('ERROR: colmapManager not initialized!');
    }
};

// COLMAP reconstruction functions
window.handleVideoUpload = function(event) {
    if (window.colmapManager) {
        window.colmapManager.handleVideoUpload(event);
    }
};

window.extractFrames = function() {
    if (window.colmapManager) {
        window.colmapManager.extractFrames();
    }
};

window.showResetModal = function() {
    if (window.colmapManager) {
        window.colmapManager.showResetModal();
    }
};

window.runFeatureExtractionWithProgress = function() {
    if (window.colmapManager) {
        window.colmapManager.runFeatureExtractionWithProgress();
    }
};

window.runSparseReconstructionWithProgress = function() {
    console.log('Global runSparseReconstructionWithProgress called');
    console.log('window.colmapManager exists:', !!window.colmapManager);
    if (window.colmapManager) {
        console.log('Calling colmapManager.runSparseReconstructionWithProgress');
        window.colmapManager.runSparseReconstructionWithProgress();
    } else {
        console.error('colmapManager not initialized!');
    }
};

window.runDenseReconstructionWithProgress = function() {
    if (window.colmapManager) {
        window.colmapManager.runDenseReconstructionWithProgress();
    }
};

window.runDenseReconstructionModified = function() {
    if (window.colmapManager) {
        window.colmapManager.runDenseReconstructionModified();
    }
};

window.runCustomFusion = function() {
    if (window.colmapManager) {
        window.colmapManager.runCustomFusion();
    }
};

window.runStereoFusionWithProgress = function() {
    if (window.colmapManager) {
        window.colmapManager.runStereoFusionWithProgress();
    }
};

// Additional COLMAP upload functions
window.handleSparseUpload = function(event) {
    if (window.colmapManager) {
        window.colmapManager.handleSparseUpload(event);
    }
};

window.handlePlyUpload = function(event) {
    if (window.colmapManager) {
        window.colmapManager.handlePlyUpload(event);
    }
};

window.handleProjectZipUpload = function(event) {
    if (window.colmapManager) {
        window.colmapManager.handleProjectZipUpload(event);
    }
};

window.showResetModal = function() {
    if (window.colmapManager) {
        window.colmapManager.showResetModal();
    }
};

window.enablePointCloud = function() {
    if (window.colmapManager) {
        window.colmapManager.enablePointCloud();
    } else {
        console.error('colmapManager not initialized!');
    }
};

// Video management functions
window.deleteVideo = function(videoId, index) {
    if (window.colmapManager) {
        window.colmapManager.deleteVideo(videoId, index);
    }
};

window.updateVideoList = function() {
    if (window.colmapManager) {
        window.colmapManager.updateVideoList();
    }
};

window.loadUploadedVideos = function() {
    if (window.colmapManager) {
        window.colmapManager.loadUploadedVideos();
    }
};

// BYO Model Upload Functions
window.handleByoUpload = async function(event, fileType) {
    try {
        const file = event.target.files[0];
        if (!file) return;
        
        // Show uploading status
        showByoUploadStatus(`Uploading ${fileType}...`, 'info');
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('file_type', fileType);
        
        const response = await fetch('/api/colmap/upload-byo-model', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showByoUploadStatus(`✅ ${result.filename} uploaded successfully`, 'success');
            updateByoFileStatus(fileType, true, {
                filename: result.filename,
                size: result.size
            });
            await refreshByoModelStatus();
        } else {
            throw new Error(result.error);
        }
        
        // Clear file input
        event.target.value = '';
        
    } catch (error) {
        console.error(`BYO upload error for ${fileType}:`, error);
        showByoUploadStatus(`❌ Upload failed: ${error.message}`, 'error');
        event.target.value = '';
    }
};

window.deleteByoFile = async function(fileType) {
    if (!confirm(`Are you sure you want to delete the ${fileType} file?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/colmap/delete-byo-model/${fileType}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showByoUploadStatus(`✅ ${fileType} file deleted successfully`, 'success');
            updateByoFileStatus(fileType, false);
            await refreshByoModelStatus();
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        console.error(`Delete BYO file error for ${fileType}:`, error);
        showByoUploadStatus(`❌ Delete failed: ${error.message}`, 'error');
    }
};

window.enableByoPointCloud = async function() {
    try {
        showByoUploadStatus('🌟 Enabling BYO point cloud...', 'info');
        
        const response = await fetch('/api/colmap/enable-byo-point-cloud', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showByoUploadStatus(`✅ ${result.message}`, 'success');
            
            // Show point cloud enabled indicator
            const indicator = document.getElementById('pointCloudEnabledIndicator');
            if (indicator) {
                indicator.style.display = 'block';
            }
            
            // Disable the button
            const btn = document.getElementById('enableByoPointCloudBtn');
            if (btn) {
                btn.disabled = true;
                btn.textContent = '✅ Point Cloud Enabled';
            }
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        console.error('Enable BYO point cloud error:', error);
        showByoUploadStatus(`❌ Failed to enable point cloud: ${error.message}`, 'error');
    }
};

function updateByoFileStatus(fileType, uploaded, fileInfo = null) {
    const statusElement = document.getElementById(`${fileType}Status`);
    const infoElement = document.getElementById(`${fileType}Info`);
    
    if (uploaded) {
        // Update status indicator
        statusElement.textContent = '✅';
        statusElement.style.color = '#28a745';
        
        // Show file info
        if (infoElement && fileInfo) {
            const sizeInKB = Math.round(fileInfo.size / 1024);
            infoElement.querySelector('.filename').textContent = fileInfo.filename;
            infoElement.querySelector('.filesize').textContent = `${sizeInKB} KB`;
            infoElement.style.display = 'block';
        }
    } else {
        // Update status indicator
        statusElement.textContent = '❌';
        statusElement.style.color = '#dc3545';
        
        // Hide file info
        if (infoElement) {
            infoElement.style.display = 'none';
        }
    }
}

function showByoUploadStatus(message, type) {
    const statusElement = document.getElementById('byoUploadStatus');
    if (statusElement) {
        statusElement.innerHTML = message;
        statusElement.className = `upload-status ${type}`;
        statusElement.style.display = 'block';
        
        // Auto-hide after 5 seconds for success messages
        if (type === 'success') {
            setTimeout(() => {
                statusElement.style.display = 'none';
            }, 5000);
        }
    }
}

async function refreshByoModelStatus() {
    try {
        const response = await fetch('/api/colmap/list-byo-model');
        const result = await response.json();
        
        if (result.status === 'success') {
            const { files_status, file_info, uploaded_count, complete } = result;
            
            // Update individual file statuses
            for (const [fileType, uploaded] of Object.entries(files_status)) {
                const info = uploaded ? file_info[fileType] : null;
                updateByoFileStatus(fileType, uploaded, info);
            }
            
            // Update overall status
            const countElement = document.getElementById('byoUploadCount');
            const enableBtn = document.getElementById('enableByoPointCloudBtn');
            
            if (countElement) {
                countElement.textContent = uploaded_count;
            }
            
            if (enableBtn) {
                enableBtn.disabled = !complete;
                if (complete) {
                    enableBtn.style.opacity = '1';
                } else {
                    enableBtn.style.opacity = '0.5';
                }
            }
        }
    } catch (error) {
        console.error('Error refreshing BYO model status:', error);
    }
}

// Initialize BYO model status on page load
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(refreshByoModelStatus, 1000); // Wait for other initialization
});

// MQTT Settings Functions
window.showMQTTSettings = function() {
    const modal = document.getElementById('mqttSettingsModal');
    if (modal) {
        modal.style.display = 'flex';
        // Initialize MQTT settings when modal opens
        if (window.mqttSettings) {
            window.mqttSettings.initialize();
        }
    }
};

window.closeMQTTSettings = function() {
    const modal = document.getElementById('mqttSettingsModal');
    if (modal) {
        modal.style.display = 'none';
        // Stop status monitoring when modal closes
        if (window.mqttSettings) {
            window.mqttSettings.stopStatusMonitoring();
        }
    }
};

// Update MQTT quick status in Settings tab
window.updateMQTTQuickStatus = async function() {
    try {
        const response = await fetch('/api/mqtt/status');
        const data = await response.json();
        
        if (data.success) {
            const statusEl = document.getElementById('mqtt-quick-status');
            const brokerEl = document.getElementById('mqtt-quick-broker');
            
            if (statusEl) {
                statusEl.textContent = data.status.connected ? '🟢 Connected' : '🔴 Disconnected';
            }
            if (brokerEl) {
                brokerEl.textContent = data.status.broker || 'Not configured';
            }
        }
    } catch (error) {
        console.error('Failed to update MQTT status:', error);
    }
};

// Update MQTT status when Settings tab is shown
document.addEventListener('DOMContentLoaded', function() {
    // Initial status check
    updateMQTTQuickStatus();
    
    // Update status every 10 seconds when on Settings tab
    setInterval(function() {
        const settingsTab = document.querySelector('.tab-content[data-tab="settings"]');
        if (settingsTab && settingsTab.style.display !== 'none') {
            updateMQTTQuickStatus();
        }
    }, 10000);
    
    // Check for point cloud availability and enable camera pose section
    checkCameraPoseAvailability();
});

// Check if camera pose recognition should be enabled
async function checkCameraPoseAvailability() {
    try {
        // Check for BYO model point cloud or pipeline point cloud
        const meshResponse = await fetch('/api/yard-map/mesh-files');
        const meshData = await meshResponse.json();
        
        let hasPointCloud = false;
        
        if (meshData.mesh_files && meshData.mesh_files.length > 0) {
            // Check for pipeline reconstruction point cloud
            hasPointCloud = meshData.mesh_files.some(file => 
                file.name === 'yard_reconstruction.ply'
            );
            
            // If no pipeline point cloud, check for BYO model files
            if (!hasPointCloud) {
                const byoResponse = await fetch('/api/colmap/list-byo-model');
                const byoData = await byoResponse.json();
                
                if (byoData.success && byoData.files) {
                    const requiredFiles = ['cameras.bin', 'images.bin', 'points3D.bin', 'fusion.ply'];
                    const uploadedFiles = Object.keys(byoData.files);
                    hasPointCloud = requiredFiles.every(file => uploadedFiles.includes(file));
                }
            }
        }
        
        // Show/hide camera pose section based on availability
        const disabledSection = document.getElementById('poseRecognitionDisabled');
        const enabledSection = document.getElementById('poseRecognitionEnabled');
        
        if (hasPointCloud) {
            if (disabledSection) disabledSection.style.display = 'none';
            if (enabledSection) {
                enabledSection.style.display = 'block';
                // Load camera poses if colmapManager is available
                if (window.colmapManager) {
                    window.colmapManager.loadCameraPoseList();
                }
            }
        } else {
            if (disabledSection) disabledSection.style.display = 'block';
            if (enabledSection) enabledSection.style.display = 'none';
        }
        
    } catch (error) {
        console.error('Error checking camera pose availability:', error);
    }
}

// Camera management functions
window.editCamera = function(cameraName) {
    console.log('Edit camera:', cameraName);
    // Open the dedicated camera edit modal
    if (window.openCameraEdit) {
        window.openCameraEdit(cameraName);
    } else {
        alert(`Camera edit functionality not yet loaded for ${cameraName}.\n\nPlease refresh the page and try again.`);
    }
};

window.removeCamera = async function(cameraName) {
    console.log('Remove camera:', cameraName);
    
    if (!confirm(`Are you sure you want to remove camera "${cameraName}"?\n\nThis will:\n- Remove camera from Frigate configuration\n- Delete all associated recordings\n- Remove detection settings\n\nThis action cannot be undone.`)) {
        return;
    }
    
    try {
        // Use the config service to remove the camera
        if (window.configManager) {
            const result = await window.configManager.removeCamera(cameraName);
            if (result.success) {
                alert(`Camera "${cameraName}" removed successfully`);
                // Refresh the page to update the camera list
                window.location.reload();
            } else {
                throw new Error(result.error || 'Unknown error');
            }
        } else {
            throw new Error('Configuration manager not available');
        }
    } catch (error) {
        console.error('Error removing camera:', error);
        alert(`Failed to remove camera "${cameraName}": ${error.message}`);
    }
};