"""
Data loading functions for risk analysis.

This module contains functions for loading and preparing data for risk analysis.
"""

import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from datetime import date, timedelta
from shapely.wkt import loads as wkt_loads

from data.weather_data import get_weather_forecast_data
from data.geospatial_data import get_us_power_lines, get_us_states, get_us_counties
from utils.geo_utils import find_region_by_name
from utils.streamlit_utils import add_status_message


def extract_risk_analysis_params(action):
    """
    Extract and validate parameters for risk analysis.
    
    Args:
        action: Action dictionary with analysis parameters.
        
    Returns:
        dict: Dictionary of validated parameters or {"valid": False}.
    """
    high_threshold = action.get("high_threshold", 16.0)
    moderate_threshold = action.get("moderate_threshold", 13.0)
    forecast_days = action.get("forecast_days", 3)
    analyze_power_lines = action.get("analyze_power_lines", False)
    
    # Provide user feedback based on parameters
    if analyze_power_lines:
        add_status_message("Power line risk analysis explicitly requested.", "info")
    
    # Get the region parameter (REQUIRED)
    region_name = action.get("region")
    if not region_name:
        add_status_message("Region parameter is required for wind risk analysis. Please specify a region (state or county).", "error")
        return {"valid": False}
    
    # For UI feedback
    if analyze_power_lines:
        add_status_message(f"Analyzing wind risk to power infrastructure in {region_name}", "info")
    else:
        add_status_message(f"Analyzing general wind risk for region: {region_name}", "info")
        
    return {
        "valid": True,
        "high_threshold": high_threshold,
        "moderate_threshold": moderate_threshold,
        "forecast_days": forecast_days,
        "analyze_power_lines": analyze_power_lines,
        "region_name": region_name
    }


def load_weather_data(forecast_days):
    """
    Load weather forecast data for the analysis.
    
    Args:
        forecast_days: Number of days to forecast.
        
    Returns:
        DataFrame: Weather forecast data or None if error.
    """
    try:
        # Get weather forecast data for the selected init_date
        selected_init_date = st.session_state.get("selected_init_date", date.today())
        
        # Generate the simplified query for display in the spinner
        from data.weather_data import get_weather_query
        _, init_date_str = get_weather_query(selected_init_date)
        simplified_query = f"SELECT weather.init_time, geography, forecast_time, temperature, precipitation, wind_speed FROM weathernext_graph_forecasts WHERE init_time = '{init_date_str}'"
        
        # Fetch the data with a spinner showing the query
        with st.spinner(f"Executing: {simplified_query}"):
            weather_df_all = get_weather_forecast_data(selected_init_date)

        if weather_df_all is None or weather_df_all.empty:
            add_status_message("No weather data available for risk analysis.", "warning")
            return None

        # Process and filter the data by timeframe
        weather_df_filtered = process_weather_timestamps(weather_df_all, forecast_days)
        return weather_df_filtered
        
    except Exception as e:
        add_status_message(f"Error loading weather data: {str(e)}", "error")
        import traceback
        traceback.print_exc()
        return None


def process_weather_timestamps(weather_df, forecast_days):
    """
    Process and filter weather data by timeframe.
    
    Args:
        weather_df: DataFrame with weather data.
        forecast_days: Number of days to forecast.
        
    Returns:
        DataFrame: Filtered weather data.
    """
    if 'forecast_time' not in weather_df.columns:
        add_status_message("Weather data missing 'forecast_time' column.", "error")
        return pd.DataFrame()  # Empty DataFrame
        
    try:
        # Make a copy before modification
        weather_df = weather_df.copy()
        
        # Convert to datetime and ensure UTC timezone
        weather_df['forecast_time'] = pd.to_datetime(weather_df['forecast_time'], errors='coerce')
        if weather_df['forecast_time'].dt.tz is None:
            weather_df['forecast_time'] = weather_df['forecast_time'].dt.tz_localize('UTC')
        else:
            weather_df['forecast_time'] = weather_df['forecast_time'].dt.tz_convert('UTC')
            
        # Drop rows where conversion failed
        weather_df.dropna(subset=['forecast_time'], inplace=True)
        
        if weather_df.empty:
            add_status_message("No valid weather timestamps found after processing.", "warning")
            return pd.DataFrame()
            
        # Filter by forecast days
        try:
            forecast_days = int(forecast_days)
            if forecast_days < 1: 
                forecast_days = 1
                st.warning("Forecast days minimum is 1.")
            if forecast_days > 10: 
                forecast_days = 10
                st.warning("Limiting forecast analysis to 10 days.")

            # Ensure init_date is a timezone-aware Timestamp
            selected_init_date = st.session_state.get("selected_init_date", date.today())
            if isinstance(selected_init_date, date) and not isinstance(selected_init_date, pd.Timestamp):
                init_dt = pd.Timestamp(selected_init_date, tz='UTC')
            else:
                init_dt = pd.Timestamp(selected_init_date).tz_convert('UTC') if pd.Timestamp(selected_init_date).tzinfo else pd.Timestamp(selected_init_date).tz_localize('UTC')

            end_dt = init_dt + timedelta(days=forecast_days)

            # Apply the time filter
            weather_df_filtered = weather_df[
                (weather_df['forecast_time'] >= init_dt) &
                (weather_df['forecast_time'] < end_dt)
            ].copy()
            
            if weather_df_filtered.empty:
                st.warning(f"No weather data available for the next {forecast_days} day(s).")
                
            return weather_df_filtered

        except (ValueError, TypeError) as e:
            st.error(f"Invalid 'forecast_days' parameter: {forecast_days}. Defaulting to 3 days. Error: {e}")
            forecast_days = 3
            
            # Recalculate with default
            selected_init_date = st.session_state.get("selected_init_date", date.today())
            if isinstance(selected_init_date, date) and not isinstance(selected_init_date, pd.Timestamp):
                init_dt = pd.Timestamp(selected_init_date, tz='UTC')
            else:
                init_dt = pd.Timestamp(selected_init_date).tz_convert('UTC') if pd.Timestamp(selected_init_date).tzinfo else pd.Timestamp(selected_init_date).tz_localize('UTC')
                
            end_dt = init_dt + timedelta(days=forecast_days)
            
            weather_df_filtered = weather_df[
                (weather_df['forecast_time'] >= init_dt) &
                (weather_df['forecast_time'] < end_dt)
            ].copy()
            
            if weather_df_filtered.empty:
                st.warning(f"No weather data available for the next {forecast_days} day(s).")
                
            return weather_df_filtered
            
    except Exception as e:
        add_status_message(f"Error processing weather timestamps: {e}", "error")
        return pd.DataFrame()


def find_and_add_region_to_map(region_name, m):
    """
    Find region boundary and add to map.
    
    Args:
        region_name: Name of the region to find (state or county).
        m: Folium map object.
        
    Returns:
        dict: Result dictionary with success flag, polygon and bounds.
    """
    region_polygon = None
    
    # First try states dataset
    states_gdf = get_us_states()
    region_match = find_region_by_name(states_gdf, region_name)
    
    if region_match is not None and not region_match.empty:
        region_polygon = region_match.geometry.iloc[0]
        add_status_message(f"Found matching state: {region_match['state_name'].iloc[0]}", "info")
    else:
        # Try counties dataset
        counties_gdf = get_us_counties()
        region_match = find_region_by_name(counties_gdf, region_name)
        
        if region_match is not None and not region_match.empty:
            region_polygon = region_match.geometry.iloc[0]
            # Include state information if available
            if 'state_name' in region_match.columns:
                add_status_message(f"Found matching county: {region_match['county_name'].iloc[0]}, {region_match['state_name'].iloc[0]}", "info")
            elif 'state' in region_match.columns:
                add_status_message(f"Found matching county: {region_match['county_name'].iloc[0]}, {region_match['state'].iloc[0]}", "info")
            else:
                add_status_message(f"Found matching county: {region_match['county_name'].iloc[0]}", "info")
    
    if region_polygon is None:
        add_status_message(f"Could not find region: {region_name}. Please specify a valid state or county name.", "error")
        return {"success": False}
    
    # Add the region to the map for reference
    folium.GeoJson(
        region_match.__geo_interface__,
        name=f"Analysis Region: {region_name}",
        style_function=lambda x: {
            'fillColor': "#8080FF",
            'color': "blue",
            'weight': 2,
            'fillOpacity': 0.1
        }
    ).add_to(m)
    
    # Add region to bounds
    region_bounds = region_match.total_bounds
    bounds = [[region_bounds[1], region_bounds[0]], [region_bounds[3], region_bounds[2]]]
    
    return {
        "success": True,
        "polygon": region_polygon,
        "bounds": bounds
    }


def convert_weather_to_geodataframe(weather_df):
    """
    Convert filtered weather data to GeoDataFrame.
    
    Args:
        weather_df: DataFrame with weather data.
        
    Returns:
        GeoDataFrame: Weather data with geometry or None if error.
    """
    geometries = []
    valid_indices = []
    parse_errors = 0
    
    for index, row in weather_df.iterrows():
        try:
            poly = wkt_loads(row['geography_polygon'])
            if poly.is_valid:
                geometries.append(poly)
                valid_indices.append(index)
            else:
                parse_errors += 1
        except Exception:
            parse_errors += 1
            
    if parse_errors > 0:
        st.warning(f"Skipped {parse_errors} rows due to invalid geometry during risk analysis.")
        
    if not valid_indices:
        st.error("No valid geometries found in filtered weather data.")
        return None
        
    weather_gdf = gpd.GeoDataFrame(
        weather_df.loc[valid_indices],
        geometry=geometries,
        crs="EPSG:4326"
    )
    
    return weather_gdf


def filter_weather_by_region(weather_df, region_polygon):
    """
    Filter weather data by region.
    
    Args:
        weather_df: DataFrame with weather data.
        region_polygon: Polygon geometry of the region.
        
    Returns:
        GeoDataFrame: Filtered weather data.
    """
    # Convert to GeoDataFrame first
    weather_gdf = convert_weather_to_geodataframe(weather_df)
    if weather_gdf is None or weather_gdf.empty:
        return pd.DataFrame()
    
    # Apply geographic filtering
    with st.spinner("Filtering weather data by region..."):
        original_count = len(weather_gdf)
        weather_gdf = weather_gdf[weather_gdf.intersects(region_polygon)].copy()
        add_status_message(f"Filtered weather data from {original_count} points to {len(weather_gdf)} points within region", "info")
        
        if weather_gdf.empty:
            add_status_message("No weather data points found within region.", "warning")
            
    return weather_gdf


def load_and_filter_power_lines(region_polygon):
    """
    Load power line data and filter by region.
    
    Args:
        region_polygon: Polygon geometry of the region.
        
    Returns:
        GeoDataFrame: Filtered power line data or None if error.
    """
    if region_polygon is None:
        add_status_message("No valid region polygon for power line analysis", "warning")
        return None
        
    # Load power line data
    add_status_message("Loading power line data...", "info")
    power_lines_gdf = get_us_power_lines(use_geojson=True)
    
    if power_lines_gdf is None or power_lines_gdf.empty:
        add_status_message("Failed to load power line data.", "error")
        return None
        
    # Display bounds for debugging
    pl_bounds = power_lines_gdf.total_bounds
    add_status_message(f"Power line data bounds: {pl_bounds}", "info")
    
    # Create a buffer around the region
    buffered_region = region_polygon.buffer(0.02)  # ~2km buffer in degrees
    add_status_message(f"Created shape-following buffer for risk analysis", "info")
    
    # First filter by bounding box for performance
    minx, miny, maxx, maxy = buffered_region.bounds
    rough_filtered = power_lines_gdf[
        (power_lines_gdf.geometry.x >= minx) & 
        (power_lines_gdf.geometry.y >= miny) & 
        (power_lines_gdf.geometry.x <= maxx) & 
        (power_lines_gdf.geometry.y <= maxy)
    ].copy()
    
    add_status_message(f"Initial bounding box filter: {len(rough_filtered)} points", "info")
    
    # Then do precise filtering using the actual buffered shape
    filtered_gdf = rough_filtered[rough_filtered.intersects(buffered_region)].copy()
    add_status_message(f"Power lines in buffered bounds: {len(filtered_gdf)}", "info")
    
    if filtered_gdf.empty:
        add_status_message("No power lines found within buffered region.", "warning")
        return None
        
    return filtered_gdf 
