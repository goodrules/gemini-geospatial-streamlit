"""Handlers for data-related map actions"""
import folium
import json
import pandas as pd
import streamlit as st
from services.action_handlers.base_handler import create_handler, ActionDict, BoundsList
from data.geospatial_data import (get_crawford_flood_zones, get_pa_power_lines)

@create_handler
def handle_show_local_dataset(action: ActionDict, m: folium.Map) -> BoundsList:
    """
    Handle the show_local_dataset action
    
    Args:
        action: The action dictionary with parameters
        m: The folium map object
        
    Returns:
        List of bounds to include in the overall map fitting
    """
    bounds = []
    
    dataset_name = action.get("dataset_name", "").lower()
    
    # Determine which dataset to load based on the dataset_name
    gdf = None
    if dataset_name == "flood_zones" or dataset_name == "crawford_flood_zones":
        gdf = get_crawford_flood_zones()
        layer_name = "Crawford County Flood Zones"
        default_color = "#0066cc"  # Blue for flood zones
        fill_color = "#99ccff"    # Light blue fill
    elif dataset_name == "power_lines" or dataset_name == "pa_power_lines":
        gdf = get_pa_power_lines()
        layer_name = "PA Power Lines"
        default_color = "#0066cc"  # Blue for power lines
        fill_color = "#ffff00"    # Yellow fill
    else:
        st.warning(f"Unknown local dataset: {dataset_name}")
        return bounds
            
    if gdf is not None:
        # Convert timestamps to strings to avoid serialization issues
        for col in gdf.columns:
            if pd.api.types.is_datetime64_any_dtype(gdf[col]):
                gdf[col] = gdf[col].astype(str)
        
        # Create a tooltip with dataset information
        first_col = gdf.columns[0] if len(gdf.columns) > 0 else None
        tooltip_fields = action.get("tooltip_fields", [first_col]) if first_col else []
        tooltip_aliases = action.get("tooltip_aliases", tooltip_fields)
        
        # Use tooltip if fields are available
        tooltip = None
        if tooltip_fields:
            tooltip = folium.GeoJsonTooltip(
                fields=tooltip_fields,
                aliases=tooltip_aliases,
                sticky=True
            )
        
        # Define a style function for the GeoJSON layer that applies customization
        # from action parameters while providing default values if not specified
        # This allows callers to customize the appearance of the dataset on the map
        geo_layer = folium.GeoJson(
            json.loads(gdf.to_json()),
            name=layer_name,
            style_function=lambda x: {
                'fillColor': action.get("fill_color", fill_color),
                'color': action.get("color", default_color),
                'weight': action.get("weight", 4),  # Thicker lines by default
                'fillOpacity': action.get("fill_opacity", 0.5)
            },
            tooltip=tooltip
        ).add_to(m)
        
        # Add dataset bounds to bounds list
        dataset_bounds = gdf.total_bounds
        bounds.append([dataset_bounds[1], dataset_bounds[0]])  # SW corner
        bounds.append([dataset_bounds[3], dataset_bounds[2]])  # NE corner
    
    return bounds 
