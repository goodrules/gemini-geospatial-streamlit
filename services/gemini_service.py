import streamlit as st
import json
from google import genai
from google.genai import types
from config.settings import PROJECT_ID, REGION, GEMINI_MODEL
from config.credentials import get_credentials
from datetime import date, timedelta, datetime # Import necessary types
from prompts.prompt_loader import load_prompt_template

@st.cache_resource
def initialize_gemini_client():
    """Initialize and return a Gemini client"""
    try:
        credentials = get_credentials()
        
        client = genai.Client(
            vertexai=True, 
            project=PROJECT_ID, 
            location=REGION, 
            credentials=credentials
        )
        return client
    except Exception as e:
        # Correctly escape braces in f-string error message
        st.error(f"Error initializing Gemini client: {{str(e)}}") 
        return None

def get_system_prompt(selected_init_date):
    """Return the system prompt for the Gemini model, making relative dates dynamic."""

    # Ensure selected_init_date is a date object with robust parsing
    if not isinstance(selected_init_date, date):
        try:
            # Try parsing YYYY-MM-DD format first
            selected_init_date = datetime.strptime(str(selected_init_date), '%Y-%m-%d').date()
        except (TypeError, ValueError):
             try:
                 # Fallback to fromisoformat if the first fails
                 selected_init_date = date.fromisoformat(str(selected_init_date))
             except (TypeError, ValueError):
                 selected_init_date = date.today() # Fallback to today if all conversions fail
                 st.warning("Invalid init_date format encountered in session state, defaulting to today for Gemini prompt.")

    # Calculate relative date strings based on the selected init_date
    today_str = selected_init_date.strftime('%Y-%m-%d')
    tomorrow_str = (selected_init_date + timedelta(days=1)).strftime('%Y-%m-%d')
    day_after_str = (selected_init_date + timedelta(days=2)).strftime('%Y-%m-%d')
    three_days_str = (selected_init_date + timedelta(days=3)).strftime('%Y-%m-%d')
    four_days_str = (selected_init_date + timedelta(days=4)).strftime('%Y-%m-%d')

    # Get streamlit session state values for feature toggles
    # Default to True if not specified, allowing selective disabling
    include_power_lines = st.session_state.get("include_power_lines", True)
    include_wind_risk = st.session_state.get("include_wind_risk", True)
    
    # Enable debug mode from session state
    debug_templates = st.session_state.get("debug_templates", False)

    # Prepare context for template rendering
    context = {
        # Date values
        "today_date": today_str,
        "tomorrow_date": tomorrow_str,
        "day_after_date": day_after_str,
        "three_days_date": three_days_str,
        "four_days_date": four_days_str,
        
        # Feature toggles
        "include_power_lines_notes": include_power_lines,
        "include_wind_risk_notes": include_wind_risk
    }

    # Load and render the prompt template using our new loader
    return load_prompt_template(context, debug=debug_templates)

def get_generate_content_config():
    """Return the configuration for Gemini content generation"""
    return types.GenerateContentConfig(
        temperature=0.2,
        top_p=0.95,
        max_output_tokens=8192,
        response_modalities = ["TEXT"],
        response_mime_type="application/json",
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
        ]
    )

def get_gemini_response(prompt, history):
    """Get response from Gemini with proper error handling"""
    from datetime import date # Import date for default
    client = initialize_gemini_client()
    if not client:
        return json.dumps({
            "response": "Error: Gemini client not initialized",
            "map_actions": []
        })
    
    model = GEMINI_MODEL
    config = get_generate_content_config()
    # Get the selected init_date from session state, defaulting to today
    selected_init_date = st.session_state.get("selected_init_date", date.today())
    system_prompt = get_system_prompt(selected_init_date) # Pass the date
    
    # Save system prompt for debugging
    st.session_state.last_system_prompt = system_prompt
    
    try:
        new_content = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )
        ]
        
        # Always prepend/replace the dynamic system prompt
        dynamic_system_content = types.Content(role="user", parts=[types.Part.from_text(text=system_prompt)])
        if history and history[0].role == "user" and "geospatial analysis assistant" in history[0].parts[0].text:
            history[0] = dynamic_system_content # Replace existing system prompt
        else:
            history.insert(0, dynamic_system_content) # Prepend new system prompt

        response = client.models.generate_content(
            model=model,
            contents=history + new_content, # Send updated history + new prompt
            config=config
        )
        
        # Save raw response for debugging
        st.session_state.last_api_response = response.text
        
        # Add the actual user prompt and model response to history *after* the call
        history.append(new_content[0])
        history.append(types.Content(
            role="model",
            parts=[types.Part.from_text(text=response.text)]
        ))
        
        return response.text
    except Exception as e:
        # Ensure braces are doubled in f-string error message
        st.error(f"Error during Gemini API call: {{str(e)}}") 
        error_response = json.dumps({
            "response": f"Error generating response: {{str(e)}}", 
            "map_actions": []
        })
        st.session_state.last_api_response = error_response
        return error_response
