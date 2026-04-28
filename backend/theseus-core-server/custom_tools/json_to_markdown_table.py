
import json
from pydantic import BaseModel, Field
from typing import List, Dict, Any

class JsonToMarkdownInput(BaseModel):
    """Input model for the JsonToMarkdownTableTool."""
    json_data: str = Field(description="A JSON string representing a list of objects.")

def json_to_markdown_table(json_data: str) -> str:
    """
    Converts a JSON string (list of objects) into a Markdown table.

    Args:
        json_data: A JSON string representing a list of objects.

    Returns:
        A string formatted as a Markdown table.

    Raises:
        ValueError: If the JSON is invalid, not a list of objects, or the objects have inconsistent keys.
    """
    try:
        data = json.loads(json_data)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format provided.")

    if not isinstance(data, list):
        raise ValueError("JSON data must be a list of objects.")

    if not data:
        return "The provided JSON array is empty."

    if not all(isinstance(item, dict) for item in data):
        raise ValueError("All items in the JSON list must be objects (dictionaries).")

    # Extract headers from the first object
    headers = list(data[0].keys())

    # Check for key consistency across all objects
    if not all(list(item.keys()) == headers for item in data):
        # This is a simple check. For more complex scenarios,
        # one might want to handle missing/extra keys differently.
        raise ValueError("All objects in the JSON list must have the same set of keys.")

    # Create header and separator lines
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"

    # Create data rows
    rows = []
    for item in data:
        row_values = [str(item.get(header, '')) for header in headers]
        rows.append("| " + " | ".join(row_values) + " |")

    # Combine all parts
    markdown_table = "\n".join([header_line, separator_line] + rows)

    return markdown_table

# Example of how to use the function:
if __name__ == '__main__':
    # Valid JSON
    valid_json_string = '[{"Name": "Alice", "Age": "30", "City": "New York"}, {"Name": "Bob", "Age": "25", "City": "Los Angeles"}]'
    print("--- Valid JSON ---")
    print(json_to_markdown_table(valid_json_string))
    print("\\n")

    # Empty JSON array
    empty_json_string = '[]'
    print("--- Empty JSON Array ---")
    print(json_to_markdown_table(empty_json_string))
    print("\\n")
    
    # Invalid JSON
    invalid_json_string = '{"name": "John", "age": 30'
    print("--- Invalid JSON ---")
    try:
        json_to_markdown_table(invalid_json_string)
    except ValueError as e:
        print(e)
    print("\\n")

    # Inconsistent keys
    inconsistent_json = '[{"Name": "Charlie", "Age": "35"}, {"Name": "David", "City": "Chicago"}]'
    print("--- Inconsistent Keys JSON ---")
    try:
        json_to_markdown_table(inconsistent_json)
    except ValueError as e:
        print(e)

