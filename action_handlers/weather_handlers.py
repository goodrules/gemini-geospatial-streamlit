"""
Handlers for weather display actions.
"""

import streamlit as st
from services.weather_service import handle_show_weather as weather_service_handler

def handle_show_weather(action, m):
    """
    Handle the show_weather action by displaying weather parameters
    and delegating to the actual implementation in the weather_service module.
    
    Args:
        action: The action payload containing weather display parameters
        m: The Folium map object
        
    Returns:
        The Folium map bounds with weather visualization added
    """
    # Use a session key to track if we've already shown the UI for this action
    # to prevent duplication
    action_id = str(action.get("id", "default"))
    ui_key = f"weather_ui_shown_{action_id}"
    
    # Only show the UI elements if we haven't already for this action
    if ui_key not in st.session_state:
        st.session_state[ui_key] = True
        
        weather_query = {
            "parameter": action.get("parameter", "temperature"),
            "forecast_timestamp": action.get("forecast_timestamp", ""),
            "forecast_date": action.get("forecast_date", ""),
            "location": action.get("location", "")
        }
        
        # Create a code block with the weather query information
        with st.container():
            st.markdown("### Weather Query Details")
            st.code(
                f"""Parameter: {weather_query['parameter']}
Timestamp: {weather_query['forecast_timestamp']}
Date: {weather_query['forecast_date']}
Location: {weather_query['location']}""", 
                language="text"
            )
        
        # Display the SQL query if available
        init_date = st.session_state.get("selected_init_date", "")
        if init_date:
            init_date_str = init_date.strftime('%Y-%m-%d') if hasattr(init_date, 'strftime') else str(init_date)
            
            # Display the SQL query that was executed
            with st.container():
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
    `weathernext_graph_forecasts.59572747_4_0` AS weather,
    UNNEST(weather.forecast) AS f
JOIN
    us_geom_lookup AS us ON ST_INTERSECTS(weather.geography, us.us_outline_geom) -- Join only weather points inside state lines
WHERE
    weather.init_time = TIMESTAMP("{init_date_str}")
"""
                st.code(sql_query, language="sql")
    
    # Delegate to the actual implementation in weather_service.py
    return weather_service_handler(action, m) 
