import streamlit as st
from data.geospatial_data import initialize_app_data
from utils.streamlit_utils import reset_session_state
from data.weather_data import get_unique_forecast_dates_str # Use the new function

def render_sidebar():
    """Render the sidebar with settings and examples"""
    with st.sidebar:
        st.header("Settings")
        
        # Data source info
        st.info("Using US States, Counties, and Zip Code data from Google BigQuery public datasets.")

        # Weather forecast date filter (uses selected_forecast_date_str session state)
        forecast_date_strs = get_unique_forecast_dates_str()
        if forecast_date_strs:
            with st.expander("Weather Data Settings"):
                # Determine the index for the selectbox based on current session state
                current_selection = st.session_state.get("selected_forecast_date_str")
                options = ["All Dates"] + forecast_date_strs
                try:
                    index = options.index(current_selection) if current_selection in options else 0
                except ValueError:
                    index = 0 # Default to "All Dates" if current selection not found

                selected_date_str = st.selectbox(
                    "Filter by forecast date:",
                    options=options,
                    index=index,
                    key="weather_date_selector" # Add a key for stability
                )

                # Update session state based on selection
                if selected_date_str != st.session_state.selected_forecast_date_str:
                    if selected_date_str != "All Dates":
                        st.session_state.selected_forecast_date_str = selected_date_str
                    else:
                        st.session_state.selected_forecast_date_str = None
                    # st.rerun() # REMOVED: Let Streamlit handle rerun on widget change

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
        "Draw a line connecting New York and Los Angeles",
        "Compare the land area of Travis County, TX and King County, WA",
        "Show all counties in Florida",
        "Highlight ZIP code 90210 on the map",
        "What's the land area of ZIP code 10001 in New York?",
    ]
    
    weather_examples = [
        "Show me the temperature forecast for Pennsylvania",
        "What's the precipitation forecast for Pennsylvania?",
        "Show the wind speed forecast for PA",
        "What's the temperature in Philadelphia area?",
        "Are any power lines at risk of high wind speed in the next 10 days?"
    ]
    
    st.subheader("Geospatial & Weather (Pennsylvania only)")
    examples = geo_examples + weather_examples
    
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
