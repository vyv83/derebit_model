"""
Base Chart Builder
==================
Abstract base class for all chart builders.
Provides common functionality and interface for chart rendering.
"""

from abc import ABC, abstractmethod
from dash import html
from config.theme import style_card, CUSTOM_CSS


class BaseChartBuilder(ABC):
    """
    Abstract base class for chart builders.
    All chart builders should inherit from this class.
    """
    
    def __init__(self):
        """Initialize base chart builder."""
        pass
    
    @abstractmethod
    def render(self, *args, **kwargs):
        """
        Render the chart.
        Must be implemented by subclasses.
        
        Returns:
            html.Div component with the chart
        """
        raise NotImplementedError("Subclasses must implement render()")
    
    def _create_error_message(self, title, message, details=None):
        """
        Create a standardized error message component.
        
        Args:
            title: Error title
            message: Main error message
            details: Optional list of detail strings
            
        Returns:
            html.Div with formatted error message
        """
        children = [
            html.H5(title, style={"color": CUSTOM_CSS["text_primary"]}),
            html.P(message, style={"color": CUSTOM_CSS["text_secondary"], "marginTop": "20px"})
        ]
        
        if details:
            children.append(html.P("This may occur if:", style={"marginTop": "20px"}))
            children.append(html.Ul([
                html.Li(detail) for detail in details
            ], style={"color": CUSTOM_CSS["text_secondary"]}))
        
        return html.Div(children, style={**style_card, "padding": "40px", "textAlign": "center"})
    
    def _create_placeholder(self, title, instructions):
        """
        Create a placeholder message for charts awaiting data.
        
        Args:
            title: Placeholder title
            instructions: List of instruction strings
            
        Returns:
            html.Div with formatted placeholder
        """
        return html.Div([
            html.H5(title, style={"color": CUSTOM_CSS["text_primary"]}),
            html.P("The chart will show:", style={"marginTop": "20px", "fontWeight": "bold"}),
            html.Ul([
                html.Li(instruction) for instruction in instructions
            ], style={"color": CUSTOM_CSS["text_secondary"]})
        ], style={**style_card, "padding": "40px", "textAlign": "center"})
