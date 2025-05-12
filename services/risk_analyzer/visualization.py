"""
Visualization functions for risk analysis.

This module contains functions for visualizing risk analysis results on maps and UI.
"""

import streamlit as st
import pandas as pd
import json
import folium
from branca.colormap import LinearColormap
from branca.element import MacroElement
from jinja2 import Template

from services.weather_service import get_weather_color_scale
from utils.streamlit_utils import add_status_message


def create_risk_ui_header(risk_summary):
    """
    Create the UI header for risk analysis results.
    
    Args:
        risk_summary: Dictionary with risk analysis summary.
    """
    # Dynamic title based on analysis type
    analysis_type_title = "General Wind Risk Assessment"
    analysis_details_suffix = ""
    
    if risk_summary.get("analysis_type") == "power_line_impact":
        analysis_type_title = "Power Line Wind Risk Assessment"
    elif risk_summary.get("analyze_power_lines", False):  # Requested PL but didn't get PL impact result
        analysis_details_suffix = " (Power Line Data Issues)"  # Append info

    st.markdown(f"#### {analysis_type_title}{analysis_details_suffix}")
    st.markdown(f"_{risk_summary.get('message', 'Analysis complete.')}_")

    # Display metrics based on analysis type
    metrics_cols = st.columns(3)
    metrics_cols[0].metric("High Risk Areas", f"{risk_summary.get('high_risk_areas', 0)}")
    metrics_cols[1].metric("Moderate Risk Areas", f"{risk_summary.get('moderate_risk_areas', 0)}")
    
    # Only show 'Affected Lines' if power line analysis was successful
    if risk_summary.get("analysis_type") == "power_line_impact":
        metrics_cols[2].metric("Affected Lines (Est.)", f"{risk_summary.get('affected_power_lines_km', 0):.1f} km")
    else:
        metrics_cols[2].empty()  # Leave the column blank if not applicable


def create_event_options(events):
    """
    Create options for the event selector dropdown.
    
    Args:
        events: List of event summary dictionaries.
        
    Returns:
        list: List of (event_id, display_text) tuples for dropdown.
    """
    event_options = [
        (event["id"], f"{event['timestamp']} - {event['risk_level']} Risk (Max: {event['max_wind_speed']:.1f} m/s)")
        for event in events
    ]
    # Sort events chronologically for the dropdown
    event_options.sort(key=lambda x: x[1])
    event_options.insert(0, ("all_timestamps", "Show All Risk Timestamps"))
    
    return event_options


def format_timestamps_for_display(df):
    """
    Format timestamps for display in the UI.
    
    Args:
        df: DataFrame with forecast_time column.
    """
    if df.empty:
        return
        
    try:
        if 'forecast_time' in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df['forecast_time']):
                df.loc[:, 'forecast_time_str'] = df['forecast_time'].dt.strftime('%Y-%m-%d %H:%M')
            else:  # Attempt conversion if not already datetime
                df.loc[:, 'forecast_time'] = pd.to_datetime(df['forecast_time'], errors='coerce')
                df.loc[:, 'forecast_time_str'] = df['forecast_time'].dt.strftime('%Y-%m-%d %H:%M').fillna('Invalid Time')
    except Exception:
        df.loc[:, 'forecast_time_str'] = 'Error Formatting Time'


def process_all_risk_events(risk_events):
    """
    Process all risk events into combined high and moderate risk dataframes.
    
    Args:
        risk_events: Dictionary mapping event IDs to GeoDataFrames.
        
    Returns:
        tuple: (high_risk_df, moderate_risk_df) GeoDataFrames.
    """
    all_areas_list = []
    target_crs = None
    
    for event_id, gdf in risk_events.items():
        add_status_message(f"Processing event {event_id}: {len(gdf) if gdf is not None else 0} areas", "info")
        if gdf is not None and not gdf.empty:
            # Check if risk_level exists
            if 'risk_level' not in gdf.columns:
                add_status_message(f"WARNING: Event {event_id} missing risk_level column", "warning")
                continue
                
            if target_crs is None:
                target_crs = gdf.crs
            if gdf.crs != target_crs:
                gdf = gdf.to_crs(target_crs)
            all_areas_list.append(gdf)

    if not all_areas_list:
        return pd.DataFrame(), pd.DataFrame()
        
    # Combine all areas
    all_risk_gdf = pd.concat(all_areas_list, ignore_index=True)
    
    # Ensure it's still a GeoDataFrame with geometry
    if not isinstance(all_risk_gdf, gpd.GeoDataFrame):
        if 'geometry' not in all_risk_gdf.columns and hasattr(all_risk_gdf, 'geometry'):
            all_risk_gdf = gpd.GeoDataFrame(all_risk_gdf, geometry=all_risk_gdf.geometry.name, crs=target_crs)
        elif 'geometry' in all_risk_gdf.columns and not isinstance(all_risk_gdf, gpd.GeoDataFrame):
            all_risk_gdf = gpd.GeoDataFrame(all_risk_gdf, geometry='geometry', crs=target_crs)

    if all_risk_gdf.empty:
        return pd.DataFrame(), pd.DataFrame()
        
    # Filtering a GeoDataFrame results in a GeoDataFrame
    high_risk_df_display = all_risk_gdf[all_risk_gdf['risk_level'] == 'high'].copy()
    moderate_risk_df_display = all_risk_gdf[all_risk_gdf['risk_level'] == 'moderate'].copy()
    
    return high_risk_df_display, moderate_risk_df_display


def process_single_risk_event(selected_gdf):
    """
    Process a single risk event into high and moderate risk dataframes.
    
    Args:
        selected_gdf: GeoDataFrame for a single event.
        
    Returns:
        tuple: (high_risk_df, moderate_risk_df) GeoDataFrames.
    """
    add_status_message(f"Event has {len(selected_gdf)} total areas", "info")
    
    # Check if the risk_level column exists (it should)
    if 'risk_level' not in selected_gdf.columns:
        add_status_message("WARNING: risk_level column missing from event data", "warning")
        add_status_message(f"Available columns: {', '.join(selected_gdf.columns)}", "info")
        return pd.DataFrame(), pd.DataFrame()
        
    # Filtering a GeoDataFrame results in a GeoDataFrame
    high_risk_df_display = selected_gdf[selected_gdf['risk_level'] == 'high'].copy()
    moderate_risk_df_display = selected_gdf[selected_gdf['risk_level'] == 'moderate'].copy()
    
    # Log counts
    add_status_message(f"Found {len(high_risk_df_display)} high risk and {len(moderate_risk_df_display)} moderate risk areas", "info")
    
    return high_risk_df_display, moderate_risk_df_display


def get_risk_areas_for_display(selected_event_id, risk_events):
    """
    Get risk areas to display based on the selected event ID.
    
    Args:
        selected_event_id: ID of the selected event, or "all_timestamps".
        risk_events: Dictionary mapping event IDs to GeoDataFrames.
        
    Returns:
        tuple: (high_risk_df, moderate_risk_df) GeoDataFrames.
    """
    high_risk_df = pd.DataFrame()
    moderate_risk_df = pd.DataFrame()
    
    if selected_event_id == "all_timestamps":
        add_status_message(f"Showing all risk events ({len(risk_events.keys()) if risk_events else 0} timestamps)", "info")
        if risk_events:
            # Process all risk events
            high_risk_df, moderate_risk_df = process_all_risk_events(risk_events)
    else:
        # Process a single event
        selected_gdf = risk_events.get(selected_event_id)
        add_status_message(f"Showing risk event: {selected_event_id}", "info")
        
        if selected_gdf is not None and not selected_gdf.empty:
            high_risk_df, moderate_risk_df = process_single_risk_event(selected_gdf)
        else:
            add_status_message(f"No data found for event: {selected_event_id}", "warning")
    
    # Format timestamps for display
    format_timestamps_for_display(high_risk_df)
    format_timestamps_for_display(moderate_risk_df)
    
    # Remove datetime columns that are not JSON serializable
    for df in [high_risk_df, moderate_risk_df]:
        if not df.empty:
            if 'forecast_time' in df.columns:
                df.drop(columns=['forecast_time'], inplace=True, errors='ignore')
            if 'init_time' in df.columns:
                df.drop(columns=['init_time'], inplace=True, errors='ignore')
    
    return high_risk_df, moderate_risk_df


def prepare_risk_colormaps(is_pl_impact):
    """
    Prepare color scales for risk visualization.
    
    Args:
        is_pl_impact: Boolean indicating if this is a power line impact analysis.
        
    Returns:
        dict: Dictionary of colormaps for high and moderate risk.
    """
    caption_suffix = " (Power Lines)" if is_pl_impact else ""
    
    risk_colormaps = {
        'high': get_weather_color_scale('wind_risk', 0, 100),
        'moderate': get_weather_color_scale('wind_risk', 0, 100)
    }
    
    risk_colormaps['high'].caption = f"High Wind Risk Score{caption_suffix}"
    risk_colormaps['moderate'].caption = f"Moderate Wind Risk Score{caption_suffix}"
    
    return risk_colormaps


def add_high_risk_layer(high_risk_df, is_pl_impact, m, bounds, risk_colormaps):
    """
    Add high risk areas to the map.
    
    Args:
        high_risk_df: GeoDataFrame with high risk areas.
        is_pl_impact: Boolean indicating if this is a power line impact analysis.
        m: Folium map object.
        bounds: List to append map bounds to.
        risk_colormaps: Dictionary of colormaps.
    """
    layer_name_suffix = " (Power Lines)" if is_pl_impact else ""
    add_status_message(f"Drawing {len(high_risk_df)} high risk areas on map", "info")
    
    try:
        # Calculate bounds BEFORE converting to JSON, ensuring standard floats
        b = high_risk_df.total_bounds  # [minx, miny, maxx, maxy]
        bounds.append([[float(b[1]), float(b[0])], [float(b[3]), float(b[2])]])  # [[miny, minx], [maxy, maxx]]
        
        # Check for required columns
        if 'geometry' not in high_risk_df:
            add_status_message("High risk dataframe missing geometry column!", "error")
            return
        
        # Convert to GeoJSON dictionary
        high_risk_geojson = json.loads(high_risk_df.to_json())
        
        # Check for features in GeoJSON
        if not high_risk_geojson.get('features', []):
            add_status_message("No features in high risk GeoJSON!", "warning")
            return
            
        # Add main GeoJSON layer
        folium.GeoJson(
            high_risk_geojson,
            name=f"High Wind Risk Areas{layer_name_suffix}",
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
        for idx, row in high_risk_df.iterrows():
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
        
        # Add color scale legend
        risk_colormaps['high'].add_to(m)
        
    except Exception as e:
        add_status_message(f"Error displaying high risk areas: {str(e)}", "error")


def add_moderate_risk_layer(moderate_risk_df, is_pl_impact, m, bounds, risk_colormaps):
    """
    Add moderate risk areas to the map.
    
    Args:
        moderate_risk_df: GeoDataFrame with moderate risk areas.
        is_pl_impact: Boolean indicating if this is a power line impact analysis.
        m: Folium map object.
        bounds: List to append map bounds to.
        risk_colormaps: Dictionary of colormaps.
    """
    layer_name_suffix = " (Power Lines)" if is_pl_impact else ""
    add_status_message(f"Drawing {len(moderate_risk_df)} moderate risk areas on map", "info")
    
    try:
        # Calculate bounds BEFORE converting to JSON, ensuring standard floats
        b = moderate_risk_df.total_bounds  # [minx, miny, maxx, maxy]
        bounds.append([[float(b[1]), float(b[0])], [float(b[3]), float(b[2])]])  # [[miny, minx], [maxy, maxx]]
        
        # Check for required columns
        if 'geometry' not in moderate_risk_df:
            add_status_message("Moderate risk dataframe missing geometry column!", "error")
            return
        
        # Convert to GeoJSON dictionary
        moderate_risk_geojson = json.loads(moderate_risk_df.to_json())
        
        # Check for features in GeoJSON
        if not moderate_risk_geojson.get('features', []):
            add_status_message("No features in moderate risk GeoJSON!", "warning")
            return
            
        # Add main GeoJSON layer
        folium.GeoJson(
            moderate_risk_geojson,
            name=f"Moderate Wind Risk Areas{layer_name_suffix}",
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
        for idx, row in moderate_risk_df.iterrows():
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
        
        # Add color scale legend
        risk_colormaps['moderate'].add_to(m)
        
    except Exception as e:
        add_status_message(f"Error displaying moderate risk areas: {str(e)}", "error")


def add_risk_layers_to_map(high_risk_df, moderate_risk_df, is_pl_impact, m, bounds):
    """
    Add risk layers to the map.
    
    Args:
        high_risk_df: GeoDataFrame with high risk areas.
        moderate_risk_df: GeoDataFrame with moderate risk areas.
        is_pl_impact: Boolean indicating if this is a power line impact analysis.
        m: Folium map object.
        bounds: List to append map bounds to.
        
    Returns:
        list: Updated bounds list.
    """
    # Prepare risk colormaps and labels
    risk_colormaps = prepare_risk_colormaps(is_pl_impact)
    
    # Add high risk layer
    if not high_risk_df.empty:
        add_high_risk_layer(high_risk_df, is_pl_impact, m, bounds, risk_colormaps)
    
    # Add moderate risk layer
    if not moderate_risk_df.empty:
        add_moderate_risk_layer(moderate_risk_df, is_pl_impact, m, bounds, risk_colormaps)
    
    return bounds


def create_voltage_legend(m):
    """
    Create a legend for power line voltage colors.
    
    Args:
        m: Folium map object.
        
    Returns:
        folium.Map: Map with legend added.
    """
    legend_html = """
    {% macro html(this, kwargs) %}
    <div style="
        position: fixed; 
        bottom: 50px; 
        right: 50px; 
        width: 180px; 
        height: 150px; 
        z-index: 1000;
        background-color: white;
        padding: 10px;
        border-radius: 5px;
        border: 2px solid grey;
        font-size: 14px;
        color: black;
        text-shadow: 0px 0px 1px rgba(255,255,255,0.5);
        box-shadow: 0 0 15px rgba(0,0,0,0.2);
        ">
        <div style="text-align: center; margin-bottom: 5px; font-weight: bold; color: black;">Power Line Voltage</div>
        <div style="margin-bottom: 5px; color: black;">
            <span style="display: inline-block; width: 15px; height: 15px; background-color: #FFD700; margin-right: 5px; border: 1px solid #333;"></span>
            &lt; 100 kV (Low)
        </div>
        <div style="margin-bottom: 5px; color: black;">
            <span style="display: inline-block; width: 15px; height: 15px; background-color: #FFA500; margin-right: 5px; border: 1px solid #333;"></span>
            100-300 kV (Medium)
        </div>
        <div style="margin-bottom: 5px; color: black;">
            <span style="display: inline-block; width: 15px; height: 15px; background-color: #FF0000; margin-right: 5px; border: 1px solid #333;"></span>
            300-500 kV (High)
        </div>
        <div style="color: black;">
            <span style="display: inline-block; width: 15px; height: 15px; background-color: #8B0000; margin-right: 5px; border: 1px solid #333;"></span>
            &gt; 500 kV (Very High)
        </div>
    </div>
    {% endmacro %}
    """
    
    legend = MacroElement()
    legend._template = Template(legend_html)
    
    m.get_root().add_child(legend)
    
    return m


def add_power_lines_to_map(power_lines_gdf, high_risk_df, moderate_risk_df, selected_event_id, risk_events, m):
    """
    Add power lines to the map, filtered to only those in risk areas.
    
    Args:
        power_lines_gdf: GeoDataFrame with power line geometries.
        high_risk_df: GeoDataFrame with high risk areas.
        moderate_risk_df: GeoDataFrame with moderate risk areas.
        selected_event_id: ID of selected event or "all_timestamps".
        risk_events: Dictionary mapping event IDs to GeoDataFrames.
        m: Folium map object.
    """
    import geopandas as gpd
    
    try:
        # Get all the risk geometry - either for specific event or all events
        risk_geometry = None
        
        if selected_event_id == "all_timestamps":
            if high_risk_df is not None and not high_risk_df.empty:
                risk_geometry = high_risk_df.geometry.unary_union
            if moderate_risk_df is not None and not moderate_risk_df.empty:
                if risk_geometry is not None:
                    risk_geometry = risk_geometry.union(moderate_risk_df.geometry.unary_union)
                else:
                    risk_geometry = moderate_risk_df.geometry.unary_union
        else:
            # Get geometry for specific event
            event_gdf = risk_events.get(selected_event_id)
            if event_gdf is not None and not event_gdf.empty:
                risk_geometry = event_gdf.geometry.unary_union
        
        # If we have risk geometry, filter power lines to those intersecting
        # If not, use all power lines in the region
        if risk_geometry is not None:
            add_status_message("Filtering power lines to those in risk areas...", "info")
            filtered_power_lines = power_lines_gdf[power_lines_gdf.intersects(risk_geometry)].copy()
            area_description = "risk areas"
        else:
            add_status_message("No risk areas found. Showing all power lines in region.", "info")
            filtered_power_lines = power_lines_gdf.copy()
            area_description = "region"
        
        if filtered_power_lines.empty:
            add_status_message(f"No power lines found in {area_description}.", "info")
            return
            
        add_status_message(f"Rendering {len(filtered_power_lines)} power line points in {area_description}", "info")
        
        # Create a feature group for power lines
        feature_name = "Power Lines in Risk Areas" if risk_geometry is not None else "Power Lines in Region"
        dot_group = folium.FeatureGroup(name=f"{feature_name} ({len(filtered_power_lines)} points)")
        
        # Add power line points to the map
        for idx, row in filtered_power_lines.iterrows():
            # Extract coordinates
            coords = (row.geometry.y, row.geometry.x)
            
            # Create tooltip
            point_tooltip = f"""
            <div style='min-width: 200px;'>
                <b>Voltage:</b> {row.get('VOLTAGE', 'N/A')} kV<br>
                <b>Type:</b> {row.get('TYPE', 'N/A')}<br>
                <b>Owner:</b> {row.get('OWNER', 'N/A')}<br>
                <b>Description:</b> {row.get('NAICS_DESC', 'N/A')}
            </div>
            """
            
            # Determine color based on voltage
            voltage = row.get('VOLTAGE', 0)
            
            if voltage < 100:
                line_color = '#FFD700'  # Yellow for low voltage
            elif voltage < 300:
                line_color = '#FFA500'  # Orange for medium voltage
            elif voltage < 500:
                line_color = '#FF0000'  # Red for high voltage
            else:
                line_color = '#8B0000'  # DarkRed for very high voltage
            
            # Create a circle with voltage-based colors
            folium.Circle(
                location=coords,
                radius=400,  # Adjusted to 400 meters
                color=line_color,
                weight=2,
                fill=True,
                fill_color=line_color,
                fill_opacity=0.7,
                tooltip=point_tooltip,
                zIndex=1000  # High z-index to ensure they're on top
            ).add_to(dot_group)
        
        # Add the feature group to the map
        dot_group.add_to(m)
        
        # Add voltage legend to the map
        create_voltage_legend(m)
        
    except Exception as e:
        add_status_message(f"Error adding power lines to map: {str(e)}", "error")


def display_event_details(selected_event_id, events, is_pl_impact):
    """
    Display details for a specific event.
    
    Args:
        selected_event_id: ID of the selected event.
        events: List of event summary dictionaries.
        is_pl_impact: Boolean indicating if this is a power line impact analysis.
    """
    if selected_event_id == "all_timestamps":
        return
        
    event_data = next((e for e in events if e["id"] == selected_event_id), None)
    if not event_data:
        return
        
    # Create formatted markdown
    details_md = f"""
    **Timestamp Details ({event_data['timestamp']}):**
    - Risk Level: {event_data['risk_level']}
    - High Risk Areas: {event_data['high_risk_count']}
    - Moderate Risk Areas: {event_data['moderate_risk_count']}
    - Max Wind Speed: {event_data['max_wind_speed']:.1f} m/s
    """
    
    # Only show affected lines estimate if applicable
    if is_pl_impact and event_data.get('affected_km', 0) > 0:
        details_md += f"- Affected Power Lines (Est.): ~{event_data['affected_km']:.1f} km"
        
    st.markdown(details_md)


def display_risk_results(risk_summary, risk_events, m, power_lines_gdf, bounds):
    """
    Display risk analysis results in the UI and on the map.
    
    Args:
        risk_summary: Dictionary with risk analysis summary.
        risk_events: Dictionary mapping event IDs to GeoDataFrames.
        m: Folium map object.
        power_lines_gdf: GeoDataFrame with power line geometries.
        bounds: List to append map bounds to.
    """
    risk_container = st.container(border=True)
    with risk_container:
        # Create UI components for risk display
        create_risk_ui_header(risk_summary)
        
        # Create event selector if we have events
        if "events" in risk_summary and risk_summary.get("events"):
            events = risk_summary["events"]
            event_options = create_event_options(events)
            
            selected_event_id = st.selectbox(
                "Select Risk Timestamp to Display:",
                options=[id for id, _ in event_options],
                format_func=lambda x: dict(event_options).get(x, "Select..."),
                key="wind_event_selector"
            )
            
            # Get risk areas to display
            high_risk_df, moderate_risk_df = get_risk_areas_for_display(
                selected_event_id, risk_events
            )
            
            # Add risk layers to map
            is_pl_impact = risk_summary.get("analysis_type") == "power_line_impact"
            add_risk_layers_to_map(
                high_risk_df, moderate_risk_df, is_pl_impact, m, bounds
            )
            
            # Potentially add power line visualization
            if power_lines_gdf is not None and not power_lines_gdf.empty:
                add_power_lines_to_map(
                    power_lines_gdf, 
                    high_risk_df, 
                    moderate_risk_df,
                    selected_event_id,
                    risk_events,
                    m
                )
            
            # Display details for a specific timestamp
            display_event_details(selected_event_id, events, is_pl_impact)
            
        else:
            add_status_message("Wind risk areas found, but no specific event timestamps generated.", "warning") 
