import streamlit as st
from data.geospatial_data import initialize_app_data
from utils.streamlit_utils import reset_session_state, extract_date_from_prompt
# Removed unused import: from data.weather_data import get_unique_forecast_dates_str
from datetime import date, timedelta # Import date objects

def render_sidebar():
    """Render the sidebar with settings and examples"""
    with st.sidebar:
        st.header("Settings")

        # Display current init_date clearly - first element and yellow color
        current_init_date = st.session_state.get("selected_init_date", date.today())
        formatted_date = current_init_date.strftime("%B %d, %Y") if hasattr(current_init_date, "strftime") else str(current_init_date)
        st.warning(f"📅 **Current forecast date:** {formatted_date}")

        # Info about date specification in prompts
        st.info("Specify dates in your prompt like \"May 15, 2023\" to use weather data from that date.")
        
        # Data source info
        st.info("Using US States, Counties, and Zip Code data from Google BigQuery public datasets.")
        
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

        # Prompt template controls
        with st.expander("Prompt Template Controls", expanded=False):
            st.subheader("Feature Toggles")
            st.caption("Enable or disable specific capabilities in the prompt template.")
            
            # Initialize session state values if they don't exist
            if "include_power_lines" not in st.session_state:
                st.session_state.include_power_lines = True
            if "include_wind_risk" not in st.session_state:
                st.session_state.include_wind_risk = True
            if "debug_templates" not in st.session_state:
                st.session_state.debug_templates = False
                
            # Create toggles for each feature
            power_lines_toggle = st.toggle(
                "Power Lines Information", 
                value=st.session_state.include_power_lines,
                help="Include instructions about power lines in the prompt"
            )
            wind_risk_toggle = st.toggle(
                "Wind Risk Analysis",
                value=st.session_state.include_wind_risk,
                help="Include instructions about wind risk analysis in the prompt"
            )
            
            # Debug mode toggle
            debug_toggle = st.toggle(
                "Debug Template Rendering",
                value=st.session_state.debug_templates,
                help="Log template loading and rendering information"
            )
            
            # Update session state values when toggles change
                
            if power_lines_toggle != st.session_state.include_power_lines:
                st.session_state.include_power_lines = power_lines_toggle
                
            if wind_risk_toggle != st.session_state.include_wind_risk:
                st.session_state.include_wind_risk = wind_risk_toggle
                
            if debug_toggle != st.session_state.debug_templates:
                st.session_state.debug_templates = debug_toggle
                
            # Show note about changes
            st.caption("Changes to these toggles will take effect on the next prompt.")

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
    
    weather_examples = [
        "Are any power lines at risk of high wind speed in the next 10 days near Houston TX starting on July 8, 2024?",
        "Show me temperature risks to oil wells in North Dakota starting on February 13, 2021 where temperatures are lower than -15˚F",
        "Are any power lines at risk from high temperatures above 95°F in New York on June 24, 2025?",
        "Show the temperature forecast for California",
        "What is the wind speed forecast for Chicago?",
    ]

    geo_examples = [
        "Compare the land area of Travis County, TX and King County, WA",
        "Show me power lines near Atlanta, GA",
        "What's the land area of ZIP code 10001 in New York?",
    ]
    
    st.subheader("Geospatial & Weather")
    examples = weather_examples + geo_examples
    
    for example in examples:
        if st.button(example):
            # Check for date in the example prompt
            extracted_date = extract_date_from_prompt(example)
            if extracted_date:
                # Update selected_init_date if a date was found in the prompt
                if extracted_date != st.session_state.selected_init_date:
                    previous_date = st.session_state.selected_init_date
                    st.session_state.selected_init_date = extracted_date
                    # Clear weather-related cache when init_date changes
                    try:
                        from data.weather_data import get_weather_forecast_data
                        get_weather_forecast_data.clear()
                        
                        # Also clear caches from weather service functions
                        from services.weather_service.processing import fetch_weather_data
                        if hasattr(fetch_weather_data, "clear"):
                            fetch_weather_data.clear()
                        
                        # Clear any action-related caches
                        if "map_actions" in st.session_state:
                            st.session_state.map_actions = []

                        # Reset status messages
                        if "status_messages" in st.session_state:
                            st.session_state.status_messages = []
                        
                        # Display formatted dates for better readability
                        formatted_new = extracted_date.strftime("%B %d, %Y")
                        formatted_old = previous_date.strftime("%B %d, %Y") if hasattr(previous_date, "strftime") else "default date"
                        st.success(f"📅 Date changed: {formatted_old} → {formatted_new}")
                    except Exception as e:
                        st.warning(f"Could not clear weather data cache: {e}")
            
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
