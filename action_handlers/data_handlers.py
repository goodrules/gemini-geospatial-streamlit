"""Handlers for data-related map actions"""
import folium
import json
import pandas as pd
import streamlit as st
from action_handlers.base_handler import create_handler, ActionDict, BoundsList
from data.geospatial_data import  (get_pa_power_lines)
from utils.streamlit_utils import add_status_message

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
    if dataset_name == "power_lines" or dataset_name == "pa_power_lines":
        # Get region information from action parameters if available
        region_name = action.get("region", None)
        
        # SIMPLIFICATION: If no region is specified, don't show any power lines
        if not region_name:
            add_status_message("No region specified for power lines. Please specify a region name.", "warning")
            return bounds
            
        # Get the region geometry to filter power lines
        from utils.geo_utils import find_region_by_name
        from data.geospatial_data import get_us_states, get_us_counties
        
        region_polygon = None
        region_found = False
        
        # First try to find the region in states dataset
        states_gdf = get_us_states()
        region_match = find_region_by_name(states_gdf, region_name)
        
        if region_match is not None and not region_match.empty:
            region_polygon = region_match.geometry.iloc[0]
            region_found = True
            add_status_message(f"Found region in states data: {region_match['state_name'].iloc[0]}", "info")
        else:
            # Try counties dataset
            counties_gdf = get_us_counties()
            region_match = find_region_by_name(counties_gdf, region_name)
            
            if region_match is not None and not region_match.empty:
                region_polygon = region_match.geometry.iloc[0]
                region_found = True
                # Include state information if available
                if 'state_name' in region_match.columns:
                    add_status_message(f"Found region in counties data: {region_match['county_name'].iloc[0]}, {region_match['state_name'].iloc[0]}", "info")
                elif 'state' in region_match.columns:
                    add_status_message(f"Found region in counties data: {region_match['county_name'].iloc[0]}, {region_match['state'].iloc[0]}", "info")
                else:
                    add_status_message(f"Found region in counties data: {region_match['county_name'].iloc[0]}", "info")
        
        # If we couldn't find the region, don't show power lines
        if not region_found or region_polygon is None:
            add_status_message(f"Could not identify region '{region_name}'. No power lines will be displayed.", "warning")
            return bounds
        
        # Load power line data and immediately filter it
        add_status_message(f"Loading power line data and filtering for {region_name}...", "info")
        gdf = get_pa_power_lines(use_geojson=True)
        
        if gdf is None or gdf.empty:
            add_status_message("Failed to load power line data.", "error")
            return bounds
        
        # Log region polygon information
        add_status_message(f"Region polygon bounds: {region_polygon.bounds}", "info")
        
        # No special cases - just log the information
        add_status_message(f"Processing region: {region_name}", "info")
        
        # Create a buffer around the region for more lenient filtering
        buffered_region = region_polygon.buffer(0.05)  # ~5km buffer in degrees
        add_status_message(f"Using buffered region for power line filtering", "info")
        
        # Display min/max coordinates of power line data as debugging info
        pl_bounds = gdf.total_bounds
        add_status_message(f"Power line data bounds: {pl_bounds}", "info")
        
        # Get the bounds of the region
        minx, miny, maxx, maxy = region_polygon.bounds
        
        # Add a simple buffer to the bounds (0.1 degrees ~ 10km)
        buffered_bounds = (minx - 0.1, miny - 0.1, maxx + 0.1, maxy + 0.1)
        add_status_message(f"Using buffered bounds: {buffered_bounds}", "info")
        
        # Simple filtering by checking if points fall within bounds
        # This is a simpler approach that will work with any polygon bounds
        filtered_gdf = gdf[(gdf.geometry.x >= buffered_bounds[0]) & 
                           (gdf.geometry.y >= buffered_bounds[1]) & 
                           (gdf.geometry.x <= buffered_bounds[2]) & 
                           (gdf.geometry.y <= buffered_bounds[3])].copy()
        
        add_status_message(f"Power lines in buffered bounds: {len(filtered_gdf)}", "info")
        
        # Use the filtered data
        gdf = filtered_gdf
        add_status_message(f"Final power line count for {region_name}: {len(gdf)}", "info")
        
        if gdf.empty:
            add_status_message(f"No power lines found within {region_name}.", "warning")
            return bounds
        
        # For display configuration
        layer_name = f"Power Lines ({region_name})"
        default_color = "#0066cc"  # Blue for power lines
        fill_color = "#ffff00"    # Yellow fill
    else:
        # st.warning(f"Unknown local dataset: {dataset_name}")
        return bounds
            
    if gdf is None or gdf.empty:
        add_status_message(f"No data available for {dataset_name}.", "warning")
        return bounds
        
    # Convert timestamps to strings to avoid serialization issues
    for col in gdf.columns:
        if pd.api.types.is_datetime64_any_dtype(gdf[col]):
            gdf[col] = gdf[col].astype(str)
    
    # Create a tooltip with dataset information
    default_tooltip_fields = ["ID", "VOLTAGE", "OWNER"] if "VOLTAGE" in gdf.columns else [gdf.columns[0]]
    default_tooltip_aliases = ["Line ID", "Voltage (kV)", "Owner"] if "VOLTAGE" in gdf.columns else [gdf.columns[0]]
    
    tooltip_fields = action.get("tooltip_fields", default_tooltip_fields)
    tooltip_aliases = action.get("tooltip_aliases", default_tooltip_aliases)
    
    # Use tooltip if fields are available
    tooltip = None
    if tooltip_fields:
        tooltip = folium.GeoJsonTooltip(
            fields=tooltip_fields,
            aliases=tooltip_aliases,
            sticky=True
        )
    
    # Detect if we're using points or lines for different rendering
    is_point_data = all(geom.geom_type == 'Point' for geom in gdf.geometry)
    
    if is_point_data:
        # For point data, add individual dots with no markers
        add_status_message(f"Rendering {len(gdf)} power line points as dots without markers", "info")
        
        # Create a feature group for the dots
        dot_group = folium.FeatureGroup(name=layer_name)
        
        # Add the points as dots (circles) directly
        for idx, row in gdf.iterrows():
            # Extract coordinates from the Point geometry
            coords = (row.geometry.y, row.geometry.x)
            
            # Create tooltip for this point
            point_tooltip = f"Voltage: {row.get('VOLTAGE', 'N/A')}, Owner: {row.get('OWNER', 'N/A')}"
            
            # Create a slightly larger circle with partial opacity
            folium.Circle(
                location=coords,
                radius=300,  # 300 meters as requested
                color=action.get("color", '#ff3300'),  # Use action color or default to orange-red
                weight=2,  # Line weight
                fill=True,
                fill_color=action.get("color", '#ff3300'),  # Use action color or default to orange-red
                fill_opacity=0.7,  # Partial opacity as requested
                tooltip=point_tooltip,  # Use tooltip only, no popup to avoid markers
            ).add_to(dot_group)
        
        # Add the feature group to the map
        dot_group.add_to(m)
    else:
        # For line data, use regular GeoJSON style
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
