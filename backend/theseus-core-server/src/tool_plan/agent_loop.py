from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from src.config import settings
from theseus_engine.models.messages import ConversationMessage, ToolResultBlock
from theseus_engine.models.state import AgentMode, PlanPhase, TheseusStateMachine
from theseus_engine.wrappers.llm_clients.api_types import (
    ApiMessageCompleteEvent,
    ApiMessageRequest,
    ApiTextDeltaEvent,
    SupportsStreamingMessages,
)


CheckpointCallback = Callable[[dict], Awaitable[None] | None]
ChunkCallback = Callable[[str], Awaitable[None] | None]


@dataclass
class ToolPlanToolExecutionContext:
    cwd: Path
    metadata: dict[str, Any] = field(default_factory=dict)
    hook_executor: Any | None = None


class EmptyToolRegistry:
    def get(self, name: str):
        return None

    def to_api_schema(self) -> list[dict[str, Any]]:
        return []


@dataclass
class ToolPlanAgentLoopResult:
    final_text: str
    checkpoint: dict


@dataclass
class ToolPlanAgentLoop:
    llm_client: SupportsStreamingMessages
    model_name: str
    tool_registry: Any = field(default_factory=EmptyToolRegistry)
    max_turns: int = field(default_factory=lambda: settings.CORE_TOOL_PLAN_MAX_AGENT_TURNS)
    cwd: Path = field(default_factory=lambda: Path.cwd())

    async def run(
        self,
        *,
        initial_prompt: str,
        system_prompt: str,
        checkpoint: dict | None = None,
        checkpoint_callback: CheckpointCallback | None = None,
        chunk_callback: ChunkCallback | None = None,
    ) -> ToolPlanAgentLoopResult:
        restored_checkpoint = checkpoint if isinstance(checkpoint, dict) else {}
        state_machine = self._restore_state_machine(self._dict_or_none(restored_checkpoint.get("stateMachine")))
        messages = self._restore_messages(self._list_or_empty(restored_checkpoint.get("conversation")))
        tool_trace = self._restore_tool_trace(restored_checkpoint.get("toolTrace"))
        completed_steps = self._restore_completed_steps(restored_checkpoint.get("progress"))

        if not messages:
            messages = [ConversationMessage.from_user_text(initial_prompt)]
            await self._save_checkpoint(
                state_machine,
                messages,
                tool_trace,
                completed_steps=completed_steps,
                checkpoint_callback=checkpoint_callback,
            )

        if self._has_pending_tool_use(messages):
            completed_steps = await self._resume_pending_tool_uses(
                state_machine,
                messages,
                tool_trace,
                completed_steps=completed_steps,
                checkpoint_callback=checkpoint_callback,
            )

        for turn_index in range(completed_steps, self.max_turns):
            final_message = None
            async for llm_event in self.llm_client.stream_message(
                ApiMessageRequest(
                    model=self.model_name,
                    messages=messages,
                    system_prompt=system_prompt,
                    max_tokens=4096,
                    tools=self.tool_registry.to_api_schema(),
                )
            ):
                if isinstance(llm_event, ApiTextDeltaEvent):
                    await self._emit_chunk(chunk_callback, llm_event.text)
                elif isinstance(llm_event, ApiMessageCompleteEvent):
                    final_message = llm_event.message

            if final_message is None:
                raise RuntimeError("ToolPlan agent loop finished without an assistant message")

            messages.append(final_message)
            completed_steps = turn_index + 1
            await self._save_checkpoint(
                state_machine,
                messages,
                tool_trace,
                completed_steps=completed_steps,
                checkpoint_callback=checkpoint_callback,
            )

            if not final_message.tool_uses:
                return ToolPlanAgentLoopResult(
                    final_text=final_message.text,
                    checkpoint=self._checkpoint_payload(state_machine, messages, tool_trace, completed_steps),
                )

            tool_results = []
            for tool_use in final_message.tool_uses:
                trace_item = {
                    "toolUseId": tool_use.id,
                    "toolName": tool_use.name,
                    "toolInput": tool_use.input,
                    "status": "started",
                    "turn": completed_steps,
                }
                tool_trace.append(trace_item)
                await self._save_checkpoint(
                    state_machine,
                    messages,
                    tool_trace,
                    completed_steps=completed_steps,
                    checkpoint_callback=checkpoint_callback,
                )

                result_block = await self._execute_tool(tool_use.name, tool_use.id, tool_use.input)
                trace_item["status"] = "failed" if result_block.is_error else "completed"
                trace_item["toolOutput"] = result_block.content
                tool_results.append(result_block)
                await self._save_checkpoint(
                    state_machine,
                    messages,
                    tool_trace,
                    completed_steps=completed_steps,
                    checkpoint_callback=checkpoint_callback,
                )

            messages.append(ConversationMessage(role="user", content=tool_results))
            await self._save_checkpoint(
                state_machine,
                messages,
                tool_trace,
                completed_steps=completed_steps,
                checkpoint_callback=checkpoint_callback,
            )

        raise RuntimeError(f"ToolPlan agent loop exceeded max turns: {self.max_turns}")

    def _has_pending_tool_use(self, messages: list[ConversationMessage]) -> bool:
        if not messages:
            return False
        last_message = messages[-1]
        return last_message.role == "assistant" and bool(last_message.tool_uses)

    async def _resume_pending_tool_uses(
        self,
        state_machine: TheseusStateMachine,
        messages: list[ConversationMessage],
        tool_trace: list[dict],
        *,
        completed_steps: int,
        checkpoint_callback: CheckpointCallback | None,
    ) -> int:
        pending_message = messages[-1]
        tool_results = []
        for tool_use in pending_message.tool_uses:
            trace_item = self._find_or_create_trace_item(
                tool_trace,
                tool_use_id=tool_use.id,
                tool_name=tool_use.name,
                tool_input=tool_use.input,
                turn=completed_steps,
            )
            trace_item["status"] = "resuming"
            await self._save_checkpoint(
                state_machine,
                messages,
                tool_trace,
                completed_steps=completed_steps,
                checkpoint_callback=checkpoint_callback,
            )
            result_block = await self._execute_tool(tool_use.name, tool_use.id, tool_use.input)
            trace_item["status"] = "failed" if result_block.is_error else "completed"
            trace_item["toolOutput"] = result_block.content
            tool_results.append(result_block)

        messages.append(ConversationMessage(role="user", content=tool_results))
        await self._save_checkpoint(
            state_machine,
            messages,
            tool_trace,
            completed_steps=completed_steps,
            checkpoint_callback=checkpoint_callback,
        )
        return completed_steps

    def _find_or_create_trace_item(
        self,
        tool_trace: list[dict],
        *,
        tool_use_id: str,
        tool_name: str,
        tool_input: dict,
        turn: int,
    ) -> dict:
        for item in tool_trace:
            if item.get("toolUseId") == tool_use_id:
                return item
        item = {
            "toolUseId": tool_use_id,
            "toolName": tool_name,
            "toolInput": tool_input,
            "status": "started",
            "turn": turn,
        }
        tool_trace.append(item)
        return item

    async def _execute_tool(self, tool_name: str, tool_use_id: str, tool_input: dict) -> ToolResultBlock:
        tool = self.tool_registry.get(tool_name)
        if tool is None:
            return ToolResultBlock(
                tool_use_id=tool_use_id,
                content=f"Unknown tool: {tool_name}",
                is_error=True,
            )
        try:
            parsed_input = tool.input_model.model_validate(tool_input)
            result = await tool.execute(parsed_input, ToolPlanToolExecutionContext(cwd=self.cwd))
            return ToolResultBlock(
                tool_use_id=tool_use_id,
                content=result.output,
                is_error=result.is_error,
            )
        except Exception as exc:
            return ToolResultBlock(
                tool_use_id=tool_use_id,
                content=f"Tool {tool_name} failed: {type(exc).__name__}: {exc}",
                is_error=True,
            )

    def _restore_state_machine(self, payload: dict | None) -> TheseusStateMachine:
        state_machine = TheseusStateMachine(initial_mode=AgentMode.PLAN)
        state_machine.mode = AgentMode.PLAN
        state_machine.plan_phase = PlanPhase.DRAFTING
        if payload:
            mode = payload.get("mode")
            phase = payload.get("planPhase")
            if mode:
                state_machine.mode = self._enum_value(AgentMode, mode)
            if phase:
                state_machine.plan_phase = self._enum_value(PlanPhase, phase)
            state_machine.plan = payload.get("plan") or ""
            state_machine.plan_blocks = payload.get("planBlocks") or []
            state_machine.plan_document = payload.get("planDocument")
        return state_machine

    def _restore_messages(self, payload: list[dict] | None) -> list[ConversationMessage]:
        if not payload:
            return []
        return [ConversationMessage.model_validate(message) for message in payload]

    def _restore_tool_trace(self, payload: Any) -> list[dict]:
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def _restore_completed_steps(self, payload: Any) -> int:
        if not isinstance(payload, dict):
            return 0
        try:
            return int(payload.get("completedTurns") or 0)
        except (TypeError, ValueError):
            return 0

    def _dict_or_none(self, value: Any) -> dict | None:
        return value if isinstance(value, dict) else None

    def _list_or_empty(self, value: Any) -> list:
        return value if isinstance(value, list) else []

    async def _save_checkpoint(
        self,
        state_machine: TheseusStateMachine,
        messages: list[ConversationMessage],
        tool_trace: list[dict],
        *,
        completed_steps: int,
        checkpoint_callback: CheckpointCallback | None,
    ) -> None:
        if checkpoint_callback is None:
            return
        payload = self._checkpoint_payload(state_machine, messages, tool_trace, completed_steps)
        result = checkpoint_callback(payload)
        if result is not None:
            await result

    def _checkpoint_payload(
        self,
        state_machine: TheseusStateMachine,
        messages: list[ConversationMessage],
        tool_trace: list[dict],
        completed_steps: int,
    ) -> dict:
        return {
            "stateMachine": self._serialize_state_machine(state_machine),
            "conversation": [message.model_dump(mode="json") for message in messages],
            "toolTrace": tool_trace,
            "progress": {
                "completedTurns": completed_steps,
                "maxTurns": self.max_turns,
            },
        }

    def _serialize_state_machine(self, state_machine: TheseusStateMachine) -> dict:
        return {
            "schemaVersion": 1,
            "mode": state_machine.mode.value,
            "planPhase": state_machine.plan_phase.value if state_machine.plan_phase else None,
            "coordinatorPhase": (
                state_machine.coordinator_phase.value if state_machine.coordinator_phase else None
            ),
            "plan": state_machine.plan,
            "planBlocks": state_machine.plan_blocks,
            "planDocument": self._jsonable(state_machine.plan_document),
        }

    def _jsonable(self, value):
        if value is None:
            return None
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        return value

    def _enum_value(self, enum_cls, value):
        try:
            return enum_cls(value)
        except ValueError:
            return enum_cls[str(value)]

    async def _emit_chunk(self, callback: ChunkCallback | None, content: str) -> None:
        if callback is None or not content:
            return
        result = callback(content)
        if result is not None:
            await result
