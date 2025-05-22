"""
Core risk analysis functionality for wind and power line risk assessment.

This module contains the main functions for risk analysis including the public API
functions analyze_wind_risk and handle_analyze_wind_risk.
"""

import streamlit as st
import pandas as pd
import traceback
import geopandas as gpd
from shapely.wkt import loads as wkt_loads
import folium

from services.risk_analyzer.validation import validate_weather_data
from services.risk_analyzer.processing import (
    filter_by_risk_thresholds,
    process_power_line_impact,
    calculate_risk_scores,
    generate_risk_events,
    generate_risk_summary,
    create_empty_risk_summary
)
from services.risk_analyzer.data_loading import (
    extract_risk_analysis_params,
    load_weather_data,
    process_weather_timestamps,
    find_and_add_region_to_map,
    filter_weather_by_region,
    load_and_filter_power_lines
)
from services.risk_analyzer.visualization import display_risk_results

from utils.streamlit_utils import add_status_message


def analyze_wind_risk(weather_gdf, power_lines_gdf, high_threshold=15.0, moderate_threshold=9.0, analyze_power_line_impact=False):
    """
    Analyze wind risk, optionally intersecting with power line data.

    Args:
        weather_gdf: GeoDataFrame with weather forecast data (already filtered for time period).
        power_lines_gdf: GeoDataFrame with power line geometries (used only if analyze_power_line_impact is True).
        high_threshold: High risk wind speed threshold in m/s (default: 15.0 m/s).
        moderate_threshold: Moderate risk wind speed threshold in m/s (default: 9.0 m/s).
        analyze_power_line_impact (bool): If True, perform intersection with power lines.
                                          If False, analyze general wind risk areas.

    Returns:
        risk_events: Dictionary mapping timestamp-based event IDs (e.g., wind_event_YYYYMMDD_HHMM)
                     to GeoDataFrames of risk areas (either general or intersecting power lines).
        summary: Dictionary with overall risk summary information across all timestamps, including analysis_type.
    """
    try:
        # Validate input data
        validation_result = validate_weather_data(weather_gdf)
        if not validation_result["is_valid"]:
            return {}, create_empty_risk_summary(validation_result["message"])

        # Filter by risk thresholds
        wind_risk_areas_initial = filter_by_risk_thresholds(weather_gdf, moderate_threshold, high_threshold)
        
        if wind_risk_areas_initial.empty:
            return {}, create_empty_risk_summary(
                f"No areas with wind speeds over {moderate_threshold} m/s found in the analyzed forecast period."
            )

        # Process power line impact if requested
        risk_areas, power_line_analysis_result = process_power_line_impact(
            wind_risk_areas_initial, power_lines_gdf, analyze_power_line_impact, moderate_threshold, high_threshold
        )

        # Handle case where risk_areas is empty
        if risk_areas.empty:
            summary_msg = f"No areas with wind speeds over {moderate_threshold} m/s found."
            if analyze_power_line_impact and power_line_analysis_result["power_lines_loaded"] and power_line_analysis_result["no_intersection_found"]:
                summary_msg = "Found wind risk areas, but none intersected buffered power lines."
            elif analyze_power_line_impact and not power_line_analysis_result["power_lines_loaded"]:
                summary_msg += " (Power line data unavailable for intersection)."
            return {}, create_empty_risk_summary(summary_msg)

        # Calculate risk metrics
        risk_areas = calculate_risk_scores(risk_areas, moderate_threshold)

        # Generate risk events by timestamp
        risk_events, events_list = generate_risk_events(
            risk_areas, high_threshold, power_line_analysis_result["intersection_performed"]
        )

        # Generate summary
        if not events_list:
            summary_msg = "No significant wind risk events found after processing."
            return {}, create_empty_risk_summary(summary_msg)
            
        summary = generate_risk_summary(
            events_list, power_line_analysis_result, analyze_power_line_impact
        )

        return risk_events, summary

    except Exception as e:
        st.error(f"Error analyzing wind risk: {str(e)}")
        traceback.print_exc()
        return {}, create_empty_risk_summary(f"Error analyzing wind risk: {str(e)}")


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

    try:
        # Extract and validate parameters
        params = extract_risk_analysis_params(action)
        if not params["valid"]:
            return bounds
        
        # Load weather data
        weather_df = load_weather_data(params["forecast_days"])
        if weather_df is None or weather_df.empty:
            return bounds
        
        # Find and add region to the map
        region_result = find_and_add_region_to_map(params["region_name"], m)
        if not region_result["success"]:
            return bounds
            
        bounds.append(region_result["bounds"])
        region_polygon = region_result["polygon"]
        
        # Filter weather data by region
        weather_gdf = filter_weather_by_region(weather_df, region_polygon)
        if weather_gdf.empty:
            add_status_message(f"No weather data points found within {params['region_name']}.", "warning")
            return bounds
        
        # Load power line data if needed
        power_lines_gdf = None
        saved_power_lines_gdf = None  # For later visualization
        
        if params["analyze_power_lines"]:
            add_status_message(f"Loading power line data for {params['region_name']}...", "info")
            power_lines_gdf = load_and_filter_power_lines(region_polygon)
            
            if power_lines_gdf is not None and not power_lines_gdf.empty:
                saved_power_lines_gdf = power_lines_gdf.copy()
                add_status_message(f"Final power line count for risk analysis in {params['region_name']}: {len(power_lines_gdf)}", "info")
            else:
                add_status_message(f"No power lines found within {params['region_name']}.", "warning")
        
        # Analyze wind risk
        analysis_desc = "power line impact" if params["analyze_power_lines"] else "general wind risk"
        add_status_message(f"Analyzing {analysis_desc} for {params['region_name']} over the next {params['forecast_days']} day(s) (high >= {params['high_threshold']} m/s, moderate >= {params['moderate_threshold']} m/s)...", "info")

        risk_events, risk_summary = analyze_wind_risk(
            weather_gdf,
            power_lines_gdf, 
            params["high_threshold"],
            params["moderate_threshold"],
            analyze_power_line_impact=params["analyze_power_lines"]
        )
        
        # Display results
        if risk_summary.get("risk_found"):
            display_risk_results(risk_summary, risk_events, m, saved_power_lines_gdf, bounds)
        else:
            add_status_message(risk_summary.get("message", "No significant wind risk found."), "info")
            # Still display power lines even if no risk areas are found
            if saved_power_lines_gdf is not None and not saved_power_lines_gdf.empty and params["analyze_power_lines"]:
                from services.risk_analyzer.visualization import add_power_lines_to_map
                add_status_message("Displaying all power lines in region despite no risk areas found.", "info")
                # Add power lines directly to the map
                add_power_lines_to_map(saved_power_lines_gdf, None, None, "all_timestamps", {}, m)
        
    except Exception as e:
        add_status_message(f"Error handling wind risk analysis: {str(e)}", "error")
        traceback.print_exc()
        
    return bounds 
