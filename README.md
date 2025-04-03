# Geospatial AI Assistant

A Python-based interactive geospatial analysis application that combines the power of Google's Gemini AI model with mapping capabilities to enable natural language interactions with geographic data.

## Features

- **AI-Powered Chat Interface**: Communicate with a geospatial-specialized AI assistant
- **Dynamic Map Visualization**: See results directly on an interactive map
- **Multiple Geospatial Operations**:
  - Location marking
  - Region highlighting (states, countries, continents)
  - Distance measurements and route visualization
  - Line drawing between points
  - Polygon creation
  - Circular radius visualization
  - Heatmap generation

## Requirements

- Python 3.7+
- Google Cloud project with Vertex AI API access
- Google Cloud service account credentials

## Installation

1. **Clone this repository**:
   ```
   git clone https://github.com/yourusername/geospatial-ai-assistant.git
   cd geospatial-ai-assistant
   ```

2. **Install dependencies**:
   ```
   pip install streamlit folium geopandas streamlit-folium google-cloud-aiplatform numpy pandas google-genai
   ```

3. **Set up Google Cloud credentials**:
   ```
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/credentials.json"
   ```

## Usage

1. **Start the application**:
   ```
   streamlit run app.py
   ```

2. **Interact with the AI**:
   - Type natural language questions or commands in the chat input
   - See responses and map visualizations in real-time
   - Use example queries from the sidebar to get started

## Example Queries

- "Show me the 10 largest cities in the United States"
- "Highlight Georgia on the map"
- "Draw a line connecting New York and Los Angeles"
- "Create a polygon around the Great Lakes region"
- "Show me the distance between Chicago and Miami"
- "Highlight the continent of Asia"

## How It Works

The application uses Google's Gemini model to interpret natural language queries about geographic data and locations. The AI returns structured JSON responses that the application translates into map actions using Folium and GeoPandas. Results are displayed in a user-friendly Streamlit interface.

## Customization

- **Change the base map**: Modify the `initialize_map()` function to use different map tiles
- **Add new map actions**: Extend the `process_map_actions()` function with additional capabilities
- **Customize the system prompt**: Update the system prompt in `get_gemini_response()` to change AI behavior
- **Add more datasets**: Create additional data loading functions similar to `get_us_states()`

## Project Structure

- `app.py`: Main application file containing all code
- Functionality is organized into modular functions:
  - Data handling: `get_us_states()`, `get_world_countries()`, `get_major_cities()`
  - AI interaction: `initialize_gemini_client()`, `get_gemini_response()`
  - Map processing: `process_map_actions()`, `find_region_by_name()`
  - UI components: Streamlit layout and interactions

## Notes

- The application uses GeoPandas' built-in natural earth datasets, which might be deprecated in future versions
- For production use, consider downloading and storing required geodata files locally
