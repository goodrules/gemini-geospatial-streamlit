"""
Services module for the Gemini Geospatial Streamlit application.
This module contains all services for data processing, analysis, and visualization.
"""

# Import services for direct access through services package
from services.gemini_service import initialize_gemini_client, get_gemini_response
from services.map_core import initialize_map, serialize_geojson, fit_map_to_bounds
from services.map_processor import process_map_actions, get_action_handlers
from services.risk_analyzer import analyze_wind_risk, handle_analyze_wind_risk
from services.weather_service import (
    create_weather_tooltip,
    get_weather_color_scale,
    add_weather_layer_to_map,
    handle_show_weather,
    fetch_weather_data,
    filter_weather_data_by_time,
    filter_weather_by_location
)
