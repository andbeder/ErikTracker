/**
 * Unit Testing Framework for Erik Image Manager
 * Lightweight testing framework for client-side JavaScript testing
 */

class TestFramework {
    constructor() {
        this.tests = new Map();
        this.suites = new Map();
        this.results = {
            total: 0,
            passed: 0,
            failed: 0,
            skipped: 0,
            errors: []
        };
        this.currentSuite = null;
        this.beforeEachHooks = [];
        this.afterEachHooks = [];
        this.beforeAllHooks = [];
        this.afterAllHooks = [];
        this.logger = window.logger;
        this.startTime = null;
        this.endTime = null;
        this.mockRegistry = new Map();
    }

    /**
     * Create a test suite
     */
    describe(name, callback) {
        const suite = {
            name,
            tests: [],
            beforeEach: [],
            afterEach: [],
            beforeAll: [],
            afterAll: [],
            only: false,
            skip: false
        };

        this.suites.set(name, suite);
        const previousSuite = this.currentSuite;
        this.currentSuite = suite;

        try {
            callback();
        } catch (error) {
            this.logger?.error(`Suite setup error: ${name}`, error);
        }

        this.currentSuite = previousSuite;
        return suite;
    }

    /**
     * Create a test case
     */
    test(name, callback, options = {}) {
        const { timeout = 5000, skip = false, only = false } = options;
        
        const testCase = {
            name,
            callback,
            timeout,
            skip,
            only,
            suite: this.currentSuite?.name || 'Global',
            id: this.generateId()
        };

        if (this.currentSuite) {
            this.currentSuite.tests.push(testCase);
        } else {
            this.tests.set(testCase.id, testCase);
        }

        return testCase;
    }

    /**
     * Alias for test
     */
    it(name, callback, options = {}) {
        return this.test(name, callback, options);
    }

    /**
     * Skip a test
     */
    skip(name, callback) {
        return this.test(name, callback, { skip: true });
    }

    /**
     * Run only this test
     */
    only(name, callback) {
        return this.test(name, callback, { only: true });
    }

    /**
     * Setup hooks
     */
    beforeEach(callback) {
        if (this.currentSuite) {
            this.currentSuite.beforeEach.push(callback);
        } else {
            this.beforeEachHooks.push(callback);
        }
    }

    afterEach(callback) {
        if (this.currentSuite) {
            this.currentSuite.afterEach.push(callback);
        } else {
            this.afterEachHooks.push(callback);
        }
    }

    beforeAll(callback) {
        if (this.currentSuite) {
            this.currentSuite.beforeAll.push(callback);
        } else {
            this.beforeAllHooks.push(callback);
        }
    }

    afterAll(callback) {
        if (this.currentSuite) {
            this.currentSuite.afterAll.push(callback);
        } else {
            this.afterAllHooks.push(callback);
        }
    }

    /**
     * Run all tests
     */
    async runTests() {
        this.startTime = performance.now();
        this.resetResults();

        this.logger?.info('🧪 Starting test execution...');

        try {
            // Run global beforeAll hooks
            await this.runHooks(this.beforeAllHooks);

            // Run individual tests
            for (const [id, test] of this.tests) {
                await this.runSingleTest(test);
            }

            // Run test suites
            for (const [name, suite] of this.suites) {
                await this.runTestSuite(suite);
            }

            // Run global afterAll hooks
            await this.runHooks(this.afterAllHooks);

        } catch (error) {
            this.logger?.error('Test execution failed:', error);
        }

        this.endTime = performance.now();
        this.displayResults();
        return this.results;
    }

    /**
     * Run a single test suite
     */
    async runTestSuite(suite) {
        this.logger?.info(`📁 Running suite: ${suite.name}`);

        try {
            // Run beforeAll hooks for suite
            await this.runHooks(suite.beforeAll);

            // Check for only tests
            const onlyTests = suite.tests.filter(test => test.only);
            const testsToRun = onlyTests.length > 0 ? onlyTests : suite.tests;

            // Run tests
            for (const test of testsToRun) {
                await this.runHooks(suite.beforeEach);
                await this.runHooks(this.beforeEachHooks);
                
                await this.runSingleTest(test);
                
                await this.runHooks(this.afterEachHooks);
                await this.runHooks(suite.afterEach);
            }

            // Run afterAll hooks for suite
            await this.runHooks(suite.afterAll);

        } catch (error) {
            this.logger?.error(`Suite error: ${suite.name}`, error);
        }
    }

    /**
     * Run a single test
     */
    async runSingleTest(test) {
        if (test.skip) {
            this.results.skipped++;
            this.results.total++;
            this.logger?.info(`⏭️ Skipped: ${test.name}`);
            return;
        }

        const startTime = performance.now();
        let result = null;

        try {
            // Set up timeout
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => reject(new Error(`Test timeout: ${test.timeout}ms`)), test.timeout);
            });

            // Run test
            const testPromise = this.runTestWithAssertions(test);
            result = await Promise.race([testPromise, timeoutPromise]);

            this.results.passed++;
            const duration = Math.round(performance.now() - startTime);
            this.logger?.info(`✅ Passed: ${test.name} (${duration}ms)`);

        } catch (error) {
            this.results.failed++;
            this.results.errors.push({
                test: test.name,
                suite: test.suite,
                error: error.message,
                stack: error.stack,
                duration: Math.round(performance.now() - startTime)
            });
            
            this.logger?.error(`❌ Failed: ${test.name}`, error.message);
        }

        this.results.total++;
    }

    /**
     * Run test with assertion context
     */
    async runTestWithAssertions(test) {
        const assertions = new Assertions();
        
        // If test expects assertions, pass them as parameter
        if (test.callback.length > 0) {
            return await test.callback(assertions);
        } else {
            // Set global assertions
            window.expect = assertions.expect.bind(assertions);
            window.assert = assertions;
            
            try {
                return await test.callback();
            } finally {
                // Clean up global assertions
                delete window.expect;
                delete window.assert;
            }
        }
    }

    /**
     * Run hooks
     */
    async runHooks(hooks) {
        for (const hook of hooks) {
            try {
                await hook();
            } catch (error) {
                this.logger?.error('Hook error:', error);
                throw error;
            }
        }
    }

    /**
     * Mock a function or object
     */
    mock(target, method, implementation) {
        const original = target[method];
        const mockId = this.generateId();
        
        target[method] = implementation || (() => {});
        
        const mock = {
            restore: () => {
                target[method] = original;
                this.mockRegistry.delete(mockId);
            },
            calls: [],
            callCount: 0,
            lastCall: null
        };

        // Wrap implementation to track calls
        if (implementation) {
            const wrappedImpl = target[method];
            target[method] = (...args) => {
                mock.calls.push(args);
                mock.callCount++;
                mock.lastCall = args;
                return wrappedImpl(...args);
            };
        }

        this.mockRegistry.set(mockId, mock);
        return mock;
    }

    /**
     * Restore all mocks
     */
    restoreAllMocks() {
        this.mockRegistry.forEach(mock => mock.restore());
        this.mockRegistry.clear();
    }

    /**
     * Create a spy function
     */
    spy(implementation = () => {}) {
        const calls = [];
        const spyFn = (...args) => {
            calls.push(args);
            return implementation(...args);
        };
        
        spyFn.calls = calls;
        spyFn.callCount = () => calls.length;
        spyFn.lastCall = () => calls[calls.length - 1];
        spyFn.reset = () => calls.length = 0;
        
        return spyFn;
    }

    /**
     * Reset test results
     */
    resetResults() {
        this.results = {
            total: 0,
            passed: 0,
            failed: 0,
            skipped: 0,
            errors: []
        };
    }

    /**
     * Display test results
     */
    displayResults() {
        const duration = Math.round(this.endTime - this.startTime);
        const passRate = Math.round((this.results.passed / this.results.total) * 100);

        console.log('\n🧪 Test Results');
        console.log('================');
        console.log(`Total: ${this.results.total}`);
        console.log(`✅ Passed: ${this.results.passed}`);
        console.log(`❌ Failed: ${this.results.failed}`);
        console.log(`⏭️ Skipped: ${this.results.skipped}`);
        console.log(`📊 Pass Rate: ${passRate}%`);
        console.log(`⏱️ Duration: ${duration}ms`);

        if (this.results.errors.length > 0) {
            console.log('\n❌ Failed Tests:');
            this.results.errors.forEach((error, index) => {
                console.log(`${index + 1}. ${error.test} (${error.suite})`);
                console.log(`   ${error.error}`);
            });
        }

        // Log to logger if available
        this.logger?.info('Test execution completed', {
            results: this.results,
            duration,
            passRate
        });
    }

    /**
     * Generate test report
     */
    generateReport() {
        return {
            timestamp: new Date().toISOString(),
            duration: this.endTime - this.startTime,
            results: this.results,
            suites: Array.from(this.suites.keys()),
            environment: {
                userAgent: navigator.userAgent,
                url: window.location.href,
                config: window.SERVER_CONFIG || {}
            }
        };
    }

    /**
     * Generate unique ID
     */
    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }
}

class Assertions {
    expect(actual) {
        return {
            toBe: (expected) => {
                if (actual !== expected) {
                    throw new Error(`Expected ${actual} to be ${expected}`);
                }
            },
            
            toEqual: (expected) => {
                if (!this.deepEqual(actual, expected)) {
                    throw new Error(`Expected ${JSON.stringify(actual)} to equal ${JSON.stringify(expected)}`);
                }
            },
            
            toBeTruthy: () => {
                if (!actual) {
                    throw new Error(`Expected ${actual} to be truthy`);
                }
            },
            
            toBeFalsy: () => {
                if (actual) {
                    throw new Error(`Expected ${actual} to be falsy`);
                }
            },
            
            toBeNull: () => {
                if (actual !== null) {
                    throw new Error(`Expected ${actual} to be null`);
                }
            },
            
            toBeUndefined: () => {
                if (actual !== undefined) {
                    throw new Error(`Expected ${actual} to be undefined`);
                }
            },
            
            toContain: (expected) => {
                if (Array.isArray(actual) || typeof actual === 'string') {
                    if (!actual.includes(expected)) {
                        throw new Error(`Expected ${actual} to contain ${expected}`);
                    }
                } else {
                    throw new Error('toContain can only be used with arrays or strings');
                }
            },
            
            toHaveLength: (expected) => {
                if (actual.length !== expected) {
                    throw new Error(`Expected length ${expected}, got ${actual.length}`);
                }
            },
            
            toThrow: () => {
                if (typeof actual !== 'function') {
                    throw new Error('toThrow expects a function');
                }
                
                try {
                    actual();
                    throw new Error('Expected function to throw');
                } catch (error) {
                    // Function threw as expected
                    if (error.message === 'Expected function to throw') {
                        throw error;
                    }
                }
            },
            
            toHaveBeenCalled: () => {
                if (!actual.calls) {
                    throw new Error('toHaveBeenCalled can only be used with spies or mocks');
                }
                if (actual.calls.length === 0) {
                    throw new Error('Expected spy to have been called');
                }
            },
            
            toHaveBeenCalledWith: (...args) => {
                if (!actual.calls) {
                    throw new Error('toHaveBeenCalledWith can only be used with spies or mocks');
                }
                
                const found = actual.calls.some(call => 
                    call.length === args.length && 
                    call.every((arg, index) => this.deepEqual(arg, args[index]))
                );
                
                if (!found) {
                    throw new Error(`Expected spy to have been called with ${JSON.stringify(args)}`);
                }
            }
        };
    }

    /**
     * Assert function
     */
    assert(condition, message = 'Assertion failed') {
        if (!condition) {
            throw new Error(message);
        }
    }

    /**
     * Deep equality check
     */
    deepEqual(a, b) {
        if (a === b) return true;
        
        if (a == null || b == null) return a === b;
        
        if (typeof a !== typeof b) return false;
        
        if (typeof a === 'object') {
            const keysA = Object.keys(a);
            const keysB = Object.keys(b);
            
            if (keysA.length !== keysB.length) return false;
            
            return keysA.every(key => 
                keysB.includes(key) && this.deepEqual(a[key], b[key])
            );
        }
        
        return false;
    }
}

// Create global test framework instance
window.testFramework = new TestFramework();

// Global test functions
window.describe = (name, callback) => window.testFramework.describe(name, callback);
window.test = (name, callback, options) => window.testFramework.test(name, callback, options);
window.it = (name, callback, options) => window.testFramework.it(name, callback, options);
window.beforeEach = (callback) => window.testFramework.beforeEach(callback);
window.afterEach = (callback) => window.testFramework.afterEach(callback);
window.beforeAll = (callback) => window.testFramework.beforeAll(callback);
window.afterAll = (callback) => window.testFramework.afterAll(callback);

// Mock and spy utilities
window.mock = (target, method, impl) => window.testFramework.mock(target, method, impl);
window.spy = (impl) => window.testFramework.spy(impl);

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TestFramework, Assertions };
}

console.log('✅ Test Framework initialized');