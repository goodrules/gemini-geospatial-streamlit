"""Handlers for temperature risk-related map actions"""
import folium
import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
from branca.colormap import LinearColormap
import hashlib
from typing import Dict, List, Tuple, Optional, Any, Union
import os.path

from action_handlers.base_handler import create_handler, ActionDict, BoundsList
from services.weather_service import fetch_weather_data, filter_weather_data_by_time
from utils.weather_utils import prepare_display_values, create_weather_geodataframe
from utils.streamlit_utils import add_status_message
from data.geospatial_data import get_oil_wells_data
from utils.geo_utils import find_region_by_name
from data.geospatial_data import get_us_states, get_us_power_lines

def _get_region_data(region_name: str, m: folium.Map) -> Tuple[Optional[gpd.GeoDataFrame], Optional[List]]:
    """Get region GeoDataFrame and add boundary to map."""
    bounds = []
    states_gdf = get_us_states()
    region_match = find_region_by_name(states_gdf, region_name)
    
    if region_match is None or region_match.empty:
        add_status_message(f"Region not found: {region_name}", "error")
        return None, bounds
    
    # Add the region outline to the map
    folium.GeoJson(
        region_match.__geo_interface__,
        name="State Boundary",
        style_function=lambda x: {
            'fillColor': 'transparent',
            'color': 'black',
            'weight': 2,
            'fillOpacity': 0
        }
    ).add_to(m)
    
    # Get region bounds
    region_bounds = region_match.total_bounds
    
    # Convert bounds to [[lat, lon], [lat, lon]] format for Folium
    sw = [region_bounds[1], region_bounds[0]]  # [lat, lon] format for folium
    ne = [region_bounds[3], region_bounds[2]]
    bounds.append([sw, ne])
    
    return region_match, bounds

def _get_weather_data(selected_timestamp_str: Optional[str], selected_date_str: str) -> Optional[pd.DataFrame]:
    """Fetch and preprocess weather data."""
    # 1. Get weather forecast data
    weather_df_all = fetch_weather_data()
    if weather_df_all is None or weather_df_all.empty:
        add_status_message("No weather data available", "error")
        return None

    # 2. Process timestamps
    from utils.weather_utils import preprocess_weather_timestamps
    weather_df_all = preprocess_weather_timestamps(weather_df_all)
    if weather_df_all is None or weather_df_all.empty:
        add_status_message("No valid weather timestamps found after processing", "warning")
        return None

    # 3. Filter by timestamp or date
    weather_df, filter_message = filter_weather_data_by_time(
        weather_df_all, "temperature", selected_timestamp_str, selected_date_str
    )
    
    if weather_df.empty:
        add_status_message(f"No weather data available for selected time filter: {filter_message}", "warning")
        return None
        
    return weather_df

def _prepare_temperature_data(weather_df: pd.DataFrame, region_polygon, min_temp_f: float) -> Optional[gpd.GeoDataFrame]:
    """Process weather data to find unsafe temperatures."""
    # Create GeoDataFrame from the weather data
    weather_gdf = create_weather_geodataframe(weather_df)
    if weather_gdf is None or weather_gdf.empty:
        add_status_message("Failed to convert weather data to GeoDataFrame", "warning")
        return None
        
    # Prepare values for display (convert Kelvin to Celsius first)
    weather_gdf, unit = prepare_display_values(weather_gdf, "temperature")
    
    # Convert Celsius to Fahrenheit for unsafe temperature check
    weather_gdf["temp_f"] = weather_gdf["display_value"] * 9/5 + 32
    
    # Filter weather data by the region
    weather_gdf = weather_gdf[weather_gdf.intersects(region_polygon)].copy()
    
    if weather_gdf.empty:
        add_status_message("No weather data found for region", "warning")
        return None
        
    # Filter only unsafe temperatures (below threshold)
    unsafe_weather_gdf = weather_gdf[weather_gdf["temp_f"] <= min_temp_f].copy()
    
    if unsafe_weather_gdf.empty:
        add_status_message(f"No unsafe temperatures (below {min_temp_f}°F) found in the region", "info")
        return None
    
    add_status_message(f"Found {len(unsafe_weather_gdf)} areas with temperatures below {min_temp_f}°F", "info")
    return unsafe_weather_gdf

def _create_temperature_features(unsafe_weather_gdf: gpd.GeoDataFrame, min_temp_f: float) -> Dict:
    """Create GeoJSON features from the temperature data."""
    # Get min temperature to determine color range
    min_temp = unsafe_weather_gdf["temp_f"].min()
    if pd.isna(min_temp):
        min_temp = min_temp_f - 15
    
    # Add ID column for joining
    unsafe_weather_gdf = unsafe_weather_gdf.reset_index(drop=True)
    unsafe_weather_gdf['id'] = unsafe_weather_gdf.index.astype(str)
    
    # Create a direct mapping from ID to temperature
    temp_data = pd.DataFrame({
        'id': unsafe_weather_gdf['id'],
        'temp_f': unsafe_weather_gdf['temp_f']
    })
    
    # Create a clean GeoJSON with IDs matching the data
    features = []
    for idx, row in unsafe_weather_gdf.iterrows():
        try:
            features.append({
                'type': 'Feature',
                'id': str(idx),  # Use index as ID
                'properties': {
                    'id': str(idx),
                    'temperature': float(row['temp_f'])
                },
                'geometry': row.geometry.__geo_interface__
            })
        except Exception:
            continue
    
    return {
        'features': features,
        'min_temp': min_temp,
        'max_temp': min_temp_f,
        'total_bounds': unsafe_weather_gdf.total_bounds
    }

def _visualize_temperatures(temperature_data: Dict, m: folium.Map) -> None:
    """Visualize temperature data on the map."""
    features = temperature_data['features']
    min_temp = temperature_data['min_temp']
    min_temp_f = temperature_data['max_temp']
    
    if not features:
        return
    
    geo_json = {'type': 'FeatureCollection', 'features': features}
    
    # Create a custom color map with only blue-purple colors for cold temperatures
    # Using darker blues for colder temperatures
    colors = ['#08306b', '#2171b5', '#4292c6', '#6baed6', '#9ecae1', '#c6dbef']
    colormap = LinearColormap(
        colors=colors,
        vmin=min_temp,
        vmax=min_temp_f
    )
    colormap.caption = f"Temperature (°F) below {min_temp_f}°F"
    
    # Add the colormap to the map
    colormap.add_to(m)
    
    # Apply the temperature visualization as a GeoJSON layer with color function
    folium.GeoJson(
        geo_json,
        name="Cold Temperatures",
        style_function=lambda feature: {
            'fillColor': colormap(feature['properties']['temperature']),
            'color': 'black',
            'weight': 0.5,
            'fillOpacity': 0.7
        },
        tooltip=folium.GeoJsonTooltip(
            fields=['temperature'],
            aliases=['Temperature (°F):'],
            style=('background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;')
        ),
        highlight_function=lambda x: {'weight': 3, 'fillOpacity': 0.9}
    ).add_to(m)

def _is_oil_wells_data_available(region_name: str) -> bool:
    """Check if oil wells data is available for the specified region."""
    # Currently, oil wells data is only available for North Dakota
    if region_name.lower() == "north dakota":
        try:
            # Try to load oil wells data to check availability
            oil_wells_gdf = get_oil_wells_data()
            return oil_wells_gdf is not None and not oil_wells_gdf.empty
        except Exception:
            return False
    return False

def _process_oil_wells(region_name: str, selected_date_str: str, unsafe_weather_gdf: gpd.GeoDataFrame) -> Dict:
    """Process oil wells data and calculate affected wells."""
    # Use a cache key to avoid re-loading the oil wells data
    if 'oil_wells_cache' not in st.session_state:
        st.session_state.oil_wells_cache = {}
    
    # Create a hash key based on the region and forecast date
    cache_key = f"{region_name}_{selected_date_str}"
    
    if cache_key in st.session_state.oil_wells_cache:
        # Use cached processed data
        return st.session_state.oil_wells_cache[cache_key]
    
    # Load oil wells data - specific to North Dakota
    oil_wells_gdf = get_oil_wells_data()
    
    if oil_wells_gdf is None or oil_wells_gdf.empty:
        add_status_message("Failed to load oil wells data", "error")
        return {'affected_wells': [], 'normal_wells': [], 'wells_at_risk': 0, 'total_wells': 0}
    
    # Reset index to ensure consistent sampling 
    oil_wells_gdf = oil_wells_gdf.reset_index(drop=True)
    total_wells = len(oil_wells_gdf)
    
    try:
        # Calculate wells in unsafe zones
        unsafe_areas = unsafe_weather_gdf.unary_union
        oil_wells_gdf['in_unsafe_zone'] = oil_wells_gdf.intersects(unsafe_areas)
        wells_at_risk = int(oil_wells_gdf['in_unsafe_zone'].sum())
        
        add_status_message(f"{wells_at_risk} of {total_wells} oil wells affected by unsafe temperatures", "info")
    except Exception:
        # Handle spatial operation failure
        oil_wells_gdf['in_unsafe_zone'] = False
        wells_at_risk = 0
    
    # Extract at-risk wells data
    at_risk_wells = oil_wells_gdf[oil_wells_gdf['in_unsafe_zone'] == True].head(50)
    affected_wells = []
    
    for _, row in at_risk_wells.iterrows():
        if hasattr(row.geometry, 'y') and hasattr(row.geometry, 'x'):
            affected_wells.append((row.geometry.y, row.geometry.x))
    
    # Extract normal wells data - use deterministic selection instead of random sampling
    normal_wells_gdf = oil_wells_gdf[oil_wells_gdf['in_unsafe_zone'] == False]
    # Take evenly spaced wells to ensure consistency
    normal_wells_gdf = normal_wells_gdf.iloc[::max(1, len(normal_wells_gdf) // 20)][:20]
    
    normal_wells = []
    for _, row in normal_wells_gdf.iterrows():
        if hasattr(row.geometry, 'y') and hasattr(row.geometry, 'x'):
            normal_wells.append((row.geometry.y, row.geometry.x))
    
    # Create result dictionary
    result = {
        'affected_wells': affected_wells,
        'normal_wells': normal_wells,
        'wells_at_risk': wells_at_risk,
        'total_wells': total_wells
    }
    
    # Store processed data in cache
    st.session_state.oil_wells_cache[cache_key] = result
    return result

def _visualize_oil_wells(oil_wells_data: Dict, m: folium.Map) -> None:
    """Visualize oil wells on the map."""
    affected_wells = oil_wells_data['affected_wells']
    normal_wells = oil_wells_data['normal_wells']
    
    # Create feature group for wells
    wells_layer = folium.FeatureGroup(name="Oil Wells")
    
    # Draw affected wells
    for lat, lon in affected_wells:
        folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            color='black',
            weight=1,
            fill=True,
            fill_color='red',
            fill_opacity=0.7,
            tooltip="Oil Well (at risk)"
        ).add_to(wells_layer)
    
    # Draw normal wells
    for lat, lon in normal_wells:
        folium.CircleMarker(
            location=[lat, lon],
            radius=3,
            color='black',
            weight=1,
            fill=True,
            fill_color='green',
            fill_opacity=0.7,
            tooltip="Oil Well (normal)"
        ).add_to(wells_layer)
    
    # Add wells layer to map
    wells_layer.add_to(m)
    
    # Add a legend - Using HTML with minimal interactivity
    legend_html = '''
    <div style="position: fixed; 
        bottom: 50px; right: 50px; 
        border:2px solid grey; z-index:9999; font-size:14px;
        background-color: white;
        padding: 10px;
        opacity: 0.8;">
        &nbsp; <span style="color:red">●</span> &nbsp; At-risk Oil Wells <br>
        &nbsp; <span style="color:green">●</span> &nbsp; Normal Oil Wells
    </div>
    '''
    legend_element = folium.Element(legend_html)
    m.get_root().html.add_child(legend_element)

@create_handler
def handle_unsafe_temperature(action: ActionDict, m: folium.Map) -> BoundsList:
    """
    Handle the unsafe_temperature action that shows areas with unsafe cold temperatures
    and overlays oil well data.
    
    Args:
        action: The action dictionary with parameters
        m: The folium map object
        
    Returns:
        List of bounds to include in the overall map fitting
    """
    bounds = []
    
    # Get parameters once - don't modify during rendering
    region_name = action.get("region", "North Dakota")
    min_temp_f = action.get("min_temp_f", 20)
    selected_timestamp_str = action.get("forecast_timestamp")
    selected_date_str = action.get("forecast_date", "2024-12-18")
    show_oil_wells = action.get("show_oil_wells", True)
    
    # Check if oil wells data is available for this region
    oil_wells_available = _is_oil_wells_data_available(region_name)
    if show_oil_wells and not oil_wells_available:
        add_status_message(f"Oil wells data is only available for North Dakota, not for {region_name}", "warning")
        show_oil_wells = False
    
    try:
        # 1. Get region data and add to map
        region_match, region_bounds = _get_region_data(region_name, m)
        if region_match is None:
            return bounds
        
        # Store region bounds for return - ONLY return these bounds
        primary_bounds = region_bounds.copy()
        
        # 2. Get weather data
        weather_df = _get_weather_data(selected_timestamp_str, selected_date_str)
        if weather_df is None:
            return primary_bounds
            
        # 3. Process temperature data
        unsafe_weather_gdf = _prepare_temperature_data(weather_df, region_match.geometry.iloc[0], min_temp_f)
        if unsafe_weather_gdf is None:
            return primary_bounds
        
        # 4. Create temperature features
        temperature_data = _create_temperature_features(unsafe_weather_gdf, min_temp_f)
        
        # 5. Visualize temperatures on map
        _visualize_temperatures(temperature_data, m)
            
        # 6. Process and visualize oil wells if requested and available
        if show_oil_wells and oil_wells_available:
            try:
                oil_wells_data = _process_oil_wells(region_name, selected_date_str, unsafe_weather_gdf)
                _visualize_oil_wells(oil_wells_data, m)
            except Exception as e:
                add_status_message(f"Error displaying oil wells: {str(e)}", "error")
        
        # 7. Add layer control
        folium.LayerControl(position='topright').add_to(m)
        
        # Return ONLY the region bounds for proper zooming
        return primary_bounds
        
    except Exception as e:
        add_status_message(f"Error processing temperature risk data: {str(e)}", "error")
    
    return bounds


def _prepare_high_temperature_data_multi_timestamp(weather_gdf: gpd.GeoDataFrame, region_polygon, max_temp_f: float) -> Optional[gpd.GeoDataFrame]:
    """Process weather data to find dangerous high temperatures across all forecast timestamps."""
    try:
        if weather_gdf is None or weather_gdf.empty:
            add_status_message("No weather data provided for temperature analysis", "warning")
            return None
        
        # Convert Kelvin to Celsius first, then to Fahrenheit
        if 'temperature' in weather_gdf.columns:
            # Temperature is in Kelvin, convert to Celsius then Fahrenheit
            weather_gdf = weather_gdf.copy()
            weather_gdf["temp_celsius"] = weather_gdf["temperature"] - 273.15
            weather_gdf["temp_f"] = weather_gdf["temp_celsius"] * 9/5 + 32
        else:
            add_status_message("Temperature column not found in weather data", "error")
            return None
        
        # Filter only dangerous high temperatures (above threshold)
        high_temp_weather_gdf = weather_gdf[weather_gdf["temp_f"] >= max_temp_f].copy()
        
        if high_temp_weather_gdf.empty:
            add_status_message(f"No dangerous temperatures (above {max_temp_f}°F) found in the region", "info")
            return None
        
        add_status_message(f"Found {len(high_temp_weather_gdf)} weather points with temperatures above {max_temp_f}°F", "info")
        return high_temp_weather_gdf
        
    except Exception as e:
        add_status_message(f"Error processing high temperature data: {str(e)}", "error")
        import traceback
        traceback.print_exc()
        return None


def _prepare_high_temperature_data(weather_df: pd.DataFrame, region_polygon, max_temp_f: float) -> Optional[gpd.GeoDataFrame]:
    """Process weather data to find dangerous high temperatures."""
    # Create GeoDataFrame from the weather data
    weather_gdf = create_weather_geodataframe(weather_df)
    if weather_gdf is None or weather_gdf.empty:
        add_status_message("Failed to convert weather data to GeoDataFrame", "warning")
        return None
        
    # Prepare values for display (convert Kelvin to Celsius first)
    weather_gdf, unit = prepare_display_values(weather_gdf, "temperature")
    
    # Convert Celsius to Fahrenheit for high temperature check
    weather_gdf["temp_f"] = weather_gdf["display_value"] * 9/5 + 32
    
    # Filter weather data by the region
    weather_gdf = weather_gdf[weather_gdf.intersects(region_polygon)].copy()
    
    if weather_gdf.empty:
        add_status_message("No weather data found for region", "warning")
        return None
        
    # Filter only dangerous high temperatures (above threshold)
    high_temp_weather_gdf = weather_gdf[weather_gdf["temp_f"] >= max_temp_f].copy()
    
    if high_temp_weather_gdf.empty:
        add_status_message(f"No dangerous temperatures (above {max_temp_f}°F) found in the region", "info")
        return None
    
    add_status_message(f"Found {len(high_temp_weather_gdf)} areas with temperatures above {max_temp_f}°F", "info")
    return high_temp_weather_gdf


def _create_high_temperature_features(high_temp_weather_gdf: gpd.GeoDataFrame, max_temp_f: float) -> Dict:
    """Create GeoJSON features from the high temperature data."""
    # Get max temperature to determine color range
    max_temp = high_temp_weather_gdf["temp_f"].max()
    if pd.isna(max_temp):
        max_temp = max_temp_f + 15
    
    # Add ID column for joining
    high_temp_weather_gdf = high_temp_weather_gdf.reset_index(drop=True)
    high_temp_weather_gdf['id'] = high_temp_weather_gdf.index.astype(str)
    
    # Create a direct mapping from ID to temperature
    temp_data = pd.DataFrame({
        'id': high_temp_weather_gdf['id'],
        'temp_f': high_temp_weather_gdf['temp_f']
    })
    
    # Create a clean GeoJSON with IDs matching the data
    features = []
    for idx, row in high_temp_weather_gdf.iterrows():
        try:
            features.append({
                'type': 'Feature',
                'id': str(idx),  # Use index as ID
                'properties': {
                    'id': str(idx),
                    'temperature': float(row['temp_f'])
                },
                'geometry': row.geometry.__geo_interface__
            })
        except Exception:
            continue
    
    return {
        'features': features,
        'min_temp': max_temp_f,
        'max_temp': max_temp,
        'total_bounds': high_temp_weather_gdf.total_bounds
    }


def _visualize_high_temperatures(temperature_data: Dict, m: folium.Map) -> None:
    """Visualize high temperature data on the map."""
    features = temperature_data['features']
    min_temp_f = temperature_data['min_temp']
    max_temp = temperature_data['max_temp']
    
    if not features:
        return
    
    geo_json = {'type': 'FeatureCollection', 'features': features}
    
    # Create a custom color map with red-orange colors for hot temperatures
    # Using darker reds for hotter temperatures
    colors = ['#fee5d9', '#fcbba1', '#fc9272', '#fb6a4a', '#ef3b2c', '#cb181d', '#99000d']
    colormap = LinearColormap(
        colors=colors,
        vmin=min_temp_f,
        vmax=max_temp
    )
    colormap.caption = f"Temperature (°F) above {min_temp_f}°F"
    
    # Add the colormap to the map
    colormap.add_to(m)
    
    # Apply the temperature visualization as a GeoJSON layer with color function
    folium.GeoJson(
        geo_json,
        name="High Temperatures",
        style_function=lambda feature: {
            'fillColor': colormap(feature['properties']['temperature']),
            'color': 'black',
            'weight': 0.5,
            'fillOpacity': 0.7
        },
        tooltip=folium.GeoJsonTooltip(
            fields=['temperature'],
            aliases=['Temperature (°F):'],
            style=('background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;')
        ),
        highlight_function=lambda x: {'weight': 3, 'fillOpacity': 0.9}
    ).add_to(m)


def _process_power_lines_high_temp(region_polygon, high_temp_weather_gdf: gpd.GeoDataFrame) -> Dict:
    """Process power lines data and calculate affected lines by high temperature."""
    try:
        # Load power lines data
        power_lines_gdf = get_us_power_lines(use_geojson=True)
        
        if power_lines_gdf is None or power_lines_gdf.empty:
            add_status_message("Failed to load power lines data", "error")
            return {'affected_lines': [], 'normal_lines': [], 'lines_at_risk': 0, 'total_lines': 0}
        
        # Filter power lines to the region
        power_lines_gdf = power_lines_gdf[power_lines_gdf.intersects(region_polygon)].copy()
        
        if power_lines_gdf.empty:
            add_status_message("No power lines found in the region", "warning")
            return {'affected_lines': [], 'normal_lines': [], 'lines_at_risk': 0, 'total_lines': 0}
        
        # Reset index to ensure consistent sampling 
        power_lines_gdf = power_lines_gdf.reset_index(drop=True)
        total_lines = len(power_lines_gdf)
        
        # Calculate power lines in high temperature zones
        high_temp_areas = high_temp_weather_gdf.unary_union
        power_lines_gdf['in_high_temp_zone'] = power_lines_gdf.intersects(high_temp_areas)
        lines_at_risk = int(power_lines_gdf['in_high_temp_zone'].sum())
        
        add_status_message(f"{lines_at_risk} of {total_lines} power line points affected by high temperatures", "info")
        
        # Extract at-risk power lines data
        at_risk_lines = power_lines_gdf[power_lines_gdf['in_high_temp_zone'] == True].head(100)
        affected_lines = []
        
        for _, row in at_risk_lines.iterrows():
            if hasattr(row.geometry, 'y') and hasattr(row.geometry, 'x'):
                affected_lines.append((row.geometry.y, row.geometry.x))
        
        # Extract normal power lines data - use deterministic selection
        normal_lines_gdf = power_lines_gdf[power_lines_gdf['in_high_temp_zone'] == False]
        # Take evenly spaced lines to ensure consistency
        normal_lines_gdf = normal_lines_gdf.iloc[::max(1, len(normal_lines_gdf) // 50)][:50]
        
        normal_lines = []
        for _, row in normal_lines_gdf.iterrows():
            if hasattr(row.geometry, 'y') and hasattr(row.geometry, 'x'):
                normal_lines.append((row.geometry.y, row.geometry.x))
        
        return {
            'affected_lines': affected_lines,
            'normal_lines': normal_lines,
            'lines_at_risk': lines_at_risk,
            'total_lines': total_lines
        }
        
    except Exception as e:
        add_status_message(f"Error processing power lines: {str(e)}", "error")
        return {'affected_lines': [], 'normal_lines': [], 'lines_at_risk': 0, 'total_lines': 0}


def _visualize_power_lines_high_temp(power_lines_data: Dict, m: folium.Map) -> None:
    """Visualize power lines on the map for high temperature risk."""
    affected_lines = power_lines_data['affected_lines']
    normal_lines = power_lines_data['normal_lines']
    
    # Create feature group for power lines
    lines_layer = folium.FeatureGroup(name="Power Lines")
    
    # Draw affected power lines
    for lat, lon in affected_lines:
        folium.CircleMarker(
            location=[lat, lon],
            radius=4,
            color='black',
            weight=1,
            fill=True,
            fill_color='red',
            fill_opacity=0.8,
            tooltip="Power Line (at risk from heat)"
        ).add_to(lines_layer)
    
    # Draw normal power lines
    for lat, lon in normal_lines:
        folium.CircleMarker(
            location=[lat, lon],
            radius=2,
            color='black',
            weight=1,
            fill=True,
            fill_color='blue',
            fill_opacity=0.6,
            tooltip="Power Line (normal)"
        ).add_to(lines_layer)
    
    # Add lines layer to map
    lines_layer.add_to(m)
    
    # Add a legend
    legend_html = '''
    <div style="position: fixed; 
        bottom: 50px; right: 50px; 
        border:2px solid grey; z-index:9999; font-size:14px;
        background-color: white;
        padding: 10px;
        opacity: 0.8;">
        &nbsp; <span style="color:red">●</span> &nbsp; Power Lines at Risk (High Temp) <br>
        &nbsp; <span style="color:blue">●</span> &nbsp; Normal Power Lines
    </div>
    '''
    legend_element = folium.Element(legend_html)
    m.get_root().html.add_child(legend_element)


@create_handler
def handle_high_temperature_risk(action: ActionDict, m: folium.Map) -> BoundsList:
    """
    Handle the high_temperature_risk action that shows areas with dangerous high temperatures
    and overlays power line data to show lines at risk of sag and faults.
    
    Args:
        action: The action dictionary with parameters
        m: The folium map object
        
    Returns:
        List of bounds to include in the overall map fitting
    """
    bounds = []
    
    try:
        # Extract and validate parameters (similar to wind risk)
        region_name = action.get("region", "Texas")
        max_temp_f = action.get("max_temp_f", 95)
        forecast_days = action.get("forecast_days", 3)
        init_date = action.get("init_date")
        analyze_power_lines = action.get("analyze_power_lines", True)
        
        if not region_name:
            add_status_message("Region parameter is required for high temperature risk analysis.", "error")
            return bounds
        
        add_status_message(f"Analyzing high temperature risk to power lines in {region_name} over the next {forecast_days} day(s) (threshold >= {max_temp_f}°F)...", "info")
        
        # 1. Load weather data for forecast period (like wind risk)
        from services.risk_analyzer.data_loading import load_weather_data, find_and_add_region_to_map, filter_weather_by_region
        
        weather_df = load_weather_data(forecast_days)
        if weather_df is None or weather_df.empty:
            add_status_message("No weather data available for high temperature risk analysis.", "warning")
            return bounds
        
        # 2. Find and add region to the map
        region_result = find_and_add_region_to_map(region_name, m)
        if not region_result["success"]:
            return bounds
            
        bounds.append(region_result["bounds"])
        region_polygon = region_result["polygon"]
        
        # 3. Filter weather data by region
        weather_gdf = filter_weather_by_region(weather_df, region_polygon)
        if weather_gdf.empty:
            add_status_message(f"No weather data points found within {region_name}.", "warning")
            return bounds
        
        # 4. Process high temperature data (analyze all forecast timestamps)
        high_temp_weather_gdf = _prepare_high_temperature_data_multi_timestamp(weather_gdf, region_polygon, max_temp_f)
        if high_temp_weather_gdf is None or high_temp_weather_gdf.empty:
            add_status_message(f"No dangerous temperatures (above {max_temp_f}°F) found in {region_name} for the forecast period.", "info")
            return bounds
        
        # 5. Create temperature features
        temperature_data = _create_high_temperature_features(high_temp_weather_gdf, max_temp_f)
        
        # 6. Visualize temperatures on map
        _visualize_high_temperatures(temperature_data, m)
            
        # 7. Process and visualize power lines if requested
        if analyze_power_lines:
            try:
                power_lines_data = _process_power_lines_high_temp(region_polygon, high_temp_weather_gdf)
                _visualize_power_lines_high_temp(power_lines_data, m)
            except Exception as e:
                add_status_message(f"Error displaying power lines: {str(e)}", "error")
        
        # 8. Add layer control
        folium.LayerControl(position='topright').add_to(m)
        
        # Return the region bounds for proper zooming
        return bounds
        
    except Exception as e:
        add_status_message(f"Error processing high temperature risk data: {str(e)}", "error")
        import traceback
        traceback.print_exc()
    
    return bounds 
