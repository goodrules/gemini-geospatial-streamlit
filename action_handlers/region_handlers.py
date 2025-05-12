"""Handlers for region-related map actions"""
import folium
import json
import pandas as pd
import streamlit as st
from data.geospatial_data import (get_us_states, get_us_counties, get_us_zipcodes, get_us_power_lines)
from utils.streamlit_utils import add_status_message
from action_handlers.base_handler import create_handler, ActionDict, BoundsList
from utils.geo_utils import find_region_by_name, get_world_countries
from utils.streamlit_utils import create_tooltip_html

@create_handler
def handle_highlight_region(action: ActionDict, m: folium.Map) -> BoundsList:
    """
    Handle the highlight_region action
    
    Args:
        action: The action dictionary with parameters
        m: The folium map object
        
    Returns:
        List of bounds to include in the overall map fitting
    """
    bounds = []
    
    region_name = action.get("region_name")
    region_type = action.get("region_type", "state")
    
    if not region_name:
        return bounds
        
    # Get the appropriate dataset based on region type
    gdf = None
    if region_type.lower() == "state":
        gdf = get_us_states()
    elif region_type.lower() == "county":
        gdf = get_us_counties()
        # For counties, we might need to include state in the search
        state_name = action.get("state_name")
        if state_name and gdf is not None:
            # First filter by state if provided
            states = get_us_states()
            state = find_region_by_name(states, state_name)
            if state is not None:
                state_fips = state['state_fips_code'].iloc[0]
                gdf = gdf[gdf['state_fips_code'] == state_fips]
    elif region_type.lower() in ["zipcode", "zip_code", "zip"]:
        gdf = get_us_zipcodes()
        # For zip codes, we might need to filter by state or county
        state_name = action.get("state_name")
        county_name = action.get("county_name")
        if state_name and gdf is not None:
            # Filter by state if provided
            gdf = gdf[gdf['state_name'].str.lower() == state_name.lower()]
        if county_name and gdf is not None:
            # Filter by county if provided
            gdf = gdf[gdf['county'].str.lower() == county_name.lower()]
    elif region_type.lower() == "country":
        gdf = get_world_countries()
    elif region_type.lower() == "continent":
        gdf = get_world_countries()
        # For continents, search the continent column
        region = find_region_by_name(gdf, region_name, ['continent'])
        if region is not None:
            # Add the GeoJSON for this region
            folium.GeoJson(
                region.__geo_interface__,
                name=f"{region_name}",
                style_function=lambda x: {
                    'fillColor': action.get("fill_color", "#ff7800"),
                    'color': action.get("color", "black"),
                    'weight': 2,
                    'fillOpacity': action.get("fill_opacity", 0.5)
                }
            ).add_to(m)
            
            # Add region bounds to bounds list
            region_bounds = region.total_bounds
            bounds.append([region_bounds[1], region_bounds[0]])  # SW corner
            bounds.append([region_bounds[3], region_bounds[2]])  # NE corner
        return bounds
    elif region_type.lower() == "power_line":
        gdf = get_us_power_lines()
    
    # Find the region
    region = find_region_by_name(gdf, region_name)
    
    if region is not None:
        # Create a tooltip with region information
        tooltip_html = create_tooltip_html(region, region_type)
        
        # Convert timestamps to strings to avoid serialization issues
        for col in region.columns:
            if pd.api.types.is_datetime64_any_dtype(region[col]):
                region[col] = region[col].astype(str)
        
        # Add the GeoJSON for this region with tooltip
        geo_layer = folium.GeoJson(
            json.loads(region.to_json()),
            name=f"{region_name}",
            style_function=lambda x: {
                'fillColor': action.get("fill_color", "#ff7800"),
                'color': action.get("color", "black"),
                'weight': action.get("weight", 2),
                'fillOpacity': action.get("fill_opacity", 0.5)
            },
            tooltip=folium.Tooltip(tooltip_html)
        ).add_to(m)
        
        # Add region bounds to bounds list
        region_bounds = region.total_bounds
        bounds.append([region_bounds[1], region_bounds[0]])  # SW corner
        bounds.append([region_bounds[3], region_bounds[2]])  # NE corner
    else:
        st.write(f"Could not find region: {region_name}")
            
    return bounds 
