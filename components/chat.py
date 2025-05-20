import streamlit as st
import json
import pandas as pd
from services.gemini_service import get_gemini_response
from utils.streamlit_utils import extract_date_from_prompt
from datetime import date

def render_chat_interface():
    """Render the chat interface with message history and input"""
    st.subheader("Chat with the AI")
    
    # Display chat messages
    display_chat_messages()
    
    # Chat input
    handle_chat_input()

def display_chat_messages():
    """Display the chat message history"""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            
            # Display structured data if available for assistant messages
            if message["role"] == "assistant" and "additional_data" in st.session_state:
                display_structured_data(st.session_state.additional_data)

def display_structured_data(data):
    """Display structured data from AI responses"""
    if not data:
        return
        
    # Display action summaries from the response
    if "action_summary" in data:
        with st.expander("📊 Analysis Details", expanded=True):
            for action in data["action_summary"]:
                action_type = action.get("action")
                
                if action_type == "Wind Risk Analysis":
                    # Create a formatted display for wind risk analysis
                    st.markdown(f"#### {action_type}: {action.get('region')}")
                    
                    # Create two columns for the details
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Forecast Days:** {action.get('forecast_days')}")
                        st.markdown(f"**High Risk Threshold:** {action.get('high_threshold')} m/s")
                    with col2:
                        st.markdown(f"**Moderate Risk Threshold:** {action.get('moderate_threshold')} m/s")
                        st.markdown(f"**Power Line Analysis:** {action.get('power_line_analysis')}")
                    
                    # Display power line guidance if applicable
                    if action.get('power_line_analysis') == "Yes" and action.get('region') != "Pennsylvania":
                        st.info("📌 Note: Detailed power line data is currently only available for Pennsylvania. For other regions, general estimates are shown.")
                
                elif action_type == "Power Line Data Display":
                    st.markdown(f"#### {action_type}: {action.get('region')}")
                    st.markdown("""
                    **Legend Information:**
                    - Yellow: < 100 kV (Low Voltage)
                    - Orange: 100-300 kV (Medium Voltage)
                    - Red: 300-500 kV (High Voltage)
                    - Dark Red: > 500 kV (Very High Voltage)
                    """)
                
                elif action_type == "Weather Data Display":
                    st.markdown(f"#### {action_type}: {action.get('region')}")
                    st.markdown(f"""
                    **Metric:** {action.get('metric').capitalize()}
                    **Forecast Day:** {action.get('forecast_day')}
                    """)
    
    # Display risk analysis results if available
    if "status_info" in data:
        with st.expander("🔍 Risk Analysis Results", expanded=True):
            for message in data["status_info"]:
                if "high risk" in message.lower():
                    st.warning(message)
                elif "moderate risk" in message.lower():
                    st.info(message)
                else:
                    st.success(message)
    
    # Original data sections
    if "region_info" in data:
        with st.expander("Region Information", expanded=False):
            st.json(data["region_info"])
        
    if "comparison" in data:
        with st.expander("Region Comparison", expanded=False):
            st.dataframe(pd.DataFrame(data["comparison"]))
        
    if "statistics" in data:
        with st.expander("Statistics", expanded=False):
            st.json(data["statistics"])

def handle_chat_input():
    """Handle user chat input and generate AI responses"""
    prompt = st.chat_input("Ask about locations, spatial analysis, etc.")
    if prompt:
        # Check for date in the prompt
        extracted_date = extract_date_from_prompt(prompt)
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
        
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        # Get AI response
        with st.spinner("Generating response..."):
            raw_response = get_gemini_response(prompt, st.session_state.history)
            
            try:
                response_data = json.loads(raw_response)
                ai_message = response_data.get("response", "Sorry, I couldn't process that request.")
                map_actions = response_data.get("map_actions", [])
                additional_data = response_data.get("data", None)
                
                # Update map actions in session state
                st.session_state.map_actions = map_actions
                
                # Store additional data in session state if present
                if additional_data:
                    st.session_state.additional_data = additional_data
                else:
                    if "additional_data" in st.session_state:
                        del st.session_state.additional_data
                        
            except json.JSONDecodeError:
                ai_message = "I encountered an error processing your request. Please try again."
        
        # Display AI response
        with st.chat_message("assistant"):
            st.write(ai_message)
            
            # Display structured data if available
            if "additional_data" in st.session_state and st.session_state.additional_data:
                display_structured_data(st.session_state.additional_data)
        
        # Add AI message to chat history
        st.session_state.messages.append({"role": "assistant", "content": ai_message}) 
