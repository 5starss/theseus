
from openharness.tools.base import BaseTool, ToolResult, ToolExecutionContext
from pydantic import BaseModel, Field
import os

class ConfigWriterInput(BaseModel):
    key: str = Field(description="The configuration key to write.")
    value: str = Field(description="The configuration value to write.")
    file_path: str = Field(default=".env", description="The path to the configuration file.")

class ConfigWriterTool(BaseTool):
    """
    A tool to write a key-value pair to a configuration file (e.g., .env).
    """
    name = "config_writer"
    description = "Writes a key-value pair to a specified configuration file."
    input_model = ConfigWriterInput
    permission_level = 1
    example_queries = [
        ".env 파일에 값 저장해줘", "환경변수 설정해줘",
        "설정값 변경해줘", "API 키 저장해줘",
        "write config value", "set env variable",
    ]

    async def execute(self, arguments: ConfigWriterInput, context: ToolExecutionContext) -> ToolResult:
        try:
            # Read existing lines
            if os.path.exists(arguments.file_path):
                with open(arguments.file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            else:
                lines = []

            # Update or append the key-value pair
            key_found = False
            new_line = f"{arguments.key}='{arguments.value}'\\n"
            for i, line in enumerate(lines):
                if line.strip().startswith(f"{arguments.key}="):
                    lines[i] = new_line
                    key_found = True
                    break
            
            if not key_found:
                lines.append(new_line)

            # Write the updated lines back to the file
            with open(arguments.file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
            return ToolResult(output=f"Successfully wrote '{arguments.key}' to '{arguments.file_path}'.")
        except Exception as e:
            return ToolResult(output=f"An error occurred: {e}", is_error=True)

