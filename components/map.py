import streamlit as st
from streamlit_folium import st_folium
from services.map_processor import initialize_map, process_map_actions
from utils.streamlit_utils import clear_status_messages, display_status_messages, StatusMessageInterceptor

def render_map():
    """Render the interactive map with any active map actions"""
    st.subheader("Interactive Map")
    
    # Clear any previous messages at the beginning of rendering
    clear_status_messages()
    
    # First render of status messages box (may be empty)
    display_status_messages()
    
    # Map initialization
    m = initialize_map()
    
    # Wrap map action processing with status message interception
    if isinstance(st.session_state.map_actions, list) and len(st.session_state.map_actions) > 0:
        with StatusMessageInterceptor():
            # Process the map actions while intercepting status messages
            m = process_map_actions(st.session_state.map_actions, m)
            
    # Display the map
    st_folium(m, width=900, height=800)
    
    # Display status messages after processing
    display_status_messages()
