/**
 * Image Manager Module for Erik Image Manager
 * Handles image uploads, file management, camera operations, and live feeds
 */

class ImageManager {
    constructor(apiClient) {
        this.api = apiClient;
        this.cameras = ['front_door', 'backyard', 'side_yard', 'garage'];
        this.cameraUpdateInterval = null;
        this.currentFullscreenCamera = null;
        this.isRTSPMode = false;
        this.refreshIntervals = new Map();
        
        // Camera RTSP configuration (will be loaded from config)
        this.cameraRTSPConfig = {
            'front_door': { ip: '192.168.0.101', port: 7101 },
            'backyard': { ip: '192.168.0.102', port: 7102 },
            'side_yard': { ip: '192.168.0.103', port: 7103 },
            'garage': { ip: '192.168.0.104', port: 7104 }
        };
        
        this.initializeEventListeners();
    }

    /**
     * Get configuration values with fallbacks
     */
    getConfig(key, fallback) {
        // Try global configuration first
        if (window.CONFIG_VALUES && window.CONFIG_VALUES[key]) {
            return window.CONFIG_VALUES[key];
        }
        
        // Try app config
        if (window.appConfig) {
            return window.appConfig.get(key, fallback);
        }
        
        // Try server config
        if (window.SERVER_CONFIG && window.SERVER_CONFIG[key]) {
            return window.SERVER_CONFIG[key];
        }
        
        return fallback;
    }

    /**
     * Initialize event listeners
     */
    initializeEventListeners() {
        // File selection preview
        const fileInput = document.getElementById('fileInput');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => this.handleFileSelection(e));
        }
        
        // Auto-refresh matches every 10 seconds
        this.startMatchesRefresh();
    }

    /**
     * Handle file selection preview
     * @param {Event} e - File input change event
     */
    handleFileSelection(e) {
        const files = e.target.files;
        const selectedDiv = document.getElementById('selectedFiles');
        const fileList = document.getElementById('fileList');
        
        if (!selectedDiv || !fileList) return;
        
        if (files.length > 0) {
            selectedDiv.style.display = 'block';
            fileList.innerHTML = '';
            
            for (let i = 0; i < files.length; i++) {
                const li = document.createElement('li');
                const sizeInMB = (files[i].size / 1024 / 1024).toFixed(2);
                li.textContent = `${files[i].name} (${sizeInMB} MB)`;
                fileList.appendChild(li);
            }
        } else {
            selectedDiv.style.display = 'none';
        }
    }

    /**
     * Clear all detection matches
     */
    async clearMatches() {
        if (!confirm('Are you sure you want to clear all detection matches? This cannot be undone.')) {
            return;
        }

        try {
            const data = await this.api.clearMatches();
            if (data.status === 'success') {
                location.reload();
            }
        } catch (error) {
            console.error('Error clearing matches:', error);
            alert('Error clearing matches. Please try again.');
        }
    }

    /**
     * Start auto-refresh for matches
     */
    startMatchesRefresh() {
        // Check for new matches every 10 seconds
        setInterval(() => this.refreshMatches(), 10000);
        
        // Schedule page refresh every 30 seconds (only on matches tab)
        this.schedulePageRefresh();
    }

    /**
     * Refresh matches data
     */
    async refreshMatches() {
        const matchesTab = document.getElementById('matches-tab');
        if (!matchesTab || !matchesTab.classList.contains('active')) {
            return;
        }

        try {
            const data = await this.api.getMatches();
            const currentCount = document.querySelectorAll('.match-card').length;
            if (data.total_count !== currentCount) {
                location.reload();
            }
        } catch (error) {
            console.error('Error fetching matches:', error);
        }
    }

    /**
     * Schedule page refresh for matches tab
     */
    schedulePageRefresh() {
        setTimeout(() => {
            const matchesTab = document.getElementById('matches-tab');
            if (matchesTab && matchesTab.classList.contains('active')) {
                location.reload();
            }
            // Always schedule the next check
            this.schedulePageRefresh();
        }, this.getConfig('matchRefreshInterval', 30000));
    }

    /**
     * Initialize camera thumbnails
     */
    initializeCameraThumbnails() {
        // Clear existing refresh intervals
        this.refreshIntervals.forEach((interval, key) => {
            if (key.startsWith('thumbnail-')) {
                clearInterval(interval);
                this.refreshIntervals.delete(key);
            }
        });
        
        // Start auto-refresh for thumbnails
        const refreshInterval = setInterval(() => this.refreshCameraThumbnails(), 5000);
        this.refreshIntervals.set('thumbnail-refresh', refreshInterval);
        
        // Refresh immediately
        setTimeout(() => this.refreshCameraThumbnails(), 1000);
    }

    /**
     * Refresh camera thumbnails
     */
    refreshCameraThumbnails() {
        const thumbnails = document.querySelectorAll('.thumbnail-image');
        thumbnails.forEach(img => {
            let currentSrc = img.src.split('?')[0];
            
            // Fix missing external IP if detected
            if (currentSrc.includes('http://:5000')) {
                const cameraName = img.id.replace('thumbnail-', '');
                const hostname = window.location.hostname;
                currentSrc = `http://${hostname}:5000/api/${cameraName}/latest.jpg`;
            }
            
            img.src = `${currentSrc}?timestamp=${Utils.getCurrentTimestamp()}`;
            
            // Reset states
            img.style.display = 'block';
            img.classList.remove('loaded');
            
            const cameraName = img.id.replace('thumbnail-', '');
            const errorDiv = document.getElementById(`error-${cameraName}`);
            const statusSpan = document.getElementById(`status-${cameraName}`);
            
            if (errorDiv) errorDiv.style.display = 'none';
            if (statusSpan) statusSpan.innerHTML = '🟢 Live';
        });
    }

    /**
     * Show thumbnail error state
     * @param {HTMLImageElement} img - Image element
     * @param {string} cameraName - Camera name
     */
    showThumbnailError(img, cameraName) {
        img.style.display = 'none';
        
        const errorDiv = document.getElementById(`error-${cameraName}`);
        const statusSpan = document.getElementById(`status-${cameraName}`);
        
        if (errorDiv) errorDiv.style.display = 'flex';
        if (statusSpan) statusSpan.innerHTML = '🔴 Offline';
    }

    /**
     * Initialize live tab
     */
    initializeLiveTab() {
        console.log('Initializing Live Tab...');
        
        // Clear existing interval first
        if (this.cameraUpdateInterval) {
            clearInterval(this.cameraUpdateInterval);
        }
        
        // Immediate load
        this.loadCameraSnapshots();
        
        // Set up auto-refresh interval
        this.cameraUpdateInterval = setInterval(() => {
            this.loadCameraSnapshots();
        }, this.getConfig('erikTrackingInterval', 2000));
        
        console.log('Live tab initialized with', this.cameras.length, 'cameras');
    }

    /**
     * Load camera snapshots
     */
    loadCameraSnapshots() {
        console.log('Loading camera snapshots for:', this.cameras);
        this.cameras.forEach(camera => {
            console.log('Updating camera:', camera);
            this.updateCameraSnapshot(camera);
        });
    }

    /**
     * Refresh camera snapshots (public method)
     */
    refreshCameraSnapshots() {
        this.loadCameraSnapshots();
    }

    /**
     * Update single camera snapshot
     * @param {string} cameraName - Camera name
     */
    updateCameraSnapshot(cameraName) {
        const img = document.getElementById(`camera-${cameraName}`);
        if (!img) {
            console.error('Camera image element not found:', `camera-${cameraName}`);
            return;
        }
        
        const statusDiv = img.parentElement.querySelector('.camera-status');
        const timestampDiv = img.parentElement.querySelector('.camera-timestamp');
        
        const url = this.api.getCameraSnapshot(cameraName);
        console.log('Loading camera image from:', url);
        
        // Update status to loading
        if (statusDiv) statusDiv.textContent = '⏳ Loading...';
        
        // Create test image to check availability
        const testImg = new Image();
        testImg.onload = () => {
            console.log('Camera image loaded successfully:', cameraName);
            img.src = url;
            if (statusDiv) statusDiv.textContent = '🟢 Live';
            if (timestampDiv) timestampDiv.textContent = Utils.formatTimestamp(new Date());
            img.style.opacity = '1';
        };
        testImg.onerror = (error) => {
            console.error('Camera image failed to load:', cameraName, error);
            if (statusDiv) statusDiv.textContent = '🔴 Offline';
            if (timestampDiv) timestampDiv.textContent = 'No signal';
            img.style.opacity = '0.3';
        };
        testImg.src = url;
    }

    /**
     * Open camera in fullscreen mode
     * @param {string} cameraName - Camera name
     */
    openCameraFullscreen(cameraName) {
        this.currentFullscreenCamera = cameraName;
        this.isRTSPMode = false;
        
        const fullscreenView = document.getElementById('camera-fullscreen-view');
        const gridView = document.getElementById('camera-grid-view');
        const backBtn = document.getElementById('back-to-grid-btn');
        const title = document.getElementById('fullscreen-camera-title');
        const snapshot = document.getElementById('fullscreen-snapshot');
        const video = document.getElementById('fullscreen-rtsp');
        const toggleBtn = document.getElementById('stream-toggle-btn');
        
        if (!fullscreenView || !gridView) return;
        
        // Update title
        if (title) {
            title.textContent = cameraName.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()) + ' Camera';
        }
        
        // Show fullscreen view
        gridView.style.display = 'none';
        fullscreenView.style.display = 'block';
        if (backBtn) backBtn.style.display = 'inline-block';
        
        // Reset to snapshot mode
        if (snapshot) snapshot.style.display = 'block';
        if (video) video.style.display = 'none';
        if (toggleBtn) toggleBtn.textContent = '📹 Switch to RTSP Stream';
        
        // Start fullscreen updates
        this.updateFullscreenSnapshot();
        this.startFullscreenUpdates();
    }

    /**
     * Start fullscreen snapshot updates
     */
    startFullscreenUpdates() {
        // Clear existing interval
        if (window.fullscreenUpdateInterval) {
            clearInterval(window.fullscreenUpdateInterval);
        }
        
        window.fullscreenUpdateInterval = setInterval(() => this.updateFullscreenSnapshot(), 1000);
    }

    /**
     * Update fullscreen snapshot
     */
    updateFullscreenSnapshot() {
        if (!this.currentFullscreenCamera || this.isRTSPMode) return;
        
        const snapshot = document.getElementById('fullscreen-snapshot');
        if (snapshot) {
            snapshot.src = this.api.getCameraSnapshot(this.currentFullscreenCamera);
        }
    }

    /**
     * Toggle RTSP stream mode
     */
    toggleRTSPStream() {
        if (!this.currentFullscreenCamera) return;
        
        const snapshot = document.getElementById('fullscreen-snapshot');
        const video = document.getElementById('fullscreen-rtsp');
        const toggleBtn = document.getElementById('stream-toggle-btn');
        
        if (!snapshot || !video || !toggleBtn) return;
        
        if (!this.isRTSPMode) {
            // Switch to HLS stream mode
            this.isRTSPMode = true;
            const rtspConfig = this.cameraRTSPConfig[this.currentFullscreenCamera];
            
            const hlsUrl = `http://${window.location.hostname}:8080/${this.currentFullscreenCamera}/playlist.m3u8`;
            
            snapshot.style.display = 'none';
            video.style.display = 'block';
            
            // Try to use HLS.js if available
            if (video.canPlayType('application/vnd.apple.mpegurl')) {
                video.src = hlsUrl;
            } else if (typeof Hls !== 'undefined') {
                const hls = new Hls();
                hls.loadSource(hlsUrl);
                hls.attachMedia(video);
            } else {
                const directRTSPUrl = `http://${window.location.hostname}:${rtspConfig.port}`;
                video.src = directRTSPUrl;
            }
            
            video.play().catch(e => {
                console.warn('Video play failed:', e);
                alert('Unable to start video stream. Please ensure RTSP forwarding is configured.');
                this.toggleRTSPStream(); // Switch back to snapshots
            });
            
            toggleBtn.textContent = '📸 Switch to Snapshots';
            
            // Clear snapshot update interval
            if (window.fullscreenUpdateInterval) {
                clearInterval(window.fullscreenUpdateInterval);
            }
        } else {
            // Switch back to snapshot mode
            this.isRTSPMode = false;
            video.pause();
            video.src = '';
            video.style.display = 'none';
            snapshot.style.display = 'block';
            toggleBtn.textContent = '📹 Switch to Live Stream';
            
            // Resume snapshot updates
            this.updateFullscreenSnapshot();
            this.startFullscreenUpdates();
        }
    }

    /**
     * Return to camera grid view
     */
    backToGrid() {
        const fullscreenView = document.getElementById('camera-fullscreen-view');
        const gridView = document.getElementById('camera-grid-view');
        const backBtn = document.getElementById('back-to-grid-btn');
        const video = document.getElementById('fullscreen-rtsp');
        
        if (!fullscreenView || !gridView) return;
        
        // Hide fullscreen and show grid
        fullscreenView.style.display = 'none';
        gridView.style.display = 'grid';
        if (backBtn) backBtn.style.display = 'none';
        
        // Stop video if playing
        if (video) {
            video.pause();
            video.src = '';
        }
        
        // Clear fullscreen update interval
        if (window.fullscreenUpdateInterval) {
            clearInterval(window.fullscreenUpdateInterval);
            window.fullscreenUpdateInterval = null;
        }
        
        // Reset variables
        this.currentFullscreenCamera = null;
        this.isRTSPMode = false;
    }

    /**
     * Toggle stream mode (alias for toggleRTSPStream)
     */
    toggleStreamMode() {
        this.toggleRTSPStream();
    }

    /**
     * Open thumbnail modal
     * @param {string} cameraName - Camera name
     */
    openThumbnailModal(cameraName) {
        const modal = Utils.createModal(`${cameraName.charAt(0).toUpperCase() + cameraName.slice(1)} Live Feed`);
        const modalBody = modal.querySelector('.modal-body');
        
        const cameraUrl = this.api.getCameraSnapshot(cameraName);
        
        modalBody.innerHTML = `
            <div style="text-align: center;">
                <img src="${cameraUrl}" 
                     alt="${cameraName} Live Feed" 
                     style="max-width: 100%; max-height: 70vh; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);"
                     id="modal-camera-${cameraName}">
                <div style="margin-top: 15px;">
                    <button class="action-button" onclick="imageManager.refreshModalThumbnail('${cameraName}')" 
                            style="background: linear-gradient(135deg, #17a2b8 0%, #138496 100%);">
                        🔄 Refresh
                    </button>
                </div>
            </div>
        `;
        
        modal.style.display = 'block';
        
        // Auto-refresh modal image every 3 seconds
        const refreshInterval = setInterval(() => {
            this.refreshModalThumbnail(cameraName);
        }, 3000);
        
        // Store interval reference
        modal.refreshInterval = refreshInterval;
        
        // Clear interval when modal closes
        const originalClose = modal.querySelector('.close').onclick;
        modal.querySelector('.close').onclick = function() {
            clearInterval(refreshInterval);
            originalClose.call(this);
        };
    }

    /**
     * Refresh modal thumbnail
     * @param {string} cameraName - Camera name
     */
    refreshModalThumbnail(cameraName) {
        const modalImg = document.getElementById(`modal-camera-${cameraName}`);
        if (modalImg) {
            modalImg.src = this.api.getCameraSnapshot(cameraName);
        }
    }

    /**
     * Refresh camera streams (for iframe-based streams)
     */
    refreshCameraStreams() {
        const iframes = document.querySelectorAll('#cameras-tab iframe');
        iframes.forEach(iframe => {
            const src = iframe.src;
            iframe.src = '';
            setTimeout(() => {
                iframe.src = src;
            }, 100);
        });
    }

    /**
     * Toggle fullscreen mode for camera grid
     */
    toggleFullscreenMode() {
        const cameraGrid = document.querySelector('#cameras-tab .camera-grid');
        if (!cameraGrid) return;
        
        const isCurrentlyFullscreen = cameraGrid.style.gridTemplateColumns === '1fr';
        
        if (!isCurrentlyFullscreen) {
            cameraGrid.style.gridTemplateColumns = '1fr';
            cameraGrid.style.gap = '30px';
            const iframes = cameraGrid.querySelectorAll('iframe');
            iframes.forEach(iframe => {
                iframe.style.height = '500px';
            });
        } else {
            cameraGrid.style.gridTemplateColumns = '1fr 1fr';
            cameraGrid.style.gap = '20px';
            const iframes = cameraGrid.querySelectorAll('iframe');
            iframes.forEach(iframe => {
                iframe.style.height = '300px';
            });
        }
    }

    /**
     * Load camera URLs and setup auto-refresh
     */
    async loadCameraUrls() {
        try {
            // Get external IP from config manager if available
            let externalIP = window.configManager?.externalIP || window.externalIP;
            
            if (!externalIP) {
                const result = await this.api.getExternalIP();
                externalIP = result.external_ip;
                window.externalIP = externalIP;
            }
            
            // Setup auto-refresh for camera snapshots
            const cameraConfigs = [
                { id: 'frontDoorStream', camera: 'front_door' },
                { id: 'backyardStream', camera: 'backyard' },
                { id: 'sideYardStream', camera: 'side_yard' },
                { id: 'garageStream', camera: 'garage' }
            ];
            
            cameraConfigs.forEach(config => {
                const baseUrl = `http://${externalIP}:5000/api/${config.camera}/latest.jpg`;
                Utils.setupImageRefresh(config.id, baseUrl, 1000);
            });
            
            // Update Frigate link
            Utils.safeElementOperation('frigateLink', el => el.href = `http://${externalIP}:5000`);
            
        } catch (error) {
            console.error('Error loading camera URLs:', error);
            
            // Fallback to default IP
            const fallbackIP = this.getConfig('externalIP', '192.168.68.54');
            window.externalIP = fallbackIP;
            
            const baseUrl = `http://${fallbackIP}:5000/api`;
            Utils.setupImageRefresh('frontDoorStream', `${baseUrl}/front_door/latest.jpg`, 1000);
            Utils.setupImageRefresh('backyardStream', `${baseUrl}/backyard/latest.jpg`, 1000);
            Utils.setupImageRefresh('sideYardStream', `${baseUrl}/side_yard/latest.jpg`, 1000);
            Utils.setupImageRefresh('garageStream', `${baseUrl}/garage/latest.jpg`, 1000);
            
            Utils.safeElementOperation('frigateLink', el => el.href = `http://${fallbackIP}:5000`);
        }
    }

    /**
     * Cleanup intervals and listeners
     */
    cleanup() {
        // Clear all refresh intervals
        this.refreshIntervals.forEach(interval => clearInterval(interval));
        this.refreshIntervals.clear();
        
        // Clear camera update interval
        if (this.cameraUpdateInterval) {
            clearInterval(this.cameraUpdateInterval);
            this.cameraUpdateInterval = null;
        }
        
        // Clear fullscreen update interval
        if (window.fullscreenUpdateInterval) {
            clearInterval(window.fullscreenUpdateInterval);
            window.fullscreenUpdateInterval = null;
        }
    }
}

// Global instance
let imageManager;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing ImageManager...');
    if (window.api) {
        console.log('API available, creating ImageManager instance...');
        imageManager = new ImageManager(window.api);
        window.imageManager = imageManager; // Make it globally accessible
        imageManager.loadCameraUrls();
        console.log('ImageManager initialized and made globally available');
    } else {
        console.error('API not available for ImageManager initialization');
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (imageManager) {
        imageManager.cleanup();
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ImageManager;
}

// Make available globally
window.ImageManager = ImageManager;