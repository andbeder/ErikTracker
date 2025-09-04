/**
 * Service Worker Management System for Erik Image Manager
 * Handles registration, updates, and communication with service worker
 */

class ServiceWorkerManager {
    constructor() {
        this.registration = null;
        this.isOnline = navigator.onLine;
        this.updateAvailable = false;
        this.logger = window.logger;
        this.messageChannel = null;
        
        this.initializeServiceWorker();
        this.setupOnlineOfflineHandlers();
    }

    /**
     * Initialize service worker if supported
     */
    async initializeServiceWorker() {
        if (!('serviceWorker' in navigator)) {
            this.logger?.warn('Service Worker not supported');
            return;
        }

        try {
            this.registration = await navigator.serviceWorker.register('/static/js/service-worker.js', {
                scope: '/'
            });

            this.logger?.info('Service Worker registered successfully');

            // Handle service worker updates
            this.registration.addEventListener('updatefound', () => {
                this.handleServiceWorkerUpdate();
            });

            // Check if service worker is already active
            if (this.registration.active) {
                this.setupMessageChannel();
            }

            // Listen for service worker state changes
            if (this.registration.installing) {
                this.trackServiceWorkerState(this.registration.installing);
            }

            // Check for updates periodically
            setInterval(() => {
                this.checkForUpdates();
            }, 60000); // Check every minute

        } catch (error) {
            this.logger?.error('Service Worker registration failed:', error);
        }
    }

    /**
     * Handle service worker updates
     */
    handleServiceWorkerUpdate() {
        const installingWorker = this.registration.installing;
        
        if (installingWorker) {
            this.trackServiceWorkerState(installingWorker);
        }

        this.updateAvailable = true;
        this.showUpdateNotification();
    }

    /**
     * Track service worker state changes
     */
    trackServiceWorkerState(worker) {
        worker.addEventListener('statechange', () => {
            this.logger?.info('Service Worker state changed:', worker.state);

            if (worker.state === 'installed') {
                if (navigator.serviceWorker.controller) {
                    // New service worker installed, update available
                    this.updateAvailable = true;
                    this.showUpdateNotification();
                } else {
                    // First time installation
                    this.logger?.info('Service Worker installed for first time');
                    this.setupMessageChannel();
                }
            }

            if (worker.state === 'activated') {
                this.logger?.info('Service Worker activated');
                this.setupMessageChannel();
            }
        });
    }

    /**
     * Setup message channel for communication
     */
    setupMessageChannel() {
        if (this.messageChannel) return;

        this.messageChannel = new MessageChannel();
        
        // Handle messages from service worker
        this.messageChannel.port1.addEventListener('message', (event) => {
            this.handleServiceWorkerMessage(event);
        });
        
        this.messageChannel.port1.start();

        // Send port to service worker
        if (navigator.serviceWorker.controller) {
            navigator.serviceWorker.controller.postMessage({
                type: 'INIT_PORT'
            }, [this.messageChannel.port2]);
        }
    }

    /**
     * Handle messages from service worker
     */
    handleServiceWorkerMessage(event) {
        const { type, data, error } = event.data;

        switch (type) {
            case 'CACHE_STATUS':
                this.handleCacheStatus(data);
                break;
            case 'CACHE_CLEARED':
                this.handleCacheCleared(data);
                break;
            case 'CONFIG_UPDATED':
                this.handleConfigUpdated();
                break;
            case 'ERROR':
                this.logger?.error('Service Worker error:', error);
                break;
            default:
                this.logger?.debug('Unknown service worker message:', type);
        }
    }

    /**
     * Show update notification to user
     */
    showUpdateNotification() {
        if (!window.Utils || typeof window.Utils.createModal !== 'function') {
            // Fallback notification
            if (confirm('A new version is available. Reload to update?')) {
                this.skipWaiting();
            }
            return;
        }

        const content = `
            <div style="text-align: center; padding: 20px;">
                <h3 style="color: #007bff; margin-bottom: 15px;">🚀 Update Available</h3>
                <p>A new version of Erik Image Manager is ready to install.</p>
                <p>The update includes performance improvements and bug fixes.</p>
                <div style="margin-top: 20px;">
                    <button onclick="window.serviceWorkerManager.skipWaiting()" 
                            style="background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-right: 10px;">
                        ✨ Update Now
                    </button>
                    <button onclick="window.serviceWorkerManager.dismissUpdate()" 
                            style="background: #6c757d; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">
                        ⏰ Later
                    </button>
                </div>
            </div>
        `;

        window.Utils.createModal('Update Available', content, false);
    }

    /**
     * Skip waiting and activate new service worker
     */
    skipWaiting() {
        if (this.registration && this.registration.waiting) {
            this.registration.waiting.postMessage({ type: 'SKIP_WAITING' });
            
            // Reload page after activation
            navigator.serviceWorker.addEventListener('controllerchange', () => {
                window.location.reload();
            });
        }
    }

    /**
     * Dismiss update notification
     */
    dismissUpdate() {
        // Close any open modals
        const modal = document.querySelector('.modal');
        if (modal) {
            modal.remove();
        }
        
        this.logger?.info('Service Worker update dismissed');
    }

    /**
     * Check for service worker updates
     */
    async checkForUpdates() {
        if (this.registration) {
            try {
                await this.registration.update();
            } catch (error) {
                this.logger?.debug('Service Worker update check failed:', error);
            }
        }
    }

    /**
     * Setup online/offline event handlers
     */
    setupOnlineOfflineHandlers() {
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.handleOnline();
        });

        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.handleOffline();
        });

        // Check connection status
        this.checkConnectionStatus();
    }

    /**
     * Handle online event
     */
    handleOnline() {
        this.logger?.info('Connection restored');
        
        // Update UI to show online status
        this.updateConnectionStatus(true);
        
        // Sync any pending data
        this.syncPendingData();
        
        // Update configuration cache
        this.updateConfigCache();
    }

    /**
     * Handle offline event
     */
    handleOffline() {
        this.logger?.warn('Connection lost');
        
        // Update UI to show offline status
        this.updateConnectionStatus(false);
        
        // Show offline notification
        this.showOfflineNotification();
    }

    /**
     * Update connection status in UI
     */
    updateConnectionStatus(isOnline) {
        // Create or update status indicator
        let statusIndicator = document.getElementById('connection-status');
        
        if (!statusIndicator) {
            statusIndicator = document.createElement('div');
            statusIndicator.id = 'connection-status';
            statusIndicator.style.cssText = `
                position: fixed;
                top: 10px;
                right: 10px;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                z-index: 10000;
                transition: all 0.3s ease;
            `;
            document.body.appendChild(statusIndicator);
        }

        if (isOnline) {
            statusIndicator.textContent = '🟢 Online';
            statusIndicator.style.background = '#d4edda';
            statusIndicator.style.color = '#155724';
            statusIndicator.style.border = '1px solid #c3e6cb';
            
            // Hide after 3 seconds
            setTimeout(() => {
                statusIndicator.style.opacity = '0';
                setTimeout(() => {
                    if (statusIndicator.parentNode) {
                        statusIndicator.parentNode.removeChild(statusIndicator);
                    }
                }, 300);
            }, 3000);
        } else {
            statusIndicator.textContent = '🔴 Offline';
            statusIndicator.style.background = '#f8d7da';
            statusIndicator.style.color = '#721c24';
            statusIndicator.style.border = '1px solid #f5c6cb';
            statusIndicator.style.opacity = '1';
        }
    }

    /**
     * Show offline notification
     */
    showOfflineNotification() {
        const content = `
            <div style="text-align: center; padding: 20px;">
                <h3 style="color: #dc3545; margin-bottom: 15px;">📡 You're Offline</h3>
                <p>Some features may be limited while offline.</p>
                <p>Cached content will continue to work normally.</p>
                <div style="margin-top: 20px;">
                    <button onclick="this.closest('.modal').remove()" 
                            style="background: #6c757d; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">
                        Understood
                    </button>
                </div>
            </div>
        `;

        if (window.Utils && typeof window.Utils.createModal === 'function') {
            window.Utils.createModal('Offline Mode', content, false);
        }
    }

    /**
     * Check connection status periodically
     */
    checkConnectionStatus() {
        setInterval(() => {
            const wasOnline = this.isOnline;
            this.isOnline = navigator.onLine;
            
            if (wasOnline !== this.isOnline) {
                if (this.isOnline) {
                    this.handleOnline();
                } else {
                    this.handleOffline();
                }
            }
        }, 5000);
    }

    /**
     * Sync pending data when back online
     */
    async syncPendingData() {
        if ('serviceWorker' in navigator && this.registration) {
            try {
                await this.registration.sync.register('background-sync');
                this.logger?.info('Background sync registered');
            } catch (error) {
                this.logger?.debug('Background sync not supported:', error);
            }
        }
    }

    /**
     * Update configuration cache
     */
    updateConfigCache() {
        if (this.messageChannel) {
            this.sendMessage({
                type: 'UPDATE_CONFIG'
            });
        }
    }

    /**
     * Send message to service worker
     */
    sendMessage(message) {
        if (this.messageChannel) {
            this.messageChannel.port1.postMessage(message);
        }
    }

    /**
     * Get cache status from service worker
     */
    async getCacheStatus() {
        return new Promise((resolve, reject) => {
            if (!this.messageChannel) {
                reject(new Error('Service Worker not available'));
                return;
            }

            const timeout = setTimeout(() => {
                reject(new Error('Cache status request timeout'));
            }, 5000);

            const handler = (event) => {
                if (event.data.type === 'CACHE_STATUS') {
                    clearTimeout(timeout);
                    this.messageChannel.port1.removeEventListener('message', handler);
                    resolve(event.data.data);
                } else if (event.data.type === 'ERROR') {
                    clearTimeout(timeout);
                    this.messageChannel.port1.removeEventListener('message', handler);
                    reject(new Error(event.data.error));
                }
            };

            this.messageChannel.port1.addEventListener('message', handler);
            this.sendMessage({ type: 'GET_CACHE_STATUS' });
        });
    }

    /**
     * Clear cache
     */
    async clearCache(cacheName = null) {
        return new Promise((resolve, reject) => {
            if (!this.messageChannel) {
                reject(new Error('Service Worker not available'));
                return;
            }

            const timeout = setTimeout(() => {
                reject(new Error('Clear cache request timeout'));
            }, 10000);

            const handler = (event) => {
                if (event.data.type === 'CACHE_CLEARED') {
                    clearTimeout(timeout);
                    this.messageChannel.port1.removeEventListener('message', handler);
                    resolve(event.data.cacheName);
                } else if (event.data.type === 'ERROR') {
                    clearTimeout(timeout);
                    this.messageChannel.port1.removeEventListener('message', handler);
                    reject(new Error(event.data.error));
                }
            };

            this.messageChannel.port1.addEventListener('message', handler);
            this.sendMessage({ type: 'CLEAR_CACHE', cacheName });
        });
    }

    /**
     * Handle cache status response
     */
    handleCacheStatus(data) {
        this.logger?.info('Cache Status:', data);
    }

    /**
     * Handle cache cleared response
     */
    handleCacheCleared(cacheName) {
        this.logger?.info('Cache cleared:', cacheName || 'All caches');
    }

    /**
     * Handle config updated response
     */
    handleConfigUpdated() {
        this.logger?.info('Configuration cache updated');
    }

    /**
     * Request persistent storage
     */
    async requestPersistentStorage() {
        if ('storage' in navigator && 'persist' in navigator.storage) {
            try {
                const granted = await navigator.storage.persist();
                if (granted) {
                    this.logger?.info('Persistent storage granted');
                } else {
                    this.logger?.info('Persistent storage denied');
                }
                return granted;
            } catch (error) {
                this.logger?.error('Persistent storage request failed:', error);
                return false;
            }
        }
        return false;
    }

    /**
     * Get storage usage
     */
    async getStorageUsage() {
        if ('storage' in navigator && 'estimate' in navigator.storage) {
            try {
                const estimate = await navigator.storage.estimate();
                return {
                    used: estimate.usage,
                    available: estimate.quota,
                    percentage: Math.round((estimate.usage / estimate.quota) * 100)
                };
            } catch (error) {
                this.logger?.error('Storage usage estimation failed:', error);
                return null;
            }
        }
        return null;
    }

    /**
     * Get service worker status
     */
    getStatus() {
        return {
            supported: 'serviceWorker' in navigator,
            registered: !!this.registration,
            active: !!(this.registration && this.registration.active),
            updateAvailable: this.updateAvailable,
            isOnline: this.isOnline,
            messageChannelReady: !!this.messageChannel
        };
    }
}

// Initialize global service worker manager
window.serviceWorkerManager = new ServiceWorkerManager();

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ServiceWorkerManager };
}

console.log('✅ Service Worker Manager initialized');