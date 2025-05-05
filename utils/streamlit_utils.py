import streamlit as st
from google.genai import types

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
    """Display all collected status messages in a compact format"""
    if "status_messages" in st.session_state and st.session_state.status_messages:
        # Group messages by type
        info_messages = [msg["text"] for msg in st.session_state.status_messages if msg["type"] == "info"]
        warning_messages = [msg["text"] for msg in st.session_state.status_messages if msg["type"] == "warning"]
        error_messages = [msg["text"] for msg in st.session_state.status_messages if msg["type"] == "error"]
        success_messages = [msg["text"] for msg in st.session_state.status_messages if msg["type"] == "success"]
        
        # Display in a compact expander
        with st.expander("Status Messages", expanded=True):
            cols = st.columns([1, 1])
            
            # Column 1: Info and Success
            with cols[0]:
                if info_messages:
                    _original_info("\n".join(f"• {msg}" for msg in info_messages))
                if success_messages:
                    _original_success("\n".join(f"• {msg}" for msg in success_messages))
            
            # Column 2: Warning and Error
            with cols[1]:
                if warning_messages:
                    _original_warning("\n".join(f"• {msg}" for msg in warning_messages))
                if error_messages:
                    _original_error("\n".join(f"• {msg}" for msg in error_messages))
        
        # Clear after display
        clear_status_messages()
