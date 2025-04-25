"""Base handler module that defines the interface for all action handlers"""
from typing import List, Dict, Any, Callable, Optional
import folium

# Type definitions for better clarity
ActionDict = Dict[str, Any]
BoundsList = List[List[float]]
HandlerFunction = Callable[[ActionDict, folium.Map], Optional[BoundsList]]

def create_handler(handler_func: HandlerFunction) -> HandlerFunction:
    """
    Decorator to standardize error handling across all handlers
    
    Args:
        handler_func: The handler function to decorate
        
    Returns:
        Decorated handler function with standardized error handling
    """
    def wrapper(action: ActionDict, m: folium.Map) -> Optional[BoundsList]:
        try:
            return handler_func(action, m)
        except Exception as e:
            import streamlit as st
            st.error(f"Error in {handler_func.__name__}: {str(e)}")
            return []
    
    return wrapper 
