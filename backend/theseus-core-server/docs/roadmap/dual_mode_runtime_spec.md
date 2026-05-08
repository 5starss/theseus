# Dual-Mode Runtime 명세

## Standalone vs Server-Connected 모드 분기 설계

> 작성일: 2026-05-07  
> 기준 코드: `temp_di` 브랜치

---

## 1. 개요

Theseus는 두 가지 배포 형태로 실행된다.

| 구분 | Standalone (CLI) | Server-Connected |
|------|-----------------|-----------------|
| 진입점 | `theseus_cli.py`, `cli_main.py` | `src/routes/stream.py` (FastAPI SSE) |
| 인증 | 없음 (로컬 사용자) | Spring Boot JWT → `SessionContext` |
| 권한 소스 | `theseus_engine/custom_tools/*.meta.json` + 파일시스템 | DB (Spring Backend) + `src/auth/permissions.py` |
| 툴 저장 위치 | `theseus_engine/custom_tools/` | `theseus_engine/custom_tools/projects/<project_id>/` |
| 툴 생성 파이프라인 | `tool_factory.py` (단순: 코드 검증 → 저장) | `src/tooling/service.py` (계획 가드 → 검증 → 샌드박스 → 활성화) |
| 메타 관리 | local `.meta.json` | local `.meta.json` + DB 레코드 (예정) |
| RBAC 체커 | `TheseusPermissionChecker` (파일 기반 level) | `TheseusPermissionChecker` (DB 조회 level) |

현재 `engine_builder.py`(standalone)와 `src/builder/engine.py`(server)가 완전히 별도로 존재하지만,  
**모드 감지 → 공통 인터페이스 → 모드별 구현체** 구조가 없어서 로직 중복과 동작 불일치가 발생한다.

---

## 2. 핵심 분기 지점

### 2-1. 권한(Permission) 소스

```
Standalone:
  tool_permissions = {tool.name: tool.permission_level}  ← .py 클래스 속성

Server-Connected:
  tool_permissions = await get_project_tool_permissions(project_id, user_id)
                   ← Spring Backend API 호출 (또는 DB 직접 조회)
```

- Standalone은 `.meta.json`의 `permissionLevel`이나 `.py` 클래스의 `permission_level`을 source of truth로 사용
- Server-Connected는 DB에 저장된 툴 레코드의 `permissionLevel`이 source of truth
- **문제**: 같은 툴이라도 환경에 따라 레벨이 달라질 수 있고, 현재 이 차이를 시스템이 감지하지 못함

### 2-2. 툴 로딩 경로

```
Standalone:    load_custom_tools(registry, tool_permissions)
                → custom_tools/*.py 스캔
                → .meta.json 정규화

Server:        load_custom_tools_for_project(registry, project_id=..., tool_permissions=...)
                → custom_tools/projects/<project_id>/*.meta.json 스캔
                → isActive=True && sandboxResult.success=True 인 것만 로드
```

### 2-3. 툴 생성(create_tool) 파이프라인

```
Standalone:    ToolCreatorTool._execute_legacy()
                단계: 네이밍 → 권한 주입 → 문법 검증 → 저장 → 런타임 등록

Server:        create_tool_for_server(ServerToolCreationRequest)
                단계: 플랜 가드 → 초안 저장 → 검증 → 샌드박스 → 활성화 → 런타임 등록
```

### 2-4. 민감 툴 HITL(Human-In-The-Loop)

```
Standalone:    require_human_confirm=False (CLI에서 직접 확인 프롬프트)
Server:        require_human_confirm=False + approval_policy="reject"
               → permission_prompt가 항상 False 반환 (_deny_permission_prompt)
```

---

## 3. 모드 감지 설계

### 3-1. `RuntimeMode` 열거형 (신규)

**위치**: `theseus_engine/models/runtime_mode.py`

```python
from enum import Enum

class RuntimeMode(str, Enum):
    STANDALONE = "standalone"   # CLI, 로컬 파일시스템 기반
    SERVER     = "server"       # FastAPI SSE, DB 기반
```

### 3-2. 감지 규칙

우선순위 순서:

1. **명시적 환경변수** `THESEUS_RUNTIME_MODE=standalone|server`
2. **서버 컨텍스트 존재 여부**: `EngineBuildContext.project_id is not None`
3. **폴백**: `standalone`

```python
# theseus_engine/models/runtime_mode.py

def detect_runtime_mode(
    project_id: str | None = None,
    actor_user_id: str | None = None,
) -> RuntimeMode:
    env = os.getenv("THESEUS_RUNTIME_MODE", "").lower()
    if env in ("standalone", "server"):
        return RuntimeMode(env)
    if project_id is not None and actor_user_id is not None:
        return RuntimeMode.SERVER
    return RuntimeMode.STANDALONE
```

---

## 4. 공통 인터페이스 — `ToolPermissionProvider`

**위치**: `theseus_engine/models/permission_provider.py`

두 모드가 동일한 인터페이스를 따르면서 내부 구현만 다르게 가져간다.

```python
from abc import ABC, abstractmethod

class ToolPermissionProvider(ABC):
    """툴 권한 맵을 공급하는 추상 인터페이스."""

    @abstractmethod
    async def get_permissions(self) -> dict[str, int]:
        """tool_name → required_level 맵 반환."""

    @abstractmethod
    async def sync_tool(
        self,
        tool_name: str,
        permission_level: int,
        *,
        meta: dict | None = None,
    ) -> None:
        """툴 생성/갱신 후 권한 소스에 변경사항을 반영."""
```

### 4-1. `StandalonePermissionProvider`

**위치**: `theseus_engine/models/permission_provider.py`

```
동작:
- get_permissions(): custom_tools/*.py 클래스 속성 스캔 + .meta.json permissionLevel 합산
- sync_tool(): .meta.json 의 permissionLevel 갱신 (normalize_tool_meta 호출)
- DB 없음, 네트워크 없음
```

### 4-2. `ServerPermissionProvider`

**위치**: `theseus_engine/models/permission_provider.py`

```
동작:
- get_permissions(): Spring Backend API 호출 (src/auth/permissions.py → permission_client)
  실패 시 캐시된 값 또는 .meta.json 폴백
- sync_tool(): DB 레코드 업데이트 요청 (Spring Backend REST API)
  실패 시 .meta.json에만 로컬 기록 후 재시도 큐에 추가
- 인증: JWT 토큰 (SessionContext.token) 헤더 포함
```

---

## 5. 모드별 동작 명세

### 5-1. 세션 시작 시 툴 로딩

| 단계 | Standalone | Server |
|------|-----------|--------|
| 1. 권한 맵 조회 | `StandalonePermissionProvider.get_permissions()` | `ServerPermissionProvider.get_permissions()` |
| 2. 기본 툴 등록 | `ALL_CORE_TOOLS` 전체 | `ALL_CORE_TOOLS` 전체 |
| 3. 커스텀 툴 로딩 | `load_custom_tools()` (로컬 `.py` 스캔) | `load_custom_tools_for_project()` (project_id 기반) |
| 4. 동적 툴 선택 | `ToolRetriever.retrieve_top_k()` | `ToolRetriever.retrieve_top_k()` |
| 5. RBAC 필터 | `build_filtered_registry(user_level=로컬 레벨)` | `build_filtered_registry(user_level=DB 레벨)` |

### 5-2. 툴 생성 (`create_tool`)

| 단계 | Standalone | Server |
|------|-----------|--------|
| 플랜 가드 | 없음 | `assert_plan_execution_context()` (DB) |
| 코드 저장 경로 | `custom_tools/<name>.py` | `custom_tools/projects/<project_id>/<name>.py` |
| 검증 | `ToolValidator` (로컬) | `ToolValidator` (로컬) |
| 샌드박스 | 없음 | `run_tool_sandbox_gate()` (Docker) |
| 활성화 조건 | 검증 통과 즉시 | 검증 + 샌드박스 통과 시 |
| 메타 저장 | `.meta.json` (로컬) | `.meta.json` + DB 레코드 (Spring Backend) |
| 권한 동기화 | `StandalonePermissionProvider.sync_tool()` | `ServerPermissionProvider.sync_tool()` |
| 런타임 등록 | `full_registry` + `active_registry` 즉시 | `full_registry` + `active_registry` 즉시 |

### 5-3. RBAC 평가

| 항목 | Standalone | Server |
|------|-----------|--------|
| `user_level` 소스 | 로컬 설정 (기본값 1 또는 env) | `SessionContext.permission_level` (DB) |
| `tool_permissions` 소스 | `.py` 클래스 속성 + `.meta.json` | Spring Backend API |
| HITL 프롬프트 | `custom_permission_prompt()` (CLI stdin) | `_deny_permission_prompt()` (항상 거부) |
| 민감 툴 처리 | `require_human_confirm=True` → CLI 확인 | `approval_policy="reject"` → 자동 거부 |

### 5-4. 세션 히스토리

| 항목 | Standalone | Server |
|------|-----------|--------|
| 저장 위치 | `.theseus_sessions/<name>.json` | DB (`src/history/service.py`) |
| 로드 함수 | `load_session_history()` | `load_history_messages()` |
| 저장 함수 | `save_session_history()` | `persist_user_message()` + `persist_assistant_message()` |

---

## 6. `engine_builder.py` 통합 방향

현재 standalone용 `theseus_engine/core/engine_builder.py`와 server용 `src/builder/engine.py`가 완전히 분리되어 있다.  
두 파일을 즉시 병합하면 리스크가 크므로, **점진적 수렴** 방식을 택한다.

### 단계 1 — `RuntimeMode` 및 `ToolPermissionProvider` 추가 (즉시)

```
신규 파일:
  theseus_engine/models/runtime_mode.py
  theseus_engine/models/permission_provider.py
```

`engine_builder.py`의 `setup_engine()`에 `runtime_mode` 파라미터 추가:

```python
async def setup_engine(
    sm: TheseusStateMachine,
    user_level: int,
    project_tool_permissions: dict,
    permission_prompt_func,
    runtime_mode: RuntimeMode = RuntimeMode.STANDALONE,   # 추가
    permission_provider: ToolPermissionProvider | None = None,  # 추가
    ...
)
```

- `permission_provider=None` → `detect_runtime_mode()`로 자동 감지, 적절한 구현체 생성
- 기존 코드는 모두 `RuntimeMode.STANDALONE` 경로로 동작 — **하위 호환 유지**

### 단계 2 — `ServerPermissionProvider` DB 조회 연결 (중기)

- `src/auth/permissions.py`의 `get_project_tool_permissions()`를 `ServerPermissionProvider.get_permissions()`로 위임
- `src/builder/engine.py`의 `get_query_engine()`이 `ServerPermissionProvider`를 생성해 `setup_engine()`에 주입

### 단계 3 — `src/builder/engine.py` 로직을 `setup_engine()`으로 흡수 (장기)

- `get_query_engine()`은 `EngineBuildContext` → `setup_engine()` 호출로 얇아짐
- OH `QueryEngine` 분리 완료 후 가능

---

## 7. 메타데이터 스키마 — 모드별 확장 필드

현재 canonical 스키마(`normalize_tool_meta` 기준)에 서버 모드 전용 필드가 추가된다.

```jsonc
{
  // ── Standalone + Server 공통 ──────────────────────────
  "toolName":        "internet_speed_tool",
  "moduleName":      "internet_speed_tool",
  "projectId":       "local",          // server: 실제 project_id
  "chatSessionId":   null,             // server: int
  "creatorUserId":   "cli_user",       // server: 실제 user_id
  "planId":          null,             // server: plan UUID
  "fileName":        "internet_speed_tool.py",
  "createdAt":       "2026-05-07T...",
  "updatedAt":       "2026-05-07T...",
  "permissionLevel": 1,
  "status":          "active",
  "isActive":        true,
  "validationResult": { ... },

  // ── Server 전용 (standalone에서는 null) ───────────────
  "sandboxResult":   null,             // server: Docker sandbox 결과
  "approvalHistory": null,             // server: plan 승인 이력
  "latestTraceId":   null,             // server: 감사 추적 ID
  "activatedAt":     null,             // server: 활성화 시각
  "dbSyncedAt":      null,             // server: DB 동기화 시각
  "runtimeMode":     "standalone"      // "standalone" | "server"
}
```

`normalize_tool_meta()`는 `runtimeMode` 필드를 채워 추후 어느 환경에서 생성됐는지 구분 가능하게 한다.

---

## 8. DB 툴 테이블 설계 (서버 모드 신규)

Spring Backend에 아래 테이블이 필요하다. AI 서버에서 직접 쓰지 않고  
**Spring Backend REST API를 통해서만 읽기/쓰기**한다.

```sql
CREATE TABLE project_tools (
    id               BIGSERIAL PRIMARY KEY,
    project_id       VARCHAR(36)  NOT NULL,
    tool_name        VARCHAR(64)  NOT NULL,
    module_name      VARCHAR(128) NOT NULL,
    permission_level SMALLINT     NOT NULL DEFAULT 1,
    status           VARCHAR(32)  NOT NULL DEFAULT 'active',
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    creator_user_id  VARCHAR(255) NOT NULL,
    plan_id          VARCHAR(36),
    chat_session_id  INTEGER,
    file_path        TEXT,
    metadata         JSONB,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, tool_name)
);
```

AI 서버가 Spring에 요청하는 API:

| 메서드 | 경로 | 용도 |
|--------|------|------|
| `GET`  | `/api/projects/{project_id}/tools` | 프로젝트 툴 목록 + 권한 맵 조회 |
| `POST` | `/api/projects/{project_id}/tools` | 툴 생성 등록 |
| `PATCH`| `/api/projects/{project_id}/tools/{tool_name}` | 상태/권한 레벨 변경 |
| `GET`  | `/api/projects/{project_id}/tools/permissions` | `{tool_name: level}` 맵만 반환 |

---

## 9. 구현 우선순위

```
P0 (즉시) ─────────────────────────────────────────────────
  ① runtime_mode.py — RuntimeMode enum + detect_runtime_mode()
  ② permission_provider.py — 추상 인터페이스 + StandalonePermissionProvider
  ③ engine_builder.py에 runtime_mode 파라미터 추가 (기본값: STANDALONE)

P1 (단기) ─────────────────────────────────────────────────
  ④ ServerPermissionProvider 구현
       - get_permissions() → src/auth/permissions.py 위임
       - sync_tool() → Spring PATCH API 호출 (실패 시 로컬 기록)
  ⑤ normalize_tool_meta()에 runtimeMode 필드 추가
  ⑥ create_tool 파이프라인에서 permission_provider.sync_tool() 호출

P2 (중기) ─────────────────────────────────────────────────
  ⑦ src/builder/engine.py → ServerPermissionProvider 주입
  ⑧ Spring Backend project_tools 테이블 + API 엔드포인트
  ⑨ ServerPermissionProvider.get_permissions() 캐시 레이어 (TTL 30s)

P3 (장기) ─────────────────────────────────────────────────
  ⑩ src/builder/engine.py 로직을 setup_engine()으로 흡수
  ⑪ 세션 히스토리 공통 인터페이스 (SessionHistoryProvider)
```

---

## 10. 파일 변경 요약

```
신규:
  theseus_engine/models/runtime_mode.py
  theseus_engine/models/permission_provider.py

수정:
  theseus_engine/core/engine_builder.py   ← runtime_mode 파라미터, provider 주입
  theseus_engine/tools/core/tool_factory.py  ← sync_tool() 호출 (P1)
  src/builder/engine.py                   ← ServerPermissionProvider 주입 (P1)

미정 (Spring Backend):
  project_tools 테이블 마이그레이션
  /api/projects/{id}/tools/* REST API
```
