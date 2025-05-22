import streamlit as st
import hashlib
import json
from streamlit_folium import st_folium
from services.map_processor import initialize_map, process_map_actions, get_actions_hash
from utils.streamlit_utils import clear_status_messages, display_status_messages, StatusMessageInterceptor

def render_map():
    """
    Render the interactive map with any active map actions
    
    This redesigned version ensures a fresh map on each new prompt by:
    1. Using a running map counter to force fresh processing
    2. Storing rendering information in session state
    3. Clearing all relevant state between prompts
    """
    st.subheader("Interactive Map")
    
    # Initialize a render counter if it doesn't exist
    if "map_render_counter" not in st.session_state:
        st.session_state.map_render_counter = 0
    
    # Get current map actions and generate hash
    current_actions = st.session_state.map_actions
    actions_hash = get_actions_hash(current_actions)
    
    # Session state keys for storing processed map data
    map_html_key = "processed_map_html"
    last_hash_key = "last_actions_hash"
    
    # Always process the map on each render to ensure freshness
    # The cached HTML approach wasn't working reliably enough for complete resets
    needs_processing = True
    
    # Process the map if needed
    if needs_processing:
        # Clear status messages
        clear_status_messages()
        
        # Get the center and zoom (with proper format conversion)
        default_center = [39.8283, -98.5795]
        default_zoom = 4
        
        # Always reset to default center/zoom on empty actions
        if not current_actions:
            center = default_center
            zoom = default_zoom
        else:
            stored_center = st.session_state.get("map_center", default_center)
            if isinstance(stored_center, dict) and 'lat' in stored_center and 'lng' in stored_center:
                center = [stored_center['lat'], stored_center['lng']]
            else:
                center = stored_center
            
            zoom = st.session_state.get("map_zoom", default_zoom)
        
        # Initialize the base map and process actions
        with StatusMessageInterceptor():
            m = initialize_map(center=center, zoom=zoom)
            
            if isinstance(current_actions, list) and len(current_actions) > 0:
                m = process_map_actions(current_actions, m)
                
            # Save the map as HTML
            # Use a unique counter for render stability
            if "map_render_counter" not in st.session_state:
                st.session_state.map_render_counter = 0
            
            # Increment the counter for future renders
            st.session_state.map_render_counter += 1
            
            # Add a timestamp to the HTML to prevent browser caching
            import time
            timestamp = int(time.time())
            
            # Save map with an anti-cache timestamp
            map_html = f"""
            <!-- Map render {timestamp} -->
            {m.get_root().render()}
            """
            
            # Store in session state
            st.session_state[map_html_key] = map_html
            st.session_state[last_hash_key] = actions_hash
    
    # Display status messages
    display_status_messages()
    
    # Display the map HTML directly from session state
    map_container = st.container(key="map_control")
    with map_container:
        if map_html_key in st.session_state:
            # st.components.v1.html doesn't accept the key parameter, so we use a wrapper container instead
            # to ensure uniqueness with each render
            unique_container_key = f"map_container_{st.session_state.map_render_counter}"
            with st.container(key=unique_container_key):
                st.components.v1.html(
                    st.session_state[map_html_key],
                    height=800,
                    scrolling=False
                )
        else:
            # Show default map
            m = initialize_map()
            map_html = m.get_root().render()
            with st.container(key="default_map_container"):
                st.components.v1.html(
                    map_html,
                    height=800,
                    scrolling=False
                )

