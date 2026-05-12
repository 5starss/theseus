"""JSON Lines runner for editor integrations."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any

from theseus_engine.runner_runtime import EditorRuntime


async def _read_stdin_line() -> str:
    return await asyncio.to_thread(sys.stdin.readline)


def emit(payload: dict[str, Any]) -> None:
    sys.__stdout__.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.__stdout__.flush()


def _permission_request_id() -> str:
    return f"perm-{int(time.time() * 1000)}-{secrets.token_hex(4)}"


def _permission_response_decision(
    payload: dict[str, Any],
    request_id: str,
) -> bool | None:
    if payload.get("type") != "PermissionResponse":
        return None
    payload_request_id = payload.get("request_id") or payload.get("requestId")
    if payload_request_id and str(payload_request_id) != request_id:
        return None
    approved = payload.get("approved")
    if isinstance(approved, bool):
        return approved
    decision = str(payload.get("decision", "")).strip().lower()
    if decision in {"approve", "approved", "allow", "allowed", "yes", "y", "true"}:
        return True
    if decision in {"deny", "denied", "reject", "rejected", "no", "n", "false"}:
        return False
    return False


async def run_json_mode(args: argparse.Namespace) -> int:
    model_name = os.getenv("THESEUS_MODEL") or os.getenv("OPENHARNESS_MODEL") or args.model

    async def permission_prompt(tool_name: str, prompt_msg: str) -> bool:
        request_id = _permission_request_id()
        emit(
            {
                "type": "PermissionRequest",
                "request_id": request_id,
                "tool_name": tool_name,
                "message": prompt_msg,
            }
        )
        while True:
            line = await _read_stdin_line()
            if line == "":
                return False
            stripped = line.lstrip("\ufeff").strip()
            if not stripped:
                continue
            if stripped.startswith("{"):
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    payload = None
                if isinstance(payload, dict):
                    decision = _permission_response_decision(payload, request_id)
                    if decision is not None:
                        return decision
            raw_lower = stripped.strip("\"'").lower()
            if raw_lower in {"yes", "y", "approve", "allow"}:
                return True
            if raw_lower in {"no", "n", "deny", "reject"}:
                return False

    runtime = EditorRuntime(
        model=model_name,
        user_level=args.user_level,
        cwd=Path.cwd(),
        permission_prompt=permission_prompt,
    )
    for event in await runtime.initialize():
        emit(event)

    while True:
        line = await _read_stdin_line()
        if line == "":
            break
        async for event in runtime.submit(line):
            emit(event)
            if event.get("type") == "RunnerStopped":
                return 0
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Theseus JSON Lines runner")
    parser.add_argument("--json-mode", action="store_true", help="emit StreamEvents as JSON Lines")
    parser.add_argument("--model", default="google/gemini-3.1-pro-preview-customtools")
    parser.add_argument("--user-level", type=int, default=5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.json_mode:
        print("Only --json-mode is supported.", file=sys.stderr)
        return 2
    return asyncio.run(run_json_mode(args))


if __name__ == "__main__":
    raise SystemExit(main())
