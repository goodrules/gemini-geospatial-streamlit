import streamlit as st
from data.geospatial_data import initialize_app_data
from utils.streamlit_utils import reset_session_state
from data.weather_data import get_weather_forecast_dates

def render_sidebar():
    """Render the sidebar with settings and examples"""
    with st.sidebar:
        st.header("Settings")
        
        # Data source info
        st.info("Using US States, Counties, and Zip Code data from Google BigQuery public datasets.")
        
        # Weather forecast date filter
        if "weather_forecast_date" not in st.session_state:
            st.session_state.weather_forecast_date = None
            
        forecast_dates = get_weather_forecast_dates()
        if forecast_dates:
            with st.expander("Weather Data Settings"):
                selected_date = st.selectbox(
                    "Filter by forecast date:",
                    options=["All Dates"] + forecast_dates,
                    index=0
                )
                
                if selected_date != "All Dates":
                    st.session_state.weather_forecast_date = selected_date
                else:
                    st.session_state.weather_forecast_date = None
                    
                st.caption("Weather data is available for Pennsylvania only.")
        
        if st.button("Clear Chat"):
            reset_session_state()
            st.rerun()
            
        if st.button("Reload Geospatial Data"):
            # Force reload by clearing the cache for these functions
            st.cache_data.clear()
            initialize_app_data()
            st.rerun()
        
        # Example questions to help users
        render_example_questions()

def render_example_questions():
    """Display example questions users can click on"""
    st.header("Example Questions")
    
    geo_examples = [
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
    
    weather_examples = [
        "Show me the temperature forecast for Pennsylvania",
        "What's the precipitation forecast for Pennsylvania?",
        "Show the wind speed forecast for PA",
        "What's the temperature in Philadelphia area?",
        "Show me the weather forecast for Pittsburgh"
    ]
    
    st.subheader("Geospatial")
    examples = geo_examples
    
    st.subheader("Weather (Pennsylvania only)")
    examples.extend(weather_examples)
    
    for example in examples:
        if st.button(example):
            # Simulate clicking the example
            st.session_state.messages.append({"role": "user", "content": example})
            with st.spinner("Generating response..."):
                from services.gemini_service import get_gemini_response
                raw_response = get_gemini_response(example, st.session_state.history)
                try:
                    import json
                    response_data = json.loads(raw_response)
                    ai_message = response_data.get("response", "Sorry, I couldn't process that request.")
                    map_actions = response_data.get("map_actions", [])
                    st.session_state.map_actions = map_actions
                except json.JSONDecodeError:
                    ai_message = "I encountered an error processing your request. Please try again."
            st.session_state.messages.append({"role": "assistant", "content": ai_message})
            st.rerun() 
