# Prompt Templates

This directory contains the modular prompt templates used by the Gemini geospatial assistant.

## Directory Structure

- `main_prompt.j2`: The main Jinja2 template that includes all other template parts
- `intro.txt`: Introduction to the assistant and basic response format
- `action_examples.txt`: Examples of map actions in JSON format
- `action_examples.json`: JSON schema for map actions (reference only)
- `region_types.txt`: Supported region types for highlight_region
- `action_types.txt`: Supported action types with descriptions
- Various domain-specific templates for different features:
  - `flood_zones_notes.txt`
  - `power_lines_notes.txt`
  - `wind_risk_notes.txt`
  - `weather_notes.txt`
  - `weather_examples.txt`
  - `data_notes.txt`

## Using Jinja2 Comments

You can add comments to your templates that will be completely removed during rendering:

```jinja
{# This is a single-line comment #}

{# 
   This is a multi-line comment
   that can span multiple lines
   and will be removed during rendering
#}
```

### Commenting Out Sections

You can temporarily disable sections of your templates without deleting them:

```jinja
{# 
This entire section is commented out and will be ignored
{
    "action_type": "example_action",
    "parameter": "value"
}
#}
```

## Variable Interpolation

Templates support variable interpolation with the `{{variable_name}}` syntax:

```jinja
"forecast_date": "{{today_date}}"
"forecast_timestamp": "{{tomorrow_date}}T12:00:00Z"
```

## Conditional Inclusion of Template Parts

You can conditionally include or exclude template parts based on context variables:

```jinja
{% if include_weather_examples %}
  {% include "weather_examples.txt" %}
{% endif %}

{# With default fallback if variable is not defined #}
{% if include_power_lines_notes is not defined or include_power_lines_notes %}
  {% include "power_lines_notes.txt" %}
{% endif %}
```

This allows you to selectively include template sections based on the use case. For example:

```python
# Include all sections
context = {
    "today_date": "2023-05-10",
    "include_weather_examples": True,
    "include_power_lines_notes": True
}

# Include only specific sections
context = {
    "today_date": "2023-05-10",
    "include_weather_examples": True,
    "include_power_lines_notes": False  # This section will be omitted
}
```

## Adding New Template Parts

1. Create a new text file in this directory
2. Add content using plain text and Jinja2 syntax if needed
3. Include the new file in `main_prompt.j2` using:
   ```jinja
   {% include "your_new_file.txt" %}
   ``` 
