import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon, shape
import json
import os
from datetime import datetime, timedelta
from data.bigquery_client import execute_query

#PROJECT_ID = os.environ.get('PROJECT_ID')
PROJECT_ID = 'mg-ce-demos'  # remove for deployment

@st.cache_data(ttl=3600)
def get_weather_forecast_data(init_date):
    """
    Retrieve weather forecast data from BigQuery for a specific init_date.

    Args:
        init_date (datetime.date or str): The initialization date for the forecast.
                                           If str, expected format 'YYYY-MM-DD'.
    
    This data covers Pennsylvania (PA) only - so it will only work for 
    PA regions and will show "No data" for other states.
    
    Note: init_time represents the initialization time of the forecast run.
    forecast_time represents the specific timestamp for which the forecast applies (UTC).
    """
    try:
        # Format the date argument for the query FIRST
        if isinstance(init_date, str):
            init_date_str = init_date
        else: # Assume datetime.date object
            init_date_str = init_date.strftime('%Y-%m-%d')

        # Now define the query using the formatted string
        query = f"""
        WITH state_geom_lookup AS (
        SELECT
            state_geom
        FROM
            `bigquery-public-data.geo_us_boundaries.states`
        WHERE
            state_name = 'Pennsylvania'
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
            SQRT(POW(f.`10m_u_component_of_wind`, 2) + POW(f.`10m_v_component_of_wind`, 2)) AS wind_speed   -- Calculate wind speed from U and V components
        FROM
            `{PROJECT_ID}.weathernext_graph_forecasts.59572747_4_0` AS weather,
            UNNEST(weather.forecast) AS f
        JOIN
            state_geom_lookup AS st ON ST_INTERSECTS(weather.geography, st.state_geom) -- Join only weather points inside state lines
        WHERE
            -- Use the provided init_date, formatted as YYYY-MM-DD string for TIMESTAMP
            weather.init_time = TIMESTAMP("{init_date_str}")
        """

        st.info(f"Querying weather data for init_date: {init_date_str}") # Info for debugging
                
        # Execute the query (no .format needed anymore)
        forecast_df = execute_query(query)
            
        return forecast_df
    except Exception as e:
        st.error(f"Error fetching weather forecast data: {e}")
        # Use fallback sample data if query fails
        st.warning("Using sample weather data (BigQuery connection unavailable)")
        return get_sample_weather_data()

def get_sample_weather_data():
    """
    Load sample weather data from CSV file.
    Used as fallback when BigQuery is unavailable.
    """
    try:
        # Path to sample data file
        sample_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "data_samples", "weather", "weather_data_sample.csv"
        )
        
        # Load the sample data
        sample_df = pd.read_csv(sample_file)
        
        return sample_df
    except Exception as e:
        st.error(f"Error loading sample weather data: {e}")
        return None

def get_weather_forecast_times(init_date):
    """
    Get a list of unique forecast timestamps available in the weather data
    for a specific initialization date.

    Args:
        init_date (datetime.date or str): The initialization date for the forecast.

    Returns:
        List[pd.Timestamp]: Sorted list of unique pandas Timestamps (UTC).
    """
    df = get_weather_forecast_data(init_date) # Pass init_date
    # Ensure forecast_time is datetime before proceeding
    if df is not None and not df.empty and 'forecast_time' in df.columns:
        try:
            # Convert to datetime if it's not already, coercing errors
            df['forecast_time'] = pd.to_datetime(df['forecast_time'], errors='coerce')
            # Ensure UTC
            if df['forecast_time'].dt.tz is None:
                 df['forecast_time'] = df['forecast_time'].dt.tz_localize('UTC')
            else:
                 df['forecast_time'] = df['forecast_time'].dt.tz_convert('UTC')
            # Drop rows where conversion failed
            df.dropna(subset=['forecast_time'], inplace=True)
            # Get unique, sorted timestamps
            return sorted(df['forecast_time'].unique().tolist())
        except Exception as e:
            st.error(f"Error processing forecast timestamps: {e}")
            return []
    return []

def get_unique_forecast_dates_str(init_date):
    """
    Get a list of unique forecast dates (as strings YYYY-MM-DD) from the weather data
    for a specific initialization date.

    Args:
        init_date (datetime.date or str): The initialization date for the forecast.

    Returns:
        List[str]: Sorted list of unique date strings.
    """
    timestamps = get_weather_forecast_times(init_date) # Pass init_date
    if timestamps:
        # Extract date part, format as string, get unique, sort
        date_strs = sorted(list(set([ts.strftime('%Y-%m-%d') for ts in timestamps])))
        return date_strs
    return []
