"""
Weather service module for weather data processing and visualization.
"""

# Public API for weather_service - import everything from core.py
from services.weather_service.core import (
    # Main handler
    handle_show_weather,
    
    # Visualization functions
    create_weather_tooltip,
    get_weather_color_scale,
    add_weather_layer_to_map,
    
    # Processing functions
    fetch_weather_data,
    filter_weather_data_by_time,
    filter_weather_by_location
) 
