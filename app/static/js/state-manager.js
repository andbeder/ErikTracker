/**
 * State Management System for Erik Image Manager
 * Provides centralized state management, reactive updates, and persistence
 */

class StateManager {
    constructor() {
        this.state = new Map();
        this.subscribers = new Map();
        this.middleware = [];
        this.history = [];
        this.maxHistory = 50;
        this.logger = window.logger;
        this.persistentKeys = new Set();
        this.storagePrefix = 'erik_state_';
        
        this.initializeState();
    }

    /**
     * Initialize state management
     */
    initializeState() {
        // Load persistent state from localStorage
        this.loadPersistentState();
        
        // Initialize default state
        this.setState('app', {
            initialized: false,
            loading: false,
            currentTab: 'map',
            currentConfigTab: 'photos',
            error: null,
            lastUpdated: Date.now()
        });

        this.setState('config', {
            loaded: false,
            data: null,
            error: null
        });

        this.setState('images', {
            list: [],
            count: 0,
            uploading: false,
            selected: [],
            lastRefresh: null
        });

        this.setState('colmap', {
            models: [],
            processing: false,
            selectedModel: null,
            progress: {},
            videos: []
        });

        this.setState('yardMap', {
            active: null,
            generating: false,
            progress: 0,
            bounds: null
        });

        this.setState('cameras', {
            list: [],
            snapshots: {},
            config: {},
            live: false
        });

        this.setState('matches', {
            list: [],
            count: 0,
            autoRefresh: true,
            lastUpdate: null
        });

        this.setState('erik', {
            position: null,
            status: 'unknown',
            lastSeen: null,
            tracking: false
        });

        this.logger?.info('State Manager initialized with default state');
    }

    /**
     * Set state value
     */
    setState(key, value, options = {}) {
        const { merge = true, persist = false, silent = false } = options;
        
        try {
            const oldValue = this.state.get(key);
            const newValue = merge && oldValue && typeof oldValue === 'object' && typeof value === 'object' 
                ? { ...oldValue, ...value }
                : value;

            // Run middleware
            let processedValue = newValue;
            for (const middleware of this.middleware) {
                processedValue = middleware(key, processedValue, oldValue);
            }

            // Update state
            this.state.set(key, processedValue);

            // Add to history
            this.addToHistory(key, processedValue, oldValue);

            // Persist if requested
            if (persist) {
                this.persistentKeys.add(key);
                this.savePersistentState(key, processedValue);
            }

            // Notify subscribers
            if (!silent) {
                this.notifySubscribers(key, processedValue, oldValue);
            }

            this.logger?.debug(`State updated: ${key}`, { newValue: processedValue, oldValue });
            
            return processedValue;
        } catch (error) {
            this.logger?.error('setState error:', { key, value, error: error.message });
            throw error;
        }
    }

    /**
     * Get state value
     */
    getState(key, defaultValue = null) {
        return this.state.get(key) ?? defaultValue;
    }

    /**
     * Get nested state value
     */
    getNestedState(key, path, defaultValue = null) {
        const state = this.getState(key);
        if (!state || typeof state !== 'object') return defaultValue;

        const keys = path.split('.');
        let value = state;
        
        for (const k of keys) {
            if (value && typeof value === 'object' && k in value) {
                value = value[k];
            } else {
                return defaultValue;
            }
        }
        
        return value;
    }

    /**
     * Update nested state value
     */
    setNestedState(key, path, value, options = {}) {
        const currentState = this.getState(key, {});
        const keys = path.split('.');
        const lastKey = keys.pop();
        
        let target = { ...currentState };
        let current = target;
        
        // Navigate to the parent object
        for (const k of keys) {
            if (!(k in current) || typeof current[k] !== 'object') {
                current[k] = {};
            } else {
                current[k] = { ...current[k] };
            }
            current = current[k];
        }
        
        // Set the value
        current[lastKey] = value;
        
        return this.setState(key, target, options);
    }

    /**
     * Subscribe to state changes
     */
    subscribe(key, callback, options = {}) {
        const { immediate = false, filter = null } = options;
        
        if (!this.subscribers.has(key)) {
            this.subscribers.set(key, new Set());
        }
        
        const subscription = {
            callback,
            filter,
            id: this.generateId(),
            created: Date.now()
        };
        
        this.subscribers.get(key).add(subscription);
        
        // Call immediately with current state if requested
        if (immediate) {
            const currentState = this.getState(key);
            if (currentState !== null) {
                callback(currentState, null, key);
            }
        }
        
        // Return unsubscribe function
        return () => {
            const subs = this.subscribers.get(key);
            if (subs) {
                subs.delete(subscription);
                if (subs.size === 0) {
                    this.subscribers.delete(key);
                }
            }
        };
    }

    /**
     * Subscribe to multiple state keys
     */
    subscribeMultiple(keys, callback, options = {}) {
        const unsubscribers = keys.map(key => 
            this.subscribe(key, (value, oldValue, stateKey) => {
                const currentState = {};
                keys.forEach(k => {
                    currentState[k] = this.getState(k);
                });
                callback(currentState, stateKey);
            }, options)
        );
        
        return () => unsubscribers.forEach(unsub => unsub());
    }

    /**
     * Notify subscribers of state changes
     */
    notifySubscribers(key, newValue, oldValue) {
        const subscribers = this.subscribers.get(key);
        if (!subscribers) return;

        subscribers.forEach(subscription => {
            try {
                // Apply filter if present
                if (subscription.filter && !subscription.filter(newValue, oldValue)) {
                    return;
                }
                
                subscription.callback(newValue, oldValue, key);
            } catch (error) {
                this.logger?.error('Subscription callback error:', {
                    key,
                    subscriptionId: subscription.id,
                    error: error.message
                });
            }
        });
    }

    /**
     * Add middleware for state transformations
     */
    addMiddleware(middleware) {
        this.middleware.push(middleware);
        return () => {
            const index = this.middleware.indexOf(middleware);
            if (index !== -1) {
                this.middleware.splice(index, 1);
            }
        };
    }

    /**
     * Add to state history
     */
    addToHistory(key, newValue, oldValue) {
        this.history.push({
            key,
            newValue,
            oldValue,
            timestamp: Date.now(),
            id: this.generateId()
        });

        // Limit history size
        if (this.history.length > this.maxHistory) {
            this.history.shift();
        }
    }

    /**
     * Get state history
     */
    getHistory(key = null, limit = 10) {
        let history = this.history;
        
        if (key) {
            history = history.filter(entry => entry.key === key);
        }
        
        return history.slice(-limit);
    }

    /**
     * Save persistent state to localStorage
     */
    savePersistentState(key, value) {
        try {
            const storageKey = this.storagePrefix + key;
            localStorage.setItem(storageKey, JSON.stringify({
                value,
                timestamp: Date.now()
            }));
        } catch (error) {
            this.logger?.warn('Failed to persist state:', { key, error: error.message });
        }
    }

    /**
     * Load persistent state from localStorage
     */
    loadPersistentState() {
        try {
            Object.keys(localStorage).forEach(storageKey => {
                if (storageKey.startsWith(this.storagePrefix)) {
                    const key = storageKey.replace(this.storagePrefix, '');
                    const stored = JSON.parse(localStorage.getItem(storageKey));
                    
                    if (stored && stored.value !== undefined) {
                        this.state.set(key, stored.value);
                        this.persistentKeys.add(key);
                        this.logger?.debug(`Loaded persistent state: ${key}`, stored.value);
                    }
                }
            });
        } catch (error) {
            this.logger?.warn('Failed to load persistent state:', error.message);
        }
    }

    /**
     * Clear persistent state
     */
    clearPersistentState(key = null) {
        if (key) {
            const storageKey = this.storagePrefix + key;
            localStorage.removeItem(storageKey);
            this.persistentKeys.delete(key);
        } else {
            Object.keys(localStorage).forEach(storageKey => {
                if (storageKey.startsWith(this.storagePrefix)) {
                    localStorage.removeItem(storageKey);
                }
            });
            this.persistentKeys.clear();
        }
    }

    /**
     * Create computed state (reactive derived values)
     */
    createComputed(name, dependencies, computeFn, options = {}) {
        const { immediate = true } = options;
        
        const compute = () => {
            try {
                const values = dependencies.map(key => this.getState(key));
                const result = computeFn(...values);
                this.setState(name, result, { silent: true });
                return result;
            } catch (error) {
                this.logger?.error(`Computed state error: ${name}`, error.message);
                return null;
            }
        };

        // Subscribe to all dependencies
        const unsubscribers = dependencies.map(key => 
            this.subscribe(key, compute)
        );

        // Compute initial value
        if (immediate) {
            compute();
        }

        // Return cleanup function
        return () => unsubscribers.forEach(unsub => unsub());
    }

    /**
     * Batch state updates
     */
    batch(updateFn) {
        const oldNotify = this.notifySubscribers;
        const batchedNotifications = new Map();

        // Temporarily disable notifications
        this.notifySubscribers = (key, newValue, oldValue) => {
            batchedNotifications.set(key, { newValue, oldValue });
        };

        try {
            updateFn();
            
            // Send all batched notifications
            batchedNotifications.forEach((notification, key) => {
                oldNotify.call(this, key, notification.newValue, notification.oldValue);
            });
        } finally {
            // Restore notifications
            this.notifySubscribers = oldNotify;
        }
    }

    /**
     * Reset state to defaults
     */
    reset(key = null) {
        if (key) {
            this.state.delete(key);
            this.clearPersistentState(key);
            this.notifySubscribers(key, null, this.state.get(key));
        } else {
            this.state.clear();
            this.clearPersistentState();
            this.subscribers.clear();
            this.history = [];
            this.initializeState();
        }
        
        this.logger?.info(key ? `State reset: ${key}` : 'All state reset');
    }

    /**
     * Get state snapshot
     */
    getSnapshot() {
        const snapshot = {};
        this.state.forEach((value, key) => {
            snapshot[key] = value;
        });
        return {
            state: snapshot,
            timestamp: Date.now(),
            persistent: Array.from(this.persistentKeys)
        };
    }

    /**
     * Load state from snapshot
     */
    loadSnapshot(snapshot) {
        try {
            this.batch(() => {
                Object.entries(snapshot.state).forEach(([key, value]) => {
                    this.setState(key, value, { 
                        persist: snapshot.persistent?.includes(key) 
                    });
                });
            });
            
            this.logger?.info('State loaded from snapshot', {
                keys: Object.keys(snapshot.state).length,
                timestamp: snapshot.timestamp
            });
        } catch (error) {
            this.logger?.error('Failed to load state snapshot:', error.message);
        }
    }

    /**
     * Generate unique ID
     */
    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }

    /**
     * Get debug information
     */
    getDebugInfo() {
        return {
            stateKeys: Array.from(this.state.keys()),
            subscriberCounts: Object.fromEntries(
                Array.from(this.subscribers.entries()).map(([key, subs]) => [key, subs.size])
            ),
            persistentKeys: Array.from(this.persistentKeys),
            historyLength: this.history.length,
            middlewareCount: this.middleware.length
        };
    }
}

// Reactive state binding utilities
class StateBinding {
    constructor(stateManager) {
        this.state = stateManager;
        this.bindings = new Map();
    }

    /**
     * Bind state to DOM element property
     */
    bindProperty(element, property, stateKey, transform = (x) => x) {
        const subscription = this.state.subscribe(stateKey, (value) => {
            const transformedValue = transform(value);
            if (element && property in element) {
                element[property] = transformedValue;
            }
        }, { immediate: true });

        this.bindings.set(`${element}_${property}`, subscription);
        return subscription;
    }

    /**
     * Bind state to DOM element text content
     */
    bindText(element, stateKey, transform = (x) => String(x)) {
        return this.bindProperty(element, 'textContent', stateKey, transform);
    }

    /**
     * Bind state to DOM element innerHTML
     */
    bindHTML(element, stateKey, transform = (x) => String(x)) {
        return this.bindProperty(element, 'innerHTML', stateKey, transform);
    }

    /**
     * Bind state to element visibility
     */
    bindVisibility(element, stateKey, transform = Boolean) {
        return this.bindProperty(element, 'style.display', stateKey, 
            value => transform(value) ? 'block' : 'none'
        );
    }

    /**
     * Bind state to CSS class
     */
    bindClass(element, className, stateKey, transform = Boolean) {
        return this.state.subscribe(stateKey, (value) => {
            const shouldHaveClass = transform(value);
            if (element) {
                element.classList.toggle(className, shouldHaveClass);
            }
        }, { immediate: true });
    }

    /**
     * Two-way binding for form inputs
     */
    bindInput(element, stateKey, options = {}) {
        const { immediate = true, debounce = 300 } = options;
        
        // State to element
        const stateToElement = this.state.subscribe(stateKey, (value) => {
            if (element && element.value !== value) {
                element.value = value || '';
            }
        }, { immediate });

        // Element to state (debounced)
        let timeoutId;
        const elementToState = (event) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => {
                this.state.setState(stateKey, element.value);
            }, debounce);
        };

        if (element) {
            element.addEventListener('input', elementToState);
        }

        // Return cleanup function
        return () => {
            stateToElement();
            if (element) {
                element.removeEventListener('input', elementToState);
            }
            clearTimeout(timeoutId);
        };
    }

    /**
     * Clear all bindings
     */
    clearBindings() {
        this.bindings.forEach(unsubscribe => unsubscribe());
        this.bindings.clear();
    }
}

// Initialize global state management
window.stateManager = new StateManager();
window.stateBinding = new StateBinding(window.stateManager);

// Convenience globals
window.state = window.stateManager;

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { StateManager, StateBinding };
}

console.log('✅ State Management System initialized');