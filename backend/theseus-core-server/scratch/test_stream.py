import asyncio
import json
from src.auth.schemas import SessionContext
from src.routes.stream import stream_agent_response

async def mock_billing_report_usage(report):
    print(f"Mock Billing: {report}")

class MockBackgroundTasks:
    def add_task(self, func, *args, **kwargs):
        print(f"Background task added: {func.__name__}")

async def test_stream_theseus_engine():
    session = SessionContext(
        user_id="test_user",
        project_id="test_project",
        permission_level=1,
        token="mock_token"
    )
    prompt = "Hello"
    background_tasks = MockBackgroundTasks()

    print("--- Starting Stream (Theseus Engine Case) ---")
    async for event_str in stream_agent_response(session, prompt, background_tasks):
        print(event_str)
    print("--- Stream Finished ---")

if __name__ == "__main__":
    asyncio.run(test_stream_theseus_engine())
