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

def create_weather_tooltip(properties, parameter):
    """Create HTML tooltip for weather data"""
    # Convert temperature from Kelvin to Fahrenheit
    temp_f = None
    if "temperature" in properties:
        temp_k = float(properties["temperature"])
        temp_f = (temp_k - 273.15) * 9/5 + 32
    
    # Format precipitation as mm
    precip = None
    if "precipitation" in properties:
        precip = float(properties["precipitation"]) * 1000  # Convert to mm if needed
    
    # Format wind speed (already in m/s)
    wind = None
    if "wind_speed" in properties:
        wind = float(properties["wind_speed"])
    
    # Create tooltip with available data
    tooltip_html = f"""
    <div style="min-width: 180px;">
        <h4>Weather Forecast</h4>
        <p><b>Date:</b> {properties.get("forecast_date", "N/A")}</p>
    """
    
    if temp_f is not None:
        tooltip_html += f"<p><b>Temperature:</b> {temp_f:.1f}°F</p>"
    
    if precip is not None:
        tooltip_html += f"<p><b>Precipitation:</b> {precip:.4f} mm</p>"
    
    if wind is not None:
        tooltip_html += f"<p><b>Wind Speed:</b> {wind:.1f} m/s</p>"
    
    tooltip_html += "</div>"
    return tooltip_html

def get_weather_color_scale(parameter):
    """Define color scales for different weather parameters"""
    if parameter == "temperature":
        # Temperature color scale (Kelvin values)
        # Colors from cool blue to hot red
        return LinearColormap(
            ['#0000ff', '#00ffff', '#00ff00', '#ffff00', '#ff0000'],
            vmin=265,  # ~15°F
            vmax=285,  # ~55°F
        )
    elif parameter == "precipitation":
        # Precipitation color scale (mm)
        # Colors from white/pale blue (low) to dark blue (high)
        return LinearColormap(
            ['#ffffff', '#c6dbef', '#9ecae1', '#6baed6', '#3182bd', '#08519c'],
            vmin=0,
            vmax=0.001,  # Adjust based on actual precipitation values
        )
    elif parameter == "wind_speed":
        # Wind speed color scale (m/s)
        # Colors from white/pale green (low) to dark green (high)
        return LinearColormap(
            ['#ffffff', '#c7e9c0', '#a1d99b', '#74c476', '#31a354', '#006d2c'],
            vmin=0,
            vmax=10,  # Adjust based on actual wind speed values
        )
    else:
        # Default color scale
        return LinearColormap(
            ['#ffffff', '#bbbbbb', '#777777', '#444444', '#000000'],
            vmin=0,
            vmax=100,
        )

def process_map_actions(actions, m):
    """Process map actions from AI responses and apply them to the map"""
    if not actions or not isinstance(actions, list):
        return m
    
    # Track all bounds to calculate overall view at the end
    all_bounds = []
    
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
            location = action.get("location", None)  # Optional location filter
            
            try:
                # Fetch weather data
                weather_df = get_weather_forecast_data()
                
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
                    # We'll do a basic filtering based on polygon coordinates
                    try:
                        # Get state GeoDataFrame to find location
                        states = get_us_states()
                        counties = get_us_counties()
                        
                        # Try to find as state first
                        state_match = find_region_by_name(states, location)
                        
                        if state_match is not None:
                            # Filter by state bounds
                            gdf = gdf[gdf.intersects(state_match.unary_union)]
                        else:
                            # Try as county
                            county_match = find_region_by_name(counties, location)
                            if county_match is not None:
                                # Filter by county bounds
                                gdf = gdf[gdf.intersects(county_match.unary_union)]
                            else:
                                # For cities use a basic point and radius approach
                                if location.lower() == "philadelphia":
                                    # Philadelphia coordinates (approx)
                                    philly_point = Point(-75.1652, 39.9526)
                                    # Create a buffer around the point (in degrees, approx 20km)
                                    buffer_distance = 0.2
                                    philly_buffer = philly_point.buffer(buffer_distance)
                                    # Filter polygons that intersect with the buffer
                                    gdf = gdf[gdf.intersects(philly_buffer)]
                                elif location.lower() == "pittsburgh":
                                    # Pittsburgh coordinates (approx)
                                    pitt_point = Point(-79.9959, 40.4406)
                                    buffer_distance = 0.2
                                    pitt_buffer = pitt_point.buffer(buffer_distance)
                                    gdf = gdf[gdf.intersects(pitt_buffer)]
                    except Exception as e:
                        st.warning(f"Could not filter by location: {str(e)}")
                
                if gdf.empty:
                    st.warning(f"No weather data matching the criteria")
                    continue
                
                # Get color scale for the selected parameter
                colormap = get_weather_color_scale(parameter)
                
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
