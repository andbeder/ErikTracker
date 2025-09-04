/**
 * Utility functions for the Erik Image Manager
 * Shared utility functions used across different modules
 */

class Utils {
    /**
     * Format file size in bytes to human readable format
     * @param {number} bytes - Size in bytes
     * @returns {string} Formatted size string
     */
    static formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Show toast notification
     * @param {string} message - Message to display
     * @param {string} type - Type of notification (success, error, info, warning)
     */
    static showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 10000;
            animation: slideIn 0.3s ease-out;
            max-width: 400px;
        `;
        
        // Set background based on type
        const backgrounds = {
            'success': 'linear-gradient(135deg, #28a745 0%, #20c997 100%)',
            'error': 'linear-gradient(135deg, #dc3545 0%, #c82333 100%)',
            'info': 'linear-gradient(135deg, #007bff 0%, #0056b3 100%)',
            'warning': 'linear-gradient(135deg, #ffc107 0%, #e0a800 100%)'
        };
        toast.style.background = backgrounds[type] || backgrounds['info'];
        
        toast.textContent = message;
        document.body.appendChild(toast);
        
        // Auto-remove after 4 seconds
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => {
                if (document.body.contains(toast)) {
                    document.body.removeChild(toast);
                }
            }, 300);
        }, 4000);
    }

    /**
     * Show notification (alias for showToast)
     * @param {string} message - Message to display
     * @param {string} type - Type of notification
     */
    static showNotification(message, type = 'info') {
        this.showToast(message, type);
    }

    /**
     * Create a modal dialog
     * @param {string} title - Modal title
     * @returns {HTMLElement} Modal element
     */
    static createModal(title) {
        // Remove existing modal if any
        const existingModal = document.getElementById('configModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        const modal = document.createElement('div');
        modal.id = 'configModal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>${title}</h3>
                    <span class="close">&times;</span>
                </div>
                <div class="modal-body"></div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Close modal on X click
        modal.querySelector('.close').onclick = function() {
            modal.style.display = 'none';
        };
        
        // Close modal on outside click
        modal.onclick = function(event) {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        };
        
        return modal;
    }

    /**
     * Close the current modal
     */
    static closeModal() {
        const modal = document.getElementById('configModal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    /**
     * Setup auto-refresh for an image element
     * @param {string} elementId - ID of the image element
     * @param {string} baseUrl - Base URL for the image
     * @param {number} interval - Refresh interval in milliseconds (default: 1000)
     */
    static setupImageRefresh(elementId, baseUrl, interval = 1000) {
        const img = document.getElementById(elementId);
        if (!img) return;
        
        function refreshImage() {
            const timestamp = Date.now();
            img.src = `${baseUrl}?t=${timestamp}`;
        }
        
        // Initial load
        refreshImage();
        
        // Set up interval
        const refreshInterval = setInterval(refreshImage, interval);
        
        // Handle image load errors
        img.onerror = function() {
            // Retry after 5 seconds if image fails to load
            setTimeout(refreshImage, 5000);
        };
        
        return refreshInterval;
    }

    /**
     * Update processing step indicator
     * @param {string} stepId - ID of the step element
     * @param {string} status - Status: 'active', 'completed', 'error'
     */
    static updateProcessingStep(stepId, status) {
        const step = document.getElementById(stepId);
        if (!step) return;
        
        step.className = `processing-step ${status}`;
        
        if (status === 'completed') {
            step.innerHTML = step.innerHTML.replace(/[📸🔍🔗📐🎯]/g, '✅');
        } else if (status === 'active') {
            // Add loading animation
            const icon = step.innerHTML.charAt(0);
            step.innerHTML = step.innerHTML.replace(icon, '⏳');
        } else if (status === 'error') {
            const icon = step.innerHTML.charAt(0);
            step.innerHTML = step.innerHTML.replace(icon, '❌');
        }
    }

    /**
     * Reset processing steps to initial state
     * @param {string[]} stepIds - Array of step element IDs
     */
    static resetProcessingSteps(stepIds = ['captureStep', 'featuresStep', 'matchStep', 'poseStep', 'transformStep']) {
        stepIds.forEach(stepId => {
            const step = document.getElementById(stepId);
            if (step) {
                step.className = 'processing-step';
            }
        });
    }

    /**
     * Get current timestamp in milliseconds
     * @returns {number} Current timestamp
     */
    static getCurrentTimestamp() {
        return Date.now();
    }

    /**
     * Format timestamp to locale time string
     * @param {number|Date} timestamp - Timestamp or Date object
     * @returns {string} Formatted time string
     */
    static formatTimestamp(timestamp) {
        const date = timestamp instanceof Date ? timestamp : new Date(timestamp);
        return date.toLocaleTimeString();
    }

    /**
     * Debounce function calls
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @param {boolean} immediate - Whether to execute immediately
     * @returns {Function} Debounced function
     */
    static debounce(func, wait, immediate = false) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func(...args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func(...args);
        };
    }

    /**
     * Throttle function calls
     * @param {Function} func - Function to throttle
     * @param {number} limit - Time limit in milliseconds
     * @returns {Function} Throttled function
     */
    static throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    /**
     * Generate unique ID
     * @returns {string} Unique ID
     */
    static generateId() {
        return 'id-' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * Check if element exists in DOM
     * @param {string} id - Element ID
     * @returns {boolean} True if element exists
     */
    static elementExists(id) {
        return document.getElementById(id) !== null;
    }

    /**
     * Safe element operation - only execute if element exists
     * @param {string} id - Element ID
     * @param {Function} callback - Function to execute with the element
     */
    static safeElementOperation(id, callback) {
        const element = document.getElementById(id);
        if (element && typeof callback === 'function') {
            callback(element);
        }
    }

    /**
     * Deep clone an object
     * @param {Object} obj - Object to clone
     * @returns {Object} Cloned object
     */
    static deepClone(obj) {
        return JSON.parse(JSON.stringify(obj));
    }

    /**
     * Check if value is empty (null, undefined, empty string, empty array)
     * @param {*} value - Value to check
     * @returns {boolean} True if empty
     */
    static isEmpty(value) {
        return value === null || 
               value === undefined || 
               value === '' || 
               (Array.isArray(value) && value.length === 0) ||
               (typeof value === 'object' && Object.keys(value).length === 0);
    }
}

// Add CSS animations for toast notifications if not already present
if (!document.querySelector('#utils-animations')) {
    const style = document.createElement('style');
    style.id = 'utils-animations';
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
    `;
    document.head.appendChild(style);
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Utils;
}

// Make available globally
window.Utils = Utils;