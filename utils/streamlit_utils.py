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
    st.session_state.messages = []
    st.session_state.map_actions = []
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
