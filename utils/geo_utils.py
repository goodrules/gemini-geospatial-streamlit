import streamlit as st
import geopandas as gpd
import numpy as np
from utils.streamlit_utils import add_status_message

@st.cache_data
def get_world_countries():
    """Load world countries data"""
    try:
        countries = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        # Add a demo value column
        countries['value'] = np.random.randint(1, 100, size=len(countries))
        return countries
    except Exception as e:
        st.error(f"Error loading world countries: {e}")
        return None

@st.cache_data
def get_major_cities():
    """Create a simple point dataset for major cities"""
    # Create a simple point dataset for major cities
    cities_data = {
        'name': ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 
                'Philadelphia', 'San Antonio', 'San Diego', 'Dallas', 'San Jose',
                'Boston', 'Austin', 'Atlanta', 'Miami', 'Denver'],
        'lat': [40.7128, 34.0522, 41.8781, 29.7604, 33.4484,
                39.9526, 29.4241, 32.7157, 32.7767, 37.3382,
                42.3601, 30.2672, 33.7490, 25.7617, 39.7392],
        'lon': [-74.0060, -118.2437, -87.6298, -95.3698, -112.0740,
                -75.1652, -98.4936, -117.1611, -96.7970, -121.8863,
                -71.0589, -97.7431, -84.3880, -80.1918, -104.9903],
        'population': [8419000, 3980000, 2716000, 2328000, 1680000,
                    1584000, 1547000, 1427000, 1345000, 1031000,
                    695000, 978000, 524000, 463000, 716000]
    }
    
    cities = gpd.GeoDataFrame(
        cities_data, 
        geometry=gpd.points_from_xy(cities_data['lon'], cities_data['lat'])
    )
    return cities

def find_region_by_name(gdf, region_name, column_names=None):
    """Use fuzzy matching to find a region in a GeoDataFrame."""
    # Special case for Crawford County for debugging
    if region_name and isinstance(region_name, str) and "crawford" in region_name.lower():
        add_status_message = getattr(st, "warning", print)
        add_status_message(f"Crawford County search detected: '{region_name}'")
        
        # If we're looking in counties and this is a Crawford County search
        if 'county_name' in gdf.columns:
            crawford_matches = gdf[gdf['county_name'].str.lower() == "crawford"]
            if not crawford_matches.empty:
                add_status_message(f"Found Crawford County by direct lookup")
                return crawford_matches
    if gdf is None or len(gdf) == 0:
        return None
        
    # Check if the input is empty
    if not region_name or not isinstance(region_name, str):
        return None
    
    # Normalize input by removing trailing "County" if present and stripping spaces
    # This is specifically to handle cases like "Crawford County" -> "Crawford"
    normalized_name = region_name.lower().strip()
    if normalized_name.endswith(" county"):
        normalized_name = normalized_name[:-7].strip()  # Remove " county"
    
    # Special case for Crawford County
    if normalized_name == "crawford" or normalized_name == "crawford county":
        add_debug_message = getattr(st, "write", print)
        add_debug_message(f"Looking for Crawford County specifically")
        
    # Add county suffix for common counties if not already present
    # This specifically helps with the case where user just types "Crawford"
    if normalized_name in ["crawford", "philadelphia", "allegheny", "montgomery", "bucks", "fulton"]:
        if not region_name.lower().endswith(" county"):
            # Only print this if st.write is available
            add_debug_message = getattr(st, "write", print)
            add_debug_message(f"Adding 'County' suffix to {normalized_name}")
            normalized_name = f"{normalized_name} county"
    
    # Handle ZIP codes
    if 'zip_code' in gdf.columns:
        exact_matches = gdf[gdf['zip_code'] == region_name]
        if len(exact_matches) > 0:
            return exact_matches
        
    # Define columns to search - prioritize columns from BigQuery data
    if column_names is None:
        # Try common column names for region names
        column_names = ['state_name', 'state', 'county_name', 'county', 'name', 'NAME', 'zip_code',
                       'admin', 'ADMIN', 'region', 'REGION', 'city']
    
    # Ensure we only check columns that exist
    search_columns = [col for col in column_names if col in gdf.columns]
    
    # If no matching columns, try all string columns
    if not search_columns:
        search_columns = [col for col in gdf.columns 
                         if gdf[col].dtype == 'object' and col != 'geometry']
    
    # No string columns to search
    if not search_columns:
        return None
    
    # Try exact match first - with both original and normalized name
    for col in search_columns:
        # Try original name first
        exact_matches = gdf[gdf[col].str.lower() == region_name.lower()]
        if len(exact_matches) > 0:
            return exact_matches
            
        # Then try normalized name (without "County")
        if normalized_name != region_name.lower():
            exact_matches = gdf[gdf[col].str.lower() == normalized_name]
            if len(exact_matches) > 0:
                return exact_matches
    
    # Try contains match
    for col in search_columns:
        # Try original name first
        partial_matches = gdf[gdf[col].str.lower().str.contains(region_name.lower())]
        if len(partial_matches) > 0:
            return partial_matches
            
        # Then try normalized name (without "County")
        if normalized_name != region_name.lower():
            partial_matches = gdf[gdf[col].str.lower().str.contains(normalized_name)]
            if len(partial_matches) > 0:
                return partial_matches
    
    # No match found
    return None 
