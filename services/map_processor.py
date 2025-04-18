import folium
import streamlit as st
import pandas as pd
import json
from folium.plugins import HeatMap
from data.geospatial_data import get_us_states, get_us_counties, get_us_zipcodes
from data.geospatial_data import (get_us_states, get_us_counties, get_us_zipcodes,
                                 get_crawford_flood_zones, get_pa_power_lines)
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
