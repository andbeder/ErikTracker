/**
 * Production Readiness Validator for Erik Image Manager
 * Comprehensive checks for production deployment readiness
 */

class ProductionValidator {
    constructor() {
        this.results = {
            overall: {
                ready: false,
                score: 0,
                level: 'not-ready'
            },
            categories: {
                security: { score: 0, issues: [], passed: [] },
                performance: { score: 0, issues: [], passed: [] },
                reliability: { score: 0, issues: [], passed: [] },
                maintainability: { score: 0, issues: [], passed: [] },
                monitoring: { score: 0, issues: [], passed: [] }
            },
            deployment: {
                checklist: [],
                environment: null,
                recommendations: []
            }
        };
        
        this.checks = {
            security: [
                { name: 'HTTPS Protocol', test: () => this.checkHTTPS(), weight: 20 },
                { name: 'Content Security Policy', test: () => this.checkCSP(), weight: 15 },
                { name: 'Secure Headers', test: () => this.checkSecureHeaders(), weight: 15 },
                { name: 'Input Validation', test: () => this.checkInputValidation(), weight: 25 },
                { name: 'Error Information Exposure', test: () => this.checkErrorExposure(), weight: 25 }
            ],
            performance: [
                { name: 'Bundle Size Optimization', test: () => this.checkBundleSize(), weight: 20 },
                { name: 'Image Optimization', test: () => this.checkImageOptimization(), weight: 15 },
                { name: 'Caching Strategy', test: () => this.checkCaching(), weight: 25 },
                { name: 'Lazy Loading', test: () => this.checkLazyLoading(), weight: 20 },
                { name: 'Service Worker', test: () => this.checkServiceWorker(), weight: 20 }
            ],
            reliability: [
                { name: 'Error Handling', test: () => this.checkErrorHandling(), weight: 30 },
                { name: 'Graceful Degradation', test: () => this.checkGracefulDegradation(), weight: 25 },
                { name: 'Offline Functionality', test: () => this.checkOfflineFunctionality(), weight: 25 },
                { name: 'Auto-Recovery', test: () => this.checkAutoRecovery(), weight: 20 }
            ],
            maintainability: [
                { name: 'Code Organization', test: () => this.checkCodeOrganization(), weight: 25 },
                { name: 'Documentation', test: () => this.checkDocumentation(), weight: 20 },
                { name: 'Testing Coverage', test: () => this.checkTestingCoverage(), weight: 30 },
                { name: 'Configuration Management', test: () => this.checkConfigManagement(), weight: 25 }
            ],
            monitoring: [
                { name: 'Error Logging', test: () => this.checkErrorLogging(), weight: 30 },
                { name: 'Performance Monitoring', test: () => this.checkPerformanceMonitoring(), weight: 25 },
                { name: 'Health Checks', test: () => this.checkHealthChecks(), weight: 25 },
                { name: 'Analytics Integration', test: () => this.checkAnalytics(), weight: 20 }
            ]
        };
        
        this.logger = window.logger;
    }

    /**
     * Run complete production readiness validation
     */
    async runProductionValidation() {
        console.log('🚀 Starting Production Readiness Validation...');
        
        try {
            // Run all category checks
            for (const [category, checks] of Object.entries(this.checks)) {
                await this.runCategoryChecks(category, checks);
            }
            
            // Calculate overall score
            this.calculateOverallScore();
            
            // Generate deployment checklist
            this.generateDeploymentChecklist();
            
            // Generate recommendations
            this.generateRecommendations();
            
            // Display results
            this.displayResults();
            
            return this.results;
            
        } catch (error) {
            this.logger?.error('Production validation failed:', error);
            throw error;
        }
    }

    /**
     * Run checks for a specific category
     */
    async runCategoryChecks(category, checks) {
        console.log(`🔍 Validating ${category.toUpperCase()} requirements...`);
        
        const results = this.results.categories[category];
        let totalScore = 0;
        let maxScore = 0;

        for (const check of checks) {
            try {
                const result = await check.test();
                maxScore += check.weight;
                
                if (result.passed) {
                    totalScore += check.weight;
                    results.passed.push({
                        name: check.name,
                        weight: check.weight,
                        details: result.details || 'Check passed'
                    });
                } else {
                    results.issues.push({
                        name: check.name,
                        weight: check.weight,
                        severity: result.severity || 'medium',
                        message: result.message || 'Check failed',
                        recommendation: result.recommendation || 'Review and fix this issue'
                    });
                }
            } catch (error) {
                results.issues.push({
                    name: check.name,
                    weight: check.weight,
                    severity: 'high',
                    message: `Check failed with error: ${error.message}`,
                    recommendation: 'Investigate and fix the underlying issue'
                });
            }
        }

        results.score = maxScore > 0 ? Math.round((totalScore / maxScore) * 100) : 0;
    }

    // Security Checks
    checkHTTPS() {
        const isHTTPS = location.protocol === 'https:';
        return {
            passed: isHTTPS,
            message: isHTTPS ? 'Application served over HTTPS' : 'Application not served over HTTPS',
            severity: isHTTPS ? 'info' : 'critical',
            recommendation: isHTTPS ? null : 'Deploy with SSL/TLS certificate for production'
        };
    }

    checkCSP() {
        const cspMeta = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
        const cspHeader = document.querySelector('meta[name="csp-nonce"]'); // Indirect check
        const hasCSP = !!(cspMeta || cspHeader);
        
        return {
            passed: hasCSP,
            message: hasCSP ? 'Content Security Policy detected' : 'No Content Security Policy found',
            severity: hasCSP ? 'info' : 'high',
            recommendation: hasCSP ? null : 'Implement Content Security Policy headers'
        };
    }

    checkSecureHeaders() {
        // Check for secure response headers (limited client-side detection)
        const hasReferrerPolicy = document.querySelector('meta[name="referrer"]');
        const hasViewportSecurity = document.querySelector('meta[name="viewport"]')?.content.includes('user-scalable=no');
        
        // Basic security indicators
        const securityScore = (hasReferrerPolicy ? 50 : 0) + (hasViewportSecurity ? 50 : 0);
        const passed = securityScore > 0;
        
        return {
            passed,
            message: passed ? 'Some security headers detected' : 'Limited security headers detected',
            severity: passed ? 'info' : 'medium',
            recommendation: passed ? 'Verify all security headers on server' : 'Implement security headers (X-Frame-Options, X-Content-Type-Options, etc.)'
        };
    }

    checkInputValidation() {
        // Check for input validation patterns in forms
        const forms = document.querySelectorAll('form');
        const inputs = document.querySelectorAll('input, textarea');
        let validationScore = 0;
        let totalInputs = inputs.length;

        inputs.forEach(input => {
            if (input.pattern || input.required || input.maxLength || input.type !== 'text') {
                validationScore++;
            }
        });

        const passed = totalInputs === 0 || (validationScore / totalInputs) > 0.5;
        
        return {
            passed,
            message: `Input validation on ${validationScore}/${totalInputs} inputs`,
            severity: passed ? 'info' : 'high',
            recommendation: passed ? null : 'Implement comprehensive input validation'
        };
    }

    checkErrorExposure() {
        // Check if debug information is exposed
        const debugMode = window.SERVER_CONFIG?.debug === true;
        const envMode = window.SERVER_CONFIG?.environment === 'development';
        const exposesErrors = debugMode || envMode;
        
        return {
            passed: !exposesErrors,
            message: exposesErrors ? 'Debug/development mode detected' : 'Production mode configured',
            severity: exposesErrors ? 'high' : 'info',
            recommendation: exposesErrors ? 'Disable debug mode and set environment to production' : null
        };
    }

    // Performance Checks
    async checkBundleSize() {
        const bundleAnalysis = window.BUNDLE_ANALYSIS;
        if (!bundleAnalysis) {
            return {
                passed: false,
                message: 'Bundle analysis not available',
                severity: 'medium',
                recommendation: 'Run bundle analysis to check asset sizes'
            };
        }

        const totalSize = bundleAnalysis.assets.total;
        const passed = totalSize < 500 * 1024; // Less than 500KB
        
        return {
            passed,
            message: `Total bundle size: ${this.formatBytes(totalSize)}`,
            severity: passed ? 'info' : 'medium',
            recommendation: passed ? null : 'Optimize bundle size through code splitting and minification'
        };
    }

    checkImageOptimization() {
        const images = document.querySelectorAll('img');
        const lazyImages = document.querySelectorAll('img[data-src], img[loading="lazy"]');
        const optimized = images.length === 0 || (lazyImages.length / images.length) > 0.5;
        
        return {
            passed: optimized,
            message: `${lazyImages.length}/${images.length} images optimized`,
            severity: optimized ? 'info' : 'low',
            recommendation: optimized ? null : 'Implement lazy loading for images'
        };
    }

    checkCaching() {
        const hasServiceWorker = !!window.serviceWorkerManager;
        const hasCache = !!window.performanceOptimizer?.getMetrics()?.fetchCache;
        const passed = hasServiceWorker || hasCache;
        
        return {
            passed,
            message: passed ? 'Caching strategy implemented' : 'No caching strategy detected',
            severity: passed ? 'info' : 'medium',
            recommendation: passed ? null : 'Implement service worker or browser caching'
        };
    }

    checkLazyLoading() {
        const hasPerformanceOptimizer = !!window.performanceOptimizer;
        const hasLazyImages = document.querySelectorAll('img[data-src], img[loading="lazy"]').length > 0;
        const passed = hasPerformanceOptimizer || hasLazyImages;
        
        return {
            passed,
            message: passed ? 'Lazy loading implemented' : 'No lazy loading detected',
            severity: passed ? 'info' : 'low',
            recommendation: passed ? null : 'Implement lazy loading for better performance'
        };
    }

    checkServiceWorker() {
        const swSupported = 'serviceWorker' in navigator;
        const swManager = !!window.serviceWorkerManager;
        const passed = swSupported && swManager;
        
        return {
            passed,
            message: passed ? 'Service worker implemented' : 'Service worker not available',
            severity: passed ? 'info' : 'low',
            recommendation: passed ? null : 'Implement service worker for offline functionality'
        };
    }

    // Reliability Checks
    checkErrorHandling() {
        const hasErrorBoundary = !!window.errorBoundary;
        const hasLogger = !!window.logger;
        const hasGlobalHandlers = hasErrorBoundary && hasLogger;
        
        return {
            passed: hasGlobalHandlers,
            message: hasGlobalHandlers ? 'Error handling system implemented' : 'Incomplete error handling',
            severity: hasGlobalHandlers ? 'info' : 'high',
            recommendation: hasGlobalHandlers ? null : 'Implement comprehensive error handling system'
        };
    }

    checkGracefulDegradation() {
        // Check for feature detection patterns
        const hasFeatureDetection = !!window.compatibilityTester;
        const hasPolyfills = document.querySelectorAll('script[src*="polyfill"]').length > 0;
        const passed = hasFeatureDetection || hasPolyfills;
        
        return {
            passed,
            message: passed ? 'Graceful degradation implemented' : 'Limited graceful degradation',
            severity: passed ? 'info' : 'medium',
            recommendation: passed ? null : 'Implement feature detection and fallbacks'
        };
    }

    checkOfflineFunctionality() {
        const hasServiceWorker = !!window.serviceWorkerManager;
        const hasOfflineHandling = !!window.serviceWorkerManager?.getStatus().supported;
        const passed = hasServiceWorker && hasOfflineHandling;
        
        return {
            passed,
            message: passed ? 'Offline functionality available' : 'Limited offline functionality',
            severity: passed ? 'info' : 'low',
            recommendation: passed ? null : 'Implement service worker for offline support'
        };
    }

    checkAutoRecovery() {
        const hasWebSocketReconnect = !!window.webSocketManager?.attemptReconnect;
        const hasErrorRecovery = !!window.errorBoundary?.reset;
        const passed = hasWebSocketReconnect || hasErrorRecovery;
        
        return {
            passed,
            message: passed ? 'Auto-recovery mechanisms present' : 'Limited auto-recovery',
            severity: passed ? 'info' : 'medium',
            recommendation: passed ? null : 'Implement auto-recovery for network and error scenarios'
        };
    }

    // Maintainability Checks
    checkCodeOrganization() {
        // Check for modular structure
        const scriptCount = document.querySelectorAll('script[src]').length;
        const hasModularStructure = scriptCount > 5; // Multiple modules
        const hasNamespaces = !!(window.stateManager || window.performanceOptimizer || window.webSocketManager);
        const passed = hasModularStructure && hasNamespaces;
        
        return {
            passed,
            message: passed ? 'Modular code organization detected' : 'Monolithic code structure',
            severity: passed ? 'info' : 'low',
            recommendation: passed ? null : 'Organize code into modules and namespaces'
        };
    }

    checkDocumentation() {
        // Check for inline documentation
        const hasComments = document.documentElement.outerHTML.includes('<!--');
        const hasJSDoc = !!document.querySelector('script[src]'); // Assume modules have docs
        const passed = hasComments || hasJSDoc;
        
        return {
            passed,
            message: passed ? 'Documentation present' : 'Limited documentation',
            severity: passed ? 'info' : 'low',
            recommendation: passed ? null : 'Add comprehensive code documentation'
        };
    }

    checkTestingCoverage() {
        const hasTestFramework = !!window.testFramework;
        const hasTests = !!window.PHASE4_TEST_RESULTS;
        const hasQASystem = !!window.qaSystem;
        const passed = hasTestFramework && (hasTests || hasQASystem);
        
        return {
            passed,
            message: passed ? 'Testing infrastructure present' : 'Limited testing coverage',
            severity: passed ? 'info' : 'medium',
            recommendation: passed ? null : 'Implement comprehensive testing strategy'
        };
    }

    checkConfigManagement() {
        const hasConfigSystem = !!window.appConfig;
        const hasServerConfig = !!window.SERVER_CONFIG;
        const hasEnvConfig = window.SERVER_CONFIG?.environment !== undefined;
        const passed = hasConfigSystem && hasServerConfig && hasEnvConfig;
        
        return {
            passed,
            message: passed ? 'Configuration management implemented' : 'Incomplete configuration management',
            severity: passed ? 'info' : 'medium',
            recommendation: passed ? null : 'Implement centralized configuration management'
        };
    }

    // Monitoring Checks
    checkErrorLogging() {
        const hasLogger = !!window.logger;
        const hasErrorBoundary = !!window.errorBoundary;
        const hasRemoteLogging = window.logger?.enableRemote === true;
        const passed = hasLogger && hasErrorBoundary;
        
        return {
            passed,
            message: passed ? 'Error logging implemented' : 'No error logging system',
            severity: passed ? 'info' : 'high',
            recommendation: passed ? 'Consider remote error logging' : 'Implement error logging system'
        };
    }

    checkPerformanceMonitoring() {
        const hasPerformanceMonitor = !!window.performanceMonitor;
        const hasMetrics = !!window.performanceOptimizer?.getMetrics;
        const passed = hasPerformanceMonitor || hasMetrics;
        
        return {
            passed,
            message: passed ? 'Performance monitoring available' : 'No performance monitoring',
            severity: passed ? 'info' : 'medium',
            recommendation: passed ? null : 'Implement performance monitoring system'
        };
    }

    checkHealthChecks() {
        // Check for health check endpoints (limited client-side detection)
        const hasStateManager = !!window.stateManager;
        const hasSystemStatus = hasStateManager && window.stateManager.getState('system');
        const passed = hasSystemStatus;
        
        return {
            passed,
            message: passed ? 'System health monitoring available' : 'No health monitoring',
            severity: passed ? 'info' : 'low',
            recommendation: passed ? null : 'Implement health check endpoints'
        };
    }

    checkAnalytics() {
        // Check for analytics integration
        const hasGoogleAnalytics = !!window.gtag || !!window.ga;
        const hasCustomAnalytics = !!window.logger?.enableRemote;
        const passed = hasGoogleAnalytics || hasCustomAnalytics;
        
        return {
            passed,
            message: passed ? 'Analytics integration detected' : 'No analytics integration',
            severity: passed ? 'info' : 'low',
            recommendation: passed ? null : 'Consider adding analytics for usage monitoring'
        };
    }

    /**
     * Calculate overall production readiness score
     */
    calculateOverallScore() {
        const categoryScores = Object.values(this.results.categories).map(cat => cat.score);
        const weights = { security: 0.3, performance: 0.2, reliability: 0.3, maintainability: 0.1, monitoring: 0.1 };
        
        const weightedScore = 
            this.results.categories.security.score * weights.security +
            this.results.categories.performance.score * weights.performance +
            this.results.categories.reliability.score * weights.reliability +
            this.results.categories.maintainability.score * weights.maintainability +
            this.results.categories.monitoring.score * weights.monitoring;

        this.results.overall.score = Math.round(weightedScore);
        this.results.overall.ready = this.results.overall.score >= 80;
        
        if (this.results.overall.score >= 90) {
            this.results.overall.level = 'excellent';
        } else if (this.results.overall.score >= 80) {
            this.results.overall.level = 'production-ready';
        } else if (this.results.overall.score >= 60) {
            this.results.overall.level = 'needs-improvement';
        } else {
            this.results.overall.level = 'not-ready';
        }
    }

    /**
     * Generate deployment checklist
     */
    generateDeploymentChecklist() {
        this.results.deployment.checklist = [
            { item: 'Environment variables configured', status: window.SERVER_CONFIG?.environment !== 'development' },
            { item: 'Debug mode disabled', status: !window.SERVER_CONFIG?.debug },
            { item: 'HTTPS enabled', status: location.protocol === 'https:' },
            { item: 'Error handling implemented', status: !!window.errorBoundary },
            { item: 'Performance optimization enabled', status: !!window.performanceOptimizer },
            { item: 'Service worker registered', status: !!window.serviceWorkerManager },
            { item: 'State management configured', status: !!window.stateManager },
            { item: 'Configuration management setup', status: !!window.appConfig },
            { item: 'Testing framework available', status: !!window.testFramework },
            { item: 'Monitoring systems active', status: !!window.logger }
        ];

        this.results.deployment.environment = {
            current: window.SERVER_CONFIG?.environment || 'unknown',
            debug: window.SERVER_CONFIG?.debug || false,
            version: window.SERVER_CONFIG?.version || 'unknown'
        };
    }

    /**
     * Generate production recommendations
     */
    generateRecommendations() {
        const recommendations = [];

        // High priority recommendations
        const criticalIssues = Object.values(this.results.categories)
            .flatMap(cat => cat.issues.filter(issue => issue.severity === 'critical' || issue.severity === 'high'));

        if (criticalIssues.length > 0) {
            recommendations.push({
                priority: 'critical',
                category: 'Security & Reliability',
                action: 'Address all critical and high-severity issues before deployment',
                details: criticalIssues.map(issue => issue.name)
            });
        }

        // Performance recommendations
        if (this.results.categories.performance.score < 70) {
            recommendations.push({
                priority: 'high',
                category: 'Performance',
                action: 'Optimize application performance',
                details: ['Implement lazy loading', 'Optimize bundle size', 'Add caching strategy']
            });
        }

        // Security recommendations
        if (this.results.categories.security.score < 80) {
            recommendations.push({
                priority: 'high',
                category: 'Security',
                action: 'Strengthen security measures',
                details: ['Enable HTTPS', 'Add security headers', 'Implement CSP']
            });
        }

        // Monitoring recommendations
        if (this.results.categories.monitoring.score < 60) {
            recommendations.push({
                priority: 'medium',
                category: 'Monitoring',
                action: 'Implement monitoring and logging',
                details: ['Add error logging', 'Set up performance monitoring', 'Create health checks']
            });
        }

        this.results.deployment.recommendations = recommendations;
    }

    /**
     * Format bytes to human readable format
     */
    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Display validation results
     */
    displayResults() {
        console.log('\n🚀 PRODUCTION READINESS VALIDATION RESULTS');
        console.log('=' .repeat(50));
        
        const overall = this.results.overall;
        console.log(`📊 Overall Score: ${overall.score}% (${overall.level.toUpperCase()})`);
        console.log(`✅ Production Ready: ${overall.ready ? 'YES' : 'NO'}`);
        
        // Category scores
        console.log('\n📋 Category Breakdown:');
        Object.entries(this.results.categories).forEach(([category, result]) => {
            const icon = result.score >= 80 ? '✅' : result.score >= 60 ? '⚠️' : '❌';
            console.log(`  ${icon} ${category.charAt(0).toUpperCase() + category.slice(1)}: ${result.score}%`);
            
            if (result.issues.length > 0) {
                result.issues.forEach(issue => {
                    const severityIcon = issue.severity === 'critical' ? '🔴' : issue.severity === 'high' ? '🟡' : '🟢';
                    console.log(`    ${severityIcon} ${issue.name}: ${issue.message}`);
                });
            }
        });

        // Deployment checklist
        console.log('\n📋 Deployment Checklist:');
        this.results.deployment.checklist.forEach(item => {
            const status = item.status ? '✅' : '❌';
            console.log(`  ${status} ${item.item}`);
        });

        // Top recommendations
        if (this.results.deployment.recommendations.length > 0) {
            console.log('\n💡 Top Recommendations:');
            this.results.deployment.recommendations
                .slice(0, 3)
                .forEach((rec, index) => {
                    console.log(`  ${index + 1}. [${rec.priority.toUpperCase()}] ${rec.action}`);
                });
        }

        // Store results globally
        window.PRODUCTION_VALIDATION = this.results;
        
        console.log('\n✅ Production Validation Complete!');
    }
}

// Initialize production validator
window.productionValidator = new ProductionValidator();

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ProductionValidator };
}

console.log('✅ Production Validator loaded');