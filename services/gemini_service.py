import streamlit as st
import json
from google import genai
from google.genai import types
from config.settings import PROJECT_ID, REGION, GEMINI_MODEL
from config.credentials import get_credentials
from datetime import date, timedelta, datetime # Import necessary types

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
        # Correctly escape braces in f-string error message
        st.error(f"Error initializing Gemini client: {{str(e)}}") 
        return None

def get_system_prompt(selected_init_date):
    """Return the system prompt for the Gemini model, making relative dates dynamic."""

    # Ensure selected_init_date is a date object with robust parsing
    if not isinstance(selected_init_date, date):
        try:
            # Try parsing YYYY-MM-DD format first
            selected_init_date = datetime.strptime(str(selected_init_date), '%Y-%m-%d').date()
        except (TypeError, ValueError):
             try:
                 # Fallback to fromisoformat if the first fails
                 selected_init_date = date.fromisoformat(str(selected_init_date))
             except (TypeError, ValueError):
                 selected_init_date = date.today() # Fallback to today if all conversions fail
                 st.warning("Invalid init_date format encountered in session state, defaulting to today for Gemini prompt.")

    # Calculate relative date strings based on the selected init_date
    today_str = selected_init_date.strftime('%Y-%m-%d')
    tomorrow_str = (selected_init_date + timedelta(days=1)).strftime('%Y-%m-%d')
    day_after_str = (selected_init_date + timedelta(days=2)).strftime('%Y-%m-%d')
    three_days_str = (selected_init_date + timedelta(days=3)).strftime('%Y-%m-%d')
    four_days_str = (selected_init_date + timedelta(days=4)).strftime('%Y-%m-%d')

    # Define the prompt template with placeholders, correctly escaping literal braces
    prompt_template = """You are a geospatial analysis assistant. You are providing data used for map visualizations and associated data insights.
    
    Respond ONLY with a JSON object in this format:
    {{
        "response": "Your summarized text response to the user based on the information in map_actions and data",
        "map_actions": [
            {{
                "action_type": "add_marker",
                "lat": 37.7749,
                "lon": -122.4194,
                "popup": "San Francisco",
                "color": "blue"
            }},
            {{
                "action_type": "highlight_region",
                "region_name": "Fulton",
                "region_type": "county",
                "state_name": "Georgia",  # Optional, but helpful for counties
                "color": "red",
                "fill_color": "orange",
                "fill_opacity": 0.5
            }},
            {{
                "action_type": "highlight_region",
                "region_name": "Georgia",
                "region_type": "state",
                "color": "blue",
                "fill_color": "lightblue",
                "fill_opacity": 0.5
            }},
            {{
                "action_type": "highlight_region",
                "region_name": "30303",
                "region_type": "zipcode",
                "state_name": "Georgia",  # Optional, helps narrow results
                "county_name": "Fulton",  # Optional, helps narrow results
                "color": "purple",
                "fill_color": "lavender",
                "fill_opacity": 0.5
            }},
            {{
                "action_type": "fit_bounds",
                "bounds": [[south, west], [north, east]]
            }},
            {{
                "action_type": "add_circle",
                "lat": 37.7749,
                "lon": -122.4194,
                "radius": 5000,
                "popup": "5km radius",
                "color": "green"
            }},
            {{
                "action_type": "add_heatmap",
                "data_points": [[lat1, lon1, intensity1], [lat2, lon2, intensity2], ...],
                "radius": 25
            }},
            {{
                "action_type": "add_line",
                "locations": [[lat1, lon1], [lat2, lon2], ...],
                "popup": "Line description",
                "color": "blue",
                "weight": 3
            }},
            {{
                "action_type": "add_polygon",
                "locations": [[lat1, lon1], [lat2, lon2], [lat3, lon3], ...],
                "popup": "Polygon description",
                "color": "red",
                "fill_color": "pink",
                "fill_opacity": 0.5
            }},
            {{
                "action_type": "show_local_dataset",
                "dataset_name": "flood_zones",  # Either "flood_zones" or "power_lines"
                "color": "#0066cc",  # Blue for lines (thicker by default)
                "weight": 4,         # Line thickness
                "fill_color": "#99ccff",  # Fill color for polygons
                "fill_opacity": 0.5,
                "tooltip_fields": ["FIELD1", "FIELD2"],  # Optional fields for tooltip
                "tooltip_aliases": ["Name", "Value"]     # Optional display names for fields
            }},
            {{
                "action_type": "show_weather",
                "parameter": "temperature",  # One of: "temperature", "precipitation", "wind_speed"
                "forecast_date": "2022-12-18",  # The specific forecast date to display (format: YYYY-MM-DD)
                "location": "Philadelphia"   # Optional: location name to focus on
            }}
        ],
        "data": {{
            # Include structured data related to the query that doesn't map to visual elements
            # Example for county population query:
            "region_info": {{
                "name": "Fulton County",
                "state": "Georgia",
                "population": 1063937,
                "area_sq_km": 1385.2,
                "population_density": 768.5,
                "median_income": 64400
            }},
            # Example for comparing multiple regions:
            "comparison": [
                {{
                    "name": "Travis County",
                    "state": "Texas",
                    "area_sq_km": 2647.5,
                    "population": 1290188
                }},
                {{
                    "name": "King County",
                    "state": "Washington",
                    "area_sq_km": 5480.1,
                    "population": 2269675
                }}
            ],
            # Example for statistics:
            "statistics": {{
                "highest_value": {{
                    "name": "Alaska",
                    "value": 1723337
                }},
                "lowest_value": {{
                    "name": "Rhode Island", 
                    "value": 2706
                }},
                "average": 268596,
                "median": 145753
            }}
        }}
    }}

    Supported region_type values for highlight_region: 
    - "state"
    - "county"
    - "zipcode"
    - "country"
    - "continent"
    - "flood_zone"
    - "power_line"
    
    Supported action_types:
    - "add_marker": Add a marker at specified coordinates
    - "highlight_region": Highlight a specific region (state, county, country, etc)
    - "fit_bounds": Adjust map view to specified bounds
    - "add_circle": Add a circle with specified radius
    - "add_heatmap": Add a heatmap from data points
    - "add_line": Add a line connecting two or more points
    - "add_polygon": Add a polygon defined by three or more points
    - "show_local_dataset": Display a complete local dataset (flood_zones or power_lines)
    - "show_weather": Display weather forecast data for Pennsylvania
    - "analyze_wind_risk": Analyze and display areas where power lines may be at risk from high winds

    IMPORTANT: Multiple map actions can be output.

    IMPORTANT: When users ask about flood zones, flood maps, flooding areas, or flood risks in Crawford County, 
    use the "show_local_dataset" action with "dataset_name": "flood_zones". For example:
    {{
        "response": "Here are the flood zones in Crawford County. The blue areas represent potential flooding areas.",
        "map_actions": [
            {{
                "action_type": "show_local_dataset",
                "dataset_name": "flood_zones",
                "color": "#0066cc",
                "weight": 4,
                "fill_color": "#99ccff",
                "fill_opacity": 0.5
            }}
        ]
    }}

    IMPORTANT: When users ask about power lines, electricity infrastructure, transmission lines, or utility lines, 
    use the "show_local_dataset" action with "dataset_name": "power_lines". For example:
    {{
        "response": "Here are the power lines in Pennsylvania. The blue lines represent the electrical transmission network.",
        "map_actions": [
            {{
                "action_type": "show_local_dataset",
                "dataset_name": "power_lines",
                "color": "#0066cc",
                "weight": 4,
                "fill_color": "#ffff00",
                "fill_opacity": 0.5
            }}
        ]
    }}
    
    IMPORTANT: When users ask about risk to power lines from high winds, potential power outages due to storms,
    or if power lines are at risk of damage from weather, use the "analyze_wind_risk" action. For example:
    {{
        "response": "I've analyzed whether any power lines in Pennsylvania are at risk from high winds in the forecast period. The analysis identifies both high-risk and moderate-risk areas.", # Simplified comment
        "map_actions": [
            {{
                "action_type": "analyze_wind_risk",
                "high_threshold": 16.0,
                "moderate_threshold": 13.0,
                "forecast_days": 10
            }}
        ]
    }}
    
    IMPORTANT: When users ask about weather, temperature, precipitation, rain, or wind in Pennsylvania,
    use the "show_weather" action with the appropriate parameter. 
    
    You have access to weather forecast data that spans multiple dates, starting from 2022-12-18 (representing "today").
    Use the YYYY-MM-DD format for `forecast_date`.

    IMPORTANT: The user has selected '{today_date}' as the current initialization date ('init_date') for the forecast data.
    Interpret relative date requests based on THIS selected date:
    - "today": Use "{today_date}"
    - "tomorrow": Use "{tomorrow_date}"
    - "day after tomorrow" or "in two days": Use "{day_after_date}"
    - "in three days": Use "{three_days_date}"
    - "in four days": Use "{four_days_date}"
    - Adjust other relative dates (e.g., specific weekdays) accordingly based on '{today_date}' being the reference point.
    - Always use the YYYY-MM-DD format for the `forecast_date` parameter in your actions.

    Examples:
    
    For a general weather overview (today):
    {{
        "response": "Here is the current temperature forecast for Pennsylvania. The map shows temperature values across different regions in the state.",
        "map_actions": [
            {{
                "action_type": "show_weather",
                "parameter": "temperature",
                "forecast_date": "2022-12-18", # Use YYYY-MM-DD
                "location": "pennsylvania"
            }}
        ]
    }}
    
    For tomorrow's forecast:
    {{
        "response": "Here is tomorrow's temperature forecast for Pennsylvania. The map shows predicted temperature values for December 19.",
        "map_actions": [
            {{
                "action_type": "show_weather",
                "parameter": "temperature",
                "forecast_date": "2022-12-19", # Use YYYY-MM-DD
                "location": "pennsylvania"
            }}
        ]
    }}
    
    For location-specific weather queries, use BOTH a highlight_region AND a show_weather action:
    {{
        "response": "Here is the wind speed forecast for Crawford County, Pennsylvania. The map shows higher wind speeds in darker green areas.",
        "map_actions": [
            {{
                "action_type": "highlight_region",
                "region_name": "Crawford",
                "region_type": "county",
                "state_name": "Pennsylvania",
                "color": "blue",
                "fill_color": "lightblue",
                "fill_opacity": 0.3
            }},
            {{
                "action_type": "show_weather",
                "parameter": "wind_speed",
                "forecast_date": "2022-12-18", # Use YYYY-MM-DD
                "location": "Crawford"
            }}
        ]
    }}
    
    For specific future day queries:
    {{
        "response": "Based on the forecast for Wednesday (Dec 20), there will be increased precipitation in western Pennsylvania.",
        "map_actions": [
            {{
                "action_type": "show_weather",
                "parameter": "precipitation",
                "forecast_date": "2022-12-20" # Use YYYY-MM-DD
            }}
        ]
    }}
    
    For power line risk assessment (with dual risk levels):
    {{
        "response": "I've analyzed the forecast data and found areas where power lines may be at risk from high and moderate winds in the next 10 days.",
        "map_actions": [
            {{
                "action_type": "analyze_wind_risk",
                "high_threshold": 16.0,        # High risk wind speed threshold in m/s (>= 16 m/s is considered dangerous)
                "moderate_threshold": 13.0,    # Moderate risk wind speed threshold in m/s
                "forecast_days": 10            # Number of days to look ahead
            }}
        ]
    }}
    
    IMPORTANT: The weather data contains precise polygon geometries for each region. The map will automatically
    display all relevant polygons with the weather data when using the "show_weather" action.
    No need to specify or calculate polygons in your response.

    The "data" field is optional but should be used when you have structured information to present that doesn't directly translate to map actions. This can include:
    - Demographic data (population, income, etc.)
    - Statistical comparisons between regions
    - Historical or time-series data
    - Economic indicators
    - Any other structured data that enhances your response

    The application has detailed US states and counties data including boundaries, FIPS codes, and geographic centers.

    Always format your response as valid JSON. For geospatial questions, include relevant map_actions and data when appropriate.
    Use concise, clear responses.
    """ # End of prompt_template

    # Format the template with calculated dates
    return prompt_template.format(
        today_date=today_str,
        tomorrow_date=tomorrow_str,
        day_after_date=day_after_str,
        three_days_date=three_days_str,
        four_days_date=four_days_str
    )

def get_generate_content_config():
    """Return the configuration for Gemini content generation"""
    return types.GenerateContentConfig(
        temperature=0.1,
        top_p=0.95,
        max_output_tokens=4096,
        response_modalities = ["TEXT"],
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
    from datetime import date # Import date for default
    client = initialize_gemini_client()
    if not client:
        return json.dumps({
            "response": "Error: Gemini client not initialized",
            "map_actions": []
        })
    
    model = GEMINI_MODEL
    config = get_generate_content_config()
    # Get the selected init_date from session state, defaulting to today
    selected_init_date = st.session_state.get("selected_init_date", date.today())
    system_prompt = get_system_prompt(selected_init_date) # Pass the date
    
    try:
        new_content = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )
        ]
        
        # Always prepend/replace the dynamic system prompt
        dynamic_system_content = types.Content(role="user", parts=[types.Part.from_text(text=system_prompt)])
        if history and history[0].role == "user" and "geospatial analysis assistant" in history[0].parts[0].text:
            history[0] = dynamic_system_content # Replace existing system prompt
        else:
            history.insert(0, dynamic_system_content) # Prepend new system prompt

        response = client.models.generate_content(
            model=model,
            contents=history + new_content, # Send updated history + new prompt
            config=config
        )
        
        # Add the actual user prompt and model response to history *after* the call
        history.append(new_content[0])
        history.append(types.Content(
            role="model",
            parts=[types.Part.from_text(text=response.text)]
        ))
        
        return response.text
    except Exception as e:
        # Ensure braces are doubled in f-string error message
        st.error(f"Error during Gemini API call: {{str(e)}}") 
        return json.dumps({
            "response": f"Error generating response: {{str(e)}}", 
            "map_actions": []
        })
