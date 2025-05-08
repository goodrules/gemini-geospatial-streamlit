"""
Handlers for wind risk analysis actions.
"""

import streamlit as st
from services.risk_analyzer import handle_analyze_wind_risk as risk_analyzer_handler

def handle_analyze_wind_risk(action, m):
    """
    Handle the analyze_wind_risk action by displaying analysis parameters
    and delegating to the actual implementation in the risk_analyzer module.
    
    Args:
        action: The action payload containing wind risk parameters
        m: The Folium map object
        
    Returns:
        The Folium map with wind risk visualization added
    """
    risk_query = {
        "region": action.get("region", ""),
        "forecast_days": action.get("forecast_days", 3),
        "high_threshold": action.get("high_threshold", 16.0),
        "moderate_threshold": action.get("moderate_threshold", 13.0),
        "analyze_power_lines": action.get("analyze_power_lines", False)
    }
    
    # Create a code block with the wind risk analysis information
    st.markdown("### Wind Risk Analysis Details")
    st.code(
        f"""Region: {risk_query['region']}
Forecast Days: {risk_query['forecast_days']}
High Risk Threshold: {risk_query['high_threshold']} m/s
Moderate Risk Threshold: {risk_query['moderate_threshold']} m/s
Power Line Analysis: {"Yes" if risk_query['analyze_power_lines'] else "No"}""", 
        language="text"
    )
    
    # Delegate to the actual implementation in risk_analyzer.py
    return risk_analyzer_handler(action, m) 
