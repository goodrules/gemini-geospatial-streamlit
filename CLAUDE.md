# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Streamlit application that enables natural language-driven geospatial analysis using Google Gemini AI, BigQuery, and various mapping technologies. The app helps analyze weather risks for infrastructure, particularly power lines.

## Common Commands

### Setup and Run
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
.\venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt

# Download data from GCS (if needed)
gsutil -m cp -r "gs://geoweatherrisk-data/data/**" "data/"

# Run the application
streamlit run app.py
```

### Authentication
- Requires Google Cloud credentials
- Use Application Default Credentials: `gcloud auth application-default login`
- Ensure credentials have access to BigQuery and Vertex AI

## High-Level Architecture

### Directory Structure
```
.
├── app.py                  # Main Streamlit application entry point
├── components/
│   ├── gemini_helper.py   # Gemini AI integration for query processing
│   ├── map_generator.py   # Map generation and action handling
│   └── sidebar.py         # UI sidebar with examples and instructions
├── utils/
│   ├── ui.py             # UI helper functions (CSS, formatting)
│   └── utils.py          # General utilities
├── data/                  # Local data files (CSV, GeoJSON)
├── sample_queries.json    # Example queries for the sidebar
└── requirements.txt       # Python dependencies
```

### Key Components

1. **Two-Column Layout**:
   - Left: AI response panel with Gemini-generated analysis
   - Right: Interactive map visualization (Folium)

2. **Gemini AI Integration** (`components/gemini_helper.py`):
   - Processes natural language queries
   - Generates BigQuery SQL
   - Returns structured map actions for visualization
   - Uses `llm_sql_model` for SQL generation and `llm_text_model` for analysis

3. **Map Processing Pipeline** (`components/map_generator.py`):
   - Parses AI responses for map action objects
   - Supports multiple action types: SQL, CSV, GeoJSON, Markers
   - Renders data on Folium maps with appropriate styling

4. **Session State Management**:
   - Tracks conversation history
   - Maintains current map state
   - Preserves data loading status

### Data Sources
- **BigQuery**: Weather and infrastructure data via `bigquery-public-data.noaa_gsod` and custom datasets
- **Local Files**: CSV and GeoJSON files in the `data/` directory
- **Google Cloud Storage**: Downloadable datasets from `gs://geoweatherrisk-data/`

## Tech Stack
- **Streamlit** 1.41.1: Web application framework
- **Google Generative AI** 0.8.3: Gemini AI integration
- **Folium** 0.19.0: Interactive mapping
- **Pandas** & **GeoPandas**: Data manipulation
- **BigQuery**: Data warehouse for large-scale geospatial queries

## Coding Standards (from .cursor/rules/)
- Use Google style docstrings
- Type hints for all function parameters
- Error handling with informative messages
- Session state for user interactions
- Extract long logic into separate functions
- Use CSS in utils/ui.py for consistent styling

## Development Tips
1. **Adding New Map Actions**: Extend the pattern matching in `map_generator.py`
2. **Custom Queries**: Add to `sample_queries.json` for sidebar examples
3. **Styling**: Modify CSS in `utils/ui.py` for UI changes
4. **New Data Sources**: Add handlers in `process_dataframes()` function