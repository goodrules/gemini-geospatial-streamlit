import streamlit as st
import pandas as pd
import json
import geopandas as gpd
from datetime import date # Ensure date is imported
from shapely.geometry import shape, Point
from shapely import wkt # Import wkt loading function
from branca.colormap import LinearColormap
import folium
from data.weather_data import get_weather_forecast_data
from utils.geo_utils import find_region_by_name, get_major_cities
from services.map_core import serialize_geojson
from utils.streamlit_utils import add_status_message

def create_weather_tooltip(properties, parameter=None):
    """
    Create HTML tooltip for weather data with improved formatting and contextual information
    
    Args:
        properties: Dictionary of properties from the GeoJSON feature
        parameter: Optional specific parameter to highlight (temperature, precipitation, wind_speed)
        
    Returns:
        HTML string for the tooltip
    """
    # Convert temperature from Kelvin to both Fahrenheit and Celsius
    temp_f = None
    temp_c = None
    if "temperature" in properties:
        temp_k = float(properties["temperature"])
        temp_c = temp_k - 273.15
        temp_f = temp_c * 9/5 + 32
    
    # Format precipitation as mm and add context
    precip = None
    precip_desc = "None"
    if "precipitation" in properties:
        precip = float(properties["precipitation"]) * 1000  # Convert to mm
        # Add precipitation description
        if precip < 0.1:
            precip_desc = "None"
        elif precip < 2.5:
            precip_desc = "Very Light"
        elif precip < 7.5:
            precip_desc = "Light"
        elif precip < 15:
            precip_desc = "Moderate"
        elif precip < 30:
            precip_desc = "Heavy"
        else:
            precip_desc = "Very Heavy"
    
    # Format wind speed (m/s and mph) and add context
    wind = None
    wind_mph = None
    wind_desc = ""
    if "wind_speed" in properties:
        wind = float(properties["wind_speed"])
        wind_mph = wind * 2.237  # Convert to mph
        # Add wind description based on Beaufort scale (simplified)
        if wind < 0.5:
            wind_desc = "Calm"
        elif wind < 1.5:
            wind_desc = "Light Air"
        elif wind < 3.3:
            wind_desc = "Light Breeze"
        elif wind < 5.5:
            wind_desc = "Gentle Breeze"
        elif wind < 7.9:
            wind_desc = "Moderate Breeze"
        elif wind < 10.7:
            wind_desc = "Fresh Breeze"
        elif wind < 13.8:
            wind_desc = "Strong Breeze"
        elif wind < 17.1:
            wind_desc = "High Wind"
        else:
            wind_desc = "Gale Force"
    
    # Create tooltip with available data
    location_info = ""
    if "location_name" in properties:
        location_info = f"<h5>{properties['location_name']}</h5>"
    
    # Base tooltip HTML
    tooltip_html = f"""
    <div style="min-width: 220px; max-width: 300px; padding: 10px;">
        <h4 style="margin-top: 0; border-bottom: 1px solid #ccc; padding-bottom: 5px;">
            Weather Forecast
        </h4>
        {location_info}
        <p><b>Time (UTC):</b> {pd.to_datetime(properties.get("forecast_time")).strftime('%Y-%m-%d %H:%M') if properties.get("forecast_time") else "N/A"}</p>
    """

    # Add weather data based on what's available
    if temp_f is not None:
        highlight = ' style="background-color: #FFFF99;"' if parameter == "temperature" else ""
        tooltip_html += f'<p{highlight}><b>Temperature:</b> {temp_f:.1f}°F ({temp_c:.1f}°C)</p>'
    
    if precip is not None:
        highlight = ' style="background-color: #FFFF99;"' if parameter == "precipitation" else ""
        tooltip_html += f'<p{highlight}><b>Precipitation:</b> {precip:.2f} mm ({precip_desc})</p>'
    
    if wind is not None:
        highlight = ' style="background-color: #FFFF99;"' if parameter == "wind_speed" else ""
        tooltip_html += f'<p{highlight}><b>Wind Speed:</b> {wind:.1f} m/s ({wind_mph:.1f} mph)<br/><i>{wind_desc}</i></p>'
    
    tooltip_html += """
        <div style="font-size: 0.8em; margin-top: 10px; color: #666;">
            Click for more details
        </div>
    </div>
    """
    
    return tooltip_html

def get_weather_color_scale(parameter, min_val, max_val):
    """Define color scales for different weather parameters"""
    if parameter == "temperature":
        # Temperature color scale (Kelvin values)
        # Colors from cool blue to hot red
        return LinearColormap(
            ['#0000ff', '#00ffff', '#00ff00', '#ffff00', '#ff0000'],
            vmin=min_val,  # ~15°F
            vmax=max_val,  # ~55°F
        )
    elif parameter == "precipitation":
        # Precipitation color scale (mm)
        # Colors from white/pale blue (low) to dark blue (high)
        return LinearColormap(
            ['#ffffff', '#c6dbef', '#9ecae1', '#6baed6', '#3182bd', '#08519c'],
            vmin=min_val,
            vmax=max_val,  # Adjust based on actual precipitation values
        )
    elif parameter == "wind_speed":
        # Wind speed color scale (m/s)
        # Colors from white/pale green (low) to dark green (high)
        return LinearColormap(
            ['#ffffff', '#c7e9c0', '#a1d99b', '#74c476', '#31a354', '#006d2c'],
            vmin=min_val,
            vmax=max_val,  # Adjust based on actual wind speed values
        )
    elif parameter == "wind_risk":
        # Wind risk color scale (special scale for risk assessment)
        # Orange-red scale to indicate severity
        return LinearColormap(
            ['#fee8c8', '#fdbb84', '#e34a33'], 
            vmin=0,
            vmax=100,  # Risk percentage 
        )
    else:
        # Default color scale
        return LinearColormap(
            ['#ffffff', '#bbbbbb', '#777777', '#444444', '#000000'],
            vmin=0,
            vmax=100,
        )

def handle_show_weather(action, m):
    """
    Handle the show_weather action
    
    Args:
        action: The action dictionary with parameters
        m: The folium map object
        
    Returns:
        List of bounds to include in the overall map fitting
    """
    bounds = []
    
    # Get parameters
    parameter = action.get("parameter", "temperature")  # Default to temperature
    selected_timestamp_str = action.get("forecast_timestamp") # Expecting full timestamp string
    selected_date_str = action.get("forecast_date") # Fallback: Expecting "YYYY-MM-DD"
    location = action.get("location")  # Optional location filter

    try:
        # 1. Get all weather forecast data for the selected init_date
        selected_init_date = st.session_state.get("selected_init_date", date.today()) # Get selected init_date, default to today
        
        # Generate the simplified query for display in the spinner
        from data.weather_data import get_weather_query
        _, init_date_str = get_weather_query(selected_init_date)
        simplified_query = f"SELECT weather.init_time, geography, forecast_time, temperature, precipitation, wind_speed FROM weathernext_graph_forecasts WHERE init_time = '{init_date_str}'"
        
        # Fetch the data with a spinner showing the query
        with st.spinner(f"Executing: {simplified_query}"):
            weather_df_all = get_weather_forecast_data(selected_init_date)

        if weather_df_all is None or weather_df_all.empty:
            add_status_message("No weather data available", "warning")
            return bounds

        # Ensure forecast_time is datetime before proceeding
        if 'forecast_time' not in weather_df_all.columns:
             st.error("Weather data is missing the 'forecast_time' column.")
             return bounds
        try:
            weather_df_all['forecast_time'] = pd.to_datetime(weather_df_all['forecast_time'], errors='coerce')
            # Ensure UTC
            if weather_df_all['forecast_time'].dt.tz is None:
                 weather_df_all['forecast_time'] = weather_df_all['forecast_time'].dt.tz_localize('UTC')
            else:
                 weather_df_all['forecast_time'] = weather_df_all['forecast_time'].dt.tz_convert('UTC')
            weather_df_all.dropna(subset=['forecast_time'], inplace=True)
        except Exception as e:
            st.error(f"Error processing forecast timestamps in weather data: {e}")
            return bounds

        if weather_df_all.empty:
            st.warning("No valid weather timestamps found after processing.")
            return bounds

        # Store min/max values for color scale (use the full dataset before date filtering)
        if parameter not in weather_df_all.columns:
             st.error(f"Selected parameter '{parameter}' not found in weather data.")
             return bounds
        min_val = weather_df_all[parameter].min()
        max_val = weather_df_all[parameter].max()

        # 2. Filter by forecast timestamp, date (with max value), or latest date (with max value)
        weather_df_filtered = pd.DataFrame() # Initialize empty DataFrame
        filter_applied_message = "" # Initialize message

        if selected_timestamp_str:
            # --- Filter by specific timestamp ---
            try:
                selected_timestamp_obj = pd.to_datetime(selected_timestamp_str)
                if selected_timestamp_obj.tzinfo is None:
                    selected_timestamp_obj = selected_timestamp_obj.tz_localize('UTC')
                else:
                    selected_timestamp_obj = selected_timestamp_obj.tz_convert('UTC')

                weather_df_filtered = weather_df_all[weather_df_all['forecast_time'] == selected_timestamp_obj].copy()
                filter_applied_message = f"for timestamp: {selected_timestamp_obj.strftime('%Y-%m-%d %H:%M UTC')}"
            except Exception as e:
                st.error(f"Invalid timestamp format provided: {selected_timestamp_str}. Error: {e}")
                return bounds
        elif selected_date_str:
            # --- Filter by date, selecting MAX value per location ---
            try:
                selected_date_obj = pd.to_datetime(selected_date_str).date()
                daily_data = weather_df_all[weather_df_all['forecast_time'].dt.date == selected_date_obj].copy()

                if not daily_data.empty:
                    # Group by location polygon and find index of max parameter value within each group
                    idx = daily_data.groupby('geography_polygon')[parameter].idxmax()
                    weather_df_filtered = daily_data.loc[idx]
                    filter_applied_message = f"showing MAX {parameter} for date: {selected_date_obj.strftime('%Y-%m-%d')}"
                    st.info(f"No specific time provided. Displaying the maximum '{parameter}' value for each location on {selected_date_obj.strftime('%Y-%m-%d')}.")
                else:
                    filter_applied_message = f"for date: {selected_date_obj.strftime('%Y-%m-%d')}" # No data found msg

            except ValueError:
                st.error(f"Invalid date format provided: {selected_date_str}. Please use YYYY-MM-DD.")
                return bounds
        else:
            # --- Filter by LATEST date, selecting MAX value per location ---
            if not weather_df_all.empty:
                latest_date = weather_df_all['forecast_time'].dt.date.max()
                st.info(f"No date or time provided. Using latest available date: {latest_date.strftime('%Y-%m-%d')}")
                daily_data = weather_df_all[weather_df_all['forecast_time'].dt.date == latest_date].copy()

                if not daily_data.empty:
                    # Group by location polygon and find index of max parameter value
                    idx = daily_data.groupby('geography_polygon')[parameter].idxmax()
                    weather_df_filtered = daily_data.loc[idx]
                    filter_applied_message = f"showing MAX {parameter} for latest date: {latest_date.strftime('%Y-%m-%d')}"
                    st.info(f"Displaying the maximum '{parameter}' value for each location on the latest available date ({latest_date.strftime('%Y-%m-%d')}).")
                else:
                     filter_applied_message = f"for latest date: {latest_date.strftime('%Y-%m-%d')}" # No data found msg
            else:
                 filter_applied_message = "as no data was found" # Overall empty data case

        # Check if filtering resulted in empty dataframe
        if weather_df_filtered.empty:
            st.warning(f"No weather data available {filter_applied_message}")
            return bounds

        # 3. Convert filtered data to GeoDataFrame, handling geometry errors robustly

        # Pre-filter for potentially valid polygon strings
        valid_polygon_mask = weather_df_filtered['geography_polygon'].notna() & \
                             weather_df_filtered['geography_polygon'].apply(lambda x: isinstance(x, str) and x.strip() != '')
        weather_df_potential = weather_df_filtered[valid_polygon_mask].copy()

        if weather_df_potential.empty:
            st.warning("No rows with potentially valid polygon strings found in the filtered weather data.")
            return bounds

        geometries = []
        valid_indices = []
        parse_errors = 0
        shape_errors = 0

        # Iterate only over rows with potential polygons
        for index, row in weather_df_potential.iterrows():
            polygon_wkt = row['geography_polygon'] # Expecting WKT string
            try:
                # Use shapely.wkt.loads to parse the WKT string directly
                polygon = wkt.loads(polygon_wkt)
                if polygon.is_valid: # Check validity after loading
                    geometries.append(polygon)
                    valid_indices.append(index) # Store index of successfully processed row
                else:
                    shape_errors += 1
                    # Optional: st.warning(f"Invalid geometry created from WKT for index {index}")
            except Exception as wkt_error: # Catch errors during WKT loading or validation
                shape_errors += 1 # Increment error count
                # Display the failing WKT string and the error for diagnosis
                st.warning(f"WKT processing error for index {index}: {wkt_error}. Failing WKT: '{polygon_wkt[:100]}...'") # Show start of WKT
                pass # Add pass to make the except block valid

        # Report errors if any occurred
        if shape_errors > 0:
             st.warning(f"Skipped {shape_errors} rows due to invalid/failed WKT geometry processing.") # Corrected message

        # If no valid geometries were created after parsing
        if not valid_indices:
             st.warning("Failed to create any valid geometries from the available polygon data.")
             return bounds

        # Select the original data rows that corresponded to valid geometries
        weather_df_valid = weather_df_potential.loc[valid_indices]

        # Create the GeoDataFrame - lengths should now match
        weather_gdf = gpd.GeoDataFrame(
            weather_df_valid,
            geometry=geometries, # List of valid shapely geometries
            crs="EPSG:4326"
        )

        # Double-check if GeoDataFrame is empty after creation (shouldn't be if valid_indices is not empty)
        if weather_gdf.empty:
            st.warning("Could not create geometry from weather data")
            return bounds
            
        # 4. Location-based filtering (if location specified)
        if location:
            try:
                # Get geospatial datasets for location matching
                from data.geospatial_data import get_us_states, get_us_counties
                states_gdf = get_us_states()
                counties_gdf = get_us_counties()
                cities = get_major_cities()
                
                # Initialize a geometry to use for filtering
                filter_geometry = None
                location_found = False
                
                # Function to create a point buffer for a city location
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
                    
                # Clean up location string for better matching
                clean_location = location.lower()
                
                # For state-level queries, we need special handling
                if clean_location == "pennsylvania" or clean_location == "pa":
                    # Keep it as is for exact state name match
                    st.info(f"Processing state-level query for: {clean_location}")
                else:
                    # Remove common words that might interfere with matching
                    for word in ["county", "parish", "borough", "city", "town", "township", "state of", "commonwealth of"]:
                        clean_location = clean_location.replace(word, "").strip()
                    # Remove any trailing commas and whitespace
                    clean_location = clean_location.rstrip(",").strip()
                
                # 1. Try to match with a state
                state_match = find_region_by_name(states_gdf, clean_location)
                if state_match is not None and len(state_match) > 0:
                    add_status_message(f"Filtering weather data for state: {state_match['state_name'].iloc[0]}", "info")
                    filter_geometry = state_match.unary_union
                    location_found = True
                    
                # 2. If not a state, try to match with a county
                if not location_found:
                    county_match = find_region_by_name(counties_gdf, clean_location)
                    if county_match is not None and len(county_match) > 0:
                        add_status_message(f"Filtering weather data for county: {county_match['county_name'].iloc[0]}", "info")
                        filter_geometry = county_match.unary_union
                        location_found = True
                        
                # 3. If not a county, try to match with a major city
                if not location_found:
                    # Try exact match first
                    city_match = cities[cities['name'].str.lower() == location.lower()]
                    
                    # If no exact match, try partial match
                    if len(city_match) == 0:
                        city_match = cities[cities['name'].str.lower().str.contains(location.lower())]
                        
                    if len(city_match) > 0:
                        city_name = city_match['name'].iloc[0]
                        city_lat = city_match['lat'].iloc[0]
                        city_lon = city_match['lon'].iloc[0]
                        add_status_message(f"Filtering weather data for city: {city_name}", "info")
                        
                        # Create a buffer around the city point
                        filter_geometry = create_city_buffer(city_lat, city_lon)
                        location_found = True
                
                # 4. For PA-specific locations not in datasets but commonly requested
                if not location_found:
                    # Common PA locations with approximate coordinates
                    pa_locations = {
                        "philadelphia": (-75.1652, 39.9526),
                        "pittsburgh": (-79.9959, 40.4406),
                        "harrisburg": (-76.8867, 40.2732),
                        "allentown": (-75.4947, 40.6023),
                        "erie": (-80.0852, 42.1292),
                        "reading": (-75.9269, 40.3356),
                        "scranton": (-75.6624, 41.4090),
                        "lancaster": (-76.3055, 40.0379),
                        "bethlehem": (-75.3705, 40.6259),
                        "altoona": (-78.3947, 40.5187)
                    }
                    
                    # Check for match in PA locations dictionary
                    for city_name, coords in pa_locations.items():
                        if city_name in location.lower() or location.lower() in city_name:
                            add_status_message(f"Filtering weather data for area: {city_name.title()}", "info")
                            lon, lat = coords
                            filter_geometry = create_city_buffer(lat, lon)
                            location_found = True
                            break
                
                # 5. If we found a location, filter the weather GeoDataFrame
                if location_found and filter_geometry is not None:
                    # Filter the GeoDataFrame to only include polygons that intersect with our area
                    weather_gdf = weather_gdf[weather_gdf.intersects(filter_geometry)]
                    
                    if weather_gdf.empty:
                        st.warning(f"No weather data available within {location}")
                        return bounds
                else:
                    st.warning(f"Could not find location: {location}. Showing all weather data.")
            except Exception as e:
                st.warning(f"Could not filter by location: {str(e)}")
        
        # 5. Create display value field with proper units based on parameter
        if parameter == "temperature":
            # Convert from Kelvin to Celsius for display
            weather_gdf.loc[:, 'display_value'] = weather_gdf['temperature'] - 273.15
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

        # Add a formatted string column for the tooltip using .loc
        try:
            # Ensure forecast_time is datetime before formatting
            if pd.api.types.is_datetime64_any_dtype(weather_gdf['forecast_time']):
                weather_gdf.loc[:, 'forecast_time_str'] = weather_gdf['forecast_time'].dt.strftime('%Y-%m-%d %H:%M')
            else:
                weather_gdf.loc[:, 'forecast_time_str'] = 'Invalid Time'
        except AttributeError: # Catch potential errors if column is missing or not datetime-like
             weather_gdf.loc[:, 'forecast_time_str'] = 'Invalid Time'

        # 6. Create color scale based on parameter
        colormap = get_weather_color_scale(parameter, min_val, max_val)
        
        # Add colormap to map
        colormap.caption = f"{parameter.capitalize()} ({unit})"
        colormap.add_to(m)
        
        # 7. Create and add the GeoJSON layer
        # Style function based on the parameter
        def style_function(feature):
            value = feature['properties'][parameter]
            return {
                'fillColor': colormap(value),
                'color': 'gray',
                'weight': 1,
                'fillOpacity': 0.5 # Increased transparency
            }
        
        # Create layer name based on available info (use filter_applied_message)
        layer_name = f"{parameter.capitalize()} Forecast"
        if location:
            layer_name += f" - {location}"
        layer_name += f" - {filter_applied_message}" # Use dynamic message

        # Add the weather layer to the map with interactive tooltip
        weather_layer = folium.GeoJson(
            serialize_geojson(weather_gdf),
            name=layer_name,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=[parameter, 'forecast_time_str', 'display_value'], # Use formatted string
                aliases=[parameter.capitalize(), 'Time (UTC)', f"{parameter.capitalize()} ({unit})"], # Use updated alias
                localize=False, # Don't need Folium's localization
                # fmt dictionary removed
                sticky=True,
                labels=True
            )
        ).add_to(m)
        
        # 8. Set bounds
        bounds_total = weather_gdf.total_bounds
        bounds.append([bounds_total[1], bounds_total[0]])  # SW corner
        bounds.append([bounds_total[3], bounds_total[2]])  # NE corner

        # Display success message (use filter_applied_message)
        add_status_message(f"Displaying {parameter} forecast {filter_applied_message}", "success")

    except Exception as e:
        st.error(f"Error displaying weather data: {str(e)}")
        
    return bounds
