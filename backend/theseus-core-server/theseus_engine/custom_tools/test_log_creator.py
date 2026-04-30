
from openharness.tools.base import BaseTool, ToolResult, ToolExecutionContext
from pydantic import BaseModel, Field
import os

class TestLogCreatorInput(BaseModel):
    """Input model for the TestLogCreatorTool."""
    file_path: str = Field(default="test_log.txt", description="The path for the test log file.")
    content: str = Field(
        default="""
        INFO: Application starting...
        DEBUG: Configuration loaded.
        WARNING: Disk space is running low.
        ERROR: Failed to connect to database.
        INFO: Retrying connection...
        Error: Another error occurred.
        EXCEPTION: NullPointerException caught.
        Exception: A generic exception was thrown.
        info: All systems running.
        """,
        description="The content to write to the test log file."
    )

class TestLogCreatorTool(BaseTool):
    """
    A tool to create a test log file with specific content.
    """
    name = "test_log_creator"
    description = "Creates a test log file for demonstration purposes."
    input_model = TestLogCreatorInput
    permission_level = 1
    example_queries = [
        "테스트 로그 파일 만들어줘", "샘플 로그 생성해줘",
        "테스트용 로그 파일",
        "create test log", "generate sample log file",
    ]

    async def execute(self, arguments: TestLogCreatorInput, context: ToolExecutionContext) -> ToolResult:
        try:
            with open(arguments.file_path, 'w', encoding='utf-8') as f:
                f.write(arguments.content)
            
            absolute_path = os.path.abspath(arguments.file_path)
            return ToolResult(output=f"Successfully created test log file at '{absolute_path}'")
        except Exception as e:
            return ToolResult(output=f"Failed to create test log file: {e}", is_error=True)

