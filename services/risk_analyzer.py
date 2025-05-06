import streamlit as st
import pandas as pd
import json
import traceback # Import traceback
import geopandas as gpd
from shapely.geometry import shape, Point
from shapely import wkt # Ensure wkt is imported
import folium
from branca.colormap import LinearColormap
from data.weather_data import get_weather_forecast_data
from data.geospatial_data import get_pa_power_lines, get_us_states, get_us_counties
from services.map_core import serialize_geojson
from services.weather_service import get_weather_color_scale
from datetime import date, timedelta # Ensure date and timedelta are imported
from utils.geo_utils import find_region_by_name
from utils.streamlit_utils import add_status_message

def analyze_wind_risk(weather_gdf, power_lines_gdf, high_threshold=16.0, moderate_threshold=13.0, analyze_power_line_impact=False):
    """
    Analyze wind risk, optionally intersecting with power line data.

    Args:
        weather_gdf: GeoDataFrame with weather forecast data (already filtered for time period).
        power_lines_gdf: GeoDataFrame with power line geometries (used only if analyze_power_line_impact is True).
        high_threshold: High risk wind speed threshold in m/s (default: 16.0 m/s).
        moderate_threshold: Moderate risk wind speed threshold in m/s (default: 13.0 m/s).
        analyze_power_line_impact (bool): If True, perform intersection with power lines.
                                          If False, analyze general wind risk areas.

    Returns:
        risk_events: Dictionary mapping timestamp-based event IDs (e.g., wind_event_YYYYMMDD_HHMM)
                     to GeoDataFrames of risk areas (either general or intersecting power lines).
        summary: Dictionary with overall risk summary information across all timestamps, including analysis_type.
    """
    try:
        # Ensure forecast_time is datetime (should be done by handler, but double-check)
        if 'forecast_time' not in weather_gdf.columns:
             st.error("Weather data for risk analysis missing 'forecast_time'.")
             return {}, {"risk_found": False, "message": "Missing 'forecast_time'."}

        # Check if empty before starting
        if weather_gdf.empty:
            add_status_message("[Risk Analysis] Input weather data is empty.", "warning")
            return {}, {"risk_found": False, "message": "Input weather data is empty."}

        # Ensure required columns exist
        required_cols = ['wind_speed', 'forecast_time', 'geography_polygon', 'geometry']
        if not all(col in weather_gdf.columns for col in required_cols):
             missing = [col for col in required_cols if col not in weather_gdf.columns]
             st.error(f"Weather data for risk analysis missing required columns: {missing}")
             return {}, {"risk_found": False, "message": f"Missing required columns: {missing}"}

        # 1. Filter weather data for winds above moderate threshold
        wind_risk_areas_initial = weather_gdf[weather_gdf['wind_speed'] >= moderate_threshold].copy()

        if wind_risk_areas_initial.empty:
            return {}, {
                "risk_found": False,
                "message": f"No areas with wind speeds over {moderate_threshold} m/s found in the analyzed forecast period."
            }

        # Classify risk levels using .loc on the initial areas
        wind_risk_areas_initial.loc[:, 'risk_level'] = 'moderate'
        wind_risk_areas_initial.loc[wind_risk_areas_initial['wind_speed'] >= high_threshold, 'risk_level'] = 'high'
        
        # Verify risk level column was added
        if 'risk_level' not in wind_risk_areas_initial.columns:
            add_status_message("WARNING: Failed to add risk_level column to weather data", "warning")
            # Add it again to be sure
            wind_risk_areas_initial['risk_level'] = 'moderate'
            wind_risk_areas_initial.loc[wind_risk_areas_initial['wind_speed'] >= high_threshold, 'risk_level'] = 'high'

        # Initialize risk_areas with the initial filtered set
        risk_areas = wind_risk_areas_initial.copy()
        power_lines_loaded = power_lines_gdf is not None and not power_lines_gdf.empty  # Check if pre-loaded power lines exist
        intersection_performed = False
        no_intersection_found = False # Flag for case where join runs but finds no overlap

        # 2. Conditional Power Line Intersection Logic
        if analyze_power_line_impact:
            # SIMPLIFIED: Power line analysis requires the pre-filtered power_lines_gdf
            # from the handler function to already be passed in
            
            if power_lines_gdf is None or power_lines_gdf.empty:
                # Power line analysis requested, but no filtered data available
                add_status_message("Power line impact analysis requested, but no filtered power line data is available. Proceeding with general wind risk analysis.", "warning")
                # Proceed with general wind risk analysis (risk_areas remains wind_risk_areas_initial)
                power_lines_loaded = False
            else:
                # Already filtered power lines available, proceed with buffering and intersection
                try:
                    add_status_message(f"Creating buffer around power points for risk analysis", "info")
                    power_lines_loaded = True
                    
                    # Convert to appropriate projection for buffering
                    power_lines_proj = power_lines_gdf.to_crs("EPSG:3857")  # Web Mercator
                    
                    # Use 500m buffer for points
                    buffer_distance = 500
                    
                    # Create buffer and prepare for intersection
                    buffered_lines = power_lines_proj.buffer(buffer_distance)
                    buffered_lines_gdf = gpd.GeoDataFrame(geometry=buffered_lines, crs="EPSG:3857")
                    buffered_lines_gdf = buffered_lines_gdf.to_crs("EPSG:4326")  # Back to WGS84
                except Exception as buffer_err:
                     add_status_message(f"Error buffering power lines: {buffer_err}", "error")
                     # Revert to general analysis if buffering fails
                     risk_areas = wind_risk_areas_initial # Keep initial areas
                     add_status_message("Proceeding with general wind risk analysis due to power line buffering error.", "warning")
                     # Skip intersection step by ensuring intersection_performed is False
                     intersection_performed = False # Explicitly set just in case
                     # We don't set power_lines_loaded to False, as they were loaded but couldn't be processed

                # Only attempt join if buffer succeeded and power lines were loaded
                if power_lines_loaded and 'buffered_lines_gdf' in locals():
                    try:
                        # 4. Perform spatial join to find intersections
                        wind_risk_areas_proj = wind_risk_areas_initial.to_crs(buffered_lines_gdf.crs)
                        joined_areas = gpd.sjoin(wind_risk_areas_proj, buffered_lines_gdf, how="inner", predicate="intersects")

                        if joined_areas.empty:
                             add_status_message("Found areas with high/moderate wind risk, but none intersected buffered power lines.", "info")
                             # Keep risk_areas as wind_risk_areas_initial, but set flag for summary
                             no_intersection_found = True
                             risk_areas = wind_risk_areas_initial # Ensure we use initial areas
                             intersection_performed = False # No successful intersection
                        else:
                            # Intersection successful, update risk_areas
                             risk_areas = joined_areas.drop_duplicates(subset=['geography_polygon', 'forecast_time']).copy()
                             intersection_performed = True # Mark intersection as successful
                             
                             # Check if risk_level column survived the join
                             if 'risk_level' not in risk_areas.columns:
                                 add_status_message("WARNING: risk_level column lost during spatial join. Re-adding it.", "warning")
                                 # Add it again based on thresholds
                                 risk_areas['risk_level'] = 'moderate'
                                 risk_areas.loc[risk_areas['wind_speed'] >= high_threshold, 'risk_level'] = 'high'

                    except Exception as join_err:
                         add_status_message(f"Error during spatial join: {join_err}", "error")
                         # Revert to general analysis if join fails
                         risk_areas = wind_risk_areas_initial
                         add_status_message("Proceeding with general wind risk analysis due to spatial join error.", "warning")
                         intersection_performed = False

        # --- Risk Calculation and Event Grouping (applied to 'risk_areas' regardless of source) ---

        # 5. Calculate risk metrics (on the final risk_areas DataFrame)
        if risk_areas.empty:
             # This case means either wind_risk_areas_initial was empty, or joined_areas became empty (though handled above)
             summary_msg = f"No areas with wind speeds over {moderate_threshold} m/s found."
             # Refine message based on why it might be empty
             if analyze_power_line_impact and power_lines_loaded and no_intersection_found:
                  summary_msg = "Found wind risk areas, but none intersected buffered power lines."
             elif analyze_power_line_impact and not power_lines_loaded:
                  summary_msg += " (Power line data unavailable for intersection)."

             return {}, { "risk_found": False, "message": summary_msg }


        # Add a risk score - percentage scale using .loc
        # This applies to risk_areas, whether it contains initial areas or intersected areas
        max_possible_wind = risk_areas['wind_speed'].max()
        # Ensure denominator is not zero if all winds are at the threshold
        if (max_possible_wind - moderate_threshold) > 0:
            score_series = ((risk_areas['wind_speed'] - moderate_threshold) /
                            (max_possible_wind - moderate_threshold) * 100)
        else:
            score_series = 0 # Assign 0 if max wind is equal to the threshold
        risk_areas.loc[:, 'risk_score'] = score_series
        risk_areas.loc[:, 'risk_score'] = risk_areas['risk_score'].clip(0, 100)


        # 6. Group data into events by forecast timestamp (Corrected)
        events = [] # List to hold summary dictionaries for each event timestamp
        risk_events = {} # Dict to hold GeoDataFrames for each event timestamp

        unique_timestamps = sorted(risk_areas['forecast_time'].unique())

        for timestamp in unique_timestamps:
            timestamp_areas = risk_areas[risk_areas['forecast_time'] == timestamp].copy()
            if timestamp_areas.empty: continue

            # Check if risk_level exists in the dataset
            if 'risk_level' not in timestamp_areas.columns:
                add_status_message(f"WARNING: risk_level column missing from timestamp areas for {timestamp}", "warning")
                # Add it once more based on thresholds
                timestamp_areas['risk_level'] = 'moderate'
                timestamp_areas.loc[timestamp_areas['wind_speed'] >= high_threshold, 'risk_level'] = 'high'
            
            high_count = len(timestamp_areas[timestamp_areas['risk_level'] == 'high'])
            moderate_count = len(timestamp_areas[timestamp_areas['risk_level'] == 'moderate'])
            
            add_status_message(f"For timestamp {timestamp}: {high_count} high risk, {moderate_count} moderate risk areas", "info")
            
            if high_count + moderate_count == 0: continue

            timestamp_str_id = timestamp.strftime('%Y%m%d_%H%M')
            timestamp_str_display = timestamp.strftime('%Y-%m-%d %H:%M UTC')
            event_id = f"wind_event_{timestamp_str_id}"

            # Calculate affected_km ONLY if power line analysis was successfully performed
            affected_km_val = 0
            # Use the 'intersection_performed' flag which is True only if join succeeded and was not empty
            if analyze_power_line_impact and intersection_performed:
                # Placeholder logic - needs refinement for accurate km calculation based on intersected lines
                affected_km_val = len(timestamp_areas) * 0.25 # Still a placeholder

            event_summary = {
                "id": event_id,
                "timestamp": timestamp_str_display,
                "high_risk_count": high_count,
                "moderate_risk_count": moderate_count,
                "max_wind_speed": timestamp_areas['wind_speed'].max(),
                "affected_km": affected_km_val, # Use calculated or 0
                "risk_level": "High" if high_count > 0 else "Moderate"
            }
            events.append(event_summary)
            # Ensure timestamp_areas has geometry and risk_level column before storing
            if 'geometry' in timestamp_areas.columns and 'risk_level' in timestamp_areas.columns:
                risk_events[event_id] = timestamp_areas # Store GDF for this specific timestamp
                add_status_message(f"Added event {event_id} with {len(timestamp_areas)} areas ({high_count} high, {moderate_count} moderate)", "info")
            else:
                add_status_message(f"WARNING: Event {event_id} missing required columns. Not adding to risk_events.", "warning")
                add_status_message(f"Columns: {', '.join(timestamp_areas.columns)}", "info")


        # 7. Prepare overall summary (Corrected)
        if not events:
             # This case should ideally be caught by the risk_areas.empty check earlier
             summary_msg = "No significant wind risk events found after processing."
             # Consider specific messages based on flags if needed, but main check is risk_areas.empty
             return {}, {"risk_found": False, "message": summary_msg}


        total_high_risk = sum(event['high_risk_count'] for event in events)
        total_moderate_risk = sum(event['moderate_risk_count'] for event in events)
        total_affected_km = sum(event['affected_km'] for event in events) # Sums placeholders or 0s
        max_wind_overall = max(event['max_wind_speed'] for event in events) if events else 0

        highest_risk_event = max(events, key=lambda x: (x['high_risk_count'], x['max_wind_speed']))
        highest_risk_timestamp_str = highest_risk_event['timestamp']

        # Dynamic summary message generation based on analysis flags
        summary_analysis_desc = "general wind risk areas" # Default
        analysis_type_flag = "general_wind"
        if analyze_power_line_impact:
            if intersection_performed:
                summary_analysis_desc = "potential power line impacts"
                analysis_type_flag = "power_line_impact"
            elif power_lines_loaded and no_intersection_found: # Tried intersection but no overlap
                summary_analysis_desc = "general wind risk areas (none intersected power lines)"
                # analysis_type_flag remains general_wind
            elif not power_lines_loaded: # Tried power line analysis but data was missing/error
                summary_analysis_desc = "general wind risk areas (power line data unavailable/error)"
                # analysis_type_flag remains general_wind
            # Add case for buffer/join error? Message already handled by st.warning/st.error

        summary_message = f"Found {len(events)} timestamps with {summary_analysis_desc}."

        summary = {
            "risk_found": True,
            "message": summary_message,
            "event_count": len(events),
            "events": events,
            "high_risk_areas": total_high_risk,
            "moderate_risk_areas": total_moderate_risk,
            # Report affected_km only if power line analysis was done and successful
            "affected_power_lines_km": total_affected_km if intersection_performed else 0,
            "highest_risk_timestamp": highest_risk_timestamp_str,
            "max_wind_speed": max_wind_overall,
            # Add a clear flag indicating the type of analysis performed in the result
            "analysis_type": analysis_type_flag
        }

        return risk_events, summary

    except Exception as e:
        st.error(f"Error analyzing wind risk: {str(e)}")
        # Use traceback for more detail
        traceback.print_exc()
        return {}, {
            "risk_found": False,
            "message": f"Error analyzing wind risk: {str(e)}"
        }


def handle_analyze_wind_risk(action, m):
    """
    Handle the analyze_wind_risk action by analyzing specific timestamps.

    Args:
        action: The action dictionary with parameters ('region', 'forecast_days', 'high_threshold',
                                                      'moderate_threshold', 'analyze_power_lines').
        m: The folium map object.

    Returns:
        List of bounds to include in the overall map fitting.
    """
    bounds = []

    # Parameters for risk analysis
    high_threshold = action.get("high_threshold", 16.0)
    moderate_threshold = action.get("moderate_threshold", 13.0)
    forecast_days = action.get("forecast_days", 3) # Default to 3 days
    analyze_power_lines = action.get("analyze_power_lines", False) # Default to False
    
    # Only use power line analysis if explicitly requested with analyze_power_lines=true
    # Remove automatic detection to prevent loading PA power lines data for non-PA regions
    if analyze_power_lines:
        add_status_message("Power line risk analysis explicitly requested.", "info")
    
    # Get the region parameter (REQUIRED)
    region_name = action.get("region")
    if not region_name:
        add_status_message("Region parameter is required for wind risk analysis. Please specify a region (state or county).", "error")
        return bounds
    
    # For UI feedback
    if analyze_power_lines:
        add_status_message(f"Analyzing wind risk to power infrastructure in {region_name}", "info")
    else:
        add_status_message(f"Analyzing general wind risk for region: {region_name}", "info")

    try:
        # 1. Get all weather forecast data for the selected init_date
        selected_init_date = st.session_state.get("selected_init_date", date.today())
        # Generate the simplified query for display in the spinner
        from data.weather_data import get_weather_query
        _, init_date_str = get_weather_query(selected_init_date)
        simplified_query = f"SELECT weather.init_time, geography, forecast_time, temperature, precipitation, wind_speed FROM weathernext_graph_forecasts WHERE init_time = '{init_date_str}'"
        
        # Fetch the data with a spinner showing the query
        with st.spinner(f"Executing: {simplified_query}"):
            weather_df_all = get_weather_forecast_data(selected_init_date)

        if weather_df_all is None or weather_df_all.empty:
            add_status_message("No weather data available for risk analysis.", "warning")
            return bounds

        # Ensure forecast_time is datetime and UTC
        if 'forecast_time' not in weather_df_all.columns:
             add_status_message("Weather data missing 'forecast_time' column.", "error")
             return bounds
        try:
            # Make a copy before modification
            weather_df_all = weather_df_all.copy()
            weather_df_all['forecast_time'] = pd.to_datetime(weather_df_all['forecast_time'], errors='coerce')
            if weather_df_all['forecast_time'].dt.tz is None:
                 weather_df_all['forecast_time'] = weather_df_all['forecast_time'].dt.tz_localize('UTC')
            else:
                 weather_df_all['forecast_time'] = weather_df_all['forecast_time'].dt.tz_convert('UTC')
            weather_df_all.dropna(subset=['forecast_time'], inplace=True) # drop rows where conversion failed
        except Exception as e:
            add_status_message(f"Error processing forecast timestamps: {e}", "error")
            return bounds

        if weather_df_all.empty:
            add_status_message("No valid weather timestamps found after processing.", "warning")
            return bounds
            
        # 2. Find the region boundary to use as a filter
        region_polygon = None
        # First try states dataset
        states_gdf = get_us_states()
        region_match = find_region_by_name(states_gdf, region_name)
        
        if region_match is not None and not region_match.empty:
            region_polygon = region_match.geometry.iloc[0]
            add_status_message(f"Found matching state: {region_match['state_name'].iloc[0]}", "info")
        else:
            # Try counties dataset
            counties_gdf = get_us_counties()
            region_match = find_region_by_name(counties_gdf, region_name)
            
            if region_match is not None and not region_match.empty:
                region_polygon = region_match.geometry.iloc[0]
                # Include state information if available
                if 'state_name' in region_match.columns:
                    add_status_message(f"Found matching county: {region_match['county_name'].iloc[0]}, {region_match['state_name'].iloc[0]}", "info")
                elif 'state' in region_match.columns:
                    add_status_message(f"Found matching county: {region_match['county_name'].iloc[0]}, {region_match['state'].iloc[0]}", "info")
                else:
                    add_status_message(f"Found matching county: {region_match['county_name'].iloc[0]}", "info")
        
        if region_polygon is None:
            add_status_message(f"Could not find region: {region_name}. Please specify a valid state or county name.", "error")
            return bounds
            
        # Add the region to the map for reference
        folium.GeoJson(
            region_match.__geo_interface__,
            name=f"Analysis Region: {region_name}",
            style_function=lambda x: {
                'fillColor': "#8080FF",
                'color': "blue",
                'weight': 2,
                'fillOpacity': 0.1
            }
        ).add_to(m)
        
        # Add region to bounds
        region_bounds = region_match.total_bounds
        bounds.append([[region_bounds[1], region_bounds[0]], [region_bounds[3], region_bounds[2]]])

        # 3. Filter weather data for the specified number of forecast days
        filter_msg = ""
        try:
            forecast_days = int(forecast_days)
            if forecast_days < 1: forecast_days = 1; st.warning("Forecast days minimum is 1.")
            if forecast_days > 10: forecast_days = 10; st.warning("Limiting forecast analysis to 10 days.")

            # Ensure init_date is a timezone-aware Timestamp
            if isinstance(selected_init_date, date) and not isinstance(selected_init_date, pd.Timestamp):
                 init_dt = pd.Timestamp(selected_init_date, tz='UTC')
            else: # Convert if needed and ensure timezone
                 init_dt = pd.Timestamp(selected_init_date).tz_convert('UTC') if pd.Timestamp(selected_init_date).tzinfo else pd.Timestamp(selected_init_date).tz_localize('UTC')

            end_dt = init_dt + timedelta(days=forecast_days)

            # Perform the time filtering
            weather_df_filtered = weather_df_all[
                (weather_df_all['forecast_time'] >= init_dt) &
                (weather_df_all['forecast_time'] < end_dt) # Exclusive of the end day's 00:00
            ].copy()
            filter_msg = f"next {forecast_days} day(s)"

        except (ValueError, TypeError) as e:
            st.error(f"Invalid 'forecast_days' parameter: {forecast_days}. Defaulting to 3 days. Error: {e}")
            forecast_days = 3
            # Recalculate dates with default
            if isinstance(selected_init_date, date) and not isinstance(selected_init_date, pd.Timestamp):
                 init_dt = pd.Timestamp(selected_init_date, tz='UTC')
            else:
                 init_dt = pd.Timestamp(selected_init_date).tz_convert('UTC') if pd.Timestamp(selected_init_date).tzinfo else pd.Timestamp(selected_init_date).tz_localize('UTC')
            end_dt = init_dt + timedelta(days=forecast_days)
            weather_df_filtered = weather_df_all[
                (weather_df_all['forecast_time'] >= init_dt) &
                (weather_df_all['forecast_time'] < end_dt)
            ].copy()
            filter_msg = f"next {forecast_days} day(s)"

        if weather_df_filtered.empty:
            st.warning(f"No weather data available for the {filter_msg}.")
            return bounds

        # 4. Convert filtered data to GeoDataFrame
        # (Assuming 'geography_polygon' is WKT)
        geometries = []
        valid_indices = []
        parse_errors = 0
        for index, row in weather_df_filtered.iterrows():
             try:
                 poly = wkt.loads(row['geography_polygon'])
                 if poly.is_valid:
                     geometries.append(poly)
                     valid_indices.append(index)
                 else: parse_errors += 1
             except Exception: parse_errors += 1
        if parse_errors > 0: st.warning(f"Skipped {parse_errors} rows due to invalid geometry during risk analysis.")
        if not valid_indices: st.error("No valid geometries found in filtered weather data."); return bounds

        weather_gdf = gpd.GeoDataFrame(weather_df_filtered.loc[valid_indices], geometry=geometries, crs="EPSG:4326")
        
        # 5. Apply geographic filtering - only keep weather points that intersect with the region
        with st.spinner("Filtering weather data by region..."):
            original_count = len(weather_gdf)
            weather_gdf = weather_gdf[weather_gdf.intersects(region_polygon)].copy()
            add_status_message(f"Filtered weather data from {original_count} points to {len(weather_gdf)} points within {region_name}", "info")
            
            if weather_gdf.empty:
                add_status_message(f"No weather data points found within {region_name}.", "warning")
                return bounds

        # 6. Get power lines data only if needed (analyze_wind_risk handles internal loading if None)
        power_lines_gdf = None # Initialize as None
        if analyze_power_lines:
            # SIMPLIFIED APPROACH: Only show power lines if we have a valid region,
            # and only show the ones that actually intersect with the region
            
            if region_polygon is None:
                add_status_message("No valid region polygon for power line analysis", "warning")
            else:
                # Load power line data
                add_status_message(f"Loading power line data for {region_name}...", "info")
                power_lines_gdf = get_pa_power_lines(use_geojson=True)
                
                if power_lines_gdf is None or power_lines_gdf.empty:
                    add_status_message("Failed to load power line data.", "error")
                else:
                    # Apply strict filtering by region
                    # Display min/max coordinates of power line data as debugging info
                    pl_bounds = power_lines_gdf.total_bounds
                    add_status_message(f"Power line data bounds: {pl_bounds}", "info")
                    
                    # Get the bounds of the region
                    minx, miny, maxx, maxy = region_polygon.bounds
                    
                    # Add a simple buffer to the bounds (0.1 degrees ~ 10km)
                    buffered_bounds = (minx - 0.1, miny - 0.1, maxx + 0.1, maxy + 0.1)
                    add_status_message(f"Using buffered bounds for risk analysis: {buffered_bounds}", "info")
                    
                    # Simple filtering by checking if points fall within bounds
                    # This is a simpler approach that will work with any polygon bounds
                    filtered_gdf = power_lines_gdf[(power_lines_gdf.geometry.x >= buffered_bounds[0]) & 
                                                   (power_lines_gdf.geometry.y >= buffered_bounds[1]) & 
                                                   (power_lines_gdf.geometry.x <= buffered_bounds[2]) & 
                                                   (power_lines_gdf.geometry.y <= buffered_bounds[3])].copy()
                    
                    add_status_message(f"Power lines in buffered bounds: {len(filtered_gdf)}", "info")
                    
                    # Use the filtered data
                    power_lines_gdf = filtered_gdf
                    add_status_message(f"Final power line count for risk analysis in {region_name}: {len(power_lines_gdf)}", "info")
                    
                    if power_lines_gdf.empty:
                        add_status_message(f"No power lines found within {region_name}.", "warning")
                        power_lines_gdf = None  # Clear it so we don't use it for analysis
                    else:
                        # We'll add the power lines after analyzing risk, so save this for later
                        # This ensures we can filter to only impacted areas and draw them on top
                        saved_power_lines_gdf = power_lines_gdf.copy()
                        add_status_message(f"Will render power line points after analyzing risk", "info")

        # 7. Analyze wind risk
        analysis_desc = "power line impact" if analyze_power_lines else "general wind risk"
        # Check if region is in Pennsylvania by name or abbreviation
        is_pa_region = (region_name.lower() == "pennsylvania" or 
                        region_name.lower() == "pa" or
                        any(pa_term in region_name.lower() for pa_term in ["crawford", "fulton", "allegheny", "chester"]))
        
        # Only show PA-specific warning if NOT in Pennsylvania and power lines were requested
        if analyze_power_lines and not is_pa_region:
            add_status_message(f"NOTE: Power line data is only available for Pennsylvania regions. Results for {region_name} may be limited.", "warning")
        add_status_message(f"Analyzing {analysis_desc} for {region_name} over the {filter_msg} (high >= {high_threshold} m/s, moderate >= {moderate_threshold} m/s)...", "info")

        risk_events, risk_summary = analyze_wind_risk(
            weather_gdf,
            power_lines_gdf, # Pass potentially pre-loaded gdf or None
            high_threshold,
            moderate_threshold,
            analyze_power_line_impact=analyze_power_lines # Pass the flag
        )

        # 6. Display risk summary in Streamlit UI
        if risk_summary.get("risk_found"): # Use .get for safety
            risk_container = st.container(border=True)
            with risk_container:
                # Dynamic title based on analysis type reported by analyze_wind_risk
                analysis_type_title = "General Wind Risk Assessment"
                analysis_details_suffix = ""
                if risk_summary.get("analysis_type") == "power_line_impact":
                     analysis_type_title = "Power Line Wind Risk Assessment"
                elif analyze_power_lines: # Requested PL but didn't get PL impact result
                     analysis_details_suffix = " (Power Line Data Issues)" # Append info

                st.markdown(f"#### {analysis_type_title}{analysis_details_suffix}")
                st.markdown(f"_{risk_summary.get('message', 'Analysis complete.')}_") # Use .get

                # Adjust metrics display based on analysis type
                metrics_cols = st.columns(3)
                metrics_cols[0].metric("High Risk Areas", f"{risk_summary.get('high_risk_areas', 0)}")
                metrics_cols[1].metric("Moderate Risk Areas", f"{risk_summary.get('moderate_risk_areas', 0)}")
                # Only show 'Affected Lines' if power line analysis was successful
                if risk_summary.get("analysis_type") == "power_line_impact":
                    metrics_cols[2].metric("Affected Lines (Est.)", f"{risk_summary.get('affected_power_lines_km', 0):.1f} km")
                else:
                    metrics_cols[2].empty() # Leave the column blank if not applicable

                # Create the timestamp selector (remains largely the same)
                if "events" in risk_summary and risk_summary.get("events"):
                    events = risk_summary["events"]
                    event_options = [(event["id"], f"{event['timestamp']} - {event['risk_level']} Risk (Max: {event['max_wind_speed']:.1f} m/s)") for event in events]
                    # Sort events chronologically for the dropdown
                    event_options.sort(key=lambda x: x[1])
                    event_options.insert(0, ("all_timestamps", "Show All Risk Timestamps"))

                    selected_event_id = st.selectbox(
                        "Select Risk Timestamp to Display:",
                        options=[id for id, _ in event_options],
                        format_func=lambda x: dict(event_options).get(x, "Select..."),
                        key="wind_event_selector"
                    )

                    # The power line points are already on the map from earlier,
                    # so we don't need to add them again

                    # Dynamically adjust color scale captions and map layer names
                    is_pl_impact = risk_summary.get("analysis_type") == "power_line_impact"
                    caption_suffix = " (Power Lines)" if is_pl_impact else ""
                    layer_name_suffix = " (Power Lines)" if is_pl_impact else ""

                    risk_colormaps = {
                        'high': get_weather_color_scale('wind_risk', 0, 100),
                        'moderate': get_weather_color_scale('wind_risk', 0, 100)
                    }
                    risk_colormaps['high'].caption = f"High Wind Risk Score{caption_suffix}"
                    risk_colormaps['moderate'].caption = f"Moderate Wind Risk Score{caption_suffix}"

                    # Prepare DataFrames for display (remains the same)
                    high_risk_df_display = pd.DataFrame()
                    moderate_risk_df_display = pd.DataFrame()


                    if selected_event_id == "all_timestamps":
                        add_status_message(f"Showing all risk events ({len(risk_events.keys()) if risk_events else 0} timestamps)", "info")
                        if risk_events:
                             # Ensure all GDFs have the same CRS before concat
                             all_areas_list = []
                             target_crs = None
                             for event_id, gdf in risk_events.items():
                                 add_status_message(f"Processing event {event_id}: {len(gdf) if gdf is not None else 0} areas", "info")
                                 if gdf is not None and not gdf.empty:
                                     # Check if risk_level exists
                                     if 'risk_level' not in gdf.columns:
                                         add_status_message(f"WARNING: Event {event_id} missing risk_level column", "warning")
                                         continue
                                         
                                     if target_crs is None: target_crs = gdf.crs
                                     if gdf.crs != target_crs:
                                         gdf = gdf.to_crs(target_crs)
                                     all_areas_list.append(gdf)

                             if all_areas_list:
                                 # Use pd.concat, it should handle GeoDataFrames correctly
                                 all_risk_gdf = pd.concat(all_areas_list, ignore_index=True)
                                 # Ensure it's still a GeoDataFrame with geometry
                                 if not isinstance(all_risk_gdf, gpd.GeoDataFrame):
                                      # Ensure it's still a GeoDataFrame with geometry after concat
                                      # This might be redundant if concat works correctly, but safe check
                                      if 'geometry' not in all_risk_gdf.columns and hasattr(all_risk_gdf, 'geometry'):
                                           all_risk_gdf = gpd.GeoDataFrame(all_risk_gdf, geometry=all_risk_gdf.geometry.name, crs=target_crs)
                                      elif 'geometry' in all_risk_gdf.columns and not isinstance(all_risk_gdf, gpd.GeoDataFrame):
                                           all_risk_gdf = gpd.GeoDataFrame(all_risk_gdf, geometry='geometry', crs=target_crs)


                                 if not all_risk_gdf.empty:
                                     # Filtering a GeoDataFrame results in a GeoDataFrame
                                     high_risk_df_display = all_risk_gdf[all_risk_gdf['risk_level'] == 'high'].copy()
                                     moderate_risk_df_display = all_risk_gdf[all_risk_gdf['risk_level'] == 'moderate'].copy()
                    else:
                        selected_gdf = risk_events.get(selected_event_id) # This is already a GeoDataFrame
                        add_status_message(f"Showing risk event: {selected_event_id}", "info")
                        
                        if selected_gdf is not None and not selected_gdf.empty:
                             # Debug output
                             add_status_message(f"Event has {len(selected_gdf)} total areas", "info")
                             
                             # Check if the risk_level column exists (it should)
                             if 'risk_level' not in selected_gdf.columns:
                                 add_status_message("WARNING: risk_level column missing from event data", "warning")
                                 add_status_message(f"Available columns: {', '.join(selected_gdf.columns)}", "info")
                                 high_risk_df_display = pd.DataFrame()
                                 moderate_risk_df_display = pd.DataFrame()
                             else:
                                 # Filtering a GeoDataFrame results in a GeoDataFrame
                                 high_risk_df_display = selected_gdf[selected_gdf['risk_level'] == 'high'].copy()
                                 moderate_risk_df_display = selected_gdf[selected_gdf['risk_level'] == 'moderate'].copy()
                                 
                                 # Log counts
                                 add_status_message(f"Found {len(high_risk_df_display)} high risk and {len(moderate_risk_df_display)} moderate risk areas", "info")
                        else:
                             add_status_message(f"No data found for event: {selected_event_id}", "warning")
                             high_risk_df_display = pd.DataFrame()
                             moderate_risk_df_display = pd.DataFrame()

                    # CRS is inherited from the source GDFs (all_risk_gdf or selected_gdf)


                    # Add formatted time strings safely using .loc and checking type
                    for df in [high_risk_df_display, moderate_risk_df_display]:
                         if not df.empty:
                            try:
                                if pd.api.types.is_datetime64_any_dtype(df['forecast_time']):
                                     df.loc[:, 'forecast_time_str'] = df['forecast_time'].dt.strftime('%Y-%m-%d %H:%M')
                                else: # Attempt conversion if not already datetime
                                     df.loc[:, 'forecast_time'] = pd.to_datetime(df['forecast_time'], errors='coerce')
                                     df.loc[:, 'forecast_time_str'] = df['forecast_time'].dt.strftime('%Y-%m-%d %H:%M').fillna('Invalid Time')
                            except Exception:
                                df.loc[:, 'forecast_time_str'] = 'Error Formatting Time'

                    # Drop the original timestamp column before serialization as it's not JSON serializable
                    if 'forecast_time' in high_risk_df_display.columns:
                         high_risk_df_display = high_risk_df_display.drop(columns=['forecast_time'], errors='ignore')
                    if 'forecast_time' in moderate_risk_df_display.columns:
                         moderate_risk_df_display = moderate_risk_df_display.drop(columns=['forecast_time'], errors='ignore')
                    # Also drop init_time
                    if 'init_time' in high_risk_df_display.columns:
                         high_risk_df_display = high_risk_df_display.drop(columns=['init_time'], errors='ignore')
                    if 'init_time' in moderate_risk_df_display.columns:
                         moderate_risk_df_display = moderate_risk_df_display.drop(columns=['init_time'], errors='ignore')

                    # Add layers to map
                    def risk_style_func(feature, level):
                         score = feature['properties'].get('risk_score', 0)
                         color_map_key = 'high' if level == 'high' else 'moderate'
                         color = 'black' if level == 'high' else 'grey'
                         return {'fillColor': risk_colormaps[color_map_key](score), 'color': color, 'weight': 0.5, 'fillOpacity': 0.6}

                    if not high_risk_df_display.empty:
                        add_status_message(f"Drawing {len(high_risk_df_display)} high risk areas on map", "info")
                        try:
                            # Calculate bounds BEFORE converting to JSON, ensuring standard floats
                            b = high_risk_df_display.total_bounds # [minx, miny, maxx, maxy]
                            bounds.append([[float(b[1]), float(b[0])], [float(b[3]), float(b[2])]]) # [[miny, minx], [maxy, maxx]]
                            
                            # Check for required columns
                            if 'geometry' not in high_risk_df_display:
                                add_status_message("High risk dataframe missing geometry column!", "error")
                            
                            # Convert to GeoJSON dictionary
                            high_risk_geojson = json.loads(high_risk_df_display.to_json())
                            
                            # Check for features in GeoJSON
                            if not high_risk_geojson.get('features', []):
                                add_status_message("No features in high risk GeoJSON!", "warning")
                                
                            # First method: Try simple GeoJSON
                            folium.GeoJson(
                                high_risk_geojson, # Use GeoJSON dictionary
                                name=f"High Wind Risk Areas{layer_name_suffix}", # Dynamic name
                                style_function=lambda feature: {
                                    'fillColor': '#ff0000', 
                                    'color': '#800000',
                                    'weight': 2,
                                    'opacity': 1,
                                    'fillOpacity': 0.7
                                },
                                tooltip=folium.GeoJsonTooltip(
                                    fields=['forecast_time_str', 'wind_speed', 'risk_score'],
                                    aliases=['Time (UTC)', 'Wind Speed (m/s)', 'Risk Score (%)'],
                                    localize=False, sticky=True
                                )
                            ).add_to(m)
                            
                            # Add marker at centroid as backup visualization
                            for idx, row in high_risk_df_display.iterrows():
                                try:
                                    # Get centroid of polygon
                                    centroid = row.geometry.centroid
                                    folium.CircleMarker(
                                        location=[centroid.y, centroid.x],
                                        radius=8,
                                        color='red',
                                        fill=True,
                                        fill_color='red',
                                        fill_opacity=0.6,
                                        popup=f"High Risk: {row.get('wind_speed', 'N/A')} m/s"
                                    ).add_to(m)
                                except Exception as e:
                                    add_status_message(f"Error adding centroid marker: {e}", "error")
                            
                            risk_colormaps['high'].add_to(m) # Add legend
                            
                        except Exception as e:
                            add_status_message(f"Error displaying high risk areas: {str(e)}", "error")

                    if not moderate_risk_df_display.empty:
                        add_status_message(f"Drawing {len(moderate_risk_df_display)} moderate risk areas on map", "info")
                        try:
                            # Calculate bounds BEFORE converting to JSON, ensuring standard floats
                            b = moderate_risk_df_display.total_bounds # [minx, miny, maxx, maxy]
                            bounds.append([[float(b[1]), float(b[0])], [float(b[3]), float(b[2])]]) # [[miny, minx], [maxy, maxx]]
                            
                            # Check for required columns
                            if 'geometry' not in moderate_risk_df_display:
                                add_status_message("Moderate risk dataframe missing geometry column!", "error")
                            
                            # Convert to GeoJSON dictionary
                            moderate_risk_geojson = json.loads(moderate_risk_df_display.to_json())
                            
                            # Check for features in GeoJSON
                            if not moderate_risk_geojson.get('features', []):
                                add_status_message("No features in moderate risk GeoJSON!", "warning")
                                
                            # First method: Try simple GeoJSON
                            folium.GeoJson(
                                moderate_risk_geojson, # Use GeoJSON dictionary
                                name=f"Moderate Wind Risk Areas{layer_name_suffix}", # Dynamic name
                                style_function=lambda feature: {
                                    'fillColor': '#ffaa00', 
                                    'color': '#996600',
                                    'weight': 2,
                                    'opacity': 1,
                                    'fillOpacity': 0.6
                                },
                                tooltip=folium.GeoJsonTooltip(
                                    fields=['forecast_time_str', 'wind_speed', 'risk_score'],
                                    aliases=['Time (UTC)', 'Wind Speed (m/s)', 'Risk Score (%)'],
                                    localize=False, sticky=True
                                )
                            ).add_to(m)
                            
                            # Add marker at centroid as backup visualization
                            for idx, row in moderate_risk_df_display.iterrows():
                                try:
                                    # Get centroid of polygon
                                    centroid = row.geometry.centroid
                                    folium.CircleMarker(
                                        location=[centroid.y, centroid.x],
                                        radius=8,
                                        color='orange',
                                        fill=True,
                                        fill_color='orange',
                                        fill_opacity=0.6,
                                        popup=f"Moderate Risk: {row.get('wind_speed', 'N/A')} m/s"
                                    ).add_to(m)
                                except Exception as e:
                                    add_status_message(f"Error adding centroid marker: {e}", "error")
                            
                            risk_colormaps['moderate'].add_to(m) # Add legend
                            
                        except Exception as e:
                            add_status_message(f"Error displaying moderate risk areas: {str(e)}", "error")

                    # Now render power lines, but only those that intersect with risk areas
                    # This ensures we only show power lines in impacted areas
                    if 'saved_power_lines_gdf' in locals() and saved_power_lines_gdf is not None and not saved_power_lines_gdf.empty:
                        try:
                            # Get all the risk geometry - either for specific event or all events
                            risk_geometry = None
                            
                            if selected_event_id == "all_timestamps":
                                if high_risk_df_display is not None and not high_risk_df_display.empty:
                                    risk_geometry = high_risk_df_display.geometry.unary_union
                                if moderate_risk_df_display is not None and not moderate_risk_df_display.empty:
                                    if risk_geometry is not None:
                                        risk_geometry = risk_geometry.union(moderate_risk_df_display.geometry.unary_union)
                                    else:
                                        risk_geometry = moderate_risk_df_display.geometry.unary_union
                            else:
                                # Get geometry for specific event
                                event_gdf = risk_events.get(selected_event_id)
                                if event_gdf is not None and not event_gdf.empty:
                                    risk_geometry = event_gdf.geometry.unary_union
                            
                            # If we have risk geometry, filter power lines to only those intersecting
                            if risk_geometry is not None:
                                filtered_power_lines = saved_power_lines_gdf[saved_power_lines_gdf.intersects(risk_geometry)].copy()
                                
                                if filtered_power_lines.empty:
                                    add_status_message(f"No power lines found in impacted areas.", "info")
                                else:
                                    add_status_message(f"Rendering {len(filtered_power_lines)} power line points in impacted areas", "info")
                                    
                                    # Create a feature group for the dots - add to map last so it's on top
                                    dot_group = folium.FeatureGroup(name=f"Power Lines in Risk Areas ({len(filtered_power_lines)} points)")
                                    
                                    # Add the points as dots directly
                                    for idx, row in filtered_power_lines.iterrows():
                                        # Extract coordinates from the Point geometry
                                        coords = (row.geometry.y, row.geometry.x)
                                        
                                        # Create tooltip for this point
                                        point_tooltip = f"Voltage: {row.get('VOLTAGE', 'N/A')} kV, Owner: {row.get('OWNER', 'N/A')}"
                                        
                                        # Create a slightly larger circle with partial opacity
                                        folium.Circle(
                                            location=coords,
                                            radius=300,  # 300 meters as requested
                                            color='#ff3300',  # Orange-red
                                            weight=2,  # Line weight
                                            fill=True,
                                            fill_color='#ff3300',  # Orange-red
                                            fill_opacity=0.7,  # Partial opacity as requested
                                            tooltip=point_tooltip,  # Use tooltip only, no popup to avoid markers
                                            zIndex=1000  # High z-index to ensure they're on top
                                        ).add_to(dot_group)
                                    
                                    # Add the feature group to the map last (so it's on top)
                                    dot_group.add_to(m)
                            else:
                                add_status_message("No risk areas found to filter power lines.", "warning")
                        except Exception as e:
                            add_status_message(f"Error filtering power lines by risk areas: {str(e)}", "error")
                            
                    # Display details for the selected specific timestamp
                    if selected_event_id != "all_timestamps":
                        event_data = next((e for e in events if e["id"] == selected_event_id), None)
                        if event_data:
                             st.markdown(f"""
                             **Timestamp Details ({event_data['timestamp']}):**
                             - Risk Level: {event_data['risk_level']}
                             - High Risk Areas: {event_data['high_risk_count']}
                             - Moderate Risk Areas: {event_data['moderate_risk_count']}
                             - Max Wind Speed: {event_data['max_wind_speed']:.1f} m/s
                             """)
                             # Only show affected lines estimate if applicable
                             if is_pl_impact and event_data.get('affected_km', 0) > 0:
                                 st.markdown(f"- Affected Power Lines (Est.): ~{event_data['affected_km']:.1f} km")

                else: # Case where risk_found is True but events list is empty
                     add_status_message("Wind risk areas found, but no specific event timestamps generated.", "warning")
        else:
            add_status_message(risk_summary.get("message", "No significant wind risk found."), "info") # Use .get() for safety

    except Exception as e:
        add_status_message(f"Error handling wind risk analysis: {str(e)}", "error")
        # print(f"Detailed error in handle_analyze_wind_risk:") # Removing debug print
        traceback.print_exc() # Keep traceback enabled for now

    # print(f"--- Final Bounds for Map ---: {bounds}") # Removing debug print
    return bounds
