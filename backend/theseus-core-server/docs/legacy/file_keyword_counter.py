import json
import sys
import asyncio
from pydantic import BaseModel, Field
from openharness.tool import OpenHarnessTool, ToolMetadata

class FileKeywordCounterInput(BaseModel):
    """Input model for the FileKeywordCounterTool."""
    file_path: str = Field(..., description="The path to the text file to be analyzed.")

class FileKeywordCounterTool(OpenHarnessTool):
    """
    A tool that counts case-insensitive occurrences of 'error' and 'exception' in a file
    and returns the result as JSON.
    """
    def __init__(self):
        super().__init__(
            ToolMetadata(
                name="file_keyword_counter",
                description="Counts case-insensitive occurrences of 'error' and 'exception' in a file and returns the result as JSON."
            ),
            input_model=FileKeywordCounterInput
        )

    async def _run(self, tool_input: FileKeywordCounterInput) -> str:
        """
        Executes the tool's logic to count keywords in the specified file.
        """
        try:
            with open(tool_input.file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Convert content to lower case for case-insensitive matching
            lower_content = content.lower()
            error_count = lower_content.count('error')
            exception_count = lower_content.count('exception')

            result = {
                'error_count': error_count,
                'exception_count': exception_count
            }
            return json.dumps(result, indent=2)
        except FileNotFoundError:
            return json.dumps({"error": f"File not found: {tool_input.file_path}"}, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Usage: python file_keyword_counter.py <file_path>"}, indent=2))
        sys.exit(1)

    file_path_arg = sys.argv[1]
    tool_instance = FileKeywordCounterTool()
    input_data = FileKeywordCounterInput(file_path=file_path_arg)

    # The _run method is async, so we need to run it within an asyncio event loop.
    result_json = asyncio.run(tool_instance._run(input_data))
    print(result_json)
