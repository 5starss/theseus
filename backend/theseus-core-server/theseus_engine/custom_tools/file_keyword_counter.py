
import os
import json
from openharness.tools.base import BaseTool, ToolResult, ToolExecutionContext
from pydantic import BaseModel, Field

class FileKeywordCounterInput(BaseModel):
    """Input model for the FileKeywordCounterTool."""
    file_path: str = Field(description="The path to the text file to be analyzed.")

class FileKeywordCounterTool(BaseTool):
    """
    A tool that counts case-insensitive occurrences of 'error' and 'exception' in a file.
    """
    name = "file_keyword_counter"
    description = "Counts case-insensitive occurrences of 'error' and 'exception' in a file and returns the result as JSON."
    input_model = FileKeywordCounterInput
    permission_level = 1

    async def execute(self, arguments: FileKeywordCounterInput, context: ToolExecutionContext) -> ToolResult:
        """
        Reads the specified file, counts the keywords, and returns results as a JSON string.
        """
        try:
            # Step 2: File Reading and Exception Handling
            with open(arguments.file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Step 3: Keyword Counting and Result Formatting
            lower_content = content.lower()
            
            error_count = lower_content.count('error')
            exception_count = lower_content.count('exception')
            
            total_count = error_count + exception_count
            
            result = {
                "file_path": arguments.file_path,
                "error_count": error_count,
                "exception_count": exception_count,
                "total_count": total_count
            }
            
            return ToolResult(output=json.dumps(result, indent=2))

        except FileNotFoundError:
            return ToolResult(output=f"Error: File not found at '{arguments.file_path}'", is_error=True)
        except PermissionError:
            return ToolResult(output=f"Error: Permission denied to read the file at '{arguments.file_path}'", is_error=True)
        except Exception as e:
            return ToolResult(output=f"An unexpected error occurred: {e}", is_error=True)

