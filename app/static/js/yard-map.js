/**
 * Yard Map Module for Erik Image Manager
 * Handles yard map generation, visualization, and interactive controls
 */

class YardMapManager {
    constructor(apiClient) {
        this.api = apiClient;
        this.mapTransform = {
            scale: 1,
            translateX: 0,
            translateY: 0,
            rotation: 0
        };
        this.originalMapBounds = null;
        this.firstGenerationBounds = null;
        this.currentMapData = null;
        this.isDragging = false;
        this.isRightDragging = false;
        this.lastMouseX = 0;
        this.lastMouseY = 0;
        
        this.initializeEventListeners();
    }

    /**
     * Initialize event listeners and setup
     */
    initializeEventListeners() {
        // Load saved map thumbnail on page load
        this.loadSavedMapThumbnail();
        
        // ESC key functionality for map controls
        document.addEventListener('keydown', (e) => {
            const mapContainer = document.getElementById('mapContainer');
            if (!mapContainer || !mapContainer.matches(':hover')) return;
            
            if (e.key === 'r' || e.key === 'R') {
                e.preventDefault();
                const currentRotation = parseFloat(document.getElementById('rotation')?.value) || 0;
                const newRotation = currentRotation + (e.shiftKey ? -5 : 5);
                const rotationInput = document.getElementById('rotation');
                if (rotationInput) {
                    rotationInput.value = newRotation.toFixed(1);
                    this.mapTransform.rotation = newRotation;
                    this.updateMapTransform();
                }
            } else if (e.key === 'Escape') {
                this.resetMapTransform();
            }
        });
    }

    /**
     * Update axis labels based on projection
     * @param {string} axis1 - First axis label
     * @param {string} axis2 - Second axis label
     */
    updateAxisLabels(axis1, axis2) {
        Utils.safeElementOperation('axis1Label', el => el.textContent = `${axis1} Center (m):`);
        Utils.safeElementOperation('axis2Label', el => el.textContent = `${axis2} Center (m):`);
        Utils.safeElementOperation('axis1Small', el => el.textContent = `Center ${axis1} position`);
        Utils.safeElementOperation('axis2Small', el => el.textContent = `Center ${axis2} position`);
    }

    /**
     * Reset map transform
     * @param {boolean} keepRotation - Whether to preserve rotation value
     */
    resetMapTransform(keepRotation = false) {
        this.mapTransform = {
            scale: 1,
            translateX: 0,
            translateY: 0,
            rotation: keepRotation ? this.mapTransform.rotation : 0
        };
        
        const mapImage = document.getElementById('mapImage');
        if (mapImage) {
            mapImage.style.transform = 'translate(0, 0) scale(1) rotate(0deg)';
        }
        
        if (!keepRotation) {
            Utils.safeElementOperation('rotation', el => el.value = '0');
        }
    }

    /**
     * Initialize interactive map controls
     */
    initMapControls() {
        const mapContainer = document.getElementById('mapContainer');
        const mapImage = document.getElementById('mapImage');
        
        if (!mapContainer || !mapImage) return;
        
        // Remove existing listeners to prevent duplicates
        this.removeMapEventListeners();
        
        // Mouse down event
        this.mapMouseDownHandler = (e) => {
            e.preventDefault();
            
            if (e.button === 0) { // Left mouse button - pan
                this.isDragging = true;
                mapContainer.style.cursor = 'grabbing';
            } else if (e.button === 2) { // Right mouse button - rotate
                this.isRightDragging = true;
                mapContainer.style.cursor = 'crosshair';
            }
            
            this.lastMouseX = e.clientX;
            this.lastMouseY = e.clientY;
        };
        
        // Mouse move event
        this.mapMouseMoveHandler = (e) => {
            if (!this.isDragging && !this.isRightDragging) return;
            
            const deltaX = e.clientX - this.lastMouseX;
            const deltaY = e.clientY - this.lastMouseY;
            
            if (this.isDragging) {
                // Pan the image
                this.mapTransform.translateX += deltaX;
                this.mapTransform.translateY += deltaY;
                this.updateMapTransform();
            } else if (this.isRightDragging) {
                // Rotate the image
                const rotationSpeed = 0.5;
                this.mapTransform.rotation += deltaX * rotationSpeed;
                this.updateMapTransform();
            }
            
            this.lastMouseX = e.clientX;
            this.lastMouseY = e.clientY;
        };
        
        // Mouse up event
        this.mapMouseUpHandler = (e) => {
            this.isDragging = false;
            this.isRightDragging = false;
            mapContainer.style.cursor = 'grab';
        };
        
        // Mouse wheel event for zooming
        this.mapWheelHandler = (e) => {
            e.preventDefault();
            
            const zoomSpeed = 0.1;
            const zoomFactor = e.deltaY > 0 ? (1 - zoomSpeed) : (1 + zoomSpeed);
            
            const newScale = this.mapTransform.scale * zoomFactor;
            
            // Limit zoom range
            if (newScale >= 0.1 && newScale <= 5) {
                this.mapTransform.scale = newScale;
                this.updateMapTransform();
            }
        };
        
        // Context menu prevention
        this.mapContextMenuHandler = (e) => {
            e.preventDefault();
        };
        
        // Add event listeners
        mapContainer.addEventListener('mousedown', this.mapMouseDownHandler);
        document.addEventListener('mousemove', this.mapMouseMoveHandler);
        document.addEventListener('mouseup', this.mapMouseUpHandler);
        mapContainer.addEventListener('wheel', this.mapWheelHandler);
        mapContainer.addEventListener('contextmenu', this.mapContextMenuHandler);
        
        // Show controls help
        Utils.safeElementOperation('mapControls', el => el.style.display = 'block');
    }

    /**
     * Remove map event listeners
     */
    removeMapEventListeners() {
        const mapContainer = document.getElementById('mapContainer');
        
        if (mapContainer && this.mapMouseDownHandler) {
            mapContainer.removeEventListener('mousedown', this.mapMouseDownHandler);
            document.removeEventListener('mousemove', this.mapMouseMoveHandler);
            document.removeEventListener('mouseup', this.mapMouseUpHandler);
            mapContainer.removeEventListener('wheel', this.mapWheelHandler);
            mapContainer.removeEventListener('contextmenu', this.mapContextMenuHandler);
        }
    }

    /**
     * Update map transform
     */
    updateMapTransform() {
        const mapImage = document.getElementById('mapImage');
        if (mapImage) {
            const transform = `translate(${this.mapTransform.translateX}px, ${this.mapTransform.translateY}px) scale(${this.mapTransform.scale}) rotate(${this.mapTransform.rotation}deg)`;
            mapImage.style.transform = transform;
        }
        
        // Show/hide reset button
        const resetBtn = document.getElementById('resetTransform');
        if (resetBtn) {
            const hasTransform = this.mapTransform.scale !== 1 || 
                                this.mapTransform.translateX !== 0 || 
                                this.mapTransform.translateY !== 0 || 
                                this.mapTransform.rotation !== 0;
            resetBtn.style.display = hasTransform ? 'inline-block' : 'none';
        }
        
        // Update rotation field
        Utils.safeElementOperation('rotation', el => el.value = this.mapTransform.rotation.toFixed(1));
        
        // Update view window fields
        this.updateViewWindowFromTransform();
        
        // Display fixed resolution
        Utils.safeElementOperation('mapSizeDisplay', el => el.textContent = '1280 × 720 pixels (16:9)');
    }

    /**
     * Calculate current view bounds based on transform
     * @returns {Array|null} Bounds array [x_min, x_max, y_min, y_max]
     */
    getCurrentViewBounds() {
        if (!this.originalMapBounds) {
            if (this.firstGenerationBounds) {
                this.originalMapBounds = [...this.firstGenerationBounds];
            } else {
                return null;
            }
        }
        
        const mapImage = document.getElementById('mapImage');
        const mapContainer = document.getElementById('mapContainer');
        if (!mapImage || !mapContainer) return null;
        
        // If no transform applied, return original bounds
        if (this.mapTransform.scale === 1 && 
            this.mapTransform.translateX === 0 && 
            this.mapTransform.translateY === 0 && 
            this.mapTransform.rotation === 0) {
            return this.originalMapBounds;
        }
        
        // Calculate bounds with transform
        const [orig_x_min, orig_x_max, orig_y_min, orig_y_max] = this.originalMapBounds;
        const worldWidth = orig_x_max - orig_x_min;
        const worldHeight = orig_y_max - orig_y_min;
        
        const imageWidth = 640;
        const imageHeight = 360;
        
        const viewportWidthInOriginal = 1.0 / this.mapTransform.scale;
        const viewportHeightInOriginal = 1.0 / this.mapTransform.scale;
        
        const viewCenterX = 0.5 - (this.mapTransform.translateX / imageWidth / this.mapTransform.scale);
        const viewCenterY = 0.5 - (this.mapTransform.translateY / imageHeight / this.mapTransform.scale);
        
        const visibleWorldWidth = worldWidth / this.mapTransform.scale;
        const visibleWorldHeight = worldHeight / this.mapTransform.scale;
        
        const x_center = orig_x_min + viewCenterX * worldWidth;
        const y_center = orig_y_min + viewCenterY * worldHeight;
        
        let x_min = x_center - visibleWorldWidth / 2;
        let x_max = x_center + visibleWorldWidth / 2;
        let y_min = y_center - visibleWorldHeight / 2;
        let y_max = y_center + visibleWorldHeight / 2;
        
        // Clamp bounds with extension
        const extension = worldWidth * 0.1;
        x_min = Math.max(x_min, orig_x_min - extension);
        x_max = Math.min(x_max, orig_x_max + extension);
        y_min = Math.max(y_min, orig_y_min - extension);
        y_max = Math.min(y_max, orig_y_max + extension);
        
        return [x_min, x_max, y_min, y_max];
    }

    /**
     * Update view window controls based on current transform
     */
    updateViewWindowFromTransform() {
        const mapDisplay = document.getElementById('mapDisplay');
        if (!mapDisplay || mapDisplay.style.display === 'none' || !this.originalMapBounds) {
            return;
        }
        
        try {
            const bounds = this.getCurrentViewBounds();
            if (bounds && bounds.length === 4) {
                const centerX = (bounds[0] + bounds[1]) / 2;
                const centerY = (bounds[2] + bounds[3]) / 2;
                const output_width = 1280;
                const baseScale = (bounds[1] - bounds[0]) / output_width;
                
                Utils.safeElementOperation('xCenter', el => el.value = centerX.toFixed(2));
                Utils.safeElementOperation('yCenter', el => el.value = centerY.toFixed(2));
                Utils.safeElementOperation('scaleMetersPerPixel', el => el.value = baseScale.toFixed(4));
            }
        } catch (error) {
            console.warn('Could not update view window fields:', error);
        }
    }

    /**
     * Scan mesh boundaries
     */
    async scanBoundaries() {
        const meshFile = 'current_reconstruction/dense/fused.ply';
        const projection = document.getElementById('projection')?.value || 'xy';
        
        // Check if dense reconstruction is complete
        if (!window.colmapManager?.processingState?.denseReconstruction) {
            alert('Dense reconstruction must be completed first. Please complete the reconstruction pipeline.');
            return;
        }
        
        const scanBtn = document.getElementById('scanBoundsBtn');
        if (scanBtn) {
            scanBtn.disabled = true;
            scanBtn.textContent = '⏳ Scanning...';
        }
        
        try {
            const data = await this.api.scanBounds(meshFile, projection);
            
            if (data.success) {
                // Update axis labels based on projection
                this.updateAxisLabels(data.bounds.axis1_label, data.bounds.axis2_label);
                
                // Calculate center and scale from the scanned bounds
                const centerAxis1 = (data.bounds.axis1_min + data.bounds.axis1_max) / 2;
                const centerAxis2 = (data.bounds.axis2_min + data.bounds.axis2_max) / 2;
                const spanAxis1 = data.bounds.axis1_max - data.bounds.axis1_min;
                const spanAxis2 = data.bounds.axis2_max - data.bounds.axis2_min;
                
                // Calculate scale to fit the view (assuming 1280x720)
                const scaleX = spanAxis1 / 1280;
                const scaleY = spanAxis2 / 720;
                const scale = Math.max(scaleX, scaleY);
                
                // Fill in the fields
                Utils.safeElementOperation('xCenter', el => el.value = centerAxis1.toFixed(2));
                Utils.safeElementOperation('yCenter', el => el.value = centerAxis2.toFixed(2));
                Utils.safeElementOperation('scaleMetersPerPixel', el => el.value = scale.toFixed(4));
                
                // Enable Generate Map button
                Utils.safeElementOperation('generateBtn', el => el.disabled = false);
                
                if (scanBtn) {
                    scanBtn.textContent = '✅ Boundaries Set';
                    setTimeout(() => {
                        if (scanBtn) scanBtn.textContent = '📊 Scan Boundaries';
                    }, 2000);
                }
            } else {
                alert('Error scanning boundaries: ' + (data.error || 'Unknown error'));
                if (scanBtn) scanBtn.textContent = '📊 Scan Boundaries';
            }
        } catch (error) {
            console.error('Error scanning boundaries:', error);
            alert('Failed to scan boundaries: ' + error.message);
            if (scanBtn) scanBtn.textContent = '📊 Scan Boundaries';
        } finally {
            if (scanBtn) scanBtn.disabled = false;
        }
    }

    /**
     * Generate yard map
     */
    async generateYardMap() {
        const meshFile = 'current_reconstruction/dense/fused.ply';
        
        // Check if dense reconstruction is complete
        if (!window.colmapManager?.processingState?.denseReconstruction) {
            alert('Dense reconstruction must be completed first. Please complete the reconstruction pipeline.');
            return;
        }
        
        const rotation = parseFloat(document.getElementById('rotation')?.value) || 0;
        
        const config = {
            mesh_file: meshFile,
            grid_resolution: parseFloat(document.getElementById('gridResolution')?.value) || 0.1,
            max_points: 20000000,
            height_window: parseFloat(document.getElementById('heightWindow')?.value) || 0.5,
            coloring: document.getElementById('coloring')?.value || 'true_color',
            projection: document.getElementById('projection')?.value || 'xy',
            rotation: rotation,
            output_width: 1280,
            output_height: 720
        };
        
        // Get view window parameters
        const xCenter = parseFloat(document.getElementById('xCenter')?.value);
        const yCenter = parseFloat(document.getElementById('yCenter')?.value);
        const scale = parseFloat(document.getElementById('scaleMetersPerPixel')?.value);
        
        // Check if map has been transformed
        const hasTransform = this.mapTransform.scale !== 1 || 
                           this.mapTransform.translateX !== 0 || 
                           this.mapTransform.translateY !== 0 || 
                           this.mapTransform.rotation !== 0;
        
        if (hasTransform && this.originalMapBounds) {
            const currentBounds = this.getCurrentViewBounds();
            if (currentBounds) {
                config.custom_bounds = currentBounds;
            }
        } else if (!isNaN(xCenter) && !isNaN(yCenter) && !isNaN(scale)) {
            const halfWidth = (1280 * scale) / 2;
            const halfHeight = (720 * scale) / 2;
            config.custom_bounds = [
                xCenter - halfWidth,
                xCenter + halfWidth,
                yCenter - halfHeight,
                yCenter + halfHeight
            ];
        }
        
        this.currentMapData = config;
        
        // Show loading indicator
        Utils.safeElementOperation('loadingIndicator', el => el.style.display = 'block');
        Utils.safeElementOperation('mapDisplay', el => el.style.display = 'none');
        Utils.safeElementOperation('errorDisplay', el => el.style.display = 'none');
        Utils.safeElementOperation('generateBtn', el => el.disabled = true);
        Utils.safeElementOperation('useMapBtn', el => el.style.display = 'none');
        Utils.safeElementOperation('downloadBtn', el => el.style.display = 'none');
        
        // Reset and start progress bar
        Utils.safeElementOperation('progressBar', el => el.style.width = '0%');
        
        let progress = 0;
        const progressBar = document.getElementById('progressBar');
        const progressInterval = setInterval(() => {
            progress += 2;
            if (progress <= 90 && progressBar) {
                progressBar.style.width = progress + '%';
            }
        }, 1000);
        
        try {
            const data = await this.api.generateYardMap(config);
            
            clearInterval(progressInterval);
            if (progressBar) progressBar.style.width = '100%';
            
            setTimeout(() => {
                Utils.safeElementOperation('loadingIndicator', el => el.style.display = 'none');
                Utils.safeElementOperation('generateBtn', el => el.disabled = false);
                
                if (data.status === 'success') {
                    // Reset transform but keep rotation
                    this.resetMapTransform(true);
                    
                    // Display map
                    const mapImage = document.getElementById('mapImage');
                    if (mapImage) {
                        mapImage.src = data.image;
                        const fitToScreen = document.getElementById('fitToScreen')?.checked;
                        mapImage.style.width = fitToScreen ? '100%' : 'auto';
                    }
                    
                    // Update info display
                    Utils.safeElementOperation('mapDimensions', el => el.textContent = '1280×720px');
                    Utils.safeElementOperation('mapResolution', el => el.textContent = '1280×720');
                    Utils.safeElementOperation('mapGridSize', el => el.textContent = `${config.grid_resolution}m`);
                    Utils.safeElementOperation('mapProjection', el => {
                        const projectionText = config.projection === 'xy' ? 'Top-Down' : 
                                             config.projection === 'xz' ? 'Side View' : 'Front View';
                        el.textContent = projectionText;
                    });
                    
                    // Update bounds if available
                    if (config.custom_bounds) {
                        const centerX = (config.custom_bounds[0] + config.custom_bounds[1]) / 2;
                        const centerY = (config.custom_bounds[2] + config.custom_bounds[3]) / 2;
                        const spanX = config.custom_bounds[1] - config.custom_bounds[0];
                        const scale = spanX / 1280;
                        
                        Utils.safeElementOperation('xCenter', el => el.value = centerX.toFixed(2));
                        Utils.safeElementOperation('yCenter', el => el.value = centerY.toFixed(2));
                        Utils.safeElementOperation('scaleMetersPerPixel', el => el.value = scale.toFixed(4));
                    }
                    
                    // Store original bounds from log
                    if (data.log && !config.custom_bounds) {
                        const boundsMatch = data.log.match(/(?:Using 99% bounds|Using custom bounds|Data bounds): X=\[([-\d.]+), ([-\d.]+)\], Y=\[([-\d.]+), ([-\d.]+)\]/);
                        if (boundsMatch) {
                            this.originalMapBounds = [
                                parseFloat(boundsMatch[1]),
                                parseFloat(boundsMatch[2]),
                                parseFloat(boundsMatch[3]),
                                parseFloat(boundsMatch[4])
                            ];
                            
                            if (!this.firstGenerationBounds) {
                                this.firstGenerationBounds = [...this.originalMapBounds];
                            }
                        }
                    }
                    
                    // Show log if available
                    if (data.log) {
                        Utils.safeElementOperation('mapLog', el => {
                            el.textContent = data.log;
                            el.style.display = 'block';
                        });
                    }
                    
                    // Show controls and buttons
                    Utils.safeElementOperation('mapDisplay', el => el.style.display = 'block');
                    Utils.safeElementOperation('useMapBtn', el => {
                        el.style.display = 'inline-block';
                        el.disabled = false;
                    });
                    Utils.safeElementOperation('downloadBtn', el => {
                        el.style.display = 'inline-block';
                        el.disabled = false;
                    });
                    
                    // Initialize interactive controls
                    this.initMapControls();
                    this.updateViewWindowFromTransform();
                    
                } else {
                    // Show error
                    Utils.safeElementOperation('errorMessage', el => el.textContent = data.error || 'Unknown error');
                    Utils.safeElementOperation('errorDisplay', el => el.style.display = 'block');
                }
            }, 500);
            
        } catch (error) {
            clearInterval(progressInterval);
            Utils.safeElementOperation('loadingIndicator', el => el.style.display = 'none');
            Utils.safeElementOperation('generateBtn', el => el.disabled = false);
            Utils.safeElementOperation('errorMessage', el => el.textContent = 'Network error: ' + error.message);
            Utils.safeElementOperation('errorDisplay', el => el.style.display = 'block');
            console.error('Error generating yard map:', error);
        }
    }

    /**
     * Use yard map as active
     */
    async useYardMap() {
        if (!this.currentMapData) {
            alert('Please generate a map first');
            return;
        }
        
        const useBtn = document.getElementById('useMapBtn');
        const statusEl = document.getElementById('mapStatus');
        
        if (useBtn) useBtn.disabled = true;
        if (statusEl) {
            statusEl.textContent = 'Saving...';
            statusEl.style.color = '#ffc107';
        }
        
        try {
            const data = await this.api.useYardMap(this.currentMapData);
            
            if (data.status === 'success') {
                if (statusEl) {
                    statusEl.textContent = 'Active Map';
                    statusEl.style.color = '#28a745';
                }
                Utils.showNotification('✅ Map saved and set as active for yard tracking', 'success');
                
                // Update saved map thumbnail
                const mapImage = document.getElementById('mapImage');
                if (mapImage && mapImage.src) {
                    this.updateSavedMapThumbnail(mapImage.src);
                }
            } else {
                if (statusEl) {
                    statusEl.textContent = 'Save Failed';
                    statusEl.style.color = '#dc3545';
                }
                Utils.showNotification('❌ Failed to save map: ' + (data.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            if (statusEl) {
                statusEl.textContent = 'Save Failed';
                statusEl.style.color = '#dc3545';
            }
            Utils.showNotification('❌ Network error: ' + error.message, 'error');
            console.error('Error saving yard map:', error);
        } finally {
            if (useBtn) useBtn.disabled = false;
        }
    }

    /**
     * Download yard map
     */
    async downloadYardMap() {
        if (!this.currentMapData) {
            alert('Please generate a map first');
            return;
        }
        
        const config = Utils.deepClone(this.currentMapData);
        
        // Add current view bounds if map is transformed
        const currentBounds = this.getCurrentViewBounds();
        if (currentBounds) {
            config.custom_bounds = currentBounds;
        }
        
        try {
            const blob = await this.api.downloadYardMap(config);
            
            // Create download link
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            
            const projection = document.getElementById('projection')?.value || 'xy';
            const gridRes = config.grid_resolution !== 0.1 ? `_grid${config.grid_resolution}m` : '';
            const viewSuffix = projection !== 'xy' ? `_${projection}` : '';
            a.download = `erik_yard_map${gridRes}${viewSuffix}.png`;
            
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
        } catch (error) {
            console.error('Download error:', error);
            alert('Error downloading yard map. Please try again.');
        }
    }

    /**
     * Toggle fit to screen mode
     */
    toggleFitToScreen() {
        const fitToScreen = document.getElementById('fitToScreen')?.checked;
        const mapImage = document.getElementById('mapImage');
        const mapContainer = document.getElementById('mapContainer');
        
        if (mapImage && mapContainer) {
            if (fitToScreen) {
                mapImage.style.width = '100%';
                mapImage.style.height = 'auto';
                mapContainer.style.maxHeight = '600px';
            } else {
                mapImage.style.width = '1280px';
                mapImage.style.height = '720px';
                mapContainer.style.maxHeight = '600px';
            }
            
            // Reset transforms when toggling fit
            this.resetMapTransform();
        }
    }

    /**
     * Show map modal
     */
    showMapModal() {
        const mapImg = document.getElementById('mapImage');
        if (!mapImg || !mapImg.src) {
            alert('No map available to display');
            return;
        }
        
        const modal = document.createElement('div');
        modal.id = 'mapModal';
        modal.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            background: rgba(0,0,0,0.8); display: flex; align-items: center; 
            justify-content: center; z-index: 1000; cursor: pointer;
        `;
        
        const fullImg = document.createElement('img');
        fullImg.src = mapImg.src;
        fullImg.style.cssText = `
            max-width: 95%; max-height: 95%; 
            border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        `;
        
        modal.appendChild(fullImg);
        document.body.appendChild(modal);
        
        modal.onclick = function() {
            document.body.removeChild(modal);
        };
    }

    /**
     * Update saved map thumbnail
     * @param {string} imageSrc - Image source URL
     */
    updateSavedMapThumbnail(imageSrc) {
        const thumbnail = document.getElementById('savedMapThumbnail');
        const thumbnailContainer = document.getElementById('savedMapThumbnailContainer');
        const noMapMsg = document.getElementById('noSavedMapThumbnail');
        
        if (imageSrc) {
            if (thumbnail) thumbnail.src = imageSrc;
            if (thumbnailContainer) thumbnailContainer.style.display = 'block';
            if (noMapMsg) noMapMsg.style.display = 'none';
            localStorage.setItem('savedYardMap', imageSrc);
        } else {
            if (thumbnailContainer) thumbnailContainer.style.display = 'none';
            if (noMapMsg) noMapMsg.style.display = 'block';
            localStorage.removeItem('savedYardMap');
        }
    }

    /**
     * Load saved map thumbnail from localStorage
     */
    loadSavedMapThumbnail() {
        const savedMap = localStorage.getItem('savedYardMap');
        if (savedMap) {
            this.updateSavedMapThumbnail(savedMap);
        }
    }

    /**
     * Show saved map modal
     */
    showSavedMapModal() {
        const savedImg = document.getElementById('savedMapThumbnail');
        if (!savedImg || !savedImg.src) {
            alert('No saved map available to display');
            return;
        }
        
        const modal = document.createElement('div');
        modal.id = 'savedMapModal';
        modal.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            background: rgba(0,0,0,0.8); display: flex; align-items: center; 
            justify-content: center; z-index: 1000; cursor: pointer;
        `;
        
        const fullImg = document.createElement('img');
        fullImg.src = savedImg.src;
        fullImg.style.cssText = `
            max-width: 95%; max-height: 95%; 
            border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        `;
        
        modal.appendChild(fullImg);
        document.body.appendChild(modal);
        
        modal.onclick = function() {
            document.body.removeChild(modal);
        };
    }

    /**
     * Update mesh info display
     */
    updateMeshInfo() {
        const select = document.getElementById('meshSelect');
        const info = document.getElementById('meshInfo');
        const generateBtn = document.getElementById('generateBtn');
        const downloadBtn = document.getElementById('downloadBtn');
        const scanBoundsBtn = document.getElementById('scanBoundsBtn');
        
        if (!select) return;
        
        // Always reset view window fields when mesh changes
        Utils.safeElementOperation('xCenter', el => el.value = '');
        Utils.safeElementOperation('yCenter', el => el.value = '');
        Utils.safeElementOperation('scaleMetersPerPixel', el => el.value = '');
        
        if (generateBtn) generateBtn.disabled = true;
        if (downloadBtn) downloadBtn.disabled = true;
        
        // Reset displays
        Utils.safeElementOperation('mapDisplay', el => el.style.display = 'none');
        Utils.safeElementOperation('errorDisplay', el => el.style.display = 'none');
        
        // Reset transform state
        this.resetMapTransform();
        this.originalMapBounds = null;
        this.currentMapData = null;
        
        if (select.value) {
            const option = select.options[select.selectedIndex];
            if (info) {
                Utils.safeElementOperation('meshSize', el => el.textContent = (option.dataset.size || '0') + ' MB');
                Utils.safeElementOperation('meshModified', el => el.textContent = option.dataset.modified || 'Unknown');
                info.style.display = 'block';
            }
            if (scanBoundsBtn) scanBoundsBtn.style.display = 'inline-block';
        } else {
            if (info) info.style.display = 'none';
            if (scanBoundsBtn) scanBoundsBtn.style.display = 'none';
        }
    }
}

// Global instance
let yardMapManager;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (window.api) {
        yardMapManager = new YardMapManager(window.api);
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = YardMapManager;
}

// Make available globally
window.YardMapManager = YardMapManager;