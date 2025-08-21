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
from utils.streamlit_utils import add_status_message
from google.cloud import storage
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Setup module logger
logger = logging.getLogger(__name__)

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
          counties_table.geo_id,
          counties_table.state_fips_code,
          counties_table.county_fips_code,
          counties_table.county_name,
          counties_table.lsad_name,
          counties_table.area_land_meters,
          counties_table.area_water_meters,
          counties_table.int_point_lat,
          counties_table.int_point_lon,
          ST_ASTEXT(counties_table.county_geom) AS county_geom_wkt,
          states_table.state,
          states_table.state_name
        FROM
          `bigquery-public-data.geo_us_boundaries.counties` AS counties_table
        JOIN
          `bigquery-public-data.geo_us_boundaries.states` AS states_table
        ON
          counties_table.state_fips_code = states_table.state_fips_code;
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
            mtlcc_feature_class_code,
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
        add_status_message(f"Loading local shapefile: {filepath}", "info")
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

def read_geojson_from_gcs(filename):
    """
    Read GeoJSON file directly from Google Cloud Storage.
    
    Args:
        filename: Name of the GeoJSON file in the bucket (e.g., 'power_lines_points_us.geojson')
        
    Returns:
        GeoDataFrame containing the geospatial data, or None if reading fails
    """
    try:
        # Get bucket name from environment
        bucket_name = os.environ.get("GCS_BUCKET_NAME")
        if not bucket_name:
            logger.warning("GCS_BUCKET_NAME environment variable not set")
            return None
        
        # Initialize GCS client
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(filename)
        
        # Check if file exists
        if not blob.exists():
            logger.warning(f"File {filename} not found in GCS bucket {bucket_name}")
            return None
        
        # Download file content as string
        geojson_content = blob.download_as_text()
        
        # Read with GeoPandas from string
        import io
        gdf = gpd.read_file(io.StringIO(geojson_content))
        
        # Ensure CRS is WGS84 for web mapping
        if gdf.crs is not None and gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
            
        # Convert timestamp columns to string to avoid serialization issues
        for col in gdf.columns:
            if pd.api.types.is_datetime64_any_dtype(gdf[col]):
                gdf[col] = gdf[col].astype(str)
        
        logger.info(f"Successfully loaded {filename} from GCS bucket {bucket_name}")
        return gdf
        
    except Exception as e:
        logger.error(f"Error reading {filename} from GCS: {str(e)}")
        return None

# Function to load common local datasets
@st.cache_data(ttl=3600)
def get_us_power_lines(use_geojson=True, use_gcs=True):
    """
    Load power lines data. 
    
    Args:
        use_geojson: If True, use the simplified GeoJSON points file.
                    If False, use the original shapefile with line geometries.
        use_gcs: If True, try loading from GCS first, then fallback to local files.
    
    Returns:
        GeoDataFrame containing power line data
    """
    if use_geojson:
        gdf = None
        
        # Try GCS first if enabled
        if use_gcs:
            try:
                add_status_message("Loading power lines from GCS bucket", "info")
                gdf = read_geojson_from_gcs("power_lines_points_us.geojson")
            except Exception as e:
                logger.error(f"Error loading power lines from GCS: {str(e)}")
                add_status_message("GCS loading failed, trying local files", "warning")
        
        # Fallback to local file if GCS failed or disabled
        if gdf is None:
            try:
                add_status_message("Loading power lines from local GeoJSON file", "info")
                geojson_path = "data/local/power_lines_points_us.geojson"
                gdf = gpd.read_file(geojson_path)
                
                # Ensure CRS is WGS84 for web mapping
                if gdf.crs is not None and gdf.crs != "EPSG:4326":
                    gdf = gdf.to_crs("EPSG:4326")
                    
                # Convert timestamp columns to string to avoid serialization issues
                for col in gdf.columns:
                    if pd.api.types.is_datetime64_any_dtype(gdf[col]):
                        gdf[col] = gdf[col].astype(str)
            except Exception as e:
                st.error(f"Error loading power lines GeoJSON: {str(e)}")
                return None
        
        # Add common processing for both GCS and local data
        if gdf is not None:
            # Add a random value column for visualization if it doesn't exist
            if 'value' not in gdf.columns:
                gdf['value'] = np.random.randint(1, 100, size=len(gdf))
                
            return gdf
    
    # Original shapefile fallback logic would go here
    st.error("Shapefile loading not implemented in this version")
    return None

@st.cache_data(ttl=3600)
def get_oil_wells_data(use_gcs=True):
    """
    Load oil wells data from North Dakota.
    
    Args:
        use_gcs: If True, try loading from GCS first, then fallback to local files.
    
    Returns:
        GeoDataFrame containing oil wells data, or None if loading fails
    """
    gdf = None
    
    # Try GCS first if enabled
    if use_gcs:
        try:
            add_status_message("Loading oil wells data from GCS bucket", "info")
            gdf = read_geojson_from_gcs("north_dakota_oil_wells.geojson")
        except Exception as e:
            logger.error(f"Error loading oil wells from GCS: {str(e)}")
            add_status_message("GCS loading failed, trying local files", "warning")
    
    # Fallback to local file if GCS failed or disabled
    if gdf is None:
        try:
            add_status_message("Loading oil wells from local GeoJSON file", "info")
            oil_wells_path = "data/local/north_dakota_oil_wells.geojson"
            gdf = gpd.read_file(oil_wells_path)
            
            # Ensure CRS is WGS84 for web mapping
            if gdf.crs is not None and gdf.crs != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
                
            # Convert timestamp columns to string to avoid serialization issues
            for col in gdf.columns:
                if pd.api.types.is_datetime64_any_dtype(gdf[col]):
                    gdf[col] = gdf[col].astype(str)
        except Exception as e:
            logger.error(f"Error loading oil wells GeoJSON: {str(e)}")
            add_status_message(f"Failed to load oil wells data: {str(e)}", "error")
            return None
    
    return gdf

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
            
            # Load local GeoJSON files
            trans_lines = get_us_power_lines(use_geojson=True)
            if trans_lines is not None:
                st.session_state.power_lines_loaded = True
            else:
                st.session_state.power_lines_loaded = False
                st.warning("Failed to load power lines data.")
            
            st.session_state.data_initialized = True
            
            # Check which data sources loaded successfully
            data_sources = {
                "states": st.session_state.states_loaded,
                "counties": st.session_state.counties_loaded,
                "zipcodes": st.session_state.zipcodes_loaded,
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

