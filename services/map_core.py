import folium
import pandas as pd
import json
import streamlit as st

def initialize_map():
    """Initialize a base Folium map centered on the United States"""
    m = folium.Map(location=[39.8283, -98.5795], zoom_start=4, tiles="OpenStreetMap")
    return m

def serialize_geojson(gdf):
    """Convert GeoDataFrame to properly serialized GeoJSON"""
    # First convert any timestamp columns to strings
    for col in gdf.columns:
        if pd.api.types.is_datetime64_any_dtype(gdf[col]):
            gdf[col] = gdf[col].astype(str)
    
    # Use to_json with default serializer for dates
    return json.loads(gdf.to_json())

def fit_map_to_bounds(m, bounds):
    """
    Fit the map to show all features based on provided coordinate bounds
    
    Args:
        m: The folium map object to adjust
        bounds: List of [lat, lon] coordinate pairs representing points or corners
               of areas that should be visible on the map
               
    Note:
        - If bounds is empty, the function will make no changes to the map view
        - For a single point, centers the map on that point with zoom level 10
        - For multiple points, calculates a bounding box that includes all points
        - The padding parameter (30,30) adds margin around the bounds for better visibility
    """
    if not bounds:
        return
        
    if len(bounds) == 1:
        # If only one point, center on it with a reasonable zoom
        m.location = bounds[0]
        m.zoom_start = 10
    else:
        # Calculate the bounds that encompass all points/regions
        try:
            # Use folium's fit_bounds to automatically adjust the view
            m.fit_bounds(bounds, padding=(30, 30))
        except Exception as e:
            st.error(f"Error fitting bounds: {e}") 
