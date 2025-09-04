"""
Configuration helper utilities
Common configuration operations and settings management
"""

import os
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

def load_json_config(config_path, default_config=None):
    """Load JSON configuration file with defaults
    
    Args:
        config_path: Path to JSON configuration file
        default_config: Default configuration dictionary
        
    Returns:
        Configuration dictionary
    """
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        else:
            logger.warning(f"Configuration file not found: {config_path}")
            return default_config or {}
            
    except Exception as e:
        logger.error(f"Error loading JSON config from {config_path}: {e}")
        return default_config or {}

def save_json_config(config_path, config_data, backup=True):
    """Save JSON configuration file with optional backup
    
    Args:
        config_path: Path to save configuration
        config_data: Configuration dictionary to save
        backup: Whether to create backup of existing file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create backup if requested and file exists
        if backup and os.path.exists(config_path):
            from .file_helpers import backup_file
            backup_file(config_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Save configuration
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2, default=str)
        
        logger.info(f"Saved configuration to {config_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving JSON config to {config_path}: {e}")
        return False

def load_yaml_config(config_path, default_config=None):
    """Load YAML configuration file with defaults
    
    Args:
        config_path: Path to YAML configuration file
        default_config: Default configuration dictionary
        
    Returns:
        Configuration dictionary
    """
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded YAML configuration from {config_path}")
                return config
        else:
            logger.warning(f"YAML configuration file not found: {config_path}")
            return default_config or {}
            
    except Exception as e:
        logger.error(f"Error loading YAML config from {config_path}: {e}")
        return default_config or {}

def save_yaml_config(config_path, config_data, backup=True):
    """Save YAML configuration file with optional backup
    
    Args:
        config_path: Path to save configuration
        config_data: Configuration dictionary to save
        backup: Whether to create backup of existing file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create backup if requested and file exists
        if backup and os.path.exists(config_path):
            from .file_helpers import backup_file
            backup_file(config_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Save configuration
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False, indent=2)
        
        logger.info(f"Saved YAML configuration to {config_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving YAML config to {config_path}: {e}")
        return False

def get_env_config(env_vars, defaults=None):
    """Get configuration from environment variables
    
    Args:
        env_vars: Dictionary mapping config keys to env var names
        defaults: Dictionary of default values
        
    Returns:
        Configuration dictionary
    """
    config = {}
    defaults = defaults or {}
    
    for config_key, env_var in env_vars.items():
        value = os.environ.get(env_var, defaults.get(config_key))
        
        # Try to convert to appropriate type
        if value is not None:
            # Convert boolean strings
            if isinstance(value, str):
                if value.lower() in ('true', 'false'):
                    value = value.lower() == 'true'
                elif value.isdigit():
                    value = int(value)
                elif value.replace('.', '').isdigit():
                    value = float(value)
            
            config[config_key] = value
    
    return config

def merge_configs(*configs):
    """Merge multiple configuration dictionaries
    
    Args:
        *configs: Configuration dictionaries to merge
        
    Returns:
        Merged configuration dictionary
    """
    merged = {}
    
    for config in configs:
        if isinstance(config, dict):
            merged.update(config)
    
    return merged

def validate_config(config, required_keys, optional_keys=None):
    """Validate configuration dictionary
    
    Args:
        config: Configuration dictionary to validate
        required_keys: List of required configuration keys
        optional_keys: List of optional configuration keys
        
    Returns:
        Tuple of (is_valid, missing_keys, extra_keys)
    """
    if not isinstance(config, dict):
        return False, required_keys, []
    
    config_keys = set(config.keys())
    required_set = set(required_keys)
    optional_set = set(optional_keys or [])
    
    missing_keys = required_set - config_keys
    valid_keys = required_set | optional_set
    extra_keys = config_keys - valid_keys
    
    is_valid = len(missing_keys) == 0
    
    return is_valid, list(missing_keys), list(extra_keys)

def get_config_value(config, key_path, default=None):
    """Get nested configuration value using dot notation
    
    Args:
        config: Configuration dictionary
        key_path: Dot-separated key path (e.g., 'database.host')
        default: Default value if key not found
        
    Returns:
        Configuration value or default
    """
    try:
        value = config
        for key in key_path.split('.'):
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default

def set_config_value(config, key_path, value):
    """Set nested configuration value using dot notation
    
    Args:
        config: Configuration dictionary to modify
        key_path: Dot-separated key path (e.g., 'database.host')
        value: Value to set
        
    Returns:
        Modified configuration dictionary
    """
    keys = key_path.split('.')
    current = config
    
    # Navigate to parent of target key
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    
    # Set the final value
    current[keys[-1]] = value
    
    return config

def get_system_info():
    """Get system information for configuration context
    
    Returns:
        Dictionary with system information
    """
    import platform
    import psutil
    
    try:
        return {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'disk_usage': psutil.disk_usage('/').percent,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'timestamp': datetime.now().isoformat()
        }

def create_default_config(config_path, default_values):
    """Create default configuration file if it doesn't exist
    
    Args:
        config_path: Path to configuration file
        default_values: Default configuration values
        
    Returns:
        True if file was created, False if already exists
    """
    if os.path.exists(config_path):
        return False
    
    try:
        if config_path.endswith('.yaml') or config_path.endswith('.yml'):
            return save_yaml_config(config_path, default_values, backup=False)
        else:
            return save_json_config(config_path, default_values, backup=False)
    except Exception as e:
        logger.error(f"Error creating default config: {e}")
        return False