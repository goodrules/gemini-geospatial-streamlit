import streamlit as st
from streamlit_folium import st_folium
from services.map_processor import initialize_map, process_map_actions
from utils.streamlit_utils import clear_status_messages, display_status_messages, StatusMessageInterceptor

def render_map():
    """Render the interactive map with any active map actions"""
    st.subheader("Interactive Map")
    
    # Clear any previous messages at the beginning of rendering
    clear_status_messages()
    
    # Map initialization
    m = initialize_map()
    
    # Process map actions with status message interception
    if isinstance(st.session_state.map_actions, list) and len(st.session_state.map_actions) > 0:
        with StatusMessageInterceptor():
            # Process the map actions while intercepting status messages
            m = process_map_actions(st.session_state.map_actions, m)
    
    # Display status messages BEFORE the map
    display_status_messages()
    
    # Display the map
    st_folium(m, height=800, use_container_width=True)
    
    # Display query information for weather or wind risk actions
    if isinstance(st.session_state.map_actions, list) and len(st.session_state.map_actions) > 0:
        for action in st.session_state.map_actions:
            if isinstance(action, dict):
                # Handle weather action
                if action.get("action_type") == "show_weather":
                    weather_query = {
                        "parameter": action.get("parameter", "temperature"),
                        "forecast_timestamp": action.get("forecast_timestamp", ""),
                        "forecast_date": action.get("forecast_date", ""),
                        "location": action.get("location", "")
                    }
                    
                    # Create a code block with the weather query information
                    st.markdown("### Weather Query Details")
                    st.code(
                        f"""Parameter: {weather_query['parameter']}
Timestamp: {weather_query['forecast_timestamp']}
Date: {weather_query['forecast_date']}
Location: {weather_query['location']}""", 
                        language="text"
                    )
                    
                    # Get the init_date from session state to construct the query
                    init_date = st.session_state.get("selected_init_date", "")
                    if init_date:
                        init_date_str = init_date.strftime('%Y-%m-%d') if hasattr(init_date, 'strftime') else str(init_date)
                        
                        # Display the SQL query that was executed
                        st.markdown("### SQL Query")
                        # Use the stored query if available, otherwise construct a template
                        if "last_weather_query" in st.session_state:
                            sql_query = st.session_state.last_weather_query
                        else:
                            sql_query = f"""
WITH us_geom_lookup AS (
SELECT
    us_outline_geom
FROM
    `bigquery-public-data.geo_us_boundaries.national_outline`
)
SELECT
    weather.init_time,
    weather.geography,
    weather.geography_polygon,
    f.time AS forecast_time,
    f.`2m_temperature` as temperature,
    f.total_precipitation_6hr as precipitation,
    f.`10m_u_component_of_wind`,
    f.`10m_v_component_of_wind`,
    SQRT(POW(f.`10m_u_component_of_wind`, 2) + POW(f.`10m_v_component_of_wind`, 2)) AS `wind_speed`   -- Calculate wind speed from U and V components
FROM
    `mg-ce-demos.weathernext_graph_forecasts.59572747_4_0` AS weather,
    UNNEST(weather.forecast) AS f
JOIN
    us_geom_lookup AS us ON ST_INTERSECTS(weather.geography, us.us_outline_geom) -- Join only weather points inside state lines
WHERE
    weather.init_time = TIMESTAMP("{init_date_str}")
"""
                        st.code(sql_query, language="sql")
                
                # Handle wind risk analysis action
                elif action.get("action_type") == "analyze_wind_risk":
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
