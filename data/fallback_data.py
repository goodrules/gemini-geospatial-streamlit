import geopandas as gpd
import numpy as np
import streamlit as st

def get_us_states_fallback():
    """Fallback to GeoPandas built-in datasets if BigQuery fails."""
    try:
        states = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        us = states[states['iso_a3'] == 'USA'].copy()
        us['value'] = np.random.randint(1, 100, size=len(us))
        us['state_name'] = 'United States'  # Add placeholder state_name
        us['state'] = 'US'  # Add placeholder state abbreviation
        us['state_fips_code'] = '00'  # Add placeholder FIPS code
        return us
    except Exception as e:
        st.error(f"Error loading fallback US states: {e}")
        return None 
