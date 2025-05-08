"""Handlers for map view-related actions"""
import folium
import streamlit as st
from action_handlers.base_handler import create_handler, ActionDict, BoundsList

@create_handler
def handle_fit_bounds(action: ActionDict, m: folium.Map) -> BoundsList:
    """
    Handle the fit_bounds action
    
    Args:
        action: The action dictionary with parameters
        m: The folium map object
        
    Returns:
        List of bounds to include in the overall map fitting, or None if explicit bounds applied
        
    Note:
        This function has special return behavior:
        - Returns None when explicit bounds are provided and applied directly to the map
          (indicating to the caller that no further bounds calculations are needed)
        - Returns an empty list when no bounds are provided 
          (allowing the caller to continue with other bounds calculations)
        
        The bounds parameter should be a list of two [lat, lon] pairs representing 
        the southwest and northeast corners of the bounding box.
    """
    # If explicit fit_bounds is specified, honor it directly
    bounds = action.get("bounds")
    if bounds and isinstance(bounds, list) and len(bounds) == 2:
        m.fit_bounds(bounds)  # Apply explicit bounds
        return None  # Indicating we've already fit the bounds
        
    # If no bounds provided, return empty list
    return [] 
