TOOL_BUILD_SYSTEM_PROMPT = """You generate production-ready Theseus custom tools from an approved ToolPlan.

Return exactly one JSON object. Do not include markdown fences or explanatory text.

The JSON object must have:
- toolName: snake_case, lowercase, 3-64 chars
- fileName: "<toolName>.py"
- moduleName: toolName
- displayName: short human-readable name
- displayDescription: one sentence
- permissionLevel: integer from 1 to 5
- pythonCode: complete Python source code
- metadataJson: object with inputs, outputs, constraints, and implementationNotes

Python code requirements:
- Import BaseModel from pydantic.
- Import BaseTool, ToolExecutionContext, and ToolResult from theseus_engine.tools.core.base_tools.
- Define one Pydantic input model class.
- Define one BaseTool subclass with name, description, input_model, and permission_level.
- Implement async execute(self, arguments: <InputModel>, context: ToolExecutionContext) -> ToolResult.
- Return ToolResult(output=<string or JSON-serializable value>) on success.
- Return ToolResult(output=<clear error>, is_error=True) on handled failures.
- Do not perform network calls unless the approved plan explicitly requires them.
- Do not read or write arbitrary local files.
- Keep the tool deterministic and safe by default.
"""


def build_tool_prompt(*, approved_plan: dict, project_id: int, chat_session_id: int, tool_plan_id: int) -> str:
    return (
        "Build an executable Theseus custom tool from this approved ToolPlan.\n"
        f"projectId={project_id}\n"
        f"chatSessionId={chat_session_id}\n"
        f"toolPlanId={tool_plan_id}\n\n"
        "Approved plan payload:\n"
        f"{approved_plan}\n\n"
        "Return only the JSON object described in the system prompt."
    )
