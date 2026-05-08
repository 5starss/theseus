from textual.binding import Binding

THESEUS_TUI_CSS = """
/* 화면 전체 정렬 속성 제거 (헤더 짤림 방지) */
Screen {
    padding: 0;
}

#app-container {
    width: 100%;
    height: 100%;
}

#main-row {
    height: 100%;
}

#transcript-column {
    width: 1fr;
    height: 100%;
}

#side-column {
    width: 35;
    height: 100%;
    border-left: vkey $accent;
    padding: 0 1;
}

/* 자동완성 드롭다운 전체 창 */
#autocomplete {
    display: none;
    max-height: 8;
    border: solid $accent;
    background: $panel;
    margin: 0 1;
}

#autocomplete > .option-list--option-highlighted {
    background: $accent !important;
    color: $surface !important;
    text-style: bold reverse !important;
}

#autocomplete > .option-list--option-hover {
    background: $accent 50%;
}
"""

THESEUS_BINDINGS = [
    # tui_main.py의 BINDINGS에 직접 정의된 키와 중복되지 않게
    # 확장용 바인딩만 관리 (현재는 빈 목록)
]
