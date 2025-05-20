"""
Map processor module that orchestrates map-related operations.

This is the main entry point for map processing operations, handling the 
coordination between different map actions and their implementations.
"""
import streamlit as st
import logging

# Setup module logger
logger = logging.getLogger(__name__)

# Import core map functionality
from services.map_core import initialize_map, fit_map_to_bounds

# Import utilities
from utils.streamlit_utils import add_status_message

# Import action handlers
from action_handlers import (
    handle_add_marker, 
    handle_add_circle,
    handle_highlight_region,
    handle_add_line, 
    handle_add_polygon, 
    handle_add_heatmap,
    handle_show_local_dataset,
    handle_fit_bounds,
    handle_analyze_wind_risk,
    handle_show_weather,
    handle_unsafe_temperature
)

import hashlib
import json

def get_actions_hash(actions):
    """
    Generate a hash of map actions for caching purposes
    
    Args:
        actions: List of action dictionaries
        
    Returns:
        str: A hash string representing the actions
    """
    if not actions:
        return "empty_actions"
    
    try:
        # Convert to stable JSON string and hash
        actions_json = json.dumps(actions, sort_keys=True)
        return hashlib.md5(actions_json.encode()).hexdigest()
    except Exception as e:
        logger.error(f"Error hashing actions: {e}")
        # Return a timestamp-based fallback if we can't hash properly
        import time
        return f"fallback_{int(time.time())}"

def process_actions_for_bounds(actions):
    """
    Process map actions to collect bounds (no caching)
    
    IMPORTANT: Removed caching to prevent widget warning - widgets should never be in cached functions
    
    Args:
        actions: List of action dictionaries
        
    Returns:
        list: List of bounds to fit the map to
    """
    # Create handler registry
    action_handlers = get_action_handlers()
    
    # Track all bounds
    all_bounds = []
    
    # Process each action and collect bounds only
    for action in actions:
        if not isinstance(action, dict):
            continue
            
        action_type = action.get("action_type")
        logger.info(f"Processing action type: {action_type}")
        if action_type in action_handlers:
            try:
                # We need to create a temporary map for each handler
                # since we're only collecting bounds at this stage
                temp_map = initialize_map()
                bounds = action_handlers[action_type](action, temp_map)
                if bounds:
                    all_bounds.extend(bounds)
            except Exception as e:
                add_status_message(f"Error processing {action_type} action: {str(e)}", "error")
    
    return all_bounds

def process_map_actions(actions, m):
    """
    Process map actions from AI responses and apply them to the map
    
    This simplified version:
    1. Directly applies actions to the map
    2. Avoids any caching to prevent Streamlit widget warnings
    3. Supports all types of UI components in action handlers
    
    Args:
        actions: List of action dictionaries
        m: The folium map object to modify
        
    Returns:
        folium.Map: The modified map
    """
    if not actions or not isinstance(actions, list):
        return m
    
    # Get action handlers
    action_handlers = get_action_handlers()
    
    # Track all bounds
    all_bounds = []
    
    # Process each action and apply it to the map
    for action in actions:
        if not isinstance(action, dict):
            continue
            
        action_type = action.get("action_type")
        if action_type in action_handlers:
            try:
                # Process the action and collect bounds
                bounds = action_handlers[action_type](action, m)
                if bounds:
                    all_bounds.extend(bounds)
            except Exception as e:
                add_status_message(f"Error applying {action_type} action to map: {str(e)}", "error")
    
    # Fit the map to the collected bounds
    if all_bounds:
        fit_map_to_bounds(m, all_bounds)
    
    return m

def get_action_handlers():
    """
    Return dictionary of action handlers
    
    This function implements several design patterns:
    1. Factory Method Pattern - Creates a dictionary of handler functions
    2. Strategy Pattern - Each handler encapsulates a specific map operation strategy
    3. Dependency Inversion - High-level process_map_actions depends on abstractions (handlers)
       not concrete implementations
    4. Open/Closed Principle - New action types can be added without modifying existing code
       by simply adding new handler functions to this registry
    
    Returns:
        Dictionary mapping action_type strings to their handler functions
    """
    return {
        "add_marker": handle_add_marker,
        "highlight_region": handle_highlight_region,
        "fit_bounds": handle_fit_bounds,
        "show_weather": handle_show_weather,
        "analyze_wind_risk": handle_analyze_wind_risk,
        "show_local_dataset": handle_show_local_dataset,
        "add_circle": handle_add_circle,
        "add_heatmap": handle_add_heatmap,
        "add_line": handle_add_line,
        "add_polygon": handle_add_polygon,
        "unsafe_temperature": handle_unsafe_temperature
    }
