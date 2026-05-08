"""Theseus TUI 모달 위젯 모음.

현재 구현:
  - SecurityApprovalModal : 파괴적 툴 실행 전 HITL 보안 승인 팝업
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class SecurityApprovalModal(ModalScreen[str]):
    """파괴적 툴 실행 전 사용자 승인을 요청하는 모달 팝업.

    Returns:
        "approve"       — 이번 한 번만 승인
        "approve_all"   — 세션 동안 항상 승인
        "deny"          — 거부
    """

    BINDINGS = [
        Binding("y", "approve", "승인", show=True),
        Binding("a", "approve_all", "항상 승인", show=True),
        Binding("n", "deny", "거부", show=True),
        Binding("escape", "deny", show=False),
    ]

    DEFAULT_CSS = """
    SecurityApprovalModal {
        align: center middle;
    }

    #modal-container {
        width: 70;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }

    #modal-title {
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }

    #modal-tool-name {
        text-style: bold;
        color: $accent;
    }

    #modal-input-box {
        background: $panel;
        border: solid $primary;
        padding: 0 1;
        margin: 1 0;
        max-height: 8;
        overflow-y: auto;
    }

    #modal-hint {
        color: $text-muted;
        margin-top: 1;
    }

    #button-row {
        align: center middle;
        height: 3;
        margin-top: 1;
    }

    Button {
        margin: 0 1;
        min-width: 16;
    }

    #btn-approve    { variant: success; }
    #btn-approve-all { variant: warning; }
    #btn-deny       { variant: error; }
    """

    def __init__(self, tool_name: str, tool_input: dict) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.tool_input = tool_input

    def compose(self) -> ComposeResult:
        # 입력값 요약 (긴 경우 잘라냄)
        input_preview = _format_tool_input(self.tool_input, max_chars=300)

        with Vertical(id="modal-container"):
            yield Label("⚠️  보안 승인 요청", id="modal-title")
            yield Label(f"툴: {self.tool_name}", id="modal-tool-name")
            yield Static(input_preview, id="modal-input-box")
            yield Label(
                "[y] 승인  [a] 항상 승인  [n] 거부  [Esc] 거부",
                id="modal-hint",
            )
            with Horizontal(id="button-row"):
                yield Button("[y] 승인", id="btn-approve", variant="success")
                yield Button("[a] 항상 승인", id="btn-approve-all", variant="warning")
                yield Button("[n] 거부", id="btn-deny", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        mapping = {
            "btn-approve":     "approve",
            "btn-approve-all": "approve_all",
            "btn-deny":        "deny",
        }
        self.dismiss(mapping.get(event.button.id, "deny"))

    def action_approve(self)     -> None: self.dismiss("approve")
    def action_approve_all(self) -> None: self.dismiss("approve_all")
    def action_deny(self)        -> None: self.dismiss("deny")


# ── 헬퍼 ─────────────────────────────────────────────────────────

def _format_tool_input(tool_input: dict, max_chars: int = 300) -> str:
    """tool_input dict를 사람이 읽기 좋은 텍스트로 변환합니다."""
    import json
    try:
        text = json.dumps(tool_input, ensure_ascii=False, indent=2)
    except Exception:
        text = str(tool_input)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n…(생략)"
    return text
