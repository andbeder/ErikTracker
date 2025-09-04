/**
 * WebSocket Communication Manager for Erik Image Manager
 * Handles real-time communication, auto-reconnection, and message routing
 */

class WebSocketManager {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.isReconnecting = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.heartbeatInterval = null;
        this.heartbeatTimeout = null;
        this.messageQueue = [];
        this.subscriptions = new Map();
        this.logger = window.logger;
        this.stateManager = window.stateManager;
        
        this.initializeWebSocket();
    }

    /**
     * Initialize WebSocket connection
     */
    initializeWebSocket() {
        try {
            // WebSocket server not implemented yet - skip connection
            this.logger?.info('WebSocket server not available - using polling mode');
            this.isConnected = false;
            this.connectionStatus = 'disabled';
            
            // Update state manager if available
            if (this.stateManager) {
                this.stateManager.setState('websocket', {
                    connected: false,
                    status: 'disabled',
                    message: 'WebSocket server not implemented - using polling mode'
                });
            }
            
            return; // Skip actual WebSocket connection
            
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            const wsUrl = `${protocol}//${host}/ws`;

            this.socket = new WebSocket(wsUrl);
            this.setupEventHandlers();
            
            this.logger?.info('WebSocket initializing:', wsUrl);
            
        } catch (error) {
            this.logger?.error('WebSocket initialization failed:', error);
            this.handleConnectionError();
        }
    }

    /**
     * Setup WebSocket event handlers
     */
    setupEventHandlers() {
        this.socket.onopen = (event) => {
            this.handleOpen(event);
        };

        this.socket.onclose = (event) => {
            this.handleClose(event);
        };

        this.socket.onerror = (event) => {
            this.handleError(event);
        };

        this.socket.onmessage = (event) => {
            this.handleMessage(event);
        };
    }

    /**
     * Handle WebSocket open event
     */
    handleOpen(event) {
        this.logger?.info('WebSocket connected');
        
        this.isConnected = true;
        this.isReconnecting = false;
        this.reconnectAttempts = 0;
        
        // Update connection state
        if (this.stateManager) {
            this.stateManager.setState('websocket', {
                connected: true,
                reconnecting: false,
                lastConnected: new Date().toISOString()
            });
        }

        // Start heartbeat
        this.startHeartbeat();

        // Send queued messages
        this.sendQueuedMessages();

        // Send initial subscription requests
        this.sendSubscriptions();

        // Trigger connected event
        this.emit('connected', { timestamp: Date.now() });
    }

    /**
     * Handle WebSocket close event
     */
    handleClose(event) {
        this.logger?.warn('WebSocket disconnected:', { code: event.code, reason: event.reason });
        
        this.isConnected = false;
        this.stopHeartbeat();

        // Update connection state
        if (this.stateManager) {
            this.stateManager.setState('websocket', {
                connected: false,
                reconnecting: false,
                lastDisconnected: new Date().toISOString(),
                closeCode: event.code,
                closeReason: event.reason
            });
        }

        // Trigger disconnected event
        this.emit('disconnected', { 
            code: event.code, 
            reason: event.reason,
            timestamp: Date.now()
        });

        // Attempt to reconnect if not intentional
        if (event.code !== 1000 && event.code !== 1001) {
            this.attemptReconnect();
        }
    }

    /**
     * Handle WebSocket error event
     */
    handleError(event) {
        this.logger?.error('WebSocket error:', event);
        
        // Trigger error event
        this.emit('error', { event, timestamp: Date.now() });
        
        this.handleConnectionError();
    }

    /**
     * Handle WebSocket message
     */
    handleMessage(event) {
        try {
            const message = JSON.parse(event.data);
            this.logger?.debug('WebSocket message received:', message);

            // Handle system messages
            if (message.type === 'pong') {
                this.handlePong();
                return;
            }

            if (message.type === 'error') {
                this.logger?.error('WebSocket server error:', message.data);
                return;
            }

            // Route message to subscribers
            this.routeMessage(message);

            // Update state if applicable
            this.updateStateFromMessage(message);

        } catch (error) {
            this.logger?.error('WebSocket message parse error:', error);
        }
    }

    /**
     * Route message to subscribers
     */
    routeMessage(message) {
        const { type, data } = message;
        
        // Send to specific type subscribers
        if (this.subscriptions.has(type)) {
            this.subscriptions.get(type).forEach(callback => {
                try {
                    callback(data, message);
                } catch (error) {
                    this.logger?.error('WebSocket subscriber error:', { type, error });
                }
            });
        }

        // Send to global subscribers
        if (this.subscriptions.has('*')) {
            this.subscriptions.get('*').forEach(callback => {
                try {
                    callback(data, message);
                } catch (error) {
                    this.logger?.error('WebSocket global subscriber error:', error);
                }
            });
        }
    }

    /**
     * Update application state from WebSocket message
     */
    updateStateFromMessage(message) {
        const { type, data } = message;

        switch (type) {
            case 'erik_position':
                if (this.stateManager) {
                    this.stateManager.setState('erik', {
                        position: data.position,
                        status: data.status,
                        lastSeen: data.timestamp,
                        tracking: true
                    });
                }
                break;

            case 'camera_status':
                if (this.stateManager) {
                    this.stateManager.setNestedState('cameras', `status.${data.camera}`, data.status);
                }
                break;

            case 'colmap_progress':
                if (this.stateManager) {
                    this.stateManager.setNestedState('colmap', 'progress', data);
                }
                break;

            case 'yard_map_progress':
                if (this.stateManager) {
                    this.stateManager.setState('yardMap', {
                        generating: data.status === 'processing',
                        progress: data.progress || 0
                    });
                }
                break;

            case 'match_detected':
                if (this.stateManager) {
                    const matches = this.stateManager.getState('matches', { list: [] });
                    matches.list.unshift(data);
                    matches.count = matches.list.length;
                    matches.lastUpdate = Date.now();
                    this.stateManager.setState('matches', matches);
                }
                break;

            case 'system_status':
                if (this.stateManager) {
                    this.stateManager.setState('system', data);
                }
                break;
        }
    }

    /**
     * Send message to server
     */
    send(message) {
        if (this.connectionStatus === 'disabled') {
            this.logger?.debug('WebSocket send skipped (disabled):', message);
            return false; // Gracefully fail when disabled
        }
        
        if (this.isConnected && this.socket && this.socket.readyState === WebSocket.OPEN) {
            try {
                const messageString = typeof message === 'string' ? message : JSON.stringify(message);
                this.socket.send(messageString);
                this.logger?.debug('WebSocket message sent:', message);
                return true;
            } catch (error) {
                this.logger?.error('WebSocket send error:', error);
                this.queueMessage(message);
                return false;
            }
        } else {
            this.queueMessage(message);
            return false;
        }
    }

    /**
     * Queue message for sending when connected
     */
    queueMessage(message) {
        this.messageQueue.push({
            message,
            timestamp: Date.now()
        });

        // Limit queue size
        if (this.messageQueue.length > 100) {
            this.messageQueue.shift();
        }
    }

    /**
     * Send queued messages
     */
    sendQueuedMessages() {
        while (this.messageQueue.length > 0) {
            const { message } = this.messageQueue.shift();
            if (!this.send(message)) {
                // If send fails, put it back at front of queue
                this.messageQueue.unshift({ message, timestamp: Date.now() });
                break;
            }
        }
    }

    /**
     * Subscribe to message type
     */
    subscribe(type, callback) {
        if (!this.subscriptions.has(type)) {
            this.subscriptions.set(type, new Set());
        }
        
        this.subscriptions.get(type).add(callback);
        
        // Send subscription request to server if connected
        if (this.isConnected && type !== '*') {
            this.send({
                type: 'subscribe',
                data: { messageType: type }
            });
        }

        // Return unsubscribe function
        return () => {
            if (this.subscriptions.has(type)) {
                this.subscriptions.get(type).delete(callback);
                
                if (this.subscriptions.get(type).size === 0) {
                    this.subscriptions.delete(type);
                    
                    // Send unsubscribe request to server
                    if (this.isConnected && type !== '*') {
                        this.send({
                            type: 'unsubscribe',
                            data: { messageType: type }
                        });
                    }
                }
            }
        };
    }

    /**
     * Subscribe to multiple message types
     */
    subscribeMultiple(types, callback) {
        const unsubscribers = types.map(type => this.subscribe(type, callback));
        return () => unsubscribers.forEach(unsub => unsub());
    }

    /**
     * Emit event to subscribers (internal use)
     */
    emit(eventType, data) {
        const message = {
            type: `ws_${eventType}`,
            data,
            timestamp: Date.now()
        };
        
        this.routeMessage(message);
    }

    /**
     * Send subscription requests for current subscriptions
     */
    sendSubscriptions() {
        for (const type of this.subscriptions.keys()) {
            if (type !== '*') {
                this.send({
                    type: 'subscribe',
                    data: { messageType: type }
                });
            }
        }
    }

    /**
     * Start heartbeat mechanism
     */
    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            if (this.isConnected) {
                this.send({ type: 'ping', timestamp: Date.now() });
                
                // Set timeout for pong response
                this.heartbeatTimeout = setTimeout(() => {
                    this.logger?.warn('WebSocket heartbeat timeout');
                    this.handleConnectionError();
                }, 5000);
            }
        }, 30000); // Send ping every 30 seconds
    }

    /**
     * Stop heartbeat mechanism
     */
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
        
        if (this.heartbeatTimeout) {
            clearTimeout(this.heartbeatTimeout);
            this.heartbeatTimeout = null;
        }
    }

    /**
     * Handle pong response
     */
    handlePong() {
        if (this.heartbeatTimeout) {
            clearTimeout(this.heartbeatTimeout);
            this.heartbeatTimeout = null;
        }
        
        this.logger?.debug('WebSocket heartbeat pong received');
    }

    /**
     * Handle connection error
     */
    handleConnectionError() {
        if (this.isConnected) {
            this.isConnected = false;
            this.stopHeartbeat();
            
            if (this.stateManager) {
                this.stateManager.setState('websocket', {
                    connected: false,
                    error: true,
                    lastError: new Date().toISOString()
                });
            }
        }
        
        this.attemptReconnect();
    }

    /**
     * Attempt to reconnect
     */
    attemptReconnect() {
        if (this.isReconnecting || this.reconnectAttempts >= this.maxReconnectAttempts) {
            return;
        }

        this.isReconnecting = true;
        this.reconnectAttempts++;

        if (this.stateManager) {
            this.stateManager.setState('websocket', {
                connected: false,
                reconnecting: true,
                reconnectAttempts: this.reconnectAttempts
            });
        }

        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            this.maxReconnectDelay
        );

        this.logger?.info(`WebSocket reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

        setTimeout(() => {
            this.initializeWebSocket();
        }, delay);
    }

    /**
     * Manually disconnect WebSocket
     */
    disconnect() {
        if (this.socket) {
            this.socket.close(1000, 'Manual disconnect');
        }
    }

    /**
     * Manually reconnect WebSocket
     */
    reconnect() {
        this.disconnect();
        this.reconnectAttempts = 0;
        this.isReconnecting = false;
        
        setTimeout(() => {
            this.initializeWebSocket();
        }, 1000);
    }

    /**
     * Get connection status
     */
    getStatus() {
        return {
            connected: this.isConnected,
            reconnecting: this.isReconnecting,
            reconnectAttempts: this.reconnectAttempts,
            queuedMessages: this.messageQueue.length,
            subscriptions: Array.from(this.subscriptions.keys()),
            readyState: this.socket ? this.socket.readyState : null,
            url: this.socket ? this.socket.url : null
        };
    }

    /**
     * Clear message queue
     */
    clearQueue() {
        this.messageQueue = [];
        this.logger?.info('WebSocket message queue cleared');
    }

    /**
     * Get debug information
     */
    getDebugInfo() {
        return {
            status: this.getStatus(),
            messageQueue: this.messageQueue,
            subscriptions: Object.fromEntries(
                Array.from(this.subscriptions.entries()).map(([type, callbacks]) => 
                    [type, callbacks.size]
                )
            ),
            heartbeatActive: !!this.heartbeatInterval
        };
    }
}

// Convenience methods for common subscriptions
WebSocketManager.prototype.subscribeToErikPosition = function(callback) {
    return this.subscribe('erik_position', callback);
};

WebSocketManager.prototype.subscribeToMatches = function(callback) {
    return this.subscribe('match_detected', callback);
};

WebSocketManager.prototype.subscribeToColmapProgress = function(callback) {
    return this.subscribe('colmap_progress', callback);
};

WebSocketManager.prototype.subscribeToYardMapProgress = function(callback) {
    return this.subscribe('yard_map_progress', callback);
};

WebSocketManager.prototype.subscribeToCameraStatus = function(callback) {
    return this.subscribe('camera_status', callback);
};

WebSocketManager.prototype.subscribeToSystemStatus = function(callback) {
    return this.subscribe('system_status', callback);
};

// Initialize global WebSocket manager
window.webSocketManager = new WebSocketManager();

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { WebSocketManager };
}

console.log('✅ WebSocket Manager initialized');