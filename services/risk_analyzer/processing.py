"""
Processing functions for risk analysis.

This module contains core data processing functions for risk analysis.
"""

import geopandas as gpd
from utils.streamlit_utils import add_status_message


def filter_by_risk_thresholds(weather_gdf, moderate_threshold, high_threshold):
    """
    Filter weather data by wind speed thresholds and add risk levels.
    
    Args:
        weather_gdf: GeoDataFrame with weather forecast data.
        moderate_threshold: Wind speed threshold for moderate risk (m/s).
        high_threshold: Wind speed threshold for high risk (m/s).
        
    Returns:
        GeoDataFrame: Filtered data with risk levels added.
    """
    risk_areas = weather_gdf[weather_gdf['wind_speed'] >= moderate_threshold].copy()
    
    if not risk_areas.empty:
        risk_areas.loc[:, 'risk_level'] = 'moderate'
        risk_areas.loc[risk_areas['wind_speed'] >= high_threshold, 'risk_level'] = 'high'
        
        # Verify risk level column was added
        if 'risk_level' not in risk_areas.columns:
            add_status_message("WARNING: Failed to add risk_level column to weather data", "warning")
            # Add it again to be sure
            risk_areas['risk_level'] = 'moderate'
            risk_areas.loc[risk_areas['wind_speed'] >= high_threshold, 'risk_level'] = 'high'
            
    return risk_areas


def buffer_power_lines(power_lines_gdf):
    """
    Create buffers around power lines for intersection.
    
    Args:
        power_lines_gdf: GeoDataFrame with power line geometries.
        
    Returns:
        GeoDataFrame: Buffered power lines in WGS84 projection.
    """
    add_status_message(f"Creating buffer around power points for risk analysis", "info")
    
    # Convert to appropriate projection for buffering
    power_lines_proj = power_lines_gdf.to_crs("EPSG:3857")  # Web Mercator
    
    # Use 500m buffer for points
    buffer_distance = 500
    
    # Create buffer and prepare for intersection
    buffered_lines = power_lines_proj.buffer(buffer_distance)
    buffered_lines_gdf = gpd.GeoDataFrame(geometry=buffered_lines, crs="EPSG:3857")
    return buffered_lines_gdf.to_crs("EPSG:4326")  # Back to WGS84


def process_power_line_impact(wind_risk_areas, power_lines_gdf, analyze_power_line_impact, moderate_threshold, high_threshold):
    """
    Process power line impact analysis if requested.
    
    Args:
        wind_risk_areas: GeoDataFrame with wind risk areas.
        power_lines_gdf: GeoDataFrame with power line geometries.
        analyze_power_line_impact: Boolean flag to perform power line impact analysis.
        moderate_threshold: Wind speed threshold for moderate risk (m/s).
        high_threshold: Wind speed threshold for high risk (m/s).
        
    Returns:
        tuple: (risk_areas, result_dict) where risk_areas is a GeoDataFrame of filtered areas
               and result_dict contains information about the intersection process.
    """
    result = {
        "intersection_performed": False,
        "no_intersection_found": False,
        "power_lines_loaded": power_lines_gdf is not None and not power_lines_gdf.empty
    }
    
    # Initialize risk_areas with the initial filtered set
    risk_areas = wind_risk_areas.copy()
    
    if not analyze_power_line_impact:
        return risk_areas, result
        
    if not result["power_lines_loaded"]:
        add_status_message("Power line impact analysis requested, but no filtered power line data is available. Proceeding with general wind risk analysis.", "warning")
        return risk_areas, result
    
    # Buffer power lines and perform intersection
    try:
        buffered_lines_gdf = buffer_power_lines(power_lines_gdf)
    except Exception as buffer_err:
        add_status_message(f"Error buffering power lines: {buffer_err}", "error")
        add_status_message("Proceeding with general wind risk analysis due to power line buffering error.", "warning")
        return risk_areas, result
    
    try:
        # Perform spatial join to find intersections
        wind_risk_areas_proj = wind_risk_areas.to_crs(buffered_lines_gdf.crs)
        joined_areas = gpd.sjoin(wind_risk_areas_proj, buffered_lines_gdf, how="inner", predicate="intersects")

        if joined_areas.empty:
            add_status_message("Found areas with high/moderate wind risk, but none intersected buffered power lines.", "info")
            result["no_intersection_found"] = True
            return wind_risk_areas, result
            
        # Intersection successful, update risk_areas
        risk_areas = joined_areas.drop_duplicates(subset=['geography_polygon', 'forecast_time']).copy()
        result["intersection_performed"] = True
        
        # Check if risk_level column survived the join
        if 'risk_level' not in risk_areas.columns:
            add_status_message("WARNING: risk_level column lost during spatial join. Re-adding it.", "warning")
            risk_areas['risk_level'] = 'moderate'
            risk_areas.loc[risk_areas['wind_speed'] >= high_threshold, 'risk_level'] = 'high'
            
        return risk_areas, result
        
    except Exception as join_err:
        add_status_message(f"Error during spatial join: {join_err}", "error")
        add_status_message("Proceeding with general wind risk analysis due to spatial join error.", "warning")
        return wind_risk_areas, result


def calculate_risk_scores(risk_areas, moderate_threshold):
    """
    Calculate risk scores for each area.
    
    Args:
        risk_areas: GeoDataFrame with risk areas.
        moderate_threshold: Wind speed threshold for moderate risk (m/s).
        
    Returns:
        GeoDataFrame: Input data with risk scores added.
    """
    if risk_areas.empty:
        return risk_areas
        
    # Add a risk score - percentage scale using .loc
    max_possible_wind = risk_areas['wind_speed'].max()
    
    # Ensure denominator is not zero if all winds are at the threshold
    if (max_possible_wind - moderate_threshold) > 0:
        score_series = ((risk_areas['wind_speed'] - moderate_threshold) /
                        (max_possible_wind - moderate_threshold) * 100)
    else:
        score_series = 0  # Assign 0 if max wind is equal to the threshold
        
    risk_areas.loc[:, 'risk_score'] = score_series
    risk_areas.loc[:, 'risk_score'] = risk_areas['risk_score'].clip(0, 100)
    
    return risk_areas


def generate_risk_events(risk_areas, high_threshold, intersection_performed):
    """
    Group data into events by forecast timestamp.
    
    Args:
        risk_areas: GeoDataFrame with risk areas.
        high_threshold: Wind speed threshold for high risk (m/s).
        intersection_performed: Boolean indicating if power line intersection was performed.
        
    Returns:
        tuple: (risk_events, events) where risk_events is a dictionary mapping event IDs to
               GeoDataFrames, and events is a list of summary dictionaries for each event.
    """
    events = []  # List to hold summary dictionaries for each event timestamp
    risk_events = {}  # Dict to hold GeoDataFrames for each event timestamp

    unique_timestamps = sorted(risk_areas['forecast_time'].unique())

    for timestamp in unique_timestamps:
        timestamp_areas = risk_areas[risk_areas['forecast_time'] == timestamp].copy()
        if timestamp_areas.empty:
            continue

        # Check if risk_level exists in the dataset
        if 'risk_level' not in timestamp_areas.columns:
            add_status_message(f"WARNING: risk_level column missing from timestamp areas for {timestamp}", "warning")
            # Add it once more based on thresholds
            timestamp_areas['risk_level'] = 'moderate'
            timestamp_areas.loc[timestamp_areas['wind_speed'] >= high_threshold, 'risk_level'] = 'high'
        
        high_count = len(timestamp_areas[timestamp_areas['risk_level'] == 'high'])
        moderate_count = len(timestamp_areas[timestamp_areas['risk_level'] == 'moderate'])
        
        add_status_message(f"For timestamp {timestamp}: {high_count} high risk, {moderate_count} moderate risk areas", "info")
        
        if high_count + moderate_count == 0:
            continue

        timestamp_str_id = timestamp.strftime('%Y%m%d_%H%M')
        timestamp_str_display = timestamp.strftime('%Y-%m-%d %H:%M UTC')
        event_id = f"wind_event_{timestamp_str_id}"

        # Calculate affected_km ONLY if power line analysis was successfully performed
        affected_km_val = 0
        if intersection_performed:
            # Placeholder logic - needs refinement for accurate km calculation based on intersected lines
            affected_km_val = len(timestamp_areas) * 0.25  # Still a placeholder

        event_summary = {
            "id": event_id,
            "timestamp": timestamp_str_display,
            "high_risk_count": high_count,
            "moderate_risk_count": moderate_count,
            "max_wind_speed": timestamp_areas['wind_speed'].max(),
            "affected_km": affected_km_val,  # Use calculated or 0
            "risk_level": "High" if high_count > 0 else "Moderate"
        }
        events.append(event_summary)
        
        # Ensure timestamp_areas has geometry and risk_level column before storing
        if 'geometry' in timestamp_areas.columns and 'risk_level' in timestamp_areas.columns:
            risk_events[event_id] = timestamp_areas  # Store GDF for this specific timestamp
            add_status_message(f"Added event {event_id} with {len(timestamp_areas)} areas ({high_count} high, {moderate_count} moderate)", "info")
        else:
            add_status_message(f"WARNING: Event {event_id} missing required columns. Not adding to risk_events.", "warning")
            add_status_message(f"Columns: {', '.join(timestamp_areas.columns)}", "info")

    return risk_events, events


def generate_risk_summary(events, power_line_analysis, analyze_power_line_impact):
    """
    Generate overall risk summary.
    
    Args:
        events: List of event summary dictionaries.
        power_line_analysis: Dictionary with power line analysis results.
        analyze_power_line_impact: Boolean flag indicating if power line analysis was requested.
        
    Returns:
        dict: Risk summary with overall statistics and information.
    """
    total_high_risk = sum(event['high_risk_count'] for event in events)
    total_moderate_risk = sum(event['moderate_risk_count'] for event in events)
    total_affected_km = sum(event['affected_km'] for event in events)
    max_wind_overall = max(event['max_wind_speed'] for event in events) if events else 0

    highest_risk_event = max(events, key=lambda x: (x['high_risk_count'], x['max_wind_speed']))
    highest_risk_timestamp_str = highest_risk_event['timestamp']

    # Dynamic summary message generation based on analysis flags
    summary_analysis_desc = "general wind risk areas"  # Default
    analysis_type_flag = "general_wind"
    
    if analyze_power_line_impact:
        if power_line_analysis["intersection_performed"]:
            summary_analysis_desc = "potential power line impacts"
            analysis_type_flag = "power_line_impact"
        elif power_line_analysis["power_lines_loaded"] and power_line_analysis["no_intersection_found"]:
            summary_analysis_desc = "general wind risk areas (none intersected power lines)"
        elif not power_line_analysis["power_lines_loaded"]:
            summary_analysis_desc = "general wind risk areas (power line data unavailable/error)"

    summary_message = f"Found {len(events)} timestamps with {summary_analysis_desc}."

    return {
        "risk_found": True,
        "message": summary_message,
        "event_count": len(events),
        "events": events,
        "high_risk_areas": total_high_risk,
        "moderate_risk_areas": total_moderate_risk,
        "affected_power_lines_km": total_affected_km if power_line_analysis["intersection_performed"] else 0,
        "highest_risk_timestamp": highest_risk_timestamp_str,
        "max_wind_speed": max_wind_overall,
        "analysis_type": analysis_type_flag
    }


def create_empty_risk_summary(message):
    """
    Create an empty risk summary with the given message.
    
    Args:
        message: Error or information message.
        
    Returns:
        dict: Empty risk summary with the message.
    """
    return {
        "risk_found": False,
        "message": message
    } 
