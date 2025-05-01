import streamlit as st
import pandas as pd
import json
import geopandas as gpd
from shapely.geometry import shape
from shapely import wkt # Ensure wkt is imported
import folium
from branca.colormap import LinearColormap
from data.weather_data import get_weather_forecast_data
from data.geospatial_data import get_pa_power_lines
from services.map_core import serialize_geojson
from services.weather_service import get_weather_color_scale

def analyze_wind_risk(weather_gdf, power_lines_gdf, high_threshold=16.0, moderate_threshold=13.0):
    """
    Analyze risk to power lines from high and moderate winds
    
    Args:
        weather_gdf: GeoDataFrame with weather forecast data
        power_lines_gdf: GeoDataFrame with power line geometries
        high_threshold: High risk wind speed threshold in m/s (default: 16.0 m/s)
        moderate_threshold: Moderate risk wind speed threshold in m/s (default: 13.0 m/s)
        
    Returns:
        risk_events: Dictionary mapping event IDs to GeoDataFrames of risk areas for that event.
        summary: Dictionary with overall risk summary information.
    """
    try:
        # Ensure forecast_time is datetime
        if 'forecast_time' not in weather_gdf.columns:
             st.error("Weather data for risk analysis missing 'forecast_time'.")
             return None, {"risk_found": False, "message": "Missing 'forecast_time'."}
        try:
            weather_gdf['forecast_time'] = pd.to_datetime(weather_gdf['forecast_time'], errors='coerce')
            # Ensure UTC
            if weather_gdf['forecast_time'].dt.tz is None:
                 weather_gdf['forecast_time'] = weather_gdf['forecast_time'].dt.tz_localize('UTC')
            else:
                 weather_gdf['forecast_time'] = weather_gdf['forecast_time'].dt.tz_convert('UTC')
            weather_gdf.dropna(subset=['forecast_time'], inplace=True)
        except Exception as e:
            st.error(f"Error processing forecast timestamps for risk analysis: {e}")
            return None, {"risk_found": False, "message": "Timestamp processing error."}

        # 1. Filter weather data for winds above moderate threshold
        wind_risk_areas = weather_gdf[weather_gdf['wind_speed'] >= moderate_threshold].copy()
        
        if wind_risk_areas.empty:
            return None, {
                "risk_found": False,
                "message": f"No areas with wind speeds over {moderate_threshold} m/s found in the forecast period."
            }
        
        # Classify risk levels
        wind_risk_areas['risk_level'] = 'moderate'
        wind_risk_areas.loc[wind_risk_areas['wind_speed'] >= high_threshold, 'risk_level'] = 'high'
        
        # Count areas in each risk category
        high_risk_count = len(wind_risk_areas[wind_risk_areas['risk_level'] == 'high'])
        moderate_risk_count = len(wind_risk_areas[wind_risk_areas['risk_level'] == 'moderate'])
            
        # 2. Prepare power lines data
        if power_lines_gdf is None:
            power_lines_gdf = get_pa_power_lines()
            
        if power_lines_gdf is None or power_lines_gdf.empty:
            return wind_risk_areas, {
                "risk_found": True,
                "message": f"Found areas with high ({high_risk_count}) and moderate ({moderate_risk_count}) wind risk, but no power line data available for detailed assessment.",
                "high_risk_areas": high_risk_count,
                "moderate_risk_areas": moderate_risk_count,
                # Get unique dates as strings
                "affected_dates": sorted(list(set(wind_risk_areas['forecast_time'].dt.strftime('%Y-%m-%d').unique()))),
                "max_wind_speed": wind_risk_areas['wind_speed'].max()
            }

        # 3. Create a buffer around power lines (approximately 1km buffer)
        # Convert to a projected CRS for accurate buffering
        power_lines_proj = power_lines_gdf.to_crs("EPSG:3857")  # Web Mercator
        buffered_lines = power_lines_proj.buffer(1000)  # 1km buffer
        buffered_lines_gdf = gpd.GeoDataFrame(power_lines_gdf, geometry=buffered_lines)
        buffered_lines_gdf = buffered_lines_gdf.to_crs("EPSG:4326")  # Back to WGS84
        
        # 4. Perform spatial join to find intersections
        # Convert risk areas to same CRS
        wind_risk_areas_proj = wind_risk_areas.to_crs("EPSG:4326")
        
        # Perform spatial join - find where wind risk areas intersect with power line buffers
        risk_areas = gpd.sjoin(wind_risk_areas_proj, buffered_lines_gdf, how="inner", predicate="intersects")
        
        if risk_areas.empty:
            return wind_risk_areas, {
                "risk_found": True,
                "message": f"Found areas with high ({high_risk_count}) and moderate ({moderate_risk_count}) wind risk, but none affect power lines.",
                "high_risk_areas": high_risk_count,
                "moderate_risk_areas": moderate_risk_count,
                 # Get unique dates as strings
                "affected_dates": sorted(list(set(wind_risk_areas['forecast_time'].dt.strftime('%Y-%m-%d').unique()))),
                "max_wind_speed": wind_risk_areas['wind_speed'].max()
            }

        # 5. Calculate risk metrics
        # Add a risk score - percentage scale
        max_possible_wind = risk_areas['wind_speed'].max()
        min_threshold = moderate_threshold
        risk_areas['risk_score'] = ((risk_areas['wind_speed'] - min_threshold) / 
                                    (max_possible_wind - min_threshold) * 100)
        
        # Ensure risk score is between 0-100
        risk_areas['risk_score'] = risk_areas['risk_score'].clip(0, 100)
        
        # 6. Group data into events by date
        events = [] # List to hold summary dictionaries for each event date
        risk_events = {} # Dict to hold GeoDataFrames for each event date, keyed by event_id

        # Get unique dates (as date objects) to iterate through
        unique_dates = sorted(risk_areas['forecast_time'].dt.date.unique())

        # Process each date as a potential event
        for current_date_obj in unique_dates:
            # Filter risk_areas for the current date
            date_areas = risk_areas[risk_areas['forecast_time'].dt.date == current_date_obj].copy()
            current_date_str = current_date_obj.strftime('%Y-%m-%d') # String for event ID and summary

            # Skip if no data for this date
            if date_areas.empty:
                continue
                
            # Count risk levels
            high_count = len(date_areas[date_areas['risk_level'] == 'high'])
            moderate_count = len(date_areas[date_areas['risk_level'] == 'moderate'])
            
            # Skip if no significant risk
            if high_count + moderate_count == 0:
                continue

            # Create event ID using the date string
            event_id = f"wind_event_{current_date_str.replace('-', '')}"

            # Create a summary for this event
            event_summary = {
                "id": event_id,
                "date": current_date_str, # Store date as string
                "high_risk_count": high_count,
                "moderate_risk_count": moderate_count,
                "max_wind_speed": date_areas['wind_speed'].max(),
                "affected_km": len(date_areas) * 0.25,  # Rough estimate of affected area
                "risk_level": "High" if high_count > 0 else "Moderate"
            }
            
            # Add to events list
            events.append(event_summary)
            
            # Store the actual data for this event
            risk_events[event_id] = date_areas
        
        # 7. Prepare overall summary
        total_high_risk = sum(event['high_risk_count'] for event in events)
        total_moderate_risk = sum(event['moderate_risk_count'] for event in events)
        total_affected_km = sum(event['affected_km'] for event in events)
        max_wind_overall = max(event['max_wind_speed'] for event in events) if events else 0
        
        # Find date with highest risk
        if events:
            # Find event with the most high risk areas, break ties with moderate risk areas
            highest_risk_event = max(events, key=lambda x: (x['high_risk_count'], x['moderate_risk_count']))
            highest_risk_date_str = highest_risk_event['date'] # Date string
        else:
            highest_risk_date_str = "None"

        summary = {
            "risk_found": len(events) > 0,
            "message": f"Found {len(events)} potential wind events affecting power lines.",
            "event_count": len(events),
            "events": events,
            "high_risk_areas": total_high_risk,
            "moderate_risk_areas": total_moderate_risk,
            "affected_power_lines_km": total_affected_km,
            "highest_risk_date": highest_risk_date_str, # Store date string
            "max_wind_speed": max_wind_overall
        }
        
        return risk_events, summary
        
    except Exception as e:
        st.error(f"Error analyzing wind risk: {str(e)}")
        return None, {
            "risk_found": False,
            "message": f"Error analyzing wind risk: {str(e)}"
        }

def handle_analyze_wind_risk(action, m):
    """
    Handle the analyze_wind_risk action
    
    Args:
        action: The action dictionary with parameters
        m: The folium map object
        
    Returns:
        List of bounds to include in the overall map fitting
    """
    bounds = []
    
    # Parameters for risk analysis
    high_threshold = action.get("high_threshold", 16.0)  # High risk threshold (default 16 m/s)
    moderate_threshold = action.get("moderate_threshold", 13.0)  # Moderate risk threshold (default 13 m/s)
    # Get date from action (expecting "YYYY-MM-DD" list or single string) or session state
    selected_date_str = st.session_state.get("selected_forecast_date_str") # From UI
    action_dates = action.get("dates") # From Gemini (could be list or single string)

    try:
        # 1. Get all weather forecast data
        weather_df_all = get_weather_forecast_data()

        if weather_df_all is None or weather_df_all.empty:
            st.warning("No weather data available for risk analysis")
            return bounds

        # Ensure forecast_time is datetime
        if 'forecast_time' not in weather_df_all.columns:
             st.error("Weather data for risk analysis missing 'forecast_time'.")
             return bounds
        try:
            weather_df_all['forecast_time'] = pd.to_datetime(weather_df_all['forecast_time'], errors='coerce')
            # Ensure UTC
            if weather_df_all['forecast_time'].dt.tz is None:
                 weather_df_all['forecast_time'] = weather_df_all['forecast_time'].dt.tz_localize('UTC')
            else:
                 weather_df_all['forecast_time'] = weather_df_all['forecast_time'].dt.tz_convert('UTC')
            weather_df_all.dropna(subset=['forecast_time'], inplace=True)
        except Exception as e:
            st.error(f"Error processing forecast timestamps for risk analysis: {e}")
            return bounds

        if weather_df_all.empty:
            st.warning("No valid weather timestamps found for risk analysis.")
            return bounds

        # 2. Determine dates to filter by
        weather_df_filtered = weather_df_all
        filter_date_msg = "all available dates"

        # Prioritize UI selection
        if selected_date_str:
            try:
                selected_date_obj = pd.to_datetime(selected_date_str).date()
                weather_df_filtered = weather_df_all[weather_df_all['forecast_time'].dt.date == selected_date_obj].copy()
                filter_date_msg = f"date {selected_date_str}"
            except ValueError:
                 st.error(f"Invalid date format from UI selector: {selected_date_str}. Showing all dates.")
        # Use Gemini action dates if UI is "All Dates"
        elif action_dates:
            date_objs_to_filter = []
            if isinstance(action_dates, str): # Single date string
                try:
                    date_objs_to_filter.append(pd.to_datetime(action_dates).date())
                    filter_date_msg = f"date {action_dates}"
                except ValueError:
                     st.error(f"Invalid date format from action: {action_dates}. Showing all dates.")
            elif isinstance(action_dates, list): # List of date strings
                valid_dates = []
                for d_str in action_dates:
                    try:
                        date_objs_to_filter.append(pd.to_datetime(d_str).date())
                        valid_dates.append(d_str)
                    except ValueError:
                         st.warning(f"Ignoring invalid date format in list from action: {d_str}")
                if valid_dates:
                    weather_df_filtered = weather_df_all[weather_df_all['forecast_time'].dt.date.isin(date_objs_to_filter)].copy()
                    filter_date_msg = f"dates: {', '.join(valid_dates)}"
                else:
                     st.error("No valid dates provided in list from action. Showing all dates.")
            else:
                 st.warning("Unexpected format for 'dates' parameter in action. Showing all dates.")

        if weather_df_filtered.empty:
            st.warning("No weather data available for the specified dates")
            return bounds

        # 3. Convert filtered data to GeoDataFrame, handling WKT geometry errors robustly

        # Pre-filter for potentially valid polygon strings
        valid_polygon_mask = weather_df_filtered['geography_polygon'].notna() & \
                             weather_df_filtered['geography_polygon'].apply(lambda x: isinstance(x, str) and x.strip() != '')
        weather_df_potential = weather_df_filtered[valid_polygon_mask].copy()

        if weather_df_potential.empty:
            st.warning("[Risk Analysis] No rows with potentially valid polygon strings found in weather data.")
            return bounds

        geometries = []
        valid_indices = []
        shape_errors = 0

        # Iterate only over rows with potential polygons
        for index, row in weather_df_potential.iterrows():
            polygon_wkt = row['geography_polygon'] # Expecting WKT string
            try:
                # Use shapely.wkt.loads to parse the WKT string directly
                polygon = wkt.loads(polygon_wkt)
                if polygon.is_valid: # Check validity after loading
                    geometries.append(polygon)
                    valid_indices.append(index) # Store index of successfully processed row
                else:
                    shape_errors += 1
                    # Optional: st.warning(f"Invalid geometry created from WKT for risk analysis at index {index}")
            except Exception as wkt_error: # Catch errors during WKT loading or validation
                shape_errors += 1 # Increment error count
                # Optional: st.warning(f"WKT processing error for risk analysis at index {index}: {wkt_error}")
                pass # Skip this row

        # Report errors if any occurred
        if shape_errors > 0:
             st.warning(f"[Risk Analysis] Skipped {shape_errors} rows due to invalid/failed WKT geometry processing.")

        # If no valid geometries were created after parsing
        if not valid_indices:
             st.warning("[Risk Analysis] Failed to create any valid geometries from the available polygon data.")
             return bounds

        # Select the original data rows that corresponded to valid geometries
        weather_df_valid = weather_df_potential.loc[valid_indices]

        # Create the GeoDataFrame - lengths should now match
        weather_gdf = gpd.GeoDataFrame(
            weather_df_valid, # Use the filtered DataFrame with valid geometries
            geometry=geometries,
            crs="EPSG:4326"
        )
        
        # 4. Get power lines data
        power_lines_gdf = get_pa_power_lines()
        
        # 5. Analyze wind risk
        st.info(f"Analyzing wind risk ({filter_date_msg}) to power lines (high: {high_threshold} m/s, moderate: {moderate_threshold} m/s)...")
        risk_events, risk_summary = analyze_wind_risk(
            weather_gdf, # Pass the potentially date-filtered GDF
            power_lines_gdf,
            high_threshold,
            moderate_threshold
        )
        
        # 6. Display risk summary
        if risk_summary["risk_found"]:
            # Create a container for the risk assessment
            risk_container = st.container()
            
            with risk_container:
                st.markdown("## Power Line Risk Assessment")
                st.markdown(risk_summary["message"])
                
                # Create metrics row
                metrics_cols = st.columns(3)
                with metrics_cols[0]:
                    st.metric("High Risk Areas", f"{risk_summary['high_risk_areas']}")
                with metrics_cols[1]:
                    st.metric("Moderate Risk Areas", f"{risk_summary['moderate_risk_areas']}")
                with metrics_cols[2]:
                    st.metric("Affected Power Lines", f"{risk_summary['affected_power_lines_km']:.1f} km")
                    
                # Create the event selector
                if "events" in risk_summary and risk_summary["events"]:
                    events = risk_summary["events"]
                    
                    # Format event options for the selector
                    event_options = []
                    for event in events:
                        date = event["date"]
                        risk_level = event["risk_level"]
                        max_wind = event["max_wind_speed"]
                        option_text = f"{date} - {risk_level} Risk (max wind: {max_wind:.1f} m/s)"
                        event_options.append((event["id"], option_text))
                    
                    # Add "All Events" option
                    event_options.insert(0, ("all_events", "Show All Events"))
                    
                    # Create the selector
                    st.markdown("### Select Wind Event to Display:")
                    selected_event = st.selectbox(
                        "Wind Events",
                        options=[id for id, _ in event_options],
                        format_func=lambda x: dict(event_options)[x],
                        key="wind_event_selector"
                    )
                    
                    # 7. Visualize risk areas based on selection
                    # Add power lines layer
                    if power_lines_gdf is not None:
                        folium.GeoJson(
                            json.loads(power_lines_gdf.to_json()),
                            name="Power Lines",
                            style_function=lambda x: {
                                'color': '#0066cc',
                                'weight': 2,
                                'opacity': 0.8
                            }
                        ).add_to(m)
                    
                    # Create color scales for risk visualization
                    risk_colormaps = {
                        'high': LinearColormap(
                            ['#fdbb84', '#e34a33', '#b30000'],
                            vmin=0,
                            vmax=100,
                            caption="High Wind Risk (≥ 16 m/s)"
                        ),
                        'moderate': LinearColormap(
                            ['#fee8c8', '#fdbb84', '#e34a33'],
                            vmin=0,
                            vmax=100,
                            caption="Moderate Wind Risk (13-16 m/s)"
                        )
                    }
                    
                    # Get data for selected event
                    if selected_event == "all_events":
                        # Combine all events into one GeoDataFrame
                        all_risk_areas = pd.concat([df for df in risk_events.values()])
                        
                        # Split by risk level
                        high_risk_df = all_risk_areas[all_risk_areas['risk_level'] == 'high']
                        moderate_risk_df = all_risk_areas[all_risk_areas['risk_level'] == 'moderate']
                    else:
                        # Get single event data
                        all_risk_areas = risk_events.get(selected_event)
                        if all_risk_areas is not None:
                            # Split by risk level
                            high_risk_df = all_risk_areas[all_risk_areas['risk_level'] == 'high']
                            moderate_risk_df = all_risk_areas[all_risk_areas['risk_level'] == 'moderate']
                        else:
                            st.warning(f"No data available for selected event: {selected_event}")
                            return bounds
                    # Add formatted time strings for tooltips BEFORE creating GeoJson
                    if not high_risk_df.empty:
                        try:
                            high_risk_df['forecast_time_str'] = high_risk_df['forecast_time'].dt.strftime('%Y-%m-%d %H:%M')
                        except AttributeError:
                            high_risk_df['forecast_time_str'] = 'Invalid Time'
                    if not moderate_risk_df.empty:
                         try:
                            moderate_risk_df['forecast_time_str'] = moderate_risk_df['forecast_time'].dt.strftime('%Y-%m-%d %H:%M')
                         except AttributeError:
                            moderate_risk_df['forecast_time_str'] = 'Invalid Time'
                    # Add formatted time strings for tooltips BEFORE creating GeoJson
                    if not high_risk_df.empty:
                        try:
                            high_risk_df['forecast_time_str'] = high_risk_df['forecast_time'].dt.strftime('%Y-%m-%d %H:%M')
                        except AttributeError:
                            high_risk_df['forecast_time_str'] = 'Invalid Time'
                    if not moderate_risk_df.empty:
                         try:
                            moderate_risk_df['forecast_time_str'] = moderate_risk_df['forecast_time'].dt.strftime('%Y-%m-%d %H:%M')
                         except AttributeError:
                            moderate_risk_df['forecast_time_str'] = 'Invalid Time'
                    # Add formatted time strings for tooltips BEFORE creating GeoJson
                    if not high_risk_df.empty:
                        try:
                            high_risk_df['forecast_time_str'] = high_risk_df['forecast_time'].dt.strftime('%Y-%m-%d %H:%M')
                        except AttributeError:
                            high_risk_df['forecast_time_str'] = 'Invalid Time'
                    if not moderate_risk_df.empty:
                         try:
                            moderate_risk_df['forecast_time_str'] = moderate_risk_df['forecast_time'].dt.strftime('%Y-%m-%d %H:%M')
                         except AttributeError:
                            moderate_risk_df['forecast_time_str'] = 'Invalid Time'

                    # Add layers to map
                    # Style function for high risk areas
                    def high_risk_style(feature):
                        risk = feature['properties'].get('risk_score', 0)
                        return {
                            'fillColor': risk_colormaps['high'](risk),
                            'color': 'black',
                            'weight': 1,
                            'fillOpacity': 0.7
                        }
                        
                    # Style function for moderate risk areas
                    def moderate_risk_style(feature):
                        risk = feature['properties'].get('risk_score', 0)
                        return {
                            'fillColor': risk_colormaps['moderate'](risk),
                            'color': 'gray',
                            'weight': 1,
                            'fillOpacity': 0.6
                        }
                    
                    # Add high risk areas if exist
                    if not high_risk_df.empty:
                        high_risk_layer = folium.GeoJson(
                            serialize_geojson(high_risk_df),
                            name="High Wind Risk Areas",
                            style_function=high_risk_style,
                            tooltip=folium.GeoJsonTooltip(
                                fields=['forecast_time_str', 'wind_speed', 'risk_score'], # Use pre-formatted string
                                aliases=['Time (UTC)', 'Wind Speed (m/s)', 'Risk Score'],
                                # fmt removed
                                localize=False,
                                sticky=True
                            )
                        ).add_to(m)
                        
                        # Add high risk colormap
                        risk_colormaps['high'].add_to(m)
                        
                        # Track bounds
                        risk_bounds = high_risk_df.total_bounds
                        bounds.append([risk_bounds[1], risk_bounds[0]])  # SW corner
                        bounds.append([risk_bounds[3], risk_bounds[2]])  # NE corner
                    
                    # Add moderate risk areas if exist
                    if not moderate_risk_df.empty:
                        moderate_risk_layer = folium.GeoJson(
                            serialize_geojson(moderate_risk_df),
                            name="Moderate Wind Risk Areas",
                            style_function=moderate_risk_style,
                            tooltip=folium.GeoJsonTooltip(
                                fields=['forecast_time_str', 'wind_speed', 'risk_score'], # Use pre-formatted string
                                aliases=['Time (UTC)', 'Wind Speed (m/s)', 'Risk Score'],
                                # fmt removed
                                localize=False,
                                sticky=True
                            )
                        ).add_to(m)
                        
                        # Add moderate risk colormap
                        risk_colormaps['moderate'].add_to(m)
                        
                        # Track bounds
                        risk_bounds = moderate_risk_df.total_bounds
                        bounds.append([risk_bounds[1], risk_bounds[0]])  # SW corner
                        bounds.append([risk_bounds[3], risk_bounds[2]])  # NE corner
                    
                    # Display event details
                    if selected_event != "all_events":
                        event_data = next((e for e in events if e["id"] == selected_event), None)
                        if event_data:
                            st.markdown(f"""
                            #### Event Details: {event_data['date']}
                            - **Risk Level:** {event_data['risk_level']}
                            - **High Risk Areas:** {event_data['high_risk_count']}
                            - **Moderate Risk Areas:** {event_data['moderate_risk_count']}
                            - **Maximum Wind Speed:** {event_data['max_wind_speed']:.1f} m/s
                            - **Affected Power Lines:** ~{event_data['affected_km']:.1f} km
                            """)
                else:
                    st.warning("No specific wind events were identified in the analysis.")
        else:
            st.info(risk_summary["message"])
        
    except Exception as e:
        st.error(f"Error analyzing wind risk: {str(e)}")
        
    return bounds
