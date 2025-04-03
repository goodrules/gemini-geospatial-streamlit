import os
import json
import streamlit as st
import folium
import geopandas as gpd
from streamlit_folium import st_folium
from google.oauth2 import service_account
from google import genai
from google.genai import types
import numpy as np
import pandas as pd
from folium.plugins import HeatMap
from google.cloud import bigquery
import shapely.wkt

# Configure page
st.set_page_config(page_title="Geospatial AI Assistant", layout="wide")

# Initialize session state variables if they don't exist
if "messages" not in st.session_state:
    st.session_state.messages = []
if "map_actions" not in st.session_state:
    st.session_state.map_actions = []
if "data_initialized" not in st.session_state:
    st.session_state.data_initialized = False
if "states_loaded" not in st.session_state:
    st.session_state.states_loaded = False
if "counties_loaded" not in st.session_state:
    st.session_state.counties_loaded = False
if "zipcodes_loaded" not in st.session_state:
    st.session_state.zipcodes_loaded = False
if "history" not in st.session_state:
    st.session_state.history = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text="Hello")]
        ),
        types.Content(
            role="model",
            parts=[types.Part.from_text(text="""{"response": "Hello! I'm your geospatial assistant. I can help with location analysis, mapping, and spatial queries. What would you like to explore today?", "map_actions": []}""")]
        ),
    ]

def initialize_app_data():
    """Initialize and cache all geospatial data at app startup."""
    with st.spinner("Loading geospatial data..."):
        try:
            states = get_us_states()
            if states is not None:
                st.session_state.states_loaded = True
            else:
                st.session_state.states_loaded = False
                st.warning("Failed to load US states data.")
            
            counties = get_us_counties()
            if counties is not None:
                st.session_state.counties_loaded = True
            else:
                st.session_state.counties_loaded = False
                st.warning("Failed to load US counties data.")
            
            zipcodes = get_us_zipcodes()
            if zipcodes is not None:
                st.session_state.zipcodes_loaded = True
            else:
                st.session_state.zipcodes_loaded = False
                st.warning("Failed to load US ZIP codes data.")
            
            st.session_state.data_initialized = True
            
            if all([st.session_state.states_loaded, 
                   st.session_state.counties_loaded, 
                   st.session_state.zipcodes_loaded]):
                st.success("All geospatial data loaded successfully!")
            else:
                missing = []
                if not st.session_state.states_loaded:
                    missing.append("states")
                if not st.session_state.counties_loaded:
                    missing.append("counties")
                if not st.session_state.zipcodes_loaded:
                    missing.append("ZIP codes")
                st.warning(f"Some data sources failed to load: {', '.join(missing)}")
            
        except Exception as e:
            st.error(f"Error initializing geospatial data: {str(e)}")
            st.session_state.data_initialized = False


# Initialize Gemini client
@st.cache_resource
def initialize_gemini_client():
    PROJECT_ID = os.environ.get("PROJECT_ID")
    REGION = os.environ.get("REGION", "us-central1")
    
    if os.path.exists(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')):
        credentials = service_account.Credentials.from_service_account_file(
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'],
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        client = genai.Client(
            vertexai=True, 
            project=PROJECT_ID, 
            location=REGION, 
            credentials=credentials
        )
    else:
        st.error("Google application credentials not found. Please set the GOOGLE_APPLICATION_CREDENTIALS environment variable.")
        client = None
    
    return client

# BigQuery client initialization
@st.cache_resource
def initialize_bigquery_client():
    """Initialize and return a BigQuery client using the same credentials as Gemini."""
    if os.path.exists(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')):
        credentials = service_account.Credentials.from_service_account_file(
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'],
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        client = bigquery.Client(credentials=credentials, project=credentials.project_id)
        return client
    else:
        st.error("Google application credentials not found. Please set the GOOGLE_APPLICATION_CREDENTIALS environment variable.")
        return None

# Function to fetch and cache US states data from BigQuery
@st.cache_data(ttl=3600)
def get_us_states():
    """Fetch US states data from Google BigQuery public dataset."""
    try:
        client = initialize_bigquery_client()
        if not client:
            st.warning("Using fallback dataset as BigQuery client could not be initialized.")
            return get_us_states_fallback()
            
        # Query to fetch US states data
        query = """
        SELECT 
            geo_id, 
            state, 
            state_name, 
            state_fips_code, 
            int_point_lat, 
            int_point_lon,
            area_land_meters,
            area_water_meters,
            ST_AsText(state_geom) as state_geom_wkt
        FROM 
            `bigquery-public-data.geo_us_boundaries.states`
        """
        
        # Run the query
        df = client.query(query).to_dataframe()
        
        # Convert WKT geometry to GeoDataFrame
        geometry = df['state_geom_wkt'].apply(shapely.wkt.loads)
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        
        # Add a value column for visualization
        gdf['value'] = np.random.randint(1, 100, size=len(gdf))
        
        # Cleanup
        if 'state_geom_wkt' in gdf.columns:
            gdf = gdf.drop(columns=['state_geom_wkt'])
            
        return gdf
        
    except Exception as e:
        st.error(f"Error fetching data from BigQuery: {e}")
        return get_us_states_fallback()

# Function to fetch and cache US counties data from BigQuery
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_us_counties():
    """Fetch US counties data from Google BigQuery public dataset."""
    try:
        client = initialize_bigquery_client()
        if not client:
            st.warning("Using fallback dataset as BigQuery client could not be initialized.")
            return None
            
        # Query to fetch US counties data
        query = """
        SELECT 
            geo_id, 
            state_fips_code,
            county_fips_code,
            county_name,
            lsad_name,
            area_land_meters,
            area_water_meters,
            int_point_lat, 
            int_point_lon,
            ST_AsText(county_geom) as county_geom_wkt
        FROM 
            `bigquery-public-data.geo_us_boundaries.counties`
        """
        
        # Run the query
        df = client.query(query).to_dataframe()
        
        # Convert WKT geometry to GeoDataFrame
        geometry = df['county_geom_wkt'].apply(shapely.wkt.loads)
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        
        # Add a value column for visualization
        gdf['value'] = np.random.randint(1, 100, size=len(gdf))
        
        # Cleanup
        if 'county_geom_wkt' in gdf.columns:
            gdf = gdf.drop(columns=['county_geom_wkt'])
            
        return gdf
        
    except Exception as e:
        st.error(f"Error fetching county data from BigQuery: {e}")
        return None

# Function to fetch and cache US zip codes data from BigQuery
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_us_zipcodes():
    """Fetch US zip codes data from Google BigQuery public dataset."""
    try:
        client = initialize_bigquery_client()
        if not client:
            st.warning("Using fallback dataset as BigQuery client could not be initialized.")
            return None
            
        # Query to fetch US zip codes data
        query = """
        SELECT 
            zip_code, 
            city, 
            county,
            state_fips_code,
            state_code,
            state_name,
            fips_class_code,
            mtfcc_feature_class_code,
            functional_status,
            area_land_meters,
            area_water_meters,
            internal_point_lat, 
            internal_point_lon,
            ST_AsText(internal_point_geom) as internal_point_geom_wkt,
            ST_AsText(zip_code_geom) as zip_code_geom_wkt
        FROM 
            `bigquery-public-data.geo_us_boundaries.zip_codes`
        """
        
        # Run the query
        df = client.query(query).to_dataframe()
        
        # Convert WKT geometry to GeoDataFrame
        geometry = df['zip_code_geom_wkt'].apply(shapely.wkt.loads)
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        
        # Add a value column for visualization
        gdf['value'] = np.random.randint(1, 100, size=len(gdf))
        
        # Cleanup
        if 'zip_code_geom_wkt' in gdf.columns:
            gdf = gdf.drop(columns=['zip_code_geom_wkt'])
        if 'internal_point_geom_wkt' in gdf.columns:
            gdf = gdf.drop(columns=['internal_point_geom_wkt'])
            
        return gdf
        
    except Exception as e:
        st.error(f"Error fetching zip code data from BigQuery: {e}")
        return None

# Fallback function to use if BigQuery connection fails
def get_us_states_fallback():
    """Fallback to GeoPandas built-in datasets if BigQuery fails."""
    try:
        states = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        us = states[states['iso_a3'] == 'USA'].copy()
        us['value'] = np.random.randint(1, 100, size=len(us))
        us['state_name'] = 'United States'  # Add placeholder state_name
        us['state'] = 'US'  # Add placeholder state abbreviation
        us['state_fips_code'] = '00'  # Add placeholder FIPS code
        return us
    except Exception as e:
        st.error(f"Error loading fallback US states: {e}")
        return None

# Generate content config for JSON output
def get_generate_content_config():
    #tools = [types.Tool(google_search=types.GoogleSearch())]
    return types.GenerateContentConfig(
        temperature=0.2,
        top_p=0.95,
        max_output_tokens=8192,
        #tools=tools,
        response_mime_type="application/json",
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
        ]
    )

# Function to get response from Gemini
def get_gemini_response(prompt, history):
    client = initialize_gemini_client()
    if not client:
        return json.dumps({
            "response": "Error: Gemini client not initialized",
            "map_actions": []
        })
    
    model = "gemini-2.0-flash-001" # gemini-2.0-flash-001, gemini-2.0-flash-lite-001, gemini-2.5-pro-exp-03-25, gemini-2.0-flash-thinking-exp-01-21
    config = get_generate_content_config()
    
    system_prompt = """You are a geospatial analysis assistant. 
    Your responses must always be in valid JSON format with the following structure:
    {
        "response": "Your text response to the user",
        "map_actions": [
            {
                "action_type": "add_marker",
                "lat": 37.7749,
                "lon": -122.4194,
                "popup": "San Francisco",
                "color": "blue"
            },
            {
                "action_type": "highlight_region",
                "region_name": "Fulton",
                "region_type": "county",
                "state_name": "Georgia",  # Optional, but helpful for counties
                "color": "red",
                "fill_color": "orange",
                "fill_opacity": 0.5
            },
            {
                "action_type": "highlight_region",
                "region_name": "Georgia",
                "region_type": "state",
                "color": "blue",
                "fill_color": "lightblue",
                "fill_opacity": 0.5
            },
            {
                "action_type": "highlight_region",
                "region_name": "30303",
                "region_type": "zipcode",
                "state_name": "Georgia",  # Optional, helps narrow results
                "county_name": "Fulton",  # Optional, helps narrow results
                "color": "purple",
                "fill_color": "lavender",
                "fill_opacity": 0.5
            },
            {
                "action_type": "fit_bounds",
                "bounds": [[south, west], [north, east]]
            },
            {
                "action_type": "add_circle",
                "lat": 37.7749,
                "lon": -122.4194,
                "radius": 5000,
                "popup": "5km radius",
                "color": "green"
            },
            {
                "action_type": "add_heatmap",
                "data_points": [[lat1, lon1, intensity1], [lat2, lon2, intensity2], ...],
                "radius": 25
            },
            {
                "action_type": "add_line",
                "locations": [[lat1, lon1], [lat2, lon2], ...],
                "popup": "Line description",
                "color": "blue",
                "weight": 3
            },
            {
                "action_type": "add_polygon",
                "locations": [[lat1, lon1], [lat2, lon2], [lat3, lon3], ...],
                "popup": "Polygon description",
                "color": "red",
                "fill_color": "pink",
                "fill_opacity": 0.5
            }
        ]
    }

    Supported region_type values for highlight_region: "state", "county", "zipcode", "country", "continent"
    Supported action_types:
    - add_marker: Add a marker at specified coordinates
    - highlight_region: Highlight a specific region (state, county, country, etc)
    - fit_bounds: Adjust map view to specified bounds
    - add_circle: Add a circle with specified radius
    - add_heatmap: Add a heatmap from data points
    - add_line: Add a line connecting two or more points
    - add_polygon: Add a polygon defined by three or more points

    For state highlighting:
    {
        "action_type": "highlight_region",
        "region_name": "Georgia",  # or "GA"
        "region_type": "state",
        "color": "blue",
        "fill_color": "lightblue",
        "fill_opacity": 0.5
    }

    For county highlighting:
    {
        "action_type": "highlight_region",
        "region_name": "Fulton",
        "region_type": "county",
        "state_name": "Georgia",  # Optional but helps disambiguate counties with the same name
        "color": "red",
        "fill_color": "pink",
        "fill_opacity": 0.5
    }

    For zipcode highlighting:
    {
        "action_type": "highlight_region",
        "region_name": "30303",
        "region_type": "zipcode",
        "state_name": "Georgia",  # Optional, helps narrow results
        "county_name": "Fulton",  # Optional, helps narrow results
        "color": "purple",
        "fill_color": "lavender",
        "fill_opacity": 0.5
    }

    The application has detailed US states and counties data including boundaries, FIPS codes, and geographic centers.

    Always format your response as valid JSON. For geospatial questions, include relevant map_actions.
    Use concise, clear responses.
    """
    
    try:
        new_content = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )
        ]
        
        # Add system prompt as a user message at the beginning if not already present
        if not any("geospatial analysis assistant" in str(c) for c in history):
            history.insert(0, types.Content(
                role="user", 
                parts=[types.Part.from_text(text=system_prompt)]
            ))
        
        response = client.models.generate_content(
            model=model,
            contents=history + new_content,
            config=config
        )
        
        # Add the new exchange to history
        history.append(new_content[0])
        history.append(types.Content(
            role="model",
            parts=[types.Part.from_text(text=response.text)]
        ))
        
        return response.text
    except Exception as e:
        return json.dumps({
            "response": f"Error: {str(e)}",
            "map_actions": []
        })

# Initialize map
def initialize_map():
    m = folium.Map(location=[39.8283, -98.5795], zoom_start=4, tiles="OpenStreetMap")
    return m

# Load world countries data
@st.cache_data
def get_world_countries():
    try:
        countries = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        # Add a demo value column
        countries['value'] = np.random.randint(1, 100, size=len(countries))
        return countries
    except Exception as e:
        st.error(f"Error loading world countries: {e}")
        return None

# Create a function to get major cities
@st.cache_data
def get_major_cities():
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

# Find a region by name with fuzzy matching
def find_region_by_name(gdf, region_name, column_names=None):
    """Use fuzzy matching to find a region in a GeoDataFrame."""
    if gdf is None or len(gdf) == 0:
        return None

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
    
    # Try exact match first
    for col in search_columns:
        exact_matches = gdf[gdf[col].str.lower() == region_name.lower()]
        if len(exact_matches) > 0:
            return exact_matches
    
    # Try contains match
    for col in search_columns:
        partial_matches = gdf[gdf[col].str.lower().str.contains(region_name.lower())]
        if len(partial_matches) > 0:
            return partial_matches
    
    # No match found
    return None

# Process map actions
def process_map_actions(actions, m):
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
            
            # Find the region
            region = find_region_by_name(gdf, region_name)
            
            if region is not None:
                # Create a tooltip with region information
                if region_type.lower() == "state":
                    # For states, add state-specific information
                    tooltip_html = f"""
                    <div style="min-width: 180px;">
                        <h4>{region['state_name'].iloc[0]}</h4>
                        <p><b>State Code:</b> {region['state'].iloc[0]}</p>
                        <p><b>FIPS Code:</b> {region['state_fips_code'].iloc[0]}</p>
                        <p><b>Land Area:</b> {region['area_land_meters'].iloc[0]/1e6:.2f} sq km</p>
                        <p><b>Water Area:</b> {region['area_water_meters'].iloc[0]/1e6:.2f} sq km</p>
                    </div>
                    """
                elif region_type.lower() == "county":
                    # County-specific tooltip
                    tooltip_html = f"""
                    <div style="min-width: 180px;">
                        <h4>{region['county_name'].iloc[0]} {region['lsad_name'].iloc[0]}</h4>
                        <p><b>State FIPS:</b> {region['state_fips_code'].iloc[0]}</p>
                        <p><b>County FIPS:</b> {region['county_fips_code'].iloc[0]}</p>
                        <p><b>Land Area:</b> {region['area_land_meters'].iloc[0]/1e6:.2f} sq km</p>
                        <p><b>Water Area:</b> {region['area_water_meters'].iloc[0]/1e6:.2f} sq km</p>
                    </div>
                    """
                elif region_type.lower() in ["zipcode", "zip_code", "zip"]:
                    # Zip code-specific tooltip
                    tooltip_html = f"""
                    <div style="min-width: 180px;">
                        <h4>ZIP Code: {region['zip_code'].iloc[0]}</h4>
                        <p><b>City:</b> {region['city'].iloc[0]}</p>
                        <p><b>County:</b> {region['county'].iloc[0]}</p>
                        <p><b>State:</b> {region['state_name'].iloc[0]} ({region['state_code'].iloc[0]})</p>
                        <p><b>Land Area:</b> {region['area_land_meters'].iloc[0]/1e6:.2f} sq km</p>
                        <p><b>Water Area:</b> {region['area_water_meters'].iloc[0]/1e6:.2f} sq km</p>
                    </div>
                    """
                else:
                    # Generic tooltip for other region types
                    tooltip_html = f"<div><h4>{region_name}</h4></div>"
                
                # Add the GeoJSON for this region with tooltip
                geo_layer = folium.GeoJson(
                    region.__geo_interface__,
                    name=f"{region_name}",
                    style_function=lambda x: {
                        'fillColor': action.get("fill_color", "#ff7800"),
                        'color': action.get("color", "black"),
                        'weight': 2,
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
                
                # Add circle center to bounds, plus points at radius distance in cardinal directions
                all_bounds.append([lat, lon])
                # We could also add points at the circle's edge in 4 directions to better represent the circle's extent
                # but this might be overkill for most use cases
            
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

# UI Layout
st.title("Geospatial AI Assistant")

# Two-column layout
col1, col2 = st.columns([1, 3])

with col1:
    # Display chat interface
    st.subheader("Chat with the AI")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Chat input
    prompt = st.chat_input("Ask about locations, spatial analysis, etc.")
    if prompt:
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        # Get AI response
        with st.spinner("Generating response..."):
            raw_response = get_gemini_response(prompt, st.session_state.history)
            
            try:
                response_data = json.loads(raw_response)
                ai_message = response_data.get("response", "Sorry, I couldn't process that request.")
                map_actions = response_data.get("map_actions", [])
                
                # Update map actions in session state
                st.session_state.map_actions = map_actions
                
            except json.JSONDecodeError:
                ai_message = "I encountered an error processing your request. Please try again."
        
        # Display AI response
        with st.chat_message("assistant"):
            st.write(ai_message)
        
        # Add AI message to chat history
        st.session_state.messages.append({"role": "assistant", "content": ai_message})

with col2:
    # Display map
    st.subheader("Interactive Map")
    
    # Initialize base map
    m = initialize_map()
    
    # Apply any map actions from the session state
    if isinstance(st.session_state.map_actions, list) and len(st.session_state.map_actions) > 0:
        m = process_map_actions(st.session_state.map_actions, m)
    
    # Display the map
    st_folium(m, width=900, height=800)

# Sidebar with additional options
with st.sidebar:
    st.header("Settings")
    
    # Data source info
    st.info("Using US States, Counties, and Zip Code data from Google BigQuery public datasets.")
    
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.session_state.map_actions = []
        st.session_state.history = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text="Hello")]
            ),
            types.Content(
                role="model",
                parts=[types.Part.from_text(text="""{"response": "Hello! I'm your geospatial assistant. I can help with location analysis, mapping, and spatial queries. What would you like to explore today?", "map_actions": []}""")]
            ),
        ]
        st.rerun()

    if st.button("Reload Geospatial Data"):
        # Force reload by clearing the cache for these functions
        st.cache_data.clear()
        initialize_app_data()
        st.rerun()
    
    # Example questions to help users
    st.header("Example Questions")
    examples = [
        "Show me the 10 largest cities in the United States",
        "Highlight Fulton County, Georgia on the map",
        "Which state has the largest land area?",
        "Draw a line connecting New York and Los Angeles",
        "Compare the land area of Travis County, TX and King County, WA",
        "Show all counties in Florida",
        "Highlight ZIP code 90210 on the map",
        "What's the land area of ZIP code 10001 in New York?",
        "Show me all ZIP codes in Miami, Florida"
    ]
    
    for example in examples:
        if st.button(example):
            # Simulate clicking the example
            st.session_state.messages.append({"role": "user", "content": example})
            with st.spinner("Generating response..."):
                raw_response = get_gemini_response(example, st.session_state.history)
                try:
                    response_data = json.loads(raw_response)
                    ai_message = response_data.get("response", "Sorry, I couldn't process that request.")
                    map_actions = response_data.get("map_actions", [])
                    st.session_state.map_actions = map_actions
                except json.JSONDecodeError:
                    ai_message = "I encountered an error processing your request. Please try again."
            st.session_state.messages.append({"role": "assistant", "content": ai_message})
            st.rerun()
