# 프로젝트별 역할 기반 툴 가시성 (Project-Scoped Tool Visibility)

> 작성일: 2026-05-08  
> 기준 브랜치: `temp_di`  
> 변경 범위: `theseus_engine` 패키지 한정 (Java/Spring 영역 제외)

---

## 1. 목표

회사(조직) → 프로젝트 구조에서 **접속 사용자에게 보이는 툴이 프로젝트·역할에 따라 달라지도록** 에이전트 코어를 준비한다.

| 시나리오 | 기대 동작 |
|----------|----------|
| 프로젝트 A의 ADMIN | 코어 툴 전체 + 프로젝트 A 커스텀 툴 + `create_tool` 사용 가능 |
| 프로젝트 A의 MEMBER | 코어 툴 전체 + 프로젝트 A 커스텀 툴 (RBAC 레벨 내) |
| 프로젝트 B의 MEMBER | 코어 툴 전체 + 프로젝트 B 커스텀 툴 (A 툴 안 보임) |
| Standalone CLI 사용자 | 기존 동작 유지 (`custom_tools/` 전체 로드) |

---

## 2. 구현 항목

### 2.1 `theseus_engine/models/runtime_mode.py` (신규)

- `RuntimeMode` enum: `STANDALONE` / `SERVER`
- `detect_runtime_mode(project_id, actor_user_id)` 함수
- 우선순위: 환경변수 `THESEUS_RUNTIME_MODE` > 컨텍스트 파라미터 > 폴백 STANDALONE

### 2.2 `theseus_engine/models/permission_provider.py` (신규)

- `ToolPermissionProvider` ABC
  - `get_permissions() -> dict[str, int]`
  - `get_disabled_tools() -> set[str]`
  - `sync_tool(tool_name, permission_level, meta)` — 생성/갱신 후 소스 동기화
- `StandalonePermissionProvider` — `.meta.json` 파일 스캔
- `ServerPermissionProvider` — 콜백 함수 주입 방식 (src/auth 위임)

### 2.3 `theseus_engine/tools/core/tool_factory.py` (수정)

- `load_custom_tools_for_project(registry, project_id, tool_permissions)` 함수 추가
  - 경로: `custom_tools/projects/<project_id>/*.py`
  - 조건: `isActive=True` && `status="active"` 인 것만 로드
- `normalize_tool_meta()` — `runtimeMode` 필드 추가

### 2.4 `theseus_engine/tools/core/__init__.py` (수정)

- `load_custom_tools_for_project` export 추가

### 2.5 `theseus_engine/core/engine_builder.py` (수정)

- `setup_engine()` 파라미터 추가:
  - `project_id: str | None = None`
  - `actor_role: str = "MEMBER"`
  - `project_disabled_tools: set | None = None`
- 툴 로딩 분기: `project_id` 유무에 따라 global / project-scoped 로더 선택
- `create_tool` 제외 로직: `ADMIN` + `PLAN EXECUTING` 일 때만 허용
- `project_disabled_tools`를 `exclude_tools`에 합산

---

## 3. 하위 호환

- 모든 신규 파라미터에 기본값 설정 → 기존 `theseus_cli.py`, `tui_main.py` 호출 변경 없음
- `StandalonePermissionProvider`는 기존 `load_custom_tools` 경로와 동일 동작
- `ServerPermissionProvider`는 콜백 주입 방식이므로 `src/auth/permissions.py` 코드 변경 불필요

---

## 4. 체크리스트

- [x] `runtime_mode.py` — enum + detect 함수 ✅ Session 40
- [x] `permission_provider.py` — ABC + Standalone + Server 구현 ✅ Session 40
- [x] `tool_factory.py` — `load_custom_tools_for_project` + `runtimeMode` 필드 ✅ Session 40
- [x] `__init__.py` — export 추가 ✅ Session 40
- [x] `engine_builder.py` — 파라미터 확장 + 분기 로직 ✅ Session 40
- [x] CHANGELOG 업데이트 ✅ Session 40

---

## 5. 서버 연결 (참고 — 본 작업 범위 밖)

`src/builder/engine.py`가 `setup_engine()`에 아래 값을 주입하면 서버 경로 연결 완료:

```python
await setup_engine(
    ...,
    project_id=build_context.project_id,
    actor_role=build_context.actor_role,         # JWT claim
    project_disabled_tools=disabled_tools,         # Spring API 응답
)
```

Spring Backend `project_tools` 테이블 + REST API는 별도 계획.
