/**
 * Browser Compatibility Tester for Erik Image Manager
 * Tests browser features and provides fallback recommendations
 */

class CompatibilityTester {
    constructor() {
        this.results = {
            browser: this.getBrowserInfo(),
            features: {},
            compatibility: {
                score: 0,
                level: 'unknown',
                issues: [],
                warnings: []
            },
            polyfills: [],
            fallbacks: []
        };
        
        this.requiredFeatures = {
            // Core JavaScript features
            es6Classes: { test: () => this.testES6Classes(), critical: true },
            es6ArrowFunctions: { test: () => this.testArrowFunctions(), critical: true },
            es6Promise: { test: () => this.testPromises(), critical: true },
            es6AsyncAwait: { test: () => this.testAsyncAwait(), critical: true },
            es6Modules: { test: () => this.testES6Modules(), critical: false },
            
            // Web APIs
            fetch: { test: () => 'fetch' in window, critical: true },
            localStorage: { test: () => this.testLocalStorage(), critical: true },
            sessionStorage: { test: () => this.testSessionStorage(), critical: false },
            webSockets: { test: () => 'WebSocket' in window, critical: false },
            serviceWorker: { test: () => 'serviceWorker' in navigator, critical: false },
            
            // DOM APIs
            querySelector: { test: () => 'querySelector' in document, critical: true },
            addEventListener: { test: () => 'addEventListener' in window, critical: true },
            intersectionObserver: { test: () => 'IntersectionObserver' in window, critical: false },
            mutationObserver: { test: () => 'MutationObserver' in window, critical: false },
            performanceObserver: { test: () => 'PerformanceObserver' in window, critical: false },
            
            // CSS features
            cssGrid: { test: () => this.testCSSFeature('display', 'grid'), critical: false },
            cssFlexbox: { test: () => this.testCSSFeature('display', 'flex'), critical: true },
            cssVariables: { test: () => this.testCSSVariables(), critical: false },
            cssCalc: { test: () => this.testCSSFeature('width', 'calc(100%)'), critical: false },
            
            // Performance APIs
            performanceTiming: { test: () => 'performance' in window && 'timing' in performance, critical: false },
            performanceMemory: { test: () => 'performance' in window && 'memory' in performance, critical: false },
            requestAnimationFrame: { test: () => 'requestAnimationFrame' in window, critical: false },
            
            // Media APIs
            mediaQueries: { test: () => 'matchMedia' in window, critical: false },
            getUserMedia: { test: () => this.testGetUserMedia(), critical: false },
            
            // Security features
            https: { test: () => location.protocol === 'https:', critical: false },
            csp: { test: () => this.testCSP(), critical: false }
        };
        
        this.logger = window.logger;
    }

    /**
     * Run complete compatibility test suite
     */
    async runCompatibilityTests() {
        console.log('🌐 Starting Browser Compatibility Tests...');
        
        try {
            // Test all features
            this.testAllFeatures();
            
            // Calculate compatibility score
            this.calculateCompatibilityScore();
            
            // Generate polyfill recommendations
            this.generatePolyfillRecommendations();
            
            // Generate fallback strategies
            this.generateFallbackStrategies();
            
            // Display results
            this.displayResults();
            
            return this.results;
            
        } catch (error) {
            this.logger?.error('Compatibility testing failed:', error);
            throw error;
        }
    }

    /**
     * Get browser information
     */
    getBrowserInfo() {
        const ua = navigator.userAgent;
        
        // Detect browser type
        let browser = 'Unknown';
        let version = 'Unknown';
        
        if (ua.includes('Chrome') && !ua.includes('Edg')) {
            browser = 'Chrome';
            version = ua.match(/Chrome\/(\d+)/)?.[1] || 'Unknown';
        } else if (ua.includes('Firefox')) {
            browser = 'Firefox';
            version = ua.match(/Firefox\/(\d+)/)?.[1] || 'Unknown';
        } else if (ua.includes('Safari') && !ua.includes('Chrome')) {
            browser = 'Safari';
            version = ua.match(/Version\/(\d+)/)?.[1] || 'Unknown';
        } else if (ua.includes('Edg')) {
            browser = 'Edge';
            version = ua.match(/Edg\/(\d+)/)?.[1] || 'Unknown';
        } else if (ua.includes('MSIE') || ua.includes('Trident')) {
            browser = 'Internet Explorer';
            version = ua.match(/(?:MSIE |rv:)(\d+)/)?.[1] || 'Unknown';
        }

        // Detect mobile
        const mobile = /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua);
        
        return {
            userAgent: ua,
            browser,
            version: parseInt(version) || 0,
            mobile,
            platform: navigator.platform,
            language: navigator.language,
            cookieEnabled: navigator.cookieEnabled,
            onLine: navigator.onLine,
            javaEnabled: typeof navigator.javaEnabled === 'function' ? navigator.javaEnabled() : false
        };
    }

    /**
     * Test all required features
     */
    testAllFeatures() {
        console.log('🔍 Testing Browser Features...');
        
        for (const [featureName, config] of Object.entries(this.requiredFeatures)) {
            try {
                const supported = config.test();
                this.results.features[featureName] = {
                    supported,
                    critical: config.critical,
                    tested: true
                };
                
                if (!supported && config.critical) {
                    this.results.compatibility.issues.push({
                        feature: featureName,
                        message: `Critical feature '${featureName}' is not supported`,
                        severity: 'high'
                    });
                } else if (!supported) {
                    this.results.compatibility.warnings.push({
                        feature: featureName,
                        message: `Feature '${featureName}' is not supported`,
                        severity: 'medium'
                    });
                }
                
            } catch (error) {
                this.results.features[featureName] = {
                    supported: false,
                    critical: config.critical,
                    tested: false,
                    error: error.message
                };
                
                this.results.compatibility.issues.push({
                    feature: featureName,
                    message: `Failed to test feature '${featureName}': ${error.message}`,
                    severity: 'medium'
                });
            }
        }
    }

    /**
     * Test ES6 Classes
     */
    testES6Classes() {
        try {
            eval('class TestClass {}');
            return true;
        } catch (e) {
            return false;
        }
    }

    /**
     * Test Arrow Functions
     */
    testArrowFunctions() {
        try {
            eval('(() => {})');
            return true;
        } catch (e) {
            return false;
        }
    }

    /**
     * Test Promises
     */
    testPromises() {
        return typeof Promise !== 'undefined' && typeof Promise.resolve === 'function';
    }

    /**
     * Test Async/Await
     */
    testAsyncAwait() {
        try {
            eval('(async () => {})');
            return true;
        } catch (e) {
            return false;
        }
    }

    /**
     * Test ES6 Modules
     */
    testES6Modules() {
        // Check for module support by testing for script type="module"
        const script = document.createElement('script');
        return 'noModule' in script;
    }

    /**
     * Test localStorage with actual read/write
     */
    testLocalStorage() {
        try {
            const test = '__test__';
            localStorage.setItem(test, 'test');
            localStorage.removeItem(test);
            return true;
        } catch (e) {
            return false;
        }
    }

    /**
     * Test sessionStorage
     */
    testSessionStorage() {
        try {
            const test = '__test__';
            sessionStorage.setItem(test, 'test');
            sessionStorage.removeItem(test);
            return true;
        } catch (e) {
            return false;
        }
    }

    /**
     * Test CSS feature support
     */
    testCSSFeature(property, value) {
        if (typeof CSS !== 'undefined' && CSS.supports) {
            return CSS.supports(property, value);
        }
        
        // Fallback for older browsers
        const element = document.createElement('div');
        element.style.cssText = `${property}:${value}`;
        return element.style[property] === value;
    }

    /**
     * Test CSS Variables
     */
    testCSSVariables() {
        return this.testCSSFeature('--test-var', 'test');
    }

    /**
     * Test getUserMedia
     */
    testGetUserMedia() {
        return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia) ||
               !!(navigator.getUserMedia || navigator.webkitGetUserMedia || 
                  navigator.mozGetUserMedia || navigator.msGetUserMedia);
    }

    /**
     * Test Content Security Policy
     */
    testCSP() {
        const metaTags = document.querySelectorAll('meta[http-equiv="Content-Security-Policy"]');
        return metaTags.length > 0 || !!document.querySelector('meta[name="csp-nonce"]');
    }

    /**
     * Calculate compatibility score
     */
    calculateCompatibilityScore() {
        const totalFeatures = Object.keys(this.requiredFeatures).length;
        const supportedFeatures = Object.values(this.results.features)
            .filter(feature => feature.supported).length;
        
        const criticalFeatures = Object.values(this.requiredFeatures)
            .filter(config => config.critical).length;
        const supportedCriticalFeatures = Object.entries(this.results.features)
            .filter(([name, feature]) => feature.supported && this.requiredFeatures[name].critical)
            .length;

        // Weight critical features more heavily
        const criticalScore = (supportedCriticalFeatures / criticalFeatures) * 70;
        const generalScore = (supportedFeatures / totalFeatures) * 30;
        
        this.results.compatibility.score = Math.round(criticalScore + generalScore);

        // Determine compatibility level
        if (this.results.compatibility.score >= 90) {
            this.results.compatibility.level = 'excellent';
        } else if (this.results.compatibility.score >= 75) {
            this.results.compatibility.level = 'good';
        } else if (this.results.compatibility.score >= 60) {
            this.results.compatibility.level = 'fair';
        } else {
            this.results.compatibility.level = 'poor';
        }

        // Add browser-specific adjustments
        this.addBrowserSpecificRecommendations();
    }

    /**
     * Add browser-specific recommendations
     */
    addBrowserSpecificRecommendations() {
        const browser = this.results.browser;
        
        if (browser.browser === 'Internet Explorer') {
            this.results.compatibility.issues.push({
                feature: 'browser',
                message: 'Internet Explorer is not recommended for this application',
                severity: 'critical',
                recommendation: 'Please use a modern browser like Chrome, Firefox, Safari, or Edge'
            });
            this.results.compatibility.score = Math.min(this.results.compatibility.score, 30);
        }
        
        if (browser.browser === 'Chrome' && browser.version < 60) {
            this.results.compatibility.warnings.push({
                feature: 'browser-version',
                message: 'Chrome version is outdated',
                severity: 'medium',
                recommendation: 'Please update to the latest version of Chrome'
            });
        }
        
        if (browser.browser === 'Firefox' && browser.version < 55) {
            this.results.compatibility.warnings.push({
                feature: 'browser-version',
                message: 'Firefox version is outdated',
                severity: 'medium',
                recommendation: 'Please update to the latest version of Firefox'
            });
        }
        
        if (browser.mobile) {
            this.results.compatibility.warnings.push({
                feature: 'mobile-device',
                message: 'Mobile device detected',
                severity: 'low',
                recommendation: 'Some features may have limited functionality on mobile devices'
            });
        }
    }

    /**
     * Generate polyfill recommendations
     */
    generatePolyfillRecommendations() {
        const unsupportedFeatures = Object.entries(this.results.features)
            .filter(([name, feature]) => !feature.supported);

        unsupportedFeatures.forEach(([featureName, feature]) => {
            const polyfill = this.getPolyfillRecommendation(featureName);
            if (polyfill) {
                this.results.polyfills.push(polyfill);
            }
        });
    }

    /**
     * Get polyfill recommendation for a feature
     */
    getPolyfillRecommendation(featureName) {
        const polyfillMap = {
            fetch: {
                name: 'fetch',
                url: 'https://cdn.jsdelivr.net/npm/whatwg-fetch@3.6.2/fetch.min.js',
                description: 'Polyfill for fetch API'
            },
            es6Promise: {
                name: 'promise',
                url: 'https://cdn.jsdelivr.net/npm/es6-promise@4.2.8/dist/es6-promise.auto.min.js',
                description: 'Polyfill for Promise support'
            },
            intersectionObserver: {
                name: 'intersection-observer',
                url: 'https://cdn.jsdelivr.net/npm/intersection-observer@0.12.0/intersection-observer.js',
                description: 'Polyfill for IntersectionObserver API'
            },
            cssVariables: {
                name: 'css-vars-ponyfill',
                url: 'https://cdn.jsdelivr.net/npm/css-vars-ponyfill@2.4.7/dist/css-vars-ponyfill.min.js',
                description: 'Polyfill for CSS custom properties'
            }
        };

        return polyfillMap[featureName] || null;
    }

    /**
     * Generate fallback strategies
     */
    generateFallbackStrategies() {
        const unsupportedCriticalFeatures = Object.entries(this.results.features)
            .filter(([name, feature]) => !feature.supported && this.requiredFeatures[name].critical);

        unsupportedCriticalFeatures.forEach(([featureName]) => {
            const fallback = this.getFallbackStrategy(featureName);
            if (fallback) {
                this.results.fallbacks.push(fallback);
            }
        });
    }

    /**
     * Get fallback strategy for a feature
     */
    getFallbackStrategy(featureName) {
        const fallbackMap = {
            fetch: {
                feature: 'fetch',
                strategy: 'Use XMLHttpRequest as fallback',
                implementation: 'Implement feature detection and fallback to XHR for API calls'
            },
            localStorage: {
                feature: 'localStorage',
                strategy: 'Use memory storage as fallback',
                implementation: 'Implement in-memory storage with session persistence warning'
            },
            cssFlexbox: {
                feature: 'cssFlexbox',
                strategy: 'Use float-based layout as fallback',
                implementation: 'Provide alternative CSS layouts for older browsers'
            },
            es6Classes: {
                feature: 'es6Classes',
                strategy: 'Use function prototypes as fallback',
                implementation: 'Transpile ES6 classes to ES5 function constructors'
            }
        };

        return fallbackMap[featureName] || null;
    }

    /**
     * Display compatibility test results
     */
    displayResults() {
        console.log('\n🌐 BROWSER COMPATIBILITY RESULTS');
        console.log('=' .repeat(45));
        
        // Browser info
        const browser = this.results.browser;
        console.log(`\n📱 Browser: ${browser.browser} ${browser.version}`);
        console.log(`📋 Platform: ${browser.platform}`);
        console.log(`📱 Mobile: ${browser.mobile ? 'Yes' : 'No'}`);
        console.log(`🌐 Online: ${browser.onLine ? 'Yes' : 'No'}`);
        
        // Compatibility score
        const compat = this.results.compatibility;
        console.log(`\n📊 Compatibility Score: ${compat.score}% (${compat.level.toUpperCase()})`);
        
        // Feature support summary
        const supported = Object.values(this.results.features).filter(f => f.supported).length;
        const total = Object.keys(this.results.features).length;
        console.log(`✅ Supported Features: ${supported}/${total}`);
        
        // Critical issues
        if (compat.issues.length > 0) {
            console.log(`\n❌ Critical Issues (${compat.issues.length}):`);
            compat.issues.forEach((issue, index) => {
                console.log(`  ${index + 1}. [${issue.severity.toUpperCase()}] ${issue.message}`);
                if (issue.recommendation) {
                    console.log(`     💡 ${issue.recommendation}`);
                }
            });
        }
        
        // Warnings
        if (compat.warnings.length > 0) {
            console.log(`\n⚠️ Warnings (${compat.warnings.length}):`);
            compat.warnings.slice(0, 5).forEach((warning, index) => {
                console.log(`  ${index + 1}. ${warning.message}`);
            });
        }
        
        // Polyfill recommendations
        if (this.results.polyfills.length > 0) {
            console.log(`\n🔧 Recommended Polyfills (${this.results.polyfills.length}):`);
            this.results.polyfills.forEach((polyfill, index) => {
                console.log(`  ${index + 1}. ${polyfill.name}: ${polyfill.description}`);
            });
        }
        
        // Store results globally
        window.COMPATIBILITY_RESULTS = this.results;
        
        console.log('\n✅ Browser Compatibility Analysis Complete!');
    }

    /**
     * Generate compatibility report
     */
    generateCompatibilityReport() {
        return {
            timestamp: new Date().toISOString(),
            system: 'Erik Image Manager - Compatibility Analysis',
            browser: this.results.browser,
            compatibility: this.results.compatibility,
            features: this.results.features,
            polyfills: this.results.polyfills,
            fallbacks: this.results.fallbacks,
            recommendations: this.generateCompatibilityRecommendations()
        };
    }

    /**
     * Generate compatibility recommendations
     */
    generateCompatibilityRecommendations() {
        const recommendations = [];
        
        if (this.results.compatibility.score < 75) {
            recommendations.push('Consider implementing polyfills for better browser compatibility');
        }
        
        if (this.results.compatibility.issues.length > 0) {
            recommendations.push('Address critical compatibility issues before production deployment');
        }
        
        if (this.results.browser.browser === 'Internet Explorer') {
            recommendations.push('Display upgrade notice for Internet Explorer users');
        }
        
        if (this.results.polyfills.length > 3) {
            recommendations.push('Consider using a polyfill service like Polyfill.io to reduce bundle size');
        }
        
        return recommendations;
    }
}

// Initialize compatibility tester
window.compatibilityTester = new CompatibilityTester();

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CompatibilityTester };
}

console.log('✅ Browser Compatibility Tester loaded');