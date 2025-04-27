"""
Configuration loader for SteamOKAutomaticScript.
Handles loading and accessing YAML configuration files.
"""
import os
import yaml
import logging

# Global configuration storage
_config = None

def load_config(config_path=None):
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to the configuration file. If None, uses default path.
        
    Returns:
        dict: Configuration dictionary
    """
    global _config
    
    # Default config path is in the same directory as this file
    if config_path is None:
        config_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(config_dir, 'config.yaml')
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            _config = yaml.safe_load(f)
        logging.info(f"Configuration loaded from {config_path}")
        return _config
    except Exception as e:
        logging.error(f"Error loading configuration from {config_path}: {str(e)}")
        # Create a default config if loading fails
        quit()


def get_config():
    """
    Get the loaded configuration. Loads default if not already loaded.
    
    Returns:
        dict: Configuration dictionary
    """
    global _config
    if _config is None:
        return load_config()
    return _config