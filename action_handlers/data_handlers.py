"""Handlers for data-related map actions"""
import folium
import pandas as pd
from action_handlers.base_handler import create_handler, ActionDict, BoundsList
from data.geospatial_data import  (get_us_power_lines)
from utils.streamlit_utils import add_status_message

@create_handler
def handle_show_local_dataset(action: ActionDict, m: folium.Map) -> BoundsList:
    """
    Handle the show_local_dataset action
    
    Args:
        action: The action dictionary with parameters
        m: The folium map object
        
    Returns:
        List of bounds to include in the overall map fitting
    """
    bounds = []
    
    dataset_name = action.get("dataset_name", "").lower()
    
    # Determine which dataset to load based on the dataset_name
    gdf = None
    if dataset_name == "power_lines" or dataset_name == "pa_power_lines":
        # Get region information from action parameters if available
        region_name = action.get("region", None)
        
        # SIMPLIFICATION: If no region is specified, don't show any power lines
        if not region_name:
            add_status_message("No region specified for power lines. Please specify a region name.", "warning")
            return bounds
            
        # Get the region geometry to filter power lines
        from utils.geo_utils import find_region_by_name
        from data.geospatial_data import get_us_states, get_us_counties
        
        region_polygon = None
        region_found = False
        
        # First try to find the region in states dataset
        states_gdf = get_us_states()
        region_match = find_region_by_name(states_gdf, region_name)
        
        if region_match is not None and not region_match.empty:
            region_polygon = region_match.geometry.iloc[0]
            region_found = True
            add_status_message(f"Found region in states data: {region_match['state_name'].iloc[0]}", "info")
        else:
            # Try counties dataset
            counties_gdf = get_us_counties()
            region_match = find_region_by_name(counties_gdf, region_name)
            
            if region_match is not None and not region_match.empty:
                region_polygon = region_match.geometry.iloc[0]
                region_found = True
                # Include state information if available
                if 'state_name' in region_match.columns:
                    add_status_message(f"Found region in counties data: {region_match['county_name'].iloc[0]}, {region_match['state_name'].iloc[0]}", "info")
                elif 'state' in region_match.columns:
                    add_status_message(f"Found region in counties data: {region_match['county_name'].iloc[0]}, {region_match['state'].iloc[0]}", "info")
                else:
                    add_status_message(f"Found region in counties data: {region_match['county_name'].iloc[0]}", "info")
        
        # If we couldn't find the region, don't show power lines
        if not region_found or region_polygon is None:
            add_status_message(f"Could not identify region '{region_name}'. No power lines will be displayed.", "warning")
            return bounds
        
        # Load power line data and immediately filter it
        add_status_message(f"Loading power line data and filtering for {region_name}...", "info")
        gdf = get_us_power_lines(use_geojson=True)
        
        if gdf is None or gdf.empty:
            add_status_message("Failed to load power line data.", "error")
            return bounds
        
        # Process the region filtering
        
        # Create a buffer around the region that follows its shape
        # Use a small buffer (~2km) to include points just outside the region boundary
        buffered_region = region_polygon.buffer(0.02)  # ~2km buffer in degrees
        
        # First get a rough subset using the bounding box for performance
        # (much faster initial filter before the more precise spatial operation)
        minx, miny, maxx, maxy = buffered_region.bounds
        rough_filtered = gdf[(gdf.geometry.x >= minx) &
                             (gdf.geometry.y >= miny) &
                             (gdf.geometry.x <= maxx) &
                             (gdf.geometry.y <= maxy)].copy()

        # Then do precise filtering using the actual buffered shape
        # This is more accurate but slower, so we only do it on the subset
        filtered_gdf = rough_filtered[rough_filtered.intersects(buffered_region)].copy()
        
        # Use the filtered data
        gdf = filtered_gdf
        add_status_message(f"Final power line count for {region_name}: {len(gdf)}", "info")
        
        if gdf.empty:
            add_status_message(f"No power lines found within {region_name}.", "warning")
            return bounds
        
        # For display configuration
        layer_name = f"Power Lines ({region_name})"
    else:
        # st.warning(f"Unknown local dataset: {dataset_name}")
        return bounds
            
    if gdf is None or gdf.empty:
        add_status_message(f"No data available for {dataset_name}.", "warning")
        return bounds
        
    # Convert timestamps to strings to avoid serialization issues
    for col in gdf.columns:
        if pd.api.types.is_datetime64_any_dtype(gdf[col]):
            gdf[col] = gdf[col].astype(str)
    
    # We'll use custom tooltips per feature for better formatting
    
    # Convert points to lines for power line data
    if dataset_name in ["power_lines", "pa_power_lines"] and all(geom.geom_type == 'Point' for geom in gdf.geometry):
        from utils.geo_utils import convert_power_line_points_to_lines
        lines_gdf = convert_power_line_points_to_lines(gdf)
        if lines_gdf is not None and not lines_gdf.empty:
            gdf = lines_gdf
            add_status_message(f"Converted {len(gdf)} power lines for visualization", "info")

    # Detect if we're using points or lines for different rendering
    is_point_data = all(geom.geom_type == 'Point' for geom in gdf.geometry)

    if is_point_data:
        # For point data, add individual dots with no markers
        
        # Create a feature group for the dots
        dot_group = folium.FeatureGroup(name=layer_name)
        
        # Add the points as dots (circles) directly
        for _, row in gdf.iterrows():
            # Extract coordinates from the Point geometry
            coords = (row.geometry.y, row.geometry.x)
            
            # Create enhanced tooltip with additional information
            point_tooltip = f"""
            <div style='min-width: 200px;'>
                <b>Voltage:</b> {row.get('VOLTAGE', 'N/A')} kV<br>
                <b>Type:</b> {row.get('TYPE', 'N/A')}<br>
                <b>Owner:</b> {row.get('OWNER', 'N/A')}<br>
                <b>Description:</b> {row.get('NAICS_DESC', 'N/A')}
            </div>
            """
            
            # Get voltage for color determination
            voltage = row.get('VOLTAGE', 0)
            
            # Create color spectrum based on voltage
            # Low voltage (0-100kV): Yellow
            # Medium voltage (100-300kV): Orange
            # High voltage (300-500kV): Red
            # Very high voltage (500+ kV): Dark red
            if voltage < 100:
                line_color = '#FFD700'  # Yellow for low voltage
            elif voltage < 300:
                line_color = '#FFA500'  # Orange for medium voltage
            elif voltage < 500:
                line_color = '#FF0000'  # Red for high voltage
            else:
                line_color = '#8B0000'  # DarkRed for very high voltage
            
            # Always use voltage-based colors for power lines
            display_color = line_color
            
            # Create a circle with voltage-based colors
            folium.Circle(
                location=coords,
                radius=400,  # Adjusted to 400 meters
                color=display_color,  # Voltage-based color
                weight=2,  # Line weight
                fill=True,
                fill_color=display_color,  # Match fill color to outline
                fill_opacity=0.7,  # Partial opacity as requested
                tooltip=point_tooltip,  # Use tooltip only, no popup to avoid markers
            ).add_to(dot_group)
        
        # Add the feature group to the map
        dot_group.add_to(m)
        
        # Use consistent voltage legend implementation from visualization.py
        from services.risk_analyzer.visualization import create_voltage_legend
        create_voltage_legend(m)
    else:
        # For line data (power lines converted from points)

        # Create a feature group for the lines
        line_group = folium.FeatureGroup(name=layer_name)

        # Add each line with voltage-based coloring
        for _, row in gdf.iterrows():
            # Get voltage for color determination
            voltage = row.get('VOLTAGE', 0)

            # Create color spectrum based on voltage
            # Low voltage (0-100kV): Yellow
            # Medium voltage (100-300kV): Orange
            # High voltage (300-500kV): Red
            # Very high voltage (500+ kV): Dark red
            if voltage < 100:
                line_color = '#FFD700'  # Yellow for low voltage
            elif voltage < 300:
                line_color = '#FFA500'  # Orange for medium voltage
            elif voltage < 500:
                line_color = '#FF0000'  # Red for high voltage
            else:
                line_color = '#8B0000'  # DarkRed for very high voltage

            # Create enhanced tooltip with additional information
            line_tooltip = f"""
            <div style='min-width: 200px;'>
                <b>Line ID:</b> {row.get('ID', 'N/A')}<br>
                <b>Voltage:</b> {row.get('VOLTAGE', 'N/A')} kV<br>
                <b>Type:</b> {row.get('TYPE', 'N/A')}<br>
                <b>Status:</b> {row.get('STATUS', 'N/A')}<br>
                <b>Owner:</b> {row.get('OWNER', 'N/A')}<br>
                <b>Substations:</b> {row.get('SUB_1', 'N/A')} to {row.get('SUB_2', 'N/A')}
            </div>
            """

            # Use PolyLine for better line rendering
            line_coords = [[y, x] for x, y in row.geometry.coords]

            # Add the line to the map with voltage-based color
            folium.PolyLine(
                locations=line_coords,
                color=line_color,
                weight=4,
                opacity=0.9,
                tooltip=line_tooltip
            ).add_to(line_group)

        # Add the feature group to the map
        line_group.add_to(m)

        # Add voltage legend
        from services.risk_analyzer.visualization import create_voltage_legend
        create_voltage_legend(m)
    
    # Add dataset bounds to bounds list
    dataset_bounds = gdf.total_bounds
    bounds.append([dataset_bounds[1], dataset_bounds[0]])  # SW corner
    bounds.append([dataset_bounds[3], dataset_bounds[2]])  # NE corner
    
    return bounds 
