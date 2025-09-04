#!/usr/bin/env python3
"""
Erik Image Manager - Main Entry Point
This is the new entry point for the refactored application
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Main entry point for the application"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Erik Image Manager')
    parser.add_argument('--dev', action='store_true', help='Run in development mode')
    parser.add_argument('--port', type=int, default=9000, help='Port to run on')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--use-legacy', action='store_true', help='Use legacy image_manager.py directly')
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.dev else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Disable noisy urllib3 debug logs for camera polling
    if args.dev:
        urllib3_logger = logging.getLogger('urllib3.connectionpool')
        urllib3_logger.setLevel(logging.INFO)
    logger = logging.getLogger(__name__)
    
    if args.use_legacy:  # Phase 3: Legacy mode (fallback)
        # Run the original image_manager app
        logger.info("Running in legacy compatibility mode")
        
        # Import legacy module only when explicitly requested
        import image_manager
        
        # Get the Flask app from image_manager
        app = image_manager.app
        
        # Start MQTT listener if it exists
        if hasattr(image_manager, 'mqtt_listener'):
            logger.info("Starting MQTT listener")
            # The mqtt_listener is already started in image_manager.py
        
        if args.dev:
            logger.info(f"🚀 Starting Erik Image Manager in DEVELOPMENT mode")
            logger.info(f"   URL: http://localhost:{args.port}")
            logger.info(f"   Upload folder: {image_manager.UPLOAD_FOLDER}")
            logger.info(f"   Mesh folder: {image_manager.MESH_FOLDER}")
            logger.info(f"   Frigate config: {image_manager.FRIGATE_CONFIG_PATH}")
            app.run(host=args.host, port=args.port, debug=True)
        else:
            logger.info(f"Starting Erik Image Manager on port {args.port}")
            logger.info(f"Upload folder: {image_manager.UPLOAD_FOLDER}")
            app.run(host=args.host, port=args.port, debug=False)
    else:
        # Use the new modular architecture (default in Phase 3)
        logger.info("Running with new modular architecture")
        from app import create_app
        
        # Determine config name
        config_name = 'development' if args.dev else 'production'
        
        # Create the application
        app = create_app(config_name)
        
        if args.dev:
            logger.info(f"🚀 Starting Erik Image Manager in DEVELOPMENT mode")
            logger.info(f"   URL: http://localhost:{args.port}")
            logger.info(f"   Upload folder: {app.config['UPLOAD_FOLDER']}")
            logger.info(f"   Mesh folder: {app.config['MESH_FOLDER']}")
            logger.info(f"   Frigate config: {app.config['FRIGATE_CONFIG_PATH']}")
            app.run(host=args.host, port=args.port, debug=True)
        else:
            logger.info(f"Starting Erik Image Manager on port {args.port}")
            logger.info(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
            app.run(host=args.host, port=args.port, debug=False)

if __name__ == '__main__':
    main()