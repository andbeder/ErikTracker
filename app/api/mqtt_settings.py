"""
MQTT Settings Management API
Handles MQTT broker configuration, authentication, and connection testing
"""

import os
import json
import logging
import paho.mqtt.client as mqtt
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import ssl
import time
from threading import Thread, Event

logger = logging.getLogger(__name__)

bp = Blueprint('mqtt_settings', __name__)

# Global MQTT client for testing connections
test_client = None
test_result = {}

class MQTTConfig:
    """MQTT Configuration Manager"""
    
    DEFAULT_CONFIG = {
        # Connection settings
        'host': 'localhost',
        'port': 1883,
        'use_ssl': False,
        'ssl_port': 8883,
        'ssl_cert_path': '',
        'ssl_key_path': '',
        'ssl_ca_path': '',
        'ssl_insecure': False,
        
        # Authentication
        'use_auth': False,
        'username': '',
        'password': '',
        'client_id': 'erik-image-manager',
        
        # Connection parameters
        'keepalive': 60,
        'connect_timeout': 30,
        'reconnect_on_failure': True,
        'reconnect_delay': 5,
        'max_reconnect_attempts': 10,
        
        # Topics
        'topic_prefix': 'frigate',
        'custom_topics': {
            'events': '{prefix}/events',
            'detection': '{prefix}/+/person',
            'tracking': 'erik/tracking/+',
            'pose': 'erik/pose/+',
            'commands': 'erik/commands/+'
        },
        'qos_level': 1,  # 0: At most once, 1: At least once, 2: Exactly once
        
        # Advanced settings
        'clean_session': True,
        'protocol_version': 4,  # 3: MQTTv3.1, 4: MQTTv3.1.1, 5: MQTTv5
        'transport': 'tcp',  # tcp or websockets
        
        # Last Will and Testament
        'use_lwt': False,
        'lwt_topic': 'erik/status',
        'lwt_message': 'offline',
        'lwt_qos': 1,
        'lwt_retain': True,
        
        # Message handling
        'retain_messages': False,
        'message_buffer_size': 1000,
        
        # Status and debugging
        'enable_logging': True,
        'log_level': 'INFO',
        'enable_metrics': False,
        'metrics_interval': 60
    }
    
    def __init__(self, config_path='/home/andrew/nvr/config/mqtt_config.json'):
        self.config_path = config_path
        self.config = self.load_config()
        self.connection_status = {
            'connected': False,
            'last_connection': None,
            'last_error': None,
            'messages_received': 0,
            'messages_sent': 0,
            'uptime': 0
        }
    
    def load_config(self):
        """Load MQTT configuration from file"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    saved_config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    config = self.DEFAULT_CONFIG.copy()
                    config.update(saved_config)
                    return config
            except Exception as e:
                logger.error(f"Error loading MQTT config: {e}")
        return self.DEFAULT_CONFIG.copy()
    
    def save_config(self, config):
        """Save MQTT configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            self.config = config
            return True
        except Exception as e:
            logger.error(f"Error saving MQTT config: {e}")
            return False
    
    def validate_config(self, config):
        """Validate MQTT configuration"""
        errors = []
        
        # Validate host
        if not config.get('host'):
            errors.append('Host is required')
        
        # Validate port
        port = config.get('port')
        if not isinstance(port, int) or port < 1 or port > 65535:
            errors.append('Port must be between 1 and 65535')
        
        # Validate SSL settings
        if config.get('use_ssl'):
            if config.get('ssl_cert_path') and not os.path.exists(config['ssl_cert_path']):
                errors.append(f"SSL certificate not found: {config['ssl_cert_path']}")
            if config.get('ssl_key_path') and not os.path.exists(config['ssl_key_path']):
                errors.append(f"SSL key not found: {config['ssl_key_path']}")
            if config.get('ssl_ca_path') and not os.path.exists(config['ssl_ca_path']):
                errors.append(f"SSL CA certificate not found: {config['ssl_ca_path']}")
        
        # Validate authentication
        if config.get('use_auth'):
            if not config.get('username'):
                errors.append('Username is required when authentication is enabled')
        
        # Validate QoS level
        qos = config.get('qos_level', 1)
        if qos not in [0, 1, 2]:
            errors.append('QoS level must be 0, 1, or 2')
        
        # Validate protocol version
        protocol = config.get('protocol_version', 4)
        if protocol not in [3, 4, 5]:
            errors.append('Protocol version must be 3 (MQTTv3.1), 4 (MQTTv3.1.1), or 5 (MQTTv5)')
        
        return errors

# Create global config manager
mqtt_config_manager = MQTTConfig()

@bp.route('/config', methods=['GET'])
def get_mqtt_config():
    """Get current MQTT configuration"""
    try:
        config = mqtt_config_manager.config
        status = mqtt_config_manager.connection_status
        
        return jsonify({
            'success': True,
            'config': config,
            'status': status
        })
    except Exception as e:
        logger.error(f"Error getting MQTT config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/config', methods=['POST'])
def update_mqtt_config():
    """Update MQTT configuration"""
    try:
        data = request.json
        
        # Validate configuration
        errors = mqtt_config_manager.validate_config(data)
        if errors:
            return jsonify({
                'success': False,
                'errors': errors
            }), 400
        
        # Save configuration
        if mqtt_config_manager.save_config(data):
            logger.info("MQTT configuration updated successfully")
            
            # Restart MQTT listener if it's running
            # This would trigger a reconnection with new settings
            if hasattr(current_app, 'mqtt_listener'):
                logger.info("Restarting MQTT listener with new configuration")
                # Implementation would restart the listener
            
            return jsonify({
                'success': True,
                'message': 'MQTT configuration updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save configuration'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating MQTT config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/test', methods=['POST'])
def test_mqtt_connection():
    """Test MQTT connection with current or provided settings"""
    global test_client, test_result
    
    try:
        # Get test configuration (either from request or current config)
        test_config = request.json if request.json else mqtt_config_manager.config
        
        # Reset test result
        test_result = {
            'connecting': True,
            'connected': False,
            'error': None,
            'details': {}
        }
        
        # Create test client
        client_id = f"{test_config.get('client_id', 'test')}-{int(time.time())}"
        # Get protocol version
        protocol_version = test_config.get('protocol_version', 4)
        if protocol_version == 3:
            protocol = mqtt.MQTTv31
        elif protocol_version == 5:
            protocol = mqtt.MQTTv5
        else:
            protocol = mqtt.MQTTv311  # Default to 3.1.1
        
        test_client = mqtt.Client(
            client_id=client_id,
            clean_session=test_config.get('clean_session', True),
            protocol=protocol
        )
        
        # Setup callbacks
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                test_result['connected'] = True
                test_result['details'] = {
                    'broker': test_config['host'],
                    'port': test_config['port'],
                    'client_id': client_id,
                    'protocol': f"MQTTv{test_config.get('protocol_version', '3.1.1')}"
                }
                logger.info(f"MQTT test connection successful to {test_config['host']}:{test_config['port']}")
            else:
                error_messages = {
                    1: "Incorrect protocol version",
                    2: "Invalid client identifier",
                    3: "Server unavailable",
                    4: "Bad username or password",
                    5: "Not authorized"
                }
                test_result['error'] = error_messages.get(rc, f"Connection failed with code {rc}")
                logger.error(f"MQTT test connection failed: {test_result['error']}")
            test_result['connecting'] = False
            client.disconnect()
        
        def on_disconnect(client, userdata, rc):
            test_result['connecting'] = False
        
        test_client.on_connect = on_connect
        test_client.on_disconnect = on_disconnect
        
        # Configure authentication
        if test_config.get('use_auth'):
            test_client.username_pw_set(
                test_config.get('username'),
                test_config.get('password')
            )
        
        # Configure SSL/TLS
        if test_config.get('use_ssl'):
            context = ssl.create_default_context()
            
            if test_config.get('ssl_ca_path'):
                context.load_verify_locations(test_config['ssl_ca_path'])
            
            if test_config.get('ssl_cert_path') and test_config.get('ssl_key_path'):
                context.load_cert_chain(
                    test_config['ssl_cert_path'],
                    test_config['ssl_key_path']
                )
            
            if test_config.get('ssl_insecure'):
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            
            test_client.tls_set_context(context)
        
        # Configure Last Will and Testament
        if test_config.get('use_lwt'):
            test_client.will_set(
                test_config.get('lwt_topic', 'test/status'),
                test_config.get('lwt_message', 'offline'),
                qos=test_config.get('lwt_qos', 1),
                retain=test_config.get('lwt_retain', True)
            )
        
        # Attempt connection
        port = test_config.get('ssl_port' if test_config.get('use_ssl') else 'port', 1883)
        test_client.connect(
            test_config['host'],
            port,
            test_config.get('keepalive', 60)
        )
        
        # Run in separate thread to avoid blocking
        def run_test():
            test_client.loop_start()
            # Wait for connection result (max 10 seconds)
            timeout = 10
            start_time = time.time()
            while test_result['connecting'] and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            test_client.loop_stop()
            
            if test_result['connecting']:
                test_result['connecting'] = False
                test_result['error'] = f"Connection timeout after {timeout} seconds"
        
        test_thread = Thread(target=run_test)
        test_thread.daemon = True
        test_thread.start()
        
        # Wait a moment for the connection to establish
        time.sleep(0.5)
        
        # Return immediate response (test continues in background)
        return jsonify({
            'success': True,
            'message': 'Connection test initiated',
            'test_id': client_id
        })
        
    except Exception as e:
        logger.error(f"Error testing MQTT connection: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/test/status', methods=['GET'])
def get_test_status():
    """Get status of ongoing connection test"""
    global test_result
    
    return jsonify({
        'success': True,
        'result': test_result
    })

@bp.route('/topics', methods=['GET'])
def get_mqtt_topics():
    """Get configured MQTT topics"""
    try:
        config = mqtt_config_manager.config
        prefix = config.get('topic_prefix', 'frigate')
        
        # Expand topic patterns with prefix
        topics = {}
        for name, pattern in config.get('custom_topics', {}).items():
            topics[name] = pattern.replace('{prefix}', prefix)
        
        return jsonify({
            'success': True,
            'prefix': prefix,
            'topics': topics,
            'qos_level': config.get('qos_level', 1)
        })
        
    except Exception as e:
        logger.error(f"Error getting MQTT topics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/topics', methods=['POST'])
def update_mqtt_topics():
    """Update MQTT topic configuration"""
    try:
        data = request.json
        config = mqtt_config_manager.config
        
        if 'prefix' in data:
            config['topic_prefix'] = data['prefix']
        
        if 'custom_topics' in data:
            config['custom_topics'].update(data['custom_topics'])
        
        if 'qos_level' in data:
            qos = data['qos_level']
            if qos not in [0, 1, 2]:
                return jsonify({
                    'success': False,
                    'error': 'QoS level must be 0, 1, or 2'
                }), 400
            config['qos_level'] = qos
        
        # Save updated configuration
        if mqtt_config_manager.save_config(config):
            return jsonify({
                'success': True,
                'message': 'MQTT topics updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save configuration'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating MQTT topics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/status', methods=['GET'])
def get_mqtt_status():
    """Get current MQTT connection status and metrics"""
    try:
        # This would integrate with the actual MQTT listener
        # For now, return the stored status
        status = mqtt_config_manager.connection_status
        
        # Add current configuration info
        config = mqtt_config_manager.config
        status['broker'] = f"{config['host']}:{config['port']}"
        status['ssl_enabled'] = config.get('use_ssl', False)
        status['auth_enabled'] = config.get('use_auth', False)
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting MQTT status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/logs', methods=['GET'])
def get_mqtt_logs():
    """Get recent MQTT activity logs"""
    try:
        # This would retrieve actual MQTT logs
        # For now, return sample data
        logs = [
            {
                'timestamp': datetime.now().isoformat(),
                'level': 'INFO',
                'message': 'MQTT settings module initialized'
            }
        ]
        
        return jsonify({
            'success': True,
            'logs': logs
        })
        
    except Exception as e:
        logger.error(f"Error getting MQTT logs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500