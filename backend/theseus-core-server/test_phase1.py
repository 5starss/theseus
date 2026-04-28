import asyncio
import os
import sys
from pathlib import Path

# `.env` 파일 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv 패키지가 설치되지 않았습니다. pip install python-dotenv를 실행하세요.")
    sys.exit(1)

# LangSmith 환경변수 체크
if not os.getenv("LANGCHAIN_API_KEY"):
    print("경고: LANGCHAIN_API_KEY가 설정되지 않아 LangSmith 추적이 작동하지 않을 수 있습니다.")

try:
    from openharness.engine.query_engine import QueryEngine
    from openharness.api.openai_client import OpenAICompatibleClient
    from openharness.permissions.checker import PermissionChecker
    from openharness.tools.base import ToolRegistry
    from openharness.engine.stream_events import (
        AssistantTextDelta,
        ToolExecutionStarted,
        ToolExecutionCompleted,
        ErrorEvent,
        StatusEvent
    )
except ImportError as e:
    print(f"OpenHarness를 불러올 수 없습니다 (상세 에러: {e}). 프로젝트 폴더에서 `pip install -e ./OpenHarness`를 실행하여 설치해주세요.")
    sys.exit(1)


async def main():
    print("🚀 [Phase 1] OpenHarness 래핑 및 스트리밍 출력 테스트 시작\n")

    # 1. API 클라이언트 설정
    model_name = os.getenv("OPENHARNESS_MODEL", "gpt-4o")
    print(f"사용 모델: {model_name}")
    
    # OpenAICompatibleClient를 기본으로 사용합니다.
    # 만약 Anthropic을 사용한다면 openharness.api.client의 AnthropicApiClient를 사용하시면 됩니다.
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # 다른 키(예: OLLAMA 등 로컬)를 사용할 경우를 위해 임시 처리
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("GEMINI_API_KEY") or "dummy-key-for-local"

    base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OLLAMA_BASE_URL")

    # Gemini 모델을 사용하고 base_url이 없는 경우, Gemini의 OpenAI 호환 엔드포인트로 자동 매핑합니다.
    if not base_url and "gemini" in model_name.lower():
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    try:
        api_client = OpenAICompatibleClient(api_key=api_key, base_url=base_url)
    except Exception as e:
        print(f"API 클라이언트 초기화 실패: {e}")
        return

    # 2. 필수 컴포넌트 초기화
    from openharness.config import load_settings
    settings = load_settings()
    
    # ToolRegistry는 빈 상태로 시작 (Phase 2에서 채움)
    tool_registry = ToolRegistry()
    permission_checker = PermissionChecker(settings=settings)
    system_prompt = """You are a helpful AI assistant running inside the Theseus Core Engine.
Your goal is to assist the user. Keep your responses clear and concise.
"""

    # 3. QueryEngine 인스턴스 생성
    engine = QueryEngine(
        api_client=api_client,
        tool_registry=tool_registry,
        permission_checker=permission_checker,
        cwd=Path.cwd(),
        model=model_name,
        system_prompt=system_prompt,
        max_turns=3
    )

    test_prompt = "안녕하세요! Theseus 시스템의 코어 엔진이 잘 작동하는지 확인하기 위해 짧은 인사말을 남겨주세요."
    print(f"User: {test_prompt}\n")
    print("Assistant (Streaming):", end=" ", flush=True)

    # 4. 모의 스트리밍 출력 확인
    try:
        async for event in engine.submit_message(test_prompt):
            if isinstance(event, AssistantTextDelta):
                # 텍스트 청크 출력
                print(event.text, end="", flush=True)
            elif isinstance(event, ToolExecutionStarted):
                print(f"\n[Tool Started: {event.tool_name}]", end=" ", flush=True)
            elif isinstance(event, ToolExecutionCompleted):
                print(f"[Tool Completed: {event.tool_name}]", end=" ", flush=True)
            elif isinstance(event, StatusEvent):
                print(f"\n[Status: {event.message}]", end=" ", flush=True)
            elif isinstance(event, ErrorEvent):
                print(f"\n[Error: {event.message}]", end=" ", flush=True)
        print("\n\n✅ 스트리밍이 성공적으로 완료되었습니다.")
        print(f"사용한 토큰/비용 현황: {engine.total_usage}")
    except Exception as e:
        print(f"\n❌ 실행 중 에러 발생: {e}")

if __name__ == "__main__":
    # 윈도우 환경에서 asyncio 루프 에러 방지용
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
