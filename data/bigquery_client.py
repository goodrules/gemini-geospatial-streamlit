import streamlit as st
from google.cloud import bigquery
from config.credentials import get_credentials
from config.settings import PROJECT_ID

@st.cache_resource
def initialize_bigquery_client():
    """Initialize and return a BigQuery client using the same credentials as Gemini."""
    try:
        credentials = get_credentials()
        client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
        return client
    except Exception as e:
        st.error(f"Error initializing BigQuery client: {str(e)}")
        return None

def execute_query(query):
    """Execute a BigQuery query and return results as DataFrame"""
    client = initialize_bigquery_client()
    if not client:
        return None
    
    try:
        return client.query(query).to_dataframe()
    except Exception as e:
        st.error(f"Error executing query: {str(e)}")
        return None 
