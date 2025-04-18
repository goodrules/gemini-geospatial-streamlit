import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import shapely.wkt
from data.bigquery_client import execute_query, initialize_bigquery_client
from data.fallback_data import get_us_states_fallback
import os
import json
from datetime import datetime
from shapely.geometry import mapping

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

@st.cache_data(ttl=3600)
def get_local_shapefile(filepath, layer=None):
    """
    Load and cache a local shapefile.
    
    Args:
        filepath: Path to the shapefile (.shp)
        layer: Layer name for multi-layer files (optional)
        
    Returns:
        GeoDataFrame containing the shapefile data
    """
    try:
        st.info(f"Loading local shapefile: {filepath}")
        gdf = gpd.read_file(filepath, layer=layer)
        
        # Ensure CRS is WGS84 for web mapping
        if gdf.crs is not None and gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
            
        # Convert timestamp columns to string to avoid serialization issues
        for col in gdf.columns:
            if pd.api.types.is_datetime64_any_dtype(gdf[col]):
                gdf[col] = gdf[col].astype(str)
                
        # Add a random value column for visualization if it doesn't exist
        if 'value' not in gdf.columns:
            gdf['value'] = np.random.randint(1, 100, size=len(gdf))
            
        return gdf
    except Exception as e:
        st.error(f"Error loading local shapefile {filepath}: {str(e)}")
        return None

# Function to load common local datasets
@st.cache_data(ttl=3600)
def get_crawford_flood_zones():
    """Load Crawford County flood zone data"""
    return get_local_shapefile("data/local/Crawford_Flood_Zones/Crawford_FP.shp")

@st.cache_data(ttl=3600)
def get_pa_power_lines():
    """Load Pennsylvania power lines data"""
    return get_local_shapefile("data/local/PA_Trans_Lines/Electric_Power_Transmission_Lines_B.shp")

def initialize_app_data():
    """Initialize and cache all geospatial data at app startup."""
    with st.spinner("Loading geospatial data..."):
        try:
            # Load existing data sources
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
            
            # Load local shapefiles
            flood_zones = get_crawford_flood_zones()
            if flood_zones is not None:
                st.session_state.flood_zones_loaded = True
            else:
                st.session_state.flood_zones_loaded = False
                st.warning("Failed to load Crawford flood zones data.")
                
            trans_lines = get_pa_power_lines()
            if trans_lines is not None:
                st.session_state.power_lines_loaded = True
            else:
                st.session_state.power_lines_loaded = False
                st.warning("Failed to load PA power lines data.")
            
            st.session_state.data_initialized = True
            
            # Check which data sources loaded successfully
            data_sources = {
                "states": st.session_state.states_loaded,
                "counties": st.session_state.counties_loaded,
                "zipcodes": st.session_state.zipcodes_loaded,
                "flood_zones": st.session_state.flood_zones_loaded,
                "trans_lines": st.session_state.trans_lines_loaded
            }
            
            if all(data_sources.values()):
                st.success("All geospatial data loaded successfully!")
            else:
                missing = [k for k, v in data_sources.items() if not v]
                st.warning(f"Some data sources failed to load: {', '.join(missing)}")
            
        except Exception as e:
            st.error(f"Error initializing geospatial data: {str(e)}")
            st.session_state.data_initialized = False

