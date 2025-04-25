"""Handlers for geometry-related map actions"""
import folium
from folium.plugins import HeatMap
from services.action_handlers.base_handler import create_handler, ActionDict, BoundsList

@create_handler
def handle_add_line(action: ActionDict, m: folium.Map) -> BoundsList:
    """
    Handle the add_line action
    
    Args:
        action: The action dictionary with parameters
        m: The folium map object
        
    Returns:
        List of bounds to include in the overall map fitting
    """
    bounds = []
    
    locations = action.get("locations", [])
    
    if locations and isinstance(locations, list) and len(locations) >= 2:
        folium.PolyLine(
            locations=locations,
            popup=action.get("popup", ""),
            color=action.get("color", "blue"),
            weight=action.get("weight", 3),
            opacity=action.get("opacity", 1.0),
            dash_array=action.get("dash_array", None)
        ).add_to(m)
        
        # Add all line points to bounds
        bounds.extend(locations)
        
    return bounds

@create_handler
def handle_add_polygon(action: ActionDict, m: folium.Map) -> BoundsList:
    """
    Handle the add_polygon action
    
    Args:
        action: The action dictionary with parameters
        m: The folium map object
        
    Returns:
        List of bounds to include in the overall map fitting
    """
    bounds = []
    
    locations = action.get("locations", [])
    
    if locations and isinstance(locations, list) and len(locations) >= 3:
        folium.Polygon(
            locations=locations,
            popup=action.get("popup", ""),
            color=action.get("color", "blue"),
            weight=action.get("weight", 2),
            fill_color=action.get("fill_color", "blue"),
            fill_opacity=action.get("fill_opacity", 0.2)
        ).add_to(m)
        
        # Add all polygon points to bounds
        bounds.extend(locations)
            
    return bounds

@create_handler
def handle_add_heatmap(action: ActionDict, m: folium.Map) -> BoundsList:
    """
    Handle the add_heatmap action
    
    Args:
        action: The action dictionary with parameters
        m: The folium map object
        
    Returns:
        List of bounds to include in the overall map fitting
    """
    bounds = []
    
    data_points = action.get("data_points", [])
    if data_points and isinstance(data_points, list):
        HeatMap(
            data=data_points,
            radius=action.get("radius", 15),
            blur=action.get("blur", 10),
            gradient=action.get("gradient", None)
        ).add_to(m)
        
        # Add all heatmap points to bounds
        for point in data_points:
            if len(point) >= 2:  # Make sure we have at least lat, lon
                bounds.append([point[0], point[1]])
                
    return bounds 
