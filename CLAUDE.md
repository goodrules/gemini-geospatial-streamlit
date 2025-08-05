# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Streamlit application that enables natural language-driven geospatial analysis using Google Gemini AI, BigQuery, and various mapping technologies. The app helps analyze weather risks for infrastructure, particularly power lines.

## Core Development Principles

### Code Reuse and Extension
- **Always prefer reusing or extending existing code** before creating new implementations
- Before writing new functionality, search for similar patterns in:
  - `components/` - Check existing component implementations
  - `utils/` - Look for reusable utility functions
  - Extend existing classes rather than creating parallel implementations
- When extending functionality, use inheritance or composition appropriately

### API Design Philosophy
- **Do not maintain backwards compatibility** - Focus on clean, optimal design
- **Allow breaking API changes** when they improve the codebase
- Refactor aggressively when it leads to better architecture
- Document breaking changes clearly in commit messages

### Pythonic Code Standards
- **Strive for clean, Pythonic code** - When in doubt, follow the Zen of Python
- Run `import this` to review Python's guiding principles
- Key principles to emphasize:
  - Explicit is better than implicit
  - Simple is better than complex
  - Readability counts
  - There should be one-- and preferably only one --obvious way to do it
  - If the implementation is hard to explain, it's a bad idea

### Dependency Injection Pattern
- **Always use explicit dependency injection** when composing classes
- Pass dependencies through constructors, not import them directly
- Example pattern:
  ```python
  # Good - Explicit dependency injection
  class MapGenerator:
      def __init__(self, gemini_client: GeminiClient, bigquery_client: BigQueryClient):
          self.gemini_client = gemini_client
          self.bigquery_client = bigquery_client
  
  # Bad - Direct imports/instantiation
  class MapGenerator:
      def __init__(self):
          self.gemini_client = GeminiClient()  # Avoid this
  ```

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

# Run linting and type checking
ruff check .
mypy .
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

## Architectural Patterns

### Component Design
- Use composition over inheritance where appropriate
- Keep components focused on a single responsibility
- Inject dependencies rather than creating them internally
- Example structure:
  ```python
  class GeminiHelper:
      def __init__(self, 
                   text_model: GenerativeModel,
                   sql_model: GenerativeModel,
                   bigquery_client: Client):
          self.text_model = text_model
          self.sql_model = sql_model
          self.bigquery_client = bigquery_client
  ```

### Error Handling
- Use specific exception types
- Provide informative error messages
- Let exceptions bubble up to appropriate handlers
- Example:
  ```python
  class QueryGenerationError(Exception):
      """Raised when SQL query generation fails"""
      pass
  ```

### State Management
- Use Streamlit session state for UI state
- Keep business logic separate from UI state
- Pass state explicitly to functions that need it

## Tech Stack
- **Streamlit** 1.41.1: Web application framework
- **Google Generative AI** 0.8.3: Gemini AI integration
- **Folium** 0.19.0: Interactive mapping
- **Pandas** & **GeoPandas**: Data manipulation
- **BigQuery**: Data warehouse for large-scale geospatial queries

## Coding Standards

### Python Style Guide
- Use Google style docstrings with full type annotations
- Type hints for all function parameters and return values
- Maximum line length: 100 characters
- Use f-strings for string formatting
- Prefer list comprehensions and generator expressions where readable

### Import Organization
```python
# Standard library imports
import json
from typing import Dict, List, Optional

# Third-party imports
import pandas as pd
import streamlit as st

# Local imports
from components.gemini_helper import GeminiHelper
from utils.ui import apply_custom_css
```

### Function Design
- Keep functions small and focused
- Extract complex logic into well-named helper functions
- Use descriptive parameter names
- Example:
  ```python
  def process_geospatial_query(
      query: str,
      gemini_helper: GeminiHelper,
      map_config: Dict[str, Any]
  ) -> Optional[FoliumMap]:
      """Process natural language query and generate map visualization.
      
      Args:
          query: Natural language query from user
          gemini_helper: Injected Gemini AI helper instance
          map_config: Configuration for map generation
          
      Returns:
          Generated Folium map or None if processing fails
      """
  ```

### Class Design
- Use dataclasses for simple data containers
- Implement `__str__` and `__repr__` for debugging
- Keep inheritance hierarchies shallow
- Favor composition and dependency injection

## Extension Patterns

### Adding New Map Actions
1. First check if existing action types in `map_generator.py` can be extended
2. If new action needed, extend the existing pattern matching system:
   ```python
   # Extend existing action processor
   class MapActionProcessor:
       def process_action(self, action: Dict[str, Any]) -> FoliumLayer:
           # Add new action type to existing switch
           if action['type'] == 'new_type':
               return self._process_new_type(action)
   ```

### Adding New Data Sources
1. Check if existing data loaders in `process_dataframes()` can handle the format
2. Extend existing loader rather than creating new function:
   ```python
   # Extend existing loader
   def load_data_source(path: str, source_type: str) -> pd.DataFrame:
       # Add new source type to existing function
       if source_type == 'new_format':
           return self._load_new_format(path)
   ```

### Modifying UI Components
1. Check existing CSS in `utils/ui.py` before adding new styles
2. Extend existing style functions rather than creating duplicates
3. Use CSS variables for consistent theming

## Development Workflow

### Before Writing Code
1. Search for existing implementations
2. Check if functionality can be extended
3. Review similar patterns in the codebase
4. Plan for dependency injection

### Code Review Checklist
- [ ] Reused/extended existing code where possible
- [ ] Used explicit dependency injection
- [ ] Followed Pythonic conventions
- [ ] Added comprehensive type hints
- [ ] Wrote clear docstrings
- [ ] Handled errors appropriately
- [ ] No backwards compatibility concerns

### Testing Approach
- Write tests that focus on behavior, not implementation
- Use dependency injection to make testing easier
- Mock external services (BigQuery, Gemini) in tests
- Test edge cases and error conditions

## Common Pitfalls to Avoid
1. Creating new utilities when similar ones exist
2. Hard-coding dependencies instead of injecting them
3. Writing overly complex solutions when simple ones suffice
4. Maintaining backwards compatibility unnecessarily
5. Creating parallel implementations instead of extending

## Quick Reference

### Frequently Extended Components
- `GeminiHelper`: Add new query types or processing logic
- `MapGenerator`: Add new visualization types
- `process_dataframes()`: Add new data source handlers
- `apply_custom_css()`: Add new UI styling

### Design Decisions
- Breaking changes are acceptable for cleaner code
- Composition > Inheritance
- Explicit > Implicit
- Simple > Complex
- Extend > Duplicate