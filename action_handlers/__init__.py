"""
Action handlers package for the map processor.

This package contains modules for different types of map actions:
- marker_handlers: For adding markers and circles
- region_handlers: For highlighting geographic regions
- geometry_handlers: For adding lines, polygons, and heatmaps
- data_handlers: For showing local datasets
- view_handlers: For controlling map view
- wind_risk_handlers: For analyzing wind risk to power lines
- weather_handlers: For displaying weather data
- temperature_risk_handlers: For showing unsafe temperature areas and affected oil wells
"""

from action_handlers.marker_handlers import handle_add_marker, handle_add_circle
from action_handlers.region_handlers import handle_highlight_region
from action_handlers.geometry_handlers import handle_add_line, handle_add_polygon, handle_add_heatmap
from action_handlers.data_handlers import handle_show_local_dataset
from action_handlers.view_handlers import handle_fit_bounds
from action_handlers.wind_risk_handlers import handle_analyze_wind_risk
from action_handlers.weather_handlers import handle_show_weather
from action_handlers.temperature_risk_handlers import handle_unsafe_temperature, handle_high_temperature_risk

# Export all handlers
__all__ = [
    'handle_add_marker', 
    'handle_add_circle',
    'handle_highlight_region',
    'handle_add_line',
    'handle_add_polygon',
    'handle_add_heatmap',
    'handle_show_local_dataset',
    'handle_fit_bounds',
    'handle_analyze_wind_risk',
    'handle_show_weather',
    'handle_unsafe_temperature',
    'handle_high_temperature_risk'
] 
