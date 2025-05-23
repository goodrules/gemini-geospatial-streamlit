"""
Risk analyzer module for wind risk and power line impact analysis.

This is a facade module that imports and re-exports the functionality 
from the refactored risk_analyzer package.
"""

# Re-export the public API
from services.risk_analyzer.core import analyze_wind_risk, handle_analyze_wind_risk 
