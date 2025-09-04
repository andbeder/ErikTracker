/**
 * Bundle Size and Performance Analyzer for Erik Image Manager
 * Analyzes asset sizes, loading times, and provides optimization recommendations
 */

class BundleAnalyzer {
    constructor() {
        this.results = {
            assets: {
                css: [],
                js: [],
                total: 0
            },
            performance: {
                loadTimes: {},
                memoryUsage: null,
                renderMetrics: {}
            },
            recommendations: [],
            optimizations: []
        };
        
        this.logger = window.logger;
        this.initialized = false;
    }

    /**
     * Initialize bundle analysis
     */
    async initialize() {
        if (this.initialized) return this.results;
        
        console.log('📊 Starting Bundle Analysis...');
        
        try {
            await this.analyzeAssetSizes();
            await this.analyzePerformanceMetrics();
            await this.analyzeRenderingPerformance();
            this.generateRecommendations();
            this.generateOptimizations();
            
            this.initialized = true;
            this.displayResults();
            
            return this.results;
            
        } catch (error) {
            this.logger?.error('Bundle analysis failed:', error);
            throw error;
        }
    }

    /**
     * Analyze CSS and JavaScript asset sizes
     */
    async analyzeAssetSizes() {
        console.log('📏 Analyzing Asset Sizes...');
        
        // Analyze CSS files
        const cssLinks = document.querySelectorAll('link[rel="stylesheet"]');
        for (const link of cssLinks) {
            try {
                const response = await fetch(link.href, { method: 'HEAD' });
                const size = parseInt(response.headers.get('content-length') || '0');
                const filename = link.href.split('/').pop();
                
                this.results.assets.css.push({
                    filename,
                    url: link.href,
                    size: size || await this.estimateSize(link.href, 'text/css'),
                    loadOrder: Array.from(cssLinks).indexOf(link)
                });
            } catch (error) {
                this.logger?.warn(`Failed to analyze CSS file: ${link.href}`, error);
            }
        }

        // Analyze JavaScript files
        const scriptTags = document.querySelectorAll('script[src]');
        for (const script of scriptTags) {
            try {
                const response = await fetch(script.src, { method: 'HEAD' });
                const size = parseInt(response.headers.get('content-length') || '0');
                const filename = script.src.split('/').pop();
                
                this.results.assets.js.push({
                    filename,
                    url: script.src,
                    size: size || await this.estimateSize(script.src, 'application/javascript'),
                    loadOrder: Array.from(scriptTags).indexOf(script),
                    async: script.async,
                    defer: script.defer
                });
            } catch (error) {
                this.logger?.warn(`Failed to analyze JS file: ${script.src}`, error);
            }
        }

        // Calculate totals
        const cssTotal = this.results.assets.css.reduce((sum, asset) => sum + asset.size, 0);
        const jsTotal = this.results.assets.js.reduce((sum, asset) => sum + asset.size, 0);
        
        this.results.assets.total = cssTotal + jsTotal;
        this.results.assets.cssTotal = cssTotal;
        this.results.assets.jsTotal = jsTotal;
    }

    /**
     * Estimate file size by downloading content
     */
    async estimateSize(url, expectedType) {
        try {
            const response = await fetch(url);
            const text = await response.text();
            
            // Rough estimate: UTF-8 encoding
            return new Blob([text]).size;
        } catch (error) {
            this.logger?.warn(`Failed to estimate size for: ${url}`, error);
            return 0;
        }
    }

    /**
     * Analyze performance metrics
     */
    async analyzePerformanceMetrics() {
        console.log('⚡ Analyzing Performance Metrics...');
        
        // Navigation timing
        if (performance.getEntriesByType) {
            const navigation = performance.getEntriesByType('navigation')[0];
            if (navigation) {
                this.results.performance.loadTimes = {
                    domContentLoaded: Math.round(navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart),
                    loadComplete: Math.round(navigation.loadEventEnd - navigation.loadEventStart),
                    domInteractive: Math.round(navigation.domInteractive - navigation.navigationStart),
                    totalPageLoad: Math.round(navigation.loadEventEnd - navigation.navigationStart)
                };
            }
        }

        // Memory usage
        if (performance.memory) {
            this.results.performance.memoryUsage = {
                used: Math.round(performance.memory.usedJSHeapSize / 1024 / 1024),
                total: Math.round(performance.memory.totalJSHeapSize / 1024 / 1024),
                limit: Math.round(performance.memory.jsHeapSizeLimit / 1024 / 1024)
            };
        }

        // Resource timing
        const resources = performance.getEntriesByType('resource');
        this.results.performance.resourceTiming = {
            scripts: resources.filter(r => r.name.includes('.js')).length,
            stylesheets: resources.filter(r => r.name.includes('.css')).length,
            images: resources.filter(r => r.initiatorType === 'img').length,
            slowestResource: this.findSlowestResource(resources)
        };
    }

    /**
     * Find the slowest loading resource
     */
    findSlowestResource(resources) {
        let slowest = null;
        let maxDuration = 0;

        resources.forEach(resource => {
            const duration = resource.responseEnd - resource.requestStart;
            if (duration > maxDuration) {
                maxDuration = duration;
                slowest = {
                    name: resource.name.split('/').pop(),
                    duration: Math.round(duration),
                    size: resource.transferSize || 0,
                    type: this.getResourceType(resource)
                };
            }
        });

        return slowest;
    }

    /**
     * Get resource type from performance entry
     */
    getResourceType(resource) {
        if (resource.name.includes('.js')) return 'script';
        if (resource.name.includes('.css')) return 'stylesheet';
        if (resource.initiatorType === 'img') return 'image';
        if (resource.initiatorType === 'fetch' || resource.initiatorType === 'xmlhttprequest') return 'api';
        return 'other';
    }

    /**
     * Analyze rendering performance
     */
    async analyzeRenderingPerformance() {
        console.log('🎨 Analyzing Rendering Performance...');
        
        try {
            // First Paint
            const paintEntries = performance.getEntriesByType('paint');
            const firstPaint = paintEntries.find(entry => entry.name === 'first-paint');
            const firstContentfulPaint = paintEntries.find(entry => entry.name === 'first-contentful-paint');

            this.results.performance.renderMetrics = {
                firstPaint: firstPaint ? Math.round(firstPaint.startTime) : null,
                firstContentfulPaint: firstContentfulPaint ? Math.round(firstContentfulPaint.startTime) : null,
                domElements: document.querySelectorAll('*').length,
                renderBlockingResources: this.findRenderBlockingResources()
            };

            // Layout metrics
            this.results.performance.renderMetrics.layout = {
                bodyHeight: document.body.scrollHeight,
                viewportHeight: window.innerHeight,
                scrollableContent: document.body.scrollHeight > window.innerHeight
            };

        } catch (error) {
            this.logger?.warn('Rendering performance analysis failed:', error);
        }
    }

    /**
     * Find render blocking resources
     */
    findRenderBlockingResources() {
        const blocking = [];
        
        // CSS files without media queries are render-blocking
        const cssLinks = document.querySelectorAll('link[rel="stylesheet"]:not([media])');
        cssLinks.forEach(link => {
            blocking.push({
                type: 'css',
                url: link.href,
                filename: link.href.split('/').pop()
            });
        });

        // Synchronous scripts in head are render-blocking
        const headScripts = document.head.querySelectorAll('script[src]:not([async]):not([defer])');
        headScripts.forEach(script => {
            blocking.push({
                type: 'script',
                url: script.src,
                filename: script.src.split('/').pop()
            });
        });

        return blocking;
    }

    /**
     * Generate optimization recommendations
     */
    generateRecommendations() {
        console.log('💡 Generating Recommendations...');
        
        const recommendations = [];

        // Bundle size recommendations
        if (this.results.assets.total > 500 * 1024) { // > 500KB
            recommendations.push({
                category: 'Bundle Size',
                priority: 'high',
                issue: `Total bundle size is ${this.formatBytes(this.results.assets.total)}`,
                recommendation: 'Consider code splitting, lazy loading, or removing unused dependencies'
            });
        }

        if (this.results.assets.jsTotal > 300 * 1024) { // > 300KB JS
            recommendations.push({
                category: 'JavaScript',
                priority: 'medium',
                issue: `JavaScript bundle is ${this.formatBytes(this.results.assets.jsTotal)}`,
                recommendation: 'Split JavaScript into smaller modules and load them on demand'
            });
        }

        // Performance recommendations
        const loadTime = this.results.performance.loadTimes?.totalPageLoad;
        if (loadTime && loadTime > 3000) { // > 3 seconds
            recommendations.push({
                category: 'Load Time',
                priority: 'high',
                issue: `Page load time is ${loadTime}ms`,
                recommendation: 'Optimize critical rendering path and reduce initial payload'
            });
        }

        // Memory recommendations
        const memoryUsage = this.results.performance.memoryUsage;
        if (memoryUsage && memoryUsage.used > 50) { // > 50MB
            recommendations.push({
                category: 'Memory',
                priority: 'medium',
                issue: `Memory usage is ${memoryUsage.used}MB`,
                recommendation: 'Implement memory management and cleanup unused objects'
            });
        }

        // Render blocking recommendations
        const renderBlocking = this.results.performance.renderMetrics?.renderBlockingResources || [];
        if (renderBlocking.length > 3) {
            recommendations.push({
                category: 'Rendering',
                priority: 'medium',
                issue: `${renderBlocking.length} render-blocking resources found`,
                recommendation: 'Add async/defer attributes to non-critical scripts and optimize CSS delivery'
            });
        }

        // DOM complexity recommendations
        const domElements = this.results.performance.renderMetrics?.domElements;
        if (domElements > 1000) {
            recommendations.push({
                category: 'DOM',
                priority: 'low',
                issue: `High DOM complexity: ${domElements} elements`,
                recommendation: 'Consider virtual scrolling for large lists and reduce DOM depth'
            });
        }

        this.results.recommendations = recommendations;
    }

    /**
     * Generate specific optimizations
     */
    generateOptimizations() {
        console.log('🔧 Generating Optimizations...');
        
        const optimizations = [];

        // CSS optimizations
        const largestCSS = this.results.assets.css
            .sort((a, b) => b.size - a.size)
            .slice(0, 3);

        largestCSS.forEach(css => {
            if (css.size > 10 * 1024) { // > 10KB
                optimizations.push({
                    type: 'css',
                    target: css.filename,
                    action: 'minify',
                    description: `Minify ${css.filename} (${this.formatBytes(css.size)})`,
                    potentialSavings: Math.round(css.size * 0.3) // Estimate 30% savings
                });
            }
        });

        // JavaScript optimizations
        const largestJS = this.results.assets.js
            .sort((a, b) => b.size - a.size)
            .slice(0, 3);

        largestJS.forEach(js => {
            if (js.size > 20 * 1024) { // > 20KB
                optimizations.push({
                    type: 'javascript',
                    target: js.filename,
                    action: 'tree-shake',
                    description: `Tree-shake and minify ${js.filename} (${this.formatBytes(js.size)})`,
                    potentialSavings: Math.round(js.size * 0.4) // Estimate 40% savings
                });
            }
        });

        // Image optimizations (if any large images detected)
        const imageResources = performance.getEntriesByType('resource')
            .filter(r => r.initiatorType === 'img' && r.transferSize > 100 * 1024);

        imageResources.forEach(img => {
            optimizations.push({
                type: 'image',
                target: img.name.split('/').pop(),
                action: 'optimize',
                description: `Optimize image ${img.name.split('/').pop()} (${this.formatBytes(img.transferSize)})`,
                potentialSavings: Math.round(img.transferSize * 0.5)
            });
        });

        // Caching optimizations
        optimizations.push({
            type: 'caching',
            target: 'static-assets',
            action: 'cache-headers',
            description: 'Add long-term caching headers for static assets',
            potentialSavings: 'Repeat visit performance improvement'
        });

        // Compression optimizations
        if (this.results.assets.total > 100 * 1024) {
            optimizations.push({
                type: 'compression',
                target: 'all-assets',
                action: 'gzip',
                description: 'Enable gzip compression on server',
                potentialSavings: Math.round(this.results.assets.total * 0.7) // Estimate 70% compression
            });
        }

        this.results.optimizations = optimizations;
    }

    /**
     * Format bytes into human readable format
     */
    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Display analysis results
     */
    displayResults() {
        console.log('\n📊 BUNDLE ANALYSIS RESULTS');
        console.log('=' .repeat(40));
        
        // Asset summary
        console.log('\n📦 Asset Summary:');
        console.log(`  Total Bundle Size: ${this.formatBytes(this.results.assets.total)}`);
        console.log(`  CSS Files: ${this.results.assets.css.length} (${this.formatBytes(this.results.assets.cssTotal)})`);
        console.log(`  JS Files: ${this.results.assets.js.length} (${this.formatBytes(this.results.assets.jsTotal)})`);

        // Performance summary
        const perf = this.results.performance;
        if (perf.loadTimes) {
            console.log('\n⚡ Performance:');
            console.log(`  Page Load: ${perf.loadTimes.totalPageLoad}ms`);
            console.log(`  DOM Interactive: ${perf.loadTimes.domInteractive}ms`);
            console.log(`  DOM Content Loaded: ${perf.loadTimes.domContentLoaded}ms`);
        }

        if (perf.memoryUsage) {
            console.log(`  Memory Usage: ${perf.memoryUsage.used}MB / ${perf.memoryUsage.total}MB`);
        }

        // Top recommendations
        console.log('\n💡 Top Recommendations:');
        this.results.recommendations
            .filter(r => r.priority === 'high')
            .slice(0, 3)
            .forEach((rec, index) => {
                console.log(`  ${index + 1}. [${rec.category}] ${rec.recommendation}`);
            });

        // Optimization opportunities
        console.log('\n🔧 Optimization Opportunities:');
        const totalSavings = this.results.optimizations
            .filter(opt => typeof opt.potentialSavings === 'number')
            .reduce((sum, opt) => sum + opt.potentialSavings, 0);
        
        console.log(`  Potential Bundle Size Reduction: ${this.formatBytes(totalSavings)}`);
        console.log(`  Optimization Actions: ${this.results.optimizations.length}`);

        // Store results globally
        window.BUNDLE_ANALYSIS = this.results;
    }

    /**
     * Generate optimization report
     */
    generateOptimizationReport() {
        const report = {
            timestamp: new Date().toISOString(),
            system: 'Erik Image Manager - Bundle Analysis',
            summary: {
                totalAssets: this.results.assets.css.length + this.results.assets.js.length,
                totalSize: this.results.assets.total,
                recommendations: this.results.recommendations.length,
                optimizations: this.results.optimizations.length
            },
            details: this.results,
            actionPlan: this.generateActionPlan()
        };

        return report;
    }

    /**
     * Generate prioritized action plan
     */
    generateActionPlan() {
        const actions = [];

        // High priority recommendations first
        this.results.recommendations
            .filter(r => r.priority === 'high')
            .forEach(rec => {
                actions.push({
                    priority: 'high',
                    action: rec.recommendation,
                    category: rec.category,
                    impact: 'high'
                });
            });

        // High-impact optimizations
        this.results.optimizations
            .filter(opt => typeof opt.potentialSavings === 'number' && opt.potentialSavings > 10 * 1024)
            .sort((a, b) => b.potentialSavings - a.potentialSavings)
            .slice(0, 5)
            .forEach(opt => {
                actions.push({
                    priority: 'medium',
                    action: opt.description,
                    category: opt.type,
                    impact: 'medium',
                    savings: this.formatBytes(opt.potentialSavings)
                });
            });

        return actions;
    }
}

// Initialize bundle analyzer
window.bundleAnalyzer = new BundleAnalyzer();

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { BundleAnalyzer };
}

console.log('✅ Bundle Analyzer loaded');