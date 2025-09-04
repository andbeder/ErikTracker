"""
Legacy routes compatibility layer
DEPRECATED: This module is no longer used after Phase 3 completion
All routes have been migrated to modular blueprints
"""

import logging

logger = logging.getLogger(__name__)

def register_legacy_routes(app):
    """Legacy route registration - no longer used
    
    This function is kept for backward compatibility but does nothing.
    All routes are now handled by modular blueprints registered in app/__init__.py
    """
    logger.info("Legacy routes registration called but not needed - using modular blueprints")
    pass