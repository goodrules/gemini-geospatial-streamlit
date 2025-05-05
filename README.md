# Geospatial AI Assistant

A Python-based interactive geospatial analysis application that combines the power of Google's Gemini AI model with mapping capabilities to enable natural language interactions with geographic data and weather data from [Google WeatherNext](https://deepmind.google/technologies/weathernext/).

## Features

- **AI-Powered Chat Interface**: Communicate with a geospatial-specialized AI assistant
- **Dynamic Map Visualization**: See results directly on an interactive map
- **Multiple Geospatial Operations**:
  - Location marking and search
  - Region highlighting (states, counties, countries, continents)
  - Distance measurements and route visualization
  - Line drawing between points
  - Polygon creation
  - Circular radius visualization
  - Heatmap generation
  - Weather data visualization (temperature, precipitation, wind speed)
  - Wind risk analysis for power infrastructure

## Quick Start Guide

### Requirements

- Python 3.12+
- Google Cloud project with Vertex AI API access
- Google Cloud service account credentials

### Installation

1. **Clone this repository**:
   ```bash
   git clone https://github.com/yourusername/gemini-geospatial-streamlit.git
   cd gemini-geospatial-streamlit
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Google Cloud credentials**:
   
   a. **Install Google Cloud SDK**:
   - Download and install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
   - Run `gcloud init` to initialize the SDK
   
   b. **Set up Application Default Credentials**:
   ```bash
   gcloud auth application-default login
   ```
   This will open a browser window for you to sign in with your Google account
   
   c. **Alternative: Use a service account key file**:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
   ```

4. **Configure environment variables**:
   Create a `.env` file in the project root with:
   ```bash
   PROJECT_ID=your-project-id
   REGION=your-gcp-region  # e.g., us-central1
   ```

5. **Start the application**:
   ```bash
   streamlit run app.py
   ```

### Using the Application

1. **Chat Interface**: The left panel contains the chat interface where you can:
   - Type natural language questions about locations, maps, and weather
   - View AI responses and any additional structured data

2. **Interactive Map**: The right panel displays the map with visualizations based on your questions.

3. **Sidebar Options**:
   - Example queries to help you get started
   - Weather data date selector
   - Buttons to clear chat history or reload data

4. **Getting the best results**:
   - Be specific about locations (e.g., "Philadelphia, PA" instead of just "Philadelphia")
   - For weather data, specify the type (temperature, precipitation, wind speed)
   - Try the example queries to see different map capabilities

## Example Queries

### Geospatial
- "Show me the 10 largest cities in the United States"
- "Highlight Fulton County, Georgia on the map"
- "Draw a line connecting New York and Los Angeles"
- "Compare the land area of Travis County, TX and King County, WA"
- "Show all counties in Florida"
- "Highlight ZIP code 90210 on the map"

### Weather Data
- "Show the temperature forecast for California"
- "What is the wind speed forecast for Chicago?"
- "Display weather data for Texas"
- "Compare precipitation forecasts for Seattle and Miami"
- "Are any power lines at risk of high wind speed in the next 10 days in PA?"
- "Show me wind risk for power lines in Crawford County for the next 5 days"

## New Features

- **Wind Risk Analysis**: Analyze and visualize areas where power infrastructure may be affected by high winds
- **Multiple Weather Event Support**: Handle and visualize multiple wind or weather events across different dates
- **Improved Location Search**: Enhanced location matching for more accurate region highlighting
- **Power Line Visualization**: Display Pennsylvania's power transmission network

## Troubleshooting

- **BigQuery Connection Issues**: The app includes fallback data if BigQuery isn't available
- **Map Not Updating**: Use the "Clear Cache" button in the sidebar or the "Clear cache" option in the Streamlit menu
- **Missing Visualizations**: Ensure your query is specific about the location and data type
- **Performance Issues**: Weather data processing can be resource-intensive; try filtering by specific dates

## Notes

- Weather data is based on forecasts available via [Google WeatherNext](https://deepmind.google/technologies/weathernext/).
- Local datasets (like power lines and flood zones) are currently limited to specific areas (e.g., Pennsylvania).
- The application uses cached data to improve performance; use the "Reload Geospatial Data" button if needed

## Contributors

- [goodrules](https://github.com/goodrules)
- [dklanac](https://github.com/dklanac)
