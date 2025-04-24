import folium
import streamlit as st
import pandas as pd
import json
import geopandas as gpd
from shapely.geometry import shape, Point
from folium.plugins import HeatMap
from branca.colormap import LinearColormap
from data.geospatial_data import get_us_states, get_us_counties, get_us_zipcodes
from data.geospatial_data import (get_us_states, get_us_counties, get_us_zipcodes,
                                 get_crawford_flood_zones, get_pa_power_lines)
from data.weather_data import get_weather_forecast_data
from utils.geo_utils import find_region_by_name, get_world_countries, get_major_cities
from utils.streamlit_utils import create_tooltip_html

def initialize_map():
    """Initialize a base Folium map centered on the United States"""
    m = folium.Map(location=[39.8283, -98.5795], zoom_start=4, tiles="OpenStreetMap")
    return m

# Serialize GeoDataFrame objects
def serialize_geojson(gdf):
    """Convert GeoDataFrame to properly serialized GeoJSON"""
    # First convert any timestamp columns to strings
    for col in gdf.columns:
        if pd.api.types.is_datetime64_any_dtype(gdf[col]):
            gdf[col] = gdf[col].astype(str)
    
    # Use to_json with default serializer for dates
    return json.loads(gdf.to_json())

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

def analyze_wind_risk(weather_gdf, power_lines_gdf, high_threshold=16.0, moderate_threshold=13.0):
    """
    Analyze risk to power lines from high and moderate winds
    
    Args:
        weather_gdf: GeoDataFrame with weather forecast data
        power_lines_gdf: GeoDataFrame with power line geometries
        high_threshold: High risk wind speed threshold in m/s (default: 16.0 m/s)
        moderate_threshold: Moderate risk wind speed threshold in m/s (default: 13.0 m/s)
        
    Returns:
        risk_events: List of wind risk events
        summary: Dictionary with risk summary information
    """
    try:
        # 1. Filter weather data for winds above moderate threshold
        wind_risk_areas = weather_gdf[weather_gdf['wind_speed'] >= moderate_threshold].copy()
        
        if wind_risk_areas.empty:
            return None, {
                "risk_found": False,
                "message": f"No areas with wind speeds over {moderate_threshold} m/s found in the forecast period."
            }
        
        # Classify risk levels
        wind_risk_areas['risk_level'] = 'moderate'
        wind_risk_areas.loc[wind_risk_areas['wind_speed'] >= high_threshold, 'risk_level'] = 'high'
        
        # Count areas in each risk category
        high_risk_count = len(wind_risk_areas[wind_risk_areas['risk_level'] == 'high'])
        moderate_risk_count = len(wind_risk_areas[wind_risk_areas['risk_level'] == 'moderate'])
            
        # 2. Prepare power lines data
        if power_lines_gdf is None:
            power_lines_gdf = get_pa_power_lines()
            
        if power_lines_gdf is None or power_lines_gdf.empty:
            return wind_risk_areas, {
                "risk_found": True,
                "message": f"Found areas with high ({high_risk_count}) and moderate ({moderate_risk_count}) wind risk, but no power line data available for detailed assessment.",
                "high_risk_areas": high_risk_count,
                "moderate_risk_areas": moderate_risk_count,
                "affected_dates": sorted(wind_risk_areas['forecast_date'].unique().tolist()),
                "max_wind_speed": wind_risk_areas['wind_speed'].max()
            }
            
        # 3. Create a buffer around power lines (approximately 1km buffer)
        # Convert to a projected CRS for accurate buffering
        power_lines_proj = power_lines_gdf.to_crs("EPSG:3857")  # Web Mercator
        buffered_lines = power_lines_proj.buffer(1000)  # 1km buffer
        buffered_lines_gdf = gpd.GeoDataFrame(power_lines_gdf, geometry=buffered_lines)
        buffered_lines_gdf = buffered_lines_gdf.to_crs("EPSG:4326")  # Back to WGS84
        
        # 4. Perform spatial join to find intersections
        # Convert risk areas to same CRS
        wind_risk_areas_proj = wind_risk_areas.to_crs("EPSG:4326")
        
        # Perform spatial join - find where wind risk areas intersect with power line buffers
        risk_areas = gpd.sjoin(wind_risk_areas_proj, buffered_lines_gdf, how="inner", predicate="intersects")
        
        if risk_areas.empty:
            return wind_risk_areas, {
                "risk_found": True,
                "message": f"Found areas with high ({high_risk_count}) and moderate ({moderate_risk_count}) wind risk, but none affect power lines.",
                "high_risk_areas": high_risk_count,
                "moderate_risk_areas": moderate_risk_count,
                "affected_dates": sorted(wind_risk_areas['forecast_date'].unique().tolist()),
                "max_wind_speed": wind_risk_areas['wind_speed'].max()
            }
                   
        # 5. Calculate risk metrics
        # Add a risk score - percentage scale
        max_possible_wind = risk_areas['wind_speed'].max()
        min_threshold = moderate_threshold
        risk_areas['risk_score'] = ((risk_areas['wind_speed'] - min_threshold) / 
                                    (max_possible_wind - min_threshold) * 100)
        
        # Ensure risk score is between 0-100
        risk_areas['risk_score'] = risk_areas['risk_score'].clip(0, 100)
        
        # 6. Group data into events by date
        events = []
        risk_events = {}
        
        # Process each date as a potential event
        for date in sorted(risk_areas['forecast_date'].unique()):
            date_areas = risk_areas[risk_areas['forecast_date'] == date]
            
            # Skip if no data for this date
            if date_areas.empty:
                continue
                
            # Count risk levels
            high_count = len(date_areas[date_areas['risk_level'] == 'high'])
            moderate_count = len(date_areas[date_areas['risk_level'] == 'moderate'])
            
            # Skip if no significant risk
            if high_count + moderate_count == 0:
                continue
                
            # Create event ID
            event_id = f"wind_event_{date.replace('-', '')}"
            
            # Create a summary for this event
            event_summary = {
                "id": event_id,
                "date": date,
                "high_risk_count": high_count,
                "moderate_risk_count": moderate_count,
                "max_wind_speed": date_areas['wind_speed'].max(),
                "affected_km": len(date_areas) * 0.25,  # Rough estimate of affected area
                "risk_level": "High" if high_count > 0 else "Moderate"
            }
            
            # Add to events list
            events.append(event_summary)
            
            # Store the actual data for this event
            risk_events[event_id] = date_areas
        
        # 7. Prepare overall summary
        total_high_risk = sum(event['high_risk_count'] for event in events)
        total_moderate_risk = sum(event['moderate_risk_count'] for event in events)
        total_affected_km = sum(event['affected_km'] for event in events)
        max_wind_overall = max(event['max_wind_speed'] for event in events) if events else 0
        
        # Find date with highest risk
        if events:
            highest_risk_event = max(events, key=lambda x: x['high_risk_count'] if x['high_risk_count'] > 0 else x['moderate_risk_count']/2)
            highest_risk_date = highest_risk_event['date']
        else:
            highest_risk_date = "None"
        
        summary = {
            "risk_found": len(events) > 0,
            "message": f"Found {len(events)} potential wind events affecting power lines.",
            "event_count": len(events),
            "events": events,
            "high_risk_areas": total_high_risk,
            "moderate_risk_areas": total_moderate_risk,
            "affected_power_lines_km": total_affected_km,
            "highest_risk_date": highest_risk_date,
            "max_wind_speed": max_wind_overall
        }
        
        return risk_events, summary
        
    except Exception as e:
        st.error(f"Error analyzing wind risk: {str(e)}")
        return None, {
            "risk_found": False,
            "message": f"Error analyzing wind risk: {str(e)}"
        }

def process_map_actions(actions, m):
    """Process map actions from AI responses and apply them to the map"""
    if not actions or not isinstance(actions, list):
        return m
    
    # Track all bounds to calculate overall view at the end
    all_bounds = []
    
    # Extract location information from all actions to use for weather filtering
    # This allows the weather action to use location data from highlight_region actions
    extracted_locations = {}
    
    # First pass - extract location data from all actions
    for action in actions:
        if not isinstance(action, dict):
            continue
            
        action_type = action.get("action_type")
        
        if action_type == "highlight_region":
            region_name = action.get("region_name")
            region_type = action.get("region_type", "state")
            state_name = action.get("state_name")
            
            if region_name:
                # Store location data keyed by region type
                if region_type.lower() == "county":
                    # For counties, include the state if available
                    county_key = region_name.lower()
                    if state_name:
                        county_key += f", {state_name.lower()}"
                    extracted_locations["county"] = county_key
                    # Also store just the county name
                    extracted_locations["county_name"] = region_name.lower()
                elif region_type.lower() == "state":
                    extracted_locations["state"] = region_name.lower()
                elif region_type.lower() in ["zipcode", "zip_code", "zip"]:
                    extracted_locations["zipcode"] = region_name
                    if state_name:
                        extracted_locations["state"] = state_name.lower()
            
        elif action_type == "show_weather":
            # Store any explicit location specified in the weather action
            location = action.get("location")
            if location:
                extracted_locations["weather_location"] = location.lower()
    
    for action in actions:
        if not isinstance(action, dict):
            continue
            
        action_type = action.get("action_type")
        
        if action_type == "add_marker":
            lat = action.get("lat")
            lon = action.get("lon")
            
            if lat is not None and lon is not None:
                folium.Marker(
                    location=[lat, lon],
                    popup=action.get("popup", ""),
                    icon=folium.Icon(color=action.get("color", "blue"))
                ).add_to(m)
                
                # Add marker bounds to all_bounds
                all_bounds.append([lat, lon])
                
        elif action_type == "highlight_region":
            region_name = action.get("region_name")
            region_type = action.get("region_type", "state")
            
            if not region_name:
                continue
                
            # Get the appropriate dataset based on region type
            gdf = None
            if region_type.lower() == "state":
                gdf = get_us_states()
            elif region_type.lower() == "county":
                gdf = get_us_counties()
                # For counties, we might need to include state in the search
                state_name = action.get("state_name")
                if state_name and gdf is not None:
                    # First filter by state if provided
                    states = get_us_states()
                    state = find_region_by_name(states, state_name)
                    if state is not None:
                        state_fips = state['state_fips_code'].iloc[0]
                        gdf = gdf[gdf['state_fips_code'] == state_fips]
            elif region_type.lower() in ["zipcode", "zip_code", "zip"]:
                gdf = get_us_zipcodes()
                # For zip codes, we might need to filter by state or county
                state_name = action.get("state_name")
                county_name = action.get("county_name")
                if state_name and gdf is not None:
                    # Filter by state if provided
                    gdf = gdf[gdf['state_name'].str.lower() == state_name.lower()]
                if county_name and gdf is not None:
                    # Filter by county if provided
                    gdf = gdf[gdf['county'].str.lower() == county_name.lower()]
            elif region_type.lower() == "country":
                gdf = get_world_countries()
            elif region_type.lower() == "continent":
                gdf = get_world_countries()
                # For continents, search the continent column
                region = find_region_by_name(gdf, region_name, ['continent'])
                if region is not None:
                    # Add the GeoJSON for this region
                    folium.GeoJson(
                        region.__geo_interface__,
                        name=f"{region_name}",
                        style_function=lambda x: {
                            'fillColor': action.get("fill_color", "#ff7800"),
                            'color': action.get("color", "black"),
                            'weight': 2,
                            'fillOpacity': action.get("fill_opacity", 0.5)
                        }
                    ).add_to(m)
                    
                    # Add region bounds to all_bounds list
                    bounds = region.total_bounds
                    all_bounds.append([bounds[1], bounds[0]])  # SW corner
                    all_bounds.append([bounds[3], bounds[2]])  # NE corner
                continue
            elif region_type.lower() == "flood_zone":
                gdf = get_crawford_flood_zones()
            elif region_type.lower() == "power_line":
                gdf = get_pa_power_lines()
            
            # Find the region
            region = find_region_by_name(gdf, region_name)
            
            if region is not None:
                # Create a tooltip with region information
                tooltip_html = create_tooltip_html(region, region_type)
                
                # Convert timestamps to strings to avoid serialization issues
                for col in region.columns:
                    if pd.api.types.is_datetime64_any_dtype(region[col]):
                        region[col] = region[col].astype(str)
                
                # Add the GeoJSON for this region with tooltip
                geo_layer = folium.GeoJson(
                    json.loads(region.to_json()),
                    name=f"{region_name}",
                    style_function=lambda x: {
                        'fillColor': action.get("fill_color", "#ff7800"),
                        'color': action.get("color", "black"),
                        'weight': action.get("weight", 2),
                        'fillOpacity': action.get("fill_opacity", 0.5)
                    },
                    tooltip=folium.Tooltip(tooltip_html)
                ).add_to(m)
                
                # Add region bounds to all_bounds list instead of fitting immediately
                bounds = region.total_bounds
                all_bounds.append([bounds[1], bounds[0]])  # SW corner
                all_bounds.append([bounds[3], bounds[2]])  # NE corner
            else:
                st.write(f"Could not find region: {region_name}")
                
        elif action_type == "fit_bounds":
            # If explicit fit_bounds is specified, honor it directly
            bounds = action.get("bounds")
            if bounds and isinstance(bounds, list) and len(bounds) == 2:
                m.fit_bounds(bounds)  # Apply explicit bounds
                return m  # Return immediately with explicit bounds
                
        elif action_type == "show_weather":
            # Get weather data parameters
            parameter = action.get("parameter", "temperature")  # Default to temperature if not specified
            forecast_date = action.get("forecast_date", "12-18-2022")  # Default to the available data date
            
            # Try to get location from multiple sources in order of priority
            location = None
            
            # First try location directly specified in this action
            if action.get("location"):
                location = action.get("location")
                st.info(f"Using location specified in weather action: {location}")
            
            # If no location in this action, try to use location from extracted_locations
            elif extracted_locations:
                # Priority order: county, county_name, state, zipcode, weather_location
                st.info(f"DEBUG: Extracted locations: {extracted_locations}")
                if "county" in extracted_locations:
                    location = extracted_locations["county"]
                    st.info(f"Using county from highlight action: {location}")
                elif "county_name" in extracted_locations:
                    location = extracted_locations["county_name"]
                    st.info(f"Using county name from highlight action: {location}")
                elif "state" in extracted_locations:
                    location = extracted_locations["state"]
                    st.info(f"Using state from highlight action: {location}")
                elif "zipcode" in extracted_locations:
                    location = extracted_locations["zipcode"]
                    st.info(f"Using zipcode from highlight action: {location}")
                elif "weather_location" in extracted_locations:
                    location = extracted_locations["weather_location"]
                    st.info(f"Using weather location: {location}")
            
            # If still no location, default to "pennsylvania" for state-level weather queries
            if location is None or location.strip() == "":
                location = "pennsylvania"
                st.info(f"No specific location found, defaulting to entire state: {location}")

            try:
                # Fetch weather data
                weather_df = get_weather_forecast_data()
                min_val = weather_df[parameter].min()
                max_val = weather_df[parameter].max()
                
                if weather_df is None or weather_df.empty:
                    st.warning("No weather data available")
                    continue
                
                # Filter by forecast date
                weather_df = weather_df[weather_df["forecast_date"] == forecast_date]
                
                if weather_df.empty:
                    st.warning(f"No weather data available for date: {forecast_date}")
                    continue
                
                # Convert GeoJSON polygon strings to actual GeoDataFrame
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
                gdf = gpd.GeoDataFrame(
                    weather_df,
                    geometry=geometries,
                    crs="EPSG:4326"
                )
                
                # Location-based filtering
                if location:
                    try:
                        # Get geospatial datasets for location matching
                        states_gdf = get_us_states()
                        counties_gdf = get_us_counties()
                        cities = get_major_cities()
                        
                        # Initialize a geometry to use for filtering
                        filter_geometry = None
                        location_found = False
                        
                        # Function to create a point buffer for a city location
                        def create_city_buffer(lat, lon, buffer_km=20):
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
                            # Remove common words that might interfere with matching for other locations
                            for word in ["county", "parish", "borough", "city", "town", "township", "state of", "commonwealth of"]:
                                clean_location = clean_location.replace(word, "").strip()
                            # Remove any trailing commas and whitespace
                            clean_location = clean_location.rstrip(",").strip()
                        
                        # Log the cleaned location for debugging
                        st.info(f"Searching for location: '{clean_location}'")
                        
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
                            gdf = gdf[gdf.intersects(filter_geometry)]
                            
                            if gdf.empty:
                                st.warning(f"No weather data available within {location}")
                        else:
                            st.warning(f"Could not find location: {location}. Showing all Pennsylvania weather data.")
                            
                    except Exception as e:
                        st.warning(f"Could not filter by location: {str(e)}")
                
                if gdf.empty:
                    st.warning(f"No weather data matching the criteria")
                    continue
                
                # Get color scale for the selected parameter
                colormap = get_weather_color_scale(parameter, min_val, max_val)
                
                # Add the weather layer with parameter-specific styling
                layer_name = f"Weather - {parameter.capitalize()}"
                if location:
                    layer_name += f" - {location}"
                layer_name += f" - {forecast_date}"
                
                # Function to style each polygon based on parameter value
                def style_function(feature):
                    properties = feature["properties"]
                    value = float(properties.get(parameter, 0))
                    color = colormap(value)
                    
                    return {
                        'fillColor': color,
                        'color': 'gray',
                        'weight': 1,
                        'fillOpacity': 0.7
                    }
                
                # Add GeoJSON layer with weather data
                # Using the built-in tooltip for stability
                weather_layer = folium.GeoJson(
                    json.loads(gdf.to_json()),
                    name=layer_name,
                    style_function=style_function,
                    tooltip=folium.GeoJsonTooltip(
                        fields=[parameter, 'forecast_date'],
                        aliases=[parameter.capitalize(), 'Date'],
                        localize=True,
                        sticky=True
                    )
                ).add_to(m)
                
                # Add colormap legend
                colormap.caption = f'{parameter.capitalize()} Scale'
                colormap.add_to(m)
                
                # Add dataset bounds to all_bounds list
                bounds = gdf.total_bounds
                all_bounds.append([bounds[1], bounds[0]])  # SW corner
                all_bounds.append([bounds[3], bounds[2]])  # NE corner
                
                st.success(f"Displaying weather data: {parameter} for {forecast_date}")
                
            except Exception as e:
                st.error(f"Error displaying weather data: {e}")
                continue
        
        elif action_type == "analyze_wind_risk":
            # This action analyzes wind risk to power lines with dual thresholds
            
            # Parameters for risk analysis
            high_threshold = action.get("high_threshold", 16.0)  # High risk threshold (default 16 m/s)
            moderate_threshold = action.get("moderate_threshold", 13.0)  # Moderate risk threshold (default 13 m/s)
            dates = action.get("dates", [])  # Optional list of specific dates to check
            forecast_days = action.get("forecast_days", 10)  # Number of days to check
            
            try:
                # 1. Get weather forecast data
                weather_df = get_weather_forecast_data()
                
                if weather_df is None or weather_df.empty:
                    st.warning("No weather data available for risk analysis")
                    continue
                    
                # 2. Filter by dates if specified
                if dates and isinstance(dates, list) and len(dates) > 0:
                    weather_df = weather_df[weather_df["forecast_date"].isin(dates)]
                else:
                    # Use all available dates within forecast_days
                    all_dates = sorted(weather_df["forecast_date"].unique().tolist())
                    # Use first date as reference (init_date)
                    base_date = all_dates[0] if all_dates else None
                    
                    if base_date is not None and len(all_dates) > 1:
                        # Get dates within the forecast period
                        dates_to_use = all_dates[:min(forecast_days, len(all_dates))]
                        weather_df = weather_df[weather_df["forecast_date"].isin(dates_to_use)]
                
                if weather_df.empty:
                    st.warning("No weather data available for the specified dates")
                    continue
                
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
                
                # 4. Get power lines data
                power_lines_gdf = get_pa_power_lines()
                
                # 5. Analyze wind risk
                st.info(f"Analyzing wind risk to power lines (high: {high_threshold} m/s, moderate: {moderate_threshold} m/s)...")
                risk_events, risk_summary = analyze_wind_risk(
                    weather_gdf, 
                    power_lines_gdf,
                    high_threshold,
                    moderate_threshold
                )
                
                # 6. Display risk summary
                if risk_summary["risk_found"]:
                    # Create a container for the risk assessment
                    risk_container = st.container()
                    
                    with risk_container:
                        st.markdown("## Power Line Risk Assessment")
                        st.markdown(risk_summary["message"])
                        
                        # Create metrics row
                        metrics_cols = st.columns(3)
                        with metrics_cols[0]:
                            st.metric("High Risk Areas", f"{risk_summary['high_risk_areas']}")
                        with metrics_cols[1]:
                            st.metric("Moderate Risk Areas", f"{risk_summary['moderate_risk_areas']}")
                        with metrics_cols[2]:
                            st.metric("Affected Power Lines", f"{risk_summary['affected_power_lines_km']:.1f} km")
                            
                        # Create the event selector
                        if "events" in risk_summary and risk_summary["events"]:
                            events = risk_summary["events"]
                            
                            # Format event options for the selector
                            event_options = []
                            for event in events:
                                date = event["date"]
                                risk_level = event["risk_level"]
                                max_wind = event["max_wind_speed"]
                                option_text = f"{date} - {risk_level} Risk (max wind: {max_wind:.1f} m/s)"
                                event_options.append((event["id"], option_text))
                            
                            # Add "All Events" option
                            event_options.insert(0, ("all_events", "Show All Events"))
                            
                            # Create the selector
                            st.markdown("### Select Wind Event to Display:")
                            selected_event = st.selectbox(
                                "Wind Events",
                                options=[id for id, _ in event_options],
                                format_func=lambda x: dict(event_options)[x],
                                key="wind_event_selector"
                            )
                            
                            # 7. Visualize risk areas based on selection
                            # Add power lines layer
                            if power_lines_gdf is not None:
                                folium.GeoJson(
                                    json.loads(power_lines_gdf.to_json()),
                                    name="Power Lines",
                                    style_function=lambda x: {
                                        'color': '#0066cc',
                                        'weight': 2,
                                        'opacity': 0.8
                                    }
                                ).add_to(m)
                            
                            # Create color scales for risk visualization
                            risk_colormaps = {
                                'high': LinearColormap(
                                    ['#fdbb84', '#e34a33', '#b30000'],
                                    vmin=0,
                                    vmax=100,
                                    caption="High Wind Risk (≥ 16 m/s)"
                                ),
                                'moderate': LinearColormap(
                                    ['#fee8c8', '#fdbb84', '#e34a33'],
                                    vmin=0,
                                    vmax=100,
                                    caption="Moderate Wind Risk (13-16 m/s)"
                                )
                            }
                            
                            # Get data for selected event
                            if selected_event == "all_events":
                                # Combine all events into one GeoDataFrame
                                all_risk_areas = pd.concat([df for df in risk_events.values()])
                                
                                # Split by risk level
                                high_risk_df = all_risk_areas[all_risk_areas['risk_level'] == 'high']
                                moderate_risk_df = all_risk_areas[all_risk_areas['risk_level'] == 'moderate']
                            else:
                                # Get single event data
                                all_risk_areas = risk_events.get(selected_event)
                                if all_risk_areas is not None:
                                    # Split by risk level
                                    high_risk_df = all_risk_areas[all_risk_areas['risk_level'] == 'high']
                                    moderate_risk_df = all_risk_areas[all_risk_areas['risk_level'] == 'moderate']
                                else:
                                    st.warning(f"No data available for selected event: {selected_event}")
                                    continue
                            
                            # Add layers to map
                            # Style function for high risk areas
                            def high_risk_style(feature):
                                risk = feature['properties'].get('risk_score', 0)
                                return {
                                    'fillColor': risk_colormaps['high'](risk),
                                    'color': 'black',
                                    'weight': 1,
                                    'fillOpacity': 0.7
                                }
                                
                            # Style function for moderate risk areas
                            def moderate_risk_style(feature):
                                risk = feature['properties'].get('risk_score', 0)
                                return {
                                    'fillColor': risk_colormaps['moderate'](risk),
                                    'color': 'gray',
                                    'weight': 1,
                                    'fillOpacity': 0.6
                                }
                            
                            # Add high risk areas if exist
                            if not high_risk_df.empty:
                                high_risk_layer = folium.GeoJson(
                                    json.loads(high_risk_df.to_json()),
                                    name="High Wind Risk Areas",
                                    style_function=high_risk_style,
                                    tooltip=folium.GeoJsonTooltip(
                                        fields=['forecast_date', 'wind_speed', 'risk_score'],
                                        aliases=['Date', 'Wind Speed (m/s)', 'Risk Score'],
                                        localize=True,
                                        sticky=True
                                    )
                                ).add_to(m)
                                
                                # Add high risk colormap
                                risk_colormaps['high'].add_to(m)
                                
                                # Track bounds
                                bounds = high_risk_df.total_bounds
                                all_bounds.append([bounds[1], bounds[0]])  # SW corner
                                all_bounds.append([bounds[3], bounds[2]])  # NE corner
                            
                            # Add moderate risk areas if exist
                            if not moderate_risk_df.empty:
                                moderate_risk_layer = folium.GeoJson(
                                    json.loads(moderate_risk_df.to_json()),
                                    name="Moderate Wind Risk Areas",
                                    style_function=moderate_risk_style,
                                    tooltip=folium.GeoJsonTooltip(
                                        fields=['forecast_date', 'wind_speed', 'risk_score'],
                                        aliases=['Date', 'Wind Speed (m/s)', 'Risk Score'],
                                        localize=True,
                                        sticky=True
                                    )
                                ).add_to(m)
                                
                                # Add moderate risk colormap
                                risk_colormaps['moderate'].add_to(m)
                                
                                # Track bounds
                                bounds = moderate_risk_df.total_bounds
                                all_bounds.append([bounds[1], bounds[0]])  # SW corner
                                all_bounds.append([bounds[3], bounds[2]])  # NE corner
                            
                            # Display event details
                            if selected_event != "all_events":
                                event_data = next((e for e in events if e["id"] == selected_event), None)
                                if event_data:
                                    st.markdown(f"""
                                    #### Event Details: {event_data['date']}
                                    - **Risk Level:** {event_data['risk_level']}
                                    - **High Risk Areas:** {event_data['high_risk_count']}
                                    - **Moderate Risk Areas:** {event_data['moderate_risk_count']}
                                    - **Maximum Wind Speed:** {event_data['max_wind_speed']:.1f} m/s
                                    - **Affected Power Lines:** ~{event_data['affected_km']:.1f} km
                                    """)
                        else:
                            st.warning("No specific wind events were identified in the analysis.")
                else:
                    st.info(risk_summary["message"])
                
            except Exception as e:
                st.error(f"Error analyzing wind risk: {str(e)}")
                
                
        elif action_type == "show_local_dataset":
            # New action type for directly displaying a full local dataset
            dataset_name = action.get("dataset_name", "").lower()
            
            if dataset_name == "flood_zones" or dataset_name == "crawford_flood_zones":
                gdf = get_crawford_flood_zones()
                layer_name = "Crawford County Flood Zones"
                default_color = "#0066cc"  # Blue for flood zones
                fill_color = "#99ccff"    # Light blue fill
            elif dataset_name == "power_lines" or dataset_name == "pa_power_lines":
                gdf = get_pa_power_lines()
                layer_name = "PA Power Lines"
                default_color = "#0066cc"  # Blue for power lines
                fill_color = "#ffff00"    # Yellow fill
            else:
                st.warning(f"Unknown local dataset: {dataset_name}")
                continue
                
            if gdf is not None:
                # Convert timestamps to strings to avoid serialization issues
                for col in gdf.columns:
                    if pd.api.types.is_datetime64_any_dtype(gdf[col]):
                        gdf[col] = gdf[col].astype(str)
                
                # Create a tooltip with dataset information
                first_col = gdf.columns[0] if len(gdf.columns) > 0 else None
                tooltip_fields = action.get("tooltip_fields", [first_col]) if first_col else []
                tooltip_aliases = action.get("tooltip_aliases", tooltip_fields)
                
                # Use tooltip if fields are available
                tooltip = None
                if tooltip_fields:
                    tooltip = folium.GeoJsonTooltip(
                        fields=tooltip_fields,
                        aliases=tooltip_aliases,
                        sticky=True
                    )
                
                # Add the GeoJSON for this dataset with tooltip
                geo_layer = folium.GeoJson(
                    json.loads(gdf.to_json()),
                    name=layer_name,
                    style_function=lambda x: {
                        'fillColor': action.get("fill_color", fill_color),
                        'color': action.get("color", default_color),
                        'weight': action.get("weight", 4),  # Thicker lines by default
                        'fillOpacity': action.get("fill_opacity", 0.5)
                    },
                    tooltip=tooltip
                ).add_to(m)
                
                # Add dataset bounds to all_bounds list
                bounds = gdf.total_bounds
                all_bounds.append([bounds[1], bounds[0]])  # SW corner
                all_bounds.append([bounds[3], bounds[2]])  # NE corner
                
        elif action_type == "add_circle":
            lat = action.get("lat")
            lon = action.get("lon")
            radius = action.get("radius", 1000)
            
            if lat is not None and lon is not None:
                folium.Circle(
                    location=[lat, lon],
                    radius=radius,
                    popup=action.get("popup", ""),
                    color=action.get("color", "blue"),
                    fill=True,
                    fill_opacity=0.2
                ).add_to(m)
                
                # Add circle center to bounds
                all_bounds.append([lat, lon])
            
        elif action_type == "add_heatmap":
            data_points = action.get("data_points", [])
            if data_points and isinstance(data_points, list):
                HeatMap(
                    data=data_points,
                    radius=action.get("radius", 15),
                    blur=action.get("blur", 10),
                    gradient=action.get("gradient", None)
                ).add_to(m)
                
                # Add all heatmap points to bounds
                for point in data_points:
                    if len(point) >= 2:  # Make sure we have at least lat, lon
                        all_bounds.append([point[0], point[1]])
                
        elif action_type == "add_line":
            locations = action.get("locations", [])
            
            if locations and isinstance(locations, list) and len(locations) >= 2:
                folium.PolyLine(
                    locations=locations,
                    popup=action.get("popup", ""),
                    color=action.get("color", "blue"),
                    weight=action.get("weight", 3),
                    opacity=action.get("opacity", 1.0),
                    dash_array=action.get("dash_array", None)
                ).add_to(m)
                
                # Add all line points to bounds
                for loc in locations:
                    all_bounds.append(loc)
                
        elif action_type == "add_polygon":
            locations = action.get("locations", [])
            
            if locations and isinstance(locations, list) and len(locations) >= 3:
                folium.Polygon(
                    locations=locations,
                    popup=action.get("popup", ""),
                    color=action.get("color", "blue"),
                    weight=action.get("weight", 2),
                    fill_color=action.get("fill_color", "blue"),
                    fill_opacity=action.get("fill_opacity", 0.2)
                ).add_to(m)
                
                # Add all polygon points to bounds
                for loc in locations:
                    all_bounds.append(loc)
                    
        elif action_type == "show_weather":
            # Get weather parameter to display (temperature, precipitation, or wind_speed)
            weather_param = action.get("weather_param", "temperature")
            
            # Get forecast date from action or session state
            forecast_date = action.get("forecast_date", None)
            if forecast_date is None and "weather_forecast_date" in st.session_state:
                forecast_date = st.session_state.weather_forecast_date
            
            # Get the weather forecast data
            weather_df = get_weather_forecast_data()
            
            if weather_df is None or weather_df.empty:
                st.error("No weather data available")
                continue
                
            # Filter by forecast date if provided
            if forecast_date:
                weather_df = weather_df[weather_df['forecast_date'] == forecast_date]
                
            if weather_df.empty:
                st.error(f"No weather data available for date {forecast_date}")
                continue
                
            # Create GeoDataFrame from the weather data
            gdf_list = []
            
            for _, row in weather_df.iterrows():
                # Parse the GeoJSON polygon from the geography_polygon column
                try:
                    geojson = json.loads(row['geography_polygon'])
                    geometry = shape(geojson)
                    
                    # Create GeoDataFrame for this row
                    gdf_row = gpd.GeoDataFrame(
                        {
                            'forecast_date': row['forecast_date'],
                            'init_date': row['init_date'],
                            'temperature': row['temperature'],
                            'precipitation': row['precipitation'],
                            'wind_speed': row['wind_speed'],
                            'geometry': [geometry]
                        },
                        crs="EPSG:4326"
                    )
                    gdf_list.append(gdf_row)
                except Exception as e:
                    st.error(f"Error parsing geography: {e}")
                    continue
            
            if not gdf_list:
                st.error("No valid geographic data found in weather forecast")
                continue
                
            # Combine all GeoDataFrames
            weather_gdf = pd.concat(gdf_list)
            
            # Generate color map based on weather parameter
            if weather_param == "temperature":
                # Convert from Kelvin to Celsius for display
                weather_gdf['display_value'] = weather_gdf['temperature'] - 273.15
                vmin = weather_gdf['display_value'].min()
                vmax = weather_gdf['display_value'].max()
                colormap = LinearColormap(
                    colors=['blue', 'green', 'yellow', 'orange', 'red'], 
                    vmin=vmin, 
                    vmax=vmax,
                    caption=f"Temperature (°C)"
                )
                unit = "°C"
            elif weather_param == "precipitation":
                weather_gdf['display_value'] = weather_gdf['precipitation']
                vmin = 0
                vmax = max(0.001, weather_gdf['display_value'].max())  # Ensure non-zero range
                colormap = LinearColormap(
                    colors=['#ffffff', '#c6dbef', '#6baed6', '#2171b5', '#08306b'], 
                    vmin=vmin, 
                    vmax=vmax,
                    caption=f"Precipitation (mm)"
                )
                unit = "mm"
            elif weather_param == "wind_speed":
                weather_gdf['display_value'] = weather_gdf['wind_speed']
                vmin = weather_gdf['display_value'].min()
                vmax = weather_gdf['display_value'].max()
                colormap = LinearColormap(
                    colors=['#f7fcf0', '#bae4b3', '#74c476', '#31a354', '#006d2c'], 
                    vmin=vmin, 
                    vmax=vmax,
                    caption=f"Wind Speed (m/s)"
                )
                unit = "m/s"
            else:
                st.error(f"Unsupported weather parameter: {weather_param}")
                continue
                
            # Serialize the GeoDataFrame to GeoJSON
            geojson_data = json.loads(weather_gdf.to_json())
            
            # Create and add the choropleth layer
            folium.GeoJson(
                geojson_data,
                name=f"{weather_param.capitalize()} Forecast",
                style_function=lambda feature: {
                    'fillColor': colormap(feature['properties']['display_value']),
                    'color': 'black',
                    'weight': 1,
                    'fillOpacity': 0.7
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['forecast_date', 'display_value'],
                    aliases=[
                        'Forecast Date', 
                        f"{weather_param.capitalize()} ({unit})"
                    ],
                    localize=True,
                    sticky=True,
                    labels=True,
                    style="""
                        background-color: #F0EFEF;
                        border: 2px solid black;
                        border-radius: 3px;
                        box-shadow: 3px;
                    """,
                )
            ).add_to(m)
            
            # Add the colormap to the map
            colormap.add_to(m)
            
            # Add dataset bounds to all_bounds list
            bounds = weather_gdf.total_bounds
            all_bounds.append([bounds[1], bounds[0]])  # SW corner
            all_bounds.append([bounds[3], bounds[2]])  # NE corner
    
    # After processing all actions, fit the map to show all features
    if all_bounds:
        if len(all_bounds) == 1:
            # If only one point, center on it with a reasonable zoom
            m.location = all_bounds[0]
            m.zoom_start = 10
        else:
            # Calculate the bounds that encompass all points/regions
            try:
                # Use folium's fit_bounds to automatically adjust the view
                m.fit_bounds(all_bounds, padding=(30, 30))
            except Exception as e:
                st.error(f"Error fitting bounds: {e}")
    
    return m
