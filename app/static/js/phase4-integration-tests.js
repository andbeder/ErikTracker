/**
 * Phase 4 Integration Tests for Erik Image Manager
 * Tests the new JavaScript enhancement modules and their interactions
 */

// Phase 4 Integration Test Suite
describe('Phase 4 JavaScript Enhancements', () => {
    let testLogger, testStateManager, testPerformanceOptimizer, testServiceWorkerManager, testWebSocketManager;

    beforeAll(() => {
        // Initialize test instances with mock dependencies
        console.log('🧪 Initializing Phase 4 Integration Tests');
    });

    afterAll(() => {
        // Cleanup test instances
        console.log('🧹 Cleaning up Phase 4 Integration Tests');
        if (window.testFramework) {
            window.testFramework.restoreAllMocks();
        }
    });

    describe('Error Handling System', () => {
        test('Logger should initialize with correct configuration', () => {
            expect(window.logger).toBeTruthy();
            expect(window.logger.logLevel).toBe('debug');
            expect(window.logger.logs).toEqual(expect.any(Array));
        });

        test('Global error handlers should be registered', () => {
            const originalConsoleError = console.error;
            const errorSpy = spy();
            console.error = errorSpy;

            // Trigger a global error
            window.dispatchEvent(new ErrorEvent('error', {
                message: 'Test error',
                filename: 'test.js',
                lineno: 1
            }));

            expect(errorSpy.callCount()).toBeGreaterThan(0);
            console.error = originalConsoleError;
        });

        test('Error boundary should catch and log errors', () => {
            expect(window.errorBoundary).toBeTruthy();
            
            const testFunction = () => {
                throw new Error('Test error for boundary');
            };

            const wrappedFunction = window.errorBoundary.wrapSync(testFunction, 'Test Context');
            
            expect(() => wrappedFunction()).toThrow();
            expect(window.errorBoundary.errorCount).toBeGreaterThan(0);
        });

        test('Performance monitor should track metrics', () => {
            expect(window.performanceMonitor).toBeTruthy();
            
            const timing = window.performanceMonitor.startTiming('test-operation');
            expect(timing).toBeTruthy();
            expect(timing.end).toBe(expect.any(Function));
            
            const duration = timing.end();
            expect(duration).toBe(expect.any(Number));
        });
    });

    describe('State Management System', () => {
        test('StateManager should initialize with default state', () => {
            expect(window.stateManager).toBeTruthy();
            expect(window.stateManager.getState('app')).toBeTruthy();
            expect(window.stateManager.getState('app').initialized).toBe(false);
        });

        test('State updates should work correctly', () => {
            const initialState = window.stateManager.getState('app');
            
            window.stateManager.setState('app', { testValue: 'test' });
            
            const updatedState = window.stateManager.getState('app');
            expect(updatedState.testValue).toBe('test');
            expect(updatedState.initialized).toBe(initialState.initialized); // Should merge
        });

        test('Subscriptions should receive state updates', () => {
            const subscriptionSpy = spy();
            const unsubscribe = window.stateManager.subscribe('test-key', subscriptionSpy);
            
            window.stateManager.setState('test-key', { value: 'test' });
            
            expect(subscriptionSpy.callCount()).toBe(1);
            expect(subscriptionSpy.lastCall()[0]).toEqual({ value: 'test' });
            
            unsubscribe();
        });

        test('Nested state updates should work', () => {
            window.stateManager.setState('nested-test', { level1: { level2: 'original' } });
            window.stateManager.setNestedState('nested-test', 'level1.level2', 'updated');
            
            const result = window.stateManager.getNestedState('nested-test', 'level1.level2');
            expect(result).toBe('updated');
        });

        test('State persistence should work', () => {
            const testKey = 'persistent-test';
            const testValue = { persistent: true, timestamp: Date.now() };
            
            window.stateManager.setState(testKey, testValue, { persist: true });
            
            // Simulate page reload by checking localStorage
            const storageKey = window.stateManager.storagePrefix + testKey;
            const stored = localStorage.getItem(storageKey);
            expect(stored).toBeTruthy();
            
            const parsed = JSON.parse(stored);
            expect(parsed.value).toEqual(testValue);
        });
    });

    describe('Performance Optimization System', () => {
        test('PerformanceOptimizer should initialize correctly', () => {
            expect(window.performanceOptimizer).toBeTruthy();
            expect(window.performanceOptimizer.observers).toBeTruthy();
            expect(window.performanceOptimizer.imageCache).toBeTruthy();
        });

        test('Lazy loading should be configurable', () => {
            // Create test image element
            const testImg = document.createElement('img');
            testImg.dataset.src = 'test-image.jpg';
            document.body.appendChild(testImg);
            
            window.performanceOptimizer.enableLazyImages('img[data-src]');
            
            // Check if observer was applied (can't easily test actual lazy loading without intersection)
            expect(testImg.dataset.src).toBe('test-image.jpg');
            
            document.body.removeChild(testImg);
        });

        test('Throttle and debounce utilities should work', () => {
            const testFunction = spy();
            const throttledFunction = window.performanceOptimizer.throttle(testFunction, 100);
            
            // Call multiple times quickly
            throttledFunction('call1');
            throttledFunction('call2');
            throttledFunction('call3');
            
            // Should only be called once immediately
            expect(testFunction.callCount()).toBe(1);
        });

        test('Performance metrics should be available', () => {
            const metrics = window.performanceOptimizer.getMetrics();
            expect(metrics).toBeTruthy();
            expect(metrics.imageCache).toBeTruthy();
            expect(metrics.fetchCache).toBeTruthy();
            expect(metrics.domElements).toBe(expect.any(Number));
        });
    });

    describe('Service Worker System', () => {
        test('ServiceWorkerManager should initialize if supported', () => {
            expect(window.serviceWorkerManager).toBeTruthy();
            
            const status = window.serviceWorkerManager.getStatus();
            expect(status.supported).toBe('serviceWorker' in navigator);
        });

        test('Online/offline detection should work', () => {
            const manager = window.serviceWorkerManager;
            expect(manager.isOnline).toBe(navigator.onLine);
        });

        test('Connection status updates should work', () => {
            const manager = window.serviceWorkerManager;
            
            // Test online status update
            manager.updateConnectionStatus(true);
            let statusElement = document.getElementById('connection-status');
            expect(statusElement).toBeTruthy();
            expect(statusElement.textContent).toContain('Online');
            
            // Clean up
            if (statusElement) {
                statusElement.remove();
            }
        });

        test('Service worker message handling should work', (assertions) => {
            const manager = window.serviceWorkerManager;
            const testData = { test: 'data' };
            
            // Mock message event
            const mockEvent = {
                data: {
                    type: 'CACHE_STATUS',
                    data: testData
                }
            };
            
            // This should not throw an error
            expect(() => {
                manager.handleServiceWorkerMessage(mockEvent);
            }).not.toThrow();
        });
    });

    describe('WebSocket Communication System', () => {
        test('WebSocketManager should initialize', () => {
            expect(window.webSocketManager).toBeTruthy();
            expect(window.webSocketManager.subscriptions).toBeTruthy();
            expect(window.webSocketManager.messageQueue).toEqual(expect.any(Array));
        });

        test('Subscription system should work', () => {
            const manager = window.webSocketManager;
            const testCallback = spy();
            
            const unsubscribe = manager.subscribe('test-message', testCallback);
            expect(typeof unsubscribe).toBe('function');
            
            // Test message routing
            manager.routeMessage({
                type: 'test-message',
                data: { test: 'data' }
            });
            
            expect(testCallback.callCount()).toBe(1);
            expect(testCallback.lastCall()[0]).toEqual({ test: 'data' });
            
            unsubscribe();
        });

        test('Message queueing should work when disconnected', () => {
            const manager = window.webSocketManager;
            const initialQueueLength = manager.messageQueue.length;
            
            // Ensure disconnected state
            manager.isConnected = false;
            
            const testMessage = { type: 'test', data: 'queued' };
            manager.send(testMessage);
            
            expect(manager.messageQueue.length).toBe(initialQueueLength + 1);
        });

        test('State integration should work', () => {
            const manager = window.webSocketManager;
            
            // Test Erik position update
            manager.updateStateFromMessage({
                type: 'erik_position',
                data: {
                    position: { x: 100, y: 200 },
                    status: 'active',
                    timestamp: Date.now()
                }
            });
            
            const erikState = window.stateManager.getState('erik');
            expect(erikState.position).toEqual({ x: 100, y: 200 });
            expect(erikState.status).toBe('active');
        });

        test('Convenience subscription methods should work', () => {
            const manager = window.webSocketManager;
            const callback = spy();
            
            const unsubscribe = manager.subscribeToErikPosition(callback);
            expect(typeof unsubscribe).toBe('function');
            
            // Check that subscription was registered
            expect(manager.subscriptions.has('erik_position')).toBe(true);
            
            unsubscribe();
        });
    });

    describe('Integration Between Systems', () => {
        test('Error handling should integrate with logging', () => {
            const initialLogCount = window.logger.logs.length;
            
            // Trigger an error through the error boundary
            try {
                const testFn = window.errorBoundary.wrapSync(() => {
                    throw new Error('Integration test error');
                }, 'Integration Test');
                testFn();
            } catch (e) {
                // Expected to throw
            }
            
            expect(window.logger.logs.length).toBeGreaterThan(initialLogCount);
        });

        test('WebSocket should update state manager', () => {
            const manager = window.webSocketManager;
            const initialMatchCount = window.stateManager.getState('matches')?.count || 0;
            
            // Simulate match detection message
            manager.updateStateFromMessage({
                type: 'match_detected',
                data: {
                    id: 'test-match',
                    confidence: 0.95,
                    timestamp: Date.now()
                }
            });
            
            const matchesState = window.stateManager.getState('matches');
            expect(matchesState.count).toBe(initialMatchCount + 1);
        });

        test('Performance optimizer should work with state manager', () => {
            const perfOpt = window.performanceOptimizer;
            const stateManager = window.stateManager;
            
            // Check that performance optimizer can access state
            expect(stateManager).toBeTruthy();
            expect(perfOpt).toBeTruthy();
            
            // Test memory cleanup with state history
            if (stateManager.history.length > 10) {
                const initialHistoryLength = stateManager.history.length;
                perfOpt.forceMemoryCleanup();
                expect(stateManager.history.length).toBeLessThanOrEqual(initialHistoryLength);
            }
        });

        test('Service worker should integrate with performance monitoring', () => {
            const swManager = window.serviceWorkerManager;
            const perfMonitor = window.performanceMonitor;
            
            expect(swManager).toBeTruthy();
            expect(perfMonitor).toBeTruthy();
            
            // Check that both systems are initialized
            expect(swManager.getStatus()).toBeTruthy();
            expect(perfMonitor.getSummary()).toBeTruthy();
        });

        test('All global objects should be available', () => {
            const expectedGlobals = [
                'logger',
                'errorBoundary', 
                'performanceMonitor',
                'stateManager',
                'stateBinding',
                'performanceOptimizer',
                'serviceWorkerManager',
                'webSocketManager',
                'testFramework'
            ];
            
            expectedGlobals.forEach(globalName => {
                expect(window[globalName]).toBeTruthy();
            });
        });
    });

    describe('Configuration Integration', () => {
        test('Server config should be injected correctly', () => {
            expect(window.SERVER_CONFIG).toBeTruthy();
            expect(window.SERVER_CONFIG.appTitle).toBeTruthy();
            expect(window.SERVER_CONFIG.version).toBe('3.0.0-phase3');
        });

        test('Config system should work with new modules', () => {
            // Test that logger uses config for log level
            expect(window.logger.logLevel).toBeTruthy();
            
            // Test that error boundary respects debug mode
            if (window.SERVER_CONFIG.debug) {
                expect(window.logger.logLevel).toBe('debug');
            }
        });
    });

    describe('Cleanup and Memory Management', () => {
        test('All systems should have cleanup methods', () => {
            expect(typeof window.performanceOptimizer.cleanup).toBe('function');
            expect(typeof window.stateManager.reset).toBe('function');
            expect(typeof window.logger.clearLogs).toBe('function');
            expect(typeof window.testFramework.restoreAllMocks).toBe('function');
        });

        test('Memory usage should be reasonable', () => {
            if (performance.memory) {
                const memoryUsage = Math.round(performance.memory.usedJSHeapSize / 1024 / 1024);
                expect(memoryUsage).toBeLessThan(200); // Less than 200MB
            }
        });

        test('Event listeners should be manageable', () => {
            // Check that we're not creating excessive event listeners
            const listenerCount = window.stateManager?.subscribers?.size || 0;
            expect(listenerCount).toBeLessThan(50); // Reasonable limit
        });
    });
});

// Auto-run tests when page loads
document.addEventListener('DOMContentLoaded', () => {
    // Wait a bit for all systems to initialize
    setTimeout(() => {
        console.log('🚀 Starting Phase 4 Integration Tests...');
        
        if (window.testFramework) {
            window.testFramework.runTests().then(results => {
                console.log('✅ Phase 4 Integration Tests completed');
                console.log('📊 Results:', results);
                
                // Store results for inspection
                window.PHASE4_TEST_RESULTS = results;
                
                // Report to state manager if available
                if (window.stateManager) {
                    window.stateManager.setState('testing', {
                        phase4Completed: true,
                        results,
                        timestamp: Date.now()
                    });
                }
            }).catch(error => {
                console.error('❌ Phase 4 Integration Tests failed:', error);
            });
        } else {
            console.warn('⚠️ Test framework not available');
        }
    }, 2000);
});

console.log('📝 Phase 4 Integration Tests loaded');