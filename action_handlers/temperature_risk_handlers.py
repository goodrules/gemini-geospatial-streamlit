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
from utils.geo_utils import find_region_by_name
from data.geospatial_data import get_us_states

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
        oil_wells_path = "data/local/north_dakota_oil_wells.geojson"
        return os.path.exists(oil_wells_path)
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
    oil_wells_path = "data/local/north_dakota_oil_wells.geojson"
    oil_wells_gdf = gpd.read_file(oil_wells_path)
    
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
