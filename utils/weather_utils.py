import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely import wkt
from utils.streamlit_utils import add_status_message
from utils.geo_utils import find_region_by_name

def format_timestamp_utc(timestamp_obj):
    """
    Format a timestamp object to a standard UTC string format
    
    Args:
        timestamp_obj: A datetime or timestamp object
        
    Returns:
        String formatted as 'YYYY-MM-DD HH:MM UTC'
    """
    if timestamp_obj is None:
        return "N/A"
    
    try:
        # Ensure timestamp is timezone aware with UTC
        if timestamp_obj.tzinfo is None:
            timestamp_obj = timestamp_obj.tz_localize('UTC')
        else:
            timestamp_obj = timestamp_obj.tz_convert('UTC')
        return timestamp_obj.strftime('%Y-%m-%d %H:%M UTC')
    except Exception:
        return str(timestamp_obj)

def preprocess_weather_timestamps(weather_df):
    """
    Ensure forecast_time is in proper datetime format with UTC timezone
    
    Args:
        weather_df: DataFrame containing weather data
        
    Returns:
        Processed DataFrame with proper timezone-aware timestamps
    """
    if 'forecast_time' not in weather_df.columns:
        st.error("Weather data is missing the 'forecast_time' column.")
        return None
    
    try:
        weather_df_copy = weather_df.copy()
        weather_df_copy['forecast_time'] = pd.to_datetime(weather_df_copy['forecast_time'], errors='coerce')
        
        # Ensure UTC
        if weather_df_copy['forecast_time'].dt.tz is None:
            weather_df_copy['forecast_time'] = weather_df_copy['forecast_time'].dt.tz_localize('UTC')
        else:
            weather_df_copy['forecast_time'] = weather_df_copy['forecast_time'].dt.tz_convert('UTC')
            
        weather_df_copy.dropna(subset=['forecast_time'], inplace=True)
        return weather_df_copy
    except Exception as e:
        st.error(f"Error processing forecast timestamps in weather data: {e}")
        return None

def create_weather_geodataframe(weather_df):
    """
    Convert weather DataFrame with WKT geography_polygon to GeoDataFrame
    
    Args:
        weather_df: DataFrame containing weather data with geography_polygon column
        
    Returns:
        GeoDataFrame with valid geometries
    """
    # Pre-filter for potentially valid polygon strings
    valid_polygon_mask = weather_df['geography_polygon'].notna() & \
                         weather_df['geography_polygon'].apply(lambda x: isinstance(x, str) and x.strip() != '')
    weather_df_potential = weather_df[valid_polygon_mask].copy()

    if weather_df_potential.empty:
        st.warning("No rows with potentially valid polygon strings found in the filtered weather data.")
        return None

    geometries = []
    valid_indices = []
    shape_errors = 0

    # Iterate only over rows with potential polygons
    for index, row in weather_df_potential.iterrows():
        polygon_wkt = row['geography_polygon']  # Expecting WKT string
        try:
            # Use shapely.wkt.loads to parse the WKT string directly
            polygon = wkt.loads(polygon_wkt)
            if polygon.is_valid:  # Check validity after loading
                geometries.append(polygon)
                valid_indices.append(index)  # Store index of successfully processed row
            else:
                shape_errors += 1
        except Exception as wkt_error:  # Catch errors during WKT loading or validation
            shape_errors += 1  # Increment error count
            st.warning(f"WKT processing error for index {index}: {wkt_error}. Failing WKT: '{polygon_wkt[:100]}...'")

    # Report errors if any occurred
    if shape_errors > 0:
        st.warning(f"Skipped {shape_errors} rows due to invalid/failed WKT geometry processing.")

    # If no valid geometries were created after parsing
    if not valid_indices:
        st.warning("Failed to create any valid geometries from the available polygon data.")
        return None

    # Select the original data rows that corresponded to valid geometries
    weather_df_valid = weather_df_potential.loc[valid_indices]

    # Create the GeoDataFrame - lengths should now match
    weather_gdf = gpd.GeoDataFrame(
        weather_df_valid,
        geometry=geometries,  # List of valid shapely geometries
        crs="EPSG:4326"
    )

    return weather_gdf

def create_city_buffer(lat, lon, buffer_km=20):
    """
    Creates a circular buffer around a city's coordinates
    
    This function approximates a buffer in geographic coordinates,
    which is useful when we need to filter weather data near a city.
    The approximation converts kilometers to degrees using a rough
    estimate that 1 degree equals 111 km at the equator.
    
    Note that this is an approximation as the actual distance represented 
    by 1 degree varies with latitude.
    
    Args:
        lat: Latitude of the city center
        lon: Longitude of the city center
        buffer_km: Buffer radius in kilometers (default: 20km)
        
    Returns:
        A shapely geometry representing the buffer area
    """
    # Convert km to approximate degrees (very rough estimate)
    # 1 degree ≈ 111 km at the equator, but varies with latitude
    buffer_deg = buffer_km / 111.0
    city_point = Point(lon, lat)
    return city_point.buffer(buffer_deg)

def find_location_geometry(location, states_gdf, counties_gdf, cities_df):
    """
    Find geometry for a location name from states, counties, or cities
    
    Args:
        location: String location name to search for
        states_gdf: GeoDataFrame of states
        counties_gdf: GeoDataFrame of counties
        cities_df: DataFrame of cities with lat/lon coordinates
        
    Returns:
        Tuple of (geometry, location_name, location_type) or (None, None, None) if not found
    """
    # Clean up location string for better matching
    clean_location = location.lower()
    
    # Remove common words that might interfere with matching
    for word in ["county", "parish", "borough", "city", "town", "township", "state of", "commonwealth of"]:
        clean_location = clean_location.replace(word, "").strip()
        
    # Remove any trailing commas and whitespace
    clean_location = clean_location.rstrip(",").strip()
    
    # 1. Try to match with a state
    state_match = find_region_by_name(states_gdf, clean_location)
    if state_match is not None and len(state_match) > 0:
        state_name = state_match['state_name'].iloc[0]
        add_status_message(f"Filtering weather data for state: {state_name}", "info")
        return state_match.unary_union, state_name, "state"
    
    # 2. If not a state, try to match with a county
    county_match = find_region_by_name(counties_gdf, clean_location)
    if county_match is not None and len(county_match) > 0:
        county_name = county_match['county_name'].iloc[0]
        add_status_message(f"Filtering weather data for county: {county_name}", "info")
        return county_match.unary_union, county_name, "county"
    
    # 3. If not a county, try to match with a major city
    # Try exact match first
    city_match = cities_df[cities_df['name'].str.lower() == clean_location]
    
    # If no exact match, try partial match
    if len(city_match) == 0:
        city_match = cities_df[cities_df['name'].str.lower().str.contains(clean_location)]
        
    if len(city_match) > 0:
        city_name = city_match['name'].iloc[0]
        city_lat = city_match['lat'].iloc[0]
        city_lon = city_match['lon'].iloc[0]
        add_status_message(f"Filtering weather data for city: {city_name}", "info")
        
        # Create a buffer around the city point
        buffer = create_city_buffer(city_lat, city_lon)
        return buffer, city_name, "city"
    
    return None, None, None

def prepare_display_values(weather_gdf, parameter):
    """
    Add display value and unit based on the parameter
    
    Args:
        weather_gdf: GeoDataFrame with weather data
        parameter: Weather parameter (temperature, precipitation, wind_speed)
        
    Returns:
        Tuple of (weather_gdf with display_value column, unit string)
    """
    if parameter == "temperature":
        # Convert from Kelvin to Celsius for display
        if 'temperature' in weather_gdf.columns:
            weather_gdf.loc[:, 'display_value'] = weather_gdf['temperature'] - 273.15
        else:
            # Log that temperature column is missing
            st.warning("Temperature column not found in weather data")
            weather_gdf.loc[:, 'display_value'] = 0
        unit = "°C"
    elif parameter == "precipitation":
        # Convert to mm
        weather_gdf.loc[:, 'display_value'] = weather_gdf['precipitation'] * 1000  # m to mm
        unit = "mm"
    elif parameter == "wind_speed":
        weather_gdf.loc[:, 'display_value'] = weather_gdf['wind_speed']
        unit = "m/s"
    else:
        weather_gdf.loc[:, 'display_value'] = weather_gdf[parameter]
        unit = ""
    
    # Add a formatted string column for the tooltip
    try:
        if pd.api.types.is_datetime64_any_dtype(weather_gdf['forecast_time']):
            weather_gdf.loc[:, 'forecast_time_str'] = weather_gdf['forecast_time'].dt.strftime('%Y-%m-%d %H:%M')
        else:
            weather_gdf.loc[:, 'forecast_time_str'] = 'Invalid Time'
    except AttributeError:  # Catch potential errors if column is missing or not datetime-like
        weather_gdf.loc[:, 'forecast_time_str'] = 'Invalid Time'
    
    return weather_gdf, unit

def filter_weather_by_timestamp(weather_df, timestamp_str):
    """
    Filter weather data by a specific timestamp
    
    Args:
        weather_df: DataFrame containing weather data
        timestamp_str: String timestamp to filter by
        
    Returns:
        Filtered DataFrame and message describing the filter
    """
    try:
        selected_timestamp_obj = pd.to_datetime(timestamp_str)
        if selected_timestamp_obj.tzinfo is None:
            selected_timestamp_obj = selected_timestamp_obj.tz_localize('UTC')
        else:
            selected_timestamp_obj = selected_timestamp_obj.tz_convert('UTC')

        filtered_df = weather_df[weather_df['forecast_time'] == selected_timestamp_obj].copy()
        filter_message = f"for timestamp: {selected_timestamp_obj.strftime('%Y-%m-%d %H:%M UTC')}"
        return filtered_df, filter_message
    except Exception as e:
        st.error(f"Invalid timestamp format provided: {timestamp_str}. Error: {e}")
        return pd.DataFrame(), ""

def filter_weather_by_date(weather_df, date_str, parameter):
    """
    Filter weather data by date, selecting MAX value of parameter per location
    
    Args:
        weather_df: DataFrame containing weather data
        date_str: String date to filter by ('YYYY-MM-DD')
        parameter: Weather parameter to maximize
        
    Returns:
        Filtered DataFrame and message describing the filter
    """
    try:
        selected_date_obj = pd.to_datetime(date_str).date()
        daily_data = weather_df[weather_df['forecast_time'].dt.date == selected_date_obj].copy()

        if not daily_data.empty:
            # Group by location polygon and find index of max parameter value within each group
            idx = daily_data.groupby('geography_polygon')[parameter].idxmax()
            filtered_df = daily_data.loc[idx]
            filter_message = f"showing MAX {parameter} for date: {selected_date_obj.strftime('%Y-%m-%d')}"
            st.info(f"No specific time provided. Displaying the maximum '{parameter}' value for each location on {selected_date_obj.strftime('%Y-%m-%d')}.")
        else:
            filtered_df = pd.DataFrame()
            filter_message = f"for date: {selected_date_obj.strftime('%Y-%m-%d')}"

        return filtered_df, filter_message
    except ValueError:
        st.error(f"Invalid date format provided: {date_str}. Please use YYYY-MM-DD.")
        return pd.DataFrame(), ""

def filter_weather_by_latest_date(weather_df, parameter):
    """
    Filter weather data by the latest available date, selecting MAX value per location
    
    Args:
        weather_df: DataFrame containing weather data
        parameter: Weather parameter to maximize
        
    Returns:
        Filtered DataFrame and message describing the filter
    """
    if not weather_df.empty:
        latest_date = weather_df['forecast_time'].dt.date.max()
        st.info(f"No date or time provided. Using latest available date: {latest_date.strftime('%Y-%m-%d')}")
        daily_data = weather_df[weather_df['forecast_time'].dt.date == latest_date].copy()

        if not daily_data.empty:
            # Group by location polygon and find index of max parameter value
            idx = daily_data.groupby('geography_polygon')[parameter].idxmax()
            filtered_df = daily_data.loc[idx]
            filter_message = f"showing MAX {parameter} for latest date: {latest_date.strftime('%Y-%m-%d')}"
            st.info(f"Displaying the maximum '{parameter}' value for each location on the latest available date ({latest_date.strftime('%Y-%m-%d')}).")
        else:
            filtered_df = pd.DataFrame()
            filter_message = f"for latest date: {latest_date.strftime('%Y-%m-%d')}"
    else:
        filtered_df = pd.DataFrame()
        filter_message = "as no data was found"
        
    return filtered_df, filter_message 
