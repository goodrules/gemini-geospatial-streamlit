import os
import streamlit as st
from dotenv import load_dotenv
from google.genai import types
from datetime import date # Import date for default init_date

# Load environment variables from .env file
load_dotenv()
PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("REGION", "us-central1")
GEMINI_MODEL = "gemini-2.5-flash-preview-04-17"

def setup_page_config():
    """Configure Streamlit page settings"""
    st.set_page_config(page_title="Geospatial AI Assistant", layout="wide")

def init_session_state():
    """Initialize session state variables if they don't exist"""
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
    # Add new state variables for local datasets
    if "flood_zones_loaded" not in st.session_state:
        st.session_state.flood_zones_loaded = False
    if "power_lines_loaded" not in st.session_state:
        st.session_state.power_lines_loaded = False
    # Add weather data state variables
    # Removed 'selected_forecast_date_str' as it's no longer driven by UI
    if "selected_init_date" not in st.session_state:
        st.session_state.selected_init_date = date.today() # Default to today
    if "weather_data_loaded" not in st.session_state:
        st.session_state.weather_data_loaded = False
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
    # Add status message container
    if "status_messages" not in st.session_state:
        st.session_state.status_messages = []
