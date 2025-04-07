import streamlit as st
from streamlit_folium import st_folium
from services.map_processor import initialize_map, process_map_actions

def render_map():
    """Render the interactive map with any active map actions"""
    st.subheader("Interactive Map")
    
    # Initialize base map
    m = initialize_map()
    
    # Apply any map actions from the session state
    if isinstance(st.session_state.map_actions, list) and len(st.session_state.map_actions) > 0:
        m = process_map_actions(st.session_state.map_actions, m)
    
    # Display the map
    st_folium(m, width=900, height=800) 
