import streamlit as st
from google.genai import types
import re
from datetime import datetime, date

def create_tooltip_html(region, region_type):
    """Create HTML tooltip for map elements based on region type"""
    if region_type.lower() == "state":
        # For states, add state-specific information
        tooltip_html = f"""
        <div style="min-width: 180px;">
            <h4>{region['state_name'].iloc[0]}</h4>
            <p><b>State Code:</b> {region['state'].iloc[0]}</p>
            <p><b>FIPS Code:</b> {region['state_fips_code'].iloc[0]}</p>
            <p><b>Land Area:</b> {region['area_land_meters'].iloc[0]/1e6:.2f} sq km</p>
            <p><b>Water Area:</b> {region['area_water_meters'].iloc[0]/1e6:.2f} sq km</p>
        </div>
        """
    elif region_type.lower() == "county":
        # County-specific tooltip
        tooltip_html = f"""
        <div style="min-width: 180px;">
            <h4>{region['county_name'].iloc[0]} {region['lsad_name'].iloc[0]}</h4>
            <p><b>State FIPS:</b> {region['state_fips_code'].iloc[0]}</p>
            <p><b>County FIPS:</b> {region['county_fips_code'].iloc[0]}</p>
            <p><b>Land Area:</b> {region['area_land_meters'].iloc[0]/1e6:.2f} sq km</p>
            <p><b>Water Area:</b> {region['area_water_meters'].iloc[0]/1e6:.2f} sq km</p>
        </div>
        """
    elif region_type.lower() in ["zipcode", "zip_code", "zip"]:
        # Zip code-specific tooltip
        tooltip_html = f"""
        <div style="min-width: 180px;">
            <h4>ZIP Code: {region['zip_code'].iloc[0]}</h4>
            <p><b>City:</b> {region['city'].iloc[0]}</p>
            <p><b>County:</b> {region['county'].iloc[0]}</p>
            <p><b>State:</b> {region['state_name'].iloc[0]} ({region['state_code'].iloc[0]})</p>
            <p><b>Land Area:</b> {region['area_land_meters'].iloc[0]/1e6:.2f} sq km</p>
            <p><b>Water Area:</b> {region['area_water_meters'].iloc[0]/1e6:.2f} sq km</p>
        </div>
        """
    else:
        # Generic tooltip for other region types
        tooltip_html = f"<div><h4>{region_type.capitalize()}</h4></div>"
    
    return tooltip_html

def reset_session_state():
    """Reset all session state to initial values"""
    # Preserve init_date if it exists
    init_date = st.session_state.get("selected_init_date")
    
    st.session_state.messages = []
    st.session_state.map_actions = []
    st.session_state.status_messages = []
    st.session_state.history = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text="Hello")]
        ),
        types.Content(
            role="model",
            parts=[types.Part.from_text(text="""{"response": "Hello! I'm your geospatial assistant. I can help with location analysis, mapping, and spatial queries. What would you like to explore today?", "map_actions": []}""")]
        ),
    ]
    
    # Remove any additional data
    if "additional_data" in st.session_state:
        del st.session_state.additional_data 
        
    # Restore init_date if it existed
    if init_date:
        st.session_state.selected_init_date = init_date

def add_status_message(message, type="info"):
    """
    Add a status message to the session state to be displayed in a compact format.
    
    Args:
        message: The message text to display
        type: The message type - "info", "warning", "error", or "success"
    """
    if "status_messages" not in st.session_state:
        st.session_state.status_messages = []
    
    # Add the message to the session state
    st.session_state.status_messages.append({
        "text": message,
        "type": type
    })
    
def clear_status_messages():
    """Clear all status messages"""
    if "status_messages" in st.session_state:
        st.session_state.status_messages = []

# Store original functions at module level
_original_info = st.info
_original_warning = st.warning
_original_error = st.error
_original_success = st.success

# Status message interception

class StatusMessageInterceptor:
    """A context manager to intercept Streamlit status messages and collect them in session state"""
    
    def __enter__(self):
        """Patch the streamlit functions with our interceptors"""
        # Replace Streamlit's status message functions with our own versions
        def intercepted_info(message):
            add_status_message(message, "info")
            # Don't call original to avoid duplicate display
        
        def intercepted_warning(message):
            add_status_message(message, "warning")
            # Don't call original to avoid duplicate display
        
        def intercepted_error(message):
            add_status_message(message, "error")
            # Don't call original to avoid duplicate display
        
        def intercepted_success(message):
            add_status_message(message, "success")
            # Don't call original to avoid duplicate display
        
        # Save the original functions
        self.original_info = st.info
        self.original_warning = st.warning
        self.original_error = st.error
        self.original_success = st.success
        
        # Replace with our versions
        st.info = intercepted_info
        st.warning = intercepted_warning
        st.error = intercepted_error
        st.success = intercepted_success
        
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        """Restore the original streamlit functions"""
        # Restore original functions
        st.info = self.original_info
        st.warning = self.original_warning
        st.error = self.original_error
        st.success = self.original_success
        
        # Return False to propagate exceptions
        return False

def display_status_messages():
    """Display all collected status messages in a compact format with each message on a separate line"""
    if "status_messages" in st.session_state and st.session_state.status_messages:
        # Group messages by type
        info_messages = [msg["text"] for msg in st.session_state.status_messages if msg["type"] == "info"]
        warning_messages = [msg["text"] for msg in st.session_state.status_messages if msg["type"] == "warning"]
        error_messages = [msg["text"] for msg in st.session_state.status_messages if msg["type"] == "error"]
        success_messages = [msg["text"] for msg in st.session_state.status_messages if msg["type"] == "success"]
        
        # Display in a compact expander
        with st.expander("Status Messages", expanded=False):
            cols = st.columns([1, 1])
            
            # Column 1: Info and Success
            with cols[0]:
                if info_messages:
                    # Display each info message individually
                    for msg in info_messages:
                        _original_info(f"{msg}")
                
                if success_messages:
                    # Display each success message individually
                    for msg in success_messages:
                        _original_success(f"{msg}")
            
            # Column 2: Warning and Error
            with cols[1]:
                if warning_messages:
                    # Display each warning message individually
                    for msg in warning_messages:
                        _original_warning(f"**{msg}**")
                
                if error_messages:
                    # Display each error message individually
                    for msg in error_messages:
                        _original_error(f"*{msg}*")
        
        # Clear after display
        clear_status_messages()

def extract_date_from_prompt(prompt_text):
    """
    Extract a date from a user's prompt text, supporting various date formats.
    
    Args:
        prompt_text (str): The text of the user's prompt
        
    Returns:
        date: The extracted date or None if no valid date is found
    """
    if not prompt_text:
        return None
        
    # Convert to lowercase for consistent pattern matching
    text = prompt_text.lower()
    
    # Try to extract exact dates first (common formats)
    
    # Format: YYYY-MM-DD
    iso_pattern = r'\b(\d{4}-\d{1,2}-\d{1,2})\b'
    iso_matches = re.findall(iso_pattern, text)
    for match in iso_matches:
        try:
            return datetime.strptime(match, '%Y-%m-%d').date()
        except ValueError:
            pass
            
    # Format: MM/DD/YYYY or M/D/YYYY
    slash_pattern = r'\b(\d{1,2}/\d{1,2}/\d{4})\b'
    slash_matches = re.findall(slash_pattern, text)
    for match in slash_matches:
        try:
            return datetime.strptime(match, '%m/%d/%Y').date()
        except ValueError:
            pass
    
    # Month mapping for text-based date parsing
    month_mapping = {
        'january': 1, 'jan': 1,
        'february': 2, 'feb': 2,
        'march': 3, 'mar': 3,
        'april': 4, 'apr': 4,
        'may': 5,
        'june': 6, 'jun': 6,
        'july': 7, 'jul': 7,
        'august': 8, 'aug': 8,
        'september': 9, 'sep': 9,
        'october': 10, 'oct': 10,
        'november': 11, 'nov': 11,
        'december': 12, 'dec': 12
    }
    
    # Look for dates with contextual phrases
    context_patterns = [
        # "starting on February 13, 2021" or variants
        r'(?:starting|beginning|from|since|after|on)\s+(?:the\s+)?(?:date\s+)?(?:of\s+)?(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)\s+(\d{1,2})(?:,?\s+|\s*,\s*)(\d{4})',
        
        # "from February 13, 2021" or variants
        r'(?:from|since|after|as of)\s+(?:the\s+)?(?:date\s+)?(?:of\s+)?(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)\s+(\d{1,2})(?:,?\s+|\s*,\s*)(\d{4})'
    ]
    
    for pattern in context_patterns:
        context_matches = re.findall(pattern, text)
        for match in context_matches:
            try:
                month_str, day_str, year_str = match
                month_num = month_mapping.get(month_str.lower())
                if month_num:
                    return date(int(year_str), month_num, int(day_str))
            except (ValueError, KeyError):
                pass

    # Format: Month DD, YYYY (e.g., "January 15, 2024" or "Jan 15, 2024")
    month_pattern = r'(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)\s+(\d{1,2})(?:,?\s+|\s*,\s*)(\d{4})'
    month_matches = re.findall(month_pattern, text)
    
    for match in month_matches:
        try:
            month_str, day_str, year_str = match
            month_num = month_mapping.get(month_str.lower())
            if month_num:
                return date(int(year_str), month_num, int(day_str))
        except (ValueError, KeyError):
            pass
            
    # Format: DD Month YYYY (e.g., "15 January 2024" or "15 Jan 2024")
    reverse_pattern = r'(\d{1,2})\s+(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)(?:,?\s+|\s*,\s*)(\d{4})'
    reverse_matches = re.findall(reverse_pattern, text)
    
    for match in reverse_matches:
        try:
            day_str, month_str, year_str = match
            month_num = month_mapping.get(month_str.lower())
            if month_num:
                return date(int(year_str), month_num, int(day_str))
        except (ValueError, KeyError):
            pass
    
    # If no specific date found, return None
    return None
