import folium
import pandas as pd
import json
import streamlit as st

def initialize_map(center=[39.8283, -98.5795], zoom=4, tile="OpenStreetMap"):
    """
    Initialize a base Folium map
    
    We're explicitly NOT caching this function to ensure a fresh map is created 
    on each prompt, preventing any stale data from being displayed.
    
    Args:
        center: Center coordinates [lat, lon] for the map
        zoom: Initial zoom level
        tile: Base tile layer
        
    Returns:
        folium.Map: Initialized map object
    """
    print(f"Creating new base map")
    m = folium.Map(location=center, zoom_start=zoom, tiles=tile)
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
    if not bounds or not isinstance(bounds, list):
        return

    if len(bounds) == 1 and isinstance(bounds[0], list) and len(bounds[0]) == 2:
        # Handle single point/marker case if bounds format is [[lat, lon]]
        # Or handle single bounding box
        if isinstance(bounds[0][0], list): # Check if it's already a bounding box [[miny,minx],[maxy,maxx]]
            final_bounds = bounds[0]
        else: # Assume it's a single point [lat, lon] - treat as small box for fitting
            lat, lon = bounds[0]
            delta = 0.01 # Small offset to create a tiny box
            final_bounds = [[lat - delta, lon - delta], [lat + delta, lon + delta]]
    elif len(bounds) > 0:
        # Robust calculation of overall bounds from a list that might contain
        # bounding boxes [[miny, minx], [maxy, maxx]] or single points [lat, lon].
        all_lats = []
        all_lons = []
        valid_bounds_found = False
        try:
            for item in bounds:
                if isinstance(item, list) and len(item) == 2:
                    # Check if it's a box [[lat, lon], [lat, lon]]
                    if isinstance(item[0], list) and len(item[0]) == 2 and \
                       isinstance(item[1], list) and len(item[1]) == 2:
                        # Extract coordinates from the box corners
                        all_lats.extend([float(item[0][0]), float(item[1][0])])
                        all_lons.extend([float(item[0][1]), float(item[1][1])])
                        valid_bounds_found = True
                    # Check if it's a single point [lat, lon]
                    elif isinstance(item[0], (int, float)) and isinstance(item[1], (int, float)):
                         all_lats.append(float(item[0]))
                         all_lons.append(float(item[1]))
                         valid_bounds_found = True
                    else:
                         st.warning(f"Skipping unexpected item format in bounds list: {item}")
                else:
                     st.warning(f"Skipping unexpected item format in bounds list: {item}")

            if not valid_bounds_found or not all_lats or not all_lons:
                 st.warning(f"Could not extract valid coordinates from bounds list: {bounds}")
                 return # Cannot proceed

            # Calculate final bounds using standard floats
            min_lat = min(all_lats)
            min_lon = min(all_lons)
            max_lat = max(all_lats)
            max_lon = max(all_lons)

            # Ensure min/max logic didn't swap accidentally if only one point/box was processed
            final_bounds = [[min_lat, min_lon], [max_lat, max_lon]]

        except (TypeError, IndexError, ValueError) as e:
             st.warning(f"Could not determine overall bounds from list: {bounds}. Error: {e}")
             return # Cannot proceed if bounds calculation fails
    else:
        st.warning(f"Unexpected bounds format received: {bounds}")
        return # Don't try to fit if format is wrong

    # Fit the map using the calculated final_bounds
    try:
        # Use folium's fit_bounds to automatically adjust the view
        m.fit_bounds(final_bounds, padding=(30, 30))
    except Exception as e:
        st.error(f"Error fitting calculated bounds {final_bounds}: {e}")
