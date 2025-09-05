/**
 * MQTT Settings Manager
 * Handles MQTT broker configuration UI and testing
 */

class MQTTSettingsManager {
    constructor(apiClient) {
        this.api = apiClient;
        this.currentConfig = null;
        this.testInProgress = false;
        this.statusUpdateInterval = null;
        
        // Bind methods
        this.initialize = this.initialize.bind(this);
        this.loadSettings = this.loadSettings.bind(this);
        this.saveSettings = this.saveSettings.bind(this);
        this.testConnection = this.testConnection.bind(this);
    }
    
    /**
     * Initialize MQTT settings UI
     */
    async initialize() {
        await this.loadSettings();
        this.setupEventListeners();
        this.startStatusMonitoring();
    }
    
    /**
     * Load current MQTT settings
     */
    async loadSettings() {
        try {
            const response = await this.api.get('/api/mqtt/config');
            if (response.success) {
                this.currentConfig = response.config;
                this.updateUI(response.config);
                this.updateStatus(response.status);
            }
        } catch (error) {
            console.error('Failed to load MQTT settings:', error);
            Utils.showToast('Failed to load MQTT settings', 'error');
        }
    }
    
    /**
     * Update UI with configuration values
     */
    updateUI(config) {
        // Connection settings
        Utils.safeSetValue('mqtt-host', config.host);
        Utils.safeSetValue('mqtt-port', config.port);
        Utils.safeSetChecked('mqtt-use-ssl', config.use_ssl);
        Utils.safeSetValue('mqtt-ssl-port', config.ssl_port);
        Utils.safeSetValue('mqtt-ssl-cert', config.ssl_cert_path);
        Utils.safeSetValue('mqtt-ssl-key', config.ssl_key_path);
        Utils.safeSetValue('mqtt-ssl-ca', config.ssl_ca_path);
        Utils.safeSetChecked('mqtt-ssl-insecure', config.ssl_insecure);
        
        // Authentication
        Utils.safeSetChecked('mqtt-use-auth', config.use_auth);
        Utils.safeSetValue('mqtt-username', config.username);
        Utils.safeSetValue('mqtt-password', config.password);
        Utils.safeSetValue('mqtt-client-id', config.client_id);
        
        // Connection parameters
        Utils.safeSetValue('mqtt-keepalive', config.keepalive);
        Utils.safeSetValue('mqtt-timeout', config.connect_timeout);
        Utils.safeSetChecked('mqtt-reconnect', config.reconnect_on_failure);
        Utils.safeSetValue('mqtt-reconnect-delay', config.reconnect_delay);
        Utils.safeSetValue('mqtt-max-reconnect', config.max_reconnect_attempts);
        
        // Topics
        Utils.safeSetValue('mqtt-topic-prefix', config.topic_prefix);
        Utils.safeSetValue('mqtt-qos', config.qos_level);
        
        // Custom topics
        if (config.custom_topics) {
            this.updateCustomTopics(config.custom_topics);
        }
        
        // Advanced settings
        Utils.safeSetChecked('mqtt-clean-session', config.clean_session);
        Utils.safeSetValue('mqtt-protocol', config.protocol_version);
        Utils.safeSetValue('mqtt-transport', config.transport);
        
        // Last Will and Testament
        Utils.safeSetChecked('mqtt-use-lwt', config.use_lwt);
        Utils.safeSetValue('mqtt-lwt-topic', config.lwt_topic);
        Utils.safeSetValue('mqtt-lwt-message', config.lwt_message);
        Utils.safeSetValue('mqtt-lwt-qos', config.lwt_qos);
        Utils.safeSetChecked('mqtt-lwt-retain', config.lwt_retain);
        
        // Message handling
        Utils.safeSetChecked('mqtt-retain', config.retain_messages);
        Utils.safeSetValue('mqtt-buffer-size', config.message_buffer_size);
        
        // Debugging
        Utils.safeSetChecked('mqtt-enable-logging', config.enable_logging);
        Utils.safeSetValue('mqtt-log-level', config.log_level);
        Utils.safeSetChecked('mqtt-enable-metrics', config.enable_metrics);
        
        // Update UI state based on toggles
        this.toggleSSLSettings(config.use_ssl);
        this.toggleAuthSettings(config.use_auth);
        this.toggleLWTSettings(config.use_lwt);
    }
    
    /**
     * Update custom topics display
     */
    updateCustomTopics(topics) {
        const container = document.getElementById('mqtt-custom-topics');
        if (!container) return;
        
        let html = '';
        for (const [name, pattern] of Object.entries(topics)) {
            html += `
                <div class="custom-topic-row">
                    <input type="text" class="topic-name" value="${name}" placeholder="Topic name">
                    <input type="text" class="topic-pattern" value="${pattern}" placeholder="Topic pattern">
                    <button class="btn-remove" onclick="mqttSettings.removeTopic('${name}')">×</button>
                </div>
            `;
        }
        container.innerHTML = html;
    }
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // SSL toggle
        Utils.safeElementOperation('mqtt-use-ssl', el => {
            el.addEventListener('change', (e) => this.toggleSSLSettings(e.target.checked));
        });
        
        // Auth toggle
        Utils.safeElementOperation('mqtt-use-auth', el => {
            el.addEventListener('change', (e) => this.toggleAuthSettings(e.target.checked));
        });
        
        // LWT toggle
        Utils.safeElementOperation('mqtt-use-lwt', el => {
            el.addEventListener('change', (e) => this.toggleLWTSettings(e.target.checked));
        });
        
        // Save button
        Utils.safeElementOperation('mqtt-save-btn', el => {
            el.addEventListener('click', () => this.saveSettings());
        });
        
        // Test button
        Utils.safeElementOperation('mqtt-test-btn', el => {
            el.addEventListener('click', () => this.testConnection());
        });
        
        // Add topic button
        Utils.safeElementOperation('mqtt-add-topic-btn', el => {
            el.addEventListener('click', () => this.addCustomTopic());
        });
        
        // Port sync when SSL is toggled
        Utils.safeElementOperation('mqtt-use-ssl', el => {
            el.addEventListener('change', (e) => {
                if (e.target.checked) {
                    const portField = document.getElementById('mqtt-port');
                    const sslPortField = document.getElementById('mqtt-ssl-port');
                    if (portField && portField.value === '1883' && sslPortField) {
                        portField.value = sslPortField.value || '8883';
                    }
                } else {
                    const portField = document.getElementById('mqtt-port');
                    if (portField && portField.value === '8883') {
                        portField.value = '1883';
                    }
                }
            });
        });
    }
    
    /**
     * Toggle SSL settings visibility
     */
    toggleSSLSettings(enabled) {
        const sslSettings = document.getElementById('mqtt-ssl-settings');
        if (sslSettings) {
            sslSettings.style.display = enabled ? 'block' : 'none';
        }
    }
    
    /**
     * Toggle authentication settings visibility
     */
    toggleAuthSettings(enabled) {
        const authSettings = document.getElementById('mqtt-auth-settings');
        if (authSettings) {
            authSettings.style.display = enabled ? 'block' : 'none';
        }
    }
    
    /**
     * Toggle LWT settings visibility
     */
    toggleLWTSettings(enabled) {
        const lwtSettings = document.getElementById('mqtt-lwt-settings');
        if (lwtSettings) {
            lwtSettings.style.display = enabled ? 'block' : 'none';
        }
    }
    
    /**
     * Gather configuration from UI
     */
    gatherConfig() {
        const config = {
            // Connection settings
            host: document.getElementById('mqtt-host')?.value || 'localhost',
            port: parseInt(document.getElementById('mqtt-port')?.value || '1883'),
            use_ssl: document.getElementById('mqtt-use-ssl')?.checked || false,
            ssl_port: parseInt(document.getElementById('mqtt-ssl-port')?.value || '8883'),
            ssl_cert_path: document.getElementById('mqtt-ssl-cert')?.value || '',
            ssl_key_path: document.getElementById('mqtt-ssl-key')?.value || '',
            ssl_ca_path: document.getElementById('mqtt-ssl-ca')?.value || '',
            ssl_insecure: document.getElementById('mqtt-ssl-insecure')?.checked || false,
            
            // Authentication
            use_auth: document.getElementById('mqtt-use-auth')?.checked || false,
            username: document.getElementById('mqtt-username')?.value || '',
            password: document.getElementById('mqtt-password')?.value || '',
            client_id: document.getElementById('mqtt-client-id')?.value || 'erik-image-manager',
            
            // Connection parameters
            keepalive: parseInt(document.getElementById('mqtt-keepalive')?.value || '60'),
            connect_timeout: parseInt(document.getElementById('mqtt-timeout')?.value || '30'),
            reconnect_on_failure: document.getElementById('mqtt-reconnect')?.checked !== false,
            reconnect_delay: parseInt(document.getElementById('mqtt-reconnect-delay')?.value || '5'),
            max_reconnect_attempts: parseInt(document.getElementById('mqtt-max-reconnect')?.value || '10'),
            
            // Topics
            topic_prefix: document.getElementById('mqtt-topic-prefix')?.value || 'frigate',
            qos_level: parseInt(document.getElementById('mqtt-qos')?.value || '1'),
            custom_topics: this.gatherCustomTopics(),
            
            // Advanced settings
            clean_session: document.getElementById('mqtt-clean-session')?.checked !== false,
            protocol_version: parseInt(document.getElementById('mqtt-protocol')?.value || '4'),
            transport: document.getElementById('mqtt-transport')?.value || 'tcp',
            
            // Last Will and Testament
            use_lwt: document.getElementById('mqtt-use-lwt')?.checked || false,
            lwt_topic: document.getElementById('mqtt-lwt-topic')?.value || 'erik/status',
            lwt_message: document.getElementById('mqtt-lwt-message')?.value || 'offline',
            lwt_qos: parseInt(document.getElementById('mqtt-lwt-qos')?.value || '1'),
            lwt_retain: document.getElementById('mqtt-lwt-retain')?.checked !== false,
            
            // Message handling
            retain_messages: document.getElementById('mqtt-retain')?.checked || false,
            message_buffer_size: parseInt(document.getElementById('mqtt-buffer-size')?.value || '1000'),
            
            // Debugging
            enable_logging: document.getElementById('mqtt-enable-logging')?.checked !== false,
            log_level: document.getElementById('mqtt-log-level')?.value || 'INFO',
            enable_metrics: document.getElementById('mqtt-enable-metrics')?.checked || false,
            metrics_interval: 60
        };
        
        return config;
    }
    
    /**
     * Gather custom topics from UI
     */
    gatherCustomTopics() {
        const topics = {};
        const rows = document.querySelectorAll('#mqtt-custom-topics .custom-topic-row');
        
        rows.forEach(row => {
            const name = row.querySelector('.topic-name')?.value;
            const pattern = row.querySelector('.topic-pattern')?.value;
            if (name && pattern) {
                topics[name] = pattern;
            }
        });
        
        // Include default topics if not already present
        if (!topics.events) topics.events = '{prefix}/events';
        if (!topics.detection) topics.detection = '{prefix}/+/person';
        if (!topics.tracking) topics.tracking = 'erik/tracking/+';
        
        return topics;
    }
    
    /**
     * Save MQTT settings
     */
    async saveSettings() {
        try {
            const config = this.gatherConfig();
            
            // Show saving indicator
            const saveBtn = document.getElementById('mqtt-save-btn');
            const originalText = saveBtn.textContent;
            saveBtn.textContent = 'Saving...';
            saveBtn.disabled = true;
            
            const response = await this.api.post('/api/mqtt/config', config);
            
            if (response.success) {
                Utils.showToast('MQTT settings saved successfully', 'success');
                this.currentConfig = config;
                
                // Restart connection with new settings
                if (document.getElementById('mqtt-auto-restart')?.checked) {
                    Utils.showToast('Restarting MQTT connection...', 'info');
                }
            } else {
                const errors = response.errors || [response.error];
                Utils.showToast(`Failed to save: ${errors.join(', ')}`, 'error');
            }
            
            saveBtn.textContent = originalText;
            saveBtn.disabled = false;
            
        } catch (error) {
            console.error('Failed to save MQTT settings:', error);
            Utils.showToast('Failed to save MQTT settings', 'error');
            
            const saveBtn = document.getElementById('mqtt-save-btn');
            saveBtn.textContent = 'Save Settings';
            saveBtn.disabled = false;
        }
    }
    
    /**
     * Test MQTT connection
     */
    async testConnection() {
        if (this.testInProgress) {
            Utils.showToast('Test already in progress', 'warning');
            return;
        }
        
        try {
            this.testInProgress = true;
            const config = this.gatherConfig();
            
            // Update UI
            const testBtn = document.getElementById('mqtt-test-btn');
            const originalText = testBtn.textContent;
            testBtn.textContent = 'Testing...';
            testBtn.disabled = true;
            
            const statusDiv = document.getElementById('mqtt-test-status');
            if (statusDiv) {
                statusDiv.innerHTML = '<div class="test-progress">🔄 Connecting to broker...</div>';
                statusDiv.style.display = 'block';
            }
            
            // Start test
            const response = await this.api.post('/api/mqtt/test', config);
            
            if (response.success) {
                // Poll for test result
                this.pollTestStatus(response.test_id, testBtn, originalText, statusDiv);
            } else {
                throw new Error(response.error || 'Test failed to start');
            }
            
        } catch (error) {
            console.error('Failed to test connection:', error);
            Utils.showToast(`Connection test failed: ${error.message}`, 'error');
            
            const testBtn = document.getElementById('mqtt-test-btn');
            testBtn.textContent = 'Test Connection';
            testBtn.disabled = false;
            this.testInProgress = false;
            
            const statusDiv = document.getElementById('mqtt-test-status');
            if (statusDiv) {
                statusDiv.innerHTML = `<div class="test-error">❌ ${error.message}</div>`;
            }
        }
    }
    
    /**
     * Poll for test connection status
     */
    async pollTestStatus(testId, button, originalText, statusDiv) {
        let attempts = 0;
        const maxAttempts = 20; // 10 seconds max
        
        const checkStatus = async () => {
            try {
                const response = await this.api.get('/api/mqtt/test/status');
                
                if (!response.result.connecting) {
                    // Test complete
                    button.textContent = originalText;
                    button.disabled = false;
                    this.testInProgress = false;
                    
                    if (response.result.connected) {
                        Utils.showToast('Connection successful!', 'success');
                        if (statusDiv) {
                            const details = response.result.details;
                            statusDiv.innerHTML = `
                                <div class="test-success">
                                    ✅ Connected successfully!
                                    <div class="test-details">
                                        <div>Broker: ${details.broker}</div>
                                        <div>Port: ${details.port}</div>
                                        <div>Client ID: ${details.client_id}</div>
                                        <div>Protocol: ${details.protocol}</div>
                                    </div>
                                </div>
                            `;
                        }
                    } else {
                        const error = response.result.error || 'Connection failed';
                        Utils.showToast(error, 'error');
                        if (statusDiv) {
                            statusDiv.innerHTML = `<div class="test-error">❌ ${error}</div>`;
                        }
                    }
                    return;
                }
                
                // Still connecting
                attempts++;
                if (attempts >= maxAttempts) {
                    throw new Error('Connection test timeout');
                }
                
                // Continue polling
                setTimeout(checkStatus, 500);
                
            } catch (error) {
                console.error('Error polling test status:', error);
                button.textContent = originalText;
                button.disabled = false;
                this.testInProgress = false;
                
                if (statusDiv) {
                    statusDiv.innerHTML = `<div class="test-error">❌ ${error.message}</div>`;
                }
            }
        };
        
        // Start polling
        checkStatus();
    }
    
    /**
     * Add custom topic
     */
    addCustomTopic() {
        const container = document.getElementById('mqtt-custom-topics');
        if (!container) return;
        
        const row = document.createElement('div');
        row.className = 'custom-topic-row';
        row.innerHTML = `
            <input type="text" class="topic-name" placeholder="Topic name">
            <input type="text" class="topic-pattern" placeholder="Topic pattern (use {prefix} for prefix)">
            <button class="btn-remove" onclick="this.parentElement.remove()">×</button>
        `;
        container.appendChild(row);
    }
    
    /**
     * Remove custom topic
     */
    removeTopic(name) {
        const rows = document.querySelectorAll('#mqtt-custom-topics .custom-topic-row');
        rows.forEach(row => {
            const nameInput = row.querySelector('.topic-name');
            if (nameInput && nameInput.value === name) {
                row.remove();
            }
        });
    }
    
    /**
     * Update connection status display
     */
    updateStatus(status) {
        // Update status indicators
        Utils.safeElementOperation('mqtt-status-connected', el => {
            el.textContent = status.connected ? '🟢 Connected' : '🔴 Disconnected';
            el.className = status.connected ? 'status-connected' : 'status-disconnected';
        });
        
        Utils.safeElementOperation('mqtt-status-broker', el => {
            el.textContent = status.broker || 'Not configured';
        });
        
        Utils.safeElementOperation('mqtt-status-messages-rx', el => {
            el.textContent = status.messages_received || '0';
        });
        
        Utils.safeElementOperation('mqtt-status-messages-tx', el => {
            el.textContent = status.messages_sent || '0';
        });
        
        if (status.last_error) {
            Utils.safeElementOperation('mqtt-status-error', el => {
                el.textContent = status.last_error;
                el.style.display = 'block';
            });
        }
    }
    
    /**
     * Start monitoring connection status
     */
    startStatusMonitoring() {
        // Update status every 5 seconds
        this.statusUpdateInterval = setInterval(async () => {
            try {
                const response = await this.api.get('/api/mqtt/status');
                if (response.success) {
                    this.updateStatus(response.status);
                }
            } catch (error) {
                console.error('Failed to update MQTT status:', error);
            }
        }, 5000);
    }
    
    /**
     * Stop status monitoring
     */
    stopStatusMonitoring() {
        if (this.statusUpdateInterval) {
            clearInterval(this.statusUpdateInterval);
            this.statusUpdateInterval = null;
        }
    }
    
    /**
     * Load and display MQTT logs
     */
    async loadLogs() {
        try {
            const response = await this.api.get('/api/mqtt/logs');
            if (response.success) {
                this.displayLogs(response.logs);
            }
        } catch (error) {
            console.error('Failed to load MQTT logs:', error);
        }
    }
    
    /**
     * Display MQTT logs
     */
    displayLogs(logs) {
        const container = document.getElementById('mqtt-logs');
        if (!container) return;
        
        let html = '';
        logs.forEach(log => {
            const levelClass = log.level.toLowerCase();
            html += `
                <div class="log-entry log-${levelClass}">
                    <span class="log-time">${new Date(log.timestamp).toLocaleTimeString()}</span>
                    <span class="log-level">[${log.level}]</span>
                    <span class="log-message">${log.message}</span>
                </div>
            `;
        });
        
        container.innerHTML = html || '<div class="no-logs">No logs available</div>';
    }
}

// Create global instance
window.mqttSettings = new MQTTSettingsManager(window.api);