import streamlit as st
from config.settings import setup_page_config, init_session_state
from components.sidebar import render_sidebar
from components.chat import render_chat_interface
from components.map import render_map

# Configure page
setup_page_config()

# Initialize session state
init_session_state()

# Two-column layout
col1, col2 = st.columns([1, 3])

with col1:
    # Display chat interface
    render_chat_interface()

with col2:
    # Display map
    render_map()

# Render sidebar
render_sidebar()
