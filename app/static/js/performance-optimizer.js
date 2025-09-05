/**
 * Performance Optimization System for Erik Image Manager
 * Handles lazy loading, memory management, DOM optimization, and resource caching
 */

class PerformanceOptimizer {
    constructor() {
        this.logger = window.logger;
        this.observers = new Map();
        this.loadQueue = new Map();
        this.imageCache = new Map();
        this.maxImageCache = 50;
        this.thresholds = {
            memoryWarning: 100, // MB
            domElementsWarning: 1000,
            fetchTimeout: 10000 // ms
        };
        
        this.initializeOptimizations();
    }

    /**
     * Initialize all performance optimizations
     */
    initializeOptimizations() {
        this.setupLazyLoading();
        this.setupMemoryMonitoring();
        this.setupDOMOptimization();
        this.setupFetchOptimization();
        this.setupEventOptimization();
        
        this.logger?.info('Performance Optimizer initialized');
    }

    /**
     * Set up lazy loading for images and components
     */
    setupLazyLoading() {
        if ('IntersectionObserver' in window) {
            this.imageObserver = new IntersectionObserver(
                this.handleImageIntersection.bind(this),
                {
                    rootMargin: '50px 0px',
                    threshold: 0.01
                }
            );

            this.componentObserver = new IntersectionObserver(
                this.handleComponentIntersection.bind(this),
                {
                    rootMargin: '100px 0px',
                    threshold: 0.1
                }
            );

            this.observers.set('images', this.imageObserver);
            this.observers.set('components', this.componentObserver);
        }
    }

    /**
     * Handle image lazy loading
     */
    handleImageIntersection(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                const src = img.dataset.src || img.dataset.lazySrc;
                
                if (src && !img.src) {
                    this.loadImage(img, src);
                    this.imageObserver.unobserve(img);
                }
            }
        });
    }

    /**
     * Load image with caching and error handling
     */
    async loadImage(img, src) {
        try {
            // Check cache first
            if (this.imageCache.has(src)) {
                const cached = this.imageCache.get(src);
                if (cached.objectURL) {
                    img.src = cached.objectURL;
                    return;
                }
            }

            // Show loading placeholder
            img.classList.add('loading');

            const response = await fetch(src);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const blob = await response.blob();
            const objectURL = URL.createObjectURL(blob);

            // Cache the image
            this.cacheImage(src, { blob, objectURL, timestamp: Date.now() });

            img.src = objectURL;
            img.classList.remove('loading');
            img.classList.add('loaded');

        } catch (error) {
            this.logger?.warn('Image load failed:', { src, error: error.message });
            img.classList.remove('loading');
            img.classList.add('error');
            
            // Set fallback image
            img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSI+PHBhdGggZD0iTTIxIDlWN0E0IDQgMCAwMDE3IDNINEE0IDQgMCAwMDAgN1Y5TTIxIDlWMTdBNCA0IDAgMDExNyAyMUg0QTQgNCAwIDAxMCAyMVY5TTIxIDlIOE0wIDlIOCIgc3Ryb2tlPSIjY2NjIiBzdHJva2Utd2lkdGg9IjIiLz48L3N2Zz4=';
        }
    }

    /**
     * Cache image with size management
     */
    cacheImage(src, data) {
        // Remove oldest entries if cache is full
        if (this.imageCache.size >= this.maxImageCache) {
            const oldestKey = Array.from(this.imageCache.keys())[0];
            const oldestData = this.imageCache.get(oldestKey);
            if (oldestData.objectURL) {
                URL.revokeObjectURL(oldestData.objectURL);
            }
            this.imageCache.delete(oldestKey);
        }

        this.imageCache.set(src, data);
    }

    /**
     * Handle component lazy loading
     */
    handleComponentIntersection(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const component = entry.target;
                const loadFunction = component.dataset.lazyLoad;
                
                if (loadFunction && window[loadFunction]) {
                    try {
                        window[loadFunction](component);
                        this.componentObserver.unobserve(component);
                    } catch (error) {
                        this.logger?.error('Component lazy load failed:', {
                            function: loadFunction,
                            error: error.message
                        });
                    }
                }
            }
        });
    }

    /**
     * Set up memory monitoring and cleanup
     */
    setupMemoryMonitoring() {
        // Monitor memory usage every 30 seconds
        setInterval(() => {
            this.checkMemoryUsage();
            this.cleanupResources();
        }, 30000);

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });
    }

    /**
     * Check memory usage and take action if needed
     */
    checkMemoryUsage() {
        if (!performance.memory) return;

        const used = Math.round(performance.memory.usedJSHeapSize / 1024 / 1024);
        const total = Math.round(performance.memory.totalJSHeapSize / 1024 / 1024);

        if (used > this.thresholds.memoryWarning) {
            this.logger?.warn('High memory usage detected:', { used, total });
            this.forceMemoryCleanup();
        }
    }

    /**
     * Force memory cleanup
     */
    forceMemoryCleanup() {
        // Clear image cache
        this.imageCache.forEach((data, key) => {
            if (data.objectURL) {
                URL.revokeObjectURL(data.objectURL);
            }
        });
        this.imageCache.clear();

        // Clear state manager history if available
        if (window.stateManager) {
            const history = window.stateManager.getHistory();
            if (history.length > 10) {
                window.stateManager.history = history.slice(-10);
            }
        }

        // Force garbage collection if available
        if (window.gc) {
            window.gc();
        }

        this.logger?.info('Memory cleanup completed');
    }

    /**
     * Set up DOM optimization
     */
    setupDOMOptimization() {
        // Virtual scrolling for large lists
        this.virtualScrollConfigs = new Map();
        
        // DOM mutation observer for performance monitoring
        if ('MutationObserver' in window) {
            this.mutationObserver = new MutationObserver(this.handleDOMChanges.bind(this));
            this.mutationObserver.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: false
            });
        }
    }

    /**
     * Handle DOM changes for optimization
     */
    handleDOMChanges(mutations) {
        let elementCount = 0;
        mutations.forEach(mutation => {
            elementCount += mutation.addedNodes.length;
        });

        const totalElements = document.querySelectorAll('*').length;
        if (totalElements > this.thresholds.domElementsWarning) {
            this.logger?.warn('High DOM element count:', { 
                total: totalElements,
                added: elementCount 
            });
        }
    }

    /**
     * Implement virtual scrolling for container
     */
    createVirtualScroll(container, items, renderItem, itemHeight = 50) {
        const config = {
            container,
            items,
            renderItem,
            itemHeight,
            viewportHeight: container.clientHeight,
            scrollTop: 0,
            startIndex: 0,
            endIndex: 0,
            visibleCount: Math.ceil(container.clientHeight / itemHeight) + 2
        };

        const scrollHandler = this.throttle(() => {
            this.updateVirtualScroll(config);
        }, 16);

        container.addEventListener('scroll', scrollHandler);
        this.virtualScrollConfigs.set(container, { config, scrollHandler });

        this.updateVirtualScroll(config);
        return config;
    }

    /**
     * Update virtual scroll rendering
     */
    updateVirtualScroll(config) {
        const { container, items, renderItem, itemHeight, visibleCount } = config;
        
        config.scrollTop = container.scrollTop;
        config.startIndex = Math.floor(config.scrollTop / itemHeight);
        config.endIndex = Math.min(config.startIndex + visibleCount, items.length);

        // Clear container
        container.innerHTML = '';

        // Create spacer for items above viewport
        if (config.startIndex > 0) {
            const topSpacer = document.createElement('div');
            topSpacer.style.height = `${config.startIndex * itemHeight}px`;
            container.appendChild(topSpacer);
        }

        // Render visible items
        for (let i = config.startIndex; i < config.endIndex; i++) {
            const element = renderItem(items[i], i);
            element.style.height = `${itemHeight}px`;
            container.appendChild(element);
        }

        // Create spacer for items below viewport
        if (config.endIndex < items.length) {
            const bottomSpacer = document.createElement('div');
            bottomSpacer.style.height = `${(items.length - config.endIndex) * itemHeight}px`;
            container.appendChild(bottomSpacer);
        }
    }

    /**
     * Set up fetch optimization with caching
     */
    setupFetchOptimization() {
        this.fetchCache = new Map();
        this.maxFetchCache = 100;
        this.fetchCacheTimeout = 5 * 60 * 1000; // 5 minutes

        // Override fetch for caching
        const originalFetch = window.fetch;
        window.fetch = this.createOptimizedFetch(originalFetch);
    }

    /**
     * Create optimized fetch with caching and timeout
     */
    createOptimizedFetch(originalFetch) {
        return async (url, options = {}) => {
            const cacheKey = `${url}_${JSON.stringify(options)}`;
            
            // Check cache for GET requests
            if (!options.method || options.method === 'GET') {
                const cached = this.fetchCache.get(cacheKey);
                if (cached && Date.now() - cached.timestamp < this.fetchCacheTimeout) {
                    return cached.response.clone();
                }
            }

            // Add timeout to request (skip timeout for COLMAP operations)
            const controller = new AbortController();
            const isColmapRequest = url.includes('/api/colmap/');
            const isYardMapRequest = url.includes('/api/yard-map/');
            const timeoutDuration = isColmapRequest ? 30 * 60 * 1000 : 
                                  isYardMapRequest ? 10 * 60 * 1000 : 
                                  this.thresholds.fetchTimeout; // 30 min for COLMAP, 10 min for yard-map, 10s for others
            const timeoutId = setTimeout(() => controller.abort(), timeoutDuration);

            try {
                const response = await originalFetch(url, {
                    ...options,
                    signal: controller.signal
                });

                clearTimeout(timeoutId);

                // Cache successful GET responses
                if (response.ok && (!options.method || options.method === 'GET')) {
                    this.cacheFetchResponse(cacheKey, response.clone());
                }

                return response;

            } catch (error) {
                clearTimeout(timeoutId);
                if (error.name === 'AbortError') {
                    this.logger?.warn('Fetch timeout:', { url, timeout: timeoutDuration });
                }
                throw error;
            }
        };
    }

    /**
     * Cache fetch response
     */
    cacheFetchResponse(key, response) {
        // Remove oldest entries if cache is full
        if (this.fetchCache.size >= this.maxFetchCache) {
            const oldestKey = Array.from(this.fetchCache.keys())[0];
            this.fetchCache.delete(oldestKey);
        }

        this.fetchCache.set(key, {
            response,
            timestamp: Date.now()
        });
    }

    /**
     * Set up event optimization
     */
    setupEventOptimization() {
        // Event delegation for dynamic content
        this.setupEventDelegation();
        
        // Throttle and debounce utilities
        this.optimizedHandlers = new Map();
    }

    /**
     * Set up event delegation for better performance
     */
    setupEventDelegation() {
        document.addEventListener('click', (e) => {
            const target = e.target.closest('[data-click]');
            if (target) {
                const handler = target.dataset.click;
                if (window[handler]) {
                    window[handler](e, target);
                }
            }
        });

        document.addEventListener('input', (e) => {
            const target = e.target;
            if (target.dataset.input) {
                const handler = target.dataset.input;
                if (window[handler]) {
                    const debouncedHandler = this.debounce(window[handler], 300);
                    debouncedHandler(e, target);
                }
            }
        });
    }

    /**
     * Throttle function execution
     */
    throttle(func, delay) {
        let timeoutId;
        let lastExecTime = 0;
        
        return (...args) => {
            const currentTime = Date.now();
            
            if (currentTime - lastExecTime > delay) {
                func(...args);
                lastExecTime = currentTime;
            } else {
                clearTimeout(timeoutId);
                timeoutId = setTimeout(() => {
                    func(...args);
                    lastExecTime = Date.now();
                }, delay - (currentTime - lastExecTime));
            }
        };
    }

    /**
     * Debounce function execution
     */
    debounce(func, delay) {
        let timeoutId;
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func(...args), delay);
        };
    }

    /**
     * Enable lazy loading for images
     */
    enableLazyImages(selector = 'img[data-src], img[data-lazy-src]') {
        const images = document.querySelectorAll(selector);
        images.forEach(img => {
            if (this.imageObserver) {
                this.imageObserver.observe(img);
            } else {
                // Fallback for browsers without IntersectionObserver
                const src = img.dataset.src || img.dataset.lazySrc;
                if (src) {
                    img.src = src;
                }
            }
        });
    }

    /**
     * Enable lazy loading for components
     */
    enableLazyComponents(selector = '[data-lazy-load]') {
        const components = document.querySelectorAll(selector);
        components.forEach(component => {
            if (this.componentObserver) {
                this.componentObserver.observe(component);
            }
        });
    }

    /**
     * Clean up resources
     */
    cleanupResources() {
        // Clean up old image cache entries
        const now = Date.now();
        const maxAge = 10 * 60 * 1000; // 10 minutes

        this.imageCache.forEach((data, key) => {
            if (now - data.timestamp > maxAge) {
                if (data.objectURL) {
                    URL.revokeObjectURL(data.objectURL);
                }
                this.imageCache.delete(key);
            }
        });

        // Clean up fetch cache
        this.fetchCache.forEach((data, key) => {
            if (now - data.timestamp > this.fetchCacheTimeout) {
                this.fetchCache.delete(key);
            }
        });
    }

    /**
     * Get performance metrics
     */
    getMetrics() {
        return {
            imageCache: {
                size: this.imageCache.size,
                maxSize: this.maxImageCache
            },
            fetchCache: {
                size: this.fetchCache.size,
                maxSize: this.maxFetchCache
            },
            memory: performance.memory ? {
                used: Math.round(performance.memory.usedJSHeapSize / 1024 / 1024),
                total: Math.round(performance.memory.totalJSHeapSize / 1024 / 1024)
            } : null,
            domElements: document.querySelectorAll('*').length,
            observers: this.observers.size
        };
    }

    /**
     * Cleanup all resources
     */
    cleanup() {
        // Disconnect observers
        this.observers.forEach(observer => observer.disconnect());
        if (this.mutationObserver) {
            this.mutationObserver.disconnect();
        }

        // Clean up image cache
        this.imageCache.forEach((data, key) => {
            if (data.objectURL) {
                URL.revokeObjectURL(data.objectURL);
            }
        });

        // Clear virtual scroll handlers
        this.virtualScrollConfigs.forEach((config, container) => {
            container.removeEventListener('scroll', config.scrollHandler);
        });

        this.logger?.info('Performance Optimizer cleanup completed');
    }
}

// Initialize global performance optimizer
window.performanceOptimizer = new PerformanceOptimizer();

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { PerformanceOptimizer };
}

console.log('✅ Performance Optimizer initialized');