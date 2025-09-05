/**
 * Phase 5 Quality Assurance System for Erik Image Manager
 * Comprehensive testing, validation, and quality checks for the entire refactored system
 */

class QualityAssuranceSystem {
    constructor() {
        this.results = {
            phases: {
                phase1: { status: 'pending', issues: [], score: 0 },
                phase2: { status: 'pending', issues: [], score: 0 },
                phase3: { status: 'pending', issues: [], score: 0 },
                phase4: { status: 'pending', issues: [], score: 0 }
            },
            overall: { status: 'pending', score: 0, issues: [] },
            performance: {},
            compatibility: {},
            production: { ready: false, issues: [] }
        };
        
        this.logger = window.logger;
        this.testFramework = window.testFramework;
        this.startTime = null;
        this.endTime = null;
        
        console.log('🔍 Phase 5 Quality Assurance System initialized');
    }

    /**
     * Run complete quality assurance suite
     */
    async runCompleteQA() {
        this.startTime = performance.now();
        console.log('🚀 Starting Phase 5 Quality Assurance...');
        
        try {
            // Phase-by-phase validation
            await this.validatePhase1();
            await this.validatePhase2();
            await this.validatePhase3();
            await this.validatePhase4();
            
            // Cross-system integration testing
            await this.runIntegrationTests();
            
            // Performance analysis
            await this.runPerformanceAnalysis();
            
            // Browser compatibility testing
            await this.runCompatibilityTests();
            
            // Production readiness validation
            await this.validateProductionReadiness();
            
            // Calculate overall score
            this.calculateOverallScore();
            
            this.endTime = performance.now();
            this.displayResults();
            
            return this.results;
            
        } catch (error) {
            this.logger?.error('QA System failed:', error);
            throw error;
        }
    }

    /**
     * Validate Phase 1: Static Asset Extraction
     */
    async validatePhase1() {
        console.log('📋 Validating Phase 1: Static Asset Extraction');
        const issues = [];
        let score = 0;

        try {
            // Check CSS files exist and are properly structured
            const cssFiles = [
                'main.css', 'components.css', 'images.css', 
                'colmap.css', 'yard-map.css'
            ];
            
            for (const file of cssFiles) {
                try {
                    const response = await fetch(`/static/css/${file}`);
                    if (response.ok) {
                        const content = await response.text();
                        if (content.length > 100) { // Reasonable content size
                            score += 15;
                        } else {
                            issues.push(`CSS file ${file} appears to be too small or empty`);
                        }
                    } else {
                        issues.push(`CSS file ${file} not accessible (${response.status})`);
                    }
                } catch (error) {
                    issues.push(`Failed to load CSS file ${file}: ${error.message}`);
                }
            }

            // Check JavaScript modules exist and load properly
            const jsModules = [
                'utils.js', 'api.js', 'config.js', 'main.js',
                'image-manager.js', 'colmap.js', 'camera-overlay.js', 'yard-map.js'
            ];

            for (const file of jsModules) {
                try {
                    const response = await fetch(`/static/js/${file}`);
                    if (response.ok) {
                        const content = await response.text();
                        if (content.includes('class ') || content.includes('function ') || content.includes('const ')) {
                            score += 5;
                        } else {
                            issues.push(`JS module ${file} may not contain expected code structure`);
                        }
                    } else {
                        issues.push(`JS module ${file} not accessible (${response.status})`);
                    }
                } catch (error) {
                    issues.push(`Failed to load JS module ${file}: ${error.message}`);
                }
            }

            // Check template reduction
            if (document.documentElement.outerHTML.length < 50000) { // Much smaller than original 7942 lines
                score += 10;
            } else {
                issues.push('Template may not have been properly reduced in size');
            }

        } catch (error) {
            issues.push(`Phase 1 validation error: ${error.message}`);
        }

        this.results.phases.phase1 = {
            status: issues.length === 0 ? 'passed' : 'issues',
            issues,
            score: Math.min(score, 100)
        };
    }

    /**
     * Validate Phase 2: Template Modularization
     */
    async validatePhase2() {
        console.log('📋 Validating Phase 2: Template Modularization');
        const issues = [];
        let score = 0;

        try {
            // Check base template structure
            const hasBaseTemplate = document.querySelector('script[src*="main.js"]');
            if (hasBaseTemplate) {
                score += 20;
            } else {
                issues.push('Base template structure may not be properly implemented');
            }

            // Check for modular partials (by looking for common partial indicators)
            const partialIndicators = [
                '.tab-content', '.image-gallery', '.colmap-section', 
                '.yard-map-display', '.camera-grid'
            ];

            partialIndicators.forEach(selector => {
                if (document.querySelector(selector)) {
                    score += 8;
                } else {
                    issues.push(`Template partial for ${selector} not found in DOM`);
                }
            });

            // Check navigation structure
            const navElements = document.querySelectorAll('.nav-tabs li, .main-tabs li');
            if (navElements.length >= 4) { // Should have multiple tabs
                score += 20;
            } else {
                issues.push('Navigation structure may not be properly modularized');
            }

        } catch (error) {
            issues.push(`Phase 2 validation error: ${error.message}`);
        }

        this.results.phases.phase2 = {
            status: issues.length === 0 ? 'passed' : 'issues',
            issues,
            score: Math.min(score, 100)
        };
    }

    /**
     * Validate Phase 3: Configuration Management
     */
    async validatePhase3() {
        console.log('📋 Validating Phase 3: Configuration Management');
        const issues = [];
        let score = 0;

        try {
            // Check server config injection
            if (window.SERVER_CONFIG) {
                score += 20;
                
                const requiredConfig = [
                    'appTitle', 'externalIP', 'maxFileSize', 
                    'autoRefreshInterval', 'environment'
                ];
                
                requiredConfig.forEach(key => {
                    if (window.SERVER_CONFIG[key] !== undefined) {
                        score += 5;
                    } else {
                        issues.push(`Required config key '${key}' not found in SERVER_CONFIG`);
                    }
                });
            } else {
                issues.push('SERVER_CONFIG not injected into window');
            }

            // Check configuration API endpoints
            const configEndpoints = [
                '/api/config/client',
                '/api/config/environment',
                '/api/config/paths',
                '/api/config/limits'
            ];

            for (const endpoint of configEndpoints) {
                try {
                    const response = await fetch(endpoint, { 
                        method: 'GET',
                        headers: { 'Accept': 'application/json' }
                    });
                    if (response.ok) {
                        const data = await response.json();
                        if (typeof data === 'object' && data !== null) {
                            score += 7;
                        } else {
                            issues.push(`Config endpoint ${endpoint} returned invalid JSON`);
                        }
                    } else {
                        issues.push(`Config endpoint ${endpoint} returned ${response.status}`);
                    }
                } catch (error) {
                    issues.push(`Config endpoint ${endpoint} failed: ${error.message}`);
                }
            }

            // Check AppConfig class
            if (window.appConfig && typeof window.appConfig.get === 'function') {
                score += 15;
            } else {
                issues.push('AppConfig class not properly initialized');
            }

        } catch (error) {
            issues.push(`Phase 3 validation error: ${error.message}`);
        }

        this.results.phases.phase3 = {
            status: issues.length === 0 ? 'passed' : 'issues',
            issues,
            score: Math.min(score, 100)
        };
    }

    /**
     * Validate Phase 4: JavaScript Enhancement
     */
    async validatePhase4() {
        console.log('📋 Validating Phase 4: JavaScript Enhancement');
        const issues = [];
        let score = 0;

        try {
            // Check error handling system
            if (window.logger && window.errorBoundary) {
                score += 15;
                
                // Test error logging
                const logId = window.logger.info('QA Test Log');
                if (logId) {
                    score += 5;
                } else {
                    issues.push('Logger not properly logging messages');
                }
            } else {
                issues.push('Error handling system not properly initialized');
            }

            // Check state management
            if (window.stateManager && window.stateBinding) {
                score += 15;
                
                // Test state operations
                try {
                    window.stateManager.setState('qa-test', { test: true });
                    const state = window.stateManager.getState('qa-test');
                    if (state && state.test === true) {
                        score += 5;
                    } else {
                        issues.push('State management not working properly');
                    }
                } catch (error) {
                    issues.push(`State management error: ${error.message}`);
                }
            } else {
                issues.push('State management system not properly initialized');
            }

            // Check performance optimizer
            if (window.performanceOptimizer) {
                score += 10;
                
                const metrics = window.performanceOptimizer.getMetrics();
                if (metrics && typeof metrics.domElements === 'number') {
                    score += 5;
                } else {
                    issues.push('Performance optimizer metrics not available');
                }
            } else {
                issues.push('Performance optimizer not initialized');
            }

            // Check service worker manager
            if (window.serviceWorkerManager) {
                score += 10;
                
                const swStatus = window.serviceWorkerManager.getStatus();
                if (swStatus && typeof swStatus.supported === 'boolean') {
                    score += 5;
                } else {
                    issues.push('Service worker manager status not available');
                }
            } else {
                issues.push('Service worker manager not initialized');
            }

            // Check WebSocket manager
            if (window.webSocketManager) {
                score += 10;
                
                const wsStatus = window.webSocketManager.getStatus();
                if (wsStatus && typeof wsStatus.connected === 'boolean') {
                    score += 5;
                } else {
                    issues.push('WebSocket manager status not available');
                }
            } else {
                issues.push('WebSocket manager not initialized');
            }

            // Check test framework
            if (window.testFramework) {
                score += 10;
                
                if (typeof window.testFramework.test === 'function') {
                    score += 5;
                } else {
                    issues.push('Test framework API not properly exposed');
                }
            } else {
                issues.push('Test framework not initialized');
            }

        } catch (error) {
            issues.push(`Phase 4 validation error: ${error.message}`);
        }

        this.results.phases.phase4 = {
            status: issues.length === 0 ? 'passed' : 'issues',
            issues,
            score: Math.min(score, 100)
        };
    }

    /**
     * Run comprehensive integration tests
     */
    async runIntegrationTests() {
        console.log('🔧 Running Integration Tests');
        
        try {
            if (window.testFramework && window.PHASE4_TEST_RESULTS) {
                // Use existing Phase 4 integration test results
                const results = window.PHASE4_TEST_RESULTS;
                this.results.integration = {
                    executed: true,
                    results,
                    passed: results.failed === 0,
                    issues: results.errors || []
                };
            } else {
                this.results.integration = {
                    executed: false,
                    issues: ['Integration tests not executed or results not available']
                };
            }
        } catch (error) {
            this.results.integration = {
                executed: false,
                error: error.message,
                issues: [`Integration test execution failed: ${error.message}`]
            };
        }
    }

    /**
     * Run performance analysis
     */
    async runPerformanceAnalysis() {
        console.log('⚡ Running Performance Analysis');
        
        try {
            const performance = {
                memory: null,
                domElements: document.querySelectorAll('*').length,
                loadTime: this.endTime ? this.endTime - this.startTime : null,
                cacheStatus: {},
                bundleSize: 0
            };

            // Memory usage
            if (window.performance && window.performance.memory) {
                performance.memory = {
                    used: Math.round(window.performance.memory.usedJSHeapSize / 1024 / 1024),
                    total: Math.round(window.performance.memory.totalJSHeapSize / 1024 / 1024)
                };
            }

            // Cache status
            if (window.performanceOptimizer) {
                const metrics = window.performanceOptimizer.getMetrics();
                performance.cacheStatus = {
                    imageCache: metrics.imageCache?.size || 0,
                    fetchCache: metrics.fetchCache?.size || 0
                };
            }

            // Rough bundle size estimation
            const scriptTags = document.querySelectorAll('script[src]');
            performance.estimatedScripts = scriptTags.length;

            this.results.performance = performance;

            // Performance issues detection
            const issues = [];
            if (performance.memory && performance.memory.used > 100) {
                issues.push(`High memory usage: ${performance.memory.used}MB`);
            }
            if (performance.domElements > 1000) {
                issues.push(`High DOM element count: ${performance.domElements}`);
            }
            if (performance.loadTime && performance.loadTime > 5000) {
                issues.push(`Slow initialization: ${Math.round(performance.loadTime)}ms`);
            }

            this.results.performance.issues = issues;
            this.results.performance.score = Math.max(0, 100 - (issues.length * 20));

        } catch (error) {
            this.results.performance.error = error.message;
        }
    }

    /**
     * Run browser compatibility tests
     */
    async runCompatibilityTests() {
        console.log('🌐 Running Browser Compatibility Tests');
        
        try {
            const compatibility = {
                userAgent: navigator.userAgent,
                features: {
                    serviceWorker: 'serviceWorker' in navigator,
                    webSockets: 'WebSocket' in window,
                    localStorage: 'localStorage' in window,
                    fetch: 'fetch' in window,
                    intersectionObserver: 'IntersectionObserver' in window,
                    performanceObserver: 'PerformanceObserver' in window,
                    mutationObserver: 'MutationObserver' in window,
                    es6Classes: true, // If we got this far, classes work
                    es6Modules: true, // If scripts loaded, modules work
                    cssGrid: CSS.supports('display', 'grid'),
                    cssFlexbox: CSS.supports('display', 'flex')
                },
                issues: []
            };

            // Check for compatibility issues
            Object.entries(compatibility.features).forEach(([feature, supported]) => {
                if (!supported) {
                    compatibility.issues.push(`${feature} not supported in this browser`);
                }
            });

            // Calculate compatibility score
            const supportedCount = Object.values(compatibility.features).filter(Boolean).length;
            const totalFeatures = Object.keys(compatibility.features).length;
            compatibility.score = Math.round((supportedCount / totalFeatures) * 100);

            this.results.compatibility = compatibility;

        } catch (error) {
            this.results.compatibility = {
                error: error.message,
                score: 0,
                issues: [`Compatibility testing failed: ${error.message}`]
            };
        }
    }

    /**
     * Validate production readiness
     */
    async validateProductionReadiness() {
        console.log('🚀 Validating Production Readiness');
        
        const issues = [];
        let score = 100;

        try {
            // Check environment configuration
            if (!window.SERVER_CONFIG || window.SERVER_CONFIG.environment === 'development') {
                issues.push('Application appears to be in development mode');
                score -= 20;
            }

            // Check error handling
            if (!window.logger || !window.errorBoundary) {
                issues.push('Error handling system not fully implemented');
                score -= 25;
            }

            // Check service worker
            if (!window.serviceWorkerManager || !window.serviceWorkerManager.getStatus().supported) {
                issues.push('Service worker not supported or not implemented');
                score -= 15;
            }

            // Check state management
            if (!window.stateManager) {
                issues.push('State management system not implemented');
                score -= 15;
            }

            // Check performance optimization
            if (!window.performanceOptimizer) {
                issues.push('Performance optimization system not implemented');
                score -= 10;
            }

            // Check configuration system
            if (!window.appConfig || typeof window.appConfig.get !== 'function') {
                issues.push('Configuration management system not properly implemented');
                score -= 15;
            }

            this.results.production = {
                ready: issues.length === 0,
                score: Math.max(0, score),
                issues
            };

        } catch (error) {
            this.results.production = {
                ready: false,
                score: 0,
                issues: [...issues, `Production validation failed: ${error.message}`]
            };
        }
    }

    /**
     * Calculate overall quality score
     */
    calculateOverallScore() {
        const phaseScores = Object.values(this.results.phases).map(p => p.score);
        const phaseAverage = phaseScores.reduce((a, b) => a + b, 0) / phaseScores.length;
        
        const performanceScore = this.results.performance.score || 0;
        const compatibilityScore = this.results.compatibility.score || 0;
        const productionScore = this.results.production.score || 0;
        
        this.results.overall.score = Math.round(
            (phaseAverage * 0.4) + 
            (performanceScore * 0.2) + 
            (compatibilityScore * 0.2) + 
            (productionScore * 0.2)
        );

        // Collect all issues
        this.results.overall.issues = [
            ...this.results.phases.phase1.issues,
            ...this.results.phases.phase2.issues,
            ...this.results.phases.phase3.issues,
            ...this.results.phases.phase4.issues,
            ...(this.results.performance.issues || []),
            ...(this.results.compatibility.issues || []),
            ...(this.results.production.issues || [])
        ];

        this.results.overall.status = this.results.overall.score >= 85 ? 'excellent' :
                                     this.results.overall.score >= 70 ? 'good' :
                                     this.results.overall.score >= 50 ? 'fair' : 'needs-improvement';
    }

    /**
     * Display comprehensive results
     */
    displayResults() {
        const duration = this.endTime - this.startTime;
        
        console.log('\n🎯 PHASE 5 QUALITY ASSURANCE RESULTS');
        console.log('=' .repeat(50));
        console.log(`⏱️ Duration: ${Math.round(duration)}ms`);
        console.log(`📊 Overall Score: ${this.results.overall.score}%`);
        console.log(`🎭 Status: ${this.results.overall.status.toUpperCase()}`);
        
        console.log('\n📋 Phase Scores:');
        Object.entries(this.results.phases).forEach(([phase, result]) => {
            const status = result.score >= 85 ? '✅' : result.score >= 70 ? '⚠️' : '❌';
            console.log(`  ${status} ${phase.toUpperCase()}: ${result.score}%`);
            if (result.issues.length > 0) {
                result.issues.forEach(issue => console.log(`    • ${issue}`));
            }
        });

        console.log(`\n⚡ Performance: ${this.results.performance.score || 'N/A'}%`);
        if (this.results.performance.memory) {
            console.log(`  Memory: ${this.results.performance.memory.used}MB used`);
        }
        console.log(`  DOM Elements: ${this.results.performance.domElements}`);

        console.log(`\n🌐 Compatibility: ${this.results.compatibility.score || 'N/A'}%`);
        
        console.log(`\n🚀 Production Ready: ${this.results.production.ready ? 'YES' : 'NO'} (${this.results.production.score}%)`);

        if (this.results.overall.issues.length > 0) {
            console.log(`\n⚠️ Issues Found (${this.results.overall.issues.length}):`);
            this.results.overall.issues.forEach((issue, index) => {
                console.log(`  ${index + 1}. ${issue}`);
            });
        }

        console.log('\n🎉 Quality Assurance Complete!');
        
        // Store results globally for inspection
        window.QA_RESULTS = this.results;
        
        // Update state manager if available
        if (window.stateManager) {
            window.stateManager.setState('qa', {
                completed: true,
                results: this.results,
                timestamp: Date.now()
            });
        }
    }

    /**
     * Generate downloadable QA report
     */
    generateReport() {
        const report = {
            timestamp: new Date().toISOString(),
            system: 'Erik Image Manager',
            phase: 'Phase 5 - Quality Assurance',
            version: window.SERVER_CONFIG?.version || '4.0.0-phase5',
            environment: {
                userAgent: navigator.userAgent,
                url: window.location.href,
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight
                }
            },
            results: this.results,
            recommendations: this.generateRecommendations()
        };

        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `erik-qa-report-${Date.now()}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        console.log('📥 QA Report downloaded');
    }

    /**
     * Generate recommendations based on results
     */
    generateRecommendations() {
        const recommendations = [];
        
        if (this.results.overall.score < 70) {
            recommendations.push('Overall quality score is below recommended threshold. Address critical issues first.');
        }
        
        if (this.results.performance.score < 80) {
            recommendations.push('Performance optimization needed. Consider implementing lazy loading and reducing bundle size.');
        }
        
        if (this.results.compatibility.score < 90) {
            recommendations.push('Browser compatibility issues detected. Consider polyfills or feature detection.');
        }
        
        if (!this.results.production.ready) {
            recommendations.push('Not ready for production deployment. Address production readiness issues.');
        }
        
        if (this.results.overall.issues.length > 10) {
            recommendations.push('High number of issues detected. Prioritize fixes based on severity.');
        }

        return recommendations;
    }
}

// Initialize QA System
window.qaSystem = new QualityAssuranceSystem();

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { QualityAssuranceSystem };
}

console.log('✅ Phase 5 Quality Assurance System loaded');