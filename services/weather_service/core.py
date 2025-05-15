"""
Core weather service functionality.

This module contains the main functions for weather data processing and visualization,
providing the public API for the weather service package.
"""

import streamlit as st
import geopandas as gpd
from datetime import date

from utils.streamlit_utils import add_status_message
from utils.weather_utils import (
    preprocess_weather_timestamps,
    create_weather_geodataframe,
    prepare_display_values
)

# Import and re-export functions from processing module
from services.weather_service.processing import (
    fetch_weather_data,
    filter_weather_data_by_time,
    filter_weather_by_location
)

# Import and re-export functions from visualization module
from services.weather_service.visualization import (
    create_weather_tooltip,
    get_weather_color_scale,
    add_weather_layer_to_map
)


def handle_show_weather(action, m):
    """
    Handle the show_weather action by processing data and displaying on map.
    
    Args:
        action: The action dictionary with parameters (parameter, forecast_timestamp, forecast_date, location)
        m: The folium map object to add layers to
        
    Returns:
        List of bounds to include in the overall map fitting
    """
    bounds = []
    
    # Get parameters
    parameter = action.get("parameter", "temperature")  # Default to temperature
    selected_timestamp_str = action.get("forecast_timestamp") # Expecting full timestamp string
    selected_date_str = action.get("forecast_date") # Fallback: Expecting "YYYY-MM-DD"
    location = action.get("location")  # Optional location filter
    
    # Get current init date from session state
    current_init_date = st.session_state.get("selected_init_date")
    
    # Verify if the selected_date_str is still valid with the current init_date
    # This ensures stale values from previous cache aren't used
    if selected_date_str and current_init_date:
        if isinstance(current_init_date, str):
            current_init_date_str = current_init_date
        else:
            current_init_date_str = current_init_date.strftime('%Y-%m-%d')
            
        # If the date is older than init_date, use the init_date instead
        # (can't forecast before the init date)
        from datetime import datetime
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            init_date = datetime.strptime(current_init_date_str, '%Y-%m-%d').date()
            
            if selected_date < init_date:
                selected_date_str = current_init_date_str
                add_status_message(f"Updated forecast date to match current initialization date: {current_init_date_str}", "info")
        except ValueError:
            # Handle invalid date formats
            selected_date_str = current_init_date_str
            add_status_message(f"Invalid date format, using initialization date: {current_init_date_str}", "warning")
    
    # Debug: Show what parameters were passed
    # st.write(f"DEBUG Weather Action - parameter: {parameter}, timestamp: {selected_timestamp_str}, date: {selected_date_str}, location: {location}")

    try:
        # 1. Get weather forecast data
        weather_df_all = fetch_weather_data()
        if weather_df_all is None or weather_df_all.empty:
            add_status_message("No weather data available", "error")
            return bounds

        # 2. Process timestamps
        weather_df_all = preprocess_weather_timestamps(weather_df_all)
        if weather_df_all is None or weather_df_all.empty:
            add_status_message("No valid weather timestamps found after processing", "warning")
            return bounds

        # 3. Filter by timestamp or date
        weather_df, filter_message = filter_weather_data_by_time(
            weather_df_all, parameter, selected_timestamp_str, selected_date_str
        )
        
        # Debug: Show filter message value
        # st.write(f"DEBUG: Filter message: {filter_message}")
        
        if weather_df.empty:
            add_status_message(f"No weather data available for selected time filter: {filter_message}", "warning")
            return bounds
            
        # 5. Create GeoDataFrame from the weather data
        weather_gdf = create_weather_geodataframe(weather_df)
        if weather_gdf is None or weather_gdf.empty:
            add_status_message("Failed to convert weather data to GeoDataFrame", "warning")
            return bounds
            
        # 4. Prepare values for display (min, max, units)
        weather_gdf, unit = prepare_display_values(weather_gdf, parameter)
        
        # Calculate min and max for display scaling
        # Use a more robust method to get min/max values
        if 'display_value' in weather_gdf.columns and not weather_gdf.empty:
            min_val = weather_gdf['display_value'].min()
            max_val = weather_gdf['display_value'].max()
            
            # Add a small buffer to min/max to ensure a proper range
            if min_val == max_val:
                min_val = min_val - 1
                max_val = max_val + 1
        else:
            # Fallback values
            min_val = 0
            max_val = 100
            add_status_message("Using default min/max values for color scale", "warning")

        # 6. Filter by location (if specified)
        if location:
            weather_gdf, location_geometry = filter_weather_by_location(weather_gdf, location)
            if location_geometry is not None:
                # Add the region outline to the map
                location_gdf = gpd.GeoDataFrame(geometry=[location_geometry], crs="EPSG:4326")
                loc_bounds = location_gdf.total_bounds
                bounds.append([[loc_bounds[1], loc_bounds[0]], [loc_bounds[3], loc_bounds[2]]])
            
            if weather_gdf.empty:
                add_status_message(f"No weather data found for location: {location}", "warning")
                return bounds

        # 7. Add the weather layer to the map
        layer_bounds = add_weather_layer_to_map(
            m, weather_gdf, parameter, min_val, max_val, unit, location, filter_message
        )
        
        if layer_bounds:
            bounds.append(layer_bounds)
            
    except Exception as e:
        add_status_message(f"Error processing weather data: {str(e)}", "error")
        import traceback
        traceback.print_exc()
    
    return bounds 
