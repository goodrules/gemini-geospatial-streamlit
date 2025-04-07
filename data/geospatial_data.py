import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import shapely.wkt
from data.bigquery_client import execute_query, initialize_bigquery_client
from data.fallback_data import get_us_states_fallback

# Function to fetch and cache US states data from BigQuery
@st.cache_data(ttl=3600)
def get_us_states():
    """Fetch US states data from Google BigQuery public dataset."""
    try:
        client = initialize_bigquery_client()
        if not client:
            st.warning("Using fallback dataset as BigQuery client could not be initialized.")
            return get_us_states_fallback()
            
        # Query to fetch US states data
        query = """
        SELECT 
            geo_id, 
            state, 
            state_name, 
            state_fips_code, 
            int_point_lat, 
            int_point_lon,
            area_land_meters,
            area_water_meters,
            ST_AsText(state_geom) as state_geom_wkt
        FROM 
            `bigquery-public-data.geo_us_boundaries.states`
        """
        
        # Run the query
        df = client.query(query).to_dataframe()
        
        # Convert WKT geometry to GeoDataFrame
        geometry = df['state_geom_wkt'].apply(shapely.wkt.loads)
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        
        # Add a value column for visualization
        gdf['value'] = np.random.randint(1, 100, size=len(gdf))
        
        # Cleanup
        if 'state_geom_wkt' in gdf.columns:
            gdf = gdf.drop(columns=['state_geom_wkt'])
            
        return gdf
        
    except Exception as e:
        st.error(f"Error fetching data from BigQuery: {e}")
        return get_us_states_fallback()

# Function to fetch and cache US counties data from BigQuery
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_us_counties():
    """Fetch US counties data from Google BigQuery public dataset."""
    try:
        client = initialize_bigquery_client()
        if not client:
            st.warning("Using fallback dataset as BigQuery client could not be initialized.")
            return None
            
        # Query to fetch US counties data
        query = """
        SELECT 
            geo_id, 
            state_fips_code,
            county_fips_code,
            county_name,
            lsad_name,
            area_land_meters,
            area_water_meters,
            int_point_lat, 
            int_point_lon,
            ST_AsText(county_geom) as county_geom_wkt
        FROM 
            `bigquery-public-data.geo_us_boundaries.counties`
        """
        
        # Run the query
        df = client.query(query).to_dataframe()
        
        # Convert WKT geometry to GeoDataFrame
        geometry = df['county_geom_wkt'].apply(shapely.wkt.loads)
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        
        # Add a value column for visualization
        gdf['value'] = np.random.randint(1, 100, size=len(gdf))
        
        # Cleanup
        if 'county_geom_wkt' in gdf.columns:
            gdf = gdf.drop(columns=['county_geom_wkt'])
            
        return gdf
        
    except Exception as e:
        st.error(f"Error fetching county data from BigQuery: {e}")
        return None

# Function to fetch and cache US zip codes data from BigQuery
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_us_zipcodes():
    """Fetch US zip codes data from Google BigQuery public dataset."""
    try:
        client = initialize_bigquery_client()
        if not client:
            st.warning("Using fallback dataset as BigQuery client could not be initialized.")
            return None
            
        # Query to fetch US zip codes data
        query = """
        SELECT 
            zip_code, 
            city, 
            county,
            state_fips_code,
            state_code,
            state_name,
            fips_class_code,
            mtfcc_feature_class_code,
            functional_status,
            area_land_meters,
            area_water_meters,
            internal_point_lat, 
            internal_point_lon,
            ST_AsText(internal_point_geom) as internal_point_geom_wkt,
            ST_AsText(zip_code_geom) as zip_code_geom_wkt
        FROM 
            `bigquery-public-data.geo_us_boundaries.zip_codes`
        """
        
        # Run the query
        df = client.query(query).to_dataframe()
        
        # Convert WKT geometry to GeoDataFrame
        geometry = df['zip_code_geom_wkt'].apply(shapely.wkt.loads)
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        
        # Add a value column for visualization
        gdf['value'] = np.random.randint(1, 100, size=len(gdf))
        
        # Cleanup
        if 'zip_code_geom_wkt' in gdf.columns:
            gdf = gdf.drop(columns=['zip_code_geom_wkt'])
        if 'internal_point_geom_wkt' in gdf.columns:
            gdf = gdf.drop(columns=['internal_point_geom_wkt'])
            
        return gdf
        
    except Exception as e:
        st.error(f"Error fetching zip code data from BigQuery: {e}")
        return None

def initialize_app_data():
    """Initialize and cache all geospatial data at app startup."""
    with st.spinner("Loading geospatial data..."):
        try:
            states = get_us_states()
            if states is not None:
                st.session_state.states_loaded = True
            else:
                st.session_state.states_loaded = False
                st.warning("Failed to load US states data.")
            
            counties = get_us_counties()
            if counties is not None:
                st.session_state.counties_loaded = True
            else:
                st.session_state.counties_loaded = False
                st.warning("Failed to load US counties data.")
            
            zipcodes = get_us_zipcodes()
            if zipcodes is not None:
                st.session_state.zipcodes_loaded = True
            else:
                st.session_state.zipcodes_loaded = False
                st.warning("Failed to load US ZIP codes data.")
            
            st.session_state.data_initialized = True
            
            if all([st.session_state.states_loaded, 
                   st.session_state.counties_loaded, 
                   st.session_state.zipcodes_loaded]):
                st.success("All geospatial data loaded successfully!")
            else:
                missing = []
                if not st.session_state.states_loaded:
                    missing.append("states")
                if not st.session_state.counties_loaded:
                    missing.append("counties")
                if not st.session_state.zipcodes_loaded:
                    missing.append("ZIP codes")
                st.warning(f"Some data sources failed to load: {', '.join(missing)}")
            
        except Exception as e:
            st.error(f"Error initializing geospatial data: {str(e)}")
            st.session_state.data_initialized = False 
