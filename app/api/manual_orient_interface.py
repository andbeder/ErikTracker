"""
Manual Camera Orientation Interface
4-quadrant Three.js interface for manual camera pose adjustment
"""

import json
import struct
import logging

logger = logging.getLogger(__name__)

def generate_manual_orient_interface(pose_data, point_cloud_path):
    """Generate 4-quadrant manual camera orientation interface"""
    translation = pose_data['translation']
    transformation_matrix = pose_data['transformation_matrix']
    camera_name = pose_data['camera_name']
    
    # Load 500k points for visualization
    sample_points = load_point_cloud_sample(point_cloud_path, max_points=500000)
    
    # Generate the HTML interface
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manual Camera Orientation - {camera_name}</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 0;
            background-color: #000;
            font-family: Arial, sans-serif;
            overflow: hidden;
        }}
        
        #container {{
            width: 100vw;
            height: 100vh;
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: 1fr 1fr;
            gap: 2px;
        }}
        
        .quadrant {{
            position: relative;
            background: #111;
            border: 1px solid #333;
        }}
        
        .quadrant-label {{
            position: absolute;
            top: 10px;
            left: 10px;
            color: white;
            background: rgba(0,0,0,0.8);
            padding: 5px 10px;
            border-radius: 3px;
            font-size: 12px;
            z-index: 100;
        }}
        
        #camera-selector {{
            position: absolute;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            background: rgba(0,0,0,0.9);
            padding: 10px 15px;
            border-radius: 5px;
            color: white;
            font-size: 14px;
        }}
        
        #camera-selector select {{
            background: #333;
            color: white;
            border: 1px solid #555;
            padding: 5px 10px;
            border-radius: 3px;
            margin-left: 10px;
            font-size: 14px;
        }}
        
        #controls {{
            position: absolute;
            top: 10px;
            right: 10px;
            color: white;
            background: rgba(0,0,0,0.8);
            padding: 10px;
            border-radius: 5px;
            font-size: 12px;
            z-index: 1000;
            max-width: 200px;
        }}
        
        #controls h4 {{
            margin: 0 0 10px 0;
            color: #4CAF50;
        }}
        
        #controls div {{
            margin: 3px 0;
        }}
        
        .key {{
            background: #333;
            padding: 2px 6px;
            border-radius: 2px;
            font-family: monospace;
        }}
        
        #status {{
            position: absolute;
            bottom: 10px;
            left: 10px;
            color: white;
            background: rgba(0,0,0,0.8);
            padding: 5px 10px;
            border-radius: 3px;
            font-size: 11px;
            z-index: 1000;
        }}
    </style>
</head>
<body>
    <div id="camera-selector">
        <label>Camera:</label>
        <select id="cameraSelect">
            <option value="backyard" {"selected" if camera_name == "backyard" else ""}>Backyard</option>
            <option value="side_yard" {"selected" if camera_name == "side_yard" else ""}>Side Yard</option>
            <option value="front_door" {"selected" if camera_name == "front_door" else ""}>Front Door</option>
            <option value="garage" {"selected" if camera_name == "garage" else ""}>Garage</option>
        </select>
    </div>
    
    <div id="container">
        <!-- UL: Top-down orthographic -->
        <div id="topdown" class="quadrant">
            <div class="quadrant-label">📍 Top-Down View (Orthographic)</div>
        </div>
        
        <!-- UR: Side view for elevation placement -->
        <div id="cameraview" class="quadrant">
            <div class="quadrant-label">📐 Side View (Elevation)</div>
        </div>
        
        <!-- LL: Camera perspective view -->
        <div id="cameraperspective" class="quadrant">
            <div class="quadrant-label">📹 Camera View (3D Perspective)</div>
        </div>
        
        <!-- LR: Superimposed live + point cloud -->
        <div id="superimposed" class="quadrant">
            <div class="quadrant-label">🔄 Live + Point Cloud Overlay</div>
        </div>
    </div>
    
    <div id="controls">
        <h4>Camera Controls</h4>
        <div><span class="key">W/S</span> Move Forward/Back</div>
        <div><span class="key">A/D</span> Move Left/Right</div>
        <div><span class="key">Q/E</span> Move Up/Down</div>
        <div><span class="key">↑/↓</span> Tilt Up/Down</div>
        <div><span class="key">←/→</span> Pan Left/Right</div>
        <div><span class="key">Z/X</span> Roll Left/Right</div>
        <div><span class="key">&lt;/&gt;</span> UL View Zoom Out/In</div>
        <div><span class="key">R</span> Reset Camera</div>
    </div>
    
    <div id="status">
        Camera: {camera_name} | Points: {len(sample_points):,} | Ready
    </div>

    <div id="transformation-section" style="margin: 20px; padding: 15px; background: #2a2a2a; border-radius: 8px; color: #fff; font-family: monospace;">
        <h3 style="margin-top: 0; color: #4CAF50;">Camera Transformation Matrix</h3>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
            <div>
                <h4 style="margin: 10px 0 5px 0; color: #FFA726;">Position (X, Y, Z)</h4>
                <div id="position-readout" style="background: #1a1a1a; padding: 8px; border-radius: 4px;">0.000, 0.000, 0.000</div>
            </div>
            <div>
                <h4 style="margin: 10px 0 5px 0; color: #FFA726;">Rotation (X, Y, Z)</h4>
                <div id="rotation-readout" style="background: #1a1a1a; padding: 8px; border-radius: 4px;">0.000, 0.000, 0.000</div>
            </div>
        </div>
        <h4 style="margin: 15px 0 5px 0; color: #FFA726;">4x4 Transformation Matrix</h4>
        <div id="matrix-readout" style="background: #1a1a1a; padding: 10px; border-radius: 4px; font-size: 12px; line-height: 1.4;">
            [1.000, 0.000, 0.000, 0.000]<br>
            [0.000, 1.000, 0.000, 0.000]<br>
            [0.000, 0.000, 1.000, 0.000]<br>
            [0.000, 0.000, 0.000, 1.000]
        </div>
        <div style="margin-top: 10px; display: flex; gap: 10px; align-items: center;">
            <label style="color: #FFA726;">Camera FoV:</label>
            <input type="range" id="fov-slider" min="10" max="180" value="90" style="flex: 1;">
            <span id="fov-value" style="color: #4CAF50; min-width: 40px;">90°</span>
        </div>
        
        <div style="margin-top: 15px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
            <div style="display: flex; gap: 10px;">
                <button id="save-pose-btn" style="background: #4CAF50; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 12px;">Save Manual Position</button>
                <button id="estimate-pose-btn" style="background: #2196F3; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 12px;">Get Initial Estimate</button>
            </div>
            <div id="calibration-status" style="color: #FFA726; font-size: 12px; margin-left: 10px;">
                Status: {pose_data.get('calibration_status', 'unknown')}
            </div>
        </div>
        
        <div id="status-message" style="margin-top: 10px; padding: 8px; border-radius: 4px; font-size: 12px; display: none;"></div>
    </div>

    <script>
        // Global variables
        let scenes = {{}};
        let cameras = {{}};
        let renderers = {{}};
        let pointCloud;
        let cameraHelper;
        let cameraMarker;
        let virtualCamera = {{}};
        
        // Point cloud data
        const pointCloudData = {json.dumps(sample_points)};
        
        // Camera parameters
        const initialPose = {{
            position: {translation},
            rotation: {transformation_matrix}
        }};
        
        // Initialize virtual camera from COLMAP pose  
        // Use normal coordinates to match point cloud
        const pos = initialPose.position;
        virtualCamera.position = new THREE.Vector3(pos[0], pos[1], pos[2]);
        virtualCamera.fov = 90;
        virtualCamera.aspect = 16/9;
        virtualCamera.near = 0.1;
        virtualCamera.far = 100;
        
        // Movement parameters
        let moveSpeed = 0.1;
        let rotateSpeed = 0.02;
        const baseMoveSpeed = 0.1;
        const baseRotateSpeed = 0.02;
        
        // Keyboard state
        const keys = {{}};
        
        function calculatePointCloudBounds(data) {{
            // Extract coordinates
            const xCoords = data.map(point => point[0]).sort((a, b) => a - b);
            const yCoords = data.map(point => point[1]).sort((a, b) => a - b);
            const zCoords = data.map(point => point[2]).sort((a, b) => a - b);
            
            // Calculate 2% and 98% percentiles
            const p2Index = Math.floor(data.length * 0.02);
            const p98Index = Math.floor(data.length * 0.98) - 1;
            
            const bounds = {{
                minX: xCoords[p2Index],
                maxX: xCoords[p98Index],
                minY: yCoords[p2Index],
                maxY: yCoords[p98Index],
                minZ: zCoords[p2Index],
                maxZ: zCoords[p98Index]
            }};
            
            console.log('Point cloud bounds (2%-98% percentiles):', bounds);
            console.log('X range:', bounds.maxX - bounds.minX);
            console.log('Y range:', bounds.maxY - bounds.minY);
            console.log('Z range:', bounds.maxZ - bounds.minZ);
            
            return bounds;
        }}
        
        function init() {{
            initTopDownView();
            initSideView();
            initCameraPerspectiveView();
            initSuperimposedView();
            initOverlayFeedRefresh();
            
            setupKeyboardControls();
            setupCameraSelection();
            setupFoVControl();
            setupButtonHandlers();
            updateTransformationMatrix();
            animate();
            
            console.log('Manual orientation interface initialized');
            console.log('Virtual camera position:', virtualCamera.position);
            console.log('Point cloud loaded:', pointCloudData.length, 'points');
        }}
        
        function initTopDownView() {{
            const container = document.getElementById('topdown');
            
            // Scene
            scenes.topdown = new THREE.Scene();
            scenes.topdown.background = new THREE.Color(0x222222);
            
            // Calculate automatic bounds based on point cloud data
            const bounds = calculatePointCloudBounds(pointCloudData);
            console.log('Calculated bounds:', bounds);
            
            // Set orthographic camera bounds to 2%-98% percentiles
            const sizeX = (bounds.maxX - bounds.minX) / 2;
            const sizeZ = (bounds.maxZ - bounds.minZ) / 2;
            const maxSize = Math.max(sizeX, sizeZ) * 1.1; // 10% padding
            
            cameras.topdown = new THREE.OrthographicCamera(
                -maxSize, maxSize, maxSize, -maxSize, 0.1, 1000
            );
            
            // Position camera above the center of the point cloud
            const centerX = (bounds.minX + bounds.maxX) / 2;
            const centerZ = (bounds.minZ + bounds.maxZ) / 2;
            const cameraY = bounds.maxY + 10; // 10 units above highest point
            
            cameras.topdown.position.set(centerX, cameraY, centerZ);
            cameras.topdown.lookAt(centerX, 0, centerZ); // Look down Y-axis toward <0, -1, 0>
            
            // Renderer
            renderers.topdown = new THREE.WebGLRenderer({{ antialias: true }});
            renderers.topdown.setSize(container.offsetWidth, container.offsetHeight);
            container.appendChild(renderers.topdown.domElement);
            
            // Create point cloud
            const geometry = createPointCloudGeometry();
            const material = new THREE.PointsMaterial({{ 
                size: 0.1,  // Increased size
                vertexColors: true,
                sizeAttenuation: false
            }});
            pointCloud = new THREE.Points(geometry, material);
            scenes.topdown.add(pointCloud);
            
            // Add camera frustum helper
            updateCameraHelper();
        }}
        
        function initOverlayFeedRefresh() {{
            // Initialize and refresh overlay live image in LR quadrant
            loadOverlayFeed();
            
            // Refresh every 5 seconds
            setInterval(() => {{
                const overlayImg = document.querySelector('#overlayLiveImage');
                const timestamp = Date.now();
                
                // Update overlay live image in LR quadrant
                if (overlayImg) {{
                    overlayImg.src = `/api/{camera_name}/latest.jpg?timestamp=${{timestamp}}`;
                }}
            }}, 5000);
        }}
        
        function loadOverlayFeed() {{
            const overlayImg = document.querySelector('#overlayLiveImage');
            if (overlayImg) {{
                const cameraName = '{camera_name}';
                const timestamp = Date.now();
                overlayImg.src = `/api/${{cameraName}}/latest.jpg?timestamp=${{timestamp}}`;
                overlayImg.onerror = function() {{
                    console.warn('Failed to load overlay camera feed for', cameraName);
                }};
            }}
        }}
        
        function initSideView() {{
            const container = document.getElementById('cameraview');
            
            // Scene
            scenes.cameraview = new THREE.Scene();
            scenes.cameraview.background = new THREE.Color(0x222222);
            
            // Calculate bounds for side view (similar to top-down)
            const bounds = calculatePointCloudBounds(pointCloudData);
            console.log('Side view bounds:', bounds);
            
            // Set orthographic camera bounds for side view (looking from side)
            const sizeY = (bounds.maxY - bounds.minY) / 2;
            const sizeZ = (bounds.maxZ - bounds.minZ) / 2;
            const maxSize = Math.max(sizeY, sizeZ) * 1.1; // 10% padding
            
            cameras.cameraview = new THREE.OrthographicCamera(
                -maxSize, maxSize, maxSize, -maxSize, 0.1, 1000
            );
            
            // Position camera to the side (looking along X-axis)
            const centerY = (bounds.minY + bounds.maxY) / 2;
            const centerZ = (bounds.minZ + bounds.maxZ) / 2;
            const cameraX = bounds.minX - 10; // 10 units to the left of the scene
            
            cameras.cameraview.position.set(cameraX, centerY, centerZ);
            cameras.cameraview.lookAt(bounds.maxX, centerY, centerZ); // Look toward positive X (into the scene)
            
            // Renderer
            renderers.cameraview = new THREE.WebGLRenderer({{ antialias: true }});
            renderers.cameraview.setSize(container.offsetWidth, container.offsetHeight);
            container.appendChild(renderers.cameraview.domElement);
            
            // Add point cloud
            const geometry = createPointCloudGeometry();
            const material = new THREE.PointsMaterial({{ 
                size: 0.1,  // Increased size for side view
                vertexColors: true,
                sizeAttenuation: false
            }});
            const cameraPointCloud = new THREE.Points(geometry, material);
            scenes.cameraview.add(cameraPointCloud);
            
            // Add camera helper for side view as well
            updateSideViewCameraHelper();
        }}
        
        function initCameraPerspectiveView() {{
            const container = document.getElementById('cameraperspective');
            
            // Scene
            scenes.cameraperspective = new THREE.Scene();
            scenes.cameraperspective.background = new THREE.Color(0x1a1a1a);
            
            // Create perspective camera that matches virtual camera
            cameras.cameraperspective = new THREE.PerspectiveCamera(
                virtualCamera.fov, 
                virtualCamera.aspect, 
                virtualCamera.near, 
                virtualCamera.far
            );
            
            // Position camera to match virtual camera
            cameras.cameraperspective.position.copy(virtualCamera.position);
            cameras.cameraperspective.rotation.copy(virtualCamera.rotation || new THREE.Euler());
            
            // Renderer
            renderers.cameraperspective = new THREE.WebGLRenderer({{ antialias: true }});
            renderers.cameraperspective.setSize(container.offsetWidth, container.offsetHeight);
            container.appendChild(renderers.cameraperspective.domElement);
            
            // Add point cloud to camera perspective view
            const geometry = createPointCloudGeometry();
            const material = new THREE.PointsMaterial({{ 
                size: 0.01,
                vertexColors: true,
                sizeAttenuation: true
            }});
            const cameraPointCloud = new THREE.Points(geometry, material);
            scenes.cameraperspective.add(cameraPointCloud);
            
            // Add lighting for better visibility
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
            scenes.cameraperspective.add(ambientLight);
            const directionalLight = new THREE.DirectionalLight(0xffffff, 0.4);
            directionalLight.position.set(5, 5, 5);
            scenes.cameraperspective.add(directionalLight);
        }}
        
        function initSuperimposedView() {{
            const container = document.getElementById('superimposed');
            
            // Add background live image
            const overlayImage = document.createElement('img');
            overlayImage.id = 'overlayLiveImage';
            overlayImage.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                object-fit: contain;
                z-index: 1;
            `;
            overlayImage.alt = 'Overlay live camera feed';
            container.appendChild(overlayImage);
            
            // Create Three.js scene with transparent background
            scenes.superimposed = new THREE.Scene();
            // Remove background color to allow transparency
            
            cameras.superimposed = new THREE.PerspectiveCamera(
                virtualCamera.fov, 
                virtualCamera.aspect, 
                virtualCamera.near, 
                virtualCamera.far
            );
            
            renderers.superimposed = new THREE.WebGLRenderer({{ 
                antialias: true,
                alpha: true 
            }});
            renderers.superimposed.setClearColor(0x000000, 0); // Transparent background
            renderers.superimposed.setSize(container.offsetWidth, container.offsetHeight);
            renderers.superimposed.domElement.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                z-index: 2;
                pointer-events: none;
            `;
            container.appendChild(renderers.superimposed.domElement);
            
            // Add semi-transparent point cloud
            const geometry = createPointCloudGeometry();
            const material = new THREE.PointsMaterial({{ 
                size: 0.01,
                vertexColors: true,
                sizeAttenuation: true,
                opacity: 0.7,
                transparent: true
            }});
            const overlayPointCloud = new THREE.Points(geometry, material);
            scenes.superimposed.add(overlayPointCloud);
        }}
        
        function createPointCloudGeometry() {{
            const geometry = new THREE.BufferGeometry();
            const positions = [];
            const colors = [];
            
            console.log('Creating point cloud geometry with', pointCloudData.length, 'points');
            
            for (const point of pointCloudData) {{
                // Use normal X and Z axes (no inversion to prevent mirroring)
                positions.push(point[0], point[1], point[2]);
                colors.push(point[3]/255, point[4]/255, point[5]/255);
            }}
            
            console.log('Point cloud positions:', positions.length / 3, 'points');
            console.log('Sample point:', positions[0], positions[1], positions[2]);
            
            geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
            geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
            
            // Compute bounding box to see the scale
            geometry.computeBoundingBox();
            console.log('Point cloud bounding box:', geometry.boundingBox);
            
            return geometry;
        }}
        
        function updateCameraHelper() {{
            // Remove old camera helper and marker
            if (cameraHelper) {{
                scenes.topdown.remove(cameraHelper);
            }}
            if (cameraMarker) {{
                scenes.topdown.remove(cameraMarker);
            }}
            
            // Create a perspective camera for the helper
            const helperCamera = new THREE.PerspectiveCamera(
                virtualCamera.fov,
                virtualCamera.aspect,
                virtualCamera.near,
                virtualCamera.far
            );
            helperCamera.position.copy(virtualCamera.position);
            helperCamera.rotation.copy(virtualCamera.rotation || new THREE.Euler());
            
            cameraHelper = new THREE.CameraHelper(helperCamera);
            cameraHelper.material.color.setHex(0x00ff00);
            scenes.topdown.add(cameraHelper);
            
            // Add camera position marker
            const markerGeometry = new THREE.SphereGeometry(0.1, 8, 8);
            const markerMaterial = new THREE.MeshBasicMaterial({{ color: 0xff0000 }});
            cameraMarker = new THREE.Mesh(markerGeometry, markerMaterial);
            cameraMarker.position.copy(virtualCamera.position);
            scenes.topdown.add(cameraMarker);
        }}
        
        function updateCameraViewPose() {{
            // Update camera perspective view to match virtual camera
            if (cameras.cameraperspective) {{
                cameras.cameraperspective.position.copy(virtualCamera.position);
                cameras.cameraperspective.rotation.copy(virtualCamera.rotation || new THREE.Euler());
            }}
            
            if (cameras.superimposed) {{
                cameras.superimposed.position.copy(virtualCamera.position);
                cameras.superimposed.rotation.copy(virtualCamera.rotation || new THREE.Euler());
            }}
        }}
        
        function setupKeyboardControls() {{
            document.addEventListener('keydown', (event) => {{
                keys[event.code] = true;
                event.preventDefault();
            }});
            
            document.addEventListener('keyup', (event) => {{
                keys[event.code] = false;
                event.preventDefault();
            }});
        }}
        
        function setupCameraSelection() {{
            const cameraSelect = document.getElementById('cameraSelect');
            cameraSelect.addEventListener('change', (event) => {{
                const selectedCamera = event.target.value;
                // Redirect to the selected camera's interface
                window.location.href = `/api/orient/visualization/${{selectedCamera}}`;
            }});
        }}
        
        function handleInput() {{
            let updated = false;
            
            // Movement (WASDQE) - relative to camera orientation
            if (!virtualCamera.rotation) {{
                virtualCamera.rotation = new THREE.Euler();
            }}
            
            // Create direction vectors based on camera rotation
            const direction = new THREE.Vector3();
            const right = new THREE.Vector3();
            const up = new THREE.Vector3(0, 1, 0);
            
            // Calculate forward direction from camera rotation
            direction.set(0, 0, -1);
            direction.applyEuler(virtualCamera.rotation);
            
            // Calculate right direction (cross product of up and forward)
            right.crossVectors(up, direction).normalize();
            
            if (keys['KeyW']) {{ // Forward (in camera's forward direction)
                virtualCamera.position.addScaledVector(direction, moveSpeed);
                updated = true;
            }}
            if (keys['KeyS']) {{ // Back (opposite of camera's forward direction)
                virtualCamera.position.addScaledVector(direction, -moveSpeed);
                updated = true;
            }}
            if (keys['KeyA']) {{ // Left (in camera's left direction)
                virtualCamera.position.addScaledVector(right, -moveSpeed);
                updated = true;
            }}
            if (keys['KeyD']) {{ // Right (in camera's right direction)
                virtualCamera.position.addScaledVector(right, moveSpeed);
                updated = true;
            }}
            if (keys['KeyQ']) {{ // Up (world up)
                virtualCamera.position.y += moveSpeed;
                updated = true;
            }}
            if (keys['KeyE']) {{ // Down (world down)
                virtualCamera.position.y -= moveSpeed;
                updated = true;
            }}
            
            // Rotation (Arrow keys + Z/X)
            if (!virtualCamera.rotation) {{
                virtualCamera.rotation = new THREE.Euler();
            }}
            
            if (keys['ArrowUp']) {{ // Tilt up
                virtualCamera.rotation.x -= rotateSpeed;
                updated = true;
            }}
            if (keys['ArrowDown']) {{ // Tilt down
                virtualCamera.rotation.x += rotateSpeed;
                updated = true;
            }}
            if (keys['ArrowLeft']) {{ // Pan left
                virtualCamera.rotation.y += rotateSpeed;
                updated = true;
            }}
            if (keys['ArrowRight']) {{ // Pan right
                virtualCamera.rotation.y -= rotateSpeed;
                updated = true;
            }}
            if (keys['KeyZ']) {{ // Roll left
                virtualCamera.rotation.z += rotateSpeed;
                updated = true;
            }}
            if (keys['KeyX']) {{ // Roll right
                virtualCamera.rotation.z -= rotateSpeed;
                updated = true;
            }}
            
            // Speed controls
            if (keys['Equal'] || keys['NumpadAdd']) {{ // + key (increase speed)
                moveSpeed = Math.min(moveSpeed * 1.5, baseMoveSpeed * 10);
                rotateSpeed = Math.min(rotateSpeed * 1.5, baseRotateSpeed * 10);
                keys['Equal'] = false;
                keys['NumpadAdd'] = false;
            }}
            if (keys['Minus'] || keys['NumpadSubtract']) {{ // - key (decrease speed)
                moveSpeed = Math.max(moveSpeed / 1.5, baseMoveSpeed * 0.00025);
                rotateSpeed = Math.max(rotateSpeed / 1.5, baseRotateSpeed * 0.00025);
                keys['Minus'] = false;
                keys['NumpadSubtract'] = false;
            }}
            
            // UL view zoom controls (< and > keys)
            if (keys['Comma']) {{ // < key (zoom out UL view)
                if (cameras.topdown && cameras.topdown.isOrthographicCamera) {{
                    const currentSize = Math.abs(cameras.topdown.left);
                    const newSize = Math.min(currentSize * 1.1, 50); // Max zoom out
                    cameras.topdown.left = -newSize;
                    cameras.topdown.right = newSize;
                    cameras.topdown.top = newSize;
                    cameras.topdown.bottom = -newSize;
                    cameras.topdown.updateProjectionMatrix();
                    updated = true;
                }}
                keys['Comma'] = false;
            }}
            if (keys['Period']) {{ // > key (zoom in UL view)
                if (cameras.topdown && cameras.topdown.isOrthographicCamera) {{
                    const currentSize = Math.abs(cameras.topdown.left);
                    const newSize = Math.max(currentSize * 0.9, 0.5); // Min zoom in
                    cameras.topdown.left = -newSize;
                    cameras.topdown.right = newSize;
                    cameras.topdown.top = newSize;
                    cameras.topdown.bottom = -newSize;
                    cameras.topdown.updateProjectionMatrix();
                    updated = true;
                }}
                keys['Period'] = false;
            }}
            
            // Reset
            if (keys['KeyR']) {{
                const pos = initialPose.position;
                virtualCamera.position.copy(new THREE.Vector3(pos[0], pos[1], pos[2]));
                virtualCamera.rotation = new THREE.Euler();
                updated = true;
                keys['KeyR'] = false; // Prevent continuous reset
            }}
            
            if (updated) {{
                updateCameraHelper();
                updateSideViewCameraHelper();
                updateTopDownTracking();
                updateStatus();
                updateTransformationMatrix();
            }}
        }}
        
        function updateTopDownTracking() {{
            // Update top-down camera to track virtual camera position
            if (cameras.topdown) {{
                const targetX = virtualCamera.position.x;
                const targetZ = virtualCamera.position.z;
                const cameraY = cameras.topdown.position.y; // Keep same height
                
                cameras.topdown.position.set(targetX, cameraY, targetZ);
                cameras.topdown.lookAt(targetX, 0, targetZ); // Look down at tracked position
            }}
        }}

        function updateSideViewCameraHelper() {{
            // Add camera helper to side view for elevation placement
            if (scenes.cameraview && virtualCamera) {{
                // Remove old camera helper from side view if it exists
                const existingHelper = scenes.cameraview.getObjectByName('sideViewCameraHelper');
                if (existingHelper) {{
                    scenes.cameraview.remove(existingHelper);
                }}
                
                // Create a perspective camera for the helper (same as top-down)
                const helperCamera = new THREE.PerspectiveCamera(
                    virtualCamera.fov,
                    virtualCamera.aspect,
                    virtualCamera.near,
                    virtualCamera.far
                );
                helperCamera.position.copy(virtualCamera.position);
                helperCamera.rotation.copy(virtualCamera.rotation || new THREE.Euler());
                
                const sideViewCameraHelper = new THREE.CameraHelper(helperCamera);
                sideViewCameraHelper.material.color.setHex(0x00ff00);
                sideViewCameraHelper.name = 'sideViewCameraHelper';
                scenes.cameraview.add(sideViewCameraHelper);
                
                // Add camera position marker for side view
                const existingMarker = scenes.cameraview.getObjectByName('sideViewCameraMarker');
                if (existingMarker) {{
                    scenes.cameraview.remove(existingMarker);
                }}
                
                const markerGeometry = new THREE.SphereGeometry(0.1, 8, 8);
                const markerMaterial = new THREE.MeshBasicMaterial({{ color: 0xff0000 }});
                const sideViewCameraMarker = new THREE.Mesh(markerGeometry, markerMaterial);
                sideViewCameraMarker.position.copy(virtualCamera.position);
                sideViewCameraMarker.name = 'sideViewCameraMarker';
                scenes.cameraview.add(sideViewCameraMarker);
            }}
        }}

        function updateStatus() {{
            const status = document.getElementById('status');
            const pos = virtualCamera.position;
            const rot = virtualCamera.rotation;
            status.textContent = `Camera: {camera_name} | Points: {len(sample_points):,} | ` +
                `Pos: (${{pos.x.toFixed(2)}}, ${{pos.y.toFixed(2)}}, ${{pos.z.toFixed(2)}}) | ` +
                `Rot: (${{(rot.x * 180/Math.PI).toFixed(1)}}°, ${{(rot.y * 180/Math.PI).toFixed(1)}}°, ${{(rot.z * 180/Math.PI).toFixed(1)}}°)`;
        }}
        
        function animate() {{
            requestAnimationFrame(animate);
            
            handleInput();
            
            // Render all views
            if (renderers.topdown) {{
                renderers.topdown.render(scenes.topdown, cameras.topdown);
            }}
            if (renderers.cameraview) {{
                renderers.cameraview.render(scenes.cameraview, cameras.cameraview);
            }}
            if (renderers.cameraperspective) {{
                renderers.cameraperspective.render(scenes.cameraperspective, cameras.cameraperspective);
            }}
            if (renderers.superimposed) {{
                renderers.superimposed.render(scenes.superimposed, cameras.superimposed);
            }}
        }}
        
        function updateTransformationMatrix() {{
            // Update position readout
            const posReadout = document.getElementById('position-readout');
            if (posReadout) {{
                posReadout.textContent = `${{virtualCamera.position.x.toFixed(3)}}, ${{virtualCamera.position.y.toFixed(3)}}, ${{virtualCamera.position.z.toFixed(3)}}`;
            }}
            
            // Update rotation readout
            const rotReadout = document.getElementById('rotation-readout');
            if (rotReadout && virtualCamera.rotation) {{
                rotReadout.textContent = `${{virtualCamera.rotation.x.toFixed(3)}}, ${{virtualCamera.rotation.y.toFixed(3)}}, ${{virtualCamera.rotation.z.toFixed(3)}}`;
            }}
            
            // Create 4x4 transformation matrix
            const matrix = new THREE.Matrix4();
            matrix.compose(
                virtualCamera.position,
                new THREE.Quaternion().setFromEuler(virtualCamera.rotation || new THREE.Euler()),
                new THREE.Vector3(1, 1, 1)
            );
            
            // Update matrix readout
            const matrixReadout = document.getElementById('matrix-readout');
            if (matrixReadout) {{
                const m = matrix.elements;
                matrixReadout.innerHTML = `
                    [${{m[0].toFixed(3)}}, ${{m[4].toFixed(3)}}, ${{m[8].toFixed(3)}}, ${{m[12].toFixed(3)}}]<br>
                    [${{m[1].toFixed(3)}}, ${{m[5].toFixed(3)}}, ${{m[9].toFixed(3)}}, ${{m[13].toFixed(3)}}]<br>
                    [${{m[2].toFixed(3)}}, ${{m[6].toFixed(3)}}, ${{m[10].toFixed(3)}}, ${{m[14].toFixed(3)}}]<br>
                    [${{m[3].toFixed(3)}}, ${{m[7].toFixed(3)}}, ${{m[11].toFixed(3)}}, ${{m[15].toFixed(3)}}]
                `;
            }}
        }}
        
        function setupFoVControl() {{
            const fovSlider = document.getElementById('fov-slider');
            const fovValue = document.getElementById('fov-value');
            
            if (fovSlider && fovValue) {{
                fovSlider.addEventListener('input', function() {{
                    virtualCamera.fov = parseFloat(this.value);
                    fovValue.textContent = this.value + '°';
                    
                    // Update camera perspective view
                    if (cameras.cameraperspective) {{
                        cameras.cameraperspective.fov = virtualCamera.fov;
                        cameras.cameraperspective.updateProjectionMatrix();
                    }}
                    
                    // Update superimposed view
                    if (cameras.superimposed) {{
                        cameras.superimposed.fov = virtualCamera.fov;
                        cameras.superimposed.updateProjectionMatrix();
                    }}
                    
                    // Update camera helper with new FoV
                    updateCameraHelper();
                }});
                
                // Set initial value
                fovSlider.value = virtualCamera.fov;
                fovValue.textContent = virtualCamera.fov + '°';
            }}
        }}
        
        // Button event handlers
        function setupButtonHandlers() {{
            // Save pose button
            const savePoseBtn = document.getElementById('save-pose-btn');
            if (savePoseBtn) {{
                savePoseBtn.addEventListener('click', async () => {{
                    try {{
                        savePoseBtn.disabled = true;
                        savePoseBtn.textContent = 'Saving...';
                        
                        // Get current camera transformation matrix and position
                        const transformationMatrix = getTransformationMatrix();
                        const translation = [virtualCamera.position.x, virtualCamera.position.y, virtualCamera.position.z];
                        
                        const response = await fetch('/api/orient/save-camera-pose', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify({{
                                camera_name: '{camera_name}',
                                transformation_matrix: transformationMatrix,
                                translation: translation
                            }})
                        }});
                        
                        const result = await response.json();
                        
                        if (result.success) {{
                            showStatusMessage('Manual position saved successfully!', 'success');
                            document.getElementById('calibration-status').textContent = 'Status: manual';
                        }} else {{
                            showStatusMessage('Error saving position: ' + (result.error || 'Unknown error'), 'error');
                        }}
                    }} catch (error) {{
                        showStatusMessage('Error saving position: ' + error.message, 'error');
                    }} finally {{
                        savePoseBtn.disabled = false;
                        savePoseBtn.textContent = 'Save Manual Position';
                    }}
                }});
            }}
            
            // Get initial estimate button
            const estimatePoseBtn = document.getElementById('estimate-pose-btn');
            if (estimatePoseBtn) {{
                estimatePoseBtn.addEventListener('click', async () => {{
                    try {{
                        estimatePoseBtn.disabled = true;
                        estimatePoseBtn.textContent = 'Estimating...';
                        
                        const response = await fetch('/api/orient/estimate-camera-pose', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify({{
                                camera_name: '{camera_name}'
                            }})
                        }});
                        
                        const result = await response.json();
                        
                        if (result.success) {{
                            showStatusMessage('Initial pose estimated! Position updated.', 'success');
                            // Update camera position based on the estimated pose
                            if (result.translation) {{
                                virtualCamera.position.set(result.translation[0], result.translation[1], result.translation[2]);
                                updateTransformationReadout();
                            }}
                            document.getElementById('calibration-status').textContent = 'Status: estimated';
                        }} else {{
                            showStatusMessage('Error estimating pose: ' + (result.error || 'Unknown error'), 'error');
                        }}
                    }} catch (error) {{
                        showStatusMessage('Error estimating pose: ' + error.message, 'error');
                    }} finally {{
                        estimatePoseBtn.disabled = false;
                        estimatePoseBtn.textContent = 'Get Initial Estimate';
                    }}
                }});
            }}
        }}
        
        function showStatusMessage(message, type) {{
            const statusMessage = document.getElementById('status-message');
            if (statusMessage) {{
                statusMessage.textContent = message;
                statusMessage.style.display = 'block';
                statusMessage.style.background = type === 'success' ? '#4CAF50' : '#f44336';
                statusMessage.style.color = 'white';
                
                // Hide after 3 seconds
                setTimeout(() => {{
                    statusMessage.style.display = 'none';
                }}, 3000);
            }}
        }}
        
        function getTransformationMatrix() {{
            // Build transformation matrix from current camera position and rotation
            const position = virtualCamera.position;
            const quaternion = virtualCamera.quaternion;
            
            // Create a 4x4 transformation matrix (world-to-camera)
            const matrix = new THREE.Matrix4();
            matrix.compose(position, quaternion, new THREE.Vector3(1, 1, 1));
            
            // Convert to nested array format
            const elements = matrix.elements;
            return [
                [elements[0], elements[4], elements[8], elements[12]],
                [elements[1], elements[5], elements[9], elements[13]],
                [elements[2], elements[6], elements[10], elements[14]],
                [elements[3], elements[7], elements[11], elements[15]]
            ];
        }}
        
        // Handle window resize
        window.addEventListener('resize', () => {{
            Object.keys(renderers).forEach(key => {{
                const container = document.getElementById(key);
                if (container && renderers[key]) {{
                    renderers[key].setSize(container.offsetWidth, container.offsetHeight);
                    if (cameras[key] && cameras[key].isPerspectiveCamera) {{
                        cameras[key].aspect = container.offsetWidth / container.offsetHeight;
                        cameras[key].updateProjectionMatrix();
                    }}
                }}
            }});
        }});
        
        // Initialize when page loads
        window.addEventListener('load', init);
    </script>
</body>
</html>
"""
    
    return html_content

def load_point_cloud_sample(point_cloud_path, max_points=500000):
    """Load a sample of points from PLY file"""
    sample_points = []
    try:
        import struct
        
        with open(point_cloud_path, 'rb') as f:
            # Read header
            header_lines = []
            while True:
                line = f.readline().decode('ascii').strip()
                header_lines.append(line)
                if line == 'end_header':
                    break
            
            # Parse header
            total_points = 0
            is_binary = False
            for line in header_lines:
                if line.startswith('element vertex'):
                    total_points = int(line.split()[-1])
                elif 'binary_little_endian' in line:
                    is_binary = True
            
            if not is_binary:
                logger.warning("PLY file is not in binary format, using dummy points")
                return [[0, 0, 0, 128, 128, 128] for _ in range(100)]
            
            # Sample points
            sample_rate = max(1, total_points // max_points)
            vertex_size = 27  # 6 floats + 3 uchars
            header_end_pos = f.tell()
            
            for i in range(0, total_points, sample_rate):
                if len(sample_points) >= max_points:
                    break
                
                f.seek(header_end_pos + i * vertex_size)
                vertex_data = f.read(vertex_size)
                if len(vertex_data) < vertex_size:
                    break
                
                x, y, z, nx, ny, nz, r, g, b = struct.unpack('<ffffffBBB', vertex_data)
                # Flip Y-axis to correct orientation
                sample_points.append([x, -y, z, r, g, b])
        
        logger.info(f"Successfully loaded {len(sample_points)} sample points from PLY file")
        
    except Exception as e:
        logger.warning(f"Could not read point cloud: {e}")
        # Generate dummy points
        sample_points = [[0, 0, 0, 128, 128, 128] for _ in range(100)]
    
    return sample_points