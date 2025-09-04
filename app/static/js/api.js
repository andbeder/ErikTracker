/**
 * API Communication Layer for Erik Image Manager
 * Centralized API calls and communication with the backend
 */

class ApiClient {
    constructor() {
        this.baseUrl = window.location.origin;
        this.defaultHeaders = {
            'Content-Type': 'application/json'
        };
    }

    /**
     * Generic API request method
     * @param {string} url - API endpoint
     * @param {Object} options - Request options
     * @returns {Promise<Object>} Response data
     */
    async request(url, options = {}) {
        const config = {
            headers: this.defaultHeaders,
            ...options
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            } else {
                return response;
            }
        } catch (error) {
            console.error(`API request failed: ${url}`, error);
            throw error;
        }
    }

    /**
     * GET request
     */
    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }

    /**
     * POST request
     */
    async post(endpoint, data = null) {
        const options = { method: 'POST' };
        if (data) {
            options.body = JSON.stringify(data);
        }
        return this.request(endpoint, options);
    }

    /**
     * PUT request
     */
    async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    /**
     * DELETE request
     */
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    // === MATCHES API ===
    /**
     * Clear all detection matches
     */
    async clearMatches() {
        return this.post('/api/matches/clear');
    }

    /**
     * Get matches data
     */
    async getMatches() {
        return this.get('/api/matches');
    }

    // === COLMAP API ===
    /**
     * Capture camera snapshot
     * @param {string} camera - Camera name
     */
    async captureCameraSnapshot(camera) {
        return this.post('/api/colmap/capture-camera-snapshot', { camera_name: camera });
    }

    /**
     * Estimate camera pose
     * @param {string} camera - Camera name
     * @param {string} snapshotPath - Path to snapshot
     */
    async estimateCameraPose(camera, snapshotPath = null) {
        const data = { camera_name: camera };
        if (snapshotPath) {
            data.snapshot_path = snapshotPath;
        }
        return this.post('/api/colmap/estimate-camera-pose', data);
    }

    /**
     * Get camera poses
     */
    async getCameraPoses() {
        return this.get('/api/colmap/camera-poses');
    }

    /**
     * Calibrate camera pose
     * @param {string} cameraName - Camera name
     */
    async calibrateCameraPose(cameraName) {
        return this.post(`/api/colmap/calibrate-camera-pose/${cameraName}`);
    }

    /**
     * Get reconstruction status
     */
    async getReconstructionStatus() {
        return this.get('/api/colmap/reconstruction-status');
    }

    /**
     * Upload video file with progress tracking
     * @param {File} file - Video file
     * @param {Function} onProgress - Progress callback
     */
    async uploadVideo(file, onProgress = null) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            const formData = new FormData();
            formData.append('file', file);
            
            // Set up timeout (30 minutes for large files)
            xhr.timeout = 30 * 60 * 1000; // 30 minutes in milliseconds
            
            // Progress tracking
            xhr.upload.addEventListener('progress', (event) => {
                if (event.lengthComputable && onProgress) {
                    const percentComplete = (event.loaded / event.total) * 100;
                    onProgress(percentComplete, event.loaded, event.total);
                }
            });
            
            // Success handler
            xhr.addEventListener('load', () => {
                try {
                    if (xhr.status === 200) {
                        const response = JSON.parse(xhr.responseText);
                        resolve(response);
                    } else {
                        reject(new Error(`HTTP error! status: ${xhr.status} - ${xhr.statusText}`));
                    }
                } catch (error) {
                    reject(new Error('Failed to parse server response'));
                }
            });
            
            // Error handlers
            xhr.addEventListener('error', () => {
                reject(new Error('Network error occurred during upload'));
            });
            
            xhr.addEventListener('timeout', () => {
                reject(new Error('Upload timed out after 30 minutes'));
            });
            
            xhr.addEventListener('abort', () => {
                reject(new Error('Upload was aborted'));
            });
            
            // Start upload
            xhr.open('POST', '/api/colmap/upload-video');
            xhr.send(formData);
        });
    }

    /**
     * List uploaded videos
     */
    async listVideos() {
        return this.get('/api/colmap/list-videos');
    }

    /**
     * Upload reconstruction files
     * @param {FileList} files - Files to upload
     * @param {string} type - Type: 'sparse' or 'dense'
     */
    async uploadReconstruction(files, type) {
        const formData = new FormData();
        Array.from(files).forEach(file => formData.append('files', file));
        formData.append('type', type);
        
        return this.request('/api/colmap/upload-reconstruction', {
            method: 'POST',
            body: formData,
            headers: {} // Let browser set content-type for FormData
        });
    }

    // === ERIK LIVE API ===
    /**
     * Get active yard map configuration
     */
    async getMapConfig() {
        return this.get('/api/erik/map-config');
    }

    /**
     * Get Erik's live position
     */
    async getLivePosition() {
        return this.get('/api/erik/live-position');
    }

    // === YARD MAP API ===
    /**
     * Scan mesh boundaries
     * @param {string} meshFile - Mesh file path
     * @param {string} projection - Projection type
     */
    async scanBounds(meshFile, projection) {
        return this.post('/api/yard-map/scan-bounds', {
            mesh_file: meshFile,
            projection: projection
        });
    }

    /**
     * Generate yard map
     * @param {Object} config - Map generation configuration
     */
    async generateYardMap(config) {
        return this.post('/api/yard-map/generate', config);
    }

    /**
     * Use yard map as active
     * @param {Object} mapData - Map data
     */
    async useYardMap(mapData) {
        return this.post('/api/yard-map/use', mapData);
    }

    /**
     * Download yard map
     * @param {Object} config - Map configuration
     * @returns {Promise<Blob>} Map file blob
     */
    async downloadYardMap(config) {
        const response = await this.request('/api/yard-map/download', {
            method: 'POST',
            body: JSON.stringify(config)
        });
        
        if (response.ok) {
            return response.blob();
        } else {
            throw new Error('Download failed');
        }
    }

    // === SETTINGS API ===
    /**
     * Get global settings
     */
    async getGlobalSettings() {
        return this.get('/api/settings/global');
    }

    /**
     * Save global settings
     * @param {Object} settings - Settings object
     */
    async saveGlobalSettings(settings) {
        return this.post('/api/settings/global', settings);
    }

    // === CONFIG API ===
    /**
     * Get external IP configuration
     */
    async getExternalIP() {
        return this.get('/api/config/external-ip');
    }

    // === MESHES API ===
    /**
     * Get available mesh files
     */
    async getMeshes() {
        return this.get('/api/meshes');
    }

    // === CAMERA API ===
    /**
     * Get latest camera snapshot
     * @param {string} cameraName - Camera name
     */
    getCameraSnapshot(cameraName) {
        const timestamp = Date.now();
        const hostname = window.location.hostname;
        const port = window.location.port; // Use actual current port
        const portStr = port ? `:${port}` : '';
        return `http://${hostname}${portStr}/api/${cameraName}/latest.jpg?timestamp=${timestamp}`;
    }

    // === FRIGATE API ===
    /**
     * Get Frigate configuration
     */
    async getFrigateConfig() {
        return this.get('/frigate/config');
    }

    /**
     * Get camera configuration
     * @param {string} cameraName - Camera name
     */
    async getCameraConfig(cameraName) {
        return this.get(`/frigate/config/camera/${cameraName}`);
    }

    /**
     * Save camera configuration
     * @param {string} cameraName - Camera name
     * @param {Object} config - Camera configuration
     */
    async saveCameraConfig(cameraName, config) {
        return this.post(`/frigate/config/camera/${cameraName}`, config);
    }

    /**
     * Create backup of Frigate configuration
     */
    async createFrigateBackup() {
        return this.post('/frigate/config/backup');
    }

    /**
     * Add new camera to Frigate configuration
     * @param {Object} data - Camera data
     */
    async addCamera(data) {
        return this.post('/frigate/config/camera', data);
    }

    /**
     * Remove camera from Frigate configuration
     * @param {string} cameraName - Camera name
     */
    async removeCamera(cameraName) {
        return this.delete(`/frigate/config/camera/${cameraName}`);
    }
}

// === PROGRESS TRACKING ===
class ProgressTracker {
    constructor(apiClient) {
        this.api = apiClient;
        this.activeTrackers = new Map();
    }

    /**
     * Start progress monitoring for a specific phase
     * @param {string} phase - Processing phase
     * @param {Function} callback - Progress callback function
     * @param {number} interval - Polling interval in milliseconds
     */
    startTracking(phase, callback, interval = 1000) {
        if (this.activeTrackers.has(phase)) {
            this.stopTracking(phase);
        }

        const trackingInterval = setInterval(async () => {
            try {
                const response = await this.api.get(`/api/progress/${phase}`);
                if (response.complete) {
                    this.stopTracking(phase);
                    callback({ ...response, complete: true });
                } else {
                    callback(response);
                }
            } catch (error) {
                console.error(`Progress tracking error for ${phase}:`, error);
                this.stopTracking(phase);
                callback({ error: error.message, complete: true });
            }
        }, interval);

        this.activeTrackers.set(phase, trackingInterval);
    }

    /**
     * Stop progress tracking for a specific phase
     * @param {string} phase - Processing phase
     */
    stopTracking(phase) {
        if (this.activeTrackers.has(phase)) {
            clearInterval(this.activeTrackers.get(phase));
            this.activeTrackers.delete(phase);
        }
    }

    /**
     * Stop all active progress tracking
     */
    stopAllTracking() {
        this.activeTrackers.forEach((interval, phase) => {
            this.stopTracking(phase);
        });
    }
}

// Create global API client instance
const apiClient = new ApiClient();
const progressTracker = new ProgressTracker(apiClient);

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ApiClient, ProgressTracker };
}

// Make available globally
window.ApiClient = ApiClient;
window.ProgressTracker = ProgressTracker;
window.api = apiClient;
window.progressTracker = progressTracker;