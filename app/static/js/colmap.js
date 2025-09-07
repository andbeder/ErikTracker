/**
 * COLMAP Module for Erik Image Manager
 * Handles 3D reconstruction, camera pose estimation, and related functionality
 */

class ColmapManager {
    constructor(apiClient, progressTracker) {
        this.api = apiClient;
        this.progressTracker = progressTracker;
        this.selectedCamera = '';
        this.processingState = {
            frameExtraction: false,
            featureExtraction: false,
            sparseReconstruction: false,
            denseReconstruction: false
        };
        this.uploadedVideos = [];
        this.currentProgressSession = null;
        this.progressUpdateInterval = null;
        this.currentProjectDir = '/home/andrew/nvr/colmap_projects/current_reconstruction';
        
        this.initializeEventListeners();
        this.initializeFrameStatus();
        this.checkForExistingModels();
    }

    /**
     * Initialize event listeners
     */
    initializeEventListeners() {
        // ESC key to close modal
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                Utils.closeModal();
            }
        });
    }

    /**
     * Load state from localStorage
     */
    loadState() {
        try {
            const savedState = localStorage.getItem('reconstructState');
            if (savedState) {
                this.processingState = { ...this.processingState, ...JSON.parse(savedState) };
            }
            
            // Check for active progress session
            const activeSession = localStorage.getItem('activeProgressSession');
            const activePhase = localStorage.getItem('activeProgressPhase');
            
            if (activeSession && activePhase) {
                console.log(`Resuming progress tracking for ${activePhase} session: ${activeSession}`);
                this.currentProgressSession = activeSession;
                this.currentPhase = activePhase;
                this.resumeProgressTracking();
            }
        } catch (error) {
            console.error('Error loading reconstruction state:', error);
        }
    }

    /**
     * Save state to localStorage
     */
    saveState() {
        try {
            localStorage.setItem('reconstructState', JSON.stringify(this.processingState));
        } catch (error) {
            console.error('Error saving reconstruction state:', error);
        }
    }

    /**
     * Update processing states based on current workflow
     */
    async updateProcessingStates() {
        // First check if point cloud is already available
        const hasPointCloud = await this.checkPointCloudAvailable();
        
        if (hasPointCloud) {
            // Point cloud exists, mark everything as complete
            this.processingState.frameExtraction = true;
            this.processingState.featureExtraction = true;
            this.processingState.sparseReconstruction = true;
            this.processingState.denseReconstruction = true;
            
            // Update the enable point cloud button
            const enablePointCloudBtn = document.getElementById('enablePointCloudBtn');
            if (enablePointCloudBtn) {
                enablePointCloudBtn.textContent = '✅ Point Cloud Available';
                enablePointCloudBtn.disabled = true;
            }
            
            // Hide the "Checking Reconstruction Status" message and show complete status
            const statusChecking = document.getElementById('statusChecking');
            const statusIncomplete = document.getElementById('statusIncomplete');
            const statusComplete = document.getElementById('statusComplete');
            
            if (statusChecking) statusChecking.style.display = 'none';
            if (statusIncomplete) statusIncomplete.style.display = 'none';
            if (statusComplete) statusComplete.style.display = 'block';
        } else {
            // Point cloud not available, show incomplete status
            const statusChecking = document.getElementById('statusChecking');
            const statusIncomplete = document.getElementById('statusIncomplete');
            const statusComplete = document.getElementById('statusComplete');
            
            if (statusChecking) statusChecking.style.display = 'none';
            if (statusIncomplete) statusIncomplete.style.display = 'block';
            if (statusComplete) statusComplete.style.display = 'none';
        }
        
        // Update workflow button states
        this.updateWorkflowButtons();
        
        // Update status indicators
        Utils.safeElementOperation('frameStatus', el => el.textContent = this.processingState.frameExtraction ? '✅' : '❌');
        Utils.safeElementOperation('featureStatus', el => el.textContent = this.processingState.featureExtraction ? '✅' : '❌');
        Utils.safeElementOperation('sparseStatus', el => el.textContent = this.processingState.sparseReconstruction ? '✅' : '❌');
        Utils.safeElementOperation('denseStatus', el => el.textContent = this.processingState.denseReconstruction ? '✅' : '❌');
    }

    /**
     * Update workflow buttons based on current state
     */
    updateWorkflowButtons() {
        const hasVideos = this.uploadedVideos.length > 0;
        
        const buttons = {
            'extractFramesBtn': hasVideos && !this.processingState.frameExtraction,
            'featureExtractionBtn': this.processingState.frameExtraction && !this.processingState.featureExtraction,
            'sparseReconstructionBtn': this.processingState.featureExtraction && !this.processingState.sparseReconstruction,
            'denseReconstructionBtn': this.processingState.sparseReconstruction && !this.processingState.denseReconstruction
        };

        Object.entries(buttons).forEach(([buttonId, enabled]) => {
            Utils.safeElementOperation(buttonId, el => el.disabled = !enabled);
        });
    }

    /**
     * Update processing status display
     * @param {string} statusId - Status element ID
     * @param {string} message - Status message
     * @param {string} type - Status type (success, error, info)
     */
    updateProcessingStatus(statusId, message, type) {
        Utils.safeElementOperation(statusId, el => {
            el.textContent = message;
            el.className = `status-text status-${type}`;
        });
    }

    /**
     * Camera selection for pose estimation
     */
    selectCamera() {
        console.log('selectCamera() called');
        const cameraSelect = document.getElementById('cameraSelect');
        const orientBtn = document.getElementById('orientCameraBtn');
        const preview = document.getElementById('cameraPosePreview');
        
        console.log('Elements found:', {cameraSelect, orientBtn, preview});
        
        if (!cameraSelect) {
            console.log('cameraSelect element not found');
            return;
        }
        
        this.selectedCamera = cameraSelect.value;
        console.log('Selected camera:', this.selectedCamera);
        
        if (this.selectedCamera && orientBtn && preview) {
            console.log('Updating camera preview for:', this.selectedCamera);
            
            // Enable orient button
            orientBtn.disabled = false;
            
            // Update preview with live camera feed
            const snapshotUrl = this.api.getCameraSnapshot(this.selectedCamera);
            console.log('Snapshot URL:', snapshotUrl);
            
            preview.innerHTML = `
                <img id="cameraPreviewImg" src="${snapshotUrl}" 
                     style="width: 100%; height: 240px; border: none; border-radius: 8px; object-fit: cover;" 
                     alt="${this.selectedCamera} camera"
                     onload="console.log('Camera image loaded successfully')"
                     onerror="console.log('Camera image failed to load')">
            `;
            
            // Set up auto-refresh for the preview
            this.setupCameraPreviewRefresh();
            
            // Update status
            Utils.safeElementOperation('poseStatusText', el => {
                el.textContent = `Camera "${this.selectedCamera.replace('_', ' ').toUpperCase()}" selected. Ready to orient.`;
            });
                
            // Reset processing steps
            Utils.resetProcessingSteps();
        } else {
            console.log('Camera not selected or elements missing');
            if (orientBtn) orientBtn.disabled = true;
            if (preview) preview.innerHTML = 'Select a camera to see live preview';
            
            Utils.safeElementOperation('poseStatusText', el => {
                el.textContent = 'Select camera and click "Orient Camera" to estimate pose using COLMAP';
            });
            
            Utils.resetProcessingSteps();
            this.clearPreviewRefresh();
        }
    }

    /**
     * Set up camera preview auto-refresh
     */
    setupCameraPreviewRefresh() {
        this.clearPreviewRefresh();
        
        const previewImg = document.getElementById('cameraPreviewImg');
        if (previewImg && this.selectedCamera) {
            window.previewRefreshInterval = setInterval(() => {
                const snapshotUrl = this.api.getCameraSnapshot(this.selectedCamera);
                previewImg.src = snapshotUrl;
            }, 1000);
        }
    }

    /**
     * Clear camera preview refresh interval
     */
    clearPreviewRefresh() {
        if (window.previewRefreshInterval) {
            clearInterval(window.previewRefreshInterval);
            window.previewRefreshInterval = null;
        }
    }

    /**
     * Orient camera using COLMAP pose estimation
     */
    async orientCamera() {
        if (!this.selectedCamera) {
            alert('Please select a camera first');
            return;
        }
        
        const orientBtn = document.getElementById('orientCameraBtn');
        const statusText = document.getElementById('poseStatusText');
        
        try {
            orientBtn.disabled = true;
            orientBtn.textContent = '⏳ Processing...';
            statusText.textContent = `Orienting ${this.selectedCamera.replace('_', ' ').toUpperCase()} camera...`;
            
            // Step 1: Capture snapshot
            Utils.updateProcessingStep('captureStep', 'active');
            statusText.textContent = 'Capturing camera snapshot...';
            
            const captureResponse = await this.api.captureCameraSnapshot(this.selectedCamera);
            if (!captureResponse.success) {
                throw new Error('Failed to capture camera snapshot');
            }
            
            Utils.updateProcessingStep('captureStep', 'completed');
            
            // Step 2: Estimate pose
            Utils.updateProcessingStep('featuresStep', 'active');
            statusText.textContent = 'Extracting SIFT features...';
            
            const poseResponse = await this.api.estimateCameraPose(this.selectedCamera, captureResponse.snapshot_path);
            if (!poseResponse.success) {
                throw new Error(poseResponse.error || 'Camera pose estimation failed');
            }
            
            // Update steps based on response
            Utils.updateProcessingStep('featuresStep', 'completed');
            Utils.updateProcessingStep('matchStep', 'completed');
            Utils.updateProcessingStep('poseStep', 'completed');
            Utils.updateProcessingStep('transformStep', 'completed');
            
            // Show results
            this.showPoseResults(poseResponse);
            statusText.textContent = 'Camera pose estimation completed successfully!';
            
        } catch (error) {
            console.error('Camera pose estimation failed:', error);
            
            // Mark current step as error
            const activeStep = document.querySelector('.processing-step.active');
            if (activeStep) {
                activeStep.className = 'processing-step error';
            }
            
            statusText.textContent = `Error: ${error.message}`;
            alert(`Camera pose estimation failed: ${error.message}`);
            
        } finally {
            orientBtn.disabled = false;
            orientBtn.textContent = '🎯 Orient Camera';
        }
    }

    /**
     * Show pose estimation results
     * @param {Object} poseData - Pose estimation data
     */
    showPoseResults(poseData) {
        const resultsDiv = document.getElementById('poseResults');
        const resultsContent = document.getElementById('poseResultsContent');
        
        if (!resultsDiv || !resultsContent) return;
        
        let resultText = `Camera: ${this.selectedCamera.replace('_', ' ').toUpperCase()}\n`;
        resultText += `Confidence: ${poseData.confidence || 'Unknown'}\n`;
        resultText += `Processing Time: ${poseData.processing_time || 'Unknown'}s\n\n`;
        
        if (poseData.transformation_matrix) {
            resultText += `Transformation Matrix:\n`;
            const matrix = poseData.transformation_matrix;
            for (let i = 0; i < 4; i++) {
                resultText += `[${matrix[i].map(x => x.toFixed(6)).join(', ')}]\n`;
            }
        }
        
        if (poseData.translation) {
            resultText += `\nTranslation: [${poseData.translation.map(x => x.toFixed(3)).join(', ')}]`;
        }
        
        if (poseData.rotation) {
            resultText += `\nRotation (quaternion): [${poseData.rotation.map(x => x.toFixed(3)).join(', ')}]`;
        }
        
        resultsContent.textContent = resultText;
        resultsDiv.style.display = 'block';
        
        // Add pose visualization section
        this.addPoseVisualization(poseData);
    }

    /**
     * Add pose visualization section to results
     * @param {Object} poseData - Pose estimation data
     */
    async addPoseVisualization(poseData) {
        try {
            // Show the full-width validation section
            const validationSection = document.getElementById('cameraValidationSection');
            if (validationSection) {
                validationSection.style.display = 'block';
            }
            
            // Use the validation container instead of creating a new section
            let vizContainer = document.getElementById('poseValidationContainer');
            
            if (!vizContainer) {
                console.error('Validation container not found');
                return;
            }
            
            // Create visualization button and iframe container in the full-width container
            vizContainer.innerHTML = `
                <button id="showPoseVisualizationBtn" 
                        style="background: #007bff; color: white; border: none; padding: 10px 20px; 
                               border-radius: 5px; cursor: pointer; font-size: 14px; margin-bottom: 15px;">
                    🎯 Show Pose Visualization
                </button>
                <div id="poseVisualizationFrame" style="display: none;">
                    <div style="position: relative; width: 100%; height: 600px; border: 1px solid #ddd; border-radius: 5px;">
                        <iframe id="poseVisualizationIframe" 
                                style="width: 100%; height: 100%; border: none; border-radius: 5px;"
                                title="Camera Pose Visualization">
                        </iframe>
                        <div style="position: absolute; top: 5px; right: 5px;">
                            <button onclick="document.getElementById('poseVisualizationFrame').style.display='none'" 
                                    style="background: rgba(255,255,255,0.8); border: 1px solid #ddd; 
                                           padding: 5px 8px; border-radius: 3px; cursor: pointer; font-size: 12px;">
                                ✕ Close
                            </button>
                        </div>
                    </div>
                    <p style="margin: 10px 0 0 0; color: #666; font-size: 12px; text-align: center;">
                        <em>Blue wireframe shows camera view frustum. Red dot is camera position. Use mouse to orbit around the scene.</em>
                    </p>
                </div>
            `;
            
            // Add event listener for visualization button
            const showBtn = document.getElementById('showPoseVisualizationBtn');
            if (showBtn) {
                showBtn.onclick = async () => {
                    await this.showPoseVisualization(poseData);
                };
            }
            
        } catch (error) {
            console.error('Error adding pose visualization:', error);
        }
    }

    /**
     * Show camera pose visualization in iframe
     * @param {Object} poseData - Pose estimation data
     */
    async showPoseVisualization(poseData) {
        const showBtn = document.getElementById('showPoseVisualizationBtn');
        const container = document.getElementById('poseVisualizationFrame');
        const iframe = document.getElementById('poseVisualizationIframe');
        
        if (!showBtn || !container || !iframe) return;
        
        try {
            // Update button state
            showBtn.disabled = true;
            showBtn.textContent = '⏳ Generating Visualization...';
            
            // Request pose visualization from backend
            const response = await fetch('/api/orient/render-camera-pose', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ camera_name: this.selectedCamera })
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                // Load visualization via web server route instead of file:// URL
                iframe.src = `/api/orient/visualization/${this.selectedCamera}`;
                
                // Show container
                container.style.display = 'block';
                
                // Update button
                showBtn.textContent = '✅ Visualization Generated';
                showBtn.style.background = '#28a745';
                
                // Scroll to visualization
                container.scrollIntoView({ behavior: 'smooth', block: 'center' });
                
                Utils.showToast('🎯 Pose visualization generated successfully!', 'success');
                
            } else {
                throw new Error(result.error || 'Failed to generate visualization');
            }
            
        } catch (error) {
            console.error('Error generating pose visualization:', error);
            Utils.showToast(`❌ Visualization failed: ${error.message}`, 'error');
            
            // Reset button
            showBtn.textContent = '🎯 Show Pose Visualization';
            showBtn.style.background = '#007bff';
        } finally {
            showBtn.disabled = false;
        }
    }

    /**
     * Load camera poses list
     */
    async loadCameraPoseList() {
        try {
            const result = await this.api.getCameraPoses();
            const hasPointCloud = await this.checkPointCloudAvailable();
            const listDiv = document.getElementById('cameraManagementList');
            
            if (!listDiv) return;
            
            // Camera configuration
            const cameras = [
                { name: 'front_door', display: 'Front Door', icon: '🚪', port: '8101' },
                { name: 'backyard', display: 'Backyard', icon: '🌳', port: '8102' },
                { name: 'side_yard', display: 'Side Yard', icon: '🏠', port: '8103' },
                { name: 'garage', display: 'Garage', icon: '🚗', port: '8104' }
            ];
            
            let html = '';
            cameras.forEach(camera => {
                const pose = result.poses ? result.poses[camera.name] : null;
                
                html += this.createCameraManagementCard(camera, pose, hasPointCloud);
            });
            
            listDiv.innerHTML = html || '<p style="color: #666; text-align: center;">No cameras available</p>';
            
            // Set up auto-refresh for camera images
            cameras.forEach(camera => {
                const snapshotUrl = this.api.getCameraSnapshot(camera.name);
                Utils.setupImageRefresh(`settingsCamera${camera.name}`, snapshotUrl, 1000);
            });
            
        } catch (error) {
            console.error('Error loading camera management:', error);
            Utils.safeElementOperation('cameraManagementList', el => {
                el.innerHTML = '<p style="color: #dc3545;">Error loading camera information</p>';
            });
        }
    }

    /**
     * Create camera management card HTML
     * @param {Object} camera - Camera configuration
     * @param {Object} pose - Pose data
     * @param {boolean} hasPointCloud - Whether point cloud is available
     * @returns {string} HTML string
     */
    createCameraManagementCard(camera, pose, hasPointCloud) {
        return `
            <div class="camera-management-card" style="background: #f8f9fa; border-radius: 12px; padding: 20px; border: 1px solid #e0e0e0; position: relative;">
                <!-- Camera Live Image -->
                <div style="margin-bottom: 15px; position: relative; width: 100%; padding-bottom: 75%; /* 4:3 aspect ratio */">
                    <img id="settingsCamera${camera.name}" 
                         style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; border-radius: 8px; background: #000;" 
                         alt="${camera.display} Camera">
                </div>
                
                <!-- Camera Info -->
                <div style="margin-bottom: 15px;">
                    <h4 style="margin: 0 0 5px 0; color: #333;">${camera.icon} ${camera.display}</h4>
                    ${pose ? `
                        <div style="margin: 8px 0; padding: 10px; background: #d4edda; border: 1px solid #c3e6cb; border-radius: 4px;">
                            <div style="font-weight: 600; color: #155724; margin-bottom: 5px;">✅ Pose Calibrated</div>
                            <div style="font-size: 12px; color: #155724;">
                                <div><strong>Calibrated:</strong> ${new Date(pose.calibrated_at).toLocaleString()}</div>
                                <div><strong>Confidence:</strong> ${(pose.confidence * 100).toFixed(1)}%</div>
                                <div><strong>Features:</strong> ${pose.features_matched}/${pose.total_features}</div>
                                <div><strong>Position:</strong> (${pose.translation.map(v => v.toFixed(2)).join(', ')})</div>
                            </div>
                            <button onclick="colmapManager.clearCameraPose('${camera.name}')" 
                                    style="margin-top: 5px; padding: 2px 6px; font-size: 11px; background: #dc3545; color: white; border: none; border-radius: 3px; cursor: pointer;">
                                🗑️ Clear Calibration
                            </button>
                        </div>
                    ` : `
                        <div style="margin: 8px 0; padding: 10px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px;">
                            <div style="font-weight: 600; color: #856404;">⚠️ Not Calibrated</div>
                            <div style="font-size: 12px; color: #856404;">Camera position not determined</div>
                        </div>
                    `}
                </div>
                
                <!-- Action Buttons -->
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <a href="http://localhost:${camera.port}" target="_blank" 
                       class="action-button" 
                       style="background: linear-gradient(135deg, #28a745 0%, #20c997 100%); font-size: 12px; padding: 6px 12px; text-decoration: none; display: inline-block;">
                        ⚙️ Settings
                    </a>
                    
                    <button class="action-button" onclick="colmapManager.recalibrateCamera('${camera.name}')" 
                            ${!hasPointCloud ? 'disabled title="Point cloud required for calibration"' : ''}
                            style="background: ${!hasPointCloud ? '#6c757d' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'}; font-size: 12px; padding: 6px 12px;">
                        🎯 ${pose ? 'Recalibrate' : 'Calibrate'}
                    </button>
                </div>
                
                ${!hasPointCloud ? `
                    <div style="margin-top: 10px; padding: 8px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px; color: #856404; font-size: 12px;">
                        ⚠️ Camera calibration requires a completed 3D reconstruction. Please complete the Reconstruct pipeline first.
                    </div>
                ` : ''}
            </div>
        `;
    }

    /**
     * Check if point cloud is available for calibration
     * @returns {boolean} True if point cloud is available
     */
    async checkPointCloudAvailable() {
        try {
            console.log('Calling getMeshes API...');
            const result = await this.api.getMeshes();
            console.log('getMeshes result:', result);
            
            if (result.mesh_files && result.mesh_files.length > 0) {
                console.log('Found mesh files:', result.mesh_files.map(f => f.name));
                const hasYardFile = result.mesh_files.some(file => 
                    file.name === 'yard_reconstruction.ply'
                );
                console.log('Has yard_reconstruction.ply:', hasYardFile);
                return hasYardFile;
            }
            console.log('No mesh files found');
            return false;
        } catch (error) {
            console.error('Error checking point cloud availability:', error);
            return false;
        }
    }

    /**
     * Recalibrate camera
     * @param {string} cameraName - Camera name
     */
    async recalibrateCamera(cameraName) {
        if (!confirm(`This will recalibrate the ${cameraName.replace('_', ' ')} camera position. Continue?`)) {
            return;
        }
        
        try {
            Utils.showToast(`📸 Starting calibration for ${cameraName.replace('_', ' ')}...`, 'info');
            
            // Capture snapshot
            const captureResponse = await this.api.captureCameraSnapshot(cameraName);
            if (!captureResponse.success) {
                throw new Error('Failed to capture snapshot');
            }
            
            Utils.showToast('🔍 Extracting features...', 'info');
            
            // Estimate pose
            const poseResult = await this.api.estimateCameraPose(cameraName);
            
            if (poseResult.success) {
                Utils.showToast(`✅ Camera ${cameraName.replace('_', ' ')} calibrated successfully!`, 'success');
                this.loadCameraPoseList(); // Refresh the list
            } else {
                Utils.showToast(`❌ Calibration failed: ${poseResult.error}`, 'error');
            }
        } catch (error) {
            Utils.showToast(`❌ Calibration error: ${error.message}`, 'error');
        }
    }

    /**
     * Clear camera pose calibration
     * @param {string} cameraName - Camera name
     */
    async clearCameraPose(cameraName) {
        if (!confirm(`This will clear the pose calibration for ${cameraName.replace('_', ' ')}. Continue?`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/orient/clear-camera-pose/${cameraName}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                Utils.showToast(`✅ Pose calibration cleared for ${cameraName.replace('_', ' ')}`, 'success');
                this.loadCameraPoseList(); // Refresh the list
            } else {
                Utils.showToast(`❌ Failed to clear calibration: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Error clearing camera pose:', error);
            Utils.showToast(`❌ Error clearing calibration: ${error.message}`, 'error');
        }
    }

    /**
     * Check reconstruction status
     */
    async checkReconstructionStatus() {
        try {
            const response = await this.api.getReconstructionStatus();
            return response || { reconstruction_complete: false, has_dense: false };
        } catch (error) {
            console.error('Error checking reconstruction status:', error);
            return { reconstruction_complete: false, has_dense: false };
        }
    }

    /**
     * Handle video upload
     * @param {Event} event - File input change event
     */
    async handleVideoUpload(event) {
        const files = Array.from(event.target.files);
        
        for (const file of files) {
            // Check file size (500MB limit)
            const maxSize = 500 * 1024 * 1024; // 500MB
            if (file.size > maxSize) {
                const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
                Utils.showToast(`❌ ${file.name} is too large (${sizeMB}MB). Maximum size is 500MB.`, 'error');
                continue;
            }

            // Check if file already exists
            if (!this.uploadedVideos.some(video => video.original_name === file.name)) {
                try {
                    console.log(`Starting upload of ${file.name} (${(file.size / (1024 * 1024)).toFixed(2)}MB)`);
                    
                    // Show uploading status with progress
                    Utils.showToast(`⏳ Starting upload of ${file.name}...`, 'info');
                    let lastProgressUpdate = 0;
                    
                    const result = await this.api.uploadVideo(file, (percent, loaded, total) => {
                        // Update progress - only show progress every 10% to avoid spam
                        const roundedPercent = Math.round(percent);
                        if (roundedPercent >= lastProgressUpdate + 10 || roundedPercent >= 90) {
                            const loadedMB = (loaded / (1024 * 1024)).toFixed(1);
                            const totalMB = (total / (1024 * 1024)).toFixed(1);
                            console.log(`Upload progress: ${roundedPercent}% (${loadedMB}/${totalMB} MB)`);
                            
                            if (roundedPercent >= lastProgressUpdate + 25) { // Show toast every 25%
                                Utils.showToast(`⏳ Uploading ${file.name}... ${roundedPercent}%`, 'info');
                                lastProgressUpdate = roundedPercent;
                            }
                        }
                    });
                    
                    console.log(`Upload result for ${file.name}:`, result);
                    
                    if (result && result.status === 'success') {
                        // Add server-stored video info to list
                        const videoInfo = {
                            name: result.filename,
                            original_name: file.name,
                            size: result.size,
                            video_id: result.video_id,
                            filename: result.filename
                        };
                        this.uploadedVideos.push(videoInfo);
                        Utils.showToast(`✅ ${file.name} uploaded successfully`, 'success');
                    } else {
                        const errorMsg = result?.error || 'Unknown server error';
                        Utils.showToast(`❌ Failed to upload ${file.name}: ${errorMsg}`, 'error');
                    }
                } catch (error) {
                    console.error(`Upload error for ${file.name}:`, error);
                    
                    let errorMessage = error.message;
                    if (error.name === 'AbortError') {
                        errorMessage = 'Upload was aborted (possibly due to timeout or connection issue)';
                    } else if (error.message.includes('Failed to fetch')) {
                        errorMessage = 'Network connection failed - check server connection';
                    } else if (error.message.includes('413')) {
                        errorMessage = 'File too large for server';
                    }
                    
                    Utils.showToast(`❌ Upload error: ${errorMessage}`, 'error');
                }
            } else {
                Utils.showToast(`⚠️ ${file.name} already uploaded`, 'warning');
            }
        }
        
        // Clear the file input so same file can be uploaded again if needed
        event.target.value = '';
        
        this.saveState();
        this.updateVideoList();
        this.updateWorkflowButtons();
    }

    /**
     * Load videos from server
     */
    async loadVideosFromServer() {
        try {
            const result = await this.api.listVideos();
            if (result.videos) {
                this.uploadedVideos = result.videos;
                this.updateVideoList();
                this.updateWorkflowButtons();
            }
        } catch (error) {
            console.error('Error loading videos from server:', error);
        }
    }

    /**
     * Load uploaded videos (alias for loadVideosFromServer)
     */
    async loadUploadedVideos() {
        await this.loadVideosFromServer();
    }

    /**
     * Update video list display
     */
    updateVideoList() {
        const videoListElement = document.getElementById('videoList');
        if (!videoListElement) return;

        if (this.uploadedVideos.length === 0) {
            videoListElement.innerHTML = '<div style="text-align: center; padding: 20px; color: #666;"><p>No videos uploaded yet. Please upload videos to start reconstruction.</p></div>';
            return;
        }

        // Create video list similar to legacy format
        const videosHtml = this.uploadedVideos.map((video, index) => {
            const sizeInMB = (video.size / (1024 * 1024)).toFixed(2);
            const uploadedTime = video.uploaded_at ? new Date(video.uploaded_at).toLocaleString() : '';
            
            return `
                <div class="video-item" style="display: flex; justify-content: space-between; align-items: center; padding: 10px; border: 1px solid #dee2e6; border-radius: 5px; margin-bottom: 10px; background: #f8f9fa;">
                    <div class="video-info">
                        <div class="video-name" style="font-weight: 600; color: #333;">📹 ${video.name || video.original_name || video.filename}</div>
                        <div class="video-size" style="font-size: 0.9em; color: #666;">${sizeInMB} MB</div>
                        ${uploadedTime ? `<div style="font-size: 0.8em; color: #666;">Uploaded: ${uploadedTime}</div>` : ''}
                    </div>
                    <div class="video-actions">
                        <button class="btn-delete" onclick="deleteVideo('${video.filename || video.name}', ${index})" style="background: #dc3545; color: white; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-size: 0.9em;">🗑️ Delete</button>
                    </div>
                </div>
            `;
        }).join('');

        videoListElement.innerHTML = videosHtml;

        // Show server persistence notice if videos exist
        if (this.uploadedVideos.length > 0) {
            const notice = document.createElement('div');
            notice.style.cssText = 'background: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 10px; border-radius: 5px; margin-top: 10px; font-size: 0.9em;';
            notice.innerHTML = '✅ Videos are stored on the server and will persist across browser refreshes';
            videoListElement.appendChild(notice);
        }
    }

    /**
     * Remove video from list (local only)
     * @param {number} index - Video index
     */
    removeVideo(index) {
        if (index >= 0 && index < this.uploadedVideos.length) {
            this.uploadedVideos.splice(index, 1);
            this.saveState();
            this.updateVideoList();
            this.updateWorkflowButtons();
        }
    }

    /**
     * DEPRECATED - Extract frames from uploaded videos (old method - DO NOT USE)
     */
    async extractFrames_OLD_DEPRECATED() {
        if (this.uploadedVideos.length === 0) {
            Utils.showToast('Please upload videos first', 'error');
            return;
        }

        const btn = document.getElementById('extractFramesBtn');
        if (!btn) {
            console.error('Extract frames button not found');
            return;
        }

        try {
            // Update UI
            btn.disabled = true;
            btn.textContent = '⏳ Extracting...';
            Utils.safeElementOperation('extractionStatus', el => {
                el.textContent = 'Extracting frames from videos...';
                el.className = 'processing-status running';
            });

            // Get selected frame interval
            const frameInterval = document.getElementById('frameInterval')?.value || '60';

            // Use first uploaded video - need absolute path for ffmpeg
            const videoFilename = this.uploadedVideos[0].filename || this.uploadedVideos[0].name;
            const videoFile = `/home/andrew/nvr/uploaded_videos/${videoFilename}`;
            const projectDir = '/home/andrew/nvr/reconstruction';

            console.log(`Starting frame extraction from ${videoFile} with interval ${frameInterval}`);
            
            // Show video file info
            const videoInfo = this.uploadedVideos[0];
            const videoSizeMB = videoInfo.size ? (videoInfo.size / (1024 * 1024)).toFixed(1) : '?';
            Utils.showToast(`Starting frame extraction from ${videoInfo.name} (${videoSizeMB}MB)`, 'info');

            // Create AbortController with longer timeout for frame extraction
            // Note: Performance optimizer now handles COLMAP timeouts (30 min vs 10s default)
            const controller = new AbortController();
            const startTime = Date.now();
            
            const timeoutId = setTimeout(() => {
                controller.abort();
            }, 20 * 60 * 1000); // 20 minute fallback timeout for frame extraction

            const response = await fetch('/api/colmap/extract-frames', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    video_file: videoFile,
                    project_dir: projectDir,
                    fps: frameInterval
                }),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            const data = await response.json();

            if (data.status === 'success') {
                // Update processing state
                this.processingState.frameExtraction = true;
                this.saveState();

                // Update UI
                Utils.safeElementOperation('extractionStatus', el => {
                    el.textContent = `✅ Extracted ${data.frames_extracted} frames`;
                    el.className = 'processing-status success';
                });
                
                btn.textContent = '✅ Frames Extracted';
                btn.style.background = 'linear-gradient(135deg, #28a745 0%, #20c997 100%)';

                // Update workflow buttons
                this.updateWorkflowButtons();
                await this.updateProcessingStates();

                Utils.showToast(`✅ Successfully extracted ${data.frames_extracted} frames`, 'success');
            } else {
                throw new Error(data.error || 'Frame extraction failed');
            }

        } catch (error) {
            const elapsed = (Date.now() - startTime) / 1000;
            console.error(`Frame extraction error after ${elapsed} seconds:`, error);
            
            let errorMessage = error.message;
            if (error.name === 'AbortError') {
                if (elapsed < 60) {
                    errorMessage = `Frame extraction aborted after ${elapsed.toFixed(1)} seconds - this is likely a network/server timeout, not our 10-minute limit`;
                } else {
                    errorMessage = `Frame extraction timed out after ${Math.round(elapsed/60)} minutes. Try with a smaller video or higher frame interval.`;
                }
            } else if (error.message.includes('Failed to fetch')) {
                errorMessage = 'Network connection failed - check server connection';
            }
            
            Utils.safeElementOperation('extractionStatus', el => {
                el.textContent = `❌ Error: ${errorMessage}`;
                el.className = 'processing-status error';
            });

            Utils.showToast(`❌ Frame extraction failed: ${errorMessage}`, 'error');
        } finally {
            btn.disabled = false;
            if (btn.textContent.includes('⏳')) {
                btn.textContent = '🎬 Extract Frames';
                btn.style.background = '';
            }
        }
    }

    /**
     * Delete video from server and update list
     * @param {string} videoId - Video filename/ID
     * @param {number} index - Video index in the list
     */
    async deleteVideo(videoId, index) {
        if (!confirm('Are you sure you want to delete this video?')) {
            return;
        }

        try {
            const response = await fetch(`/api/colmap/delete-video/${videoId}`, {
                method: 'DELETE'
            });

            const result = await response.json();
            if (result.status === 'success') {
                // Remove from local array
                if (index >= 0 && index < this.uploadedVideos.length) {
                    this.uploadedVideos.splice(index, 1);
                }
                
                this.saveState();
                this.updateVideoList();
                this.updateWorkflowButtons();
                
                // Show success message
                if (window.showToast) {
                    window.showToast('✅ Video deleted successfully', 'success');
                } else {
                    console.log('✅ Video deleted successfully');
                }
            } else {
                const errorMsg = `❌ Failed to delete video: ${result.error}`;
                if (window.showToast) {
                    window.showToast(errorMsg, 'error');
                } else {
                    alert(errorMsg);
                }
            }
        } catch (error) {
            const errorMsg = `❌ Delete error: ${error.message}`;
            if (window.showToast) {
                window.showToast(errorMsg, 'error');
            } else {
                alert(errorMsg);
            }
        }
    }

    /**
     * Start processing phase with progress tracking
     * @param {string} phase - Processing phase name
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Request data
     * @param {Function} onComplete - Completion callback
     */
    async startProcessingWithProgress(phase, endpoint, data, onComplete) {
        try {
            // Start the processing
            const response = await this.api.post(endpoint, data);
            
            if (response.success) {
                // Start progress tracking
                this.progressTracker.startTracking(phase, (progress) => {
                    this.updateProgressUI(progress, phase);
                    if (progress.complete && onComplete) {
                        onComplete(progress);
                    }
                });
            } else {
                throw new Error(response.error || `Failed to start ${phase}`);
            }
        } catch (error) {
            console.error(`Error starting ${phase}:`, error);
            Utils.showToast(`❌ Failed to start ${phase}: ${error.message}`, 'error');
        }
    }

    /**
     * Update progress UI
     * @param {Object} progress - Progress data
     * @param {string} phase - Processing phase
     */
    updateProgressUI(progress, phase) {
        const progressElement = document.getElementById(`${phase}Progress`);
        const statusElement = document.getElementById(`${phase}Status`);
        
        if (progressElement) {
            progressElement.style.display = progress.complete ? 'none' : 'block';
            if (progress.percentage) {
                const progressBar = progressElement.querySelector('.progress-bar');
                if (progressBar) {
                    progressBar.style.width = `${progress.percentage}%`;
                }
            }
        }
        
        if (statusElement) {
            if (progress.complete) {
                statusElement.textContent = progress.error ? `❌ ${progress.error}` : '✅ Complete';
                statusElement.className = progress.error ? 'status-error' : 'status-success';
            } else {
                statusElement.textContent = progress.status || 'Processing...';
                statusElement.className = 'status-processing';
            }
        }
    }

    /**
     * Run feature extraction with progress tracking
     */
    async runFeatureExtractionWithProgress() {
        try {
            // Check if we have a project directory
            const projectDir = this.currentProjectDir || '/home/andrew/nvr/colmap_projects/current_reconstruction';
            
            console.log('Starting feature extraction for project:', projectDir);
            Utils.showToast('🔍 Starting feature extraction...', 'info');
            
            // Update UI state
            const featureBtn = document.getElementById('featureExtractionBtn');
            if (featureBtn) {
                featureBtn.disabled = true;
                featureBtn.textContent = '⏳ Extracting features...';
            }
            
            // Show progress bar
            const progressContainer = document.getElementById('featureProgress');
            if (progressContainer) {
                progressContainer.style.display = 'block';
            }
            
            // Make API call to start feature extraction with progress tracking
            const response = await fetch('/api/colmap/start-with-progress/feature_extraction', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    project_dir: projectDir
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.status === 'success') {
                // Store session ID for progress tracking
                this.currentProgressSession = result.session_id;
                
                // Start polling for progress updates
                this.startProgressPolling('feature_extraction');
                
                Utils.showToast('🔍 Feature extraction started, tracking progress...', 'info');
            } else {
                throw new Error(result.error || 'Feature extraction failed');
            }
            
        } catch (error) {
            console.error('Feature extraction error:', error);
            Utils.showToast(`❌ Feature extraction failed: ${error.message}`, 'error');
            
            // Only reset on error - let progress polling handle completion
            const featureBtn = document.getElementById('featureExtractionBtn');
            if (featureBtn) {
                featureBtn.disabled = false;
                featureBtn.textContent = '🔍 Extract & Match Features';
            }
            
            // Hide progress bar on error
            const progressContainer = document.getElementById('featureProgress');
            if (progressContainer) {
                progressContainer.style.display = 'none';
            }
        }
    }

    /**
     * Run sparse reconstruction with progress tracking
     */
    async runSparseReconstructionWithProgress() {
        console.log('runSparseReconstructionWithProgress called');
        try {
            const projectDir = this.currentProjectDir || '/home/andrew/nvr/colmap_projects/current_reconstruction';
            console.log('Using project directory:', projectDir);
            
            console.log('Starting sparse reconstruction for project:', projectDir);
            console.log('Utils available:', typeof Utils);
            console.log('Utils.showToast available:', typeof Utils?.showToast);
            Utils.showToast('🏗️ Starting sparse reconstruction...', 'info');
            
            // Update UI state
            const sparseBtn = document.getElementById('sparseReconstructionBtn');
            if (sparseBtn) {
                sparseBtn.disabled = true;
                sparseBtn.textContent = '⏳ Reconstructing...';
            }
            
            // Show progress bar
            const progressContainer = document.getElementById('sparseProgress');
            if (progressContainer) {
                progressContainer.style.display = 'block';
            }
            
            // Make API call to start sparse reconstruction with progress tracking
            const response = await fetch('/api/colmap/start-with-progress/sparse_reconstruction', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    project_dir: projectDir
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.status === 'success') {
                // Store session ID for progress tracking
                this.currentProgressSession = result.session_id;
                
                // Start polling for progress updates
                this.startProgressPolling('sparse_reconstruction');
                
                Utils.showToast('🏗️ Sparse reconstruction started, tracking progress...', 'info');
            } else {
                throw new Error(result.error || 'Sparse reconstruction failed');
            }
            
        } catch (error) {
            console.error('Sparse reconstruction error:', error);
            Utils.showToast(`❌ Sparse reconstruction failed: ${error.message}`, 'error');
            
            // Only reset on error - let progress polling handle completion
            const sparseBtn = document.getElementById('sparseReconstructionBtn');
            if (sparseBtn) {
                sparseBtn.disabled = false;
                sparseBtn.textContent = '🏗️ Sparse Reconstruction';
            }
            
            // Hide progress bar on error
            const progressContainer = document.getElementById('sparseProgress');
            if (progressContainer) {
                progressContainer.style.display = 'none';
            }
        }
    }

    /**
     * Check if dense reconstruction is currently running
     */
    async checkDenseReconstructionStatus() {
        try {
            console.log('Checking dense reconstruction status...');
            const response = await fetch('/api/colmap/dense-reconstruction-status');
            const result = await response.json();
            console.log('Dense status result:', result);
            
            if (response.ok) {
                const denseBtn = document.getElementById('denseReconstructionBtn');
                const denseStatus = document.getElementById('denseStatus');
                const progressContainer = document.getElementById('denseProgress');
                
                
                if (result.running) {
                    // Dense reconstruction is running - get detailed progress
                    console.log('Dense reconstruction is running:', result.container_info);
                    
                    // Navigate to the correct tab to show the progress
                    console.log('Navigating to reconstruction tab to show progress...');
                    if (window.showTab && window.showConfigTab) {
                        window.showTab('config');
                        setTimeout(() => {
                            window.showConfigTab('reconstruct');
                        }, 100);
                    }
                    
                    // Fetch detailed progress
                    this.updateDenseReconstructionProgress();
                    
                    // Start polling for progress updates every 10 seconds
                    if (!this.denseProgressInterval) {
                        this.denseProgressInterval = setInterval(() => {
                            this.updateDenseReconstructionProgress();
                        }, 10000);
                    }
                    
                    if (denseBtn) {
                        denseBtn.disabled = true;
                        denseBtn.textContent = '🔄 Dense Reconstruction Running...';
                        denseBtn.title = result.message;
                    }
                    
                    Utils.showToast('🔄 Dense reconstruction is already running. Switching to reconstruction tab to show progress.', 'warning');
                    
                } else {
                    // No dense reconstruction running
                    console.log('No dense reconstruction running');
                    
                    // Clear progress polling
                    if (this.denseProgressInterval) {
                        clearInterval(this.denseProgressInterval);
                        this.denseProgressInterval = null;
                    }
                    
                    if (denseBtn) {
                        denseBtn.disabled = false;
                        denseBtn.textContent = '🌟 Dense Reconstruction';
                        denseBtn.title = 'Start dense reconstruction pipeline';
                    }
                    
                    if (denseStatus) {
                        denseStatus.textContent = '';
                        denseStatus.className = 'processing-status';
                    }
                    
                    if (progressContainer) {
                        progressContainer.style.display = 'none';
                    }
                }
                
                return result.running;
            } else {
                console.error('Failed to check dense reconstruction status:', result);
                return false;
            }
            
        } catch (error) {
            console.error('Error checking dense reconstruction status:', error);
            return false;
        }
    }

    /**
     * Update dense reconstruction progress with real-time data
     */
    async updateDenseReconstructionProgress() {
        try {
            const projectDir = this.currentProjectDir || '/home/andrew/nvr/colmap_projects/current_reconstruction';
            const response = await fetch(`/api/colmap/dense-reconstruction-progress?project_dir=${encodeURIComponent(projectDir)}`);
            const progress = await response.json();
            
            if (response.ok) {
                console.log('Dense progress update:', progress);
                
                const denseStatus = document.getElementById('denseStatus');
                const progressContainer = document.getElementById('denseProgress');
                
                
                if (denseStatus) {
                    denseStatus.textContent = `${progress.phase_name} - ${progress.progress_percent}%`;
                    denseStatus.className = 'processing-status running';
                    denseStatus.style.color = progress.phase === 'completed' ? '#28a745' : '#ffc107';
                }
                
                if (progressContainer) {
                    progressContainer.style.display = 'block';
                    
                    const progressFill = progressContainer.querySelector('.progress-fill');
                    const progressLabel = progressContainer.querySelector('.progress-label');
                    const progressPercentage = progressContainer.querySelector('.progress-percentage');
                    const progressDetails = progressContainer.querySelector('#denseDetails');
                    const progressTime = progressContainer.querySelector('.progress-time');
                    
                    if (progressFill) {
                        progressFill.style.width = `${progress.progress_percent}%`;
                        if (progress.phase === 'completed') {
                            progressFill.style.animation = 'none';
                            progressFill.style.background = 'linear-gradient(90deg, #28a745, #34ce57)';
                        } else {
                            progressFill.style.animation = 'pulse 2s infinite';
                            progressFill.style.background = 'linear-gradient(90deg, #007bff, #0056b3, #007bff)';
                        }
                    }
                    
                    if (progressLabel) progressLabel.textContent = progress.phase_name;
                    if (progressPercentage) progressPercentage.textContent = `${progress.progress_percent}%`;
                    if (progressDetails) progressDetails.textContent = progress.details;
                    if (progressTime) progressTime.textContent = `ETA: ${progress.estimated_time_remaining}`;
                }
                
                // If completed, stop polling and update UI
                if (progress.phase === 'completed') {
                    if (this.denseProgressInterval) {
                        clearInterval(this.denseProgressInterval);
                        this.denseProgressInterval = null;
                    }
                    
                    Utils.showToast(`✅ Dense reconstruction completed! ${progress.current_count.toLocaleString()} points created`, 'success');
                    
                    // Enable point cloud button
                    const enablePointCloudBtn = document.getElementById('enablePointCloudBtn');
                    if (enablePointCloudBtn) {
                        enablePointCloudBtn.disabled = false;
                    }
                    
                    // Re-enable dense reconstruction button
                    const denseBtn = document.getElementById('denseReconstructionBtn');
                    if (denseBtn) {
                        denseBtn.disabled = false;
                        denseBtn.textContent = '🌟 Dense Reconstruction';
                    }
                }
                
            } else {
                console.error('Failed to get dense reconstruction progress:', progress);
            }
            
        } catch (error) {
            console.error('Error updating dense reconstruction progress:', error);
        }
    }

    /**
     * Enable point cloud for yard map generation
     */
    async enablePointCloud() {
        console.log('enablePointCloud called');
        try {
            const projectDir = this.currentProjectDir || '/home/andrew/nvr/colmap_projects/current_reconstruction';
            
            console.log('Enabling point cloud for project:', projectDir);
            Utils.showToast('🌟 Enabling point cloud for yard map...', 'info');
            
            const enableBtn = document.getElementById('enablePointCloudBtn');
            if (enableBtn) {
                enableBtn.disabled = true;
                enableBtn.textContent = '⏳ Enabling...';
            }
            
            const response = await fetch('/api/colmap/enable-point-cloud', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    project_dir: projectDir
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.status === 'success') {
                Utils.showToast('✅ Point cloud enabled for yard map generation!', 'success');
                
                if (enableBtn) {
                    enableBtn.textContent = '✅ Point Cloud Enabled';
                    enableBtn.style.background = '#28a745'; // Green background
                }
                
                console.log('Point cloud file:', result.mesh_file);
            } else {
                throw new Error(result.error || 'Failed to enable point cloud');
            }
            
        } catch (error) {
            console.error('Enable point cloud error:', error);
            Utils.showToast(`❌ Failed to enable point cloud: ${error.message}`, 'error');
            
            // Reset button state on error
            const enableBtn = document.getElementById('enablePointCloudBtn');
            if (enableBtn) {
                enableBtn.disabled = false;
                enableBtn.textContent = '✅ Enable Point Cloud';
            }
        }
    }

    /**
     * Initialize frame status when page loads
     */
    async initializeFrameStatus() {
        try {
            // Check for existing frames on page load
            const existingFrameCount = await this.checkExistingFrames();
            
            if (existingFrameCount > 0) {
                // Update UI to show existing frames
                const frameStatus = document.getElementById('frameStatus');
                if (frameStatus) {
                    frameStatus.textContent = '✅';
                }
                
                const extractBtn = document.getElementById('extractFramesBtn');
                if (extractBtn) {
                    extractBtn.textContent = `📹 ${existingFrameCount} Frames Ready`;
                    extractBtn.disabled = false;
                }
                
                // Enable feature extraction button if frames exist
                const featureBtn = document.getElementById('featureExtractionBtn');
                if (featureBtn) {
                    featureBtn.disabled = false;
                }
                
                console.log(`Initialized with ${existingFrameCount} existing frames`);
            } else {
                // No frames - keep default state
                console.log('No existing frames found - ready for extraction');
            }
        } catch (error) {
            console.log('Error initializing frame status:', error.message);
        }
    }

    /**
     * Check if frames already exist in the current reconstruction project
     */
    async checkExistingFrames() {
        try {
            const response = await fetch('/api/colmap/list-frames', {
                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                }
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('list-frames API result:', result);
                if (result.success) {
                    console.log('Returning frame_count:', result.frame_count || 0);
                    return result.frame_count || 0;
                }
            }
            
            return 0;
        } catch (error) {
            console.log('Error checking existing frames:', error.message);
            return 0;
        }
    }

    /**
     * Extract frames from uploaded videos or show existing frames
     */
    async extractFrames() {
        try {
            console.log('Checking for existing frames...');
            Utils.showToast('📹 Checking for existing frames...', 'info');
            
            // Update UI state
            const extractBtn = document.getElementById('extractFramesBtn');
            if (extractBtn) {
                extractBtn.disabled = true;
                extractBtn.textContent = '⏳ Checking frames...';
            }
            
            // First check if frames already exist
            const existingFrameCount = await this.checkExistingFrames();
            
            if (existingFrameCount > 0) {
                // Frames already exist - just show them
                Utils.showToast(`✅ Found ${existingFrameCount} existing frames - ready to proceed!`, 'success');
                
                // Update workflow status
                const frameStatus = document.getElementById('frameStatus');
                if (frameStatus) {
                    frameStatus.textContent = '✅';
                }
                
                // Enable next step button
                const featureBtn = document.getElementById('featureExtractionBtn');
                if (featureBtn) {
                    featureBtn.disabled = false;
                }
                
                // Update button to show frame count
                if (extractBtn) {
                    extractBtn.textContent = `📹 ${existingFrameCount} Frames Ready`;
                }
                
                return; // Don't re-extract
            }
            
            // No existing frames - need to extract
            console.log('No existing frames found, starting extraction...');
            Utils.showToast('📹 Starting frame extraction...', 'info');
            
            if (extractBtn) {
                extractBtn.textContent = '⏳ Extracting frames...';
            }
            
            // Make API call to extract frames from ALL uploaded videos
            const response = await fetch('/api/colmap/extract-frames-all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    project_dir: '/home/andrew/nvr/colmap_projects/current_reconstruction',
                    fps: 1  // Extract 1 frame per second by default
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.status === 'success') {
                const totalFrames = result.total_frames_extracted || 0;
                const videosProcessed = result.videos_processed || 0;
                const extractionResults = result.extraction_results || [];
                
                // Create detailed success message
                let message = `✅ Extracted ${totalFrames} frames from ${videosProcessed} video(s)!`;
                if (extractionResults.length > 0) {
                    const videoDetails = extractionResults
                        .filter(r => r.status === 'success')
                        .map(r => `${r.video}: ${r.frames_extracted} frames`)
                        .join(', ');
                    if (videoDetails) {
                        message += `\n${videoDetails}`;
                    }
                }
                
                Utils.showToast(message, 'success');
                console.log('Frame extraction results:', extractionResults);
                
                // Update workflow status
                const frameStatus = document.getElementById('frameStatus');
                if (frameStatus) {
                    frameStatus.textContent = '✅';
                }
                
                // Enable next step button
                const featureBtn = document.getElementById('featureExtractionBtn');
                if (featureBtn) {
                    featureBtn.disabled = false;
                }
                
                // Update button to show frame count
                if (extractBtn) {
                    extractBtn.textContent = `📹 ${totalFrames} Frames Ready (${videosProcessed} videos)`;
                }
            } else {
                throw new Error(result.error || 'Frame extraction failed');
            }
            
        } catch (error) {
            console.error('Frame extraction error:', error);
            Utils.showToast(`❌ Frame extraction failed: ${error.message}`, 'error');
            
            // Reset button state on error
            const extractBtn = document.getElementById('extractFramesBtn');
            if (extractBtn) {
                extractBtn.disabled = false;
                extractBtn.textContent = '📹 Extract Frames';
            }
        }
    }

    /**
     * Show reset modal for confirmation
     */
    showResetModal() {
        if (confirm('⚠️ This will delete all reconstruction data and start fresh. Are you sure?')) {
            this.resetReconstruction();
        }
    }

    /**
     * Reset the entire reconstruction project
     */
    async resetReconstruction() {
        try {
            console.log('Resetting reconstruction project...');
            Utils.showToast('🔄 Resetting reconstruction...', 'info');
            
            const response = await fetch('/api/colmap/reset-project', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    project_dir: this.currentProjectDir || '/home/andrew/nvr/colmap_projects/current_reconstruction'
                })
            });
            
            const result = await response.json();
            
            if (response.ok && (result.status === 'success' || result.status === 'partial_success')) {
                if (result.status === 'success') {
                    Utils.showToast('✅ Reconstruction reset successfully!', 'success');
                } else {
                    // Partial success - show warning
                    Utils.showToast(`⚠️ ${result.message}`, 'warning');
                    if (result.errors && result.errors.length > 0) {
                        console.warn('Reset errors:', result.errors);
                        // Show first few errors
                        const errorMsg = result.errors.slice(0, 2).join(', ');
                        Utils.showToast(`❌ Some files couldn't be deleted: ${errorMsg}`, 'error');
                    }
                }
                
                // Reset all workflow status indicators
                ['frameStatus', 'featureStatus', 'sparseStatus', 'denseStatus'].forEach(id => {
                    const element = document.getElementById(id);
                    if (element) {
                        element.textContent = '❌';
                    }
                });
                
                // Reset button states
                const buttons = ['extractFramesBtn', 'featureExtractionBtn', 'sparseReconstructionBtn', 'denseReconstructionBtn'];
                buttons.forEach((id, index) => {
                    const btn = document.getElementById(id);
                    if (btn) {
                        btn.disabled = index > 0;  // Only enable first button
                        // Reset button text to original
                        if (id === 'extractFramesBtn') {
                            btn.textContent = '🎬 Extract Frames';
                        } else if (id === 'featureExtractionBtn') {
                            btn.textContent = '🔍 Extract & Match Features';
                        } else if (id === 'sparseReconstructionBtn') {
                            btn.textContent = '⚡ Sparse Reconstruction';
                        } else if (id === 'denseReconstructionBtn') {
                            btn.textContent = '🌟 Dense Reconstruction';
                        }
                    }
                });
                
                // Hide model selection if visible
                const modelSelection = document.getElementById('modelSelection');
                if (modelSelection) {
                    modelSelection.style.display = 'none';
                }
                
                // Clear all status messages
                const statusElements = ['extractionStatus', 'featureStatus', 'sparseStatus', 'denseStatus'];
                statusElements.forEach(id => {
                    const element = document.getElementById(id);
                    if (element) {
                        element.textContent = '';
                        element.className = 'processing-status';
                    }
                });
                
                // Hide all progress bars
                const progressBars = ['featureProgress', 'sparseProgress', 'denseProgress', 'stereoProgress'];
                progressBars.forEach(id => {
                    const element = document.getElementById(id);
                    if (element) {
                        element.style.display = 'none';
                        // Reset progress fill if exists
                        const progressFill = element.querySelector('.progress-fill');
                        if (progressFill) {
                            progressFill.style.width = '0%';
                        }
                    }
                });
                
                // Reset local storage state
                this.processingState = {
                    frameExtraction: false,
                    featureExtraction: false,
                    sparseReconstruction: false,
                    denseReconstruction: false
                };
                this.saveState();
                
                // Clear any active progress sessions
                localStorage.removeItem('activeProgressSession');
                localStorage.removeItem('activeProgressPhase');
                
                // Log successful deletions for debugging
                if (result.deleted_items || result.successful_deletions) {
                    console.log('Successfully deleted:', result.deleted_items || result.successful_deletions);
                }
                
            } else {
                throw new Error(result.error || 'Reset failed');
            }
            
        } catch (error) {
            console.error('Reset error:', error);
            Utils.showToast(`❌ Reset failed: ${error.message}`, 'error');
        }
    }

    /**
     * Run dense reconstruction (modified version)
     */
    async runDenseReconstructionModified() {
        console.log('runDenseReconstructionModified called');
        try {
            // First check if dense reconstruction is already running
            const isRunning = await this.checkDenseReconstructionStatus();
            if (isRunning) {
                console.log('Dense reconstruction already running, aborting');
                return; // Exit early if already running
            }
            
            const projectDir = this.currentProjectDir || '/home/andrew/nvr/colmap_projects/current_reconstruction';
            
            console.log('Starting dense reconstruction (modified) for project:', projectDir);
            Utils.showToast('🎨 Starting dense reconstruction...', 'info');
            
            const denseBtn = document.getElementById('denseReconstructionBtn');
            if (denseBtn) {
                denseBtn.disabled = true;
                denseBtn.textContent = '⏳ Creating dense model...';
            }
            
            // Show progress container with animated indicator
            const progressContainer = document.getElementById('denseProgress');
            if (progressContainer) {
                progressContainer.style.display = 'block';
                
                // Show animated progress since this is a long-running synchronous operation
                const progressFill = progressContainer.querySelector('.progress-fill');
                const progressLabel = progressContainer.querySelector('.progress-label');
                const progressPercentage = progressContainer.querySelector('.progress-percentage');
                const progressDetails = progressContainer.querySelector('#denseDetails');
                
                if (progressFill) progressFill.style.width = '100%';
                if (progressLabel) progressLabel.textContent = 'Running dense reconstruction (3 steps: undistortion → stereo → fusion)...';
                if (progressPercentage) progressPercentage.textContent = 'In Progress';
                if (progressDetails) progressDetails.textContent = 'This may take 30-90 minutes. Please wait...';
                
                // Add pulsing animation to show it's working
                if (progressFill) {
                    progressFill.style.animation = 'pulse 2s infinite';
                    progressFill.style.background = 'linear-gradient(90deg, #007bff, #0056b3, #007bff)';
                }
            }
            
            // Make API call to start dense reconstruction (note: no progress tracking available yet)
            const response = await fetch('/api/colmap/dense-reconstruction', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    project_dir: projectDir
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.status === 'success') {
                // Dense reconstruction completed successfully
                const pointCount = result.point_count || 0;
                const modelUsed = result.model_used || 'unknown';
                
                Utils.showToast(`✅ Dense reconstruction completed! ${pointCount} points created using model ${modelUsed}`, 'success');
                
                const denseStatus = document.getElementById('denseStatus');
                if (denseStatus) {
                    denseStatus.textContent = '✅';
                    denseStatus.title = `Dense reconstruction completed with ${pointCount} points`;
                }
                
                // Hide progress bar after completion
                const progressContainer = document.getElementById('denseProgress');
                if (progressContainer) {
                    progressContainer.style.display = 'none';
                }
                
                // Reset button state
                const denseBtn = document.getElementById('denseReconstructionBtn');
                if (denseBtn) {
                    denseBtn.disabled = false;
                    denseBtn.textContent = '🌟 Dense Reconstruction';
                }
                
                // Enable any post-processing buttons
                const customFusionBtn = document.getElementById('customFusionBtn');
                if (customFusionBtn) {
                    customFusionBtn.disabled = false;
                }
                
                // Enable point cloud button for yard map generation
                const enablePointCloudBtn = document.getElementById('enablePointCloudBtn');
                if (enablePointCloudBtn) {
                    enablePointCloudBtn.disabled = false;
                }
            } else {
                throw new Error(result.error || 'Dense reconstruction failed');
            }
            
        } catch (error) {
            console.error('Dense reconstruction error:', error);
            Utils.showToast(`❌ Dense reconstruction failed: ${error.message}`, 'error');
            
            // Reset button state on error
            const denseBtn = document.getElementById('denseReconstructionBtn');
            if (denseBtn) {
                denseBtn.disabled = false;
                denseBtn.textContent = '🌟 Dense Reconstruction';
            }
            
            // Hide progress bar on error
            const progressContainer = document.getElementById('denseProgress');
            if (progressContainer) {
                progressContainer.style.display = 'none';
            }
        }
    }

    /**
     * Run custom fusion (if available)
     */
    async runCustomFusion() {
        try {
            console.log('Starting custom fusion...');
            Utils.showToast('🌟 Running custom fusion...', 'info');
            
            const response = await fetch('/api/colmap/custom-fusion', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    project_dir: this.currentProjectDir || '/home/andrew/colmap/projects/yard'
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                Utils.showToast('✅ Custom fusion completed!', 'success');
            } else {
                throw new Error(result.error || 'Custom fusion failed');
            }
            
        } catch (error) {
            console.error('Custom fusion error:', error);
            Utils.showToast(`❌ Custom fusion failed: ${error.message}`, 'error');
        }
    }

    /**
     * Run dense reconstruction with progress tracking
     */
    async runDenseReconstructionWithProgress() {
        try {
            const projectDir = this.currentProjectDir || '/home/andrew/nvr/colmap_projects/current_reconstruction';
            
            console.log('Starting dense reconstruction for project:', projectDir);
            Utils.showToast('🎨 Starting dense reconstruction...', 'info');
            
            const denseBtn = document.getElementById('denseReconstructionBtn');
            if (denseBtn) {
                denseBtn.disabled = true;
                denseBtn.textContent = '⏳ Creating dense model...';
            }
            
            const response = await fetch('/api/colmap/dense-reconstruction', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    project_dir: projectDir
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.status === 'success') {
                Utils.showToast('✅ Dense reconstruction completed!', 'success');
                
                const denseStatus = document.getElementById('denseStatus');
                if (denseStatus) {
                    denseStatus.textContent = '✅';
                }
            } else {
                throw new Error(result.error || 'Dense reconstruction failed');
            }
            
        } catch (error) {
            console.error('Dense reconstruction error:', error);
            Utils.showToast(`❌ Dense reconstruction failed: ${error.message}`, 'error');
        } finally {
            const denseBtn = document.getElementById('denseReconstructionBtn');
            if (denseBtn) {
                denseBtn.disabled = false;
                denseBtn.textContent = '🎨 Dense Reconstruction';
            }
        }
    }
    
    /**
     * Start polling for progress updates
     */
    startProgressPolling(phase = 'feature_extraction') {
        if (this.progressUpdateInterval) {
            clearInterval(this.progressUpdateInterval);
        }
        
        this.currentPhase = phase;
        
        // Save session info to localStorage for persistence
        localStorage.setItem('activeProgressSession', this.currentProgressSession);
        localStorage.setItem('activeProgressPhase', phase);
        
        this.progressUpdateInterval = setInterval(() => {
            this.checkProgress();
        }, 1000); // Poll every second
    }
    
    /**
     * Stop progress polling
     */
    stopProgressPolling() {
        if (this.progressUpdateInterval) {
            clearInterval(this.progressUpdateInterval);
            this.progressUpdateInterval = null;
        }
        
        // Clear localStorage when stopping
        localStorage.removeItem('activeProgressSession');
        localStorage.removeItem('activeProgressPhase');
    }
    
    /**
     * Resume progress tracking after page refresh
     */
    async resumeProgressTracking() {
        if (!this.currentProgressSession || !this.currentPhase) {
            return;
        }
        
        try {
            // Check if the process is still running
            const response = await fetch(`/api/colmap/progress/${this.currentProgressSession}`);
            
            if (response.ok) {
                const progress = await response.json();
                
                if (progress.completed) {
                    // Process already completed, clean up
                    this.onProcessComplete();
                    return;
                }
                
                // Process is still running, resume UI and polling
                this.resumeProgressUI();
                this.startProgressPolling(this.currentPhase);
                
                Utils.showToast(`📡 Resumed tracking ${this.currentPhase.replace('_', ' ')}...`, 'info');
            } else {
                // Session not found or error, clean up
                this.cleanupProgressState();
            }
        } catch (error) {
            console.error('Error resuming progress tracking:', error);
            this.cleanupProgressState();
        }
    }
    
    /**
     * Resume progress UI elements after page refresh
     */
    resumeProgressUI() {
        const phase = this.currentPhase;
        
        if (phase === 'feature_extraction') {
            // Show progress container
            const progressContainer = document.getElementById('featureProgress');
            if (progressContainer) {
                progressContainer.style.display = 'block';
            }
            
            // Update button state
            const featureBtn = document.getElementById('featureExtractionBtn');
            if (featureBtn) {
                featureBtn.disabled = true;
                featureBtn.textContent = '⏳ Extracting features...';
            }
        } else if (phase === 'sparse_reconstruction') {
            // Show progress container
            const progressContainer = document.getElementById('sparseProgress');
            if (progressContainer) {
                progressContainer.style.display = 'block';
            }
            
            // Update button state
            const sparseBtn = document.getElementById('sparseReconstructionBtn');
            if (sparseBtn) {
                sparseBtn.disabled = true;
                sparseBtn.textContent = '⏳ Reconstructing...';
            }
        }
    }
    
    /**
     * Clean up progress tracking state
     */
    cleanupProgressState() {
        this.currentProgressSession = null;
        this.currentPhase = null;
        localStorage.removeItem('activeProgressSession');
        localStorage.removeItem('activeProgressPhase');
    }
    
    /**
     * Check current progress and update UI
     */
    async checkProgress() {
        if (!this.currentProgressSession) {
            return;
        }
        
        try {
            const response = await fetch(`/api/colmap/progress/${this.currentProgressSession}`);
            const progress = await response.json();
            
            if (response.ok) {
                this.updateProgressUI(progress);
                
                // Check if completed
                if (progress.completed) {
                    this.stopProgressPolling();
                    this.onProcessComplete();
                }
            } else {
                console.error('Progress check failed:', progress);
            }
        } catch (error) {
            console.error('Error checking progress:', error);
        }
    }
    
    /**
     * Update progress UI elements with enhanced legacy-style tracking
     */
    updateProgressUI(progress) {
        const phase = this.currentPhase || 'feature_extraction';
        const progressData = progress.progress?.[phase];
        if (!progressData) return;
        
        console.log(`Updating progress UI for ${phase}:`, progressData);
        
        if (phase === 'feature_extraction') {
            // Ensure progress container is visible
            const progressContainer = document.getElementById('featureProgress');
            if (progressContainer) {
                progressContainer.style.display = 'block';
            }
            
            // Update progress bar fill
            const progressFill = document.querySelector('#featureProgress .progress-fill');
            if (progressFill) {
                progressFill.style.width = `${progressData.percent}%`;
            }
            
            // Update progress percentage
            const progressPercentage = document.querySelector('#featureProgress .progress-percentage');
            if (progressPercentage) {
                progressPercentage.textContent = `${progressData.percent}%`;
            }
            
            // Update progress details
            const progressDetails = document.getElementById('featureDetails');
            if (progressDetails) {
                if (progressData.total > 0) {
                    progressDetails.textContent = `Processed ${progressData.current}/${progressData.total} images`;
                } else {
                    progressDetails.textContent = `Processed ${progressData.current} images`;
                }
            }
            
            // Update button text with progress
            const featureBtn = document.getElementById('featureExtractionBtn');
            if (featureBtn && progressData.percent > 0) {
                featureBtn.textContent = `⏳ Extracting features... ${progressData.percent}%`;
            }
            
        } else if (phase === 'sparse_reconstruction') {
            // Ensure progress container is visible
            const progressContainer = document.getElementById('sparseProgress');
            if (progressContainer) {
                progressContainer.style.display = 'block';
            }
            
            // Update progress bar fill
            const progressFill = document.querySelector('#sparseProgress .progress-fill');
            if (progressFill) {
                progressFill.style.width = `${progressData.percent}%`;
            }
            
            // Update progress percentage
            const progressPercentage = document.querySelector('#sparseProgress .progress-percentage');
            if (progressPercentage) {
                progressPercentage.textContent = `${progressData.percent}%`;
            }
            
            // Update progress details
            const progressDetails = document.getElementById('sparseDetails');
            if (progressDetails) {
                if (progressData.total > 0) {
                    progressDetails.textContent = `Registered ${progressData.current}/${progressData.total} images`;
                } else {
                    progressDetails.textContent = `Registered ${progressData.current} images`;
                }
            }
            
            // Update button text with progress
            const sparseBtn = document.getElementById('sparseReconstructionBtn');
            if (sparseBtn && progressData.percent > 0) {
                sparseBtn.textContent = `⏳ Reconstructing... ${progressData.percent}%`;
            }
        }
        
        // Update elapsed time for any phase
        const progressTimeElement = document.querySelector(`#${phase === 'feature_extraction' ? 'featureProgress' : 'sparseProgress'} .progress-time`);
        if (progressTimeElement && progress.start_time) {
            const startTime = new Date(progress.start_time);
            const elapsed = Math.floor((Date.now() - startTime.getTime()) / 1000);
            const minutes = Math.floor(elapsed / 60);
            const seconds = elapsed % 60;
            progressTimeElement.textContent = `Elapsed: ${minutes}:${seconds.toString().padStart(2, '0')}`;
        }
    }
    
    /**
     * Handle process completion for any phase
     */
    onProcessComplete() {
        const phase = this.currentPhase || 'feature_extraction';
        
        if (phase === 'feature_extraction') {
            Utils.showToast('✅ Feature extraction completed successfully!', 'success');
            
            // Update workflow status
            const featureStatus = document.getElementById('featureStatus');
            if (featureStatus) {
                featureStatus.textContent = '✅';
            }
            
            // Hide progress bar
            const progressContainer = document.getElementById('featureProgress');
            if (progressContainer) {
                progressContainer.style.display = 'none';
            }
            
            // Reset button state
            const featureBtn = document.getElementById('featureExtractionBtn');
            if (featureBtn) {
                featureBtn.disabled = false;
                featureBtn.textContent = '🔍 Extract & Match Features';
            }
            
            // Enable next step button
            const sparseBtn = document.getElementById('sparseReconstructionBtn');
            if (sparseBtn) {
                sparseBtn.disabled = false;
            }
        } else if (phase === 'sparse_reconstruction') {
            Utils.showToast('✅ Sparse reconstruction completed successfully!', 'success');
            
            // Update workflow status
            const sparseStatus = document.getElementById('sparseStatus');
            if (sparseStatus) {
                sparseStatus.textContent = '✅';
            }
            
            // Hide progress bar
            const progressContainer = document.getElementById('sparseProgress');
            if (progressContainer) {
                progressContainer.style.display = 'none';
            }
            
            // Reset button state
            const sparseBtn = document.getElementById('sparseReconstructionBtn');
            if (sparseBtn) {
                sparseBtn.disabled = false;
                sparseBtn.textContent = '🏗️ Sparse Reconstruction';
            }
            
            // Analyze and display available models
            this.analyzeAndDisplayModels();
            
            // Enable next step button
            const denseBtn = document.getElementById('denseReconstructionBtn');
            if (denseBtn) {
                denseBtn.disabled = false;
            }
        }
        
        this.cleanupProgressState();
    }
    
    /**
     * Analyze and display available sparse reconstruction models
     */
    async analyzeAndDisplayModels() {
        try {
            const projectDir = this.currentProjectDir || '/home/andrew/nvr/colmap_projects/current_reconstruction';
            
            Utils.showToast('🔍 Analyzing reconstruction models...', 'info');
            
            const response = await fetch(`/api/colmap/analyze-models?project_dir=${encodeURIComponent(projectDir)}`);
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.displayModelList(result.models, result.best_model);
                
                if (result.models.length > 0) {
                    Utils.showToast(`✅ Found ${result.models.length} reconstruction models. Best: Model ${result.best_model}`, 'success');
                } else {
                    Utils.showToast('⚠️ No valid reconstruction models found', 'warning');
                }
            } else {
                throw new Error(result.error || 'Failed to analyze models');
            }
        } catch (error) {
            console.error('Model analysis error:', error);
            Utils.showToast(`❌ Failed to analyze models: ${error.message}`, 'error');
        }
    }
    
    /**
     * Display the list of available models in the UI
     */
    displayModelList(models, bestModel) {
        console.log('displayModelList called with:', models.length, 'models, best:', bestModel);
        
        // Use the existing modelList container from the HTML template
        let modelContainer = document.getElementById('modelList');
        console.log('Found modelList container:', modelContainer);
        
        if (!modelContainer) {
            console.error('modelList container not found in DOM');
            return;
        }
        
        // Show the model selection section
        const modelSelectionSection = document.getElementById('modelSelection');
        if (modelSelectionSection) {
            modelSelectionSection.style.display = 'block';
            console.log('Showed model-selection section');
        }
        
        // Clear existing content
        modelContainer.innerHTML = '';
        
        if (models.length === 0) {
            modelContainer.innerHTML = '<p class="no-models">No reconstruction models found</p>';
            return;
        }
        
        // Create models HTML
        let modelsHTML = `
            <div class="models-summary">
                <p><strong>Found ${models.length} reconstruction models</strong> • Best: <strong>Model ${bestModel}</strong> 🏆</p>
            </div>
            <div class="models-grid">
        `;
        
        models.forEach(model => {
            const qualityColors = {
                'excellent': '#28a745',
                'good': '#17a2b8', 
                'fair': '#ffc107',
                'poor': '#dc3545'
            };
            const qualityColor = qualityColors[model.quality] || '#6c757d';
            const isRecommended = model.model_id === bestModel;
            
            modelsHTML += `
                <div class="model-card ${isRecommended ? 'recommended' : ''}" style="border-left: 4px solid ${qualityColor};">
                    <div class="model-header">
                        <h4>Model ${model.model_id} ${isRecommended ? '🏆' : ''}</h4>
                        <span class="quality-badge" style="background: ${qualityColor};">${model.quality.toUpperCase()}</span>
                    </div>
                    <div class="model-stats">
                        <div class="stat-row">
                            <span>Registered Images:</span>
                            <strong>${model.registered_images}/${model.images}</strong>
                        </div>
                        <div class="stat-row">
                            <span>3D Points:</span>
                            <strong>${model.points.toLocaleString()}</strong>
                        </div>
                        <div class="stat-row">
                            <span>Reprojection Error:</span>
                            <strong>${model.mean_reprojection_error.toFixed(2)}px</strong>
                        </div>
                        <div class="stat-row">
                            <span>Track Length:</span>
                            <strong>${model.mean_track_length.toFixed(1)}</strong>
                        </div>
                        <div class="stat-row">
                            <span>Observations:</span>
                            <strong>${model.observations.toLocaleString()}</strong>
                        </div>
                    </div>
                    <div class="model-actions">
                        <button class="btn-primary" onclick="window.colmapManager.selectModel('${model.model_id}')" style="background: ${qualityColor};">
                            Select for Dense Reconstruction
                        </button>
                    </div>
                </div>
            `;
        });
        
        modelsHTML += '</div>';
        modelContainer.innerHTML = modelsHTML;
        
        console.log('Model list populated successfully');
    }
    
    /**
     * Get quality badge HTML for a model
     */
    getQualityBadge(quality) {
        const badges = {
            'excellent': '<span class="quality-badge excellent">⭐ Excellent</span>',
            'good': '<span class="quality-badge good">👍 Good</span>',
            'fair': '<span class="quality-badge fair">⚠️ Fair</span>',
            'poor': '<span class="quality-badge poor">❌ Poor</span>',
            'unknown': '<span class="quality-badge unknown">❓ Unknown</span>'
        };
        return badges[quality] || badges['unknown'];
    }
    
    /**
     * Select a specific model for dense reconstruction
     */
    async selectModel(modelId) {
        try {
            const projectDir = this.currentProjectDir || '/home/andrew/nvr/colmap_projects/current_reconstruction';
            
            const response = await fetch('/api/colmap/select-model', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    project_dir: projectDir,
                    model_id: modelId
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.status === 'success') {
                Utils.showToast(`✅ Selected Model ${modelId} for dense reconstruction`, 'success');
                
                // Update UI to show selection
                document.querySelectorAll('.model-card').forEach(card => {
                    card.classList.remove('selected');
                });
                
                document.querySelector(`[onclick*="${modelId}"]`)?.closest('.model-card')?.classList.add('selected');
            } else {
                throw new Error(result.error || 'Failed to select model');
            }
        } catch (error) {
            console.error('Model selection error:', error);
            Utils.showToast(`❌ Failed to select model: ${error.message}`, 'error');
        }
    }
    
    /**
     * Check for existing models on initialization
     */
    async checkForExistingModels() {
        try {
            const projectDir = this.currentProjectDir || '/home/andrew/nvr/colmap_projects/current_reconstruction';
            
            // Wait a bit to ensure UI is loaded
            setTimeout(async () => {
                console.log('Checking for existing models...');
                
                // First check if we have processed data (database.db indicates feature extraction completed)
                await this.checkWorkflowStatus(projectDir);
                
                // Then check for models (indicates sparse reconstruction completed)
                const response = await fetch(`/api/colmap/analyze-models?project_dir=${encodeURIComponent(projectDir)}`);
                const result = await response.json();
                
                console.log('Model analysis response:', result);
                
                if (response.ok && result.success && result.models.length > 0) {
                    console.log(`Found ${result.models.length} existing reconstruction models`);
                    console.log('Best model:', result.best_model);
                    this.displayModelList(result.models, result.best_model);
                    
                    // Update workflow status to show sparse reconstruction is complete
                    this.updateWorkflowStatus('sparse_reconstruction', true);
                    
                    // Enable dense reconstruction button
                    const denseBtn = document.getElementById('denseReconstructionBtn');
                    if (denseBtn) {
                        denseBtn.disabled = false;
                    }
                } else {
                    console.log('No models found or API error:', result);
                }
            }, 1000);
        } catch (error) {
            // Silently fail - models might not exist yet
            console.log('No existing models found:', error.message);
        }
    }
    
    /**
     * Check the status of various workflow steps
     */
    async checkWorkflowStatus(projectDir) {
        try {
            // Check for database.db (indicates feature extraction completed)
            const dbResponse = await fetch(`/api/colmap/check-file?project_dir=${encodeURIComponent(projectDir)}&file=database.db`);
            if (dbResponse.ok) {
                const dbResult = await dbResponse.json();
                if (dbResult.exists) {
                    console.log('Found database.db - feature extraction completed');
                    this.updateWorkflowStatus('feature_extraction', true);
                    
                    // Enable sparse reconstruction button
                    const sparseBtn = document.getElementById('sparseReconstructionBtn');
                    if (sparseBtn) {
                        sparseBtn.disabled = false;
                    }
                }
            }
            
            // Check for images directory (indicates frame extraction completed)
            const imagesResponse = await fetch(`/api/colmap/check-file?project_dir=${encodeURIComponent(projectDir)}&file=images`);
            if (imagesResponse.ok) {
                const imagesResult = await imagesResponse.json();
                if (imagesResult.exists && imagesResult.count > 0) {
                    console.log(`Found ${imagesResult.count} images - frame extraction completed`);
                    this.updateWorkflowStatus('frame_extraction', true);
                    
                    // Enable feature extraction button
                    const featureBtn = document.getElementById('featureExtractionBtn');
                    if (featureBtn) {
                        featureBtn.disabled = false;
                    }
                }
            }
            
            // First check if point cloud is already available (enabled)
            console.log('Checking if point cloud is available...');
            const hasPointCloud = await this.checkPointCloudAvailable();
            console.log('Point cloud available:', hasPointCloud);
            
            if (hasPointCloud) {
                console.log('Point cloud is available - dense reconstruction complete');
                this.updateWorkflowStatus('dense_reconstruction', true);
                
                // Clear any existing dense reconstruction polling
                if (this.denseProgressInterval) {
                    console.log('Clearing dense reconstruction polling interval');
                    clearInterval(this.denseProgressInterval);
                    this.denseProgressInterval = null;
                }
                
                // Enable point cloud button and show as ready
                const enablePointCloudBtn = document.getElementById('enablePointCloudBtn');
                if (enablePointCloudBtn) {
                    enablePointCloudBtn.textContent = '✅ Point Cloud Available';
                    enablePointCloudBtn.disabled = true;
                }
                
                // Clear any "checking status" messages
                const denseStatus = document.getElementById('denseStatus');
                if (denseStatus) {
                    denseStatus.textContent = '✅';
                    denseStatus.className = 'processing-status completed';
                    denseStatus.style.color = '#28a745';
                }
                
                const progressContainer = document.getElementById('denseProgress');
                if (progressContainer) {
                    progressContainer.style.display = 'none';
                }
                
                // Hide checking status and show complete status
                const statusChecking = document.getElementById('statusChecking');
                const statusIncomplete = document.getElementById('statusIncomplete');
                const statusComplete = document.getElementById('statusComplete');
                
                if (statusChecking) statusChecking.style.display = 'none';
                if (statusIncomplete) statusIncomplete.style.display = 'none';
                if (statusComplete) statusComplete.style.display = 'block';
                
                return; // Skip dense reconstruction status check
            }
            
            // Check for dense reconstruction directory only if point cloud not available
            const denseResponse = await fetch(`/api/colmap/check-file?project_dir=${encodeURIComponent(projectDir)}&file=dense`);
            if (denseResponse.ok) {
                const denseResult = await denseResponse.json();
                if (denseResult.exists) {
                    console.log('Found dense reconstruction directory');
                    // Only check status if we don't already have a point cloud
                    // The point cloud check above would have returned if it existed
                    this.checkDenseReconstructionStatus();
                }
            }
            
        } catch (error) {
            console.log('Error checking workflow status:', error.message);
        }
    }
    
    /**
     * Update workflow status indicators
     */
    updateWorkflowStatus(phase, completed) {
        const statusMappings = {
            'frame_extraction': 'frameStatus',
            'feature_extraction': 'featureStatus', 
            'sparse_reconstruction': 'sparseStatus',
            'dense_reconstruction': 'denseStatus'
        };
        
        const statusId = statusMappings[phase];
        console.log(`updateWorkflowStatus called: phase=${phase}, completed=${completed}, statusId=${statusId}`);
        
        if (statusId) {
            const statusElement = document.getElementById(statusId);
            console.log(`Looking for element with ID '${statusId}':`, statusElement);
            
            if (statusElement) {
                // Clear any existing content first
                statusElement.innerHTML = '';
                
                // Set the status with explicit styling
                if (completed) {
                    statusElement.innerHTML = '<span style="color: #28a745; font-size: 18px; font-weight: bold;">✅ Completed</span>';
                    statusElement.style.display = 'block';
                    statusElement.style.visibility = 'visible';
                } else {
                    statusElement.innerHTML = '<span style="color: #dc3545; font-size: 18px; font-weight: bold;">❌ Not completed</span>';
                    statusElement.style.display = 'block';
                    statusElement.style.visibility = 'visible';
                }
                
                // Force a reflow to ensure the change is visible
                statusElement.offsetHeight;
                
                console.log(`✅ Successfully updated ${phase} status to:`, completed ? '✅ Completed' : '❌ Not completed');
                console.log('Element after update:', statusElement.outerHTML);
                console.log('Element computed style:', window.getComputedStyle(statusElement));
            } else {
                console.error(`❌ Could not find status element with ID '${statusId}'`);
                
                // Try to find similar elements
                const allElements = document.querySelectorAll('[id*="Status"], [id*="status"]');
                console.log('All status-related elements found:', allElements);
            }
        } else {
            console.error(`❌ No status mapping found for phase: ${phase}`);
        }
    }
    
    /**
     * Manually trigger model analysis (for debugging)
     */
    async manualModelAnalysis() {
        console.log('Manual model analysis triggered');
        await this.analyzeAndDisplayModels();
    }
    
    /**
     * Manually check workflow status (for debugging)
     */
    async manualStatusCheck() {
        console.log('Manual status check triggered');
        const projectDir = this.currentProjectDir || '/home/andrew/nvr/colmap_projects/current_reconstruction';
        await this.checkWorkflowStatus(projectDir);
    }
    
    /**
     * Manually set feature extraction status for testing
     */
    testFeatureStatus() {
        console.log('Testing feature extraction status update...');
        this.updateWorkflowStatus('feature_extraction', true);
    }
}

// Global instance
let colmapManager;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    console.log('ColmapManager initialization check:');
    console.log('window.api exists:', !!window.api);
    console.log('window.progressTracker exists:', !!window.progressTracker);
    
    if (window.api && window.progressTracker) {
        console.log('Initializing ColmapManager...');
        window.colmapManager = new ColmapManager(window.api, window.progressTracker);
        console.log('ColmapManager initialized successfully');
        window.colmapManager.loadState();
        window.colmapManager.loadVideosFromServer();
        
        // Check workflow status to enable appropriate buttons
        const projectDir = '/home/andrew/nvr/colmap_projects/current_reconstruction';
        await window.colmapManager.checkWorkflowStatus(projectDir);
        
        // Only check dense reconstruction status if point cloud is not available
        const hasPointCloud = await window.colmapManager.checkPointCloudAvailable();
        if (!hasPointCloud) {
            // Check if dense reconstruction is currently running
            await window.colmapManager.checkDenseReconstructionStatus();
        } else {
            console.log('Point cloud already available, skipping dense reconstruction check');
        }
    } else {
        console.log('ERROR: ColmapManager not initialized - missing dependencies');
        if (!window.api) console.log('Missing: window.api');
        if (!window.progressTracker) console.log('Missing: window.progressTracker');
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ColmapManager;
}

// Make available globally
window.ColmapManager = ColmapManager;

// Global functions for template buttons
window.refreshModels = function() {
    if (window.colmapManager) {
        window.colmapManager.analyzeAndDisplayModels();
    }
};

window.loadModelAnalysis = function() {
    if (window.colmapManager) {
        window.colmapManager.analyzeAndDisplayModels();
    }
};