/**
 * Camera Overlay System for Yard Map
 * Renders camera view cones and field of view projections onto the yard map
 */

class CameraOverlay {
    constructor() {
        this.cameras = new Map();
        this.mapBounds = null;
        this.canvas = null;
        this.ctx = null;
        this.visible = true;
        
        // Default camera parameters (can be overridden per camera)
        this.defaultCameraParams = {
            fov_horizontal: 87,  // degrees - typical security camera
            fov_vertical: 58,    // degrees
            view_distance: 30   // meters - max useful distance
        };
        
        this.colors = [
            '#ff4444', '#44ff44', '#4444ff', '#ffff44', 
            '#ff44ff', '#44ffff', '#ff8844', '#88ff44'
        ];
    }
    
    /**
     * Initialize the overlay system with map metadata
     */
    async initialize(mapContainer, mapMetadata) {
        this.mapBounds = mapMetadata.map_bounds;
        this.mapWidth = mapMetadata.image_width || 1280;
        this.mapHeight = mapMetadata.image_height || 720;
        
        // Create overlay canvas
        this.canvas = document.createElement('canvas');
        this.canvas.width = this.mapWidth;
        this.canvas.height = this.mapHeight;
        this.canvas.style.position = 'absolute';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.pointerEvents = 'none';
        this.canvas.style.zIndex = '10';
        
        this.ctx = this.canvas.getContext('2d');
        
        // Add to map container
        mapContainer.appendChild(this.canvas);
        
        // Load camera poses
        await this.loadCameraPoses();
        
        console.log('Camera overlay initialized with map bounds:', this.mapBounds);
    }
    
    /**
     * Load camera poses from the API
     */
    async loadCameraPoses() {
        try {
            const response = await fetch('/api/colmap/camera-poses');
            const data = await response.json();
            
            if (data.success && data.poses) {
                this.cameras.clear();
                let colorIndex = 0;
                
                for (const [cameraName, poseData] of Object.entries(data.poses)) {
                    const camera = {
                        name: cameraName,
                        pose: poseData,
                        color: this.colors[colorIndex % this.colors.length],
                        params: { ...this.defaultCameraParams },
                        visible: true
                    };
                    
                    this.cameras.set(cameraName, camera);
                    colorIndex++;
                }
                
                console.log(`Loaded ${this.cameras.size} camera poses for overlay`);
                this.render();
            }
        } catch (error) {
            console.error('Error loading camera poses for overlay:', error);
        }
    }
    
    /**
     * Convert world coordinates (meters) to map pixel coordinates
     */
    worldToPixel(worldX, worldY) {
        if (!this.mapBounds) return { x: 0, y: 0 };
        
        const { x_min, x_max, y_min, y_max, center_x, center_y, scale_meters_per_pixel, rotation_degrees } = this.mapBounds;
        
        // Use center and scale if available, otherwise calculate from bounds
        let pixelX, pixelY;
        
        if (center_x != null && center_y != null && scale_meters_per_pixel != null) {
            // Use center/scale method (more accurate for user-adjusted maps)
            const mapCenterX = this.mapWidth / 2;
            const mapCenterY = this.mapHeight / 2;
            
            const deltaX = worldX - center_x;
            const deltaY = worldY - center_y;
            
            pixelX = mapCenterX + (deltaX / scale_meters_per_pixel);
            pixelY = mapCenterY - (deltaY / scale_meters_per_pixel); // Flip Y axis
        } else if (x_min != null && x_max != null && y_min != null && y_max != null) {
            // Use bounds method (fallback)
            const worldWidth = x_max - x_min;
            const worldHeight = y_max - y_min;
            
            pixelX = ((worldX - x_min) / worldWidth) * this.mapWidth;
            pixelY = this.mapHeight - ((worldY - y_min) / worldHeight) * this.mapHeight; // Flip Y axis
        } else {
            console.warn('Insufficient map bounds data for coordinate conversion');
            return { x: 0, y: 0 };
        }
        
        // Apply rotation if specified
        if (rotation_degrees && rotation_degrees !== 0) {
            const angle = (rotation_degrees * Math.PI) / 180;
            const centerX = this.mapWidth / 2;
            const centerY = this.mapHeight / 2;
            
            const relX = pixelX - centerX;
            const relY = pixelY - centerY;
            
            pixelX = centerX + relX * Math.cos(-angle) - relY * Math.sin(-angle);
            pixelY = centerY + relX * Math.sin(-angle) + relY * Math.cos(-angle);
        }
        
        return { x: pixelX, y: pixelY };
    }
    
    /**
     * Extract camera position and orientation from pose data
     */
    getCameraWorldPosition(poseData) {
        // COLMAP transformation matrix is world-to-camera: X_cam = R * X_world + t
        // To get camera position in world coordinates, we need: X_world = -R^T * t
        // However, the 'translation' field in the JSON already contains the camera position in world coordinates
        // (it's been pre-computed from the transformation matrix)
        const translation = poseData.translation;
        return {
            x: translation[0],
            y: translation[1], 
            z: translation[2]
        };
    }
    
    /**
     * Calculate camera viewing direction from transformation matrix
     */
    getCameraDirection(poseData) {
        // COLMAP uses a world-to-camera transformation matrix
        // Camera looks along +Z in camera coordinates
        // To get the viewing direction in world coordinates, we need the third row of the rotation matrix
        const matrix = poseData.transformation_matrix;
        
        // The transformation matrix is [R|t] where R is rotation and t is translation
        // For world-to-camera transform, the viewing direction in world space is R^T * [0,0,1]
        // This equals the third row of R (since R^T third column = R third row)
        const viewX = matrix[2][0]; // R[2,0]
        const viewY = matrix[2][1]; // R[2,1] 
        const viewZ = matrix[2][2]; // R[2,2]
        
        // For top-down view, we project onto XY plane
        // Calculate yaw angle (rotation around Z axis)
        const yaw = Math.atan2(viewY, viewX);
        
        console.log(`Camera ${poseData.camera_name}: direction=(${viewX.toFixed(3)}, ${viewY.toFixed(3)}, ${viewZ.toFixed(3)}), yaw=${(yaw * 180/Math.PI).toFixed(1)}°, pos=(${poseData.translation[0].toFixed(2)}, ${poseData.translation[1].toFixed(2)})`);
        
        return {
            x: viewX,
            y: viewY,
            z: viewZ,
            yaw: yaw
        };
    }
    
    /**
     * Calculate field of view cone points for a camera
     */
    calculateFOVCone(camera) {
        const position = this.getCameraWorldPosition(camera.pose);
        const direction = this.getCameraDirection(camera.pose);
        const params = camera.params;
        
        // Use calculated direction from COLMAP matrix
        const yaw = direction.yaw;
        
        // Calculate cone endpoints for horizontal FOV
        const halfFOV = (params.fov_horizontal * Math.PI) / 180 / 2;
        const distance = params.view_distance;
        
        // Calculate the cone endpoints in world coordinates
        const leftAngle = yaw - halfFOV;
        const rightAngle = yaw + halfFOV;
        
        const leftEndX = position.x + distance * Math.cos(leftAngle);
        const leftEndY = position.y + distance * Math.sin(leftAngle);
        
        const rightEndX = position.x + distance * Math.cos(rightAngle);
        const rightEndY = position.y + distance * Math.sin(rightAngle);
        
        return {
            camera: { x: position.x, y: position.y },
            leftEnd: { x: leftEndX, y: leftEndY },
            rightEnd: { x: rightEndX, y: rightEndY },
            centerEnd: { 
                x: position.x + distance * Math.cos(yaw),
                y: position.y + distance * Math.sin(yaw)
            }
        };
    }
    
    /**
     * Render all camera overlays
     */
    render() {
        if (!this.ctx || !this.visible) return;
        
        // Clear canvas
        this.ctx.clearRect(0, 0, this.mapWidth, this.mapHeight);
        
        // Render each camera
        for (const camera of this.cameras.values()) {
            if (camera.visible) {
                this.renderCamera(camera);
            }
        }
    }
    
    /**
     * Render a single camera overlay
     */
    renderCamera(camera) {
        const cone = this.calculateFOVCone(camera);
        
        // Convert world coordinates to pixel coordinates
        const cameraPixel = this.worldToPixel(cone.camera.x, cone.camera.y);
        const leftPixel = this.worldToPixel(cone.leftEnd.x, cone.leftEnd.y);
        const rightPixel = this.worldToPixel(cone.rightEnd.x, cone.rightEnd.y);
        const centerPixel = this.worldToPixel(cone.centerEnd.x, cone.centerEnd.y);
        
        // Set drawing style
        this.ctx.strokeStyle = camera.color;
        this.ctx.fillStyle = camera.color + '20'; // Semi-transparent fill
        this.ctx.lineWidth = 2;
        
        // Draw FOV cone
        this.ctx.beginPath();
        this.ctx.moveTo(cameraPixel.x, cameraPixel.y);
        this.ctx.lineTo(leftPixel.x, leftPixel.y);
        this.ctx.lineTo(rightPixel.x, rightPixel.y);
        this.ctx.closePath();
        this.ctx.fill();
        this.ctx.stroke();
        
        // Draw center direction line
        this.ctx.setLineDash([5, 5]);
        this.ctx.beginPath();
        this.ctx.moveTo(cameraPixel.x, cameraPixel.y);
        this.ctx.lineTo(centerPixel.x, centerPixel.y);
        this.ctx.stroke();
        this.ctx.setLineDash([]); // Reset dash
        
        // Draw camera icon
        this.ctx.fillStyle = camera.color;
        this.ctx.beginPath();
        this.ctx.arc(cameraPixel.x, cameraPixel.y, 6, 0, Math.PI * 2);
        this.ctx.fill();
        
        // Draw camera label
        this.ctx.fillStyle = camera.color;
        this.ctx.font = '12px Arial';
        this.ctx.textAlign = 'left';
        this.ctx.fillText(camera.name, cameraPixel.x + 10, cameraPixel.y - 10);
    }
    
    /**
     * Toggle visibility of all camera overlays
     */
    toggleVisibility() {
        this.visible = !this.visible;
        if (this.visible) {
            this.render();
        } else {
            this.ctx.clearRect(0, 0, this.mapWidth, this.mapHeight);
        }
        return this.visible;
    }
    
    /**
     * Toggle visibility of a specific camera
     */
    toggleCamera(cameraName) {
        const camera = this.cameras.get(cameraName);
        if (camera) {
            camera.visible = !camera.visible;
            this.render();
            return camera.visible;
        }
        return false;
    }
    
    /**
     * Update camera parameters (FOV, distance, etc.)
     */
    updateCameraParams(cameraName, params) {
        const camera = this.cameras.get(cameraName);
        if (camera) {
            Object.assign(camera.params, params);
            this.render();
        }
    }
    
    
    /**
     * Get list of all cameras for UI controls
     */
    getCameraList() {
        return Array.from(this.cameras.values()).map(camera => ({
            name: camera.name,
            visible: camera.visible,
            color: camera.color,
            params: camera.params
        }));
    }
    
    /**
     * Cleanup overlay resources
     */
    destroy() {
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
        this.canvas = null;
        this.ctx = null;
        this.cameras.clear();
    }
}

// Make available globally
window.CameraOverlay = CameraOverlay;