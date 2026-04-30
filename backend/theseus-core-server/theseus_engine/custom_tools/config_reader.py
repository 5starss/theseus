
from openharness.tools.base import BaseTool, ToolResult, ToolExecutionContext
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

class ConfigReaderInput(BaseModel):
    key: str = Field(description="The configuration key to read.")
    file_path: str = Field(default=".env", description="The path to the configuration file.")

class ConfigReaderTool(BaseTool):
    """
    A tool to read a value from a configuration file (e.g., .env).
    """
    name = "config_reader"
    description = "Reads a value for a given key from a specified configuration file."
    input_model = ConfigReaderInput
    permission_level = 1
    example_queries = [
        ".env 파일에서 값 읽어줘", "환경변수 확인해줘",
        "설정값 조회해줘", "API 키 읽어줘",
        "read config value", "get env variable",
    ]

    async def execute(self, arguments: ConfigReaderInput, context: ToolExecutionContext) -> ToolResult:
        try:
            load_dotenv(dotenv_path=arguments.file_path)
            value = os.getenv(arguments.key)
            if value is None:
                return ToolResult(output=f"Key '{arguments.key}' not found in '{arguments.file_path}'.", is_error=True)
            return ToolResult(output=value)
        except Exception as e:
            return ToolResult(output=f"An error occurred: {e}", is_error=True)

