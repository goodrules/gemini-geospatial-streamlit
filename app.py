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

# Configure page
st.set_page_config(page_title="Geospatial AI Assistant", layout="wide")

# Initialize session state variables if they don't exist
if "messages" not in st.session_state:
    st.session_state.messages = []
if "map_actions" not in st.session_state:
    st.session_state.map_actions = []
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

# Initialize Gemini client
@st.cache_resource
def initialize_gemini_client():
    PROJECT_ID = "mg-ce-demos"
    REGION = "us-central1"
    
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

# Generate content config for JSON output
def get_generate_content_config():
    return types.GenerateContentConfig(
        temperature=0.2,
        top_p=0.95,
        max_output_tokens=4096,
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
    
    model = "gemini-2.0-flash-001"
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
                "region_name": "Georgia",
                "region_type": "state",
                "color": "red",
                "fill_color": "orange",
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

    Supported region_type values for highlight_region: "state", "country", "continent"
    Supported action_types:
    - add_marker: Add a marker at specified coordinates
    - highlight_region: Highlight a specific region (state, country, etc)
    - fit_bounds: Adjust map view to specified bounds
    - add_circle: Add a circle with specified radius
    - add_heatmap: Add a heatmap from data points
    - add_line: Add a line connecting two or more points
    - add_polygon: Add a polygon defined by three or more points

    For state highlighting (like "Highlight Georgia"), use:
    {
        "action_type": "highlight_region",
        "region_name": "Georgia",
        "region_type": "state",
        "color": "blue",
        "fill_color": "lightblue",
        "fill_opacity": 0.5
    }

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
    m = folium.Map(location=[0, 0], zoom_start=2, tiles="OpenStreetMap")
    return m

# Load US states data with more robust error handling
@st.cache_data
def get_us_states():
    try:
        # Use GeoPandas' built-in datasets
        states = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        us = states[states['iso_a3'] == 'USA'].copy()
        # Add a demo value column
        us['value'] = np.random.randint(1, 100, size=len(us))
        return us
    except Exception as e:
        st.error(f"Error loading US states: {e}")
        # Create a minimal fallback dataset
        return None

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
                'London', 'Paris', 'Tokyo', 'Beijing', 'Mumbai'],
        'lat': [40.7128, 34.0522, 41.8781, 29.7604, 33.4484,
                39.9526, 29.4241, 32.7157, 32.7767, 37.3382,
                51.5074, 48.8566, 35.6762, 39.9042, 19.0760],
        'lon': [-74.0060, -118.2437, -87.6298, -95.3698, -112.0740,
                -75.1652, -98.4936, -117.1611, -96.7970, -121.8863,
                -0.1278, 2.3522, 139.6503, 116.4074, 72.8777],
        'population': [8419000, 3980000, 2716000, 2328000, 1680000,
                    1584000, 1547000, 1427000, 1345000, 1031000,
                    8982000, 2148000, 13960000, 21540000, 12480000]
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
        
    # Define columns to search
    if column_names is None:
        # Try common column names for region names
        column_names = ['name', 'NAME', 'Name', 'state', 'STATE', 'State', 
                       'admin', 'ADMIN', 'Admin', 'region', 'REGION', 'Region']
    
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
        match = gdf[gdf[col].str.lower() == region_name.lower()]
        if len(match) > 0:
            return match
    
    # Try contains match
    for col in search_columns:
        match = gdf[gdf[col].str.lower().str.contains(region_name.lower())]
        if len(match) > 0:
            return match
    
    # No match found
    return None

# Process map actions
def process_map_actions(actions, m):
    if not actions or not isinstance(actions, list):
        return m
    
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
                
        elif action_type == "highlight_region":
            region_name = action.get("region_name")
            region_type = action.get("region_type", "state")
            
            if not region_name:
                continue
                
            # Get the appropriate dataset based on region type
            gdf = None
            if region_type.lower() == "state":
                gdf = get_us_states()
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
                    
                    # Fit bounds to this region
                    bounds = region.total_bounds
                    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
                continue
            
            # Find the region
            region = find_region_by_name(gdf, region_name)
            
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
                
                # Fit bounds to this region
                bounds = region.total_bounds
                m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
            else:
                st.write(f"Could not find region: {region_name}")
                
        elif action_type == "fit_bounds":
            bounds = action.get("bounds")
            if bounds and isinstance(bounds, list) and len(bounds) == 2:
                m.fit_bounds(bounds)
                
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
            
        elif action_type == "add_heatmap":
            data_points = action.get("data_points", [])
            if data_points and isinstance(data_points, list):
                HeatMap(
                    data=data_points,
                    radius=action.get("radius", 15),
                    blur=action.get("blur", 10),
                    gradient=action.get("gradient", None)
                ).add_to(m)
                
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
    
    return m

# UI Layout
st.title("Geospatial AI Assistant")

# Two-column layout
col1, col2 = st.columns([1, 2])

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
    st_folium(m, width=800, height=600)

# Sidebar with additional options
with st.sidebar:
    st.header("Settings")
    
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
    
    # Example questions to help users
    st.header("Example Questions")
    examples = [
        "Show me the 10 largest cities in the United States",
        "Highlight Georgia on the map",
        "Draw a line connecting New York and Los Angeles",
        "Create a polygon around the Great Lakes region",
        "Show me the distance between Chicago and Miami",
        "Highlight the continent of Asia"
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