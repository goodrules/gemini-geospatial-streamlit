"""
Validation functions for risk analysis.

This module contains functions for validating input data before risk analysis.
"""

import streamlit as st
from utils.streamlit_utils import add_status_message


def validate_weather_data(weather_gdf):
    """
    Validate weather data for risk analysis.
    
    Args:
        weather_gdf: GeoDataFrame with weather forecast data.
        
    Returns:
        dict: Validation result dictionary with "is_valid" boolean and "message" string.
    """
    if weather_gdf.empty:
        add_status_message("[Risk Analysis] Input weather data is empty.", "warning")
        return {"is_valid": False, "message": "Input weather data is empty."}

    # Ensure required columns exist
    required_cols = ['wind_speed', 'forecast_time', 'geography_polygon', 'geometry']
    if not all(col in weather_gdf.columns for col in required_cols):
        missing = [col for col in required_cols if col not in weather_gdf.columns]
        st.error(f"Weather data for risk analysis missing required columns: {missing}")
        return {"is_valid": False, "message": f"Missing required columns: {missing}"}
        
    if 'forecast_time' not in weather_gdf.columns:
        st.error("Weather data for risk analysis missing 'forecast_time'.")
        return {"is_valid": False, "message": "Missing 'forecast_time'."}
        
    return {"is_valid": True, "message": "Data valid"} 
