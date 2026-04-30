
from openharness.tools.base import BaseTool, ToolResult, ToolExecutionContext
from pydantic import BaseModel, Field
import os

class DirectoryCreatorInput(BaseModel):
    """Input model for the DirectoryCreatorTool."""
    directory_path: str = Field(description="The path of the directory to create.")

class DirectoryCreatorTool(BaseTool):
    """
    A tool to create a directory if it does not exist.
    """
    name = "directory_creator"
    description = "Creates a directory at the specified path."
    input_model = DirectoryCreatorInput
    permission_level = 1
    example_queries = [
        "폴더 만들어줘", "디렉토리 생성해줘",
        "새 폴더 생성", "경로 만들어줘",
        "create directory", "make folder",
    ]

    async def execute(self, arguments: DirectoryCreatorInput, context: ToolExecutionContext) -> ToolResult:
        try:
            if os.path.exists(arguments.directory_path):
                return ToolResult(output=f"Directory '{arguments.directory_path}' already exists.")
            
            os.makedirs(arguments.directory_path)
            return ToolResult(output=f"Successfully created directory '{arguments.directory_path}'.")
        except Exception as e:
            return ToolResult(output=f"Failed to create directory: {e}", is_error=True)

