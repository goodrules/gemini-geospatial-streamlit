import streamlit as st
import pandas as pd
import json
import geopandas as gpd
from shapely.geometry import shape, Point
from branca.colormap import LinearColormap
import folium
from data.weather_data import get_weather_forecast_data
from utils.geo_utils import find_region_by_name, get_major_cities
from services.map_core import serialize_geojson

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
        <p><b>Date:</b> {properties.get("forecast_date", "N/A")}</p>
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
    forecast_date = action.get("forecast_date", "12-18-2022")  # Default to available date
    location = action.get("location")  # Optional location filter
    
    try:
        # 1. Get weather forecast data
        weather_df = get_weather_forecast_data()
        
        if weather_df is None or weather_df.empty:
            st.warning("No weather data available")
            return bounds
        
        # Store min/max values for color scale (from whole dataset)
        min_val = weather_df[parameter].min()
        max_val = weather_df[parameter].max()
        
        # 2. Filter by forecast date
        weather_df = weather_df[weather_df["forecast_date"] == forecast_date]
        
        if weather_df.empty:
            st.warning(f"No weather data available for date: {forecast_date}")
            return bounds
        
        # 3. Convert to GeoDataFrame
        geometries = []
        for _, row in weather_df.iterrows():
            # Parse GeoJSON polygon string
            try:
                geojson = json.loads(row['geography_polygon'])
                polygon = shape(geojson)
                geometries.append(polygon)
            except Exception as e:
                st.error(f"Error parsing polygon: {e}")
                continue
        
        # Create GeoDataFrame with weather data
        weather_gdf = gpd.GeoDataFrame(
            weather_df,
            geometry=geometries,
            crs="EPSG:4326"
        )
        
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
                    st.info(f"Filtering weather data for state: {state_match['state_name'].iloc[0]}")
                    filter_geometry = state_match.unary_union
                    location_found = True
                    
                # 2. If not a state, try to match with a county
                if not location_found:
                    county_match = find_region_by_name(counties_gdf, clean_location)
                    if county_match is not None and len(county_match) > 0:
                        st.info(f"Filtering weather data for county: {county_match['county_name'].iloc[0]}")
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
                        st.info(f"Filtering weather data for city: {city_name}")
                        
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
                            st.info(f"Filtering weather data for area: {city_name.title()}")
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
                    st.warning(f"Could not find location: {location}. Showing all Pennsylvania weather data.")
            except Exception as e:
                st.warning(f"Could not filter by location: {str(e)}")
        
        # 5. Create display value field with proper units based on parameter
        if parameter == "temperature":
            # Convert from Kelvin to Celsius for display
            weather_gdf['display_value'] = weather_gdf['temperature'] - 273.15
            unit = "°C"
        elif parameter == "precipitation":
            # Convert to mm
            weather_gdf['display_value'] = weather_gdf['precipitation'] * 1000  # m to mm
            unit = "mm"
        elif parameter == "wind_speed":
            weather_gdf['display_value'] = weather_gdf['wind_speed']
            unit = "m/s"
        else:
            weather_gdf['display_value'] = weather_gdf[parameter]
            unit = ""
        
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
                'fillOpacity': 0.7
            }
        
        # Create layer name based on available info
        layer_name = f"{parameter.capitalize()} Forecast"
        if location:
            layer_name += f" - {location}"
        layer_name += f" - {forecast_date}"
        
        # Add the weather layer to the map with interactive tooltip
        weather_layer = folium.GeoJson(
            serialize_geojson(weather_gdf),
            name=layer_name,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=[parameter, 'forecast_date', 'display_value'],
                aliases=[parameter.capitalize(), 'Date', f"{parameter.capitalize()} ({unit})"],
                localize=True,
                sticky=True,
                labels=True
            )
        ).add_to(m)
        
        # 8. Set bounds
        bounds_total = weather_gdf.total_bounds
        bounds.append([bounds_total[1], bounds_total[0]])  # SW corner
        bounds.append([bounds_total[3], bounds_total[2]])  # NE corner
        
        # Display success message
        st.success(f"Displaying {parameter} forecast for {forecast_date}")
        
    except Exception as e:
        st.error(f"Error displaying weather data: {str(e)}")
        
    return bounds 
