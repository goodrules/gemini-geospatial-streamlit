import streamlit as st
from data.geospatial_data import initialize_app_data
from utils.streamlit_utils import reset_session_state
# Removed unused import: from data.weather_data import get_unique_forecast_dates_str

def render_sidebar():
    """Render the sidebar with settings and examples"""
    with st.sidebar:
        st.header("Settings")
        from datetime import date, timedelta # Import date objects

        # Data source info
        st.info("Using US States, Counties, and Zip Code data from Google BigQuery public datasets.")

        # Weather Init Date Selector
        # Removed unused variable: forecast_date_strs = get_unique_forecast_dates_str(st.session_state.selected_init_date)
        # Display the selector widget
        with st.expander("Weather Data Settings"):
            today = date.today()
            min_date = date(2022, 1, 1)
            # Ensure default selected date isn't before min_date
            default_date = st.session_state.selected_init_date if st.session_state.selected_init_date >= min_date else min_date

            new_init_date = st.date_input(
                "Select Weather Forecast Init Date:",
                value=default_date,
                min_value=min_date,
                max_value=today, # Can't select future dates for init_date
                key="init_date_selector"
            )
            # Update session state if the date changed
            if new_init_date != st.session_state.selected_init_date:
                st.session_state.selected_init_date = new_init_date
                # Clear weather-related cache when init_date changes
                try:
                    from data.weather_data import get_weather_forecast_data
                    get_weather_forecast_data.clear()
                    st.success(f"Weather data cache cleared for new init date: {new_init_date}")
                except Exception as e:
                    st.warning(f"Could not clear weather data cache: {e}")
                st.rerun() # Rerun to fetch new data based on the selected date

            st.caption("Select the initialization date for the weather forecast data (data available back to 2022).")
            
        # Debug panel - displays the raw API request and response
        with st.expander("Debug Panel", expanded=False):
            st.subheader("Last API Exchange")
            
            # Display user prompt
            if st.session_state.messages and len(st.session_state.messages) > 0:
                last_user_msg = next((m for m in reversed(st.session_state.messages) if m["role"] == "user"), None)
                if last_user_msg:
                    st.markdown("#### Last User Prompt:")
                    st.code(last_user_msg["content"], language="text")
            
            # Display system prompt if available
            if hasattr(st.session_state, 'last_system_prompt'):
                st.markdown("#### System Prompt (First 500 chars):")
                prompt_preview = st.session_state.last_system_prompt[:500] + "..." if len(st.session_state.last_system_prompt) > 500 else st.session_state.last_system_prompt
                
                if st.button("Show Full System Prompt"):
                    st.code(st.session_state.last_system_prompt, language="text")
                else:
                    st.code(prompt_preview, language="text")
                
            # Display raw API response if available
            if hasattr(st.session_state, 'last_api_response'):
                st.markdown("#### Raw API Response:")
                try:
                    # Pretty-print JSON
                    import json
                    parsed = json.loads(st.session_state.last_api_response)
                    formatted = json.dumps(parsed, indent=2)
                    
                    # Display map_actions section
                    if "map_actions" in parsed:
                        st.markdown("#### Map Actions:")
                        st.code(json.dumps(parsed["map_actions"], indent=2), language="json")
                    
                    # Option to see full response
                    if st.button("Show Full API Response"):
                        st.code(formatted, language="json")
                    else:
                        # Show a preview
                        preview = formatted[:1000] + "..." if len(formatted) > 1000 else formatted
                        st.code(preview, language="json")
                        
                except:
                    # If can't parse as JSON, show as text
                    st.code(st.session_state.last_api_response, language="text")


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
        "Compare the land area of Travis County, TX and King County, WA",
        "Show me power lines near Philadelphia, PA",
        "What's the land area of ZIP code 10001 in New York?",
    ]
    
    weather_examples = [
        "Show the temperature forecast for California",
        "What is the wind speed forecast for Chicago?",
        "Are any power lines at risk of high wind speed in the next 10 days in Erie County, PA?"
    ]
    
    st.subheader("Geospatial & Weather")
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
