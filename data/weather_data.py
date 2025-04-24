import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon, shape
import json
import os
from datetime import datetime, timedelta
from data.bigquery_client import execute_query

@st.cache_data(ttl=3600)  # Reduced TTL for faster updates during development
def get_weather_forecast_data():
    """
    Retrieve weather forecast data from BigQuery.
    Uses actual weather data from mg-ce-demos.wn_demo.pa_dec_18_2022_summ
    
    This data covers Pennsylvania (PA) only - so it will only work for 
    PA regions and will show "No data" for other states.
    
    Note: init_date represents "today's date" in the weather forecast system.
    forecast_date represents the actual future dates being forecasted.
    In our sample data, we only have data where forecast_date equals init_date,
    but in a real system these would be different dates.
    """
    try:
        query = """
        SELECT
          `forecast_date`,
          `geography_polygon`,
          `init_date`,
          `precipitation`,
          `temperature`,
          `wind_speed`
        FROM
          `mg-ce-demos.wn_demo.pa_dec_18_2022_summ`
        """
                
        forecast_df = execute_query(query)
        
        if forecast_df is None or forecast_df.empty:
            # Use fallback sample data if query fails
            st.warning("Using sample weather data (BigQuery connection unavailable)")
            forecast_df = get_sample_weather_data()
        
        # For demonstration, create more forecast dates based on the sample data
        # In a real system, these would come directly from the database
        if not forecast_df.empty and len(forecast_df['forecast_date'].unique()) <= 1:
            forecast_df = expand_forecast_dates(forecast_df)
            
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

def expand_forecast_dates(df):
    """
    Expand a single-day forecast dataset into multiple days.
    This is for demonstration purposes only - to simulate having forecast data
    for multiple days in the future.
    
    Args:
        df: DataFrame with weather data for a single date
        
    Returns:
        DataFrame with synthesized forecast data for multiple dates
    """
    if df is None or df.empty:
        return df
        
    # Get the base date from the data
    base_date = df['init_date'].iloc[0]
    try:
        base_datetime = datetime.strptime(base_date, '%m-%d-%Y')
    except:
        # If we can't parse the date, just return the original data
        return df
    
    # Create a list to hold all expanded dataframes
    expanded_dfs = [df.copy()]  # Start with the original data
    
    # Generate data for 5 additional days
    for i in range(1, 6):
        # Create a new forecast date
        forecast_date = (base_datetime + timedelta(days=i)).strftime('%m-%d-%Y')
        
        # Create a copy of the DataFrame with the new forecast date
        day_df = df.copy()
        day_df['forecast_date'] = forecast_date
        
        # Adjust the data slightly for each day to create some variability
        # Temperature: Add/subtract up to 2 degrees
        day_df['temperature'] = day_df['temperature'] + (np.random.rand(len(day_df)) * 4 - 2)
        
        # Precipitation: Make it rain more on some days
        if i in [2, 4]:  # On days 2 and 4, increase precipitation
            day_df['precipitation'] = day_df['precipitation'] * (5 + np.random.rand(len(day_df)) * 5)
        
        # Wind speed: Vary it slightly
        day_df['wind_speed'] = day_df['wind_speed'] * (0.8 + np.random.rand(len(day_df)) * 0.4)
        
        # Add to the list of expanded dataframes
        expanded_dfs.append(day_df)
    
    # Concatenate all the dataframes
    expanded_df = pd.concat(expanded_dfs, ignore_index=True)
    
    return expanded_df

def get_weather_forecast_dates():
    """
    Get a list of unique forecast dates available in the weather data.
    """
    df = get_weather_forecast_data()
    if df is not None and not df.empty:
        return sorted(df['forecast_date'].unique().tolist())
    return []