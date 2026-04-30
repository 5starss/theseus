
import json
from openharness.tools.base import BaseTool, ToolResult, ToolExecutionContext
from pydantic import BaseModel, Field

class JsonToMarkdownInput(BaseModel):
    """Input model for the JsonToMarkdownTableTool."""
    json_data: str = Field(description="A JSON string representing a list of objects.")

class JsonToMarkdownTableTool(BaseTool):
    """
    A tool to convert a JSON string, which is a list of objects, into a Markdown table.
    The keys of the first object in the list will be used as table headers.
    """
    name = "json_to_markdown_table"
    description = "Converts a JSON string (list of objects) into a Markdown table."
    input_model = JsonToMarkdownInput
    permission_level = 1
    example_queries = [
        "JSON을 마크다운 테이블로 변환해줘", "JSON 표로 만들어줘",
        "데이터 테이블 형식으로 보여줘",
        "convert JSON to table", "JSON to markdown",
    ]

    async def execute(self, arguments: JsonToMarkdownInput, context: ToolExecutionContext) -> ToolResult:
        """
        Parses the JSON string, validates the format, and generates a Markdown table.
        """
        try:
            # Step 2: JSON Parsing and Data Validation
            data = json.loads(arguments.json_data)

            if not isinstance(data, list):
                raise ValueError("JSON data must be a list of objects.")
            
            if not data:
                return ToolResult(output="Input JSON array is empty. Cannot generate a table.")

            if not all(isinstance(item, dict) for item in data):
                raise ValueError("All items in the JSON list must be objects (dictionaries).")

            # Step 3: Markdown Table Generation Logic
            # Extract headers from the keys of the first object
            headers = list(data[0].keys())
            
            # Create header and separator rows
            header_row = "| " + " | ".join(headers) + " |"
            separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"

            # Create data rows
            data_rows = []
            for item in data:
                # Use .get() to handle missing keys in some objects, defaulting to an empty string
                row_values = [str(item.get(header, '')) for header in headers]
                data_rows.append("| " + " | ".join(row_values) + " |")

            # Combine all parts into the final table string
            markdown_table = "\\n".join([header_row, separator_row] + data_rows)
            
            return ToolResult(output=markdown_table)

        except json.JSONDecodeError:
            return ToolResult(output="Invalid JSON format provided.", is_error=True)
        except ValueError as ve:
            return ToolResult(output=f"Data validation error: {ve}", is_error=True)
        except Exception as e:
            return ToolResult(output=f"An unexpected error occurred: {e}", is_error=True)

