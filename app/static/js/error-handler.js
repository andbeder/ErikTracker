/**
 * Error Handling and Logging System for Erik Image Manager
 * Provides centralized error management, logging, and reporting
 */

class Logger {
    constructor() {
        this.logLevel = this.getLogLevel();
        this.logs = [];
        this.maxLogs = 1000;
        this.enableConsole = true;
        this.enableRemote = false;
        this.remoteEndpoint = '/api/logs';
        
        this.initializeLogger();
    }

    /**
     * Get log level from configuration
     */
    getLogLevel() {
        if (window.SERVER_CONFIG?.debug) return 'debug';
        if (window.SERVER_CONFIG?.environment === 'development') return 'info';
        return 'warn';
    }

    /**
     * Initialize logger with global error handlers
     */
    initializeLogger() {
        // Global error handler
        window.addEventListener('error', (event) => {
            this.error('Global Error:', {
                message: event.message,
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno,
                error: event.error?.stack || event.error?.toString()
            });
        });

        // Unhandled promise rejection handler
        window.addEventListener('unhandledrejection', (event) => {
            this.error('Unhandled Promise Rejection:', {
                reason: event.reason?.toString() || event.reason,
                stack: event.reason?.stack
            });
        });

        // Capture fetch errors
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            try {
                const response = await originalFetch(...args);
                if (!response.ok) {
                    this.warn(`HTTP ${response.status}:`, {
                        url: args[0],
                        status: response.status,
                        statusText: response.statusText
                    });
                }
                return response;
            } catch (error) {
                this.error('Fetch Error:', {
                    url: args[0],
                    error: error.message,
                    stack: error.stack
                });
                throw error;
            }
        };
    }

    /**
     * Log message with specified level
     */
    log(level, message, data = null, context = null) {
        const timestamp = new Date().toISOString();
        const logEntry = {
            timestamp,
            level,
            message,
            data,
            context: context || this.getContext(),
            id: this.generateId()
        };

        // Add to internal log store
        this.logs.push(logEntry);
        if (this.logs.length > this.maxLogs) {
            this.logs.shift();
        }

        // Console output
        if (this.enableConsole && this.shouldLog(level)) {
            this.outputToConsole(logEntry);
        }

        // Remote logging (if enabled)
        if (this.enableRemote && this.shouldLog(level)) {
            this.sendToRemote(logEntry);
        }

        return logEntry.id;
    }

    /**
     * Logging convenience methods
     */
    debug(message, data, context) { return this.log('debug', message, data, context); }
    info(message, data, context) { return this.log('info', message, data, context); }
    warn(message, data, context) { return this.log('warn', message, data, context); }
    error(message, data, context) { return this.log('error', message, data, context); }

    /**
     * Check if message should be logged based on level
     */
    shouldLog(level) {
        const levels = { debug: 0, info: 1, warn: 2, error: 3 };
        return levels[level] >= levels[this.logLevel];
    }

    /**
     * Output log entry to console
     */
    outputToConsole(entry) {
        const style = this.getConsoleStyle(entry.level);
        const prefix = `[${entry.timestamp}] ${entry.level.toUpperCase()}:`;
        
        if (entry.data) {
            console[entry.level](prefix, entry.message, entry.data);
        } else {
            console[entry.level](prefix, entry.message);
        }
    }

    /**
     * Get console styling for log level
     */
    getConsoleStyle(level) {
        const styles = {
            debug: 'color: #888',
            info: 'color: #007bff',
            warn: 'color: #ffc107',
            error: 'color: #dc3545; font-weight: bold'
        };
        return styles[level] || '';
    }

    /**
     * Send log to remote endpoint
     */
    async sendToRemote(entry) {
        try {
            await fetch(this.remoteEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(entry)
            });
        } catch (error) {
            // Avoid infinite loops by not logging remote logging errors
            console.warn('Failed to send log to remote:', error);
        }
    }

    /**
     * Get current context information
     */
    getContext() {
        return {
            url: window.location.href,
            userAgent: navigator.userAgent,
            timestamp: Date.now(),
            viewport: {
                width: window.innerWidth,
                height: window.innerHeight
            },
            memory: performance.memory ? {
                used: Math.round(performance.memory.usedJSHeapSize / 1024 / 1024),
                total: Math.round(performance.memory.totalJSHeapSize / 1024 / 1024)
            } : null
        };
    }

    /**
     * Generate unique ID for log entries
     */
    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }

    /**
     * Get recent logs
     */
    getRecentLogs(count = 50, level = null) {
        let logs = this.logs;
        if (level) {
            logs = logs.filter(log => log.level === level);
        }
        return logs.slice(-count);
    }

    /**
     * Clear all logs
     */
    clearLogs() {
        this.logs = [];
        this.info('Log history cleared');
    }

    /**
     * Export logs as JSON
     */
    exportLogs() {
        const data = {
            exported: new Date().toISOString(),
            config: {
                logLevel: this.logLevel,
                environment: window.SERVER_CONFIG?.environment || 'unknown'
            },
            logs: this.logs
        };
        return JSON.stringify(data, null, 2);
    }

    /**
     * Get log statistics
     */
    getStats() {
        const stats = { debug: 0, info: 0, warn: 0, error: 0 };
        this.logs.forEach(log => stats[log.level]++);
        return {
            total: this.logs.length,
            levels: stats,
            oldestLog: this.logs[0]?.timestamp,
            newestLog: this.logs[this.logs.length - 1]?.timestamp
        };
    }
}

class ErrorBoundary {
    constructor() {
        this.logger = window.logger || new Logger();
        this.errorCount = 0;
        this.maxErrors = 10;
        this.errorCooldown = 5000; // 5 seconds
        this.lastErrorTime = 0;
    }

    /**
     * Wrap async function with error boundary
     */
    wrapAsync(fn, context = 'Unknown') {
        return async (...args) => {
            try {
                return await fn(...args);
            } catch (error) {
                this.handleError(error, context, { args });
                throw error;
            }
        };
    }

    /**
     * Wrap sync function with error boundary
     */
    wrapSync(fn, context = 'Unknown') {
        return (...args) => {
            try {
                return fn(...args);
            } catch (error) {
                this.handleError(error, context, { args });
                throw error;
            }
        };
    }

    /**
     * Handle caught errors
     */
    handleError(error, context, metadata = {}) {
        const now = Date.now();
        
        // Rate limiting to prevent error spam
        if (now - this.lastErrorTime < this.errorCooldown) {
            return;
        }
        
        this.errorCount++;
        this.lastErrorTime = now;

        const errorInfo = {
            message: error.message,
            stack: error.stack,
            name: error.name,
            context,
            metadata,
            errorCount: this.errorCount,
            timestamp: now
        };

        this.logger.error('Error Boundary Caught:', errorInfo);

        // Show user-friendly error if too many errors
        if (this.errorCount >= this.maxErrors) {
            this.showCriticalError();
        }
    }

    /**
     * Show critical error dialog
     */
    showCriticalError() {
        const message = `
            <div style="text-align: center; padding: 20px;">
                <h3 style="color: #dc3545; margin-bottom: 15px;">⚠️ Multiple Errors Detected</h3>
                <p>The application has encountered several errors. Please try refreshing the page.</p>
                <p><strong>Error Count:</strong> ${this.errorCount}</p>
                <div style="margin-top: 20px;">
                    <button onclick="location.reload()" style="background: #dc3545; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-right: 10px;">
                        🔄 Reload Page
                    </button>
                    <button onclick="window.errorBoundary.downloadErrorReport()" style="background: #6c757d; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer;">
                        📥 Download Error Report
                    </button>
                </div>
            </div>
        `;
        
        Utils.createModal('Critical Error', message, true);
    }

    /**
     * Download error report
     */
    downloadErrorReport() {
        const report = {
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent,
            url: window.location.href,
            errorCount: this.errorCount,
            config: window.SERVER_CONFIG || {},
            logs: this.logger.getRecentLogs(100),
            stats: this.logger.getStats()
        };

        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `erik-error-report-${Date.now()}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }

    /**
     * Reset error count
     */
    reset() {
        this.errorCount = 0;
        this.lastErrorTime = 0;
        this.logger.info('Error boundary reset');
    }
}

class PerformanceMonitor {
    constructor() {
        this.logger = window.logger || new Logger();
        this.metrics = new Map();
        this.observers = [];
        this.thresholds = {
            longTask: 50, // ms
            memoryWarning: 100, // MB
            fetchTimeout: 10000 // ms
        };
        
        this.initializeMonitoring();
    }

    /**
     * Initialize performance monitoring
     */
    initializeMonitoring() {
        // Long task observer
        if ('PerformanceObserver' in window) {
            try {
                const longTaskObserver = new PerformanceObserver((list) => {
                    list.getEntries().forEach((entry) => {
                        if (entry.duration > this.thresholds.longTask) {
                            this.logger.warn('Long Task Detected:', {
                                duration: Math.round(entry.duration),
                                startTime: Math.round(entry.startTime),
                                name: entry.name
                            });
                        }
                    });
                });
                longTaskObserver.observe({ entryTypes: ['longtask'] });
                this.observers.push(longTaskObserver);
            } catch (e) {
                this.logger.debug('Long task observer not supported');
            }
        }

        // Memory monitoring
        if (performance.memory) {
            setInterval(() => this.checkMemoryUsage(), 30000);
        }

        // Page performance monitoring
        window.addEventListener('load', () => {
            setTimeout(() => this.reportPagePerformance(), 1000);
        });
    }

    /**
     * Start timing measurement
     */
    startTiming(name) {
        const startTime = performance.now();
        this.metrics.set(name, { startTime, measurements: [] });
        return {
            end: () => this.endTiming(name),
            mark: (label) => this.markTiming(name, label)
        };
    }

    /**
     * End timing measurement
     */
    endTiming(name) {
        const metric = this.metrics.get(name);
        if (!metric) return null;

        const duration = performance.now() - metric.startTime;
        metric.duration = duration;
        
        this.logger.debug(`Performance: ${name}`, {
            duration: Math.round(duration),
            measurements: metric.measurements
        });

        return duration;
    }

    /**
     * Add timing mark
     */
    markTiming(name, label) {
        const metric = this.metrics.get(name);
        if (metric) {
            const elapsed = performance.now() - metric.startTime;
            metric.measurements.push({ label, elapsed: Math.round(elapsed) });
        }
    }

    /**
     * Check memory usage
     */
    checkMemoryUsage() {
        if (!performance.memory) return;

        const used = Math.round(performance.memory.usedJSHeapSize / 1024 / 1024);
        const total = Math.round(performance.memory.totalJSHeapSize / 1024 / 1024);

        if (used > this.thresholds.memoryWarning) {
            this.logger.warn('High Memory Usage:', { used, total, percentage: Math.round(used / total * 100) });
        }
    }

    /**
     * Report page performance metrics
     */
    reportPagePerformance() {
        const navigation = performance.getEntriesByType('navigation')[0];
        if (navigation) {
            this.logger.info('Page Performance:', {
                domContentLoaded: Math.round(navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart),
                loadComplete: Math.round(navigation.loadEventEnd - navigation.loadEventStart),
                firstPaint: this.getFirstPaint(),
                largestContentfulPaint: this.getLCP()
            });
        }
    }

    /**
     * Get First Paint timing
     */
    getFirstPaint() {
        const paintEntries = performance.getEntriesByType('paint');
        const firstPaint = paintEntries.find(entry => entry.name === 'first-paint');
        return firstPaint ? Math.round(firstPaint.startTime) : null;
    }

    /**
     * Get Largest Contentful Paint
     */
    getLCP() {
        return new Promise((resolve) => {
            if ('PerformanceObserver' in window) {
                try {
                    const observer = new PerformanceObserver((list) => {
                        const entries = list.getEntries();
                        const lastEntry = entries[entries.length - 1];
                        resolve(Math.round(lastEntry.startTime));
                        observer.disconnect();
                    });
                    observer.observe({ entryTypes: ['largest-contentful-paint'] });
                    
                    // Timeout after 10 seconds
                    setTimeout(() => {
                        observer.disconnect();
                        resolve(null);
                    }, 10000);
                } catch (e) {
                    resolve(null);
                }
            } else {
                resolve(null);
            }
        });
    }

    /**
     * Get performance summary
     */
    getSummary() {
        const summary = {
            metrics: Object.fromEntries(this.metrics),
            memory: performance.memory ? {
                used: Math.round(performance.memory.usedJSHeapSize / 1024 / 1024),
                total: Math.round(performance.memory.totalJSHeapSize / 1024 / 1024)
            } : null,
            timing: performance.timing ? {
                pageLoad: performance.timing.loadEventEnd - performance.timing.navigationStart,
                domReady: performance.timing.domContentLoadedEventEnd - performance.timing.navigationStart
            } : null
        };
        
        return summary;
    }
}

// Initialize global error handling system
window.logger = new Logger();
window.errorBoundary = new ErrorBoundary();
window.performanceMonitor = new PerformanceMonitor();

// Export classes for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { Logger, ErrorBoundary, PerformanceMonitor };
}

// Global helper for wrapping functions
window.withErrorBoundary = (fn, context) => window.errorBoundary.wrapSync(fn, context);
window.withAsyncErrorBoundary = (fn, context) => window.errorBoundary.wrapAsync(fn, context);

console.log('✅ Error Handling & Performance Monitoring initialized');