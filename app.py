import streamlit as st
import os
from config.settings import setup_page_config, init_session_state
from components.sidebar import render_sidebar
from components.chat import render_chat_interface
from components.map import render_map

def load_css(file_path):
    with open(file_path, "r") as f:
        return f.read()

# Configure page
setup_page_config()

# Initialize session state
init_session_state()

css_file = os.path.join("tw", "app.css")

if os.path.exists(css_file):
    css = load_css(css_file)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
else:
    st.error(f"CSS file not found: {css_file}")

# Two-column layout
col1, col2 = st.columns([1, 3])

with col1:
    chat_container = st.container(key="chat")    
    with chat_container:
        # Display chat interface
        render_chat_interface()

with col2:
    map_container = st.container(key="map")
    with map_container:
        # Display map
        render_map()

# Render sidebar
render_sidebar()
