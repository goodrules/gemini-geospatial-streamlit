"""
Weather service module for weather data processing and visualization.

This is a facade module that imports and re-exports the functionality 
from the refactored weather_service package.
"""

# Re-export the public API
from services.weather_service.core import (
    handle_show_weather,
    create_weather_tooltip,
    get_weather_color_scale,
    add_weather_layer_to_map,
    fetch_weather_data,
    filter_weather_data_by_time,
    filter_weather_by_location
) 
