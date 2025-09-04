/**
 * Service Worker for Erik Image Manager
 * Provides offline caching, background sync, and performance optimization
 */

const CACHE_NAME = 'erik-image-manager-v1.0.0';
const STATIC_CACHE = 'erik-static-v1.0.0';
const DYNAMIC_CACHE = 'erik-dynamic-v1.0.0';
const IMAGE_CACHE = 'erik-images-v1.0.0';

// Files to cache immediately on install
const STATIC_ASSETS = [
    '/',
    '/static/css/main.css',
    '/static/css/components.css',
    '/static/css/images.css',
    '/static/css/colmap.css',
    '/static/css/yard-map.css',
    '/static/js/main.js',
    '/static/js/config.js',
    '/static/js/api.js',
    '/static/js/utils.js',
    '/static/js/state-manager.js',
    '/static/js/error-handler.js',
    '/static/js/test-framework.js',
    '/static/js/performance-optimizer.js',
    '/static/js/image-manager.js',
    '/static/js/colmap.js',
    '/static/js/yard-map.js'
];

// API endpoints to cache with different strategies
const CACHE_STRATEGIES = {
    // Cache first for static config
    cacheFirst: [
        '/api/config/client',
        '/api/config/environment',
        '/api/config/paths',
        '/api/config/limits'
    ],
    // Network first for dynamic data
    networkFirst: [
        '/api/images',
        '/api/cameras',
        '/api/matches',
        '/api/erik/status',
        '/api/yard-map/status'
    ],
    // Cache only for static assets
    cacheOnly: [
        '/static/'
    ],
    // Network only for real-time data
    networkOnly: [
        '/api/colmap/progress',
        '/api/yard-map/generate',
        '/api/upload'
    ]
};

// Cache duration settings (in milliseconds)
const CACHE_DURATIONS = {
    static: 24 * 60 * 60 * 1000,     // 24 hours
    config: 60 * 60 * 1000,          // 1 hour
    api: 5 * 60 * 1000,              // 5 minutes
    images: 7 * 24 * 60 * 60 * 1000  // 7 days
};

/**
 * Service Worker Install Event
 */
self.addEventListener('install', (event) => {
    console.log('Service Worker: Installing...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('Service Worker: Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                console.log('Service Worker: Installed successfully');
                return self.skipWaiting();
            })
            .catch(error => {
                console.error('Service Worker: Installation failed', error);
            })
    );
});

/**
 * Service Worker Activate Event
 */
self.addEventListener('activate', (event) => {
    console.log('Service Worker: Activating...');
    
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        // Delete old caches
                        if (cacheName !== STATIC_CACHE && 
                            cacheName !== DYNAMIC_CACHE && 
                            cacheName !== IMAGE_CACHE) {
                            console.log('Service Worker: Deleting old cache', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
            .then(() => {
                console.log('Service Worker: Activated successfully');
                return self.clients.claim();
            })
    );
});

/**
 * Service Worker Fetch Event
 */
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Skip non-GET requests and chrome-extension requests
    if (request.method !== 'GET' || url.protocol === 'chrome-extension:') {
        return;
    }
    
    // Handle different types of requests
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(handleStaticRequest(request));
    } else if (url.pathname.startsWith('/api/')) {
        event.respondWith(handleApiRequest(request));
    } else if (isImageRequest(request)) {
        event.respondWith(handleImageRequest(request));
    } else {
        event.respondWith(handlePageRequest(request));
    }
});

/**
 * Handle static asset requests (cache only)
 */
async function handleStaticRequest(request) {
    try {
        const cache = await caches.open(STATIC_CACHE);
        const cachedResponse = await cache.match(request);
        
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // If not in cache, fetch and cache
        const response = await fetch(request);
        if (response.status === 200) {
            cache.put(request, response.clone());
        }
        return response;
        
    } catch (error) {
        console.error('Service Worker: Static request failed', error);
        return new Response('Asset not available offline', { status: 503 });
    }
}

/**
 * Handle API requests with appropriate caching strategy
 */
async function handleApiRequest(request) {
    const url = new URL(request.url);
    const strategy = getApiCacheStrategy(url.pathname);
    
    switch (strategy) {
        case 'cacheFirst':
            return handleCacheFirst(request, DYNAMIC_CACHE);
        case 'networkFirst':
            return handleNetworkFirst(request, DYNAMIC_CACHE);
        case 'networkOnly':
            return handleNetworkOnly(request);
        default:
            return handleNetworkFirst(request, DYNAMIC_CACHE);
    }
}

/**
 * Handle image requests with optimized caching
 */
async function handleImageRequest(request) {
    try {
        const cache = await caches.open(IMAGE_CACHE);
        const cachedResponse = await cache.match(request);
        
        // Check if cached response is still fresh
        if (cachedResponse && isCacheFresh(cachedResponse, CACHE_DURATIONS.images)) {
            return cachedResponse;
        }
        
        // Fetch new image
        const response = await fetch(request);
        if (response.status === 200) {
            // Add timestamp header for cache validation
            const responseWithTimestamp = new Response(response.body, {
                status: response.status,
                statusText: response.statusText,
                headers: {
                    ...response.headers,
                    'sw-cached-time': Date.now().toString()
                }
            });
            cache.put(request, responseWithTimestamp.clone());
            return responseWithTimestamp;
        }
        
        // Return cached version if network fails
        if (cachedResponse) {
            return cachedResponse;
        }
        
        return response;
        
    } catch (error) {
        console.error('Service Worker: Image request failed', error);
        const cache = await caches.open(IMAGE_CACHE);
        const cachedResponse = await cache.match(request);
        return cachedResponse || new Response('Image not available offline', { status: 503 });
    }
}

/**
 * Handle page requests
 */
async function handlePageRequest(request) {
    try {
        // Try network first for pages
        const response = await fetch(request);
        
        // Cache successful responses
        if (response.status === 200) {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, response.clone());
        }
        
        return response;
        
    } catch (error) {
        // Return cached version if available
        const cache = await caches.open(DYNAMIC_CACHE);
        const cachedResponse = await cache.match(request);
        
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // Return offline page or basic error
        return new Response(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>Erik Image Manager - Offline</title>
                <style>
                    body { 
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        text-align: center; 
                        padding: 50px;
                        background: #f5f5f5;
                    }
                    .offline-message {
                        background: white;
                        padding: 40px;
                        border-radius: 8px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        max-width: 500px;
                        margin: 0 auto;
                    }
                    .retry-btn {
                        background: #007bff;
                        color: white;
                        border: none;
                        padding: 12px 24px;
                        border-radius: 4px;
                        cursor: pointer;
                        margin-top: 20px;
                    }
                </style>
            </head>
            <body>
                <div class="offline-message">
                    <h1>📡 You're Offline</h1>
                    <p>Erik Image Manager is not available right now. Please check your internet connection.</p>
                    <button class="retry-btn" onclick="location.reload()">🔄 Try Again</button>
                </div>
            </body>
            </html>
        `, {
            status: 503,
            headers: { 'Content-Type': 'text/html' }
        });
    }
}

/**
 * Cache First Strategy
 */
async function handleCacheFirst(request, cacheName) {
    try {
        const cache = await caches.open(cacheName);
        const cachedResponse = await cache.match(request);
        
        if (cachedResponse && isCacheFresh(cachedResponse, CACHE_DURATIONS.config)) {
            return cachedResponse;
        }
        
        const response = await fetch(request);
        if (response.status === 200) {
            const responseWithTimestamp = new Response(response.body, {
                status: response.status,
                statusText: response.statusText,
                headers: {
                    ...response.headers,
                    'sw-cached-time': Date.now().toString()
                }
            });
            cache.put(request, responseWithTimestamp.clone());
            return responseWithTimestamp;
        }
        
        return cachedResponse || response;
        
    } catch (error) {
        const cache = await caches.open(cacheName);
        const cachedResponse = await cache.match(request);
        return cachedResponse || new Response('Service unavailable', { status: 503 });
    }
}

/**
 * Network First Strategy
 */
async function handleNetworkFirst(request, cacheName) {
    try {
        const response = await fetch(request);
        
        if (response.status === 200) {
            const cache = await caches.open(cacheName);
            const responseWithTimestamp = new Response(response.body, {
                status: response.status,
                statusText: response.statusText,
                headers: {
                    ...response.headers,
                    'sw-cached-time': Date.now().toString()
                }
            });
            cache.put(request, responseWithTimestamp.clone());
            return responseWithTimestamp;
        }
        
        return response;
        
    } catch (error) {
        const cache = await caches.open(cacheName);
        const cachedResponse = await cache.match(request);
        return cachedResponse || new Response('Service unavailable', { status: 503 });
    }
}

/**
 * Network Only Strategy
 */
async function handleNetworkOnly(request) {
    return fetch(request);
}

/**
 * Get caching strategy for API endpoint
 */
function getApiCacheStrategy(pathname) {
    for (const [strategy, patterns] of Object.entries(CACHE_STRATEGIES)) {
        if (patterns.some(pattern => pathname.startsWith(pattern))) {
            return strategy;
        }
    }
    return 'networkFirst'; // default
}

/**
 * Check if request is for an image
 */
function isImageRequest(request) {
    return request.destination === 'image' || 
           /\.(jpg|jpeg|png|gif|webp|svg)$/i.test(request.url);
}

/**
 * Check if cached response is still fresh
 */
function isCacheFresh(response, maxAge) {
    const cachedTime = response.headers.get('sw-cached-time');
    if (!cachedTime) return false;
    
    const age = Date.now() - parseInt(cachedTime);
    return age < maxAge;
}

/**
 * Background Sync for offline actions
 */
self.addEventListener('sync', (event) => {
    console.log('Service Worker: Background sync triggered', event.tag);
    
    switch (event.tag) {
        case 'background-upload':
            event.waitUntil(handleBackgroundUpload());
            break;
        case 'config-update':
            event.waitUntil(handleConfigUpdate());
            break;
        default:
            console.log('Service Worker: Unknown sync tag', event.tag);
    }
});

/**
 * Handle background upload sync
 */
async function handleBackgroundUpload() {
    try {
        // Retrieve queued uploads from IndexedDB or other storage
        const queuedUploads = await getQueuedUploads();
        
        for (const upload of queuedUploads) {
            try {
                const formData = new FormData();
                formData.append('file', upload.file);
                
                const response = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    await removeQueuedUpload(upload.id);
                    console.log('Service Worker: Background upload completed', upload.id);
                } else {
                    console.error('Service Worker: Background upload failed', upload.id, response.status);
                }
                
            } catch (error) {
                console.error('Service Worker: Background upload error', upload.id, error);
            }
        }
        
    } catch (error) {
        console.error('Service Worker: Background upload sync failed', error);
    }
}

/**
 * Handle config update sync
 */
async function handleConfigUpdate() {
    try {
        // Refresh configuration cache
        const cache = await caches.open(DYNAMIC_CACHE);
        const configUrls = [
            '/api/config/client',
            '/api/config/environment',
            '/api/config/paths',
            '/api/config/limits'
        ];
        
        for (const url of configUrls) {
            try {
                const response = await fetch(url);
                if (response.ok) {
                    await cache.put(url, response.clone());
                    console.log('Service Worker: Config updated', url);
                }
            } catch (error) {
                console.error('Service Worker: Config update failed', url, error);
            }
        }
        
    } catch (error) {
        console.error('Service Worker: Config update sync failed', error);
    }
}

/**
 * Push notification handler
 */
self.addEventListener('push', (event) => {
    console.log('Service Worker: Push message received');
    
    const options = {
        body: 'New activity detected',
        icon: '/static/images/icons/erik-icon-192.png',
        badge: '/static/images/icons/erik-badge-72.png',
        tag: 'erik-notification',
        data: event.data ? event.data.json() : {},
        actions: [
            {
                action: 'view',
                title: 'View',
                icon: '/static/images/icons/view-icon.png'
            },
            {
                action: 'dismiss',
                title: 'Dismiss'
            }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification('Erik Image Manager', options)
    );
});

/**
 * Notification click handler
 */
self.addEventListener('notificationclick', (event) => {
    console.log('Service Worker: Notification clicked', event.action);
    
    event.notification.close();
    
    if (event.action === 'view') {
        event.waitUntil(
            clients.openWindow('/')
        );
    }
});

/**
 * Message handler for communication with main thread
 */
self.addEventListener('message', (event) => {
    console.log('Service Worker: Message received', event.data);
    
    switch (event.data.type) {
        case 'GET_CACHE_STATUS':
            handleGetCacheStatus(event);
            break;
        case 'CLEAR_CACHE':
            handleClearCache(event);
            break;
        case 'UPDATE_CONFIG':
            handleUpdateConfigMessage(event);
            break;
        default:
            console.log('Service Worker: Unknown message type', event.data.type);
    }
});

/**
 * Get cache status
 */
async function handleGetCacheStatus(event) {
    try {
        const cacheNames = await caches.keys();
        const cacheStatus = {};
        
        for (const cacheName of cacheNames) {
            const cache = await caches.open(cacheName);
            const keys = await cache.keys();
            cacheStatus[cacheName] = keys.length;
        }
        
        event.ports[0].postMessage({
            type: 'CACHE_STATUS',
            data: cacheStatus
        });
        
    } catch (error) {
        event.ports[0].postMessage({
            type: 'ERROR',
            error: error.message
        });
    }
}

/**
 * Clear cache
 */
async function handleClearCache(event) {
    try {
        const { cacheName } = event.data;
        
        if (cacheName) {
            await caches.delete(cacheName);
        } else {
            const cacheNames = await caches.keys();
            await Promise.all(cacheNames.map(name => caches.delete(name)));
        }
        
        event.ports[0].postMessage({
            type: 'CACHE_CLEARED',
            cacheName
        });
        
    } catch (error) {
        event.ports[0].postMessage({
            type: 'ERROR',
            error: error.message
        });
    }
}

/**
 * Handle config update message
 */
async function handleUpdateConfigMessage(event) {
    try {
        await handleConfigUpdate();
        
        event.ports[0].postMessage({
            type: 'CONFIG_UPDATED'
        });
        
    } catch (error) {
        event.ports[0].postMessage({
            type: 'ERROR',
            error: error.message
        });
    }
}

// Utility functions for IndexedDB operations (simplified)
async function getQueuedUploads() {
    // Implementation would use IndexedDB to retrieve queued uploads
    return [];
}

async function removeQueuedUpload(id) {
    // Implementation would use IndexedDB to remove completed upload
    console.log('Removing queued upload:', id);
}

console.log('Service Worker: Loaded successfully');