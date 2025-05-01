import streamlit as st
import pandas as pd
import json
import traceback # Import traceback
import geopandas as gpd
from shapely.geometry import shape
from shapely import wkt # Ensure wkt is imported
import folium
from branca.colormap import LinearColormap
from data.weather_data import get_weather_forecast_data
from data.geospatial_data import get_pa_power_lines
from services.map_core import serialize_geojson
from services.weather_service import get_weather_color_scale
from datetime import date, timedelta # Ensure date and timedelta are imported

def analyze_wind_risk(weather_gdf, power_lines_gdf, high_threshold=16.0, moderate_threshold=13.0):
    """
    Analyze risk to power lines from high and moderate winds at specific timestamps.

    Args:
        weather_gdf: GeoDataFrame with weather forecast data (already filtered for time period).
        power_lines_gdf: GeoDataFrame with power line geometries.
        high_threshold: High risk wind speed threshold in m/s (default: 16.0 m/s).
        moderate_threshold: Moderate risk wind speed threshold in m/s (default: 13.0 m/s).

    Returns:
        risk_events: Dictionary mapping timestamp-based event IDs (e.g., wind_event_YYYYMMDD_HHMM)
                     to GeoDataFrames of risk areas for that specific timestamp.
        summary: Dictionary with overall risk summary information across all timestamps.
    """
    try:
        # Ensure forecast_time is datetime (should be done by handler, but double-check)
        if 'forecast_time' not in weather_gdf.columns:
             st.error("Weather data for risk analysis missing 'forecast_time'.")
             return {}, {"risk_found": False, "message": "Missing 'forecast_time'."}

        # Check if empty before starting
        if weather_gdf.empty:
            st.warning("[Risk Analysis] Input weather data is empty.")
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

        # Classify risk levels using .loc
        wind_risk_areas_initial.loc[:, 'risk_level'] = 'moderate'
        wind_risk_areas_initial.loc[wind_risk_areas_initial['wind_speed'] >= high_threshold, 'risk_level'] = 'high'

        # 2. Prepare power lines data
        if power_lines_gdf is None:
            power_lines_gdf = get_pa_power_lines()

        if power_lines_gdf is None or power_lines_gdf.empty:
            # Still return the wind risk areas found, but indicate no power line data
            st.warning("Power line data not available for detailed intersection analysis.")
            # Group initial risk areas by timestamp for summary/display even without intersection
            events_no_pl = []
            risk_events_no_pl = {}
            unique_timestamps_no_pl = sorted(wind_risk_areas_initial['forecast_time'].unique())
            for timestamp in unique_timestamps_no_pl:
                 timestamp_areas = wind_risk_areas_initial[wind_risk_areas_initial['forecast_time'] == timestamp].copy()
                 if timestamp_areas.empty: continue
                 high_count = len(timestamp_areas[timestamp_areas['risk_level'] == 'high'])
                 moderate_count = len(timestamp_areas[timestamp_areas['risk_level'] == 'moderate'])
                 if high_count + moderate_count == 0: continue
                 timestamp_str_id = timestamp.strftime('%Y%m%d_%H%M')
                 timestamp_str_display = timestamp.strftime('%Y-%m-%d %H:%M UTC')
                 event_id = f"wind_event_{timestamp_str_id}"
                 event_summary = { "id": event_id, "timestamp": timestamp_str_display, "high_risk_count": high_count, "moderate_risk_count": moderate_count, "max_wind_speed": timestamp_areas['wind_speed'].max(), "affected_km": 0, "risk_level": "High" if high_count > 0 else "Moderate" }
                 events_no_pl.append(event_summary)
                 # Add default risk_score before storing
                 timestamp_areas.loc[:, 'risk_score'] = 0
                 risk_events_no_pl[event_id] = timestamp_areas # Store the areas themselves

            summary_no_pl = {
                "risk_found": True,
                "message": f"Found {len(events_no_pl)} timestamps with high/moderate wind risk, but no power line data available for detailed assessment.",
                "event_count": len(events_no_pl),
                "events": events_no_pl,
                "high_risk_areas": sum(e['high_risk_count'] for e in events_no_pl),
                "moderate_risk_areas": sum(e['moderate_risk_count'] for e in events_no_pl),
                "affected_power_lines_km": 0,
                "highest_risk_timestamp": max(events_no_pl, key=lambda x: (x['high_risk_count'], x['max_wind_speed']))['timestamp'] if events_no_pl else "None",
                "max_wind_speed": max(e['max_wind_speed'] for e in events_no_pl) if events_no_pl else 0
            }
            return risk_events_no_pl, summary_no_pl


        # 3. Create a buffer around power lines (approximately 1km buffer)
        try:
            power_lines_proj = power_lines_gdf.to_crs("EPSG:3857")  # Web Mercator
            buffered_lines = power_lines_proj.buffer(1000)  # 1km buffer
            # Create new GeoDataFrame with buffered geometry (original gdf geometry name is preserved)
            # Removed problematic rename: power_lines_gdf.rename_geometry('geometry', inplace=True)
            buffered_lines_gdf = gpd.GeoDataFrame(geometry=buffered_lines, crs="EPSG:3857")
            # Add necessary columns from original GDF if needed later, e.g., power_lines_gdf['id']
            buffered_lines_gdf = buffered_lines_gdf.to_crs("EPSG:4326")  # Back to WGS84
        except Exception as buffer_err:
            st.error(f"Error buffering power lines: {buffer_err}")
            return {}, {"risk_found": False, "message": f"Error buffering power lines: {buffer_err}"}

        # 4. Perform spatial join to find intersections
        try:
            # Ensure CRS match before join
            wind_risk_areas_proj = wind_risk_areas_initial.to_crs(buffered_lines_gdf.crs)
            # Perform spatial join
            joined_areas = gpd.sjoin(wind_risk_areas_proj, buffered_lines_gdf, how="inner", predicate="intersects")
        except Exception as join_err:
             st.error(f"Error during spatial join: {join_err}")
             return {}, {"risk_found": False, "message": f"Error during spatial join: {join_err}"}


        if joined_areas.empty:
             # Found wind risk, but not intersecting power lines
            st.info("Found areas with high/moderate wind risk, but none intersected buffered power lines.")
            # Reuse the summary logic from the no-powerline-data case
            events_no_intersect = []
            risk_events_no_intersect = {}
            unique_timestamps_no_intersect = sorted(wind_risk_areas_initial['forecast_time'].unique())
            for timestamp in unique_timestamps_no_intersect:
                 timestamp_areas = wind_risk_areas_initial[wind_risk_areas_initial['forecast_time'] == timestamp].copy()
                 if timestamp_areas.empty: continue
                 high_count = len(timestamp_areas[timestamp_areas['risk_level'] == 'high'])
                 moderate_count = len(timestamp_areas[timestamp_areas['risk_level'] == 'moderate'])
                 if high_count + moderate_count == 0: continue
                 timestamp_str_id = timestamp.strftime('%Y%m%d_%H%M')
                 timestamp_str_display = timestamp.strftime('%Y-%m-%d %H:%M UTC')
                 event_id = f"wind_event_{timestamp_str_id}"
                 event_summary = { "id": event_id, "timestamp": timestamp_str_display, "high_risk_count": high_count, "moderate_risk_count": moderate_count, "max_wind_speed": timestamp_areas['wind_speed'].max(), "affected_km": 0, "risk_level": "High" if high_count > 0 else "Moderate" }
                 events_no_intersect.append(event_summary)
                 # Add default risk_score before storing
                 timestamp_areas.loc[:, 'risk_score'] = 0
                 risk_events_no_intersect[event_id] = timestamp_areas

            summary_no_intersect = {
                "risk_found": True, # Risk was found, just not intersecting
                "message": f"Found {len(events_no_intersect)} timestamps with high/moderate wind risk, but none appear to affect power lines.",
                "event_count": len(events_no_intersect),
                "events": events_no_intersect,
                "high_risk_areas": sum(e['high_risk_count'] for e in events_no_intersect),
                "moderate_risk_areas": sum(e['moderate_risk_count'] for e in events_no_intersect),
                "affected_power_lines_km": 0,
                "highest_risk_timestamp": max(events_no_intersect, key=lambda x: (x['high_risk_count'], x['max_wind_speed']))['timestamp'] if events_no_intersect else "None",
                "max_wind_speed": max(e['max_wind_speed'] for e in events_no_intersect) if events_no_intersect else 0
            }
            # Return the original risk areas, not the empty joined_areas
            return risk_events_no_intersect, summary_no_intersect


        # Ensure we are working with a copy after the join to avoid SettingWithCopyWarning
        # Keep only unique risk area geometries (a risk area might intersect multiple line buffers)
        risk_areas = joined_areas.drop_duplicates(subset=['geography_polygon', 'forecast_time']).copy()

        # 5. Calculate risk metrics
        # Add a risk score - percentage scale using .loc
        max_possible_wind = risk_areas['wind_speed'].max()
        # Ensure denominator is not zero if all winds are at the threshold
        if (max_possible_wind - moderate_threshold) > 0:
            score_series = ((risk_areas['wind_speed'] - moderate_threshold) /
                            (max_possible_wind - moderate_threshold) * 100)
        else:
            score_series = 0 # Assign 0 if max wind is equal to the threshold
        risk_areas.loc[:, 'risk_score'] = score_series
        risk_areas.loc[:, 'risk_score'] = risk_areas['risk_score'].clip(0, 100)

        # 6. Group data into events by forecast timestamp
        events = [] # List to hold summary dictionaries for each event timestamp
        risk_events = {} # Dict to hold GeoDataFrames for each event timestamp

        unique_timestamps = sorted(risk_areas['forecast_time'].unique())

        for timestamp in unique_timestamps:
            timestamp_areas = risk_areas[risk_areas['forecast_time'] == timestamp].copy()
            if timestamp_areas.empty: continue

            high_count = len(timestamp_areas[timestamp_areas['risk_level'] == 'high'])
            moderate_count = len(timestamp_areas[timestamp_areas['risk_level'] == 'moderate'])
            if high_count + moderate_count == 0: continue

            timestamp_str_id = timestamp.strftime('%Y%m%d_%H%M')
            timestamp_str_display = timestamp.strftime('%Y-%m-%d %H:%M UTC')
            event_id = f"wind_event_{timestamp_str_id}"

            event_summary = {
                "id": event_id,
                "timestamp": timestamp_str_display,
                "high_risk_count": high_count,
                "moderate_risk_count": moderate_count,
                "max_wind_speed": timestamp_areas['wind_speed'].max(),
                # A very rough estimate - area of risk polygons might be better
                "affected_km": len(timestamp_areas) * 0.25, # Placeholder - needs better logic if required
                "risk_level": "High" if high_count > 0 else "Moderate"
            }
            events.append(event_summary)
            risk_events[event_id] = timestamp_areas # Store GDF for this specific timestamp

        # 7. Prepare overall summary
        total_high_risk = sum(event['high_risk_count'] for event in events)
        total_moderate_risk = sum(event['moderate_risk_count'] for event in events)
        total_affected_km = sum(event['affected_km'] for event in events) # Still using placeholder
        max_wind_overall = max(event['max_wind_speed'] for event in events) if events else 0

        if events:
            highest_risk_event = max(events, key=lambda x: (x['high_risk_count'], x['max_wind_speed']))
            highest_risk_timestamp_str = highest_risk_event['timestamp']
        else:
            highest_risk_timestamp_str = "None"

        summary = {
            "risk_found": len(events) > 0,
            "message": f"Found {len(events)} potential wind risk timestamps affecting power lines.",
            "event_count": len(events),
            "events": events,
            "high_risk_areas": total_high_risk,
            "moderate_risk_areas": total_moderate_risk,
            "affected_power_lines_km": total_affected_km, # Using placeholder value
            "highest_risk_timestamp": highest_risk_timestamp_str,
            "max_wind_speed": max_wind_overall
        }

        return risk_events, summary

    except Exception as e:
        st.error(f"Error analyzing wind risk: {str(e)}")
        # Use traceback for more detail if needed: import traceback; traceback.print_exc()
        return {}, {
            "risk_found": False,
            "message": f"Error analyzing wind risk: {str(e)}"
        }


def handle_analyze_wind_risk(action, m):
    """
    Handle the analyze_wind_risk action by analyzing specific timestamps.

    Args:
        action: The action dictionary with parameters ('forecast_days', 'high_threshold', 'moderate_threshold').
        m: The folium map object.

    Returns:
        List of bounds to include in the overall map fitting.
    """
    bounds = []

    # Parameters for risk analysis
    high_threshold = action.get("high_threshold", 16.0)
    moderate_threshold = action.get("moderate_threshold", 13.0)
    forecast_days = action.get("forecast_days", 3) # Default to 3 days

    try:
        # 1. Get all weather forecast data for the selected init_date
        selected_init_date = st.session_state.get("selected_init_date", date.today())
        weather_df_all = get_weather_forecast_data(selected_init_date)

        if weather_df_all is None or weather_df_all.empty:
            st.warning("No weather data available for risk analysis.")
            return bounds

        # Ensure forecast_time is datetime and UTC
        if 'forecast_time' not in weather_df_all.columns:
             st.error("Weather data missing 'forecast_time' column.")
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
            st.error(f"Error processing forecast timestamps: {e}")
            return bounds

        if weather_df_all.empty:
            st.warning("No valid weather timestamps found after processing.")
            return bounds

        # 2. Filter weather data for the specified number of forecast days
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

        # 3. Convert filtered data to GeoDataFrame
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

        # 4. Get power lines data
        power_lines_gdf = get_pa_power_lines()

        # 5. Analyze wind risk (using the already filtered weather_gdf)
        st.info(f"Analyzing wind risk for the {filter_msg} to power lines (high >= {high_threshold} m/s, moderate >= {moderate_threshold} m/s)...")
        # analyze_wind_risk now expects the GDF already filtered by time
        risk_events, risk_summary = analyze_wind_risk(
            weather_gdf,
            power_lines_gdf,
            high_threshold,
            moderate_threshold
        )

        # 6. Display risk summary in Streamlit UI
        if risk_summary["risk_found"]:
            risk_container = st.container(border=True) # Add border for visual grouping
            with risk_container:
                st.markdown("#### Power Line Wind Risk Assessment")
                st.markdown(f"_{risk_summary['message']}_")

                metrics_cols = st.columns(3)
                # Use get() with default 0 for potentially missing keys
                metrics_cols[0].metric("High Risk Timestamps", f"{risk_summary.get('high_risk_areas', 0)}")
                metrics_cols[1].metric("Moderate Risk Timestamps", f"{risk_summary.get('moderate_risk_areas', 0)}")
                # Use placeholder affected_km for now
                metrics_cols[2].metric("Affected Lines (Est.)", f"{risk_summary.get('affected_power_lines_km', 0):.1f} km")

                # Create the timestamp selector
                if "events" in risk_summary and risk_summary["events"]:
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

                    # 7. Visualize risk areas based on selection
                    if power_lines_gdf is not None:
                         folium.GeoJson(
                             power_lines_gdf, # Direct GDF usage
                             name="Power Lines",
                             style_function=lambda x: {'color': '#0066cc', 'weight': 1.5, 'opacity': 0.6}
                         ).add_to(m)

                    risk_colormaps = {
                        'high': get_weather_color_scale('wind_risk', 0, 100), # Reuse scale logic
                        'moderate': get_weather_color_scale('wind_risk', 0, 100) # Same scale, different caption maybe?
                    }
                    # Adjust captions if needed
                    risk_colormaps['high'].caption = "High Wind Risk Score (Power Lines)"
                    risk_colormaps['moderate'].caption = "Moderate Wind Risk Score (Power Lines)"


                    # Prepare DataFrames for display. They will become GeoDataFrames when assigned data.
                    high_risk_df_display = pd.DataFrame()
                    moderate_risk_df_display = pd.DataFrame()


                    if selected_event_id == "all_timestamps":
                        if risk_events:
                             # Ensure all GDFs have the same CRS before concat
                             all_areas_list = []
                             target_crs = None
                             for gdf in risk_events.values():
                                 if gdf is not None and not gdf.empty:
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
                        if selected_gdf is not None and not selected_gdf.empty:
                             # Filtering a GeoDataFrame results in a GeoDataFrame
                             high_risk_df_display = selected_gdf[selected_gdf['risk_level'] == 'high'].copy()
                             moderate_risk_df_display = selected_gdf[selected_gdf['risk_level'] == 'moderate'].copy()

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
                        # Calculate bounds BEFORE converting to JSON, ensuring standard floats
                        b = high_risk_df_display.total_bounds # [minx, miny, maxx, maxy]
                        bounds.append([[float(b[1]), float(b[0])], [float(b[3]), float(b[2])]]) # [[miny, minx], [maxy, maxx]]
                        # Convert to GeoJSON dictionary
                        high_risk_geojson = json.loads(high_risk_df_display.to_json())
                        # print("--- High Risk GeoJSON for Folium ---") # Removing debug print
                        # print(json.dumps(high_risk_geojson, indent=2, default=str)) # Removing debug print
                        folium.GeoJson(
                            high_risk_geojson, # Use GeoJSON dictionary
                            name="High Wind Risk Areas",
                            style_function=lambda feature: risk_style_func(feature, 'high'),
                            tooltip=folium.GeoJsonTooltip(
                                fields=['forecast_time_str', 'wind_speed', 'risk_score'],
                                aliases=['Time (UTC)', 'Wind Speed (m/s)', 'Risk Score (%)'],
                                localize=False, sticky=True
                            )
                        ).add_to(m)
                        risk_colormaps['high'].add_to(m) # Add legend
                        # Bounds calculation moved up

                    if not moderate_risk_df_display.empty:
                        # Calculate bounds BEFORE converting to JSON, ensuring standard floats
                        b = moderate_risk_df_display.total_bounds # [minx, miny, maxx, maxy]
                        bounds.append([[float(b[1]), float(b[0])], [float(b[3]), float(b[2])]]) # [[miny, minx], [maxy, maxx]]
                        # Convert to GeoJSON dictionary
                        moderate_risk_geojson = json.loads(moderate_risk_df_display.to_json())
                        # print("--- Moderate Risk GeoJSON for Folium ---") # Removing debug print
                        # print(json.dumps(moderate_risk_geojson, indent=2, default=str)) # Removing debug print
                        folium.GeoJson(
                            moderate_risk_geojson, # Use GeoJSON dictionary
                            name="Moderate Wind Risk Areas",
                            style_function=lambda feature: risk_style_func(feature, 'moderate'),
                            tooltip=folium.GeoJsonTooltip(
                                fields=['forecast_time_str', 'wind_speed', 'risk_score'],
                                aliases=['Time (UTC)', 'Wind Speed (m/s)', 'Risk Score (%)'],
                                localize=False, sticky=True
                            )
                        ).add_to(m)
                        risk_colormaps['moderate'].add_to(m) # Add legend
                        # Bounds calculation moved up

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
                             # - Affected Power Lines (Est.): ~{event_data['affected_km']:.1f} km # Removed placeholder

                else: # Case where risk_found is True but events list is empty (shouldn't happen with current logic, but safe)
                     st.warning("Wind risk areas found, but no specific event timestamps generated.")
        else:
            st.info(risk_summary.get("message", "No significant wind risk found.")) # Use .get() for safety

    except Exception as e:
        st.error(f"Error handling wind risk analysis: {str(e)}")
        # print(f"Detailed error in handle_analyze_wind_risk:") # Removing debug print
        traceback.print_exc() # Keep traceback enabled for now

    # print(f"--- Final Bounds for Map ---: {bounds}") # Removing debug print
    return bounds
