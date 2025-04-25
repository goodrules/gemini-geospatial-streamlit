import streamlit as st
import pandas as pd
import json
import geopandas as gpd
from shapely.geometry import shape
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
        risk_events: List of wind risk events
        summary: Dictionary with risk summary information
    """
    try:
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
                "affected_dates": sorted(wind_risk_areas['forecast_date'].unique().tolist()),
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
                "affected_dates": sorted(wind_risk_areas['forecast_date'].unique().tolist()),
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
        events = []
        risk_events = {}
        
        # Process each date as a potential event
        for date in sorted(risk_areas['forecast_date'].unique()):
            date_areas = risk_areas[risk_areas['forecast_date'] == date]
            
            # Skip if no data for this date
            if date_areas.empty:
                continue
                
            # Count risk levels
            high_count = len(date_areas[date_areas['risk_level'] == 'high'])
            moderate_count = len(date_areas[date_areas['risk_level'] == 'moderate'])
            
            # Skip if no significant risk
            if high_count + moderate_count == 0:
                continue
                
            # Create event ID
            event_id = f"wind_event_{date.replace('-', '')}"
            
            # Create a summary for this event
            event_summary = {
                "id": event_id,
                "date": date,
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
            highest_risk_event = max(events, key=lambda x: x['high_risk_count'] if x['high_risk_count'] > 0 else x['moderate_risk_count']/2)
            highest_risk_date = highest_risk_event['date']
        else:
            highest_risk_date = "None"
        
        summary = {
            "risk_found": len(events) > 0,
            "message": f"Found {len(events)} potential wind events affecting power lines.",
            "event_count": len(events),
            "events": events,
            "high_risk_areas": total_high_risk,
            "moderate_risk_areas": total_moderate_risk,
            "affected_power_lines_km": total_affected_km,
            "highest_risk_date": highest_risk_date,
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
    dates = action.get("dates", [])  # Optional list of specific dates to check
    forecast_days = action.get("forecast_days", 10)  # Number of days to check
    
    try:
        # 1. Get weather forecast data
        weather_df = get_weather_forecast_data()
        
        if weather_df is None or weather_df.empty:
            st.warning("No weather data available for risk analysis")
            return bounds
            
        # 2. Filter by dates if specified
        if dates and isinstance(dates, list) and len(dates) > 0:
            weather_df = weather_df[weather_df["forecast_date"].isin(dates)]
        else:
            # Use all available dates within forecast_days
            all_dates = sorted(weather_df["forecast_date"].unique().tolist())
            # Use first date as reference (init_date)
            base_date = all_dates[0] if all_dates else None
            
            if base_date is not None and len(all_dates) > 1:
                # Get dates within the forecast period
                dates_to_use = all_dates[:min(forecast_days, len(all_dates))]
                weather_df = weather_df[weather_df["forecast_date"].isin(dates_to_use)]
        
        if weather_df.empty:
            st.warning("No weather data available for the specified dates")
            return bounds
        
        # 3. Convert to GeoDataFrame
        geometries = []
        for _, row in weather_df.iterrows():
            # Parse GeoJSON polygon string
            try:
                geojson = json.loads(row['geography_polygon'])
                polygon = shape(geojson)
                geometries.append(polygon)
            except Exception as e:
                st.error(f"Error parsing polygon: {e}")
                continue
        
        # Create GeoDataFrame with weather data
        weather_gdf = gpd.GeoDataFrame(
            weather_df,
            geometry=geometries,
            crs="EPSG:4326"
        )
        
        # 4. Get power lines data
        power_lines_gdf = get_pa_power_lines()
        
        # 5. Analyze wind risk
        st.info(f"Analyzing wind risk to power lines (high: {high_threshold} m/s, moderate: {moderate_threshold} m/s)...")
        risk_events, risk_summary = analyze_wind_risk(
            weather_gdf, 
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
                                fields=['forecast_date', 'wind_speed', 'risk_score'],
                                aliases=['Date', 'Wind Speed (m/s)', 'Risk Score'],
                                localize=True,
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
                                fields=['forecast_date', 'wind_speed', 'risk_score'],
                                aliases=['Date', 'Wind Speed (m/s)', 'Risk Score'],
                                localize=True,
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
