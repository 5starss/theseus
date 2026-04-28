# Theseus Agent Execution Guide

## 실행 방법
새롭게 작성된 `theseus_engine/app.py`를 실행하여 안정적인 3-Mode 에이전트를 테스트할 수 있습니다.
터미널에서 아래의 명령어를 입력하세요:

```bash
python theseus_engine/app.py
```

## 주요 기능 및 명령어
실행 후 나타나는 프롬프트에서 아래의 명령어들을 사용할 수 있습니다.

*   `/ask`: 지식 검색 전용 모드 (도구 사용 불가). 단순 질문에 활용하세요.
*   `/agent`: 자율 에이전트 모드 (기본값). 도구를 자유롭게 사용하여 문제를 해결합니다.
*   `/plan`: 복잡한 작업을 위한 Planning 모드로 진입합니다.
*   `/clear`: 현재까지의 대화 내용(Session Memory)을 모두 삭제하고 초기화합니다.
*   `exit` 또는 `quit`: 에이전트를 안전하게 종료하고 현재까지의 대화 내역을 파일(`.theseus_history.json`)에 저장합니다.

## 세션 저장 및 복구 (Session Memory)
이 스크립트는 멀티턴(Multi-turn) 대화를 지원합니다. 
*   대화를 진행할 때마다 자동으로 로컬 파일(`.theseus_history.json`)에 내역을 백업합니다.
*   스크립트를 종료했다가 다시 `python theseus_engine/app.py`를 실행하면, 자동으로 이전 세션의 메시지 기록을 불러와서 컨텍스트를 이어나갈 수 있습니다.

## 안전 장치 (Human-in-the-Loop)
에이전트가 시스템 파일 생성, 수정 등의 민감한 도구를 사용할 때, 화면에 `Allow this action? (y/N):` 프롬프트를 띄워 사용자의 승인을 기다립니다. 허가 시에만 도구가 실행됩니다.
