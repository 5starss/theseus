"""Theseus Interactive Tools: Tools for human-in-the-loop interaction."""

import logging
from pydantic import BaseModel, Field
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

log = logging.getLogger(__name__)

class AskUserInput(BaseModel):
    """Input for asking the user a question."""
    question: str = Field(description="The question or clarification needed from the user.")

class AskUserTool(BaseTool):
    """Asks the interactive user a question and waits for their response."""
    name = "ask_user"
    description = "Ask the human user for more information, clarification, or a decision. Use this when you are stuck or need missing data."
    input_model = AskUserInput
    permission_level = 1

    async def execute(self, arguments: AskUserInput, context: ToolExecutionContext) -> ToolResult:
        # Get the prompt function from metadata (injected by TUI/CLI)
        prompt_func = context.metadata.get("permission_prompt") or context.metadata.get("ask_user_prompt")
        
        if not prompt_func or not callable(prompt_func):
            return ToolResult(
                output="Interactive prompt is not available in the current environment.",
                is_error=True
            )
            
        try:
            # We use the same permission_prompt mechanism but for a general question
            response = await prompt_func(f"\n[AI Question]: {arguments.question}\nYour Answer: ")
            answer = str(response).strip()
            
            if not answer:
                return ToolResult(output="(User provided an empty response)")
                
            return ToolResult(output=f"User's response: {answer}")
        except Exception as e:
            log.error("AskUserTool failed: %s", e)
            return ToolResult(output=f"Failed to get user response: {e}", is_error=True)
