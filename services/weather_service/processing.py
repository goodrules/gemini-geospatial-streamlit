"""
Processing functions for weather data.

This module contains functions for processing and analyzing weather data.
"""

import streamlit as st
import pandas as pd
import geopandas as gpd
from datetime import date
from shapely.wkt import loads as wkt_loads
from shapely.geometry import shape, Point

from data.weather_data import get_weather_forecast_data
from utils.geo_utils import find_region_by_name, get_major_cities
from utils.streamlit_utils import add_status_message
from utils.weather_utils import (
    preprocess_weather_timestamps,
    create_weather_geodataframe,
    find_location_geometry,
    prepare_display_values,
    filter_weather_by_timestamp,
    filter_weather_by_date,
    filter_weather_by_latest_date
)
from data.geospatial_data import get_us_states, get_us_counties


def fetch_weather_data():
    """
    Fetch the weather forecast data
    
    Returns:
        DataFrame with weather forecast data or None if error
    """
    try:
        # Get init_date from session state or default to today
        selected_init_date = st.session_state.get("selected_init_date", date.today())
        
        with st.spinner(f"Loading weather forecast data for {selected_init_date}..."):
            weather_df = get_weather_forecast_data(selected_init_date)
            
        # Check if we got any data
        if weather_df is None or weather_df.empty:
            add_status_message("No weather forecast data available.", "warning")
            return None
            
        return weather_df
        
    except Exception as e:
        st.error(f"Error fetching weather data: {str(e)}")
        return None


def filter_weather_data_by_time(weather_df, parameter, timestamp_str=None, date_str=None):
    """
    Filter weather data by timestamp or date
    
    Args:
        weather_df: DataFrame with weather data
        parameter: The weather parameter being analyzed
        timestamp_str: Specific timestamp to filter for
        date_str: Fallback date to filter for if no timestamp
        
    Returns:
        tuple: (filtered_df, filter_message)
    """
    # Check if we have a specific timestamp to filter for
    if timestamp_str:
        # Filter for specific timestamp
        filtered_df, filter_message = filter_weather_by_timestamp(weather_df, timestamp_str)
        # filter_message is already set by the function
    elif date_str:
        # Filter for specific date
        filtered_df, filter_message = filter_weather_by_date(weather_df, date_str, parameter)
        # filter_message is already set by the function
    else:
        # Default: get the latest date in the data
        filtered_df, filter_message = filter_weather_by_latest_date(weather_df, parameter)
        # filter_message is already set by the function
    
    return filtered_df, filter_message


def filter_weather_by_location(weather_gdf, location):
    """
    Filter weather data by location
    
    Args:
        weather_gdf: GeoDataFrame with weather data
        location: Location name to filter by
        
    Returns:
        tuple: (filtered_gdf, location_geometry)
    """
    location_geometry = None
    
    # 1. Check if it's a US state
    states_gdf = get_us_states()
    state_match = find_region_by_name(states_gdf, location)
    
    if state_match is not None and not state_match.empty:
        location_geometry = state_match.geometry.iloc[0]
        add_status_message(f"Filtering weather for state: {state_match['state_name'].iloc[0]}", "info")
        
    # 2. If not a state, check if it's a US county
    if location_geometry is None:
        counties_gdf = get_us_counties()
        county_match = find_region_by_name(counties_gdf, location)
        
        if county_match is not None and not county_match.empty:
            location_geometry = county_match.geometry.iloc[0]
            # Include state information if available
            if 'state_name' in county_match.columns:
                add_status_message(f"Filtering weather for county: {county_match['county_name'].iloc[0]}, {county_match['state_name'].iloc[0]}", "info")
            else:
                add_status_message(f"Filtering weather for county: {county_match['county_name'].iloc[0]}", "info")
    
    # 3. If not a state or county, check if it's a major city
    if location_geometry is None:
        cities = get_major_cities()
        city_geometry, city_name, location_type = find_location_geometry(location, states_gdf, counties_gdf, cities)
        
        if city_geometry is not None:
            # Create a 50km buffer around the city point for filtering
            # Convert to projected CRS for buffer
            point_gdf = gpd.GeoDataFrame(geometry=[city_geometry], crs="EPSG:4326")
            point_proj = point_gdf.to_crs("EPSG:3857")  # Web Mercator
            buffer_proj = point_proj.buffer(50000)  # 50km buffer
            buffer_gdf = gpd.GeoDataFrame(geometry=buffer_proj, crs="EPSG:3857")
            buffer_back = buffer_gdf.to_crs("EPSG:4326")
            location_geometry = buffer_back.geometry.iloc[0]
            add_status_message(f"Filtering weather for {location_type}: {city_name} (50km radius)", "info")
    
    # If we couldn't find a known location, display warning and return unfiltered data
    if location_geometry is None:
        add_status_message(f"Couldn't find location: {location}. Showing all data.", "warning")
        return weather_gdf, None
    
    # Filter data by intersection with the location geometry
    filtered_gdf = weather_gdf[weather_gdf.intersects(location_geometry)].copy()
    add_status_message(f"Found {len(filtered_gdf)} weather data points for {location}", "info")
    
    return filtered_gdf, location_geometry 
