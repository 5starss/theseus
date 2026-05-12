# Multi-User Server 아키텍처

## 개요

theseus_engine은 세 가지 배포 형태를 지원한다.

| 모드 | 사용 환경 | 진입점 |
|------|----------|--------|
| **Standalone** | 로컬 단일 사용자 (서버 없음) | CLI (`theseus_cli.py`) / TUI (`tui_main.py`) |
| **Hybrid** | 에이전트는 사용자 PC에서 실행, 백엔드 서버에서 설정 fetch | CLI / TUI + `THESEUS_SERVER_URL` 설정 |
| **Server** | 에이전트가 서버 위에서 실행 (B2B 멀티유저) | FastAPI (`src/main.py`) ← Java Spring Boot 제어 |

---

## Hybrid 아키텍처 (권장)

Claude Code, Cursor 등 로컬 에이전트 도구들과 동일한 방식이다.
에이전트 코어는 사용자 PC에서 실행되고, 서버는 설정·프로젝트 정보·과금만 담당한다.

```
┌─────────────────────────────────────────────────┐
│  사용자 PC                                       │
│                                                  │
│  theseus_cli.py / tui_main.py                    │
│    ├── TheseusProjectClient.fetch_project_config │
│    │      ← 서버에서 tool_permissions, role 수신  │
│    ├── setup_engine(user_level, tool_perms, ...)  │
│    │      → 로컬 파일에 직접 접근 (no SSH 필요)   │
│    └── 턴 완료 후 sync_history / report_usage     │
│           → 서버에 이력 + 과금 데이터 전송        │
└─────────────────────────────────────────────────┘
         ↕  HTTPS (THESEUS_SERVER_URL)
┌─────────────────────────────────────────────────┐
│  Java Spring Boot 백엔드                         │
│    - 인증 / 프로젝트 설정 API                    │
│    - 대화 이력 저장 (DB)                         │
│    - 토큰 과금 집계                              │
└─────────────────────────────────────────────────┘
```

### 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `THESEUS_SERVER_URL` | 백엔드 서버 URL. 미설정 시 standalone 모드 | `""` |
| `THESEUS_PROJECT_ID` | 프로젝트 식별자 | `"local"` |
| `THESEUS_SESSION_TOKEN` | Spring Boot 발급 JWT 토큰 | `""` |

### ProjectClient 동작 원리

```python
# THESEUS_SERVER_URL 설정 시 서버에서 프로젝트 설정 로드
config = await init_project_session(project_id, token=jwt_token)
# setup_engine에 서버 설정 주입
engine, registry = await setup_engine(
    sm=sm, user_level=config.user_level, actor_role=config.actor_role,
    project_tool_permissions=config.tool_permissions,
)
# 턴 완료 후 서버 동기화
await client.sync_history(config.session_id, engine.messages, token=jwt_token)
await client.report_usage(config.session_id, {"inputTokens": ..., "outputTokens": ...})
```

`THESEUS_SERVER_URL`이 설정되어 있지 않으면 모든 `ProjectClient` 메서드가 no-op으로 동작하여
standalone 모드와 완전히 하위 호환된다.

---

## 서버 모드 구조 (에이전트가 서버에서 실행)

```
클라이언트들 (브라우저 / IDE)
       │  SSE 연결
       ▼
FastAPI (src/main.py)
  - Spring Boot 세션 토큰 검증
  - user_level, project_id 파싱
       │
       ▼  요청마다 새 인스턴스
setup_engine(
    project_id="backend-team",
    cwd=Path("/workspaces/backend-team"),
    run_id="...",
)
       │
       ▼
theseus_engine (QueryEngine)
  - LLM 실행
  - Tool 실행 (cwd 범위 내)
  - StreamEvent yield
```

---

## 사용자별 워크스페이스 격리

### 원칙

**서버 모드**: 에이전트는 서버 위에서 실행된다. 사용자의 로컬 파일에 직접 접근할 수 없으며,
서버에 마련된 사용자별 격리 디렉토리에서만 동작한다.

**Hybrid 모드**: 에이전트가 사용자 PC에서 실행되므로 로컬 파일에 직접 접근 가능하다.
별도의 workspace 격리 설정 없이 `cwd=None` (→ `Path.cwd()`)으로 동작한다.

```
서버 filesystem
/workspaces/
  ├── project-backend/    ← backend팀 전용
  └── project-frontend/   ← frontend팀 전용
```

### 격리 보장 방식

`setup_engine(cwd=Path("/workspaces/{project_id}"))` 로 주입된 `cwd`가
모든 파일 도구의 보안 검사 기준이 된다.

```python
# file_utils.py
def _check_path_security(path: Path, cwd: Path) -> str | None:
    if not path.is_relative_to(cwd):
        return f"Access denied: {path} is outside workspace {cwd}"
```

`cwd` 밖의 경로 접근은 모든 파일 도구에서 자동으로 차단된다.

### 파일을 서버 워크스페이스로 가져오는 방법

| 방법 | 설명 |
|------|------|
| Git clone | Spring Boot가 repo URL 전달 → Core 서버가 `/workspaces/{project_id}`에 clone |
| 파일 업로드 | FastAPI 업로드 엔드포인트 → workspace에 저장 |
| NFS / 볼륨 마운트 | 인프라 레벨 마운트 |

---

## 요청 스코프 격리

### CostTracker / SessionStats

멀티유저 서버에서 전역 싱글톤을 사용하면 사용자 간 통계/과금이 뒤섞인다.
`setup_engine()`은 항상 새 인스턴스를 생성한다.

```python
# engine_builder.py
tracker = CostTracker()   # 요청마다 새 인스턴스
stats   = SessionStats()  # 동일

if reset_stats:
    # standalone CLI/TUI 전용: 전역 싱글톤도 동기화
    CostTracker._instance  = tracker
    SessionStats._instance = stats
```

standalone에서 `reset_stats=True`로 호출하면 CLI의 `/cost`, `/stats` 명령이
전역 싱글톤을 통해 동일한 인스턴스를 참조한다.

### QueryEngine

`QueryEngine._messages`는 인스턴스 변수이므로 요청마다 새 인스턴스를 생성하면
대화 이력이 자연스럽게 격리된다.

---

## 멀티턴 세션 유지

요청마다 새 `QueryEngine`을 생성하면 이전 대화를 기억하지 못한다.
멀티턴을 지원하려면 세션 이력을 외부에 저장하고 요청마다 복원해야 한다.

```
요청 1 (사용자 A, 세션 S1)
  → 저장소에서 S1 이력 로드 → engine.load_messages(history)
  → 실행 → 이력 저장

요청 2 (사용자 A, 세션 S1)
  → 저장소에서 S1 이력 로드 → 이어서 실행
```

현재 `save_session_history()` / `load_session_history()`는 로컬 파일 기반이다.
서버 모드에서는 Redis 또는 DB 기반 저장소로 교체가 필요하다.

---

## 프로젝트별 툴 격리

```python
# backend팀: bash, read_file, write_file, custom_tools/backend-team/*.py
setup_engine(project_id="backend-team", project_tool_permissions={...})

# frontend팀: 별도 커스텀 툴, 별도 권한
setup_engine(project_id="frontend-team", project_tool_permissions={...})
```

`custom_tools/{project_id}/` 경로에서 해당 팀의 도구만 로드된다.
`project_disabled_tools`로 팀 단위 도구 비활성화도 가능하다.

---

## 배포 모드별 파라미터 비교

| 파라미터 | Standalone | Hybrid | Server |
|---------|-----------|--------|--------|
| `cwd` | `None` (→ `Path.cwd()`) | `None` (→ `Path.cwd()`) | `Path("/workspaces/{project_id}")` |
| `project_id` | `None` | `THESEUS_PROJECT_ID` env | `"backend-team"` 등 |
| `actor_role` | `"ADMIN"` (고정) | 서버에서 fetch | Spring Boot 토큰에서 파싱 |
| `user_level` | `5` (고정) | 서버에서 fetch | Spring Boot 토큰에서 파싱 |
| `reset_stats` | `True` | `True` | `False` |
| `run_id` | `None` | `None` | Kafka runId |
| `tool_draft_id` | `None` | `None` | Kafka toolDraftId |
| 이력 저장 | 로컬 JSON 파일 | 로컬 + 서버 동기화 | Redis / DB |
| 과금 | 로컬 `/cost` 출력 | 서버 `report_usage` 전송 | 서버 집계 |
