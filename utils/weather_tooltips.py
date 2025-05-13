import pandas as pd
from branca.colormap import LinearColormap

def create_weather_tooltip(properties, parameter=None):
    """
    Create HTML tooltip for weather data with improved formatting and contextual information
    
    Args:
        properties: Dictionary of properties from the GeoJSON feature
        parameter: Optional specific parameter to highlight (temperature, precipitation, wind_speed)
        
    Returns:
        HTML string for the tooltip
    """
    # Convert temperature from Kelvin to both Fahrenheit and Celsius
    temp_f = None
    temp_c = None
    if "temperature" in properties:
        temp_k = float(properties["temperature"])
        temp_c = temp_k - 273.15
        temp_f = temp_c * 9/5 + 32
    
    # Format precipitation as mm and add context
    precip = None
    precip_desc = "None"
    if "precipitation" in properties:
        precip = float(properties["precipitation"]) * 1000  # Convert to mm
        # Add precipitation description
        if precip < 0.1:
            precip_desc = "None"
        elif precip < 2.5:
            precip_desc = "Very Light"
        elif precip < 7.5:
            precip_desc = "Light"
        elif precip < 15:
            precip_desc = "Moderate"
        elif precip < 30:
            precip_desc = "Heavy"
        else:
            precip_desc = "Very Heavy"
    
    # Format wind speed (m/s and mph) and add context
    wind = None
    wind_mph = None
    wind_desc = ""
    if "wind_speed" in properties:
        wind = float(properties["wind_speed"])
        wind_mph = wind * 2.237  # Convert to mph
        # Add wind description based on Beaufort scale (simplified)
        if wind < 0.5:
            wind_desc = "Calm"
        elif wind < 1.5:
            wind_desc = "Light Air"
        elif wind < 3.3:
            wind_desc = "Light Breeze"
        elif wind < 5.5:
            wind_desc = "Gentle Breeze"
        elif wind < 7.9:
            wind_desc = "Moderate Breeze"
        elif wind < 10.7:
            wind_desc = "Fresh Breeze"
        elif wind < 13.8:
            wind_desc = "Strong Breeze"
        elif wind < 17.1:
            wind_desc = "High Wind"
        else:
            wind_desc = "Gale Force"
    
    # Create tooltip with available data
    location_info = ""
    if "location_name" in properties:
        location_info = f"<h5>{properties['location_name']}</h5>"
    
    # Base tooltip HTML
    tooltip_html = f"""
    <div style="min-width: 220px; max-width: 300px; padding: 10px;">
        <h4 style="margin-top: 0; border-bottom: 1px solid #ccc; padding-bottom: 5px;">
            Weather Forecast
        </h4>
        {location_info}
        <p><b>Time (UTC):</b> {pd.to_datetime(properties.get("forecast_time")).strftime('%Y-%m-%d %H:%M') if properties.get("forecast_time") else "N/A"}</p>
    """

    # Add weather data based on what's available
    if temp_f is not None:
        highlight = ' style="background-color: #FFFF99;"' if parameter == "temperature" else ""
        tooltip_html += f'<p{highlight}><b>Temperature:</b> {temp_f:.1f}°F ({temp_c:.1f}°C)</p>'
    
    if precip is not None:
        highlight = ' style="background-color: #FFFF99;"' if parameter == "precipitation" else ""
        tooltip_html += f'<p{highlight}><b>Precipitation:</b> {precip:.2f} mm ({precip_desc})</p>'
    
    if wind is not None:
        highlight = ' style="background-color: #FFFF99;"' if parameter == "wind_speed" else ""
        tooltip_html += f'<p{highlight}><b>Wind Speed:</b> {wind:.1f} m/s ({wind_mph:.1f} mph)<br/><i>{wind_desc}</i></p>'
    
    tooltip_html += """
        <div style="font-size: 0.8em; margin-top: 10px; color: #666;">
            Click for more details
        </div>
    </div>
    """
    
    return tooltip_html

def get_weather_color_scale(parameter, min_val, max_val):
    """
    Define color scales for different weather parameters
    
    Args:
        parameter: The weather parameter to create a color scale for
        min_val: Minimum value in the data for scaling
        max_val: Maximum value in the data for scaling
        
    Returns:
        branca.colormap.LinearColormap object
    """
    if parameter == "temperature":
        # Temperature color scale (Kelvin values)
        # Colors from cool blue to hot red
        return LinearColormap(
            ['#0000ff', '#00ffff', '#00ff00', '#ffff00', '#ff0000'],
            vmin=min_val,  # ~15°F
            vmax=max_val,  # ~55°F
        )
    elif parameter == "precipitation":
        # Precipitation color scale (mm)
        # Colors from white/pale blue (low) to dark blue (high)
        return LinearColormap(
            ['#ffffff', '#c6dbef', '#9ecae1', '#6baed6', '#3182bd', '#08519c'],
            vmin=min_val,
            vmax=max_val,  # Adjust based on actual precipitation values
        )
    elif parameter == "wind_speed":
        # Wind speed color scale (m/s)
        # Colors from white/pale green (low) to dark green (high)
        return LinearColormap(
            ['#ffffff', '#c7e9c0', '#a1d99b', '#74c476', '#31a354', '#006d2c'],
            vmin=min_val,
            vmax=max_val,  # Adjust based on actual wind speed values
        )
    elif parameter == "wind_risk":
        # Wind risk color scale (special scale for risk assessment)
        # Orange-red scale to indicate severity
        return LinearColormap(
            ['#fee8c8', '#fdbb84', '#e34a33'], 
            vmin=0,
            vmax=100,  # Risk percentage 
        )
    else:
        # Default color scale
        return LinearColormap(
            ['#ffffff', '#bbbbbb', '#777777', '#444444', '#000000'],
            vmin=0,
            vmax=100,
        ) 
