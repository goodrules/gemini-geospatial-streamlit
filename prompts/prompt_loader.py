"""
Prompt loader utility to assemble Jinja2 templates for the Gemini model.
"""

import os
import json
import logging
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_prompt_template(context: dict, debug: bool = False) -> str:
    """
    Load and assemble the prompt template, rendering it with the provided context variables.
    
    Args:
        context: A dictionary of context variables to render the template with, such as
                dates for the forecast.
        debug: If True, log the template source and rendered output for debugging.
                
    Returns:
        str: The fully assembled and rendered prompt template.
    """
    # Get the path to the prompts directory
    prompts_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    
    if debug:
        logger.info(f"Loading templates from: {prompts_dir}")
    
    # Load action examples from JSON file if not already in context
    if "action_examples" not in context:
        action_examples_path = prompts_dir / "action_examples.json"
        try:
            if action_examples_path.exists():
                with open(action_examples_path, "r") as f:
                    # The JSON file has parsing issues, so we're loading it as a string
                    # and adding it directly to the context
                    action_examples = f.read().strip()
                    if debug:
                        logger.info(f"Loaded action_examples.json ({len(action_examples)} chars)")
                    context["action_examples"] = action_examples
            else:
                logger.warning(f"Action examples file not found: {action_examples_path}")
        except Exception as e:
            logger.warning(f"Error loading action_examples.json: {e}")
            # Provide a fallback empty array if loading fails
            context["action_examples"] = "[]"
    
    # Set up the Jinja2 environment
    env = Environment(
        loader=FileSystemLoader(prompts_dir),
        trim_blocks=True,       # Remove first newline after a block
        lstrip_blocks=True      # Strip tabs and spaces from the beginning of a line to the start of a block
    )
    
    # Load the main template
    template = env.get_template('main_prompt.j2')
    
    if debug:
        # Log the template source for debugging (without rendering)
        template_source = env.loader.get_source(env, 'main_prompt.j2')[0]
        logger.info(f"Template source (first 100 chars): {template_source[:100]}...")
        logger.info(f"Context keys: {list(context.keys())}")
    
    # Render the template with the provided context
    rendered_template = template.render(**context)
    
    if debug:
        logger.info(f"Rendered template length: {len(rendered_template)} chars")
        logger.info(f"Rendered template (first 100 chars): {rendered_template[:100]}...")
    
    return rendered_template 
