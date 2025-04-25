"""Handlers for marker-related map actions"""
import folium
from services.action_handlers.base_handler import create_handler, ActionDict, BoundsList

@create_handler
def handle_add_marker(action: ActionDict, m: folium.Map) -> BoundsList:
    """
    Handle the add_marker action
    
    Args:
        action: The action dictionary with parameters
        m: The folium map object
        
    Returns:
        List of bounds to include in the overall map fitting
    """
    bounds = []
    
    lat = action.get("lat")
    lon = action.get("lon")
    
    if lat is not None and lon is not None:
        folium.Marker(
            location=[lat, lon],
            popup=action.get("popup", ""),
            icon=folium.Icon(color=action.get("color", "blue"))
        ).add_to(m)
        
        # Add marker bounds to the list
        bounds.append([lat, lon])
        
    return bounds

@create_handler
def handle_add_circle(action: ActionDict, m: folium.Map) -> BoundsList:
    """
    Handle the add_circle action
    
    Args:
        action: The action dictionary with parameters
        m: The folium map object
        
    Returns:
        List of bounds to include in the overall map fitting
    """
    bounds = []
    
    lat = action.get("lat")
    lon = action.get("lon")
    radius = action.get("radius", 1000)
    
    if lat is not None and lon is not None:
        folium.Circle(
            location=[lat, lon],
            radius=radius,
            popup=action.get("popup", ""),
            color=action.get("color", "blue"),
            fill=True,
            fill_opacity=0.2
        ).add_to(m)
        
        # Add circle center to bounds
        bounds.append([lat, lon])
        
    return bounds 
