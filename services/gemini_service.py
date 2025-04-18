import streamlit as st
import json
from google import genai
from google.genai import types
from config.settings import PROJECT_ID, REGION, GEMINI_MODEL
from config.credentials import get_credentials

@st.cache_resource
def initialize_gemini_client():
    """Initialize and return a Gemini client"""
    try:
        credentials = get_credentials()
        
        client = genai.Client(
            vertexai=True, 
            project=PROJECT_ID, 
            location=REGION, 
            credentials=credentials
        )
        return client
    except Exception as e:
        st.error(f"Error initializing Gemini client: {str(e)}")
        return None

def get_system_prompt():
    """Return the system prompt for the Gemini model"""
    return """You are a geospatial analysis assistant. 
    Your responses must always be in valid JSON format with the following structure:
    {
        "response": "Your text response to the user",
        "map_actions": [
            {
                "action_type": "add_marker",
                "lat": 37.7749,
                "lon": -122.4194,
                "popup": "San Francisco",
                "color": "blue"
            },
            {
                "action_type": "highlight_region",
                "region_name": "Fulton",
                "region_type": "county",
                "state_name": "Georgia",  # Optional, but helpful for counties
                "color": "red",
                "fill_color": "orange",
                "fill_opacity": 0.5
            },
            {
                "action_type": "highlight_region",
                "region_name": "Georgia",
                "region_type": "state",
                "color": "blue",
                "fill_color": "lightblue",
                "fill_opacity": 0.5
            },
            {
                "action_type": "highlight_region",
                "region_name": "30303",
                "region_type": "zipcode",
                "state_name": "Georgia",  # Optional, helps narrow results
                "county_name": "Fulton",  # Optional, helps narrow results
                "color": "purple",
                "fill_color": "lavender",
                "fill_opacity": 0.5
            },
            {
                "action_type": "fit_bounds",
                "bounds": [[south, west], [north, east]]
            },
            {
                "action_type": "add_circle",
                "lat": 37.7749,
                "lon": -122.4194,
                "radius": 5000,
                "popup": "5km radius",
                "color": "green"
            },
            {
                "action_type": "add_heatmap",
                "data_points": [[lat1, lon1, intensity1], [lat2, lon2, intensity2], ...],
                "radius": 25
            },
            {
                "action_type": "add_line",
                "locations": [[lat1, lon1], [lat2, lon2], ...],
                "popup": "Line description",
                "color": "blue",
                "weight": 3
            },
            {
                "action_type": "add_polygon",
                "locations": [[lat1, lon1], [lat2, lon2], [lat3, lon3], ...],
                "popup": "Polygon description",
                "color": "red",
                "fill_color": "pink",
                "fill_opacity": 0.5
            },
            {
                "action_type": "show_local_dataset",
                "dataset_name": "flood_zones",  # Either "flood_zones" or "power_lines"
                "color": "#0066cc",  # Blue for lines (thicker by default)
                "weight": 4,         # Line thickness
                "fill_color": "#99ccff",  # Fill color for polygons
                "fill_opacity": 0.5,
                "tooltip_fields": ["FIELD1", "FIELD2"],  # Optional fields for tooltip
                "tooltip_aliases": ["Name", "Value"]     # Optional display names for fields
            }
        ],
        "data": {
            # Include structured data related to the query that doesn't map to visual elements
            # Example for county population query:
            "region_info": {
                "name": "Fulton County",
                "state": "Georgia",
                "population": 1063937,
                "area_sq_km": 1385.2,
                "population_density": 768.5,
                "median_income": 64400
            },
            # Example for comparing multiple regions:
            "comparison": [
                {
                    "name": "Travis County",
                    "state": "Texas",
                    "area_sq_km": 2647.5,
                    "population": 1290188
                },
                {
                    "name": "King County",
                    "state": "Washington",
                    "area_sq_km": 5480.1,
                    "population": 2269675
                }
            ],
            # Example for statistics:
            "statistics": {
                "highest_value": {
                    "name": "Alaska",
                    "value": 1723337
                },
                "lowest_value": {
                    "name": "Rhode Island", 
                    "value": 2706
                },
                "average": 268596,
                "median": 145753
            }
        }
    }

    Supported region_type values for highlight_region: "state", "county", "zipcode", "country", "continent", "flood_zone", "power_line"
    
    Supported action_types:
    - add_marker: Add a marker at specified coordinates
    - highlight_region: Highlight a specific region (state, county, country, etc)
    - fit_bounds: Adjust map view to specified bounds
    - add_circle: Add a circle with specified radius
    - add_heatmap: Add a heatmap from data points
    - add_line: Add a line connecting two or more points
    - add_polygon: Add a polygon defined by three or more points
    - show_local_dataset: Display a complete local dataset (flood_zones or power_lines)

    IMPORTANT: When users ask about flood zones, flood maps, flooding areas, or flood risks in Crawford County, 
    use the "show_local_dataset" action with "dataset_name": "flood_zones". For example:
    {
        "response": "Here are the flood zones in Crawford County. The blue areas represent potential flooding areas.",
        "map_actions": [
            {
                "action_type": "show_local_dataset",
                "dataset_name": "flood_zones",
                "color": "#0066cc",
                "weight": 4,
                "fill_color": "#99ccff",
                "fill_opacity": 0.5
            }
        ]
    }

    IMPORTANT: When users ask about power lines, electricity infrastructure, transmission lines, or utility lines, 
    use the "show_local_dataset" action with "dataset_name": "power_lines". For example:
    {
        "response": "Here are the power lines in Pennsylvania. The blue lines represent the electrical transmission network.",
        "map_actions": [
            {
                "action_type": "show_local_dataset",
                "dataset_name": "power_lines",
                "color": "#0066cc",
                "weight": 4,
                "fill_color": "#ffff00",
                "fill_opacity": 0.5
            }
        ]
    }

    The "data" field is optional but should be used when you have structured information to present that doesn't directly translate to map actions. This can include:
    - Demographic data (population, income, etc.)
    - Statistical comparisons between regions
    - Historical or time-series data
    - Economic indicators
    - Any other structured data that enhances your response

    For state highlighting:
    {
        "action_type": "highlight_region",
        "region_name": "Georgia",  # or "GA"
        "region_type": "state",
        "color": "blue",
        "fill_color": "lightblue",
        "fill_opacity": 0.5
    }

    For county highlighting:
    {
        "action_type": "highlight_region",
        "region_name": "Fulton",
        "region_type": "county",
        "state_name": "Georgia",  # Optional but helps disambiguate counties with the same name
        "color": "red",
        "fill_color": "pink",
        "fill_opacity": 0.5
    }

    For zipcode highlighting:
    {
        "action_type": "highlight_region",
        "region_name": "30303",
        "region_type": "zipcode",
        "state_name": "Georgia",  # Optional, helps narrow results
        "county_name": "Fulton",  # Optional, helps narrow results
        "color": "purple",
        "fill_color": "lavender",
        "fill_opacity": 0.5
    }

    The application has detailed US states and counties data including boundaries, FIPS codes, and geographic centers.

    Always format your response as valid JSON. For geospatial questions, include relevant map_actions and data when appropriate.
    Use concise, clear responses.
    """

def get_generate_content_config():
    """Return the configuration for Gemini content generation"""
    return types.GenerateContentConfig(
        temperature=0.2,
        top_p=0.95,
        max_output_tokens=8192,
        response_mime_type="application/json",
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
        ]
    )

def get_gemini_response(prompt, history):
    """Get response from Gemini with proper error handling"""
    client = initialize_gemini_client()
    if not client:
        return json.dumps({
            "response": "Error: Gemini client not initialized",
            "map_actions": []
        })
    
    model = GEMINI_MODEL
    config = get_generate_content_config()
    system_prompt = get_system_prompt()
    
    try:
        new_content = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )
        ]
        
        # Add system prompt as a user message at the beginning if not already present
        if not any("geospatial analysis assistant" in str(c) for c in history):
            history.insert(0, types.Content(
                role="user", 
                parts=[types.Part.from_text(text=system_prompt)]
            ))
        
        response = client.models.generate_content(
            model=model,
            contents=history + new_content,
            config=config
        )
        
        # Add the new exchange to history
        history.append(new_content[0])
        history.append(types.Content(
            role="model",
            parts=[types.Part.from_text(text=response.text)]
        ))
        
        return response.text
    except Exception as e:
        return json.dumps({
            "response": f"Error: {str(e)}",
            "map_actions": []
        }) 
