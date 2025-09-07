// Process Status Monitoring for COLMAP
let processMonitorInterval = null;

window.startProcessMonitoring = function() {
    // Clear any existing interval
    if (processMonitorInterval) {
        clearInterval(processMonitorInterval);
    }
    
    // Update immediately
    updateProcessStatus();
    
    // Then update every 2 seconds
    processMonitorInterval = setInterval(updateProcessStatus, 2000);
};

window.stopProcessMonitoring = function() {
    if (processMonitorInterval) {
        clearInterval(processMonitorInterval);
        processMonitorInterval = null;
    }
    // Hide the monitor
    const monitor = document.getElementById('processStatusMonitor');
    if (monitor) {
        monitor.style.display = 'none';
    }
};

async function updateProcessStatus() {
    try {
        const response = await fetch('/api/colmap/process-status');
        const data = await response.json();
        
        if (data.success) {
            const monitor = document.getElementById('processStatusMonitor');
            const statusList = document.getElementById('processStatusList');
            
            if (data.processes.length > 0) {
                // Show monitor
                if (monitor) {
                    monitor.style.display = 'block';
                }
                
                // Build status HTML
                let html = '<div style="display: grid; gap: 10px;">';
                
                data.processes.forEach(proc => {
                    const typeEmoji = {
                        'feature_extraction': '🔍',
                        'feature_matching': '🔗',
                        'sparse_reconstruction': '🏗️',
                        'dense_stereo': '🌟',
                        'dense_fusion': '🔮',
                        'unknown': '❓'
                    }[proc.type] || '❓';
                    
                    const typeLabel = proc.type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    
                    html += `
                        <div style="background: white; padding: 10px; border-radius: 5px; border-left: 4px solid #007bff;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span><strong>${typeEmoji} ${typeLabel}</strong></span>
                                <span style="color: #666;">PID: ${proc.pid}</span>
                            </div>
                            <div style="margin-top: 5px; font-size: 0.85em; color: #666;">
                                <span>CPU: ${proc.cpu_percent}%</span> | 
                                <span>Memory: ${proc.memory_percent}%</span> | 
                                <span>Runtime: ${proc.runtime_formatted}</span>
                            </div>
                        </div>
                    `;
                });
                
                // Add sparse reconstruction progress if available
                if (data.sparse_images_registered > 0) {
                    const percent = Math.round((data.sparse_images_registered / 606) * 100);
                    html += `
                        <div style="background: #d4edda; padding: 10px; border-radius: 5px; border-left: 4px solid #28a745;">
                            <div><strong>📊 Sparse Reconstruction Progress</strong></div>
                            <div style="margin-top: 5px;">
                                <div style="background: #e9ecef; border-radius: 10px; height: 20px; overflow: hidden;">
                                    <div style="background: linear-gradient(90deg, #28a745, #34ce57); height: 100%; width: ${percent}%; transition: width 0.5s;"></div>
                                </div>
                                <div style="margin-top: 5px; font-size: 0.85em; color: #666;">
                                    Registered ${data.sparse_images_registered} / 606 images (${percent}%)
                                </div>
                            </div>
                        </div>
                    `;
                }
                
                // Add progress bars for active phases
                if (data.progress && data.progress.progress) {
                    Object.entries(data.progress.progress).forEach(([phase, info]) => {
                        if (info.percent > 0 || (data.progress.current_phase === phase)) {
                            const phaseEmoji = {
                                'feature_extraction': '🔍',
                                'feature_matching': '🔗',
                                'sparse_reconstruction': '🏗️',
                                'dense_reconstruction': '🌟'
                            }[phase] || '❓';
                            
                            const phaseLabel = phase.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                            
                            html += `
                                <div style="background: #fff3cd; padding: 10px; border-radius: 5px; border-left: 4px solid #ffc107;">
                                    <div><strong>${phaseEmoji} ${phaseLabel} Progress</strong></div>
                                    <div style="margin-top: 5px;">
                                        <div style="background: #e9ecef; border-radius: 10px; height: 15px; overflow: hidden;">
                                            <div style="background: linear-gradient(90deg, #ffc107, #ffdc73); height: 100%; width: ${info.percent}%; transition: width 0.5s;"></div>
                                        </div>
                                        <div style="margin-top: 5px; font-size: 0.85em; color: #666;">
                                            ${info.current} / ${info.total || '?'} (${info.percent}%)
                                        </div>
                                    </div>
                                </div>
                            `;
                        }
                    });
                }
                
                html += '</div>';
                
                if (statusList) {
                    statusList.innerHTML = html;
                }
            } else {
                // No processes running
                if (monitor) {
                    monitor.style.display = 'none';
                }
            }
        }
    } catch (error) {
        console.error('Error updating process status:', error);
    }
}

// Auto-start monitoring when on reconstruction tab
document.addEventListener('DOMContentLoaded', function() {
    // Start monitoring when reconstruction tab is shown
    const observer = new MutationObserver(function(mutations) {
        const reconstructTab = document.getElementById('reconstruct-config-tab');
        if (reconstructTab && reconstructTab.style.display !== 'none') {
            startProcessMonitoring();
        } else {
            stopProcessMonitoring();
        }
    });
    
    // Observe the reconstruction tab for display changes
    const reconstructTab = document.getElementById('reconstruct-config-tab');
    if (reconstructTab) {
        observer.observe(reconstructTab, { attributes: true, attributeFilter: ['style'] });
    }
    
    // Also check if we're already on the reconstruction tab
    if (window.location.hash === '#reconstruct' || window.location.hash === '#reconstruction') {
        setTimeout(startProcessMonitoring, 100);
    }
});