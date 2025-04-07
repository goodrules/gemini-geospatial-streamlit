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
   pip install -r requirements.txt
   ```

3. **Set up Google Cloud credentials**:
   
   a. **Install Google Cloud SDK**:
   - Download and install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
   - Run `gcloud init` to initialize the SDK
   
   b. **Set up Application Default Credentials**:
   - Run the following command:
      ```
      gcloud auth application-default login` to set up your user credentials
      ```
   - This will open a browser window where you can sign in with your Google account
   - Alternatively, if using a service account:
     ```
     export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
     ```

1. **Set up environment variables**:
   - Create a `.env` file in the project root directory
   - Add the following variables:
     ```
     GOOGLE_CLOUD_PROJECT=your-project-id
     REGION=your-gcp-region
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

The application has been refactored into a modular structure:

- `app.py`: Main application entry point that initializes components and manages layout
- `config/`: Configuration files and settings
  - `settings.py`: Application settings, constants, and session state initialization
  - `credentials.py`: Handles Google Cloud credentials
- `data/`: Data loading and processing modules
  - `bigquery_client.py`: BigQuery client initialization and query execution
  - `geospatial_data.py`: Functions for loading and processing geospatial data 
  - `fallback_data.py`: Fallback data sources when BigQuery is unavailable
- `components/`: UI components and Streamlit widgets
  - `sidebar.py`: Sidebar UI elements and example queries
  - `chat.py`: Chat interface components and message display
  - `map.py`: Map display and interaction
- `services/`: Business logic and external services
  - `gemini_service.py`: Gemini AI API interaction
  - `map_processor.py`: Processes map actions from AI responses
- `utils/`: Utility functions
  - `geo_utils.py`: Geospatial utility functions
  - `streamlit_utils.py`: Streamlit-specific helper functions

## Caching and Cache Management

The application uses Streamlit's caching mechanism to improve performance. Here are some common scenarios when you might need to clear the cache:

1. **After Code Changes**: When you modify functions decorated with `@st.cache_data` or `@st.cache_resource`, you'll need to clear the cache to see the changes take effect.

2. **Data Updates**: If your underlying data sources have changed but the cached results are still being used.

3. **Memory Management**: If you notice high memory usage from accumulated cached results.

To clear the cache, you can:

1. **Use the UI**: Click the "Clear cache" button in the Streamlit app's hamburger menu (☰).

2. **During Development**: Press 'C' while the app is running to clear the cache.

Remember that cached values are available to all users of your app. If you need to save results that should only be accessible within a session, use Session State instead.

## Notes

- The application uses GeoPandas' built-in natural earth datasets, which might be deprecated in future versions
- For production use, consider downloading and storing required geodata files locally

